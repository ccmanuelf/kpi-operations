"""
WIP hold tracking models (Pydantic)
PHASE 2: Work-in-process aging tracking
Enhanced with P2-001: Hold Duration Auto-Calculation

Migration note (Task 0.5): HoldStatusEnum and HoldReasonEnum removed.
Status and reason values are now free-form strings validated against
HOLD_STATUS_CATALOG / HOLD_REASON_CATALOG at the route level.
Legacy aliases kept for backward compatibility of imports.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


# ---------------------------------------------------------------------------
# Backward-compatible aliases so ``from backend.schemas.hold import
# HoldStatusEnum`` still resolves (returns the constants class from ORM).
# ---------------------------------------------------------------------------
from backend.orm.hold_entry import HoldStatus as HoldStatusEnum  # noqa: F401
from backend.orm.hold_entry import HoldReason as HoldReasonEnum  # noqa: F401


class WIPHoldCreate(BaseModel):
    """Create WIP hold record - aligned with HOLD_ENTRY schema"""

    # Multi-tenant isolation - REQUIRED
    client_id: str = Field(..., min_length=1, max_length=50)

    # Work order reference - REQUIRED (replaces product_id/shift_id)
    work_order_id: str = Field(..., min_length=1, max_length=50)
    job_id: Optional[str] = Field(None, max_length=50, description="Job ID for job-level tracking")

    # Hold tracking — free-form string validated against catalog at route level
    hold_status: str = Field(default="ON_HOLD", max_length=50, description="Hold status - defaults to ON_HOLD")
    hold_date: Optional[date] = Field(None, description="Hold date")

    # Hold reason details — free-form string validated against catalog at route level
    hold_reason_category: Optional[str] = Field(None, max_length=100, description="Hold reason category")
    hold_reason: Optional[str] = Field(None, max_length=50, description="Hold reason code from catalog")
    hold_reason_description: Optional[str] = Field(None, description="Detailed hold description")

    # Quality hold specifics
    quality_issue_type: Optional[str] = Field(None, max_length=100)
    expected_resolution_date: Optional[date] = None

    # Metadata
    notes: Optional[str] = None

    @classmethod
    def from_legacy_csv(cls, data: dict) -> "WIPHoldCreate":
        """Create from legacy CSV format with field mapping"""
        # Map legacy hold_reason string to canonical reason codes
        reason_mapping = {
            "MATERIAL": "MATERIAL_INSPECTION",
            "MATERIAL_INSPECTION": "MATERIAL_INSPECTION",
            "QUALITY": "QUALITY_ISSUE",
            "QUALITY_ISSUE": "QUALITY_ISSUE",
            "ENGINEERING": "ENGINEERING_REVIEW",
            "ENGINEERING_REVIEW": "ENGINEERING_REVIEW",
            "CUSTOMER": "CUSTOMER_REQUEST",
            "CUSTOMER_REQUEST": "CUSTOMER_REQUEST",
            "MISSING_SPEC": "MISSING_SPECIFICATION",
            "MISSING_SPECIFICATION": "MISSING_SPECIFICATION",
            "EQUIPMENT": "EQUIPMENT_UNAVAILABLE",
            "EQUIPMENT_UNAVAILABLE": "EQUIPMENT_UNAVAILABLE",
            "CAPACITY": "CAPACITY_CONSTRAINT",
            "CAPACITY_CONSTRAINT": "CAPACITY_CONSTRAINT",
        }

        raw_reason = (data.get("hold_category") or data.get("hold_reason") or "OTHER").upper()
        reason_code = reason_mapping.get(raw_reason, "OTHER")

        return cls(
            client_id=data.get("client_id", ""),
            work_order_id=data.get("work_order_number") or data.get("work_order_id", ""),
            job_id=data.get("job_id"),
            hold_status="ON_HOLD",
            hold_date=data.get("hold_date"),
            hold_reason_category=data.get("hold_category") or data.get("hold_reason_category"),
            hold_reason=reason_code,
            hold_reason_description=data.get("hold_reason") or data.get("hold_reason_description"),
            quality_issue_type=data.get("quality_issue_type"),
            expected_resolution_date=data.get("expected_resolution_date"),
            notes=data.get("notes"),
        )


class WIPHoldUpdate(BaseModel):
    """Update WIP hold record"""

    quantity_held: Optional[int] = Field(None, gt=0)
    hold_reason: Optional[str] = Field(None, max_length=255)
    hold_category: Optional[str] = Field(None, max_length=50)
    expected_resolution_date: Optional[date] = None
    release_date: Optional[date] = None
    actual_resolution_date: Optional[date] = None
    quantity_released: Optional[int] = Field(None, ge=0)
    quantity_scrapped: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    # P2-001: Status can be updated (now a free-form string)
    status: Optional[str] = Field(None, max_length=50)


class WIPHoldResumeRequest(BaseModel):
    """Request to resume a hold - P2-001"""

    notes: Optional[str] = Field(None, description="Optional notes when resuming")


class WIPHoldResponse(BaseModel):
    """WIP hold response - matches HOLD_ENTRY schema"""

    hold_entry_id: str
    client_id: str
    work_order_id: str
    job_id: Optional[str] = None
    hold_status: str
    hold_date: Optional[datetime] = None
    resume_date: Optional[datetime] = None
    total_hold_duration_hours: Optional[Decimal] = None
    hold_reason_category: Optional[str] = None
    hold_reason: Optional[str] = None
    hold_reason_description: Optional[str] = None
    quality_issue_type: Optional[str] = None
    expected_resolution_date: Optional[datetime] = None
    hold_initiated_by: Optional[str] = None
    hold_approved_by: Optional[str] = None
    resumed_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WIPAgingResponse(BaseModel):
    """WIP aging analysis"""

    total_held_quantity: int
    average_aging_days: Decimal
    aging_0_7_days: int
    aging_8_14_days: int
    aging_15_30_days: int
    aging_over_30_days: int
    total_hold_events: int
    calculation_timestamp: datetime


class WIPAgingAdjustedResponse(BaseModel):
    """WIP aging with hold-time adjustment - P2-001"""

    work_order_number: str
    raw_age_hours: Decimal
    total_hold_duration_hours: Decimal
    adjusted_age_hours: Decimal
    hold_count: int
    is_currently_on_hold: bool


class TotalHoldDurationResponse(BaseModel):
    """Total hold duration for a work order - P2-001"""

    work_order_number: str
    total_hold_duration_hours: Decimal
    hold_count: int
    active_holds: int
