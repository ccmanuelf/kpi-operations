"""
WIP hold database schema (SQLAlchemy)
PHASE 2: WIP aging tracking
Enhanced with P2-001: Hold Duration Auto-Calculation
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Numeric, Enum as SQLEnum
from sqlalchemy.sql import func
from backend.database import Base
import enum


class HoldStatus(str, enum.Enum):
    """Hold status for tracking hold/resume cycles"""
    ON_HOLD = "ON_HOLD"
    RESUMED = "RESUMED"
    RELEASED = "RELEASED"
    SCRAPPED = "SCRAPPED"


class WIPHold(Base):
    """WIP hold records table - DEPRECATED: Use HoldEntry from hold_entry.py instead"""
    __tablename__ = "wip_holds"
    __table_args__ = {"extend_existing": True}

    hold_id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    product_id = Column(Integer, ForeignKey('PRODUCT.product_id'), nullable=False)
    shift_id = Column(Integer, ForeignKey('SHIFT.shift_id'), nullable=False)
    hold_date = Column(Date, nullable=False)
    work_order_number = Column(String(50), nullable=False, index=True)
    quantity_held = Column(Integer, nullable=False)
    hold_reason = Column(String(255), nullable=False)
    hold_category = Column(String(50), nullable=False)
    expected_resolution_date = Column(Date)
    release_date = Column(Date)
    actual_resolution_date = Column(Date)
    quantity_released = Column(Integer)
    quantity_scrapped = Column(Integer)
    aging_days = Column(Integer)  # Calculated field

    # P2-001: Hold Duration Auto-Calculation Fields
    hold_timestamp = Column(DateTime(timezone=True))  # Precise timestamp when hold started
    resume_timestamp = Column(DateTime(timezone=True))  # Precise timestamp when resumed
    resumed_by = Column(Integer, ForeignKey('USER.user_id'))  # User who resumed the hold
    status = Column(SQLEnum(HoldStatus), default=HoldStatus.ON_HOLD, index=True)
    total_hold_duration_hours = Column(Numeric(10, 4))  # Auto-calculated duration in hours

    notes = Column(Text)
    entered_by = Column(Integer, ForeignKey('USER.user_id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
