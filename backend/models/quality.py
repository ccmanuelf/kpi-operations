"""
Quality metrics models (Pydantic)
PHASE 4: Detailed quality tracking
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class QualityInspectionCreate(BaseModel):
    """Create quality inspection record - aligned with QUALITY_ENTRY schema"""
    # Multi-tenant isolation - REQUIRED
    client_id: str = Field(..., min_length=1, max_length=50)

    # Work order reference - REQUIRED (replaces product_id/shift_id)
    work_order_id: str = Field(..., min_length=1, max_length=50)
    job_id: Optional[str] = Field(None, max_length=50, description="Job ID for job-level tracking")

    # Date tracking - shift_date is REQUIRED
    shift_date: date = Field(..., description="Shift date - REQUIRED for KPI calculations")
    inspection_date: Optional[date] = Field(None, description="Optional inspection date")

    # Inspection metrics - REQUIRED for KPI calculations
    units_inspected: int = Field(..., gt=0)
    units_passed: int = Field(..., ge=0, description="Units that passed inspection - for FPY")
    units_defective: int = Field(default=0, ge=0, description="Defective units - for PPM")
    total_defects_count: int = Field(default=0, ge=0, description="Total defects found - for DPMO")

    # Process tracking
    inspection_stage: Optional[str] = Field(None, max_length=50)  # Incoming, In-Process, Final
    process_step: Optional[str] = Field(None, max_length=100, description="For RTY calculation")
    operation_checked: Optional[str] = Field(None, max_length=50, description="Operation that was inspected")
    is_first_pass: int = Field(default=1, ge=0, le=1, description="1=first pass, 0=rework")

    # Disposition
    units_scrapped: int = Field(default=0, ge=0)
    units_reworked: int = Field(default=0, ge=0)
    units_requiring_repair: int = Field(default=0, ge=0, description="Units requiring repair")

    # Quality details
    inspection_method: Optional[str] = Field(None, max_length=100)

    # Metadata
    notes: Optional[str] = None

    # Legacy field aliases for CSV backwards compatibility
    @classmethod
    def from_legacy_csv(cls, data: dict) -> "QualityInspectionCreate":
        """Create from legacy CSV format with field mapping"""
        # Map legacy fields to new schema
        return cls(
            client_id=data.get('client_id', ''),
            work_order_id=data.get('work_order_number') or data.get('work_order_id', ''),
            job_id=data.get('job_id'),
            shift_date=data.get('shift_date') or data.get('inspection_date'),
            inspection_date=data.get('inspection_date'),
            units_inspected=data.get('units_inspected', 0),
            units_passed=data.get('units_passed') or (data.get('units_inspected', 0) - data.get('defects_found', 0)),
            units_defective=data.get('units_defective') or data.get('defects_found', 0),
            total_defects_count=data.get('total_defects_count') or data.get('defects_found', 0),
            inspection_stage=data.get('inspection_stage'),
            process_step=data.get('process_step'),
            operation_checked=data.get('operation_checked'),
            units_scrapped=data.get('units_scrapped') or data.get('scrap_units', 0),
            units_reworked=data.get('units_reworked') or data.get('rework_units', 0),
            units_requiring_repair=data.get('units_requiring_repair', 0),
            inspection_method=data.get('inspection_method'),
            notes=data.get('notes')
        )


class QualityInspectionUpdate(BaseModel):
    """Update quality inspection"""
    units_inspected: Optional[int] = Field(None, gt=0)
    defects_found: Optional[int] = Field(None, ge=0)
    defect_type: Optional[str] = Field(None, max_length=100)
    defect_category: Optional[str] = Field(None, max_length=50)
    scrap_units: Optional[int] = Field(None, ge=0)
    rework_units: Optional[int] = Field(None, ge=0)
    units_requiring_repair: Optional[int] = Field(None, ge=0)
    operation_checked: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class QualityInspectionResponse(BaseModel):
    """Quality inspection response - matches QUALITY_ENTRY schema"""
    quality_entry_id: str
    client_id: str
    work_order_id: str
    job_id: Optional[str] = None
    shift_date: datetime
    inspection_date: Optional[datetime] = None
    units_inspected: int
    units_passed: int
    units_defective: int
    total_defects_count: int
    inspection_stage: Optional[str] = None
    process_step: Optional[str] = None
    operation_checked: Optional[str] = None
    is_first_pass: Optional[int] = None
    units_scrapped: Optional[int] = None
    units_reworked: Optional[int] = None
    units_requiring_repair: Optional[int] = None
    ppm: Optional[Decimal] = None
    dpmo: Optional[Decimal] = None
    fpy_percentage: Optional[Decimal] = None
    inspection_method: Optional[str] = None
    inspector_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PPMCalculationResponse(BaseModel):
    """PPM (Parts Per Million) calculation with defect rate percentage"""
    product_id: int
    shift_id: int
    start_date: date
    end_date: date
    total_units_inspected: int
    total_defects: int
    ppm: Decimal
    defect_rate_percentage: Decimal  # PPM / 10,000 = percentage
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
