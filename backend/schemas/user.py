"""
User authentication models (Pydantic)
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime

from backend.auth.password_policy import validate_password_strength


class UserCreate(BaseModel):
    """User registration model with password policy enforcement (SEC-002)"""

    username: str = Field(..., min_length=3, max_length=50, description="Unique login identifier for the user")
    email: EmailStr = Field(..., description="User email address for notifications and password recovery")
    password: str = Field(..., min_length=8, max_length=128, description="User password, must meet security policy requirements")
    full_name: str = Field(..., min_length=1, max_length=100, description="User display name shown in the application")
    role: str = Field(default="operator", pattern="^(admin|poweruser|supervisor|operator|viewer)$", description="Access role determining permissions: admin, poweruser, supervisor, operator, or viewer")
    client_id_assigned: Optional[str] = Field(None, description="Client tenant ID this user is assigned to for data isolation")

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        """
        Validate password against security policy (SEC-002)

        Requirements:
        - Minimum 8 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 digit
        - At least 1 special character
        - Not a common password
        """
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v


class UserLogin(BaseModel):
    """User login model"""

    username: str = Field(..., description="Login username or identifier")
    password: str = Field(..., description="Login password for authentication")


class UserUpdate(BaseModel):
    """User update model (all fields optional)"""

    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Updated login identifier for the user")
    email: Optional[EmailStr] = Field(None, description="Updated email address for notifications")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="New password, must meet security policy requirements")
    full_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Updated display name shown in the application")
    role: Optional[str] = Field(None, pattern="^(admin|poweruser|supervisor|operator|viewer)$", description="Updated access role for permissions")
    client_id_assigned: Optional[str] = Field(None, description="Updated client tenant ID assignment")
    is_active: Optional[bool] = Field(None, description="Whether the user account is active or disabled")


class UserResponse(BaseModel):
    """User response model (without password)"""

    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Login identifier for the user")
    email: str = Field(..., description="User email address")
    full_name: Optional[str] = Field(None, description="User display name")
    role: Optional[str] = Field(None, description="Access role: admin, poweruser, supervisor, operator, or viewer")
    client_id_assigned: Optional[str] = Field(None, description="Client tenant ID this user is assigned to")
    is_active: bool = Field(True, description="Whether the user account is currently active")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the user account was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of the last account modification")

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response"""

    access_token: str = Field(..., description="JWT access token for authenticating API requests")
    token_type: str = Field("bearer", description="Token type, always 'bearer' for JWT authentication")
    user: UserResponse = Field(..., description="Authenticated user profile details")


class PasswordResetRequest(BaseModel):
    """Password reset request model"""

    email: EmailStr = Field(..., description="Email address of the account to reset")


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation model"""

    token: str = Field(..., description="Password reset token received via email")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password, must meet security policy requirements")

    @field_validator("new_password")
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        """Validate password against security policy"""
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v


class PasswordChange(BaseModel):
    """Password change model (for authenticated users)"""

    current_password: str = Field(..., description="Current password for verification before change")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password, must meet security policy requirements")

    @field_validator("new_password")
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        """Validate password against security policy"""
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v
