"""
Multi-Tenant Shift Coverage Client Isolation Tests
Tests strict data isolation for shift coverage between clients
CRITICAL: Ensures shift coverage assignments are properly isolated
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.user import User
from backend.schemas.client import Client
from backend.schemas.employee import Employee
from backend.schemas.shift import Shift
from backend.models.coverage import ShiftCoverageCreate
from backend.crud.coverage import (
    create_shift_coverage,
    get_shift_coverages,
    get_shift_coverage,
    update_shift_coverage,
    delete_shift_coverage
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


@pytest.fixture
def floating_employee(test_db: Session):
    """Create floating pool employee"""
    employee = Employee(
        employee_code="FLOAT-001",
        employee_name="Floating Employee",
        is_floating_pool=1,
        is_active=True
    )
    test_db.add(employee)
    test_db.commit()
    return employee


class TestCoverageOperatorIsolation:
    """Test OPERATOR role coverage isolation"""

    def test_operator_cannot_see_other_client_coverage(
        self, test_db, operator_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """Client A OPERATOR cannot see Client B coverage records"""
        # Create coverage for both clients
        cov_a = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date.today(),
            employee_id=employee_client_a.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False,
            client_id_fk="CLIENT-A"
        )
        cov_b = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date.today(),
            employee_id=employee_client_b.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False,
            client_id_fk="CLIENT-B"
        )

        created_a = create_shift_coverage(test_db, cov_a, operator_client_a)
        created_b = create_shift_coverage(test_db, cov_b, operator_client_b)

        # Client A OPERATOR queries coverage
        results_a = get_shift_coverages(test_db, operator_client_a)

        # Verify only Client A's records returned
        assert len(results_a) == 1
        assert all(r.client_id_fk == "CLIENT-A" for r in results_a)
        assert results_a[0].coverage_id == created_a.coverage_id

        # Verify Client B's record is not visible
        assert not any(r.coverage_id == created_b.coverage_id for r in results_a)

    def test_operator_cannot_access_other_client_coverage_by_id(
        self, test_db, operator_client_a, operator_client_b,
        employee_client_b, shift_day
    ):
        """OPERATOR cannot access specific coverage record from other client"""
        # Create coverage for Client B
        cov_b = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date.today(),
            employee_id=employee_client_b.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False,
            client_id_fk="CLIENT-B"
        )
        created_b = create_shift_coverage(test_db, cov_b, operator_client_b)

        # Client A OPERATOR tries to access Client B's record
        result = get_shift_coverage(test_db, created_b.coverage_id, operator_client_a)

        # Should return None (access denied)
        assert result is None

    def test_operator_cannot_update_other_client_coverage(
        self, test_db, operator_client_a, operator_client_b,
        employee_client_b, shift_day
    ):
        """OPERATOR cannot update coverage from other client"""
        # Create coverage for Client B
        cov_b = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date.today(),
            employee_id=employee_client_b.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False,
            client_id_fk="CLIENT-B"
        )
        created_b = create_shift_coverage(test_db, cov_b, operator_client_b)

        # Client A OPERATOR tries to update Client B's record
        update_data = {"hours_assigned": Decimal("6.0")}
        result = update_shift_coverage(
            test_db,
            created_b.coverage_id,
            update_data,
            operator_client_a
        )

        # Should return None (access denied)
        assert result is None

        # Verify record unchanged
        original = get_shift_coverage(test_db, created_b.coverage_id, operator_client_b)
        assert original.hours_assigned == Decimal("8.0")


class TestCoverageLeaderIsolation:
    """Test LEADER role coverage isolation"""

    def test_leader_restricted_to_assigned_client(
        self, test_db, leader_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """LEADER can only access their assigned client's coverage"""
        # Create coverage for both clients
        cov_a = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date.today(),
            employee_id=employee_client_a.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False,
            client_id_fk="CLIENT-A"
        )
        cov_b = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date.today(),
            employee_id=employee_client_b.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False,
            client_id_fk="CLIENT-B"
        )

        created_a = create_shift_coverage(test_db, cov_a, leader_client_a)
        created_b = create_shift_coverage(test_db, cov_b, operator_client_b)

        # LEADER queries coverage
        results = get_shift_coverages(test_db, leader_client_a)

        # Verify only assigned client's records
        assert len(results) == 1
        assert all(r.client_id_fk == "CLIENT-A" for r in results)
        assert not any(r.coverage_id == created_b.coverage_id for r in results)


