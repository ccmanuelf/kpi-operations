"""
COVERAGE_ENTRY table ORM schema (SQLAlchemy)
Floating pool coverage assignments to reduce absenteeism impact
Source: 04-Phase3_Attendance_Inventory.csv lines 22-35
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class CoverageEntry(Base):
    """COVERAGE_ENTRY table - Floating pool assignment tracking"""
    __tablename__ = "COVERAGE_ENTRY"
    __table_args__ = {"extend_existing": True}

    # Primary key
    coverage_entry_id = Column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Employee references
    floating_employee_id = Column(Integer, ForeignKey('EMPLOYEE.employee_id'), nullable=False, index=True)
    covered_employee_id = Column(Integer, ForeignKey('EMPLOYEE.employee_id'), nullable=False, index=True)

    # Coverage period
    shift_date = Column(DateTime, nullable=False, index=True)
    shift_id = Column(Integer, ForeignKey('SHIFT.shift_id'))

    # Coverage details
    coverage_start_time = Column(DateTime)
    coverage_end_time = Column(DateTime)
    coverage_hours = Column(Integer)

    # Assignment reason
    coverage_reason = Column(String(255))  # "Absence", "Additional Support", etc.

    # Metadata
    notes = Column(Text)
    assigned_by = Column(Integer, ForeignKey('USER.user_id'))

    # Audit field - tracks who last modified the record (per audit requirement)
    updated_by = Column(Integer, ForeignKey('USER.user_id'))

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
