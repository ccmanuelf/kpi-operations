"""
DB-backed token revocation tests (Run 7 T1.4, successor to SEC-R5-01/H-1).

The previous blacklist was a module-level in-memory set: revocation was lost
on every restart/redeploy (on Render's free tier the service idles out every
15 minutes, making logout near-cosmetic), was invisible to sibling workers,
and grew without bound. These tests pin the new contract: logout persists a
revocation row in TOKEN_BLACKLIST keyed by the token's jti (with a sha256
fallback for legacy tokens issued before jti existed), authentication
rejects revoked tokens via that table, and expired rows are pruned on
insert — no module-level state anywhere in the path.
"""

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from backend.auth.jwt import blacklist_token, create_access_token, is_token_blacklisted, token_revocation_key
from backend.database import get_db
from backend.orm.token_blacklist import TokenBlacklist


@contextmanager
def _db_session():
    """Session on the SAME test DB the app uses, via its dependency override.

    Importing conftest directly would re-execute it as a second module and
    create a fresh (empty) in-memory engine — the override is the one shared
    handle on the live test database.
    """
    from backend.main import app

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _register_and_login(test_client):
    uid = uuid.uuid4().hex[:8]
    payload = {
        "username": f"blk_{uid}",
        "email": f"blk_{uid}@test.com",
        "password": "SecurePassword123!",  # pragma: allowlist secret
        "full_name": "Blacklist Test User",
    }
    assert test_client.post("/api/auth/register", json=payload).status_code == 201
    login = test_client.post("/api/auth/login", json={"username": payload["username"], "password": payload["password"]})
    assert login.status_code == 200
    return login.json()["access_token"]


class TestDbBackedRevocation:
    def test_logout_rejects_token_and_persists_row(self, test_client):
        """Logout must 401 the token AND write a TOKEN_BLACKLIST row (restart-proof)."""
        token = _register_and_login(test_client)
        headers = {"Authorization": f"Bearer {token}"}

        assert test_client.get("/api/auth/me", headers=headers).status_code == 200
        assert test_client.post("/api/auth/logout", headers=headers).status_code == 200

        response = test_client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401

        # The revocation lives in the database, not in process memory — this
        # row is what survives a restart.
        with _db_session() as db:
            key = token_revocation_key(token)
            row = db.query(TokenBlacklist).filter(TokenBlacklist.jti == key).first()
            assert row is not None
            assert row.expires_at is not None

    def test_tokens_carry_jti_claim(self):
        """New tokens embed a jti so revocation is keyed, not full-token."""
        from jose import jwt as jose_jwt

        from backend.config import settings

        token = create_access_token(data={"sub": "anyone"})
        payload = jose_jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload.get("jti")

    def test_legacy_token_without_jti_still_revocable(self, test_client):
        """Tokens minted before the jti claim fall back to a sha256 digest key."""
        from jose import jwt as jose_jwt

        from backend.config import settings

        expire = datetime.now(tz=timezone.utc) + timedelta(minutes=5)
        legacy = jose_jwt.encode(
            {"sub": "legacy-user", "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )

        with _db_session() as db:
            blacklist_token(db, legacy)
            assert is_token_blacklisted(db, token_revocation_key(legacy))

    def test_expired_rows_pruned_on_insert(self, test_client):
        """Blacklisting prunes rows whose token already expired (no unbounded growth)."""
        with _db_session() as db:
            stale_key = f"stale-{uuid.uuid4().hex}"
            db.add(
                TokenBlacklist(
                    jti=stale_key,
                    expires_at=datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
                )
            )
            db.commit()

            token = create_access_token(data={"sub": "pruner"})
            blacklist_token(db, token)

            assert db.query(TokenBlacklist).filter(TokenBlacklist.jti == stale_key).first() is None
            assert is_token_blacklisted(db, token_revocation_key(token))

    def test_no_module_level_blacklist_state_remains(self):
        """The in-memory set is gone — revocation has no process-local state."""
        from backend.auth import jwt as jwt_module

        assert not hasattr(jwt_module, "_token_blacklist")
