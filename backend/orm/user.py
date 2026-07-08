"""
User ORM schema (SQLAlchemy)
Updated with multi-client assignment support
Source: 01-Core_DataEntities_Inventory.csv lines 61-71
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class UserRole(str, enum.Enum):
    """User roles enum - defines access scope.

    Canonical set of the six role strings the platform recognizes (Run 7
    reconciliation). Write authority descends ADMIN > POWERUSER > LEADER ≈
    SUPERVISOR > OPERATOR > VIEWER. See docs/user-guide/10-roles-permissions.md
    and the guard tiers in backend/auth/jwt.py.
    """

    ADMIN = "admin"  # Full system access, all clients
    POWERUSER = "poweruser"  # All clients access
    LEADER = "leader"  # Multiple clients (client_id_assigned)
    SUPERVISOR = "supervisor"  # Shift supervisor; supervisory tier (≈ leader)
    OPERATOR = "operator"  # Single client (client_id_assigned); data entry
    VIEWER = "viewer"  # Read-only; single client


# Authorization tiers — the SINGLE SOURCE OF TRUTH for write permissions
# (Run 7). Route guards (backend/auth/jwt.py), the CRUD layer, and per-module
# write checks all import these so the tiers can never drift apart again
# (the drift between route guards and CRUD checks is exactly what Run 7 fixed).
# Defined as plain str lists of UserRole values so they compose with the
# lowercase `User.role` column directly.
PLANNER_ROLES = [UserRole.ADMIN.value, UserRole.POWERUSER.value]
SUPERVISORY_ROLES = PLANNER_ROLES + [UserRole.LEADER.value, UserRole.SUPERVISOR.value]
CONTRIBUTOR_ROLES = SUPERVISORY_ROLES + [UserRole.OPERATOR.value]


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
    client_id_assigned: Mapped[Optional[str]] = mapped_column(String(500), index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
