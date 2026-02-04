"""
Capacity Calendar - Working days, shifts, holidays
Stores calendar configuration for capacity planning calculations.
Used to determine available production hours per day.
"""
from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from backend.database import Base


class CapacityCalendar(Base):
    """
    CAPACITY_CALENDAR table - Working days, shifts, and holidays

    Purpose:
    - Define which days are working days vs holidays
    - Configure number of shifts per day
    - Store hours available per shift

    Multi-tenant: All records isolated by client_id
    """
    __tablename__ = "capacity_calendar"
    __table_args__ = (
        UniqueConstraint('client_id', 'calendar_date', name='uix_capacity_calendar_client_date'),
        {"extend_existing": True}
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Calendar date
    calendar_date = Column(Date, nullable=False, index=True)

    # Working day configuration
    is_working_day = Column(Boolean, default=True, nullable=False)
    shifts_available = Column(Integer, default=1, nullable=False)  # 1, 2, or 3

    # Hours per shift (allows partial shifts, overtime, etc.)
    shift1_hours = Column(Numeric(5, 2), default=8.0)
    shift2_hours = Column(Numeric(5, 2), default=0)
    shift3_hours = Column(Numeric(5, 2), default=0)

    # Holiday tracking
    holiday_name = Column(String(100), nullable=True)

    # Notes/metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def total_hours(self) -> float:
        """Calculate total available hours for this day."""
        if not self.is_working_day:
            return 0.0
        return float(self.shift1_hours or 0) + float(self.shift2_hours or 0) + float(self.shift3_hours or 0)

    def __repr__(self):
        return f"<CapacityCalendar(client_id={self.client_id}, date={self.calendar_date}, working={self.is_working_day})>"
