"""
CRUD operations for attendance tracking
PHASE 3
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
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User


def create_attendance_record(
    db: Session,
    attendance: AttendanceRecordCreate,
    current_user: User
) -> AttendanceRecordResponse:
    """Create new attendance record"""
    # Verify user has access to this client
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
    """Get attendance record by ID"""
    db_attendance = db.query(AttendanceRecord).filter(
        AttendanceRecord.attendance_id == attendance_id
    ).first()

    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # Verify user has access to this client
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
    status: Optional[str] = None
) -> List[AttendanceRecord]:
    """Get attendance records with filters"""
    query = db.query(AttendanceRecord)

    # Apply client filtering based on user role
    client_filter = build_client_filter_clause(current_user, AttendanceRecord.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

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
    """Update attendance record"""
    db_attendance = get_attendance_record(db, attendance_id, current_user)

    if not db_attendance:
        return None

    update_data = attendance_update.dict(exclude_unset=True)

    # Verify client_id if being updated
    if 'client_id' in update_data:
        verify_client_access(current_user, update_data['client_id'])

    for field, value in update_data.items():
        setattr(db_attendance, field, value)

    db.commit()
    db.refresh(db_attendance)

    return AttendanceRecordResponse.from_orm(db_attendance)


def delete_attendance_record(
    db: Session,
    attendance_id: int,
    current_user: User
) -> bool:
    """Delete attendance record"""
    db_attendance = get_attendance_record(db, attendance_id, current_user)

    if not db_attendance:
        return False

    db.delete(db_attendance)
    db.commit()

    return True
