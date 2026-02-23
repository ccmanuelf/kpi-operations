"""
Break Time ORM schema (SQLAlchemy)
Configurable break periods associated with shifts for accurate KPI calculation.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from backend.database import Base
from datetime import datetime, timezone


class BreakTime(Base):
    """Break Time table ORM — stores configurable break periods per shift."""

    __tablename__ = "BREAK_TIME"
    __table_args__ = {"extend_existing": True}

    break_id = Column(Integer, primary_key=True, autoincrement=True)
    shift_id = Column(Integer, ForeignKey("SHIFT.shift_id"), nullable=False, index=True)
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    break_name = Column(String(100), nullable=False)  # e.g., "Morning Break", "Lunch"
    start_offset_minutes = Column(Integer, nullable=False)  # minutes from shift start
    duration_minutes = Column(Integer, nullable=False)  # break duration in minutes
    applies_to = Column(String(20), nullable=False, default="ALL")  # ALL, EMPLOYEE, LINE
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    shift = relationship("Shift", backref="break_times")
