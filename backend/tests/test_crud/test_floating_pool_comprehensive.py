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

        with patch('backend.crud.floating_pool.verify_client_access'):
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

        with patch('backend.crud.floating_pool.verify_client_access'):
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
