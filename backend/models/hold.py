"""
WIP hold tracking models (Pydantic)
PHASE 2: Work-in-process aging tracking
Enhanced with P2-001: Hold Duration Auto-Calculation
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class HoldStatusEnum(str, Enum):
    """Hold status enum for API"""
    ON_HOLD = "ON_HOLD"
    RESUMED = "RESUMED"
    RELEASED = "RELEASED"
    SCRAPPED = "SCRAPPED"


class HoldReasonEnum(str, Enum):
    """Hold reason enum for strict validation"""
    MATERIAL_INSPECTION = "MATERIAL_INSPECTION"
    QUALITY_ISSUE = "QUALITY_ISSUE"
    ENGINEERING_REVIEW = "ENGINEERING_REVIEW"
    CUSTOMER_REQUEST = "CUSTOMER_REQUEST"
    MISSING_SPECIFICATION = "MISSING_SPECIFICATION"
    EQUIPMENT_UNAVAILABLE = "EQUIPMENT_UNAVAILABLE"
    CAPACITY_CONSTRAINT = "CAPACITY_CONSTRAINT"
    OTHER = "OTHER"


class WIPHoldCreate(BaseModel):
    """Create WIP hold record - aligned with HOLD_ENTRY schema"""
    # Multi-tenant isolation - REQUIRED
    client_id: str = Field(..., min_length=1, max_length=50)

    # Work order reference - REQUIRED (replaces product_id/shift_id)
    work_order_id: str = Field(..., min_length=1, max_length=50)
    job_id: Optional[str] = Field(None, max_length=50, description="Job ID for job-level tracking")

    # Hold tracking - hold_status is REQUIRED
    hold_status: HoldStatusEnum = Field(default=HoldStatusEnum.ON_HOLD, description="Hold status - defaults to ON_HOLD")
    hold_date: Optional[date] = Field(None, description="Hold date")

    # Hold reason details
    hold_reason_category: Optional[str] = Field(None, max_length=100, description="Hold reason category")
    hold_reason: Optional[HoldReasonEnum] = Field(None, description="Enum-based hold reason")
    hold_reason_description: Optional[str] = Field(None, description="Detailed hold description")

    # Quality hold specifics
    quality_issue_type: Optional[str] = Field(None, max_length=100)
    expected_resolution_date: Optional[date] = None

    # Metadata
    notes: Optional[str] = None

    @classmethod
    def from_legacy_csv(cls, data: dict) -> "WIPHoldCreate":
        """Create from legacy CSV format with field mapping"""
        # Map legacy hold_reason string to enum
        reason_mapping = {
            "MATERIAL": HoldReasonEnum.MATERIAL_INSPECTION,
            "MATERIAL_INSPECTION": HoldReasonEnum.MATERIAL_INSPECTION,
            "QUALITY": HoldReasonEnum.QUALITY_ISSUE,
            "QUALITY_ISSUE": HoldReasonEnum.QUALITY_ISSUE,
            "ENGINEERING": HoldReasonEnum.ENGINEERING_REVIEW,
            "ENGINEERING_REVIEW": HoldReasonEnum.ENGINEERING_REVIEW,
            "CUSTOMER": HoldReasonEnum.CUSTOMER_REQUEST,
            "CUSTOMER_REQUEST": HoldReasonEnum.CUSTOMER_REQUEST,
            "MISSING_SPEC": HoldReasonEnum.MISSING_SPECIFICATION,
            "MISSING_SPECIFICATION": HoldReasonEnum.MISSING_SPECIFICATION,
            "EQUIPMENT": HoldReasonEnum.EQUIPMENT_UNAVAILABLE,
            "EQUIPMENT_UNAVAILABLE": HoldReasonEnum.EQUIPMENT_UNAVAILABLE,
            "CAPACITY": HoldReasonEnum.CAPACITY_CONSTRAINT,
            "CAPACITY_CONSTRAINT": HoldReasonEnum.CAPACITY_CONSTRAINT,
        }

        raw_reason = (data.get('hold_category') or data.get('hold_reason') or 'OTHER').upper()
        reason_enum = reason_mapping.get(raw_reason, HoldReasonEnum.OTHER)

        return cls(
            client_id=data.get('client_id', ''),
            work_order_id=data.get('work_order_number') or data.get('work_order_id', ''),
            job_id=data.get('job_id'),
            hold_status=HoldStatusEnum.ON_HOLD,
            hold_date=data.get('hold_date'),
            hold_reason_category=data.get('hold_category') or data.get('hold_reason_category'),
            hold_reason=reason_enum,
            hold_reason_description=data.get('hold_reason') or data.get('hold_reason_description'),
            quality_issue_type=data.get('quality_issue_type'),
            expected_resolution_date=data.get('expected_resolution_date'),
            notes=data.get('notes')
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
    # P2-001: Status can be updated
    status: Optional[HoldStatusEnum] = None


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
    hold_initiated_by: Optional[int] = None
    hold_approved_by: Optional[int] = None
    resumed_by: Optional[int] = None
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
