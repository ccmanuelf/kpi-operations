"""
CRUD operations for attendance tracking
PHASE 3
SECURITY: Multi-tenant client filtering enabled
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException

from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.shift import Shift
from backend.orm.employee import Employee
from backend.schemas.attendance import AttendanceRecordCreate, AttendanceRecordUpdate, AttendanceRecordResponse
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.orm.user import User
from backend.utils.soft_delete import soft_delete
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


def create_attendance_record(
    db: Session, attendance: AttendanceRecordCreate, current_user: User
) -> AttendanceRecordResponse:
    """
    Create new attendance record
    SECURITY: Verifies user has access to the specified client
    """
    # SECURITY: Verify user has access to this client
    if hasattr(attendance, "client_id") and attendance.client_id:
        verify_client_access(current_user, attendance.client_id)

    db_attendance = AttendanceEntry(**attendance.model_dump(), entered_by=current_user.user_id)

    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)

    return AttendanceRecordResponse.from_orm(db_attendance)


def get_attendance_record(db: Session, attendance_id: str, current_user: User) -> Optional[AttendanceEntry]:
    """
    Get attendance record by ID
    SECURITY: Verifies user has access to the record's client
    """
    db_attendance = db.query(AttendanceEntry).filter(AttendanceEntry.attendance_entry_id == attendance_id).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_attendance, "client_id") and db_attendance.client_id:
        verify_client_access(current_user, db_attendance.client_id)

    return db_attendance


def get_attendance_records(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    employee_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    is_absent: Optional[int] = None,
    client_id: Optional[str] = None,
) -> List[AttendanceEntry]:
    """
    Get attendance records with filters
    SECURITY: Automatically filters by user's authorized clients
    """
    query = db.query(AttendanceEntry)

    # SECURITY: Apply client filtering based on user's role
    client_filter = build_client_filter_clause(current_user, AttendanceEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply additional filters
    if client_id:
        query = query.filter(AttendanceEntry.client_id == client_id)

    if start_date:
        query = query.filter(AttendanceEntry.shift_date >= start_date)

    if end_date:
        query = query.filter(AttendanceEntry.shift_date <= end_date)

    if employee_id:
        query = query.filter(AttendanceEntry.employee_id == employee_id)

    if shift_id:
        query = query.filter(AttendanceEntry.shift_id == shift_id)

    if is_absent is not None:
        query = query.filter(AttendanceEntry.is_absent == is_absent)

    return query.order_by(AttendanceEntry.shift_date.desc()).offset(skip).limit(limit).all()


def update_attendance_record(
    db: Session, attendance_id: str, attendance_update: AttendanceRecordUpdate, current_user: User
) -> Optional[AttendanceRecordResponse]:
    """
    Update attendance record
    SECURITY: Verifies user has access to the record's client
    """
    db_attendance = db.query(AttendanceEntry).filter(AttendanceEntry.attendance_entry_id == attendance_id).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_attendance, "client_id") and db_attendance.client_id:
        verify_client_access(current_user, db_attendance.client_id)

    update_data = attendance_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if hasattr(db_attendance, field):
            setattr(db_attendance, field, value)

    db.commit()
    db.refresh(db_attendance)

    return AttendanceRecordResponse.from_orm(db_attendance)


def delete_attendance_record(db: Session, attendance_id: str, current_user: User) -> bool:
    """
    Soft delete attendance record (sets is_active = False)
    SECURITY: Verifies user has access to the record's client
    """
    db_attendance = db.query(AttendanceEntry).filter(AttendanceEntry.attendance_entry_id == attendance_id).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_attendance, "client_id") and db_attendance.client_id:
        verify_client_access(current_user, db_attendance.client_id)

    # Soft delete - preserves data integrity
    return soft_delete(db, db_attendance)


# ============================================================================
# BULK OPERATIONS
# ============================================================================


def bulk_create_attendance_records(
    db: Session, records: List[AttendanceRecordCreate], current_user: User
) -> dict:
    """
    Create multiple attendance records in one transaction.

    SECURITY: Validates client access for each record.

    Args:
        db: Database session
        records: List of AttendanceRecordCreate Pydantic models
        current_user: Authenticated user

    Returns:
        Summary dict with total, successful, failed counts, errors, and created IDs
    """
    total = len(records)
    successful = 0
    failed = 0
    errors = []
    created_ids = []

    for idx, record in enumerate(records):
        try:
            # Validate client access
            if record.client_id:
                verify_client_access(current_user, record.client_id)

            entry_id = uuid4().hex
            db_entry = AttendanceEntry(
                attendance_entry_id=entry_id,
                **record.model_dump(),
                entered_by=current_user.user_id,
            )
            db.add(db_entry)
            created_ids.append(entry_id)
            successful += 1
        except HTTPException as e:
            failed += 1
            errors.append({"index": idx, "error": e.detail})
        except Exception as e:
            failed += 1
            errors.append({"index": idx, "error": str(e)})

    if successful > 0:
        db.commit()
        logger.info(
            "Bulk attendance create: %d/%d succeeded, user=%s",
            successful,
            total,
            current_user.username,
        )
    else:
        db.rollback()

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "errors": errors,
        "created_ids": created_ids,
    }


def mark_all_present(
    db: Session, client_id: str, shift_id: int, shift_date: date, current_user: User
) -> dict:
    """
    Create attendance records for all active employees assigned to a client,
    marking them as present for a given shift and date.

    SECURITY: Verifies user has access to the specified client.

    Args:
        db: Database session
        client_id: Client to mark attendance for
        shift_id: Shift to record attendance against
        shift_date: Date of the shift
        current_user: Authenticated user

    Returns:
        Summary dict with total_employees, records_created, already_exists, created_ids
    """
    # Verify client access
    verify_client_access(current_user, client_id)

    # Get the shift to determine scheduled hours
    shift = db.query(Shift).filter(
        Shift.shift_id == shift_id,
        Shift.client_id == client_id,
    ).first()

    if not shift:
        raise HTTPException(status_code=404, detail=f"Shift {shift_id} not found for client {client_id}")

    # Calculate shift hours from start_time / end_time (handle overnight)
    start_dt = datetime.combine(shift_date, shift.start_time)
    end_dt = datetime.combine(shift_date, shift.end_time)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)  # overnight shift
    shift_hours = Decimal(str(round((end_dt - start_dt).total_seconds() / 3600, 2)))

    # Get all active employees assigned to this client
    # Employee.client_id_assigned is a comma-separated string of client IDs
    employees = db.query(Employee).filter(
        Employee.is_active == 1,
        or_(
            Employee.client_id_assigned == client_id,
            Employee.client_id_assigned.like(f"{client_id},%"),
            Employee.client_id_assigned.like(f"%,{client_id},%"),
            Employee.client_id_assigned.like(f"%,{client_id}"),
        ),
    ).all()

    total_employees = len(employees)

    # Convert shift_date to datetime for comparison with the DateTime column
    shift_datetime = datetime.combine(shift_date, datetime.min.time())

    # Find employees who already have attendance for this shift_date + shift_id
    existing_employee_ids = set()
    if employees:
        existing = db.query(AttendanceEntry.employee_id).filter(
            AttendanceEntry.client_id == client_id,
            AttendanceEntry.shift_id == shift_id,
            AttendanceEntry.shift_date == shift_datetime,
            AttendanceEntry.employee_id.in_([e.employee_id for e in employees]),
        ).all()
        existing_employee_ids = {row.employee_id for row in existing}

    already_exists = len(existing_employee_ids)
    created_ids = []

    for emp in employees:
        if emp.employee_id in existing_employee_ids:
            continue

        entry_id = uuid4().hex
        db_entry = AttendanceEntry(
            attendance_entry_id=entry_id,
            client_id=client_id,
            employee_id=emp.employee_id,
            shift_date=shift_datetime,
            shift_id=shift_id,
            scheduled_hours=shift_hours,
            actual_hours=shift_hours,
            absence_hours=Decimal("0"),
            is_absent=0,
            entered_by=current_user.user_id,
        )
        db.add(db_entry)
        created_ids.append(entry_id)

    records_created = len(created_ids)

    if records_created > 0:
        db.commit()
        logger.info(
            "Mark all present: %d records created for client=%s shift=%d date=%s, user=%s",
            records_created,
            client_id,
            shift_id,
            shift_date.isoformat(),
            current_user.username,
        )

    return {
        "total_employees": total_employees,
        "records_created": records_created,
        "already_exists": already_exists,
        "created_ids": created_ids,
    }
