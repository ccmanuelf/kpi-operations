"""
Quality metrics models (Pydantic)
PHASE 4: Detailed quality tracking
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class QualityInspectionCreate(BaseModel):
    """Create quality inspection record"""
    product_id: int = Field(..., gt=0)
    shift_id: int = Field(..., gt=0)
    inspection_date: date
    work_order_number: Optional[str] = Field(None, max_length=50)
    units_inspected: int = Field(..., gt=0)
    defects_found: int = Field(default=0, ge=0)
    defect_type: Optional[str] = Field(None, max_length=100)
    defect_category: Optional[str] = Field(None, max_length=50)
    scrap_units: int = Field(default=0, ge=0)
    rework_units: int = Field(default=0, ge=0)
    inspection_stage: str = Field(..., max_length=50)  # Incoming, In-Process, Final
    notes: Optional[str] = None


class QualityInspectionUpdate(BaseModel):
    """Update quality inspection"""
    units_inspected: Optional[int] = Field(None, gt=0)
    defects_found: Optional[int] = Field(None, ge=0)
    defect_type: Optional[str] = Field(None, max_length=100)
    defect_category: Optional[str] = Field(None, max_length=50)
    scrap_units: Optional[int] = Field(None, ge=0)
    rework_units: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class QualityInspectionResponse(BaseModel):
    """Quality inspection response"""
    inspection_id: int
    product_id: int
    shift_id: int
    inspection_date: date
    work_order_number: Optional[str]
    units_inspected: int
    defects_found: int
    defect_type: Optional[str]
    defect_category: Optional[str]
    scrap_units: int
    rework_units: int
    inspection_stage: str
    ppm: Decimal
    dpmo: Decimal
    notes: Optional[str]
    entered_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PPMCalculationResponse(BaseModel):
    """PPM (Parts Per Million) calculation"""
    product_id: int
    shift_id: int
    start_date: date
    end_date: date
    total_units_inspected: int
    total_defects: int
    ppm: Decimal
    calculation_timestamp: datetime


class DPMOCalculationResponse(BaseModel):
    """DPMO (Defects Per Million Opportunities) calculation"""
    product_id: int
    shift_id: int
    start_date: date
    end_date: date
    total_units: int
    opportunities_per_unit: int
    total_defects: int
    dpmo: Decimal
    sigma_level: Decimal
    calculation_timestamp: datetime


class FPYRTYCalculationResponse(BaseModel):
    """FPY (First Pass Yield) and RTY (Rolled Throughput Yield) calculation"""
    product_id: int
    start_date: date
    end_date: date
    total_units: int
    first_pass_good: int
    fpy_percentage: Decimal
    rty_percentage: Decimal
    total_process_steps: int
    calculation_timestamp: datetime
