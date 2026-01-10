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


class WIPHoldCreate(BaseModel):
    """Create WIP hold record"""
    client_id: str = Field(..., min_length=1, max_length=50)
    product_id: int = Field(..., gt=0)
    shift_id: int = Field(..., gt=0)
    hold_date: date
    work_order_number: str = Field(..., max_length=50)
    quantity_held: int = Field(..., gt=0)
    hold_reason: str = Field(..., max_length=255)
    hold_category: str = Field(..., max_length=50)
    expected_resolution_date: Optional[date] = None
    notes: Optional[str] = None
    # P2-001: Optional hold timestamp (defaults to now if not provided)
    hold_timestamp: Optional[datetime] = None


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
    """WIP hold response"""
    hold_id: int
    client_id: str
    product_id: int
    shift_id: int
    hold_date: date
    work_order_number: str
    quantity_held: int
    hold_reason: str
    hold_category: str
    expected_resolution_date: Optional[date]
    release_date: Optional[date]
    actual_resolution_date: Optional[date]
    quantity_released: Optional[int]
    quantity_scrapped: Optional[int]
    aging_days: Optional[int]
    # P2-001: Hold duration fields
    hold_timestamp: Optional[datetime]
    resume_timestamp: Optional[datetime]
    resumed_by: Optional[int]
    status: Optional[str]
    total_hold_duration_hours: Optional[Decimal]
    notes: Optional[str]
    entered_by: int
    created_at: datetime
    updated_at: Optional[datetime]

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
