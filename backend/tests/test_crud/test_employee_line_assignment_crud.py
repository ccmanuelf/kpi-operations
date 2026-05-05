"""
Tests for Employee Line Assignment CRUD operations.
Uses real database sessions -- no mocks for DB layer.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from backend.tests.fixtures.factories import TestDataFactory
from backend.orm.production_line import ProductionLine
from backend.crud.employee_line_assignment import (
    create_assignment,
    list_assignments,
    get_assignment,
    get_employee_lines,
    get_line_employees,
    update_assignment,
    end_assignment,
    validate_allocation,
)
from backend.schemas.employee_line_assignment import (
    EmployeeLineAssignmentCreate,
    EmployeeLineAssignmentUpdate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
CLIENT_ID = "ELA-TEST-C1"
CLIENT_ID_B = "ELA-TEST-C2"
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


def _seed_client(db, client_id=CLIENT_ID):
    """Create the minimal client row needed for FK constraints."""
    client = TestDataFactory.create_client(
        db,
        client_id=client_id,
        client_name=f"Test Client {client_id}",
    )
    db.commit()
    return client


def _seed_employee(db, client_id=CLIENT_ID, is_active=True, **kwargs):
    """Create an employee for testing."""
    employee = TestDataFactory.create_employee(
        db,
        client_id=client_id,
        is_active=is_active,
        **kwargs,
    )
    db.commit()
    return employee


def _seed_line(db, client_id=CLIENT_ID, line_code=None, line_name=None):
    """Create a production line for testing."""
    if line_code is None:
        line_code = TestDataFactory._next_id("LINE")
    if line_name is None:
        line_name = f"Test Line {line_code}"
    line = ProductionLine(
        client_id=client_id,
        line_code=line_code,
        line_name=line_name,
        line_type="DEDICATED",
        is_active=True,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _make_create(
    employee_id,
    line_id,
    client_id=CLIENT_ID,
    allocation=Decimal("100.00"),
    is_primary=True,
    effective_date=None,
    end_date=None,
):
    """Build an EmployeeLineAssignmentCreate payload."""
    return EmployeeLineAssignmentCreate(
        employee_id=employee_id,
        line_id=line_id,
        client_id=client_id,
        allocation_percentage=allocation,
        is_primary=is_primary,
        effective_date=effective_date or TODAY,
        end_date=end_date,
    )


# ============================================================================
# TestCreateAssignment
# ============================================================================
class TestCreateAssignment:
    """Tests for create_assignment function."""

    def test_create_single_assignment_100_percent(self, transactional_db):
        """Create 1 assignment at 100% -- the default case."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        data = _make_create(emp.employee_id, line.line_id)
        result = create_assignment(db, data)

        assert result.assignment_id is not None
        assert result.employee_id == emp.employee_id
        assert result.line_id == line.line_id
        assert result.client_id == CLIENT_ID
        assert result.allocation_percentage == Decimal("100.00")
        assert result.is_primary is True
        assert result.effective_date == TODAY
        assert result.end_date is None
        assert result.created_at is not None

    def test_create_60_40_split(self, transactional_db):
        """Create 60% + 40% split across two lines."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        a1 = create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("60.00")),
        )
        a2 = create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("40.00"),
                is_primary=False,
            ),
        )

        assert a1.allocation_percentage == Decimal("60.00")
        assert a2.allocation_percentage == Decimal("40.00")
        assert a1.is_primary is True
        assert a2.is_primary is False

    def test_third_assignment_raises(self, transactional_db):
        """Cannot create a 3rd active assignment."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")
        line3 = _seed_line(db, line_code="L3")

        create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("50.00")),
        )
        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("50.00"),
                is_primary=False,
            ),
        )

        with pytest.raises(ValueError, match="Maximum 2 line assignments"):
            create_assignment(
                db,
                _make_create(
                    emp.employee_id,
                    line3.line_id,
                    allocation=Decimal("10.00"),
                    is_primary=False,
                ),
            )

    def test_allocation_exceeds_100_raises(self, transactional_db):
        """70% + 40% = 110% must fail."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("70.00")),
        )

        with pytest.raises(ValueError, match="Total allocation cannot exceed 100%"):
            create_assignment(
                db,
                _make_create(
                    emp.employee_id,
                    line2.line_id,
                    allocation=Decimal("40.00"),
                    is_primary=False,
                ),
            )

    def test_employee_not_found_raises(self, transactional_db):
        """Creating assignment for non-existent employee raises ValueError."""
        db = transactional_db
        _seed_client(db)
        line = _seed_line(db)

        with pytest.raises(ValueError, match="not found"):
            create_assignment(db, _make_create(99999, line.line_id))

    def test_inactive_employee_raises(self, transactional_db):
        """Creating assignment for inactive employee raises ValueError."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db, is_active=False)
        line = _seed_line(db)

        with pytest.raises(ValueError, match="not active"):
            create_assignment(db, _make_create(emp.employee_id, line.line_id))

    def test_first_assignment_forced_primary(self, transactional_db):
        """First assignment is always primary even if is_primary=False."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        result = create_assignment(
            db,
            _make_create(emp.employee_id, line.line_id, is_primary=False),
        )

        assert result.is_primary is True

    def test_second_primary_demotes_existing(self, transactional_db):
        """Creating a second assignment as primary demotes the first."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        a1 = create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("60.00")),
        )
        a2 = create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("40.00"),
                is_primary=True,
            ),
        )

        # Refresh a1 to see the updated value
        db.refresh(a1)
        assert a1.is_primary is False
        assert a2.is_primary is True

    def test_duplicate_assignment_raises(self, transactional_db):
        """Same employee + line + effective_date raises ValueError (unique constraint)."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        create_assignment(
            db,
            _make_create(emp.employee_id, line.line_id, allocation=Decimal("50.00")),
        )

        with pytest.raises(ValueError, match="Duplicate"):
            create_assignment(
                db,
                _make_create(emp.employee_id, line.line_id, allocation=Decimal("50.00")),
            )

    def test_ended_assignment_does_not_count(self, transactional_db):
        """Ended assignments do not count toward the 2-assignment limit."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")
        line3 = _seed_line(db, line_code="L3")

        a1 = create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("50.00")),
        )
        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("50.00"),
                is_primary=False,
            ),
        )

        # End the first assignment
        end_assignment(db, a1.assignment_id)

        # Now can create a third (since only 1 active)
        a3 = create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line3.line_id,
                allocation=Decimal("50.00"),
                is_primary=True,
                effective_date=TODAY + timedelta(days=1),
            ),
        )
        assert a3.assignment_id is not None


