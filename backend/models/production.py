"""
Production entry models (Pydantic)
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class ProductionEntryCreate(BaseModel):
    """Create production entry - aligned with PRODUCTION_ENTRY schema"""
    # Multi-tenant isolation - REQUIRED
    client_id: str = Field(..., min_length=1, max_length=50)

    # References - REQUIRED
    product_id: int = Field(..., gt=0)
    shift_id: int = Field(..., gt=0)
    work_order_id: Optional[str] = Field(None, max_length=50, description="Work order reference")
    job_id: Optional[str] = Field(None, max_length=50, description="Job ID for job-level tracking")

    # Date tracking - both REQUIRED
    production_date: date = Field(..., description="Production date")
    shift_date: date = Field(..., description="Shift date - REQUIRED for KPI calculations")

    # Production metrics - REQUIRED for KPI calculations
    units_produced: int = Field(..., gt=0)
    run_time_hours: Decimal = Field(..., gt=0, le=24)
    employees_assigned: int = Field(..., gt=0, le=100)
    employees_present: Optional[int] = Field(None, ge=0, le=100, description="Employees actually present")

    # Quality metrics
    defect_count: int = Field(default=0, ge=0)
    scrap_count: int = Field(default=0, ge=0)
    rework_count: int = Field(default=0, ge=0)

    # Time breakdown
    setup_time_hours: Optional[Decimal] = Field(None, ge=0, le=24)
    downtime_hours: Optional[Decimal] = Field(None, ge=0, le=24)
    maintenance_hours: Optional[Decimal] = Field(None, ge=0, le=24)

    # Performance calculation inputs
    ideal_cycle_time: Optional[Decimal] = Field(None, gt=0, description="Hours per unit")

    # Metadata
    notes: Optional[str] = None
    entry_method: str = Field(default="MANUAL_ENTRY", description="MANUAL_ENTRY, CSV_UPLOAD, or API")

    @classmethod
    def from_legacy_csv(cls, data: dict) -> "ProductionEntryCreate":
        """Create from legacy CSV format with field mapping"""
        # Get production_date
        prod_date = data.get('production_date')

        # shift_date defaults to production_date if not provided
        shift_date = data.get('shift_date') or prod_date

        return cls(
            client_id=data.get('client_id', ''),
            product_id=int(data.get('product_id', 0)),
            shift_id=int(data.get('shift_id', 0)),
            work_order_id=data.get('work_order_number') or data.get('work_order_id'),
            job_id=data.get('job_id'),
            production_date=prod_date,
            shift_date=shift_date,
            units_produced=int(data.get('units_produced', 0)),
            run_time_hours=Decimal(str(data.get('run_time_hours', 0))),
            employees_assigned=int(data.get('employees_assigned', 1)),
            employees_present=int(data['employees_present']) if data.get('employees_present') else None,
            defect_count=int(data.get('defect_count', 0)),
            scrap_count=int(data.get('scrap_count', 0)),
            rework_count=int(data.get('rework_count', 0)),
            setup_time_hours=Decimal(str(data['setup_time_hours'])) if data.get('setup_time_hours') else None,
            downtime_hours=Decimal(str(data['downtime_hours'])) if data.get('downtime_hours') else None,
            maintenance_hours=Decimal(str(data['maintenance_hours'])) if data.get('maintenance_hours') else None,
            ideal_cycle_time=Decimal(str(data['ideal_cycle_time'])) if data.get('ideal_cycle_time') else None,
            notes=data.get('notes'),
            entry_method='CSV_UPLOAD'
        )


class ProductionEntryUpdate(BaseModel):
    """Update production entry"""
    units_produced: Optional[int] = Field(None, gt=0)
    run_time_hours: Optional[Decimal] = Field(None, gt=0, le=24)
    employees_assigned: Optional[int] = Field(None, gt=0, le=100)
    employees_present: Optional[int] = Field(None, ge=0, le=100)
    defect_count: Optional[int] = Field(None, ge=0)
    scrap_count: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    confirmed_by: Optional[int] = None
    entry_method: Optional[str] = None


class ProductionEntryResponse(BaseModel):
    """Production entry response - matches PRODUCTION_ENTRY schema"""
    production_entry_id: str
    client_id: str
    product_id: int
    shift_id: int
    work_order_id: Optional[str] = None
    job_id: Optional[str] = None
    production_date: datetime
    shift_date: datetime
    units_produced: int
    run_time_hours: Decimal
    employees_assigned: int
    employees_present: Optional[int] = None
    defect_count: int
    scrap_count: int
    rework_count: Optional[int] = None
    setup_time_hours: Optional[Decimal] = None
    downtime_hours: Optional[Decimal] = None
    maintenance_hours: Optional[Decimal] = None
    ideal_cycle_time: Optional[Decimal] = None
    actual_cycle_time: Optional[Decimal] = None
    efficiency_percentage: Optional[Decimal] = None
    performance_percentage: Optional[Decimal] = None
    quality_rate: Optional[Decimal] = None
    notes: Optional[str] = None
    entered_by: Optional[str] = None
    confirmed_by: Optional[str] = None
    confirmation_timestamp: Optional[datetime] = None
    entry_method: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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


class InferenceMetadata(BaseModel):
    """Inference metadata for KPI calculations - exposes ESTIMATED flag per audit requirement"""
    is_estimated: bool = Field(default=False, description="True if any values were inferred rather than from explicit standards")
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence score (0.0-1.0) for inferred values")
    inference_source: Optional[str] = Field(default=None, description="Source level: client_style_standard, shift_line_standard, industry_default, historical_30day_avg, global_product_avg, system_fallback")
    inference_warning: Optional[str] = Field(default=None, description="Warning message for low confidence estimates")


class KPICalculationResponse(BaseModel):
    """KPI calculation result with inference metadata"""
    entry_id: str  # production_entry_id is String
    efficiency_percentage: Decimal
    performance_percentage: Decimal
    quality_rate: Decimal
    ideal_cycle_time_used: Decimal
    was_inferred: bool  # Kept for backward compatibility
    calculation_timestamp: datetime
    # ENHANCEMENT: Full inference metadata (ESTIMATED flag) per audit requirement
    inference: Optional[InferenceMetadata] = Field(default=None, description="Inference metadata for estimated values")


class CSVUploadResponse(BaseModel):
    """CSV upload result"""
    total_rows: int
    successful: int
    failed: int
    errors: List[dict]
    created_entries: List[str]  # production_entry_id is String
