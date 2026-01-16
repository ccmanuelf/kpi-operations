"""
Attendance tracking models (Pydantic)
PHASE 3: Employee attendance and absenteeism
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class AbsenceTypeEnum(str, Enum):
    """Absence classification for absenteeism tracking - matches DB enum"""
    UNSCHEDULED_ABSENCE = "UNSCHEDULED_ABSENCE"  # Counts toward absenteeism
    VACATION = "VACATION"                        # Scheduled, doesn't count
    MEDICAL_LEAVE = "MEDICAL_LEAVE"              # Counts toward absenteeism
    PERSONAL_LEAVE = "PERSONAL_LEAVE"            # Counts toward absenteeism


class AttendanceRecordCreate(BaseModel):
    """Create attendance record - aligned with ATTENDANCE_ENTRY schema"""
    # Multi-tenant isolation - REQUIRED
    client_id: str = Field(..., min_length=1, max_length=50)

    # Employee reference - REQUIRED
    employee_id: int = Field(..., gt=0)

    # Date tracking - shift_date is REQUIRED
    shift_date: date = Field(..., description="Shift date - REQUIRED for Absenteeism KPI")
    shift_id: Optional[int] = Field(None, gt=0, description="Shift ID")

    # Hours tracking - REQUIRED for Absenteeism calculation
    scheduled_hours: Decimal = Field(..., gt=0, le=24)
    actual_hours: Decimal = Field(default=Decimal('0'), ge=0, le=24)
    absence_hours: Decimal = Field(default=Decimal('0'), ge=0, le=24, description="scheduled - actual")

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

    @classmethod
    def from_legacy_csv(cls, data: dict) -> "AttendanceRecordCreate":
        """Create from legacy CSV format with field mapping"""
        # Map legacy status to is_absent + absence_type
        status = (data.get('status') or 'Present').upper()
        is_absent = 0
        absence_type = None

        if status == 'ABSENT':
            is_absent = 1
            absence_type = AbsenceTypeEnum.UNSCHEDULED_ABSENCE
        elif status == 'LATE':
            is_absent = 0  # Present but late
        elif status == 'LEAVE':
            is_absent = 1
            absence_type = AbsenceTypeEnum.PERSONAL_LEAVE
        elif status == 'VACATION':
            is_absent = 1
            absence_type = AbsenceTypeEnum.VACATION
        elif status == 'MEDICAL':
            is_absent = 1
            absence_type = AbsenceTypeEnum.MEDICAL_LEAVE

        scheduled = Decimal(str(data.get('scheduled_hours', 8)))
        actual = Decimal(str(data.get('actual_hours_worked') or data.get('actual_hours', 0)))
        absence = scheduled - actual if is_absent else Decimal('0')

        return cls(
            client_id=data.get('client_id', ''),
            employee_id=int(data.get('employee_id', 0)),
            shift_date=data.get('shift_date') or data.get('attendance_date'),
            shift_id=int(data['shift_id']) if data.get('shift_id') else None,
            scheduled_hours=scheduled,
            actual_hours=actual,
            absence_hours=absence,
            is_absent=is_absent,
            absence_type=absence_type,
            covered_by_employee_id=int(data['covered_by_employee_id']) if data.get('covered_by_employee_id') else None,
            coverage_confirmed=int(data.get('coverage_confirmed', 0)),
            is_late=1 if status == 'LATE' else 0,
            absence_reason=data.get('absence_reason'),
            notes=data.get('notes')
        )


class AttendanceRecordUpdate(BaseModel):
    """Update attendance record"""
    status: Optional[str] = Field(None, max_length=20)
    actual_hours_worked: Optional[Decimal] = Field(None, ge=0, le=24)
    absence_reason: Optional[str] = Field(None, max_length=100)
    covered_by_employee_id: Optional[int] = Field(None, gt=0)
    coverage_confirmed: Optional[int] = Field(None, ge=0, le=1)
    notes: Optional[str] = None


class AttendanceRecordResponse(BaseModel):
    """Attendance record response"""
    attendance_id: int
    employee_id: int
    shift_id: int
    attendance_date: date
    status: str
    scheduled_hours: Decimal
    actual_hours_worked: Decimal
    absence_reason: Optional[str]
    covered_by_employee_id: Optional[int] = None
    coverage_confirmed: Optional[int] = None
    notes: Optional[str]
    entered_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AbsenteeismCalculationResponse(BaseModel):
    """Absenteeism KPI calculation"""
    shift_id: int
    start_date: date
    end_date: date
    total_scheduled_hours: Decimal
    total_hours_worked: Decimal
    total_hours_absent: Decimal
    absenteeism_rate: Decimal
    total_employees: int
    total_absences: int
    calculation_timestamp: datetime
