"""
Password hashing module.

Primary algorithm is argon2id (via argon2-cffi) — OWASP-recommended for
new password storage and the actively-maintained successor to the
project's prior passlib-backed bcrypt scheme. The library's built-in
defaults are used (memory cost 64 MiB, time cost 3 iterations,
parallelism 4) which target the OWASP "interactive login" profile.

Legacy compatibility: stored hashes produced by the passlib era begin
with ``$2[aby]$`` (bcrypt). `verify_password` accepts both formats so
existing accounts continue to authenticate without a forced reset.
`needs_rehash` flags any non-argon2 stored hash (or argon2 hash with
stale parameters) so the caller can rehash + persist after a
successful verify — the user's stored hash is then upgraded to argon2
transparently on their next successful login.

Both algorithms use constant-time comparison through their respective
libraries; the prefix discriminator is a plain-text marker that
carries no secret material.
"""

from __future__ import annotations

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

# argon2-cffi instance with library defaults.
_hasher = PasswordHasher()

# Prefixes we treat as legacy bcrypt. $2a is the modular crypt format
# emitted by older bcrypt implementations; $2b is the canonical
# specifier from the 2014 PHC submission; $2y is the PHP-flavour
# variant some toolchains still emit. All three are accepted by the
# `bcrypt` library's `checkpw`.
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")
_ARGON2_PREFIX = "$argon2"


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with argon2id.

    Returns a self-describing hash string (algorithm + parameters +
    salt + digest) that `verify_password` can later check without
    needing any side-channel state.
    """
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored hash.

    Accepts both the current argon2 format and the legacy bcrypt
    format (from the passlib era). Returns False rather than raising
    for any malformed-hash or unknown-prefix case so callers can rely
    on a single boolean contract.
    """
    if not stored_hash:
        return False

    if stored_hash.startswith(_ARGON2_PREFIX):
        try:
            _hasher.verify(stored_hash, plain_password)
            return True
        except (VerifyMismatchError, InvalidHash, VerificationError):
            # VerifyMismatchError = wrong password (expected miss path).
            # InvalidHash         = hash didn't structurally look like argon2.
            # VerificationError   = argon2-cffi could not decode the hash
            #                       (e.g. truncated PHC string). All three
            #                       collapse to "verification failed" so the
            #                       caller's contract stays a single boolean.
            return False

    if stored_hash.startswith(_BCRYPT_PREFIXES):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash.encode("utf-8"))
        except (ValueError, TypeError):
            # ValueError = malformed bcrypt hash; TypeError = encoding
            # surprise. Either way: not a valid match.
            return False

    # Unknown hash format — treat as a verification failure rather than
    # raising. Surfaces in audit logs as a failed login rather than a
    # 500-level error.
    return False


def needs_rehash(stored_hash: str) -> bool:
    """Return True if the stored hash should be re-hashed with the
    current algorithm + parameters.

    Returns True when:
      - The hash is bcrypt (legacy format from the passlib era), or
      - The hash is argon2 but with parameters older than the current
        `_hasher` defaults (argon2-cffi's `check_needs_rehash`), or
      - The hash is empty / unknown format.

    Callers should invoke this AFTER a successful `verify_password`
    and, if True, rehash the same plaintext + persist the new hash.
    Doing so during a login transaction is safe (the user just proved
    they own the password); doing so before verify would be a no-op
    information leak.
    """
    if not stored_hash:
        return True
    if stored_hash.startswith(_ARGON2_PREFIX):
        try:
            return _hasher.check_needs_rehash(stored_hash)
        except InvalidHash:
            return True
    # Legacy bcrypt OR unknown → upgrade.
    return True
