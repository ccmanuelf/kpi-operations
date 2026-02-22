"""
HOLD_ENTRY table ORM schema (SQLAlchemy)
Complete implementation for KPI #1 WIP Aging calculation
Source: 03-Phase2_Downtime_WIP_Inventory.csv lines 20-38

Migration note (Task 0.5): hold_status and hold_reason columns changed from
SQLAlchemy Enum to String(50) so values are driven by HOLD_STATUS_CATALOG and
HOLD_REASON_CATALOG tables.  HoldStatus / HoldReason are kept as plain
string-constant classes so that all existing comparison code
(e.g. ``db_hold.hold_status == HoldStatus.ON_HOLD``) continues to work.
"""

from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class HoldStatus:
    """
    Hold status string constants.

    No longer a Python enum — values are now driven by HOLD_STATUS_CATALOG.
    This class is kept for backward-compatible symbolic constants used in
    comparisons throughout the codebase.
    """

    PENDING_HOLD_APPROVAL = "PENDING_HOLD_APPROVAL"
    ON_HOLD = "ON_HOLD"
    PENDING_RESUME_APPROVAL = "PENDING_RESUME_APPROVAL"
    RESUMED = "RESUMED"
    CANCELLED = "CANCELLED"
    RELEASED = "RELEASED"
    SCRAPPED = "SCRAPPED"

    # Expose __members__ for backward compatibility with code that checks
    # ``HoldStatus.__members__`` (e.g. factory fixtures).
    __members__ = {
        "PENDING_HOLD_APPROVAL": "PENDING_HOLD_APPROVAL",
        "ON_HOLD": "ON_HOLD",
        "PENDING_RESUME_APPROVAL": "PENDING_RESUME_APPROVAL",
        "RESUMED": "RESUMED",
        "CANCELLED": "CANCELLED",
        "RELEASED": "RELEASED",
        "SCRAPPED": "SCRAPPED",
    }


class HoldReason:
    """
    Hold reason string constants.

    No longer a Python enum — values are now driven by HOLD_REASON_CATALOG.
    This class is kept for backward-compatible symbolic constants.
    """

    MATERIAL_INSPECTION = "MATERIAL_INSPECTION"
    MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE"
    QUALITY_ISSUE = "QUALITY_ISSUE"
    ENGINEERING_REVIEW = "ENGINEERING_REVIEW"
    ENGINEERING_CHANGE = "ENGINEERING_CHANGE"
    CUSTOMER_REQUEST = "CUSTOMER_REQUEST"
    MISSING_SPECIFICATION = "MISSING_SPECIFICATION"
    EQUIPMENT_UNAVAILABLE = "EQUIPMENT_UNAVAILABLE"
    CAPACITY_CONSTRAINT = "CAPACITY_CONSTRAINT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    OTHER = "OTHER"

    __members__ = {
        "MATERIAL_INSPECTION": "MATERIAL_INSPECTION",
        "MATERIAL_SHORTAGE": "MATERIAL_SHORTAGE",
        "QUALITY_ISSUE": "QUALITY_ISSUE",
        "ENGINEERING_REVIEW": "ENGINEERING_REVIEW",
        "ENGINEERING_CHANGE": "ENGINEERING_CHANGE",
        "CUSTOMER_REQUEST": "CUSTOMER_REQUEST",
        "MISSING_SPECIFICATION": "MISSING_SPECIFICATION",
        "EQUIPMENT_UNAVAILABLE": "EQUIPMENT_UNAVAILABLE",
        "CAPACITY_CONSTRAINT": "CAPACITY_CONSTRAINT",
        "PENDING_APPROVAL": "PENDING_APPROVAL",
        "OTHER": "OTHER",
    }


class HoldEntry(Base):
    """HOLD_ENTRY table - WIP hold/resume tracking for aging calculation"""

    __tablename__ = "HOLD_ENTRY"
    __table_args__ = {"extend_existing": True}

    # Primary key
    hold_entry_id = Column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Work order reference
    work_order_id = Column(String(50), ForeignKey("WORK_ORDER.work_order_id"), nullable=False, index=True)
    job_id = Column(String(50), ForeignKey("JOB.job_id"), index=True)  # Job-level tracking

    # Hold tracking — String(50) backed by HOLD_STATUS_CATALOG
    hold_status = Column(String(50), nullable=False, default=HoldStatus.ON_HOLD, index=True)
    hold_date = Column(DateTime, index=True)
    resume_date = Column(DateTime)

    # Duration calculation - CRITICAL for WIP Aging
    # Excludes this time from aging: Net Aging = Total Days - (Hold Hours / 24)
    total_hold_duration_hours = Column(Numeric(10, 2), default=0)

    # Hold reason details — String(50) backed by HOLD_REASON_CATALOG
    hold_reason_category = Column(String(100))  # Kept for backward compatibility
    hold_reason = Column(String(50))  # Now catalog-driven (was SQLEnum)
    hold_reason_description = Column(Text)

    # Quality hold specifics
    quality_issue_type = Column(String(100))
    expected_resolution_date = Column(DateTime)

    # Responsible parties
    hold_initiated_by = Column(String(50), ForeignKey("USER.user_id"))
    hold_approved_by = Column(String(50), ForeignKey("USER.user_id"))
    resumed_by = Column(String(50), ForeignKey("USER.user_id"))

    # Metadata
    notes = Column(Text)

    # Audit field - tracks who last modified the record (per audit requirement)
    updated_by = Column(String(50), ForeignKey("USER.user_id"))

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
