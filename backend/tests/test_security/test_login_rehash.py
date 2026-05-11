"""
End-to-end test for the passlib → argon2 rehash-on-verify shim.

Exercises the full login path: a user whose `password_hash` column
holds a legacy bcrypt hash logs in with their correct password, and
the response's persisted `password_hash` is upgraded to argon2id
without any visible behavior change to the client.

Uses the same engine as `test_client` (via `get_test_engine`) so the
seeded user is visible to the request handler — the project's
default `transactional_db` fixture binds a different in-memory
engine and would isolate the user from the route.
"""

from __future__ import annotations

from typing import Generator

import bcrypt
import pytest
from sqlalchemy.orm import Session, sessionmaker

from backend.orm.user import User
from tests.conftest import get_test_engine


@pytest.fixture
def rehash_db() -> Generator[Session, None, None]:
    """Session bound to the SAME engine as `test_client`. Cleans up
    its own rows so the module-scoped engine doesn't accumulate state
    across tests."""
    engine = get_test_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        # Drop any rows this test created, identified by user_id prefix.
        session.query(User).filter(User.user_id.like("USER-REHASH-%")).delete(synchronize_session=False)
        session.query(User).filter(User.user_id.like("USER-NATIVE-%")).delete(synchronize_session=False)
        session.commit()
        session.close()


def _seed_bcrypt_user(db: Session, username: str, plain_password: str, client_id_assigned: str | None = None) -> User:
    """Create a user whose stored hash mirrors the passlib-era format."""
    legacy_hash = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    assert legacy_hash.startswith("$2"), "fixture must produce a bcrypt hash"
    user = User(
        user_id=f"USER-REHASH-{username.upper()}",
        username=username,
        email=f"{username}@rehash-test.local",
        password_hash=legacy_hash,
        full_name=f"Rehash Test {username}",
        role="admin",
        client_id_assigned=client_id_assigned,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestLoginRehashOnVerify:
    """End-to-end shim contract through the login endpoint."""

    def test_legacy_bcrypt_user_login_upgrades_hash(self, test_client, rehash_db):
        """A legacy bcrypt user logs in successfully. The response is
        a 200 with a JWT; the stored hash is upgraded to argon2id."""
        plain = "rehash-shim-test-2026"
        user = _seed_bcrypt_user(rehash_db, "rehash_legacy_user", plain)
        original_hash = user.password_hash

        resp = test_client.post(
            "/api/auth/login",
            json={"username": "rehash_legacy_user", "password": plain},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("access_token"), "login should return a JWT"

        # Re-load the row from the DB. The shim should have rewritten
        # the stored hash to argon2id during the same login request.
        rehash_db.expire_all()
        refreshed = rehash_db.query(User).filter(User.username == "rehash_legacy_user").first()
        assert refreshed is not None
        assert refreshed.password_hash != original_hash, "hash should have been rewritten"
        assert refreshed.password_hash.startswith("$argon2id$"), refreshed.password_hash

    def test_legacy_user_can_login_again_with_same_password(self, test_client, rehash_db):
        """After the first login upgrades the hash, the user's NEXT login
        with the same plaintext password still succeeds — the new
        argon2id hash is a valid replacement, not a one-shot artifact."""
        plain = "second-login-test"
        _seed_bcrypt_user(rehash_db, "rehash_twice", plain)

        first = test_client.post("/api/auth/login", json={"username": "rehash_twice", "password": plain})
        assert first.status_code == 200

        # Second login uses the now-argon2 hash.
        second = test_client.post("/api/auth/login", json={"username": "rehash_twice", "password": plain})
        assert second.status_code == 200

        # And the stored hash is stable (no further rewrite on a hash that
        # already matches current params).
        rehash_db.expire_all()
        refreshed = rehash_db.query(User).filter(User.username == "rehash_twice").first()
        assert refreshed.password_hash.startswith("$argon2id$")

    def test_argon2_native_user_login_does_not_rehash(self, test_client, rehash_db):
        """A user created post-migration (already argon2id) logs in and
        the stored hash is NOT rewritten — the shim is opportunistic,
        not blanket."""
        from backend.auth.password import hash_password

        plain = "born-argon2"
        native_hash = hash_password(plain)
        user = User(
            user_id="USER-NATIVE-ARGON2",
            username="rehash_native",
            email="native@rehash-test.local",
            password_hash=native_hash,
            full_name="Native Argon2",
            role="admin",
            client_id_assigned=None,
            is_active=True,
        )
        rehash_db.add(user)
        rehash_db.commit()

        resp = test_client.post("/api/auth/login", json={"username": "rehash_native", "password": plain})
        assert resp.status_code == 200

        rehash_db.expire_all()
        refreshed = rehash_db.query(User).filter(User.username == "rehash_native").first()
        # Same exact hash string — no rewrite.
        assert refreshed.password_hash == native_hash

    def test_wrong_password_does_not_rehash(self, test_client, rehash_db):
        """A failed login (wrong password) must NOT touch the stored
        hash. The rehash hook fires only on the successful-verify path."""
        plain = "correct-password"
        user = _seed_bcrypt_user(rehash_db, "rehash_failed_login", plain)
        original_hash = user.password_hash

        resp = test_client.post(
            "/api/auth/login",
            json={"username": "rehash_failed_login", "password": "wrong-password"},
        )
        assert resp.status_code == 401

        rehash_db.expire_all()
        refreshed = rehash_db.query(User).filter(User.username == "rehash_failed_login").first()
        # Legacy bcrypt hash unchanged — failed verify never invoked the rehash.
        assert refreshed.password_hash == original_hash
        assert refreshed.password_hash.startswith("$2")
