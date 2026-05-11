"""
Contract tests for `backend/auth/password.py`.

These tests pin the migration shim's guarantees: legacy bcrypt hashes
(from the passlib era) MUST keep authenticating, new hashes MUST be
argon2, and `needs_rehash` MUST signal True for any bcrypt or stale-
argon2 stored hash so the login endpoint can transparently upgrade
the user's stored hash on their next successful verify.
"""

from __future__ import annotations

import bcrypt
import pytest

from backend.auth.password import hash_password, needs_rehash, verify_password

# ---------------------------------------------------------------------------
# Hash format / shape
# ---------------------------------------------------------------------------


class TestHashShape:
    def test_new_hashes_are_argon2id(self):
        """All new hashes use argon2id (the OWASP-recommended variant)."""
        digest = hash_password("correct horse battery staple")
        # `argon2-cffi` defaults to id; the prefix encodes that explicitly.
        assert digest.startswith("$argon2id$"), digest

    def test_hash_includes_random_salt(self):
        """Same plaintext hashed twice produces different digests."""
        d1 = hash_password("same-plain")
        d2 = hash_password("same-plain")
        assert d1 != d2, "argon2 hash output must include a random salt"

    def test_hash_is_self_describing(self):
        """Stored hash carries algorithm + parameters; no side channel needed."""
        digest = hash_password("pw")
        # Argon2 PHC format: $argon2id$v=19$m=...,t=...,p=...$salt$digest
        # We don't pin specific parameter values (those track argon2-cffi
        # defaults, which evolve), but the structural markers must hold.
        assert digest.count("$") >= 5
        assert "v=" in digest and "m=" in digest and "t=" in digest and "p=" in digest


# ---------------------------------------------------------------------------
# Round-trip — new format
# ---------------------------------------------------------------------------


class TestArgon2RoundTrip:
    def test_correct_password_verifies(self):
        digest = hash_password("my-password-1234")
        assert verify_password("my-password-1234", digest) is True

    def test_wrong_password_rejected(self):
        digest = hash_password("my-password-1234")
        assert verify_password("my-password-9999", digest) is False

    def test_empty_password_against_valid_hash_rejected(self):
        digest = hash_password("pw")
        assert verify_password("", digest) is False

    def test_unicode_password_round_trip(self):
        """argon2-cffi handles non-ASCII transparently; pin the contract."""
        plain = "🔐 Schrödinger's pässwörd — ünïcødé 漢字"
        digest = hash_password(plain)
        assert verify_password(plain, digest) is True
        assert verify_password(plain + "x", digest) is False


# ---------------------------------------------------------------------------
# Cross-format — legacy bcrypt must still authenticate
# ---------------------------------------------------------------------------


class TestLegacyBcryptCompatibility:
    """The migration's load-bearing guarantee: hashes created in the
    passlib era keep working until they're rehashed on next login."""

    @pytest.fixture
    def legacy_bcrypt_hash(self) -> str:
        """A bcrypt $2b$ hash of 'legacy-pw' — mirrors what the prior
        passlib-backed `get_password_hash` would have produced."""
        return bcrypt.hashpw(b"legacy-pw", bcrypt.gensalt(rounds=12)).decode("utf-8")

    def test_legacy_bcrypt_correct_password_verifies(self, legacy_bcrypt_hash):
        assert verify_password("legacy-pw", legacy_bcrypt_hash) is True

    def test_legacy_bcrypt_wrong_password_rejected(self, legacy_bcrypt_hash):
        assert verify_password("wrong-pw", legacy_bcrypt_hash) is False

    def test_legacy_bcrypt_2a_prefix_supported(self):
        """`$2a$` is the older bcrypt format some Python tooling still emits."""
        digest = bcrypt.hashpw(b"old-style", bcrypt.gensalt(rounds=12, prefix=b"2a")).decode("utf-8")
        assert digest.startswith("$2a$")
        assert verify_password("old-style", digest) is True
        assert verify_password("nope", digest) is False


# ---------------------------------------------------------------------------
# Malformed input safety
# ---------------------------------------------------------------------------


class TestMalformedInputSafety:
    def test_empty_hash_rejected(self):
        assert verify_password("any-pw", "") is False

    def test_none_like_hash_rejected(self):
        # The function signature is typed `str` but defensive callers may
        # pass an empty fallback; we want the boolean contract to hold.
        assert verify_password("any-pw", "") is False

    def test_unknown_prefix_rejected(self):
        """A hash from an unknown algorithm must NOT raise — verify
        returns False so the login flow logs a failed attempt rather
        than 500-ing."""
        assert verify_password("any-pw", "$pbkdf2$some-fake-format") is False
        assert verify_password("any-pw", "plain-text-not-a-hash") is False

    def test_corrupted_bcrypt_hash_rejected(self):
        """bcrypt.checkpw raises ValueError on truncated input — caller
        must see False, never an exception bubble."""
        truncated = "$2b$12$tooshort"
        assert verify_password("any-pw", truncated) is False

    def test_corrupted_argon2_hash_rejected(self):
        """argon2-cffi raises InvalidHash on a malformed hash string —
        caller must see False, not an exception."""
        assert verify_password("any-pw", "$argon2id$v=19$broken") is False


# ---------------------------------------------------------------------------
# needs_rehash — drives the migration shim
# ---------------------------------------------------------------------------


class TestNeedsRehash:
    def test_argon2_at_current_params_does_not_need_rehash(self):
        digest = hash_password("pw")
        assert needs_rehash(digest) is False

    def test_legacy_bcrypt_needs_rehash(self):
        digest = bcrypt.hashpw(b"pw", bcrypt.gensalt(rounds=12)).decode("utf-8")
        assert needs_rehash(digest) is True

    def test_empty_hash_needs_rehash(self):
        """Treat missing/empty as 'must rehash'. Callers that hit this
        path on login already failed verify, so the rehash never fires
        — the assertion is defensive."""
        assert needs_rehash("") is True

    def test_unknown_format_needs_rehash(self):
        assert needs_rehash("$pbkdf2$old") is True
        assert needs_rehash("plain-text") is True

    def test_malformed_argon2_needs_rehash(self):
        """A broken argon2 string should be rehashed (we can't trust it
        even if the prefix looks right)."""
        assert needs_rehash("$argon2id$v=19$broken") is True


# ---------------------------------------------------------------------------
# Migration scenario — end-to-end shim verification
# ---------------------------------------------------------------------------


class TestMigrationFlow:
    """Simulates the full rehash-on-verify path the login endpoint runs."""

    def test_legacy_bcrypt_login_then_upgrade(self):
        plain = "user-password-2026"

        # Step 1: user account was created in the passlib era → bcrypt hash on file.
        stored = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        assert stored.startswith("$2")

        # Step 2: user logs in with correct password.
        assert verify_password(plain, stored) is True

        # Step 3: login endpoint asks: should I upgrade?
        assert needs_rehash(stored) is True

        # Step 4: endpoint computes the upgraded hash + persists it.
        upgraded = hash_password(plain)
        assert upgraded.startswith("$argon2id$")

        # Step 5: subsequent logins use the upgraded hash + don't re-trigger upgrade.
        assert verify_password(plain, upgraded) is True
        assert needs_rehash(upgraded) is False

    def test_already_argon2_user_no_upgrade(self):
        """Users created post-migration never trigger the upgrade path."""
        plain = "post-migration-pw"
        stored = hash_password(plain)
        assert verify_password(plain, stored) is True
        assert needs_rehash(stored) is False