# ============================================================================
# TestListAssignments
# ============================================================================
class TestListAssignments:
    """Tests for list_assignments function."""

    def test_list_all_for_employee(self, transactional_db):
        """List assignments filtered by employee_id."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("60.00")),
        )
        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("40.00"),
                is_primary=False,
            ),
        )

        results = list_assignments(db, employee_id=emp.employee_id)
        assert len(results) == 2

    def test_list_filters_by_line(self, transactional_db):
        """List assignments filtered by line_id."""
        db = transactional_db
        _seed_client(db)
        emp1 = _seed_employee(db, employee_code="E1")
        emp2 = _seed_employee(db, employee_code="E2")
        line = _seed_line(db)

        create_assignment(db, _make_create(emp1.employee_id, line.line_id))
        create_assignment(db, _make_create(emp2.employee_id, line.line_id))

        results = list_assignments(db, line_id=line.line_id)
        assert len(results) == 2

    def test_list_filters_by_client(self, transactional_db):
        """List assignments filtered by client_id."""
        db = transactional_db
        _seed_client(db, CLIENT_ID)
        _seed_client(db, CLIENT_ID_B)

        emp_a = _seed_employee(db, client_id=CLIENT_ID, employee_code="EA")
        emp_b = _seed_employee(db, client_id=CLIENT_ID_B, employee_code="EB")
        line_a = _seed_line(db, client_id=CLIENT_ID, line_code="LA")
        line_b = _seed_line(db, client_id=CLIENT_ID_B, line_code="LB")

        create_assignment(db, _make_create(emp_a.employee_id, line_a.line_id, client_id=CLIENT_ID))
        create_assignment(db, _make_create(emp_b.employee_id, line_b.line_id, client_id=CLIENT_ID_B))

        results_a = list_assignments(db, client_id=CLIENT_ID)
        results_b = list_assignments(db, client_id=CLIENT_ID_B)

        assert len(results_a) == 1
        assert len(results_b) == 1
        assert results_a[0].client_id == CLIENT_ID
        assert results_b[0].client_id == CLIENT_ID_B

    def test_list_active_only_excludes_ended(self, transactional_db):
        """active_only=True excludes ended assignments."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        a = create_assignment(db, _make_create(emp.employee_id, line.line_id))
        end_assignment(db, a.assignment_id)

        active = list_assignments(db, employee_id=emp.employee_id, active_only=True)
        all_entries = list_assignments(db, employee_id=emp.employee_id, active_only=False)

        assert len(active) == 0
        assert len(all_entries) == 1

    def test_list_empty(self, transactional_db):
        """List returns empty when no assignments exist."""
        results = list_assignments(transactional_db)
        assert results == []


