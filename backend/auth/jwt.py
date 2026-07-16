"""
JWT Authentication utilities
Token creation, validation, password hashing
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, cast
import jwt
from jwt import PyJWTError
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import true
from sqlalchemy.orm import Session

from backend.auth.password import hash_password as _hash_password
from backend.auth.password import needs_rehash as _needs_rehash
from backend.auth.password import verify_password as _verify_password
from backend.config import settings
from backend.database import get_db
from backend.orm.token_blacklist import TokenBlacklist
from backend.orm.user import User, PLANNER_ROLES, SUPERVISORY_ROLES, CONTRIBUTOR_ROLES

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def token_revocation_key(token: str) -> str:
    """
    Stable revocation key for a token: its jti claim, falling back to a
    sha256 digest of the raw token for legacy tokens minted before the jti
    claim existed. The fallback keeps every outstanding token revocable
    across the rollout without storing raw JWTs in the database.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        if isinstance(jti, str) and jti:
            return jti
    except PyJWTError:
        pass
    return hashlib.sha256(token.encode()).hexdigest()


def is_token_blacklisted(db: Session, revocation_key: str) -> bool:
    """Check the TOKEN_BLACKLIST table for a revoked (logged-out) token key."""
    return db.query(TokenBlacklist.jti).filter(TokenBlacklist.jti == revocation_key).first() is not None


def blacklist_token(db: Session, token: str, user_id: Optional[str] = None) -> None:
    """
    Persist a token revocation (logout).

    Stores the token's revocation key with its own expiry so the row can be
    pruned once the JWT would be rejected by exp validation anyway. Pruning
    happens here, on insert — logout is the low-frequency write path, which
    bounds table growth without a scheduler.
    """
    expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp")
        if exp is not None:
            expires_at = datetime.fromtimestamp(float(exp), tz=timezone.utc)
    except PyJWTError:
        pass  # keep the conservative default expiry

    # Prune rows whose tokens have already expired (compare naive-UTC, the
    # storage convention of the DateTime column).
    now_naive = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    db.query(TokenBlacklist).filter(TokenBlacklist.expires_at < now_naive).delete(synchronize_session=False)

    key = token_revocation_key(token)
    if db.query(TokenBlacklist.jti).filter(TokenBlacklist.jti == key).first() is None:
        db.add(TokenBlacklist(jti=key, user_id=user_id, expires_at=expires_at.replace(tzinfo=None)))
    db.commit()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash.

    Accepts both argon2id (current) and bcrypt (legacy passlib-era)
    stored hash formats. See `backend.auth.password.verify_password`
    for the full migration-shim contract.
    """
    return _verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password using argon2id (OWASP-recommended)."""
    return _hash_password(password)


