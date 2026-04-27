"""
User ORM schema (SQLAlchemy)
Updated with multi-client assignment support
Source: 01-Core_DataEntities_Inventory.csv lines 61-71
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class UserRole(str, enum.Enum):
    """User roles enum - defines access scope"""

    ADMIN = "admin"  # Full system access, all clients
    POWERUSER = "poweruser"  # All clients access
    LEADER = "leader"  # Multiple clients (client_id_assigned)
    OPERATOR = "operator"  # Single client (client_id_assigned)


class User(Base):
    """USER table ORM - Authentication and authorization"""

    __tablename__ = "USER"
    __table_args__ = {"extend_existing": True}

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Nullable for legacy users
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="OPERATOR", index=True)

    # Multi-client assignment - CRITICAL for tenant isolation
    # Format: Comma-separated client IDs (e.g., "BOOT-LINE-A,CLIENT-B")
    # NULL for ADMIN/POWERUSER (access all), required for LEADER/OPERATOR
    client_id_assigned: Mapped[Optional[str]] = mapped_column(Text, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
