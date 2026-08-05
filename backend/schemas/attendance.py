"""
Attendance tracking models (Pydantic)
PHASE 3: Employee attendance and absenteeism
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from backend.orm.labor_taxonomy import HourCategoryEnum, LaborClassEnum  # noqa: F401  (enums re-exported)


class AbsenceTypeEnum(str, Enum):
    """Absence classification for absenteeism tracking - matches DB enum"""

    UNSCHEDULED_ABSENCE = "UNSCHEDULED_ABSENCE"  # Counts toward absenteeism
    VACATION = "VACATION"  # Scheduled, doesn't count
    MEDICAL_LEAVE = "MEDICAL_LEAVE"  # Counts toward absenteeism
    PERSONAL_LEAVE = "PERSONAL_LEAVE"  # Counts toward absenteeism


class AllocationItem(BaseModel):
    """One intra-day hour-allocation ledger row (Cycle 3 PR-A).

    Request-side only (Create/Update): ``hours`` is Decimal per this task's interface
    contract. Never wire this class as a field on a response_model — Pydantic v2
    serializes Decimal-typed fields as JSON strings, not numbers (see
    tests/test_models/test_decimal_response_serialization.py). AttendanceRecordResponse
    uses the float-typed AllocationItemResponse below instead.
    """

    category: HourCategoryEnum
    hours: Decimal = Field(gt=0, decimal_places=2)


class AllocationItemResponse(BaseModel):
    """Response-side counterpart of AllocationItem — hours as float so it serializes
    as a JSON number (see AllocationItem's docstring)."""

    category: HourCategoryEnum
    hours: float


class AttendanceRecordCreate(BaseModel):
    """Create attendance record - aligned with ATTENDANCE_ENTRY schema"""

    # Multi-tenant isolation - REQUIRED
    client_id: str = Field(..., min_length=1, max_length=50)

    # Employee reference - REQUIRED
    employee_id: int = Field(..., gt=0)
    line_id: Optional[int] = Field(None, description="Production line ID for line-level tracking")

    # Date tracking - shift_date is REQUIRED
    shift_date: date = Field(..., description="Shift date - REQUIRED for Absenteeism KPI")
    shift_id: Optional[int] = Field(None, gt=0, description="Shift ID")

    # Hours tracking - REQUIRED for Absenteeism calculation
    scheduled_hours: Decimal = Field(..., gt=0, le=24, decimal_places=2)
    actual_hours: Decimal = Field(default=Decimal("0"), ge=0, le=24, decimal_places=2)
    absence_hours: Decimal = Field(
        default=Decimal("0"), ge=0, le=24, decimal_places=2, description="scheduled - actual"
    )

    # Absence tracking
    is_absent: int = Field(default=0, ge=0, le=1, description="Boolean: 0=present, 1=absent")
    absence_type: Optional[AbsenceTypeEnum] = Field(None, description="Type of absence")

    # Coverage tracking - for floating pool assignments
    covered_by_employee_id: Optional[int] = Field(None, gt=0, description="Floating pool employee covering")
    coverage_confirmed: int = Field(default=0, ge=0, le=1, description="Boolean: 0=pending, 1=confirmed")

    # Late/early tracking
    arrival_time: Optional[datetime] = None
    departure_time: Optional[datetime] = None
    is_late: int = Field(default=0, ge=0, le=1)
    is_early_departure: int = Field(default=0, ge=0, le=1)

    # Metadata
    absence_reason: Optional[str] = None
    notes: Optional[str] = None

    # Labor-hours capture (Cycle 3 PR-A) — OT split (all-None = unsplit) + class override + allocations
    normal_hours: Optional[Decimal] = Field(
        None, ge=0, le=24, decimal_places=2, description="Straight-time hours (OT split tier)"
    )
    double_hours: Optional[Decimal] = Field(
        None, ge=0, le=24, decimal_places=2, description="Double-time hours (OT split tier)"
    )
    triple_hours: Optional[Decimal] = Field(
        None, ge=0, le=24, decimal_places=2, description="Triple-time hours (OT split tier)"
    )
    labor_class_override: Optional[LaborClassEnum] = Field(
        None, description="Per-entry direct/indirect override (NULL = use employee default)"
    )
    allocations: Optional[list[AllocationItem]] = Field(
        None, description="Intra-day hour-allocation ledger (replace-on-write)"
    )

    @classmethod
    def from_legacy_csv(cls, data: dict) -> "AttendanceRecordCreate":
        """Create from legacy CSV format with field mapping"""
        # Map legacy status to is_absent + absence_type
        status = (data.get("status") or "Present").upper()
        is_absent = 0
        absence_type = None

        if status == "ABSENT":
            is_absent = 1
            absence_type = AbsenceTypeEnum.UNSCHEDULED_ABSENCE
        elif status == "LATE":
            is_absent = 0  # Present but late
        elif status == "LEAVE":
            is_absent = 1
            absence_type = AbsenceTypeEnum.PERSONAL_LEAVE
        elif status == "VACATION":
            is_absent = 1
            absence_type = AbsenceTypeEnum.VACATION
        elif status == "MEDICAL":
            is_absent = 1
            absence_type = AbsenceTypeEnum.MEDICAL_LEAVE

        scheduled = Decimal(str(data.get("scheduled_hours", 8)))
        actual = Decimal(str(data.get("actual_hours_worked") or data.get("actual_hours", 0)))
        absence = scheduled - actual if is_absent else Decimal("0")

        return cls(
            client_id=data.get("client_id", ""),
            employee_id=int(data.get("employee_id", 0)),
            shift_date=data.get("shift_date") or data.get("attendance_date"),
            shift_id=int(data["shift_id"]) if data.get("shift_id") else None,
            scheduled_hours=scheduled,
            actual_hours=actual,
            absence_hours=absence,
            is_absent=is_absent,
            absence_type=absence_type,
            covered_by_employee_id=int(data["covered_by_employee_id"]) if data.get("covered_by_employee_id") else None,
            coverage_confirmed=int(data.get("coverage_confirmed", 0)),
            is_late=1 if status == "LATE" else 0,
            absence_reason=data.get("absence_reason"),
            notes=data.get("notes"),
            # Labor-hours capture (Cycle 3 PR-A, Task 6): optional OT split + class
            # override from CSV. `not in (None, "")` (not a truthy check) so an
            # explicit "0" tier is preserved rather than treated as absent.
            normal_hours=Decimal(str(data["normal_hours"])) if data.get("normal_hours") not in (None, "") else None,
            double_hours=Decimal(str(data["double_hours"])) if data.get("double_hours") not in (None, "") else None,
            triple_hours=Decimal(str(data["triple_hours"])) if data.get("triple_hours") not in (None, "") else None,
            labor_class_override=data.get("labor_class_override") or None,
        )


class AttendanceRecordUpdate(BaseModel):
    """Update attendance record"""

    line_id: Optional[int] = Field(None, description="Updated production line ID")
    status: Optional[str] = Field(None, max_length=20)
    actual_hours_worked: Optional[Decimal] = Field(None, ge=0, le=24, decimal_places=2)
    # Grid-style edits (useAttendanceGridData.ts buildPayload) send `actual_hours`,
    # matching AttendanceRecordCreate's field name and the ORM column name directly
    # (fix round 3, item 4 — actual_hours_worked above has never actually mapped
    # onto the ORM's `actual_hours` attribute; the update loop is a blind
    # hasattr-gated setattr, so a field name mismatch silently no-ops).
    actual_hours: Optional[Decimal] = Field(
        None, ge=0, le=24, decimal_places=2, description="Updated actual hours worked"
    )
    absence_reason: Optional[str] = Field(None, max_length=100)
    covered_by_employee_id: Optional[int] = Field(None, gt=0)
    coverage_confirmed: Optional[int] = Field(None, ge=0, le=1)
    notes: Optional[str] = None

    # Labor-hours capture (Cycle 3 PR-A) — OT split + class override + allocations (replace-on-write)
    normal_hours: Optional[Decimal] = Field(
        None, ge=0, le=24, decimal_places=2, description="Straight-time hours (OT split tier)"
    )
    double_hours: Optional[Decimal] = Field(
        None, ge=0, le=24, decimal_places=2, description="Double-time hours (OT split tier)"
    )
    triple_hours: Optional[Decimal] = Field(
        None, ge=0, le=24, decimal_places=2, description="Triple-time hours (OT split tier)"
    )
    labor_class_override: Optional[LaborClassEnum] = Field(
        None, description="Per-entry direct/indirect override (NULL = use employee default)"
    )
    allocations: Optional[list[AllocationItem]] = Field(
        None, description="Intra-day hour-allocation ledger; presence replaces the full list"
    )


class AttendanceRecordResponse(BaseModel):
    """Attendance record response - matches ATTENDANCE_ENTRY schema"""

    attendance_entry_id: str
    client_id: str
    employee_id: int
    line_id: Optional[int] = None
    shift_date: datetime
    shift_id: Optional[int] = None
    scheduled_hours: float
    actual_hours: Optional[float] = None
    absence_hours: Optional[float] = None
    is_absent: int
    absence_type: Optional[str] = None
    covered_by_employee_id: Optional[int] = None
    coverage_confirmed: Optional[int] = None
    arrival_time: Optional[datetime] = None
    departure_time: Optional[datetime] = None
    is_late: Optional[int] = None
    is_early_departure: Optional[int] = None
    absence_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Labor-hours capture (Cycle 3 PR-A) — raw columns.
    # float, not Decimal: response_model fields must serialize as JSON numbers, not
    # strings (see AllocationItem's docstring / test_decimal_response_serialization.py).
    normal_hours: Optional[float] = None
    double_hours: Optional[float] = None
    triple_hours: Optional[float] = None
    labor_class_override: Optional[str] = None

    # Labor-hours capture — derived fields (populated by crud layer; defaults let
    # model_validate(entry) succeed even though entry has no matching attribute)
    allocations: list[AllocationItemResponse] = Field(default_factory=list)
    billed_hours: float = Field(default=0.0)
    available_for_efficiency_hours: Optional[float] = None
    effective_labor_class: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


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
        description=(
            "Source level: client_style_standard, shift_line_standard, "
            "industry_default, historical_30day_avg, global_product_avg, "
            "system_fallback"
        ),
    )
    inference_warning: Optional[str] = Field(default=None, description="Warning message for low confidence estimates")


class AbsenteeismCalculationResponse(BaseModel):
    """Absenteeism KPI calculation"""

    shift_id: int
    start_date: date
    end_date: date
    total_scheduled_hours: float
    total_hours_worked: float
    total_hours_absent: float
    absenteeism_rate: float
    total_employees: int
    total_absences: int
    calculation_timestamp: datetime
    # ENHANCEMENT: Inference metadata (ESTIMATED flag) per audit requirement
    inference: Optional[InferenceMetadata] = Field(default=None, description="Inference metadata for estimated values")
