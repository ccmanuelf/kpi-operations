"""
Comprehensive Tests for Floating Pool CRUD Operations
Target: Increase floating_pool.py coverage from 28% to 60%+
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from fastapi import HTTPException


class TestCreateFloatingPoolEntry:
    """Tests for create_floating_pool_entry function"""

    def test_create_entry_permission_denied(self, db_session, admin_user):
        """Test create entry without supervisor/admin role"""
        from backend.crud.floating_pool import create_floating_pool_entry

        # Set user to operator role
        admin_user.role = "operator"

        pool_data = {"employee_id": 1, "notes": "Test entry"}

        with pytest.raises(HTTPException) as exc_info:
            create_floating_pool_entry(db_session, pool_data, admin_user)
        assert exc_info.value.status_code == 403

    def test_create_entry_employee_not_found(self, db_session, admin_user):
        """Test create entry with non-existent employee"""
        from backend.crud.floating_pool import create_floating_pool_entry

        admin_user.role = "admin"
        pool_data = {"employee_id": 99999, "notes": "Test entry"}

        with pytest.raises(HTTPException) as exc_info:
            create_floating_pool_entry(db_session, pool_data, admin_user)
        assert exc_info.value.status_code == 404


class TestGetFloatingPoolEntry:
    """Tests for get_floating_pool_entry function"""

    def test_get_entry_not_found(self, db_session, admin_user):
        """Test get entry with non-existent ID"""
        from backend.crud.floating_pool import get_floating_pool_entry

        with pytest.raises(HTTPException) as exc_info:
            get_floating_pool_entry(db_session, 99999, admin_user)
        assert exc_info.value.status_code == 404


class TestGetFloatingPoolEntries:
    """Tests for get_floating_pool_entries function"""

    def test_get_entries_basic(self, db_session, admin_user):
        """Test get entries with no filters"""
        from backend.crud.floating_pool import get_floating_pool_entries

        result = get_floating_pool_entries(db_session, admin_user)
        assert isinstance(result, list)

    def test_get_entries_by_employee(self, db_session, admin_user):
        """Test get entries filtered by employee"""
        from backend.crud.floating_pool import get_floating_pool_entries

        result = get_floating_pool_entries(
            db_session,
            admin_user,
            employee_id=1
        )
        assert isinstance(result, list)

    def test_get_entries_available_only(self, db_session, admin_user):
        """Test get only available entries"""
        from backend.crud.floating_pool import get_floating_pool_entries

        result = get_floating_pool_entries(
            db_session,
            admin_user,
            available_only=True
        )
        assert isinstance(result, list)


class TestUpdateFloatingPoolEntry:
    """Tests for update_floating_pool_entry function"""

    def test_update_entry_permission_denied(self, db_session, admin_user):
        """Test update entry without supervisor/admin role"""
        from backend.crud.floating_pool import update_floating_pool_entry

        admin_user.role = "operator"

        with pytest.raises(HTTPException) as exc_info:
            update_floating_pool_entry(db_session, 1, {"notes": "Updated"}, admin_user)
        assert exc_info.value.status_code == 403

    def test_update_entry_not_found(self, db_session, admin_user):
        """Test update non-existent entry"""
        from backend.crud.floating_pool import update_floating_pool_entry

        admin_user.role = "admin"

        with pytest.raises(HTTPException) as exc_info:
            update_floating_pool_entry(db_session, 99999, {"notes": "Updated"}, admin_user)
        assert exc_info.value.status_code == 404


class TestDeleteFloatingPoolEntry:
    """Tests for delete_floating_pool_entry function"""

    def test_delete_entry_permission_denied(self, db_session, admin_user):
        """Test delete entry without supervisor/admin role"""
        from backend.crud.floating_pool import delete_floating_pool_entry

        admin_user.role = "operator"

        with pytest.raises(HTTPException) as exc_info:
            delete_floating_pool_entry(db_session, 1, admin_user)
        assert exc_info.value.status_code == 403

    def test_delete_entry_not_found(self, db_session, admin_user):
        """Test delete non-existent entry"""
        from backend.crud.floating_pool import delete_floating_pool_entry

        admin_user.role = "admin"

        with pytest.raises(HTTPException) as exc_info:
            delete_floating_pool_entry(db_session, 99999, admin_user)
        assert exc_info.value.status_code == 404


class TestAssignFloatingPoolToClient:
    """Tests for assign_floating_pool_to_client function"""

    def test_assign_permission_denied(self, db_session, admin_user):
        """Test assign without supervisor/admin role"""
        from backend.crud.floating_pool import assign_floating_pool_to_client

        admin_user.role = "operator"

        with pytest.raises(HTTPException) as exc_info:
            assign_floating_pool_to_client(
                db_session, 1, "CLIENT-1", None, None, admin_user
            )
        assert exc_info.value.status_code == 403

    def test_assign_employee_not_found(self, db_session, admin_user):
        """Test assign non-existent employee"""
        from backend.crud.floating_pool import assign_floating_pool_to_client

        admin_user.role = "admin"

        with patch('backend.crud.floating_pool.assignments.verify_client_access'):
            with pytest.raises(HTTPException) as exc_info:
                assign_floating_pool_to_client(
                    db_session, 99999, "CLIENT-1", None, None, admin_user
                )
            assert exc_info.value.status_code == 404


class TestUnassignFloatingPoolFromClient:
    """Tests for unassign_floating_pool_from_client function"""

    def test_unassign_permission_denied(self, db_session, admin_user):
        """Test unassign without supervisor/admin role"""
        from backend.crud.floating_pool import unassign_floating_pool_from_client

        admin_user.role = "operator"

        with pytest.raises(HTTPException) as exc_info:
            unassign_floating_pool_from_client(db_session, 1, admin_user)
        assert exc_info.value.status_code == 403

    def test_unassign_not_found(self, db_session, admin_user):
        """Test unassign non-existent entry"""
        from backend.crud.floating_pool import unassign_floating_pool_from_client

        admin_user.role = "admin"

        with pytest.raises(HTTPException) as exc_info:
            unassign_floating_pool_from_client(db_session, 99999, admin_user)
        assert exc_info.value.status_code == 404


class TestDoubleAssignmentPrevention:
    """Tests for double-assignment prevention (Phase 6.3)"""

    def test_double_assignment_blocked_indefinite(self, db_session, admin_user):
        """Test that double-assignment is blocked for indefinite assignments"""
        from backend.crud.floating_pool import assign_floating_pool_to_client
        from backend.schemas.floating_pool import FloatingPool
        from backend.schemas.employee import Employee

        admin_user.role = "admin"

        # Create mock employee in floating pool
        mock_employee = MagicMock(spec=Employee)
        mock_employee.employee_id = 12345
        mock_employee.is_floating_pool = True

        # Create existing assignment
        mock_existing = MagicMock(spec=FloatingPool)
        mock_existing.employee_id = 12345
        mock_existing.current_assignment = "CLIENT-EXISTING"
        mock_existing.available_from = None
        mock_existing.available_to = None

        with patch('backend.crud.floating_pool.assignments.verify_client_access'):
            with patch.object(db_session, 'query') as mock_query:
                # First query returns employee, second returns existing assignment
                mock_query.return_value.filter.return_value.first.side_effect = [
                    mock_employee,
                    mock_existing
                ]

                with pytest.raises(HTTPException) as exc_info:
                    assign_floating_pool_to_client(
                        db_session, 12345, "CLIENT-NEW", None, None, admin_user
                    )

                assert exc_info.value.status_code == 409
                assert "already assigned" in exc_info.value.detail

    def test_double_assignment_blocked_overlapping_dates(self, db_session, admin_user):
        """Test that double-assignment is blocked for overlapping date ranges"""
        from backend.crud.floating_pool import assign_floating_pool_to_client
        from backend.schemas.floating_pool import FloatingPool
        from backend.schemas.employee import Employee

        admin_user.role = "admin"

        # Create mock employee in floating pool
        mock_employee = MagicMock(spec=Employee)
        mock_employee.employee_id = 12346
        mock_employee.is_floating_pool = True

        # Create existing assignment with date range
        mock_existing = MagicMock(spec=FloatingPool)
        mock_existing.employee_id = 12346
        mock_existing.current_assignment = "CLIENT-EXISTING"
        mock_existing.available_from = datetime(2026, 1, 15)
        mock_existing.available_to = datetime(2026, 1, 25)

        with patch('backend.crud.floating_pool.assignments.verify_client_access'):
            with patch.object(db_session, 'query') as mock_query:
                mock_query.return_value.filter.return_value.first.side_effect = [
                    mock_employee,
                    mock_existing
                ]

                # Try to assign with overlapping dates
                with pytest.raises(HTTPException) as exc_info:
                    assign_floating_pool_to_client(
                        db_session,
                        12346,
                        "CLIENT-NEW",
                        datetime(2026, 1, 20),  # Overlaps with existing
                        datetime(2026, 1, 30),
                        admin_user
                    )

                assert exc_info.value.status_code == 409
                assert "already assigned" in exc_info.value.detail
                assert "CLIENT-EXISTING" in exc_info.value.detail

    def test_assignment_allowed_non_overlapping_dates(self, db_session, admin_user):
        """Test that assignment is allowed for non-overlapping date ranges"""
        from backend.crud.floating_pool import is_employee_available_for_assignment
        from backend.schemas.floating_pool import FloatingPool

        # Create mock existing assignment with date range
        mock_existing = MagicMock(spec=FloatingPool)
        mock_existing.employee_id = 12347
        mock_existing.current_assignment = "CLIENT-EXISTING"
        mock_existing.available_from = datetime(2026, 1, 1)
        mock_existing.available_to = datetime(2026, 1, 10)

        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = mock_existing

            # Check availability for non-overlapping dates
            result = is_employee_available_for_assignment(
                db_session,
                12347,
                proposed_start=datetime(2026, 1, 15),  # After existing ends
                proposed_end=datetime(2026, 1, 25)
            )

            assert result["is_available"] == True
            assert "no overlap" in result["message"].lower()

    def test_availability_check_returns_conflict_details(self, db_session):
        """Test availability check returns proper conflict information"""
        from backend.crud.floating_pool import is_employee_available_for_assignment
        from backend.schemas.floating_pool import FloatingPool

        # Create mock existing assignment
        mock_existing = MagicMock(spec=FloatingPool)
        mock_existing.employee_id = 12348
        mock_existing.current_assignment = "CLIENT-A"
        mock_existing.available_from = datetime(2026, 1, 10)
        mock_existing.available_to = datetime(2026, 1, 20)

        with patch.object(db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = mock_existing

            result = is_employee_available_for_assignment(
                db_session,
                12348,
                proposed_start=datetime(2026, 1, 15),  # Overlapping
                proposed_end=datetime(2026, 1, 25)
            )

            assert result["is_available"] == False
            assert result["current_assignment"] == "CLIENT-A"
            assert result["conflict_dates"] is not None
            assert "existing_start" in result["conflict_dates"]
            assert "existing_end" in result["conflict_dates"]


class TestGetAvailableFloatingPoolEmployees:
    """Tests for get_available_floating_pool_employees function"""

    def test_get_available_employees(self, db_session, admin_user):
        """Test get available floating pool employees"""
        from backend.crud.floating_pool import get_available_floating_pool_employees

        result = get_available_floating_pool_employees(db_session, admin_user)
        assert isinstance(result, list)

    def test_get_available_employees_as_of_date(self, db_session, admin_user):
        """Test get available employees as of specific date"""
        from backend.crud.floating_pool import get_available_floating_pool_employees

        result = get_available_floating_pool_employees(
            db_session,
            admin_user,
            as_of_date=datetime.utcnow()
        )
        assert isinstance(result, list)


class TestGetFloatingPoolAssignmentsByClient:
    """Tests for get_floating_pool_assignments_by_client function"""

    def test_get_assignments_by_client(self, db_session, admin_user):
        """Test get assignments for client"""
        from backend.crud.floating_pool import get_floating_pool_assignments_by_client

        with patch('backend.crud.floating_pool.assignments.verify_client_access'):
            result = get_floating_pool_assignments_by_client(
                db_session,
                "TEST-CLIENT",
                admin_user
            )
            assert isinstance(result, list)


class TestIsEmployeeAvailableForAssignment:
    """Tests for is_employee_available_for_assignment function"""

    def test_availability_check_no_assignment(self, db_session):
        """Test availability check for unassigned employee"""
        from backend.crud.floating_pool import is_employee_available_for_assignment

        result = is_employee_available_for_assignment(db_session, 99999)
        assert result["is_available"] == True
        assert result["current_assignment"] is None

    def test_availability_check_with_dates(self, db_session):
        """Test availability check with proposed dates"""
        from backend.crud.floating_pool import is_employee_available_for_assignment

        result = is_employee_available_for_assignment(
            db_session,
            99999,
            proposed_start=datetime.utcnow(),
            proposed_end=datetime.utcnow() + timedelta(days=7)
        )
        assert "is_available" in result


class TestGetFloatingPoolSummary:
    """Tests for get_floating_pool_summary function"""

    def test_get_summary(self, db_session, admin_user):
        """Test get floating pool summary"""
        from backend.crud.floating_pool import get_floating_pool_summary

        result = get_floating_pool_summary(db_session, admin_user)
        assert "total_floating_pool_employees" in result
        assert "currently_available" in result
        assert "currently_assigned" in result
        assert "available_employees" in result
