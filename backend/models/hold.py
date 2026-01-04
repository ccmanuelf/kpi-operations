"""
WIP hold tracking models (Pydantic)
PHASE 2: Work-in-process aging tracking
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


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


class WIPHoldResponse(BaseModel):
    """WIP hold response"""
    hold_id: int
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
    notes: Optional[str]
    entered_by: int
    created_at: datetime
    updated_at: datetime

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
