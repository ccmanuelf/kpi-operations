"""
Real-database tests for bulk attendance CRUD operations.
Uses transactional_db fixture (in-memory SQLite with automatic rollback).
No mocks for database operations.
"""

import pytest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from sqlalchemy import func

from backend.orm import (
    AttendanceEntry,
    User,
    UserRole,
)
from backend.tests.fixtures.factories import TestDataFactory
from backend.crud.attendance import bulk_create_attendance_records, mark_all_present
from backend.schemas.attendance import AttendanceRecordCreate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_prereqs(db, client_id="BULK-ATT-C1", num_employees=5, overnight_shift=False):
    """Create client, admin user, employees, and shift for bulk attendance tests."""
    client = TestDataFactory.create_client(db, client_id=client_id, client_name=f"Bulk Test {client_id}")
    user = TestDataFactory.create_user(db, username=f"bulk_admin_{client_id}", role="admin", client_id=client_id)

    employees = []
    for i in range(num_employees):
        emp = TestDataFactory.create_employee(db, client_id=client_id, employee_name=f"Worker {client_id}-{i}")
        employees.append(emp)

    if overnight_shift:
        shift = TestDataFactory.create_shift(
            db,
            client_id=client_id,
            shift_name=f"Night Shift {client_id}",
            start_time="22:00:00",
            end_time="06:00:00",
        )
    else:
        shift = TestDataFactory.create_shift(
            db,
            client_id=client_id,
            shift_name=f"Day Shift {client_id}",
            start_time="06:00:00",
            end_time="14:00:00",
        )

    db.flush()
    return client, user, employees, shift


