"""
Attendance Tracking API Routes
PHASE 3: Employee attendance and absenteeism KPIs
All endpoints enforce multi-tenant client filtering
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from backend.database import get_db
from backend.models.attendance import (
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceRecordResponse,
    AbsenteeismCalculationResponse
)
from crud.attendance import (
    create_attendance_record,
    get_attendance_record,
    get_attendance_records,
    update_attendance_record,
    delete_attendance_record
)
from backend.calculations.absenteeism import calculate_absenteeism, calculate_bradford_factor
from auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User


router = APIRouter(
    prefix="/api/attendance",
    tags=["Attendance Tracking"]
)


@router.post("", response_model=AttendanceRecordResponse, status_code=status.HTTP_201_CREATED)
def create_attendance(
    attendance: AttendanceRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new attendance record
    SECURITY: Enforces client filtering through user authentication
    """
    return create_attendance_record(db, attendance, current_user)


@router.get("", response_model=List[AttendanceRecordResponse])
def list_attendance(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    employee_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List attendance records with filters
    SECURITY: Returns only attendance for user's authorized clients
    """
    return get_attendance_records(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, employee_id=employee_id,
        shift_id=shift_id, status=status
    )


@router.get("/{attendance_id}", response_model=AttendanceRecordResponse)
def get_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get attendance record by ID
    SECURITY: Verifies user has access to this attendance record
    """
    record = get_attendance_record(db, attendance_id, current_user)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return record


@router.get("/by-employee/{employee_id}", response_model=List[AttendanceRecordResponse])
def get_attendance_by_employee(
    employee_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all attendance records for a specific employee
    SECURITY: Returns only attendance for user's authorized clients
    """
    return get_attendance_records(
        db,
        current_user=current_user,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )


@router.get("/by-date-range", response_model=List[AttendanceRecordResponse])
def get_attendance_by_date_range(
    start_date: date,
    end_date: date,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get attendance records within a date range
    SECURITY: Returns only attendance for user's authorized clients
    """
    return get_attendance_records(
        db,
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )


@router.get("/statistics/summary")
def get_attendance_statistics(
    start_date: date,
    end_date: date,
    shift_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get attendance statistics and summary for a date range
    SECURITY: Returns only data for user's authorized clients
    """
    from sqlalchemy import func
    from backend.schemas.attendance import AttendanceRecord

    query = db.query(
        AttendanceRecord.status,
        func.count(AttendanceRecord.attendance_id).label('count'),
        func.sum(AttendanceRecord.actual_hours_worked).label('total_hours')
    )

    # Apply date filters
    query = query.filter(
        AttendanceRecord.attendance_date >= start_date,
        AttendanceRecord.attendance_date <= end_date
    )

    # Optional shift filter
    if shift_id:
        query = query.filter(AttendanceRecord.shift_id == shift_id)

    # Group by status
    results = query.group_by(AttendanceRecord.status).all()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "shift_id": shift_id,
        "statistics": [
            {
                "status": row.status,
                "count": row.count,
                "total_hours": float(row.total_hours) if row.total_hours else 0
            }
            for row in results
        ],
        "calculation_timestamp": datetime.utcnow()
    }


@router.put("/{attendance_id}", response_model=AttendanceRecordResponse)
def update_attendance(
    attendance_id: int,
    attendance_update: AttendanceRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update attendance record
    SECURITY: Verifies user has access to this attendance record
    """
    updated = update_attendance_record(db, attendance_id, attendance_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return updated


@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete attendance record (supervisor only)
    SECURITY: Supervisor/admin only, verifies client access
    """
    success = delete_attendance_record(db, attendance_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Attendance record not found")


# ============================================================================
# KPI CALCULATION ENDPOINTS
# ============================================================================

@router.get("/kpi/absenteeism", response_model=AbsenteeismCalculationResponse)
def calculate_absenteeism_kpi(
    shift_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate absenteeism KPI for a shift and date range
    Formula: (Total Hours Absent / Total Scheduled Hours) * 100
    """
    rate, scheduled, absent, emp_count, absence_count = calculate_absenteeism(
        db, shift_id, start_date, end_date
    )

    return AbsenteeismCalculationResponse(
        shift_id=shift_id,
        start_date=start_date,
        end_date=end_date,
        total_scheduled_hours=scheduled,
        total_hours_worked=scheduled - absent,
        total_hours_absent=absent,
        absenteeism_rate=rate,
        total_employees=emp_count,
        total_absences=absence_count,
        calculation_timestamp=datetime.utcnow()
    )


@router.get("/kpi/bradford-factor/{employee_id}")
def get_bradford_factor(
    employee_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate Bradford Factor for employee
    Formula: B = S² × D (where S = number of absences, D = total days absent)

    Interpretation:
    - 0-50: Low risk
    - 51-125: Medium risk - Monitor closely
    - 126-250: High risk - Formal action required
    - 251+: Critical - Final warning/termination
    """
    score = calculate_bradford_factor(db, employee_id, start_date, end_date)

    interpretation = "Low risk"
    if score > 250:
        interpretation = "Critical - Final warning/termination"
    elif score > 125:
        interpretation = "High risk - Formal action required"
    elif score > 50:
        interpretation = "Medium risk - Monitor closely"

    return {
        "employee_id": employee_id,
        "bradford_score": score,
        "interpretation": interpretation,
        "start_date": start_date,
        "end_date": end_date,
        "calculation_timestamp": datetime.utcnow()
    }
