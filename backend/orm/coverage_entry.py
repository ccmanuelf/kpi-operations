"""
COVERAGE_ENTRY table ORM schema (SQLAlchemy)
Floating pool coverage assignments to reduce absenteeism impact
Source: 04-Phase3_Attendance_Inventory.csv lines 22-35
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class CoverageEntry(Base):
    """COVERAGE_ENTRY table - Floating pool assignment tracking"""

    __tablename__ = "COVERAGE_ENTRY"
    __table_args__ = {"extend_existing": True}

    # Primary key
    coverage_entry_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Employee references
    floating_employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("EMPLOYEE.employee_id"), nullable=False, index=True
    )
    covered_employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("EMPLOYEE.employee_id"), nullable=False, index=True
    )

    # Coverage period
    shift_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    shift_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("SHIFT.shift_id"))

    # Coverage details
    coverage_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    coverage_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    coverage_hours: Mapped[Optional[int]] = mapped_column(Integer)

    # Assignment reason
    coverage_reason: Mapped[Optional[str]] = mapped_column(String(255))  # "Absence", etc.

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)
    assigned_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("USER.user_id"))

    # Audit field - tracks who last modified the record (per audit requirement)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("USER.user_id"))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
