"""
User authentication models (Pydantic)
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime

from backend.auth.password_policy import validate_password_strength


class UserCreate(BaseModel):
    """User registration model with password policy enforcement (SEC-002)"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="operator", pattern="^(admin|supervisor|operator|viewer)$")

    @field_validator('password')
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
    username: str
    password: str


class UserResponse(BaseModel):
    """User response model (without password)"""
    user_id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordResetRequest(BaseModel):
    """Password reset request model"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation model"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        """Validate password against security policy"""
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v


class PasswordChange(BaseModel):
    """Password change model (for authenticated users)"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        """Validate password against security policy"""
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v
