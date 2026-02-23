"""
Attendance Service
Thin service layer wrapping Attendance CRUD operations.
Routes should import from this module instead of backend.crud.attendance directly.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.attendance import (
    create_attendance_record,
    get_attendance_record,
    get_attendance_records,
    update_attendance_record,
    delete_attendance_record,
    bulk_create_attendance_records,
    mark_all_present,
)


def create_record(db: Session, data: dict, current_user: User):
    """Create a new attendance record."""
    return create_attendance_record(db, data, current_user)


def get_record(db: Session, attendance_id: str, current_user: User):
    """Get an attendance record by ID."""
    return get_attendance_record(db, attendance_id, current_user)


def list_records(
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
):
    """List attendance records with filters."""
    return get_attendance_records(
        db, current_user,
        skip=skip, limit=limit,
        start_date=start_date, end_date=end_date,
        employee_id=employee_id, shift_id=shift_id,
        is_absent=is_absent, client_id=client_id,
    )


def update_record(db: Session, attendance_id: str, data: dict, current_user: User):
    """Update an attendance record."""
    return update_attendance_record(db, attendance_id, data, current_user)


def delete_record(db: Session, attendance_id: str, current_user: User) -> bool:
    """Delete an attendance record."""
    return delete_attendance_record(db, attendance_id, current_user)


def bulk_create_records(db: Session, records: list, current_user: User):
    """Bulk create attendance records."""
    return bulk_create_attendance_records(db, records, current_user)


def mark_all_employees_present(db: Session, client_id: str, shift_id: int, shift_date, current_user: User):
    """Mark all employees as present for a shift."""
    return mark_all_present(db, client_id, shift_id, shift_date, current_user)
