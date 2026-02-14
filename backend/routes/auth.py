"""
Authentication API Routes
All authentication endpoints: register, login, logout, password management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
import uuid

from backend.database import get_db
from backend.config import settings
from backend.utils.logging_utils import get_module_logger, log_operation, log_security_event

logger = get_module_logger(__name__)
from backend.models.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordChange,
)
from backend.middleware.rate_limit import limiter, RateLimitConfig
from backend.auth.jwt import verify_password, get_password_hash, create_access_token, get_current_user, oauth2_scheme
from backend.schemas.user import User


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# Token blacklist for logout functionality (per audit requirement)
# In production, this should be replaced with Redis or database-backed storage
_token_blacklist: set = set()


def is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted (logged out)"""
    return token in _token_blacklist


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RateLimitConfig.AUTH_LIMIT)
def register_user(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    """Register new user (rate limited: 10 requests/minute)"""
    client_ip = request.client.host if request.client else None

    # Check if username exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        log_security_event(
            logger,
            "REGISTER_DUPLICATE_USERNAME",
            details=f"Attempted registration with existing username: {user.username}",
            ip_address=client_ip,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    # Check if email exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        log_security_event(
            logger,
            "REGISTER_DUPLICATE_EMAIL",
            details=f"Attempted registration with existing email",
            ip_address=client_ip,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Create user with generated ID
    user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
    hashed_password = get_password_hash(user.password)
    db_user = User(
        user_id=user_id,
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        full_name=user.full_name,
        role=user.role.upper() if user.role else "OPERATOR",
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    log_security_event(
        logger,
        "USER_REGISTERED",
        user_id=user_id,
        details=f"New user registered: {user.username}",
        ip_address=client_ip,
    )
    return db_user


@router.post("/login", response_model=Token)
@limiter.limit(RateLimitConfig.AUTH_LIMIT)
def login(request: Request, user_credentials: UserLogin, db: Session = Depends(get_db)):
    """User login (rate limited: 10 requests/minute)"""
    client_ip = request.client.host if request.client else None
    user = db.query(User).filter(User.username == user_credentials.username).first()

    if not user or not verify_password(user_credentials.password, user.password_hash):
        log_security_event(
            logger,
            "LOGIN_FAILED",
            details=f"Failed login attempt for: {user_credentials.username}",
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        log_security_event(
            logger,
            "LOGIN_INACTIVE_USER",
            user_id=user.user_id,
            details="Login attempt for inactive account",
            ip_address=client_ip,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    # Create access token with client_id for stateless validation (per audit requirement)
    # Include client_id_assigned in JWT payload for stateless tenant verification
    token_data = {
        "sub": user.username,
        "role": user.role,
        "client_ids": user.client_id_assigned,  # Comma-separated or None for admin/poweruser
    }
    access_token = create_access_token(data=token_data)

    log_security_event(
        logger, "LOGIN_SUCCESS", user_id=user.user_id, client_id=user.client_id_assigned, ip_address=client_ip
    )

    return Token(access_token=access_token, token_type="bearer", user=UserResponse.from_orm(user))


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@router.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user), token: str = Depends(oauth2_scheme)):
    """
    Explicit logout endpoint (per audit requirement)

    Invalidates the current access token by adding it to the blacklist.
    Client should also clear the token from local storage.

    Returns:
        Success message confirming logout
    """
    client_ip = request.client.host if request.client else None

    # Add token to blacklist (JTI would be better, using full token for simplicity)
    # In production, use Redis with TTL matching token expiration
    _token_blacklist.add(token)

    log_security_event(logger, "LOGOUT", user_id=current_user.user_id, ip_address=client_ip)

    return {
        "message": "Successfully logged out",
        "detail": "Token has been invalidated. Please clear your local session.",
    }


@router.post("/forgot-password")
@limiter.limit(RateLimitConfig.AUTH_LIMIT)
def forgot_password(request: Request, reset_request: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Request password reset (rate limited: 10 requests/minute)

    Sends a password reset email with a time-limited token.
    Always returns success to prevent email enumeration attacks.
    """
    user = db.query(User).filter(User.email == reset_request.email).first()

    if user and user.is_active:
        # Create password reset token (24 hour expiry)
        reset_token = create_access_token(
            data={"sub": user.username, "type": "password_reset"}, expires_delta=timedelta(hours=24)
        )
        # TODO: Send email with reset link
        # In production, integrate with email service
        # For now, log the token (remove in production)
        print(f"[DEV] Password reset token for {user.email}: {reset_token}")

    # Always return success to prevent email enumeration
    return {"message": "If your email is registered, you will receive a password reset link"}


@router.post("/reset-password")
@limiter.limit(RateLimitConfig.AUTH_LIMIT)
def reset_password(request: Request, reset_confirm: PasswordResetConfirm, db: Session = Depends(get_db)):
    """
    Reset password using token (rate limited: 10 requests/minute)
    """
    try:
        payload = jwt.decode(reset_confirm.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        token_type = payload.get("type")

        if token_type != "password_reset" or not username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")

        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")

        # Update password
        user.password_hash = get_password_hash(reset_confirm.new_password)
        user.updated_at = datetime.utcnow()
        db.commit()

        return {"message": "Password has been reset successfully"}

    except JWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")


@router.post("/change-password")
def change_password(
    password_data: PasswordChange, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Change password for authenticated user"""
    if not verify_password(password_data.current_password, current_user.password_hash):
        log_security_event(
            logger,
            "PASSWORD_CHANGE_FAILED",
            user_id=current_user.user_id,
            details="Incorrect current password provided",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    current_user.password_hash = get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()

    log_security_event(logger, "PASSWORD_CHANGED", user_id=current_user.user_id)

    return {"message": "Password changed successfully"}
