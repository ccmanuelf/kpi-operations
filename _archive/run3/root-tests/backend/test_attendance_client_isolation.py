"""
Multi-Tenant Attendance Client Isolation Tests
Tests strict data isolation for attendance records between clients
CRITICAL: Ensures Client A cannot access Client B's attendance data
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.user import User
from backend.schemas.client import Client
from backend.schemas.employee import Employee
from backend.schemas.shift import Shift
from backend.models.attendance import AttendanceRecordCreate
from backend.crud.attendance import (
    create_attendance_record,
    get_attendance_records,
    get_attendance_record,
    update_attendance_record,
    delete_attendance_record
)


@pytest.fixture
def client_a(test_db: Session):
    """Create Client A"""
    client = Client(
        client_id="CLIENT-A",
        client_name="Test Client A",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    return client


@pytest.fixture
def client_b(test_db: Session):
    """Create Client B"""
    client = Client(
        client_id="CLIENT-B",
        client_name="Test Client B",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    return client


@pytest.fixture
def operator_client_a(test_db: Session, client_a):
    """Create OPERATOR user for Client A"""
    user = User(
        username="operator_a",
        email="operator_a@test.com",
        password_hash="hashed_password",
        role="OPERATOR",
        client_id_fk="CLIENT-A",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def operator_client_b(test_db: Session, client_b):
    """Create OPERATOR user for Client B"""
    user = User(
        username="operator_b",
        email="operator_b@test.com",
        password_hash="hashed_password",
        role="OPERATOR",
        client_id_fk="CLIENT-B",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def leader_client_a(test_db: Session, client_a):
    """Create LEADER user for Client A"""
    user = User(
        username="leader_a",
        email="leader_a@test.com",
        password_hash="hashed_password",
        role="LEADER",
        client_id_fk="CLIENT-A",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def admin_user(test_db: Session):
    """Create ADMIN user (can access all clients)"""
    user = User(
        username="admin_user",
        email="admin@test.com",
        password_hash="hashed_password",
        role="ADMIN",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def shift_day(test_db: Session):
    """Create day shift"""
    shift = Shift(
        shift_name="Day Shift",
        start_time="08:00",
        end_time="16:00",
        is_active=True
    )
    test_db.add(shift)
    test_db.commit()
    return shift


@pytest.fixture
def employee_client_a(test_db: Session, client_a):
    """Create employee for Client A"""
    employee = Employee(
        employee_code="EMP-A-001",
        employee_name="Employee A",
        client_id_fk="CLIENT-A",
        is_active=True
    )
    test_db.add(employee)
    test_db.commit()
    return employee


@pytest.fixture
def employee_client_b(test_db: Session, client_b):
    """Create employee for Client B"""
    employee = Employee(
        employee_code="EMP-B-001",
        employee_name="Employee B",
        client_id_fk="CLIENT-B",
        is_active=True
    )
    test_db.add(employee)
    test_db.commit()
    return employee


class TestAttendanceOperatorIsolation:
    """Test OPERATOR role attendance isolation"""

    def test_operator_cannot_see_other_client_attendance(
        self, test_db, client_a, client_b, operator_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """Client A OPERATOR cannot see Client B attendance records"""
        # Create attendance for both clients
        att_a = AttendanceRecordCreate(
            employee_id=employee_client_a.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        att_b = AttendanceRecordCreate(
            employee_id=employee_client_b.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )

        created_a = create_attendance_record(test_db, att_a, operator_client_a)
        created_b = create_attendance_record(test_db, att_b, operator_client_b)

        # Client A OPERATOR queries attendance
        results_a = get_attendance_records(test_db, operator_client_a)

        # Verify only Client A's records returned
        assert len(results_a) == 1
        assert all(r.employee.client_id_fk == "CLIENT-A" for r in results_a)
        assert results_a[0].attendance_id == created_a.attendance_id

        # Verify Client B's record is not visible
        assert not any(r.attendance_id == created_b.attendance_id for r in results_a)

    def test_operator_cannot_access_other_client_record_by_id(
        self, test_db, operator_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """OPERATOR cannot access specific attendance record from other client"""
        # Create attendance for Client B
        att_b = AttendanceRecordCreate(
            employee_id=employee_client_b.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        created_b = create_attendance_record(test_db, att_b, operator_client_b)

        # Client A OPERATOR tries to access Client B's record
        result = get_attendance_record(test_db, created_b.attendance_id, operator_client_a)

        # Should return None (access denied)
        assert result is None

    def test_operator_cannot_update_other_client_attendance(
        self, test_db, operator_client_a, operator_client_b,
        employee_client_b, shift_day
    ):
        """OPERATOR cannot update attendance from other client"""
        # Create attendance for Client B
        att_b = AttendanceRecordCreate(
            employee_id=employee_client_b.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        created_b = create_attendance_record(test_db, att_b, operator_client_b)

        # Client A OPERATOR tries to update Client B's record
        update_data = {"status": "ABSENT", "actual_hours": Decimal("0.0")}
        result = update_attendance_record(
            test_db,
            created_b.attendance_id,
            update_data,
            operator_client_a
        )

        # Should return None (access denied)
        assert result is None

        # Verify record unchanged
        original = get_attendance_record(test_db, created_b.attendance_id, operator_client_b)
        assert original.status == "PRESENT"
        assert original.actual_hours == Decimal("8.0")

    def test_operator_cannot_delete_other_client_attendance(
        self, test_db, operator_client_a, operator_client_b,
        employee_client_b, shift_day
    ):
        """OPERATOR cannot delete attendance from other client"""
        # Create attendance for Client B
        att_b = AttendanceRecordCreate(
            employee_id=employee_client_b.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        created_b = create_attendance_record(test_db, att_b, operator_client_b)

        # Client A OPERATOR tries to delete Client B's record
        result = delete_attendance_record(
            test_db,
            created_b.attendance_id,
            operator_client_a
        )

        # Should return False (access denied)
        assert result is False

        # Verify record still exists
        existing = get_attendance_record(test_db, created_b.attendance_id, operator_client_b)
        assert existing is not None


class TestAttendanceLeaderIsolation:
    """Test LEADER role attendance isolation"""

    def test_leader_restricted_to_assigned_client(
        self, test_db, leader_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """LEADER can only access their assigned client's data"""
        # Create attendance for both clients
        att_a = AttendanceRecordCreate(
            employee_id=employee_client_a.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        att_b = AttendanceRecordCreate(
            employee_id=employee_client_b.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )

        created_a = create_attendance_record(test_db, att_a, leader_client_a)
        created_b = create_attendance_record(test_db, att_b, operator_client_b)

        # LEADER queries attendance
        results = get_attendance_records(test_db, leader_client_a)

        # Verify only assigned client's records
        assert len(results) == 1
        assert all(r.employee.client_id_fk == "CLIENT-A" for r in results)
        assert not any(r.attendance_id == created_b.attendance_id for r in results)


class TestAttendanceAdminAccess:
    """Test ADMIN role can access all clients"""

    def test_admin_can_see_all_clients_attendance(
        self, test_db, admin_user, operator_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """ADMIN can access attendance for all clients"""
        # Create attendance for both clients
        att_a = AttendanceRecordCreate(
            employee_id=employee_client_a.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        att_b = AttendanceRecordCreate(
            employee_id=employee_client_b.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="ABSENT"
        )

        created_a = create_attendance_record(test_db, att_a, operator_client_a)
        created_b = create_attendance_record(test_db, att_b, operator_client_b)

        # ADMIN queries all attendance
        results = get_attendance_records(test_db, admin_user)

        # Verify both clients' records returned
        assert len(results) >= 2
        client_ids = set(r.employee.client_id_fk for r in results)
        assert "CLIENT-A" in client_ids
        assert "CLIENT-B" in client_ids

        # Verify specific records exist
        record_ids = [r.attendance_id for r in results]
        assert created_a.attendance_id in record_ids
        assert created_b.attendance_id in record_ids

    def test_admin_can_update_any_client_attendance(
        self, test_db, admin_user, operator_client_b,
        employee_client_b, shift_day
    ):
        """ADMIN can update attendance for any client"""
        # Create attendance for Client B
        att_b = AttendanceRecordCreate(
            employee_id=employee_client_b.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        created_b = create_attendance_record(test_db, att_b, operator_client_b)

        # ADMIN updates Client B's record
        update_data = {"status": "LATE", "actual_hours": Decimal("6.0")}
        result = update_attendance_record(
            test_db,
            created_b.attendance_id,
            update_data,
            admin_user
        )

        # Verify update succeeded
        assert result is not None
        assert result.status == "LATE"
        assert result.actual_hours == Decimal("6.0")


class TestAttendanceDateRangeIsolation:
    """Test date range filtering maintains client isolation"""

    def test_date_range_query_respects_client_boundary(
        self, test_db, operator_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """Date range queries maintain client isolation"""
        # Create attendance for multiple dates
        dates = [date.today() - timedelta(days=i) for i in range(5)]

        for attendance_date in dates:
            # Client A attendance
            att_a = AttendanceRecordCreate(
                employee_id=employee_client_a.employee_id,
                shift_id=shift_day.shift_id,
                attendance_date=attendance_date,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                status="PRESENT"
            )
            # Client B attendance
            att_b = AttendanceRecordCreate(
                employee_id=employee_client_b.employee_id,
                shift_id=shift_day.shift_id,
                attendance_date=attendance_date,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                status="PRESENT"
            )

            create_attendance_record(test_db, att_a, operator_client_a)
            create_attendance_record(test_db, att_b, operator_client_b)

        # Client A queries date range
        results_a = get_attendance_records(
            test_db,
            operator_client_a,
            start_date=dates[-1],
            end_date=dates[0]
        )

        # Verify only Client A records
        assert len(results_a) == 5
        assert all(r.employee.client_id_fk == "CLIENT-A" for r in results_a)


class TestAttendanceConcurrentAccess:
    """Test concurrent access maintains isolation"""

    def test_concurrent_queries_maintain_isolation(
        self, test_db, operator_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """Concurrent queries by different clients maintain isolation"""
        import threading

        # Create attendance for both clients
        att_a = AttendanceRecordCreate(
            employee_id=employee_client_a.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        att_b = AttendanceRecordCreate(
            employee_id=employee_client_b.employee_id,
            shift_id=shift_day.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )

        create_attendance_record(test_db, att_a, operator_client_a)
        create_attendance_record(test_db, att_b, operator_client_b)

        # Concurrent queries
        results = {"CLIENT-A": None, "CLIENT-B": None}

        def query_client_a():
            results["CLIENT-A"] = get_attendance_records(test_db, operator_client_a)

        def query_client_b():
            results["CLIENT-B"] = get_attendance_records(test_db, operator_client_b)

        thread_a = threading.Thread(target=query_client_a)
        thread_b = threading.Thread(target=query_client_b)

        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

        # Verify no cross-contamination
        assert all(r.employee.client_id_fk == "CLIENT-A" for r in results["CLIENT-A"])
        assert all(r.employee.client_id_fk == "CLIENT-B" for r in results["CLIENT-B"])
        assert len(results["CLIENT-A"]) == 1
        assert len(results["CLIENT-B"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
