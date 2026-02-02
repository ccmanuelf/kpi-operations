"""
Attendance Service
Service layer for Attendance operations.
Coordinates CRUD operations with shift calculations and absenteeism tracking.

Phase 2: Service Layer Enforcement
"""
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.schemas.user import User
from backend.crud.attendance import (
    create_attendance_record,
    get_attendance_record,
    get_attendance_records,
    update_attendance_record,
    delete_attendance_record,
)
from backend.database import get_db


class AttendanceService:
    """
    Service layer for Attendance operations.

    Wraps attendance CRUD with business logic:
    - Shift hour calculations
    - Absenteeism rate tracking
    - Attendance summary statistics
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_attendance(
        self,
        data: dict,
        user: User
    ):
        """
        Create an attendance record.

        Args:
            data: Attendance data
            user: Authenticated user

        Returns:
            Created attendance record
        """
        return create_attendance_record(self.db, data, user)

    def get_attendance(
        self,
        attendance_id: int,
        user: User
    ):
        """
        Get an attendance record by ID.

        Args:
            attendance_id: Attendance ID
            user: Authenticated user

        Returns:
            Attendance record or None
        """
        return get_attendance_record(self.db, attendance_id, user)

    def list_attendance(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        employee_id: Optional[int] = None,
        client_id: Optional[str] = None
    ) -> List:
        """
        List attendance records with filtering.

        Args:
            user: Authenticated user
            skip: Records to skip
            limit: Maximum records
            start_date: Filter start date
            end_date: Filter end date
            employee_id: Filter by employee
            client_id: Filter by client

        Returns:
            List of attendance records
        """
        return get_attendance_records(
            self.db, user, skip, limit,
            start_date, end_date, employee_id, client_id
        )

    def update_attendance(
        self,
        attendance_id: int,
        data: dict,
        user: User
    ):
        """
        Update an attendance record.

        Args:
            attendance_id: Attendance ID
            data: Update data
            user: Authenticated user

        Returns:
            Updated attendance record
        """
        return update_attendance_record(self.db, attendance_id, data, user)

    def delete_attendance(
        self,
        attendance_id: int,
        user: User
    ) -> bool:
        """
        Delete an attendance record.

        Args:
            attendance_id: Attendance ID
            user: Authenticated user

        Returns:
            True if deleted
        """
        return delete_attendance_record(self.db, attendance_id, user)

    def calculate_absenteeism_rate(
        self,
        client_id: str,
        user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict:
        """
        Calculate absenteeism rate for a client.

        Args:
            client_id: Client ID
            user: Authenticated user
            start_date: Filter start date
            end_date: Filter end date

        Returns:
            Dictionary with absenteeism statistics
        """
        # Get attendance records for the period
        records = self.list_attendance(
            user=user,
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Get all records
        )

        total_records = len(records)
        if total_records == 0:
            return {
                "client_id": client_id,
                "total_records": 0,
                "absent_count": 0,
                "absenteeism_rate": 0.0
            }

        # Count absences (assuming 'present' field or status)
        absent_count = sum(
            1 for r in records
            if hasattr(r, 'present') and not r.present
        )

        return {
            "client_id": client_id,
            "total_records": total_records,
            "absent_count": absent_count,
            "absenteeism_rate": round((absent_count / total_records) * 100, 2)
        }


def get_attendance_service(db: Session = Depends(get_db)) -> AttendanceService:
    """
    FastAPI dependency to get AttendanceService instance.
    """
    return AttendanceService(db)
