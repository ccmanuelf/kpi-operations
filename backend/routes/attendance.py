"""
Attendance Tracking API Routes
PHASE 3: Employee attendance and absenteeism KPIs
All endpoints enforce multi-tenant client filtering
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import case
from typing import List, Optional
from datetime import date, datetime

from backend.database import get_db
from backend.utils.logging_utils import get_module_logger, log_operation, log_error

logger = get_module_logger(__name__)
from backend.models.attendance import (
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceRecordResponse,
    AbsenteeismCalculationResponse
)
from backend.crud.attendance import (
    create_attendance_record,
    get_attendance_record,
    get_attendance_records,
    update_attendance_record,
    delete_attendance_record
)
from backend.calculations.absenteeism import calculate_absenteeism, calculate_bradford_factor
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User
from backend.middleware.client_auth import build_client_filter_clause, verify_client_access


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
    try:
        result = create_attendance_record(db, attendance, current_user)
        log_operation(logger, "CREATE", "attendance",
                     resource_id=str(result.attendance_entry_id),
                     user_id=current_user.user_id,
                     client_id=getattr(attendance, 'client_id', None))
        return result
    except Exception as e:
        log_error(logger, "CREATE", "attendance", e,
                 user_id=current_user.user_id,
                 client_id=getattr(attendance, 'client_id', None))
        raise


@router.get("", response_model=List[AttendanceRecordResponse])
def list_attendance(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    employee_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    is_absent: Optional[int] = None,
    client_id: Optional[str] = None,
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
        shift_id=shift_id, is_absent=is_absent, client_id=client_id
    )


@router.get("/{attendance_id}", response_model=AttendanceRecordResponse)
def get_attendance(
    attendance_id: str,
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
    client_id: Optional[str] = None,
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

    # SECURITY FIX (VULN-003): Apply client filter to prevent cross-client data access
    if client_id:
        verify_client_access(current_user, client_id)
        query = query.filter(AttendanceRecord.client_id == client_id)
    else:
        client_filter = build_client_filter_clause(current_user, AttendanceRecord.client_id)
        if client_filter is not None:
            query = query.filter(client_filter)

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
    try:
        updated = update_attendance_record(db, attendance_id, attendance_update, current_user)
        if not updated:
            raise HTTPException(status_code=404, detail="Attendance record not found")
        log_operation(logger, "UPDATE", "attendance",
                     resource_id=str(attendance_id),
                     user_id=current_user.user_id)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "UPDATE", "attendance", e,
                 resource_id=str(attendance_id),
                 user_id=current_user.user_id)
        raise


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
    try:
        success = delete_attendance_record(db, attendance_id, current_user)
        if not success:
            raise HTTPException(status_code=404, detail="Attendance record not found")
        log_operation(logger, "DELETE", "attendance",
                     resource_id=str(attendance_id),
                     user_id=current_user.user_id)
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "DELETE", "attendance", e,
                 resource_id=str(attendance_id),
                 user_id=current_user.user_id)
        raise


# ============================================================================
# KPI CALCULATION ENDPOINTS
# ============================================================================

@router.get("/kpi/absenteeism")
def calculate_absenteeism_kpi(
    shift_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate absenteeism KPI for a shift and date range with client filtering
    Formula: (Total Hours Absent / Total Scheduled Hours) * 100

    Parameters are optional - defaults to all shifts and last 30 days

    Returns extended data including:
    - by_reason: Breakdown of absences by reason/type
    - by_department: Absenteeism rates by client/department
    - high_absence_employees: Employees with high absence counts
    """
    from datetime import timedelta
    from backend.schemas.attendance_entry import AttendanceEntry
    from sqlalchemy import func, desc

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Date filter conditions
    date_filter = [
        AttendanceEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        AttendanceEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    ]

    # Build base query with client filter - using ATTENDANCE_ENTRY table
    # Calculate absent hours from absence_hours column or scheduled - actual
    query = db.query(
        func.sum(AttendanceEntry.scheduled_hours).label('scheduled'),
        func.sum(func.coalesce(AttendanceEntry.absence_hours, AttendanceEntry.scheduled_hours - func.coalesce(AttendanceEntry.actual_hours, 0))).label('absent'),
        func.count(func.distinct(AttendanceEntry.employee_id)).label('emp_count'),
        func.sum(case((AttendanceEntry.is_absent == 1, 1), else_=0)).label('absence_count')
    ).filter(*date_filter)

    # Apply optional filters
    if shift_id:
        query = query.filter(AttendanceEntry.shift_id == shift_id)
    if effective_client_id:
        query = query.filter(AttendanceEntry.client_id == effective_client_id)

    result = query.first()
    scheduled = float(result.scheduled or 0)
    absent = float(result.absent or 0)
    emp_count = result.emp_count or 0
    absence_count = result.absence_count or 0
    rate = (absent / scheduled * 100) if scheduled > 0 else 0

    # Get shift_id for response if not provided
    if shift_id is None:
        from backend.schemas.shift import Shift
        first_shift = db.query(Shift).first()
        shift_id = first_shift.shift_id if first_shift else 1

    # ========================================
    # Additional breakdown data for tables
    # ========================================

    # 1. Absence by reason/type - use raw SQL to avoid enum issues
    from sqlalchemy import text
    reason_sql = """
        SELECT
            COALESCE(absence_type, 'Unspecified') as reason,
            COUNT(*) as count
        FROM ATTENDANCE_ENTRY
        WHERE shift_date >= :start_date
          AND shift_date <= :end_date
          AND is_absent = 1
    """
    if effective_client_id:
        reason_sql += " AND client_id = :client_id"
    reason_sql += " GROUP BY COALESCE(absence_type, 'Unspecified')"

    reason_params = {
        "start_date": datetime.combine(start_date, datetime.min.time()),
        "end_date": datetime.combine(end_date, datetime.max.time())
    }
    if effective_client_id:
        reason_params["client_id"] = effective_client_id

    reason_results = db.execute(text(reason_sql), reason_params).fetchall()

    total_absences_for_pct = sum(r.count for r in reason_results) or 1
    by_reason = [
        {
            "reason": r.reason or "Unspecified",
            "count": r.count,
            "percentage": round((r.count / total_absences_for_pct) * 100, 1)
        }
        for r in reason_results
    ]

    # 2. Absenteeism by department (using client_id as proxy)
    dept_query = db.query(
        AttendanceEntry.client_id.label('department'),
        func.count(func.distinct(AttendanceEntry.employee_id)).label('workforce'),
        func.sum(case((AttendanceEntry.is_absent == 1, 1), else_=0)).label('absences'),
        func.sum(AttendanceEntry.scheduled_hours).label('scheduled_hrs'),
        func.sum(func.coalesce(AttendanceEntry.absence_hours, 0)).label('absent_hrs')
    ).filter(*date_filter)

    if effective_client_id:
        dept_query = dept_query.filter(AttendanceEntry.client_id == effective_client_id)

    dept_results = dept_query.group_by(AttendanceEntry.client_id).all()

    by_department = [
        {
            "department": d.department,
            "workforce": d.workforce,
            "absences": d.absences,
            "rate": round((float(d.absent_hrs or 0) / float(d.scheduled_hrs or 1)) * 100, 1)
        }
        for d in dept_results
    ]

    # 3. High absence employees (more than 2 absences in period)
    high_absence_query = db.query(
        AttendanceEntry.employee_id,
        AttendanceEntry.client_id.label('department'),
        func.count().label('absence_count'),
        func.max(AttendanceEntry.shift_date).label('last_absence')
    ).filter(
        *date_filter,
        AttendanceEntry.is_absent == 1
    )

    if effective_client_id:
        high_absence_query = high_absence_query.filter(AttendanceEntry.client_id == effective_client_id)

    high_absence_results = high_absence_query.group_by(
        AttendanceEntry.employee_id,
        AttendanceEntry.client_id
    ).having(func.count() >= 2).order_by(desc('absence_count')).limit(10).all()

    high_absence_employees = [
        {
            "employee_id": e.employee_id,
            "department": e.department,
            "absence_count": e.absence_count,
            "last_absence": e.last_absence.strftime('%Y-%m-%d') if e.last_absence else None
        }
        for e in high_absence_results
    ]

    return {
        "shift_id": shift_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_scheduled_hours": scheduled,
        "total_hours_worked": scheduled - absent,
        "total_hours_absent": absent,
        "rate": round(rate, 2),
        "absenteeism_rate": round(rate, 2),
        "total_employees": emp_count,
        "total_absences": absence_count,
        "calculation_timestamp": datetime.utcnow().isoformat(),
        "by_reason": by_reason,
        "by_department": by_department,
        "high_absence_employees": high_absence_employees
    }


