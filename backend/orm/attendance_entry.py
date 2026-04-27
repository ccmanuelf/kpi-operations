"""
ATTENDANCE_ENTRY table ORM schema (SQLAlchemy)
Complete implementation for KPI #10 Absenteeism calculation
Source: 04-Phase3_Attendance_Inventory.csv lines 2-21
Enhanced with composite indexes for query performance (per audit requirement)
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class AbsenceType(str, enum.Enum):
    """Absence classification for absenteeism tracking"""

    UNSCHEDULED_ABSENCE = "UNSCHEDULED_ABSENCE"  # Counts toward absenteeism
    VACATION = "VACATION"  # Scheduled, doesn't count
    MEDICAL_LEAVE = "MEDICAL_LEAVE"  # Counts toward absenteeism
    PERSONAL_LEAVE = "PERSONAL_LEAVE"  # Counts toward absenteeism


class AttendanceEntry(Base):
    """ATTENDANCE_ENTRY table - Daily attendance tracking for Absenteeism KPI"""

    __tablename__ = "ATTENDANCE_ENTRY"
    __table_args__ = (
        # Composite indexes for query performance (per audit requirement)
        Index("ix_attendance_client_shift_date", "client_id", "shift_date"),  # Most common query pattern
        Index("ix_attendance_client_employee", "client_id", "employee_id"),  # Employee attendance history
        Index("ix_attendance_shift_date_absent", "shift_date", "is_absent"),  # Absenteeism reports
        {"extend_existing": True},
    )

    # Primary key
    attendance_entry_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    line_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("PRODUCTION_LINE.line_id"), nullable=True, index=True
    )

    # Employee reference
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("EMPLOYEE.employee_id"), nullable=False, index=True)

    # Date tracking
    shift_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    shift_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("SHIFT.shift_id"))

    # Hours tracking - REQUIRED for Absenteeism calculation
    scheduled_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    actual_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), default=0)
    absence_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), default=0)  # scheduled - actual

    # Absence tracking
    is_absent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)  # Boolean
    absence_type: Mapped[Optional[AbsenceType]] = mapped_column(SQLEnum(AbsenceType))

    # Coverage tracking - for floating pool assignments
    covered_by_employee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("EMPLOYEE.employee_id")
    )  # FK to floating pool employee
    coverage_confirmed: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # 0=pending, 1=confirmed

    # Late/early departure tracking
    arrival_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    departure_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_late: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # Boolean
    is_early_departure: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # Boolean

    # Metadata
    absence_reason: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    entered_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("USER.user_id"))

    # Audit field - tracks who last modified the record (per audit requirement)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("USER.user_id"))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