def needs_password_rehash(hashed_password: str) -> bool:
    """Return True if the stored hash should be re-hashed.

    Login flow should call this after a successful `verify_password`
    and, if True, rehash the same plaintext + persist the new hash.
    """
    return _needs_rehash(hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        data: Payload to encode
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(tz=timezone.utc) + expires_delta
    else:
        expire = datetime.now(tz=timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # jti keys the DB-backed revocation (logout) without storing raw tokens.
    to_encode.setdefault("jti", uuid.uuid4().hex)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded payload

    Raises:
        HTTPException: If token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("sub") is None:
            raise credentials_exception
        return cast(Dict[Any, Any], payload)
    except PyJWTError:
        raise credentials_exception


def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Dependency to get current authenticated user

    Enhanced: Extracts client_ids from JWT for stateless validation (per audit requirement)
    This allows client access verification without additional DB queries.
    Sets request.state.user_id for AuditLogMiddleware attribution.

    Args:
        request: FastAPI request (used to set user_id on request.state for audit logging)
        token: JWT token from request
        db: Database session

    Returns:
        Current user object with _jwt_client_ids attribute for stateless validation

    Raises:
        HTTPException: If user not found or inactive
    """
    payload = decode_access_token(token)

    # Reject revoked (logged-out) tokens. The check is DB-backed so it
    # survives restarts and is shared across workers (Run 7 T1.4).
    jti = payload.get("jti")
    revocation_key = jti if isinstance(jti, str) and jti else hashlib.sha256(token.encode()).hexdigest()
    if is_token_blacklisted(db, revocation_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # JWT "sub" claim must be a non-empty string. payload.get returns
    # Optional[Any] — refuse the token rather than passing None into
    # the username filter (which would either match no rows or, on
    # some dialects, raise).
    raw_username = payload.get("sub")
    if not isinstance(raw_username, str) or not raw_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: str = raw_username

    user = db.query(User).filter(User.username == username).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    # ENHANCEMENT: Attach JWT payload data for stateless validation
    # This allows client_auth middleware to validate without DB lookup
    user._jwt_role = payload.get("role")
    user._jwt_client_ids = payload.get("client_ids")  # Comma-separated or None

    # Set user_id on request.state so AuditLogMiddleware can attribute actions correctly
    request.state.user_id = user.user_id

    return user


# Role tiers (Run 7), per the documented permission matrix in
# docs/user-guide/10-roles-permissions.md. Canonical definitions live in
# backend/orm/user.py and are imported here (and by the CRUD layer and
# per-module write checks) so the tiers can never drift apart:
#   admin               -> system administration
#   PLANNER_ROLES       -> capacity planning, scenarios, configuration
#   SUPERVISORY_ROLES   -> operations master data, work orders, bulk loads
#   CONTRIBUTOR_ROLES   -> transactional data entry (everyone except viewer)
#   viewer              -> read-only (excluded from all write guards)


def get_current_active_supervisor(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to require a supervisory-tier role (any role except operator).

    Per docs/user-guide/10-roles-permissions.md: Admin, PowerUser, Leader and
    (legacy) Supervisor manage operations master data and work orders;
    Operators are restricted to transactional data entry. Before Run 7 T2.7
    this guard only accepted ["supervisor", "admin"], wrongly denying
    PowerUser and Leader everywhere it was used.

    Raises:
        HTTPException: If the caller is an operator (or unknown role)
    """
    if current_user.role not in SUPERVISORY_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return current_user


def get_current_planner(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to require a planning-tier role (admin or poweruser).

    Per docs/user-guide/10-roles-permissions.md: editing the capacity
    workbook, saving scenarios, and platform configuration are
    Admin/PowerUser-only.

    Raises:
        HTTPException: If the caller lacks a planning-tier role
    """
    if current_user.role not in PLANNER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Planner access required (admin or poweruser)"
        )
    return current_user


def get_current_contributor(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency for transactional data entry: any authenticated role except
    viewer (Run 7 role-model reconciliation).

    Viewers are read-only — they may authenticate and read, but cannot create
    or modify operational records (production, downtime, attendance, quality,
    holds, coverage, defects). Operators and above are contributors.

    Raises:
        HTTPException: If the caller is a viewer
    """
    if current_user.role not in CONTRIBUTOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a data-entry role (viewers are read-only)",
        )
    return current_user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to require admin role

    Args:
        current_user: Current authenticated user

    Returns:
        User if admin

    Raises:
        HTTPException: If user is not admin
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@dataclass(frozen=True)
class ClientScope:
    """Resolved, authorized set of clients for a request. client_ids is None
    => all clients (admin/poweruser); otherwise the exact authorized tuple."""

    client_ids: Optional[tuple[str, ...]]

    def filter(self, column: Any) -> Any:
        """SQLAlchemy clause scoping `column` to this scope (true() = no filter)."""
        if self.client_ids is None:
            return true()
        return column.in_(self.client_ids)

    def as_single(self) -> Optional[str]:
        """Scalar client_id for legacy scalar-consuming services."""
        if self.client_ids is None:
            return None
        if len(self.client_ids) == 1:
            return self.client_ids[0]
        raise HTTPException(status_code=400, detail="Multiple clients in scope; specify a client_id")


def resolve_client_scope(
    client_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClientScope:
    """Central client-scope authorization for read endpoints. Admin/poweruser
    see all clients (or narrow to one); scoped users are confined to their
    assigned client(s); an unauthorized client_id -> 403."""
    # Deferred import: backend.middleware's __init__ imports write_access,
    # which imports get_current_user from this module. A module-level import
    # here would deadlock jwt.py's own import (circular). By call time this
    # module is already fully loaded, so the cycle doesn't apply.
    from backend.middleware.client_auth import get_user_client_filter, ClientAccessError

    allowed = get_user_client_filter(current_user, db)  # None=all; list=scoped; raises 403 if scoped & unassigned
    if client_id is not None:
        if allowed is not None and client_id not in allowed:
            raise ClientAccessError(detail=f"Not authorized for client {client_id}")
        return ClientScope((client_id,))
    return ClientScope(None if allowed is None else tuple(allowed))
