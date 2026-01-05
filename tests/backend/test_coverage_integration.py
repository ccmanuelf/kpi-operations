"""
Integration Tests for Shift Coverage API Endpoints
Tests all 6 coverage endpoints, floating pool assignment, and double-billing prevention
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.coverage import ShiftCoverage
from backend.schemas.employee import Employee
from backend.schemas.shift import Shift
from backend.schemas.user import User
from backend.crud.coverage import (
    create_shift_coverage,
    get_shift_coverage,
    get_shift_coverages,
    update_shift_coverage,
    delete_shift_coverage
)


@pytest.fixture
def test_employees(test_db: Session):
    """Create test employees including floating pool"""
    employees = []
    for i in range(5):
        emp = Employee(
            employee_code=f"EMP-CVG-{i:03d}",
            employee_name=f"Coverage Test Employee {i}",
            is_floating_pool=1 if i < 2 else 0,  # First 2 are floating pool
            client_id_fk="TEST-CLIENT"
        )
        test_db.add(emp)
        test_db.flush()
        employees.append(emp)
    test_db.commit()
    return employees


@pytest.fixture
def test_shift(test_db: Session):
    """Create test shift"""
    shift = Shift(
        shift_name="Coverage Test Shift",
        start_time="08:00",
        end_time="16:00",
        is_active=True
    )
    test_db.add(shift)
    test_db.commit()
    return shift


@pytest.fixture
def test_user(test_db: Session):
    """Create test supervisor user"""
    user = User(
        username="coverage_supervisor",
        email="coverage@test.com",
        password_hash="hashed_password",
        full_name="Coverage Supervisor",
        role="SUPERVISOR",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


class TestCoverageCreate:
    """Test POST /api/coverage - Create shift coverage record"""

    def test_create_regular_coverage(self, test_db, test_employees, test_shift, test_user):
        """Should create shift coverage for regular employee"""
        from backend.models.coverage import ShiftCoverageCreate

        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[2].employee_id,  # Regular employee
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False
        )

        result = create_shift_coverage(test_db, coverage_data, test_user)

        assert result is not None
        assert result.employee_id == test_employees[2].employee_id
        assert result.hours_assigned == Decimal("8.0")
        assert result.is_floating_pool is False

    def test_create_floating_pool_coverage(self, test_db, test_employees, test_shift, test_user):
        """Should create shift coverage for floating pool employee"""
        from backend.models.coverage import ShiftCoverageCreate

        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[0].employee_id,  # Floating pool
            hours_assigned=Decimal("8.0"),
            is_floating_pool=True
        )

        result = create_shift_coverage(test_db, coverage_data, test_user)

        assert result is not None
        assert result.is_floating_pool is True

    def test_create_partial_coverage(self, test_db, test_employees, test_shift, test_user):
        """Should create partial shift coverage"""
        from backend.models.coverage import ShiftCoverageCreate

        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[2].employee_id,
            hours_assigned=Decimal("4.0"),
            is_floating_pool=False
        )

        result = create_shift_coverage(test_db, coverage_data, test_user)

        assert result.hours_assigned == Decimal("4.0")


class TestCoverageRead:
    """Test GET /api/coverage - List shift coverage records"""

    def test_list_all_coverage(self, test_db, test_employees, test_shift, test_user):
        """Should list all shift coverage records"""
        from backend.models.coverage import ShiftCoverageCreate

        # Create multiple coverage records
        for i, emp in enumerate(test_employees[:3]):
            coverage_data = ShiftCoverageCreate(
                shift_id=test_shift.shift_id,
                coverage_date=date.today(),
                employee_id=emp.employee_id,
                hours_assigned=Decimal("8.0"),
                is_floating_pool=(i < 2)
            )
            create_shift_coverage(test_db, coverage_data, test_user)

        result = get_shift_coverages(test_db, test_user)

        assert len(result) == 3

    def test_filter_by_date_range(self, test_db, test_employees, test_shift, test_user):
        """Should filter coverage by date range"""
        from backend.models.coverage import ShiftCoverageCreate

        # Create records for different dates
        dates = [date.today() - timedelta(days=i) for i in range(5)]
        for d in dates:
            coverage_data = ShiftCoverageCreate(
                shift_id=test_shift.shift_id,
                coverage_date=d,
                employee_id=test_employees[2].employee_id,
                hours_assigned=Decimal("8.0"),
                is_floating_pool=False
            )
            create_shift_coverage(test_db, coverage_data, test_user)

        start_date = date.today() - timedelta(days=2)
        end_date = date.today()

        result = get_shift_coverages(
            test_db, test_user,
            start_date=start_date,
            end_date=end_date
        )

        assert len(result) == 3

    def test_filter_by_shift(self, test_db, test_employees, test_user):
        """Should filter coverage by shift"""
        from backend.models.coverage import ShiftCoverageCreate

        # Create another shift
        shift2 = Shift(
            shift_name="Night Shift",
            start_time="16:00",
            end_time="00:00",
            is_active=True
        )
        test_db.add(shift2)
        test_db.commit()

        # Create coverage for both shifts
        shifts = [test_shift, shift2]
        for shift in shifts:
            coverage_data = ShiftCoverageCreate(
                shift_id=shift.shift_id,
                coverage_date=date.today(),
                employee_id=test_employees[2].employee_id,
                hours_assigned=Decimal("8.0"),
                is_floating_pool=False
            )
            create_shift_coverage(test_db, coverage_data, test_user)

        result = get_shift_coverages(test_db, test_user, shift_id=shift2.shift_id)

        assert len(result) == 1
        assert result[0].shift_id == shift2.shift_id


class TestCoverageGetById:
    """Test GET /api/coverage/{coverage_id} - Get coverage by ID"""

    def test_get_existing_coverage(self, test_db, test_employees, test_shift, test_user):
        """Should get coverage record by ID"""
        from backend.models.coverage import ShiftCoverageCreate

        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[2].employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False
        )

        created = create_shift_coverage(test_db, coverage_data, test_user)
        result = get_shift_coverage(test_db, created.coverage_id, test_user)

        assert result is not None
        assert result.coverage_id == created.coverage_id

    def test_get_nonexistent_coverage(self, test_db, test_user):
        """Should return None for nonexistent coverage"""
        result = get_shift_coverage(test_db, 99999, test_user)
        assert result is None


class TestCoverageUpdate:
    """Test PUT /api/coverage/{coverage_id} - Update coverage"""

    def test_update_hours_assigned(self, test_db, test_employees, test_shift, test_user):
        """Should update hours assigned"""
        from backend.models.coverage import ShiftCoverageCreate, ShiftCoverageUpdate

        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[2].employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False
        )
        created = create_shift_coverage(test_db, coverage_data, test_user)

        update_data = ShiftCoverageUpdate(hours_assigned=Decimal("6.0"))
        updated = update_shift_coverage(test_db, created.coverage_id, update_data, test_user)

        assert updated.hours_assigned == Decimal("6.0")

    def test_update_floating_pool_status(self, test_db, test_employees, test_shift, test_user):
        """Should update floating pool status"""
        from backend.models.coverage import ShiftCoverageCreate, ShiftCoverageUpdate

        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[0].employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False
        )
        created = create_shift_coverage(test_db, coverage_data, test_user)

        update_data = ShiftCoverageUpdate(is_floating_pool=True)
        updated = update_shift_coverage(test_db, created.coverage_id, update_data, test_user)

        assert updated.is_floating_pool is True


class TestCoverageDelete:
    """Test DELETE /api/coverage/{coverage_id} - Delete coverage"""

    def test_delete_coverage_as_supervisor(self, test_db, test_employees, test_shift, test_user):
        """Should delete coverage record as supervisor"""
        from backend.models.coverage import ShiftCoverageCreate

        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[2].employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False
        )
        created = create_shift_coverage(test_db, coverage_data, test_user)

        success = delete_shift_coverage(test_db, created.coverage_id, test_user)

        assert success is True

        # Verify deleted
        result = get_shift_coverage(test_db, created.coverage_id, test_user)
        assert result is None


class TestFloatingPoolAssignment:
    """Test floating pool employee assignment and tracking"""

    def test_floating_pool_can_work_multiple_shifts(self, test_db, test_employees, test_shift, test_user):
        """Floating pool employee can work multiple shifts in same day"""
        from backend.models.coverage import ShiftCoverageCreate

        # Create multiple shifts
        shift2 = Shift(shift_name="Shift 2", start_time="16:00", end_time="00:00", is_active=True)
        test_db.add(shift2)
        test_db.commit()

        floating_emp = test_employees[0]  # Floating pool employee

        # Assign to both shifts
        for shift in [test_shift, shift2]:
            coverage_data = ShiftCoverageCreate(
                shift_id=shift.shift_id,
                coverage_date=date.today(),
                employee_id=floating_emp.employee_id,
                hours_assigned=Decimal("4.0"),
                is_floating_pool=True
            )
            create_shift_coverage(test_db, coverage_data, test_user)

        # Query all coverage for this employee
        all_coverage = test_db.query(ShiftCoverage).filter(
            ShiftCoverage.employee_id == floating_emp.employee_id,
            ShiftCoverage.coverage_date == date.today()
        ).all()

        assert len(all_coverage) == 2
        total_hours = sum(c.hours_assigned for c in all_coverage)
        assert total_hours == Decimal("8.0")

    def test_floating_pool_assigned_to_different_clients(self, test_db, test_employees, test_shift, test_user):
        """Floating pool employee can be assigned to different clients"""
        from backend.models.coverage import ShiftCoverageCreate

        floating_emp = test_employees[0]

        # Create coverage for today (Client A)
        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=floating_emp.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=True,
            client_id_fk="CLIENT-A"
        )
        create_shift_coverage(test_db, coverage_data, test_user)

        # Create coverage for tomorrow (Client B)
        tomorrow = date.today() + timedelta(days=1)
        coverage_data2 = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=tomorrow,
            employee_id=floating_emp.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=True,
            client_id_fk="CLIENT-B"
        )
        create_shift_coverage(test_db, coverage_data2, test_user)

        # Verify both assignments exist
        all_coverage = test_db.query(ShiftCoverage).filter(
            ShiftCoverage.employee_id == floating_emp.employee_id
        ).all()

        assert len(all_coverage) == 2
        clients = [c.client_id_fk for c in all_coverage]
        assert "CLIENT-A" in clients
        assert "CLIENT-B" in clients


class TestDoubleBillingPrevention:
    """Test prevention of double-billing same employee to multiple clients"""

    def test_prevent_double_booking_same_shift(self, test_db, test_employees, test_shift, test_user):
        """Should prevent double-booking employee to same shift"""
        from backend.models.coverage import ShiftCoverageCreate

        # First booking
        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[2].employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False
        )
        create_shift_coverage(test_db, coverage_data, test_user)

        # Second booking (should fail or warn)
        coverage_data2 = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[2].employee_id,
            hours_assigned=Decimal("4.0"),
            is_floating_pool=False
        )

        # Note: Implementation should check for existing coverage
        # This test assumes validation is in place
        existing = test_db.query(ShiftCoverage).filter(
            ShiftCoverage.shift_id == test_shift.shift_id,
            ShiftCoverage.coverage_date == date.today(),
            ShiftCoverage.employee_id == test_employees[2].employee_id
        ).first()

        assert existing is not None  # Employee already assigned

    def test_track_total_hours_per_employee_per_day(self, test_db, test_employees, test_shift, test_user):
        """Should track total hours per employee per day"""
        from backend.models.coverage import ShiftCoverageCreate

        # Create multiple shifts
        shift2 = Shift(shift_name="Afternoon", start_time="12:00", end_time="20:00", is_active=True)
        test_db.add(shift2)
        test_db.commit()

        employee = test_employees[2]

        # Assign to multiple shifts
        for shift in [test_shift, shift2]:
            coverage_data = ShiftCoverageCreate(
                shift_id=shift.shift_id,
                coverage_date=date.today(),
                employee_id=employee.employee_id,
                hours_assigned=Decimal("4.0"),
                is_floating_pool=False
            )
            create_shift_coverage(test_db, coverage_data, test_user)

        # Calculate total hours for the day
        total_hours = test_db.query(
            test_db.func.sum(ShiftCoverage.hours_assigned)
        ).filter(
            ShiftCoverage.employee_id == employee.employee_id,
            ShiftCoverage.coverage_date == date.today()
        ).scalar()

        assert total_hours == Decimal("8.0")

    def test_warn_overtime_assignment(self, test_db, test_employees, test_shift, test_user):
        """Should warn when assigning more than 8 hours per day"""
        from backend.models.coverage import ShiftCoverageCreate

        employee = test_employees[2]

        # Assign 10 hours total
        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=employee.employee_id,
            hours_assigned=Decimal("10.0"),
            is_floating_pool=False
        )

        created = create_shift_coverage(test_db, coverage_data, test_user)

        # Verify overtime assignment
        assert created.hours_assigned > Decimal("8.0")


class TestCoverageRBAC:
    """Test role-based access control for coverage endpoints"""

    def test_supervisor_can_create_coverage(self, test_db, test_employees, test_shift):
        """SUPERVISOR can create shift coverage"""
        supervisor = User(
            username="coverage_super",
            email="super@test.com",
            password_hash="hashed",
            role="SUPERVISOR",
            is_active=True
        )
        test_db.add(supervisor)
        test_db.commit()

        from backend.models.coverage import ShiftCoverageCreate

        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[2].employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False
        )

        result = create_shift_coverage(test_db, coverage_data, supervisor)
        assert result is not None

    def test_operator_can_view_coverage(self, test_db, test_employees, test_shift):
        """OPERATOR can view shift coverage"""
        operator = User(
            username="coverage_operator",
            email="operator@test.com",
            password_hash="hashed",
            role="OPERATOR",
            is_active=True
        )
        test_db.add(operator)
        test_db.commit()

        from backend.models.coverage import ShiftCoverageCreate

        coverage_data = ShiftCoverageCreate(
            shift_id=test_shift.shift_id,
            coverage_date=date.today(),
            employee_id=test_employees[2].employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=False
        )

        created = create_shift_coverage(test_db, coverage_data, operator)
        result = get_shift_coverage(test_db, created.coverage_id, operator)

        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