# ============================================================================
# TestGetAssignment
# ============================================================================
class TestGetAssignment:
    """Tests for get_assignment function."""

    def test_get_found(self, transactional_db):
        """Get returns the assignment when it exists."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        created = create_assignment(db, _make_create(emp.employee_id, line.line_id))
        result = get_assignment(db, created.assignment_id)

        assert result is not None
        assert result.assignment_id == created.assignment_id

    def test_get_not_found(self, transactional_db):
        """Get returns None for non-existent assignment."""
        result = get_assignment(transactional_db, 999999)
        assert result is None


# ============================================================================
# TestGetEmployeeLines
# ============================================================================
class TestGetEmployeeLines:
    """Tests for get_employee_lines function."""

    def test_returns_active_only(self, transactional_db):
        """get_employee_lines returns only active assignments."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        a1 = create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("60.00")),
        )
        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("40.00"),
                is_primary=False,
            ),
        )

        # End one
        end_assignment(db, a1.assignment_id)

        results = get_employee_lines(db, emp.employee_id)
        assert len(results) == 1
        assert results[0].line_id == line2.line_id

    def test_primary_first(self, transactional_db):
        """get_employee_lines returns primary assignment first."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("60.00")),
        )
        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("40.00"),
                is_primary=False,
            ),
        )

        results = get_employee_lines(db, emp.employee_id)
        assert len(results) == 2
        assert results[0].is_primary is True


# ============================================================================
# TestGetLineEmployees
# ============================================================================
class TestGetLineEmployees:
    """Tests for get_line_employees function."""

    def test_returns_employees_for_line(self, transactional_db):
        """get_line_employees returns all active employees on a line."""
        db = transactional_db
        _seed_client(db)
        emp1 = _seed_employee(db, employee_code="E1")
        emp2 = _seed_employee(db, employee_code="E2")
        line = _seed_line(db)

        create_assignment(db, _make_create(emp1.employee_id, line.line_id))
        create_assignment(db, _make_create(emp2.employee_id, line.line_id))

        results = get_line_employees(db, line.line_id, CLIENT_ID)
        assert len(results) == 2

    def test_tenant_isolation(self, transactional_db):
        """get_line_employees only returns assignments for the given client."""
        db = transactional_db
        _seed_client(db, CLIENT_ID)
        _seed_client(db, CLIENT_ID_B)

        emp_a = _seed_employee(db, client_id=CLIENT_ID, employee_code="EA")
        emp_b = _seed_employee(db, client_id=CLIENT_ID_B, employee_code="EB")
        line_a = _seed_line(db, client_id=CLIENT_ID, line_code="LA")
        line_b = _seed_line(db, client_id=CLIENT_ID_B, line_code="LB")

        create_assignment(db, _make_create(emp_a.employee_id, line_a.line_id, client_id=CLIENT_ID))
        create_assignment(db, _make_create(emp_b.employee_id, line_b.line_id, client_id=CLIENT_ID_B))

        results_a = get_line_employees(db, line_a.line_id, CLIENT_ID)
        results_b = get_line_employees(db, line_b.line_id, CLIENT_ID_B)

        assert len(results_a) == 1
        assert results_a[0].client_id == CLIENT_ID
        assert len(results_b) == 1
        assert results_b[0].client_id == CLIENT_ID_B


# ============================================================================
# TestUpdateAssignment
# ============================================================================
class TestUpdateAssignment:
    """Tests for update_assignment function."""

    def test_update_allocation(self, transactional_db):
        """Update allocation percentage."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        created = create_assignment(
            db,
            _make_create(emp.employee_id, line.line_id, allocation=Decimal("80.00")),
        )

        updated = update_assignment(
            db,
            created.assignment_id,
            EmployeeLineAssignmentUpdate(allocation_percentage=Decimal("50.00")),
        )

        assert updated is not None
        assert updated.allocation_percentage == Decimal("50.00")

    def test_update_allocation_exceeds_100_raises(self, transactional_db):
        """Updating allocation to exceed 100% raises ValueError."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("60.00")),
        )
        a2 = create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("40.00"),
                is_primary=False,
            ),
        )

        with pytest.raises(ValueError, match="Total allocation cannot exceed 100%"):
            update_assignment(
                db,
                a2.assignment_id,
                EmployeeLineAssignmentUpdate(allocation_percentage=Decimal("50.00")),
            )

    def test_update_is_primary(self, transactional_db):
        """Update is_primary flag."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        created = create_assignment(db, _make_create(emp.employee_id, line.line_id))

        updated = update_assignment(
            db,
            created.assignment_id,
            EmployeeLineAssignmentUpdate(is_primary=False),
        )

        assert updated.is_primary is False

    def test_update_end_date(self, transactional_db):
        """Update end_date."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        created = create_assignment(db, _make_create(emp.employee_id, line.line_id))
        future_date = TODAY + timedelta(days=30)

        updated = update_assignment(
            db,
            created.assignment_id,
            EmployeeLineAssignmentUpdate(end_date=future_date),
        )

        assert updated.end_date == future_date

    def test_update_nonexistent_returns_none(self, transactional_db):
        """Updating non-existent assignment returns None."""
        result = update_assignment(
            transactional_db,
            999999,
            EmployeeLineAssignmentUpdate(is_primary=False),
        )
        assert result is None


# ============================================================================
# TestEndAssignment
# ============================================================================
class TestEndAssignment:
    """Tests for end_assignment function."""

    def test_end_sets_today(self, transactional_db):
        """end_assignment defaults to today."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        created = create_assignment(db, _make_create(emp.employee_id, line.line_id))
        ended = end_assignment(db, created.assignment_id)

        assert ended is not None
        assert ended.end_date == TODAY

    def test_end_with_custom_date(self, transactional_db):
        """end_assignment with explicit end_date."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        created = create_assignment(db, _make_create(emp.employee_id, line.line_id))
        custom_date = TODAY + timedelta(days=7)
        ended = end_assignment(db, created.assignment_id, end_date_value=custom_date)

        assert ended.end_date == custom_date

    def test_end_nonexistent_returns_none(self, transactional_db):
        """Ending non-existent assignment returns None."""
        result = end_assignment(transactional_db, 999999)
        assert result is None

    def test_end_frees_slot_for_new_assignment(self, transactional_db):
        """After ending an assignment, a new one can be created."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")
        line3 = _seed_line(db, line_code="L3")

        a1 = create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("60.00")),
        )
        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("40.00"),
                is_primary=False,
            ),
        )

        # At this point, 2 active assignments, 100% allocated
        # End the first
        end_assignment(db, a1.assignment_id)

        # Now should be able to create a new one
        a3 = create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line3.line_id,
                allocation=Decimal("60.00"),
                is_primary=True,
                effective_date=TOMORROW,
            ),
        )
        assert a3.assignment_id is not None
        assert a3.allocation_percentage == Decimal("60.00")


