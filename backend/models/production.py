"""
Production entry models (Pydantic)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Union, Any
from datetime import date, datetime
from decimal import Decimal


class ProductionEntryCreate(BaseModel):
    """Create production entry - aligned with PRODUCTION_ENTRY schema"""

    # Multi-tenant isolation - REQUIRED
    client_id: str = Field(..., min_length=1, max_length=50, description="Tenant client identifier for multi-tenant isolation")

    # References - REQUIRED
    product_id: int = Field(..., gt=0, description="Product being manufactured in this entry")
    shift_id: int = Field(..., gt=0, description="Shift during which production occurred")
    work_order_id: Optional[str] = Field(None, max_length=50, description="Work order reference")
    job_id: Optional[str] = Field(None, max_length=50, description="Job ID for job-level tracking")

    # Date tracking - both REQUIRED
    production_date: date = Field(..., description="Production date")
    shift_date: date = Field(..., description="Shift date - REQUIRED for KPI calculations")

    # Production metrics - REQUIRED for KPI calculations
    units_produced: int = Field(..., gt=0, description="Total good units produced during this entry")
    run_time_hours: Decimal = Field(..., gt=0, le=24, description="Actual machine run time in hours")
    employees_assigned: int = Field(..., gt=0, le=100, description="Number of employees scheduled for the shift")
    employees_present: Optional[int] = Field(None, ge=0, le=100, description="Employees actually present")

    # Quality metrics
    defect_count: int = Field(default=0, ge=0, description="Number of defective units identified during production")
    scrap_count: int = Field(default=0, ge=0, description="Number of units scrapped and not recoverable")
    rework_count: int = Field(default=0, ge=0, description="Number of units requiring rework to meet specifications")

    # Time breakdown
    setup_time_hours: Optional[Decimal] = Field(None, ge=0, le=24, description="Time spent on machine setup and changeover in hours")
    downtime_hours: Optional[Decimal] = Field(None, ge=0, le=24, description="Unplanned downtime during the shift in hours")
    maintenance_hours: Optional[Decimal] = Field(None, ge=0, le=24, description="Planned maintenance time during the shift in hours")

    # Performance calculation inputs
    ideal_cycle_time: Optional[Decimal] = Field(None, gt=0, description="Hours per unit")

    # Metadata
    notes: Optional[str] = Field(None, description="Operator notes or comments about this production entry")
    entry_method: str = Field(default="MANUAL_ENTRY", description="MANUAL_ENTRY, CSV_UPLOAD, or API")

    @classmethod
    def from_legacy_csv(cls, data: dict) -> "ProductionEntryCreate":
        """Create from legacy CSV format with field mapping"""
        # Get production_date
        prod_date = data.get("production_date")

        # shift_date defaults to production_date if not provided
        shift_date = data.get("shift_date") or prod_date

        return cls(
            client_id=data.get("client_id", ""),
            product_id=int(data.get("product_id", 0)),
            shift_id=int(data.get("shift_id", 0)),
            work_order_id=data.get("work_order_number") or data.get("work_order_id"),
            job_id=data.get("job_id"),
            production_date=prod_date,
            shift_date=shift_date,
            units_produced=int(data.get("units_produced", 0)),
            run_time_hours=Decimal(str(data.get("run_time_hours", 0))),
            employees_assigned=int(data.get("employees_assigned", 1)),
            employees_present=int(data["employees_present"]) if data.get("employees_present") else None,
            defect_count=int(data.get("defect_count", 0)),
            scrap_count=int(data.get("scrap_count", 0)),
            rework_count=int(data.get("rework_count", 0)),
            setup_time_hours=Decimal(str(data["setup_time_hours"])) if data.get("setup_time_hours") else None,
            downtime_hours=Decimal(str(data["downtime_hours"])) if data.get("downtime_hours") else None,
            maintenance_hours=Decimal(str(data["maintenance_hours"])) if data.get("maintenance_hours") else None,
            ideal_cycle_time=Decimal(str(data["ideal_cycle_time"])) if data.get("ideal_cycle_time") else None,
            notes=data.get("notes"),
            entry_method="CSV_UPLOAD",
        )


class ProductionEntryUpdate(BaseModel):
    """Update production entry"""

    units_produced: Optional[int] = Field(None, gt=0, description="Updated count of good units produced")
    run_time_hours: Optional[Decimal] = Field(None, gt=0, le=24, description="Updated machine run time in hours")
    employees_assigned: Optional[int] = Field(None, gt=0, le=100, description="Updated number of employees scheduled")
    employees_present: Optional[int] = Field(None, ge=0, le=100, description="Updated count of employees actually present")
    defect_count: Optional[int] = Field(None, ge=0, description="Updated number of defective units")
    scrap_count: Optional[int] = Field(None, ge=0, description="Updated number of scrapped units")
    notes: Optional[str] = Field(None, description="Updated operator notes or comments")
    confirmed_by: Optional[Union[str, int]] = Field(None, description="User ID of the supervisor who confirmed this entry")
    entry_method: Optional[str] = Field(None, description="How this entry was created: MANUAL_ENTRY, CSV_UPLOAD, or API")


class ProductionEntryResponse(BaseModel):
    """Production entry response - matches PRODUCTION_ENTRY schema"""

    production_entry_id: str = Field(..., description="Unique identifier for this production entry")
    client_id: str = Field(..., description="Tenant client identifier for data isolation")
    product_id: int = Field(..., description="Product manufactured in this entry")
    shift_id: int = Field(..., description="Shift during which production occurred")
    work_order_id: Optional[str] = Field(None, description="Associated work order reference")
    job_id: Optional[str] = Field(None, description="Job-level tracking identifier")
    production_date: datetime = Field(..., description="Date when production took place")
    shift_date: datetime = Field(..., description="Shift date used for KPI calculations")
    units_produced: int = Field(..., description="Total good units produced")
    run_time_hours: Decimal = Field(..., description="Actual machine run time in hours")
    employees_assigned: int = Field(..., description="Number of employees scheduled for the shift")
    employees_present: Optional[int] = Field(None, description="Number of employees actually present")
    defect_count: int = Field(..., description="Number of defective units identified")
    scrap_count: int = Field(..., description="Number of units scrapped")
    rework_count: Optional[int] = Field(None, description="Number of units requiring rework")
    setup_time_hours: Optional[Decimal] = Field(None, description="Machine setup and changeover time in hours")
    downtime_hours: Optional[Decimal] = Field(None, description="Unplanned downtime during the shift in hours")
    maintenance_hours: Optional[Decimal] = Field(None, description="Planned maintenance time in hours")
    ideal_cycle_time: Optional[Decimal] = Field(None, description="Standard hours per unit for performance calculation")
    actual_cycle_time: Optional[Decimal] = Field(None, description="Measured hours per unit from actual production")
    efficiency_percentage: Optional[Decimal] = Field(None, description="Production efficiency as a percentage")
    performance_percentage: Optional[Decimal] = Field(None, description="OEE performance component as a percentage")
    quality_rate: Optional[Decimal] = Field(None, description="Quality rate: good units divided by total units produced")
    notes: Optional[str] = Field(None, description="Operator notes or comments about this entry")
    entered_by: Optional[Union[str, int]] = Field(None, description="User ID of the person who created this entry")
    confirmed_by: Optional[Union[str, int]] = Field(None, description="User ID of the supervisor who confirmed this entry")
    confirmation_timestamp: Optional[datetime] = Field(None, description="Timestamp when the entry was confirmed by a supervisor")
    entry_method: Optional[str] = Field(None, description="How this entry was created: MANUAL_ENTRY, CSV_UPLOAD, or API")
    updated_by: Optional[Union[str, int]] = Field(None, description="User ID of the person who last modified this entry")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the record was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of the last modification")

    class Config:
        from_attributes = True


class ProductionEntryWithKPIs(ProductionEntryResponse):
    """Production entry with detailed KPI breakdown"""

    product_name: str = Field(..., description="Display name of the product manufactured")
    shift_name: str = Field(..., description="Display name of the production shift")
    ideal_cycle_time: Optional[Decimal] = Field(None, description="Standard hours per unit used in KPI calculation")
    inferred_cycle_time: bool = Field(False, description="Whether the cycle time was inferred rather than explicitly set")

    # Calculated values
    total_available_hours: Decimal = Field(..., description="Total available production hours after deducting downtime")
    quality_rate: Decimal = Field(..., description="Quality rate: good units divided by total units produced")
    oee: Optional[Decimal] = Field(None, description="Overall Equipment Effectiveness combining availability, performance, and quality")


class InferenceMetadata(BaseModel):
    """Inference metadata for KPI calculations - exposes ESTIMATED flag per audit requirement"""

    is_estimated: bool = Field(
        default=False, description="True if any values were inferred rather than from explicit standards"
    )
    confidence_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Confidence score (0.0-1.0) for inferred values"
    )
    inference_source: Optional[str] = Field(
        default=None,
        description="Source level: client_style_standard, shift_line_standard, industry_default, historical_30day_avg, global_product_avg, system_fallback",
    )
    inference_warning: Optional[str] = Field(default=None, description="Warning message for low confidence estimates")


class KPICalculationResponse(BaseModel):
    """KPI calculation result with inference metadata"""

    entry_id: str = Field(..., description="Production entry ID this calculation applies to")
    efficiency_percentage: Decimal = Field(..., description="Production efficiency as a percentage")
    performance_percentage: Decimal = Field(..., description="OEE performance component as a percentage")
    quality_rate: Decimal = Field(..., description="Quality rate: good units divided by total units produced")
    ideal_cycle_time_used: Decimal = Field(..., description="Ideal cycle time value used in this calculation (hours per unit)")
    was_inferred: bool = Field(..., description="Whether the ideal cycle time was inferred rather than explicitly set")
    calculation_timestamp: datetime = Field(..., description="Timestamp when this KPI calculation was performed")
    # ENHANCEMENT: Full inference metadata (ESTIMATED flag) per audit requirement
    inference: Optional[InferenceMetadata] = Field(default=None, description="Inference metadata for estimated values")


class CSVUploadResponse(BaseModel):
    """CSV upload result"""

    total_rows: int = Field(..., description="Total number of rows processed from the CSV file")
    successful: int = Field(..., description="Number of rows successfully imported")
    failed: int = Field(..., description="Number of rows that failed validation or import")
    errors: List[dict] = Field(..., description="List of error details for each failed row")
    created_entries: List[str] = Field(..., description="List of production entry IDs created from successful rows")
