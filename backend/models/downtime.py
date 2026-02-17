"""
Downtime tracking models (Pydantic)
PHASE 2: Machine availability tracking
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class DowntimeReasonEnum(str, Enum):
    """Downtime categories for availability calculation - matches DB enum"""

    EQUIPMENT_FAILURE = "EQUIPMENT_FAILURE"
    MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE"
    SETUP_CHANGEOVER = "SETUP_CHANGEOVER"
    QUALITY_HOLD = "QUALITY_HOLD"
    MAINTENANCE = "MAINTENANCE"
    POWER_OUTAGE = "POWER_OUTAGE"
    OTHER = "OTHER"


class DowntimeEventCreate(BaseModel):
    """Create downtime event - aligned with DOWNTIME_ENTRY schema"""

    # Multi-tenant isolation - REQUIRED
    client_id: str = Field(..., min_length=1, max_length=50, description="Tenant client identifier for multi-tenant isolation")

    # Work order reference - REQUIRED (replaces product_id/shift_id)
    work_order_id: str = Field(..., min_length=1, max_length=50, description="Work order affected by this downtime event")

    # Date tracking - shift_date is REQUIRED
    shift_date: date = Field(..., description="Shift date - REQUIRED for Availability KPI")

    # Downtime classification - REQUIRED
    downtime_reason: DowntimeReasonEnum = Field(..., description="Downtime category enum")
    downtime_duration_minutes: int = Field(..., gt=0, le=1440, description="Duration in minutes (max 24h)")

    # Equipment details
    machine_id: Optional[str] = Field(None, max_length=100, description="Identifier of the machine or equipment affected")
    equipment_code: Optional[str] = Field(None, max_length=50, description="Equipment asset code for maintenance tracking")

    # Root cause analysis
    root_cause_category: Optional[str] = Field(None, max_length=100, description="Classification of the root cause for analysis")
    corrective_action: Optional[str] = Field(None, description="Description of corrective or preventive action taken")

    # Metadata
    notes: Optional[str] = Field(None, description="Additional context or observations about the downtime event")

    @classmethod
    def from_legacy_csv(cls, data: dict) -> "DowntimeEventCreate":
        """Create from legacy CSV format with field mapping"""
        # Map legacy category to enum
        category_mapping = {
            "EQUIPMENT": DowntimeReasonEnum.EQUIPMENT_FAILURE,
            "EQUIPMENT_FAILURE": DowntimeReasonEnum.EQUIPMENT_FAILURE,
            "MATERIAL": DowntimeReasonEnum.MATERIAL_SHORTAGE,
            "MATERIAL_SHORTAGE": DowntimeReasonEnum.MATERIAL_SHORTAGE,
            "SETUP": DowntimeReasonEnum.SETUP_CHANGEOVER,
            "SETUP_CHANGEOVER": DowntimeReasonEnum.SETUP_CHANGEOVER,
            "CHANGEOVER": DowntimeReasonEnum.SETUP_CHANGEOVER,
            "QUALITY": DowntimeReasonEnum.QUALITY_HOLD,
            "QUALITY_HOLD": DowntimeReasonEnum.QUALITY_HOLD,
            "MAINTENANCE": DowntimeReasonEnum.MAINTENANCE,
            "POWER": DowntimeReasonEnum.POWER_OUTAGE,
            "POWER_OUTAGE": DowntimeReasonEnum.POWER_OUTAGE,
        }

        raw_category = (data.get("downtime_category") or data.get("downtime_reason") or "OTHER").upper()
        reason_enum = category_mapping.get(raw_category, DowntimeReasonEnum.OTHER)

        # Convert hours to minutes if duration_hours provided
        duration_minutes = data.get("downtime_duration_minutes")
        if duration_minutes is None:
            duration_hours = float(data.get("duration_hours", 0))
            duration_minutes = int(duration_hours * 60)

        return cls(
            client_id=data.get("client_id", ""),
            work_order_id=data.get("work_order_number") or data.get("work_order_id", ""),
            shift_date=data.get("shift_date") or data.get("production_date"),
            downtime_reason=reason_enum,
            downtime_duration_minutes=duration_minutes,
            machine_id=data.get("machine_id"),
            equipment_code=data.get("equipment_code"),
            root_cause_category=data.get("root_cause_category"),
            corrective_action=data.get("corrective_action"),
            notes=data.get("notes"),
        )


class DowntimeEventUpdate(BaseModel):
    """Update downtime event"""

    downtime_category: Optional[str] = Field(None, max_length=50, description="Updated downtime classification category")
    downtime_reason: Optional[str] = Field(None, max_length=255, description="Updated detailed reason for the downtime")
    duration_hours: Optional[Decimal] = Field(None, gt=0, le=24, description="Updated downtime duration in hours")
    machine_id: Optional[str] = Field(None, max_length=50, description="Updated machine or equipment identifier")
    notes: Optional[str] = Field(None, description="Updated notes about the downtime event")


class DowntimeEventResponse(BaseModel):
    """Downtime event response - matches DOWNTIME_ENTRY schema"""

    downtime_entry_id: str = Field(..., description="Unique identifier for this downtime entry")
    client_id: str = Field(..., description="Tenant client identifier for data isolation")
    work_order_id: str = Field(..., description="Work order affected by this downtime event")
    shift_date: datetime = Field(..., description="Shift date when the downtime occurred")
    downtime_reason: str = Field(..., description="Category or reason for the downtime")
    downtime_duration_minutes: int = Field(..., description="Total downtime duration in minutes")
    machine_id: Optional[str] = Field(None, description="Machine or equipment identifier affected")
    equipment_code: Optional[str] = Field(None, description="Equipment asset code for maintenance tracking")
    root_cause_category: Optional[str] = Field(None, description="Classification of the root cause")
    corrective_action: Optional[str] = Field(None, description="Corrective or preventive action taken")
    notes: Optional[str] = Field(None, description="Additional context about the downtime event")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the record was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of the last modification")

    class Config:
        from_attributes = True


class AvailabilityCalculationResponse(BaseModel):
    """Availability KPI calculation"""

    product_id: int = Field(..., description="Product identifier for this availability calculation")
    shift_id: int = Field(..., description="Shift identifier for the calculation period")
    production_date: date = Field(..., description="Production date of the availability calculation")
    total_scheduled_hours: Decimal = Field(..., description="Total scheduled production hours for the period")
    total_downtime_hours: Decimal = Field(..., description="Sum of all downtime hours during the period")
    available_hours: Decimal = Field(..., description="Net available hours (scheduled minus downtime)")
    availability_percentage: Decimal = Field(..., description="Availability rate as percentage (available / scheduled * 100)")
    downtime_events: int = Field(..., description="Count of distinct downtime events in the period")
    calculation_timestamp: datetime = Field(..., description="Timestamp when this calculation was performed")
