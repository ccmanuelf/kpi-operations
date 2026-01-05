"""
Shift coverage database schema (SQLAlchemy)
PHASE 3: Shift coverage tracking
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from backend.database import Base


class ShiftCoverage(Base):
    """Shift coverage table"""
    __tablename__ = "shift_coverage"

    coverage_id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    shift_id = Column(Integer, ForeignKey('shifts.shift_id'), nullable=False)
    coverage_date = Column(Date, nullable=False)
    required_employees = Column(Integer, nullable=False)
    actual_employees = Column(Integer, nullable=False)
    coverage_percentage = Column(Numeric(5, 2))  # Calculated field
    notes = Column(Text)
    entered_by = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