class TestCoverageAdminAccess:
    """Test ADMIN role can access all clients"""

    def test_admin_can_see_all_clients_coverage(
        self, test_db, admin_user, operator_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """ADMIN can access coverage for all clients"""
        # Create coverage for both clients
        cov_a = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date.today(),
            employee_id=employee_client_a.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False,
            client_id_fk="CLIENT-A"
        )
        cov_b = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date.today(),
            employee_id=employee_client_b.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False,
            client_id_fk="CLIENT-B"
        )

        created_a = create_shift_coverage(test_db, cov_a, operator_client_a)
        created_b = create_shift_coverage(test_db, cov_b, operator_client_b)

        # ADMIN queries all coverage
        results = get_shift_coverages(test_db, admin_user)

        # Verify both clients' records returned
        assert len(results) >= 2
        client_ids = set(r.client_id_fk for r in results)
        assert "CLIENT-A" in client_ids
        assert "CLIENT-B" in client_ids

        # Verify specific records exist
        record_ids = [r.coverage_id for r in results]
        assert created_a.coverage_id in record_ids
        assert created_b.coverage_id in record_ids


class TestFloatingPoolIsolation:
    """Test floating pool employee assignment isolation"""

    def test_floating_pool_assignment_isolated_per_client(
        self, test_db, operator_client_a, operator_client_b,
        floating_employee, shift_day
    ):
        """Floating pool assignments tracked per client"""
        # Assign floating employee to Client A
        cov_a = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date.today(),
            employee_id=floating_employee.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=True,
            client_id_fk="CLIENT-A"
        )

        created_a = create_shift_coverage(test_db, cov_a, operator_client_a)

        # Client A sees assignment
        results_a = get_shift_coverages(
            test_db,
            operator_client_a,
            coverage_date=date.today()
        )
        assert len(results_a) == 1
        assert results_a[0].is_floating_pool is True

        # Client B should NOT see Client A's assignment
        results_b = get_shift_coverages(
            test_db,
            operator_client_b,
            coverage_date=date.today()
        )
        assert len(results_b) == 0

    def test_floating_pool_can_be_assigned_to_different_clients_different_dates(
        self, test_db, operator_client_a, operator_client_b,
        floating_employee, shift_day
    ):
        """Floating pool can be assigned to different clients on different dates"""
        # Assign to Client A on date 1
        date_1 = date.today()
        cov_a = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date_1,
            employee_id=floating_employee.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=True,
            client_id_fk="CLIENT-A"
        )
        create_shift_coverage(test_db, cov_a, operator_client_a)

        # Assign to Client B on date 2
        date_2 = date.today() + timedelta(days=1)
        cov_b = ShiftCoverageCreate(
            shift_id=shift_day.shift_id,
            coverage_date=date_2,
            employee_id=floating_employee.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=True,
            client_id_fk="CLIENT-B"
        )
        create_shift_coverage(test_db, cov_b, operator_client_b)

        # Client A sees only their date
        results_a = get_shift_coverages(test_db, operator_client_a, coverage_date=date_1)
        assert len(results_a) == 1
        assert results_a[0].client_id_fk == "CLIENT-A"

        # Client B sees only their date
        results_b = get_shift_coverages(test_db, operator_client_b, coverage_date=date_2)
        assert len(results_b) == 1
        assert results_b[0].client_id_fk == "CLIENT-B"


class TestCoverageDateRangeIsolation:
    """Test date range filtering maintains client isolation"""

    def test_date_range_query_respects_client_boundary(
        self, test_db, operator_client_a, operator_client_b,
        employee_client_a, employee_client_b, shift_day
    ):
        """Date range queries maintain client isolation"""
        # Create coverage for multiple dates
        dates = [date.today() - timedelta(days=i) for i in range(5)]

        for coverage_date in dates:
            # Client A coverage
            cov_a = ShiftCoverageCreate(
                shift_id=shift_day.shift_id,
                coverage_date=coverage_date,
                employee_id=employee_client_a.employee_id,
                hours_assigned=Decimal("8.0"),
                is_floating_pool=False,
                client_id_fk="CLIENT-A"
            )
            # Client B coverage
            cov_b = ShiftCoverageCreate(
                shift_id=shift_day.shift_id,
                coverage_date=coverage_date,
                employee_id=employee_client_b.employee_id,
                hours_assigned=Decimal("8.0"),
                is_floating_pool=False,
                client_id_fk="CLIENT-B"
            )

            create_shift_coverage(test_db, cov_a, operator_client_a)
            create_shift_coverage(test_db, cov_b, operator_client_b)

        # Client A queries date range
        results_a = get_shift_coverages(
            test_db,
            operator_client_a,
            start_date=dates[-1],
            end_date=dates[0]
        )

        # Verify only Client A records
        assert len(results_a) == 5
        assert all(r.client_id_fk == "CLIENT-A" for r in results_a)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