# ============================================================================
# TestValidateAllocation
# ============================================================================
class TestValidateAllocation:
    """Tests for validate_allocation function."""

    def test_zero_with_no_assignments(self, transactional_db):
        """Returns 0 when employee has no assignments."""
        total = validate_allocation(transactional_db, 99999)
        assert total == Decimal("0.00")

    def test_returns_sum_of_active(self, transactional_db):
        """Returns sum of active assignment allocations."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("60.00")),
        )
        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("30.00"),
                is_primary=False,
            ),
        )

        total = validate_allocation(db, emp.employee_id)
        assert total == Decimal("90.00")

    def test_excludes_specified_assignment(self, transactional_db):
        """Excludes the given assignment_id from the total."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        a1 = create_assignment(
            db,
            _make_create(emp.employee_id, line1.line_id, allocation=Decimal("60.00")),
        )
        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line2.line_id,
                allocation=Decimal("30.00"),
                is_primary=False,
            ),
        )

        total_without_a1 = validate_allocation(
            db,
            emp.employee_id,
            exclude_assignment_id=a1.assignment_id,
        )
        assert total_without_a1 == Decimal("30.00")


# ============================================================================
# TestDateBoundedQueries
# ============================================================================
class TestDateBoundedQueries:
    """Test that date-bounded queries work correctly."""

    def test_past_end_date_is_inactive(self, transactional_db):
        """Assignment with end_date in the past is not considered active."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line.line_id,
                effective_date=TODAY - timedelta(days=30),
                end_date=YESTERDAY,
            ),
        )

        active = get_employee_lines(db, emp.employee_id)
        assert len(active) == 0

    def test_future_end_date_is_active(self, transactional_db):
        """Assignment with end_date in the future is still active."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        create_assignment(
            db,
            _make_create(
                emp.employee_id,
                line.line_id,
                effective_date=TODAY - timedelta(days=10),
                end_date=TOMORROW,
            ),
        )

        active = get_employee_lines(db, emp.employee_id)
        assert len(active) == 1

    def test_null_end_date_is_active(self, transactional_db):
        """Assignment with end_date=NULL is active."""
        db = transactional_db
        _seed_client(db)
        emp = _seed_employee(db)
        line = _seed_line(db)

        create_assignment(
            db,
            _make_create(emp.employee_id, line.line_id, end_date=None),
        )

        active = get_employee_lines(db, emp.employee_id)
        assert len(active) == 1


