"""
Production entry models (Pydantic)
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class ProductionEntryCreate(BaseModel):
    """Create production entry"""
    product_id: int = Field(..., gt=0)
    shift_id: int = Field(..., gt=0)
    production_date: date
    work_order_number: Optional[str] = Field(None, max_length=50)
    units_produced: int = Field(..., gt=0)
    run_time_hours: Decimal = Field(..., gt=0, le=24)
    employees_assigned: int = Field(..., gt=0, le=100)
    defect_count: int = Field(default=0, ge=0)
    scrap_count: int = Field(default=0, ge=0)
    notes: Optional[str] = None


class ProductionEntryUpdate(BaseModel):
    """Update production entry"""
    units_produced: Optional[int] = Field(None, gt=0)
    run_time_hours: Optional[Decimal] = Field(None, gt=0, le=24)
    employees_assigned: Optional[int] = Field(None, gt=0, le=100)
    defect_count: Optional[int] = Field(None, ge=0)
    scrap_count: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    confirmed_by: Optional[int] = None


class ProductionEntryResponse(BaseModel):
    """Production entry response"""
    entry_id: int
    product_id: int
    shift_id: int
    production_date: date
    work_order_number: Optional[str]
    units_produced: int
    run_time_hours: Decimal
    employees_assigned: int
    defect_count: int
    scrap_count: int
    efficiency_percentage: Optional[Decimal]
    performance_percentage: Optional[Decimal]
    notes: Optional[str]
    entered_by: int
    confirmed_by: Optional[int]
    confirmation_timestamp: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductionEntryWithKPIs(ProductionEntryResponse):
    """Production entry with detailed KPI breakdown"""
    product_name: str
    shift_name: str
    ideal_cycle_time: Optional[Decimal]
    inferred_cycle_time: bool = False

    # Calculated values
    total_available_hours: Decimal
    quality_rate: Decimal
    oee: Optional[Decimal] = None


class KPICalculationResponse(BaseModel):
    """KPI calculation result"""
    entry_id: int
    efficiency_percentage: Decimal
    performance_percentage: Decimal
    quality_rate: Decimal
    ideal_cycle_time_used: Decimal
    was_inferred: bool
    calculation_timestamp: datetime


class CSVUploadResponse(BaseModel):
    """CSV upload result"""
    total_rows: int
    successful: int
    failed: int
    errors: List[dict]
    created_entries: List[int]
