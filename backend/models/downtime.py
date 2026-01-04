"""
Downtime tracking models (Pydantic)
PHASE 2: Machine availability tracking
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class DowntimeEventCreate(BaseModel):
    """Create downtime event"""
    client_id: str = Field(..., min_length=1, max_length=50)
    product_id: int = Field(..., gt=0)
    shift_id: int = Field(..., gt=0)
    production_date: date
    downtime_category: str = Field(..., max_length=50)
    downtime_reason: str = Field(..., max_length=255)
    duration_hours: Decimal = Field(..., gt=0, le=24)
    machine_id: Optional[str] = Field(None, max_length=50)
    work_order_number: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class DowntimeEventUpdate(BaseModel):
    """Update downtime event"""
    downtime_category: Optional[str] = Field(None, max_length=50)
    downtime_reason: Optional[str] = Field(None, max_length=255)
    duration_hours: Optional[Decimal] = Field(None, gt=0, le=24)
    machine_id: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class DowntimeEventResponse(BaseModel):
    """Downtime event response"""
    downtime_id: int
    product_id: int
    shift_id: int
    production_date: date
    downtime_category: str
    downtime_reason: str
    duration_hours: Decimal
    machine_id: Optional[str]
    work_order_number: Optional[str]
    notes: Optional[str]
    entered_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvailabilityCalculationResponse(BaseModel):
    """Availability KPI calculation"""
    product_id: int
    shift_id: int
    production_date: date
    total_scheduled_hours: Decimal
    total_downtime_hours: Decimal
    available_hours: Decimal
    availability_percentage: Decimal
    downtime_events: int
    calculation_timestamp: datetime
