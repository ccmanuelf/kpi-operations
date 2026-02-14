"""
Real-database tests for Attendance CRUD operations.
Uses transactional_db fixture (in-memory SQLite with automatic rollback).
No mocks for database operations.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import func

from backend.schemas import (
    Client,
    ClientType,
    User,
    UserRole,
    Employee,
    Shift,
    AttendanceEntry,
    AbsenceType,
)
from backend.tests.fixtures.factories import TestDataFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_attendance_prereqs(db, client_id="ATT-TEST-C1"):
    """Create client, employee, shift needed for attendance entries."""
    client = TestDataFactory.create_client(db, client_id=client_id, client_name="Attendance Test Client")
    user = TestDataFactory.create_user(db, username=f"att_admin_{client_id}", role="admin", client_id=client_id)
    employee = TestDataFactory.create_employee(db, client_id=client_id, employee_name=f"Worker {client_id}")
    shift = TestDataFactory.create_shift(db, client_id=client_id, shift_name=f"Day Shift {client_id}")
    db.flush()
    return client, user, employee, shift


class TestAttendanceCRUD:
    """Test Attendance CRUD operations using real database."""

    def test_create_attendance_entry(self, transactional_db):
        """Test creating attendance record persists to DB."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
        )
        db.flush()

        from_db = (
            db.query(AttendanceEntry)
            .filter_by(
                attendance_entry_id=entry.attendance_entry_id,
            )
            .first()
        )
        assert from_db is not None
        assert from_db.client_id == client.client_id
        assert from_db.employee_id == employee.employee_id
        assert float(from_db.scheduled_hours) == 8.0

    def test_get_attendance_by_employee(self, transactional_db):
        """Test getting attendance records by employee ID."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        for i in range(5):
            TestDataFactory.create_attendance_entry(
                db,
                employee_id=employee.employee_id,
                client_id=client.client_id,
                shift_id=shift.shift_id,
                shift_date=date.today() - timedelta(days=i),
            )
        db.flush()

        results = (
            db.query(AttendanceEntry)
            .filter(
                AttendanceEntry.employee_id == employee.employee_id,
            )
            .all()
        )
        assert len(results) == 5

    def test_get_attendance_by_date_range(self, transactional_db):
        """Test getting attendance records filtered by date range."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        base = date.today() - timedelta(days=10)
        for i in range(10):
            TestDataFactory.create_attendance_entry(
                db,
                employee_id=employee.employee_id,
                client_id=client.client_id,
                shift_id=shift.shift_id,
                shift_date=base + timedelta(days=i),
            )
        db.flush()

        start_dt = datetime.combine(base + timedelta(days=3), datetime.min.time())
        end_dt = datetime.combine(base + timedelta(days=7), datetime.min.time())

        results = (
            db.query(AttendanceEntry)
            .filter(
                AttendanceEntry.client_id == client.client_id,
                AttendanceEntry.shift_date >= start_dt,
                AttendanceEntry.shift_date <= end_dt,
            )
            .all()
        )

        assert len(results) == 5

    def test_update_attendance_absence_fields(self, transactional_db):
        """Test updating attendance to mark as absent persists."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            is_absent=0,
            actual_hours=Decimal("8.0"),
        )
        db.flush()

        # Mark as absent
        entry.is_absent = 1
        entry.actual_hours = Decimal("0")
        entry.absence_hours = Decimal("8.0")
        entry.absence_type = AbsenceType.UNSCHEDULED_ABSENCE
        db.flush()

        from_db = (
            db.query(AttendanceEntry)
            .filter_by(
                attendance_entry_id=entry.attendance_entry_id,
            )
            .first()
        )
        assert from_db.is_absent == 1
        assert float(from_db.actual_hours) == 0.0
        assert from_db.absence_type == AbsenceType.UNSCHEDULED_ABSENCE

    def test_delete_attendance_record(self, transactional_db):
        """Test deleting attendance record removes it from DB."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
        )
        db.flush()

        entry_id = entry.attendance_entry_id
        db.delete(entry)
        db.flush()

        from_db = (
            db.query(AttendanceEntry)
            .filter_by(
                attendance_entry_id=entry_id,
            )
            .first()
        )
        assert from_db is None

    def test_calculate_hours_worked(self, transactional_db):
        """Test hours calculation from stored actual_hours."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            actual_hours=Decimal("8.5"),
            scheduled_hours=Decimal("8.0"),
        )
        db.flush()

        from_db = (
            db.query(AttendanceEntry)
            .filter_by(
                attendance_entry_id=entry.attendance_entry_id,
            )
            .first()
        )

        overtime = float(from_db.actual_hours) - float(from_db.scheduled_hours)
        assert overtime == 0.5

    def test_attendance_absence_type_values(self, transactional_db):
        """Test all valid absence type enum values persist correctly."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        valid_types = [
            AbsenceType.UNSCHEDULED_ABSENCE,
            AbsenceType.VACATION,
            AbsenceType.MEDICAL_LEAVE,
            AbsenceType.PERSONAL_LEAVE,
        ]

        for at in valid_types:
            entry = TestDataFactory.create_attendance_entry(
                db,
                employee_id=employee.employee_id,
                client_id=client.client_id,
                shift_id=shift.shift_id,
                is_absent=1,
                absence_type=at,
                actual_hours=Decimal("0"),
                absence_hours=Decimal("8.0"),
            )
            db.flush()

            from_db = (
                db.query(AttendanceEntry)
                .filter_by(
                    attendance_entry_id=entry.attendance_entry_id,
                )
                .first()
            )
            assert from_db.absence_type == at

    def test_overtime_calculation(self, transactional_db):
        """Test overtime calculation from stored hours."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("10.0"),
        )
        db.flush()

        from_db = (
            db.query(AttendanceEntry)
            .filter_by(
                attendance_entry_id=entry.attendance_entry_id,
            )
            .first()
        )

        overtime = max(0, float(from_db.actual_hours) - float(from_db.scheduled_hours))
        assert overtime == 2.0

    def test_attendance_summary_by_shift(self, transactional_db):
        """Test attendance summary aggregation per shift."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        # Create additional employees
        employees = [employee]
        for _ in range(4):
            emp = TestDataFactory.create_employee(db, client_id=client.client_id)
            employees.append(emp)
        db.flush()

        today = date.today()
        # 4 present, 1 absent
        for i, emp in enumerate(employees):
            TestDataFactory.create_attendance_entry(
                db,
                employee_id=emp.employee_id,
                client_id=client.client_id,
                shift_id=shift.shift_id,
                shift_date=today,
                is_absent=1 if i == 4 else 0,
                actual_hours=Decimal("0") if i == 4 else Decimal("8.0"),
            )
        db.flush()

        total = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == client.client_id,
                AttendanceEntry.shift_id == shift.shift_id,
            )
            .scalar()
        )

        present = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == client.client_id,
                AttendanceEntry.shift_id == shift.shift_id,
                AttendanceEntry.is_absent == 0,
            )
            .scalar()
        )

        absent = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == client.client_id,
                AttendanceEntry.shift_id == shift.shift_id,
                AttendanceEntry.is_absent == 1,
            )
            .scalar()
        )

        assert total == 5
        assert present == 4
        assert absent == 1

    def test_absenteeism_rate_calculation(self, transactional_db):
        """Test absenteeism rate computation from real attendance data."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        # Create 20 employees
        employees = [employee]
        for _ in range(19):
            emp = TestDataFactory.create_employee(db, client_id=client.client_id)
            employees.append(emp)
        db.flush()

        today = date.today()
        # 19 present, 1 absent
        for i, emp in enumerate(employees):
            TestDataFactory.create_attendance_entry(
                db,
                employee_id=emp.employee_id,
                client_id=client.client_id,
                shift_id=shift.shift_id,
                shift_date=today,
                is_absent=1 if i == 0 else 0,
            )
        db.flush()

        total_employees = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == client.client_id,
            )
            .scalar()
        )

        absent_count = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == client.client_id,
                AttendanceEntry.is_absent == 1,
            )
            .scalar()
        )

        absenteeism_rate = (absent_count / total_employees) * 100
        assert absenteeism_rate == 5.0

    def test_duplicate_attendance_prevention(self, transactional_db):
        """Test checking for existing attendance entry before insert."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        today = date.today()
        TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=today,
        )
        db.flush()

        # Check if entry already exists
        existing = (
            db.query(AttendanceEntry)
            .filter(
                AttendanceEntry.employee_id == employee.employee_id,
                AttendanceEntry.client_id == client.client_id,
                AttendanceEntry.shift_date == datetime.combine(today, datetime.min.time()),
            )
            .first()
        )
        assert existing is not None  # Entry exists, should not create duplicate


