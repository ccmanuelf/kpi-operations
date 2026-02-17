"""
JWT Authentication utilities
Token creation, validation, password hashing
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.schemas.user import User

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Token blacklist for logout functionality (per audit requirement)
# In production, this should be replaced with Redis or database-backed storage
_token_blacklist: set = set()


def is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted (logged out)"""
    return token in _token_blacklist


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)


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

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return encoded_jwt


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

    # Check token blacklist before decoding (catches logged-out tokens)
    if is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception


def get_current_user(
    request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
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
    username: str = payload.get("sub")

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


def get_current_active_supervisor(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to require supervisor or admin role

    Args:
        current_user: Current authenticated user

    Returns:
        User if supervisor or admin

    Raises:
        HTTPException: If user lacks permissions
    """
    if current_user.role not in ["supervisor", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
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