class TestBulkCreateAttendanceRecords:
    """Tests for bulk_create_attendance_records CRUD function."""

    def test_bulk_create_valid_records(self, transactional_db):
        """Test bulk creation with all valid records succeeds."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db, num_employees=3)

        records = [
            AttendanceRecordCreate(
                client_id=client.client_id,
                employee_id=emp.employee_id,
                shift_date=date.today(),
                shift_id=shift.shift_id,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                is_absent=0,
            )
            for emp in employees
        ]

        result = bulk_create_attendance_records(db, records, user)

        assert result["total"] == 3
        assert result["successful"] == 3
        assert result["failed"] == 0
        assert len(result["errors"]) == 0
        assert len(result["created_ids"]) == 3

        # Verify records exist in DB
        count = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == client.client_id,
            )
            .scalar()
        )
        assert count == 3

    def test_bulk_create_mixed_valid_invalid(self, transactional_db):
        """Test bulk creation with mixed valid/invalid records."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db, num_employees=2)

        # Create operator user for CLIENT-B (no access to BULK-ATT-C1)
        other_client = TestDataFactory.create_client(db, client_id="BULK-OTHER-C", client_name="Other")
        operator = TestDataFactory.create_user(db, username="bulk_operator", role="operator", client_id="BULK-OTHER-C")
        db.flush()

        records = [
            # Valid record for the operator's client
            AttendanceRecordCreate(
                client_id="BULK-OTHER-C",
                employee_id=employees[0].employee_id,
                shift_date=date.today(),
                shift_id=shift.shift_id,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                is_absent=0,
            ),
            # Invalid: operator can't access BULK-ATT-C1
            AttendanceRecordCreate(
                client_id=client.client_id,
                employee_id=employees[1].employee_id,
                shift_date=date.today(),
                shift_id=shift.shift_id,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                is_absent=0,
            ),
        ]

        result = bulk_create_attendance_records(db, records, operator)

        assert result["total"] == 2
        assert result["successful"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["index"] == 1

    def test_bulk_create_empty_list(self, transactional_db):
        """Test bulk creation with empty list returns zero counts."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db)

        result = bulk_create_attendance_records(db, [], user)

        assert result["total"] == 0
        assert result["successful"] == 0
        assert result["failed"] == 0

    def test_bulk_create_generates_unique_ids(self, transactional_db):
        """Test that each bulk-created record gets a unique ID."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db, num_employees=5)

        records = [
            AttendanceRecordCreate(
                client_id=client.client_id,
                employee_id=emp.employee_id,
                shift_date=date.today(),
                shift_id=shift.shift_id,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                is_absent=0,
            )
            for emp in employees
        ]

        result = bulk_create_attendance_records(db, records, user)

        # All IDs should be unique
        assert len(set(result["created_ids"])) == 5

    def test_bulk_create_admin_access_any_client(self, transactional_db):
        """Test that admin user can bulk create for any client."""
        db = transactional_db
        client_a, user_a, emps_a, shift_a = _seed_prereqs(db, client_id="BULK-A")
        client_b, user_b, emps_b, shift_b = _seed_prereqs(db, client_id="BULK-B")

        # Create an admin user (no client assignment = access all)
        admin = TestDataFactory.create_user(db, username="bulk_super_admin", role="admin")
        db.flush()

        records = [
            AttendanceRecordCreate(
                client_id="BULK-A",
                employee_id=emps_a[0].employee_id,
                shift_date=date.today(),
                shift_id=shift_a.shift_id,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                is_absent=0,
            ),
            AttendanceRecordCreate(
                client_id="BULK-B",
                employee_id=emps_b[0].employee_id,
                shift_date=date.today(),
                shift_id=shift_b.shift_id,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                is_absent=0,
            ),
        ]

        result = bulk_create_attendance_records(db, records, admin)
        assert result["successful"] == 2
        assert result["failed"] == 0


class TestMarkAllPresent:
    """Tests for mark_all_present CRUD function."""

    def test_mark_all_present_creates_for_all_employees(self, transactional_db):
        """Test mark_all_present creates records for all active employees."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db, num_employees=5)

        result = mark_all_present(db, client.client_id, shift.shift_id, date.today(), user)

        assert result["total_employees"] == 5
        assert result["records_created"] == 5
        assert result["already_exists"] == 0
        assert len(result["created_ids"]) == 5

        # Verify records in DB
        count = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == client.client_id,
                AttendanceEntry.shift_id == shift.shift_id,
            )
            .scalar()
        )
        assert count == 5

    def test_mark_all_present_skips_existing(self, transactional_db):
        """Test mark_all_present skips employees who already have attendance."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db, num_employees=5)

        # Pre-create attendance for first 2 employees
        for emp in employees[:2]:
            TestDataFactory.create_attendance_entry(
                db,
                employee_id=emp.employee_id,
                client_id=client.client_id,
                shift_id=shift.shift_id,
                shift_date=date.today(),
            )
        db.flush()

        result = mark_all_present(db, client.client_id, shift.shift_id, date.today(), user)

        assert result["total_employees"] == 5
        assert result["records_created"] == 3
        assert result["already_exists"] == 2

    def test_mark_all_present_calculates_shift_hours(self, transactional_db):
        """Test shift hours are correctly calculated from start/end time."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db, num_employees=1)

        # Day shift: 06:00 to 14:00 = 8 hours
        result = mark_all_present(db, client.client_id, shift.shift_id, date.today(), user)

        entry = (
            db.query(AttendanceEntry).filter(AttendanceEntry.attendance_entry_id == result["created_ids"][0]).first()
        )

        assert float(entry.scheduled_hours) == 8.0
        assert float(entry.actual_hours) == 8.0
        assert float(entry.absence_hours) == 0.0
        assert entry.is_absent == 0

    def test_mark_all_present_overnight_shift_hours(self, transactional_db):
        """Test shift hours calculation for overnight shifts (end < start)."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(
            db, client_id="BULK-NIGHT", num_employees=1, overnight_shift=True
        )

        # Night shift: 22:00 to 06:00 = 8 hours
        result = mark_all_present(db, client.client_id, shift.shift_id, date.today(), user)

        entry = (
            db.query(AttendanceEntry).filter(AttendanceEntry.attendance_entry_id == result["created_ids"][0]).first()
        )

        assert float(entry.scheduled_hours) == 8.0

    def test_mark_all_present_invalid_shift(self, transactional_db):
        """Test mark_all_present raises 404 for invalid shift_id."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db)

        with pytest.raises(Exception) as exc_info:
            mark_all_present(db, client.client_id, 99999, date.today(), user)

        assert exc_info.value.status_code == 404

    def test_mark_all_present_excludes_inactive_employees(self, transactional_db):
        """Test mark_all_present excludes inactive employees."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db, num_employees=3)

        # Deactivate one employee
        employees[0].is_active = 0
        db.flush()

        result = mark_all_present(db, client.client_id, shift.shift_id, date.today(), user)

        assert result["total_employees"] == 2
        assert result["records_created"] == 2

    def test_mark_all_present_multi_tenant_isolation(self, transactional_db):
        """Test mark_all_present only creates for the specified client's employees."""
        db = transactional_db
        client_a, user_a, emps_a, shift_a = _seed_prereqs(db, client_id="ISO-A", num_employees=3)
        client_b, user_b, emps_b, shift_b = _seed_prereqs(db, client_id="ISO-B", num_employees=4)

        result = mark_all_present(db, "ISO-A", shift_a.shift_id, date.today(), user_a)

        assert result["total_employees"] == 3
        assert result["records_created"] == 3

        # Verify no records created for ISO-B
        b_count = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == "ISO-B",
            )
            .scalar()
        )
        assert b_count == 0

    def test_mark_all_present_operator_cannot_access_other_client(self, transactional_db):
        """Test operator user cannot mark present for another client."""
        db = transactional_db
        client_a, user_a, emps_a, shift_a = _seed_prereqs(db, client_id="OP-A", num_employees=2)
        client_b, user_b, emps_b, shift_b = _seed_prereqs(db, client_id="OP-B", num_employees=2)

        # Create operator restricted to OP-A
        operator = TestDataFactory.create_user(db, username="restricted_op", role="operator", client_id="OP-A")
        db.flush()

        # Should succeed for own client
        result_ok = mark_all_present(db, "OP-A", shift_a.shift_id, date.today(), operator)
        assert result_ok["records_created"] == 2

        # Should fail for other client
        with pytest.raises(Exception) as exc_info:
            mark_all_present(db, "OP-B", shift_b.shift_id, date.today(), operator)
        assert exc_info.value.status_code == 403

    def test_mark_all_present_idempotent(self, transactional_db):
        """Test calling mark_all_present twice does not create duplicate records."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db, num_employees=3)

        first = mark_all_present(db, client.client_id, shift.shift_id, date.today(), user)
        assert first["records_created"] == 3

        second = mark_all_present(db, client.client_id, shift.shift_id, date.today(), user)
        assert second["records_created"] == 0
        assert second["already_exists"] == 3

        # Total in DB should be 3, not 6
        count = (
            db.query(func.count(AttendanceEntry.attendance_entry_id))
            .filter(
                AttendanceEntry.client_id == client.client_id,
            )
            .scalar()
        )
        assert count == 3

    def test_mark_all_present_sets_correct_metadata(self, transactional_db):
        """Test that created records have correct field values."""
        db = transactional_db
        client, user, employees, shift = _seed_prereqs(db, num_employees=1)
        target_date = date(2026, 3, 15)

        result = mark_all_present(db, client.client_id, shift.shift_id, target_date, user)

        entry = (
            db.query(AttendanceEntry).filter(AttendanceEntry.attendance_entry_id == result["created_ids"][0]).first()
        )

        assert entry.client_id == client.client_id
        assert entry.employee_id == employees[0].employee_id
        assert entry.shift_id == shift.shift_id
        assert entry.shift_date == datetime.combine(target_date, datetime.min.time())
        assert entry.is_absent == 0
        assert entry.entered_by == user.user_id