class TestAttendanceEdgeCases:
    """Edge case tests for attendance using real database."""

    def test_midnight_shift_crossing(self, transactional_db):
        """Test storing attendance with arrival/departure crossing midnight."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        base_date = date(2026, 1, 15)
        check_in = datetime(2026, 1, 15, 22, 0, 0)
        check_out = datetime(2026, 1, 16, 6, 0, 0)

        entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=base_date,
            arrival_time=check_in,
            departure_time=check_out,
            actual_hours=Decimal("8.0"),
        )
        db.flush()

        from_db = (
            db.query(AttendanceEntry)
            .filter_by(
                attendance_entry_id=entry.attendance_entry_id,
            )
            .first()
        )

        hours = (from_db.departure_time - from_db.arrival_time).total_seconds() / 3600
        assert hours == 8.0

    def test_partial_day_attendance(self, transactional_db):
        """Test partial day attendance with less than scheduled hours."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("4.0"),
            absence_hours=Decimal("4.0"),
        )
        db.flush()

        from_db = (
            db.query(AttendanceEntry)
            .filter_by(
                attendance_entry_id=entry.attendance_entry_id,
            )
            .first()
        )

        is_partial = float(from_db.actual_hours) < float(from_db.scheduled_hours)
        assert is_partial is True

    def test_future_attendance_date_stored(self, transactional_db):
        """Test that future dates can be stored (validation is at app layer)."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        future_date = date.today() + timedelta(days=7)
        entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=future_date,
        )
        db.flush()

        from_db = (
            db.query(AttendanceEntry)
            .filter_by(
                attendance_entry_id=entry.attendance_entry_id,
            )
            .first()
        )

        is_future = from_db.shift_date.date() > date.today()
        assert is_future is True

    def test_bulk_attendance_creation(self, transactional_db):
        """Test bulk attendance entry creation for multiple employees."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        employees = [employee]
        for _ in range(49):
            emp = TestDataFactory.create_employee(db, client_id=client.client_id)
            employees.append(emp)
        db.flush()

        today = date.today()
        for emp in employees:
            TestDataFactory.create_attendance_entry(
                db,
                employee_id=emp.employee_id,
                client_id=client.client_id,
                shift_id=shift.shift_id,
                shift_date=today,
            )
        db.flush()

        count = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == client.client_id,
            )
            .scalar()
        )
        assert count == 50

    def test_attendance_with_break_time_deduction(self, transactional_db):
        """Test that actual hours correctly reflect break deductions."""
        db = transactional_db
        client, user, employee, shift = _seed_attendance_prereqs(db)

        total_time = Decimal("9.0")
        break_time = Decimal("1.0")
        net_hours = total_time - break_time

        entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            actual_hours=net_hours,
            scheduled_hours=Decimal("8.0"),
        )
        db.flush()

        from_db = (
            db.query(AttendanceEntry)
            .filter_by(
                attendance_entry_id=entry.attendance_entry_id,
            )
            .first()
        )
        assert float(from_db.actual_hours) == 8.0

    def test_multi_tenant_attendance_isolation(self, transactional_db):
        """Test attendance entries are isolated per client_id."""
        db = transactional_db
        client_a, user_a, emp_a, shift_a = _seed_attendance_prereqs(db, client_id="CLIENT-A")
        client_b, user_b, emp_b, shift_b = _seed_attendance_prereqs(db, client_id="CLIENT-B")

        for i in range(4):
            TestDataFactory.create_attendance_entry(
                db,
                employee_id=emp_a.employee_id,
                client_id=client_a.client_id,
                shift_id=shift_a.shift_id,
                shift_date=date.today() - timedelta(days=i),
            )
        for i in range(2):
            TestDataFactory.create_attendance_entry(
                db,
                employee_id=emp_b.employee_id,
                client_id=client_b.client_id,
                shift_id=shift_b.shift_id,
                shift_date=date.today() - timedelta(days=i),
            )
        db.flush()

        a_count = db.query(AttendanceEntry).filter(AttendanceEntry.client_id == "CLIENT-A").count()
        b_count = db.query(AttendanceEntry).filter(AttendanceEntry.client_id == "CLIENT-B").count()

        assert a_count == 4
        assert b_count == 2
