"""
ATTENDANCE_ENTRY table ORM schema (SQLAlchemy)
Complete implementation for KPI #10 Absenteeism calculation
Source: 04-Phase3_Attendance_Inventory.csv lines 2-21
"""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from backend.database import Base
import enum


class AbsenceType(str, enum.Enum):
    """Absence classification for absenteeism tracking"""
    UNSCHEDULED_ABSENCE = "UNSCHEDULED_ABSENCE"  # Counts toward absenteeism
    VACATION = "VACATION"                        # Scheduled, doesn't count
    MEDICAL_LEAVE = "MEDICAL_LEAVE"              # Counts toward absenteeism
    PERSONAL_LEAVE = "PERSONAL_LEAVE"            # Counts toward absenteeism


class AttendanceEntry(Base):
    """ATTENDANCE_ENTRY table - Daily attendance tracking for Absenteeism KPI"""
    __tablename__ = "ATTENDANCE_ENTRY"

    # Primary key
    attendance_entry_id = Column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Employee reference
    employee_id = Column(Integer, ForeignKey('EMPLOYEE.employee_id'), nullable=False, index=True)

    # Date tracking
    shift_date = Column(DateTime, nullable=False, index=True)
    shift_id = Column(Integer, ForeignKey('SHIFT.shift_id'))

    # Hours tracking - REQUIRED for Absenteeism calculation
    scheduled_hours = Column(Numeric(5, 2), nullable=False)
    actual_hours = Column(Numeric(5, 2), default=0)
    absence_hours = Column(Numeric(5, 2), default=0)  # scheduled_hours - actual_hours

    # Absence tracking
    is_absent = Column(Integer, nullable=False, default=0, index=True)  # Boolean
    absence_type = Column(SQLEnum(AbsenceType))

    # Late/early departure tracking
    arrival_time = Column(DateTime)
    departure_time = Column(DateTime)
    is_late = Column(Integer, default=0)  # Boolean
    is_early_departure = Column(Integer, default=0)  # Boolean

    # Metadata
    absence_reason = Column(Text)
    notes = Column(Text)
    entered_by = Column(Integer, ForeignKey('USER.user_id'))

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
