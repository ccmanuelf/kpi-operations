"""
Attendance tracking models (Pydantic)
PHASE 3: Employee attendance and absenteeism
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class AttendanceRecordCreate(BaseModel):
    """Create attendance record"""
    employee_id: int = Field(..., gt=0)
    shift_id: int = Field(..., gt=0)
    attendance_date: date
    status: str = Field(..., max_length=20)  # Present, Absent, Late, Leave
    scheduled_hours: Decimal = Field(..., gt=0, le=24)
    actual_hours_worked: Decimal = Field(default=Decimal('0'), ge=0, le=24)
    absence_reason: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class AttendanceRecordUpdate(BaseModel):
    """Update attendance record"""
    status: Optional[str] = Field(None, max_length=20)
    actual_hours_worked: Optional[Decimal] = Field(None, ge=0, le=24)
    absence_reason: Optional[str] = Field(None, max_length=100)
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
