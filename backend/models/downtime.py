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
    client_id: str = Field(..., min_length=1, max_length=50)

    # Work order reference - REQUIRED (replaces product_id/shift_id)
    work_order_id: str = Field(..., min_length=1, max_length=50)

    # Date tracking - shift_date is REQUIRED
    shift_date: date = Field(..., description="Shift date - REQUIRED for Availability KPI")

    # Downtime classification - REQUIRED
    downtime_reason: DowntimeReasonEnum = Field(..., description="Downtime category enum")
    downtime_duration_minutes: int = Field(..., gt=0, le=1440, description="Duration in minutes (max 24h)")

    # Equipment details
    machine_id: Optional[str] = Field(None, max_length=100)
    equipment_code: Optional[str] = Field(None, max_length=50)

    # Root cause analysis
    root_cause_category: Optional[str] = Field(None, max_length=100)
    corrective_action: Optional[str] = None

    # Metadata
    notes: Optional[str] = None

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

        raw_category = (data.get('downtime_category') or data.get('downtime_reason') or 'OTHER').upper()
        reason_enum = category_mapping.get(raw_category, DowntimeReasonEnum.OTHER)

        # Convert hours to minutes if duration_hours provided
        duration_minutes = data.get('downtime_duration_minutes')
        if duration_minutes is None:
            duration_hours = float(data.get('duration_hours', 0))
            duration_minutes = int(duration_hours * 60)

        return cls(
            client_id=data.get('client_id', ''),
            work_order_id=data.get('work_order_number') or data.get('work_order_id', ''),
            shift_date=data.get('shift_date') or data.get('production_date'),
            downtime_reason=reason_enum,
            downtime_duration_minutes=duration_minutes,
            machine_id=data.get('machine_id'),
            equipment_code=data.get('equipment_code'),
            root_cause_category=data.get('root_cause_category'),
            corrective_action=data.get('corrective_action'),
            notes=data.get('notes')
        )


class DowntimeEventUpdate(BaseModel):
    """Update downtime event"""
    downtime_category: Optional[str] = Field(None, max_length=50)
    downtime_reason: Optional[str] = Field(None, max_length=255)
    duration_hours: Optional[Decimal] = Field(None, gt=0, le=24)
    machine_id: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class DowntimeEventResponse(BaseModel):
    """Downtime event response - matches DOWNTIME_ENTRY schema"""
    downtime_entry_id: str
    client_id: str
    work_order_id: str
    shift_date: datetime
    downtime_reason: str
    downtime_duration_minutes: int
    machine_id: Optional[str] = None
    equipment_code: Optional[str] = None
    root_cause_category: Optional[str] = None
    corrective_action: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
