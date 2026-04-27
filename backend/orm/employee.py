"""
EMPLOYEE table ORM schema (SQLAlchemy)
Source: 01-Core_DataEntities_Inventory.csv lines 43-53
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class Employee(Base):
    """EMPLOYEE table - Staff directory with floating pool flag"""

    __tablename__ = "EMPLOYEE"
    __table_args__ = {"extend_existing": True}

    # Primary key
    employee_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Employee identification
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Multi-client assignment (comma-separated client IDs for leaders/supervisors)
    client_id_assigned: Mapped[Optional[str]] = mapped_column(Text)  # NULL for floating pool, comma-separated otherwise

    # Floating pool flag
    is_floating_pool: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, index=True
    )  # 0=regular, 1=floating

    # Status and department
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)  # Soft delete: 1/0
    department: Mapped[Optional[str]] = mapped_column(String(50))  # Department classification

    # Additional info
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    position: Mapped[Optional[str]] = mapped_column(String(100))
    hire_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
