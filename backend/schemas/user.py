"""
User ORM schema (SQLAlchemy)
Updated with multi-client assignment support
Source: 01-Core_DataEntities_Inventory.csv lines 61-71
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from backend.database import Base
import enum


class UserRole(str, enum.Enum):
    """User roles enum - defines access scope"""
    ADMIN = "admin"         # Full system access, all clients
    POWERUSER = "poweruser" # All clients access
    LEADER = "leader"       # Multiple clients (client_id_assigned)
    OPERATOR = "operator"   # Single client (client_id_assigned)


class User(Base):
    """USER table ORM - Authentication and authorization"""
    __tablename__ = "USER"

    user_id = Column(String(50), primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for legacy users
    full_name = Column(String(255), nullable=True)
    role = Column(String(20), nullable=True, default="OPERATOR", index=True)

    # Multi-client assignment - CRITICAL for tenant isolation
    # Format: Comma-separated client IDs (e.g., "BOOT-LINE-A,CLIENT-B")
    # NULL for ADMIN/POWERUSER (access all), required for LEADER/OPERATOR
    client_id_assigned = Column(Text, index=True)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
