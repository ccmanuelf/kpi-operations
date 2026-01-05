"""
Attendance database schema (SQLAlchemy)
PHASE 3: Employee attendance tracking
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from backend.database import Base


class AttendanceRecord(Base):
    """Attendance records table"""
    __tablename__ = "attendance_records"

    attendance_id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    employee_id = Column(Integer, nullable=False)  # Will link to employee table in future
    shift_id = Column(Integer, ForeignKey('shifts.shift_id'), nullable=False)
    attendance_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)  # Present, Absent, Late, Leave
    scheduled_hours = Column(Numeric(5, 2), nullable=False)
    actual_hours_worked = Column(Numeric(5, 2), default=0)
    absence_reason = Column(String(100))
    notes = Column(Text)
    entered_by = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
