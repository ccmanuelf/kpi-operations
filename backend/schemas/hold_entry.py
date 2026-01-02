"""
HOLD_ENTRY table ORM schema (SQLAlchemy)
Complete implementation for KPI #1 WIP Aging calculation
Source: 03-Phase2_Downtime_WIP_Inventory.csv lines 20-38
"""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from backend.database import Base
import enum


class HoldStatus(str, enum.Enum):
    """Hold status tracking"""
    ON_HOLD = "ON_HOLD"
    RESUMED = "RESUMED"
    CANCELLED = "CANCELLED"


class HoldEntry(Base):
    """HOLD_ENTRY table - WIP hold/resume tracking for aging calculation"""
    __tablename__ = "HOLD_ENTRY"

    # Primary key
    hold_entry_id = Column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Work order reference
    work_order_id = Column(String(50), ForeignKey('WORK_ORDER.work_order_id'), nullable=False, index=True)

    # Hold tracking
    hold_status = Column(SQLEnum(HoldStatus), nullable=False, default=HoldStatus.ON_HOLD, index=True)
    hold_date = Column(DateTime, index=True)
    resume_date = Column(DateTime)

    # Duration calculation - CRITICAL for WIP Aging
    # Excludes this time from aging: Net Aging = Total Days - (Hold Hours / 24)
    total_hold_duration_hours = Column(Numeric(10, 2), default=0)

    # Hold reason details
    hold_reason_category = Column(String(100))
    hold_reason_description = Column(Text)

    # Quality hold specifics
    quality_issue_type = Column(String(100))
    expected_resolution_date = Column(DateTime)

    # Responsible parties
    hold_initiated_by = Column(Integer, ForeignKey('USER.user_id'))
    hold_approved_by = Column(Integer, ForeignKey('USER.user_id'))
    resumed_by = Column(Integer, ForeignKey('USER.user_id'))

    # Metadata
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
