"""
CRUD operations for attendance tracking
PHASE 3
SECURITY: Multi-tenant client filtering enabled
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from fastapi import HTTPException

from backend.schemas.attendance import AttendanceRecord
from backend.models.attendance import (
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceRecordResponse
)
from middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User
from backend.utils.soft_delete import soft_delete


def create_attendance_record(
    db: Session,
    attendance: AttendanceRecordCreate,
    current_user: User
) -> AttendanceRecordResponse:
    """
    Create new attendance record
    SECURITY: Verifies user has access to the specified client
    """
    # SECURITY: Verify user has access to this client
    if hasattr(attendance, 'client_id') and attendance.client_id:
        verify_client_access(current_user, attendance.client_id)

    db_attendance = AttendanceRecord(
        **attendance.dict(),
        entered_by=current_user.user_id
    )

    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)

    return AttendanceRecordResponse.from_orm(db_attendance)


def get_attendance_record(
    db: Session,
    attendance_id: int,
    current_user: User
) -> Optional[AttendanceRecord]:
    """
    Get attendance record by ID
    SECURITY: Verifies user has access to the record's client
    """
    db_attendance = db.query(AttendanceRecord).filter(
        AttendanceRecord.attendance_id == attendance_id
    ).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_attendance, 'client_id') and db_attendance.client_id:
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
    status: Optional[str] = None,
    client_id: Optional[str] = None
) -> List[AttendanceRecord]:
    """
    Get attendance records with filters
    SECURITY: Automatically filters by user's authorized clients
    """
    query = db.query(AttendanceRecord)

    # SECURITY: Apply client filtering based on user's role
    client_filter = build_client_filter_clause(current_user, AttendanceRecord.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply additional filters
    if client_id:
        query = query.filter(AttendanceRecord.client_id == client_id)

    if start_date:
        query = query.filter(AttendanceRecord.attendance_date >= start_date)

    if end_date:
        query = query.filter(AttendanceRecord.attendance_date <= end_date)

    if employee_id:
        query = query.filter(AttendanceRecord.employee_id == employee_id)

    if shift_id:
        query = query.filter(AttendanceRecord.shift_id == shift_id)

    if status:
        query = query.filter(AttendanceRecord.status == status)

    return query.order_by(
        AttendanceRecord.attendance_date.desc()
    ).offset(skip).limit(limit).all()


def update_attendance_record(
    db: Session,
    attendance_id: int,
    attendance_update: AttendanceRecordUpdate,
    current_user: User
) -> Optional[AttendanceRecordResponse]:
    """
    Update attendance record
    SECURITY: Verifies user has access to the record's client
    """
    db_attendance = db.query(AttendanceRecord).filter(
        AttendanceRecord.attendance_id == attendance_id
    ).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_attendance, 'client_id') and db_attendance.client_id:
        verify_client_access(current_user, db_attendance.client_id)

    update_data = attendance_update.dict(exclude_unset=True)

    for field, value in update_data.items():
        if hasattr(db_attendance, field):
            setattr(db_attendance, field, value)

    db.commit()
    db.refresh(db_attendance)

    return AttendanceRecordResponse.from_orm(db_attendance)


def delete_attendance_record(
    db: Session,
    attendance_id: int,
    current_user: User
) -> bool:
    """
    Soft delete attendance record (sets is_active = False)
    SECURITY: Verifies user has access to the record's client
    """
    db_attendance = db.query(AttendanceRecord).filter(
        AttendanceRecord.attendance_id == attendance_id
    ).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_attendance, 'client_id') and db_attendance.client_id:
        verify_client_access(current_user, db_attendance.client_id)

    # Soft delete - preserves data integrity
    return soft_delete(db, db_attendance)