# ============================================================================
# TestMultiTenantIsolation
# ============================================================================
class TestMultiTenantIsolation:
    """Test multi-tenant data isolation."""

    def test_assignments_isolated_by_client(self, transactional_db):
        """Assignments from client A are not visible when filtering by client B."""
        db = transactional_db
        _seed_client(db, CLIENT_ID)
        _seed_client(db, CLIENT_ID_B)

        emp_a = _seed_employee(db, client_id=CLIENT_ID, employee_code="EMP-A")
        emp_b = _seed_employee(db, client_id=CLIENT_ID_B, employee_code="EMP-B")
        line_a = _seed_line(db, client_id=CLIENT_ID, line_code="LINE-A")
        line_b = _seed_line(db, client_id=CLIENT_ID_B, line_code="LINE-B")

        create_assignment(
            db,
            _make_create(emp_a.employee_id, line_a.line_id, client_id=CLIENT_ID),
        )
        create_assignment(
            db,
            _make_create(emp_b.employee_id, line_b.line_id, client_id=CLIENT_ID_B),
        )

        a_results = list_assignments(db, client_id=CLIENT_ID)
        b_results = list_assignments(db, client_id=CLIENT_ID_B)

        assert len(a_results) == 1
        assert len(b_results) == 1
        assert a_results[0].client_id == CLIENT_ID
        assert b_results[0].client_id == CLIENT_ID_B
