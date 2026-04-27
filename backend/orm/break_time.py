"""
Break Time ORM schema (SQLAlchemy)
Configurable break periods associated with shifts for accurate KPI calculation.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class BreakTime(Base):
    """Break Time table ORM — stores configurable break periods per shift."""

    __tablename__ = "BREAK_TIME"
    __table_args__ = {"extend_existing": True}

    break_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shift_id: Mapped[int] = mapped_column(Integer, ForeignKey("SHIFT.shift_id"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    break_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "Morning Break", "Lunch"
    start_offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # minutes from shift start
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # break duration in minutes
    applies_to: Mapped[str] = mapped_column(String(20), nullable=False, default="ALL")  # ALL, EMPLOYEE, LINE
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    shift = relationship("Shift", backref="break_times")
