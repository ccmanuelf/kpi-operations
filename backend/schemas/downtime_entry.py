"""
DOWNTIME_ENTRY table ORM schema (SQLAlchemy)
Complete implementation for KPI #8 Availability calculation
Source: 03-Phase2_Downtime_WIP_Inventory.csv lines 2-19
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from backend.database import Base
import enum


class DowntimeReason(str, enum.Enum):
    """Downtime categories for availability calculation"""
    EQUIPMENT_FAILURE = "EQUIPMENT_FAILURE"
    MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE"
    SETUP_CHANGEOVER = "SETUP_CHANGEOVER"
    QUALITY_HOLD = "QUALITY_HOLD"
    MAINTENANCE = "MAINTENANCE"
    POWER_OUTAGE = "POWER_OUTAGE"
    OTHER = "OTHER"


class DowntimeEntry(Base):
    """DOWNTIME_ENTRY table - Equipment downtime tracking for Availability KPI"""
    __tablename__ = "DOWNTIME_ENTRY"

    # Primary key
    downtime_entry_id = Column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Work order reference
    work_order_id = Column(String(50), ForeignKey('WORK_ORDER.work_order_id'), nullable=False, index=True)

    # Date tracking
    shift_date = Column(DateTime, nullable=False, index=True)

    # Downtime classification
    downtime_reason = Column(SQLEnum(DowntimeReason), nullable=False, index=True)
    downtime_duration_minutes = Column(Integer, nullable=False)  # REQUIRED for Availability

    # Equipment details
    machine_id = Column(String(100))
    equipment_code = Column(String(50))

    # Root cause analysis
    root_cause_category = Column(String(100))
    corrective_action = Column(Text)

    # Responsible parties
    reported_by = Column(Integer, ForeignKey('USER.user_id'))
    resolved_by = Column(Integer, ForeignKey('USER.user_id'))
    resolution_timestamp = Column(DateTime)

    # Metadata
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