@router.get("/kpi/absenteeism/trend")
def get_absenteeism_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get daily absenteeism trend data for charting

    Returns array of { date, value } where value is the absenteeism rate %
    """
    from datetime import timedelta
    from backend.schemas.attendance_entry import AttendanceEntry
    from sqlalchemy import func

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query daily absenteeism rates
    # Calculate absent hours: only count when is_absent=1
    # Note: `case` is imported at module level
    query = db.query(
        func.date(AttendanceEntry.shift_date).label('date'),
        func.sum(AttendanceEntry.scheduled_hours).label('scheduled'),
        func.sum(
            case(
                (AttendanceEntry.is_absent == 1, AttendanceEntry.scheduled_hours),
                else_=0
            )
        ).label('absent')
    ).filter(
        AttendanceEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        AttendanceEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(AttendanceEntry.client_id == effective_client_id)

    results = query.group_by(func.date(AttendanceEntry.shift_date)).order_by('date').all()

    trend_data = []
    for r in results:
        scheduled = float(r.scheduled or 0)
        absent = float(r.absent or 0)
        rate = (absent / scheduled * 100) if scheduled > 0 else 0
        trend_data.append({
            "date": r.date.isoformat() if hasattr(r.date, 'isoformat') else str(r.date),
            "value": round(rate, 2)
        })

    return trend_data


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
