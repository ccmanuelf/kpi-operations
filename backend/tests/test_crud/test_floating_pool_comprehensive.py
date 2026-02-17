"""
Comprehensive Tests for Floating Pool CRUD Operations
Migrated to use real database (transactional_db) instead of mocks.
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from backend.tests.fixtures.factories import TestDataFactory


class TestCreateFloatingPoolEntry:
    """Tests for create_floating_pool_entry function"""

    def test_create_entry_permission_denied(self, transactional_db):
        """Test create entry without supervisor/admin role"""
        from backend.crud.floating_pool import create_floating_pool_entry

        client = TestDataFactory.create_client(transactional_db, client_id="FP-CL")
        operator = TestDataFactory.create_user(transactional_db, role="operator", client_id="FP-CL")
        transactional_db.commit()

        pool_data = {"employee_id": 1, "notes": "Test entry"}

        with pytest.raises(HTTPException) as exc_info:
            create_floating_pool_entry(transactional_db, pool_data, operator)
        assert exc_info.value.status_code == 403

    def test_create_entry_employee_not_found(self, transactional_db):
        """Test create entry with non-existent employee"""
        from backend.crud.floating_pool import create_floating_pool_entry

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        pool_data = {"employee_id": 99999, "notes": "Test entry"}

        with pytest.raises(HTTPException) as exc_info:
            create_floating_pool_entry(transactional_db, pool_data, admin)
        assert exc_info.value.status_code == 404


class TestGetFloatingPoolEntry:
    """Tests for get_floating_pool_entry function"""

    def test_get_entry_not_found(self, transactional_db):
        """Test get entry with non-existent ID"""
        from backend.crud.floating_pool import get_floating_pool_entry

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_floating_pool_entry(transactional_db, 99999, admin)
        assert exc_info.value.status_code == 404


class TestGetFloatingPoolEntries:
    """Tests for get_floating_pool_entries function"""

    def test_get_entries_basic(self, transactional_db):
        """Test get entries with no filters"""
        from backend.crud.floating_pool import get_floating_pool_entries

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_floating_pool_entries(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_entries_with_data(self, transactional_db):
        """Test get entries with seeded floating pool assignment"""
        from backend.crud.floating_pool import get_floating_pool_entries

        client = TestDataFactory.create_client(transactional_db, client_id="FPE-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="FPE-CL")
        emp = TestDataFactory.create_employee(transactional_db, client_id="FPE-CL", is_floating_pool=True)
        transactional_db.flush()

        TestDataFactory.create_floating_pool_assignment(
            transactional_db,
            employee_id=emp.employee_id,
            client_id="FPE-CL",
        )
        transactional_db.commit()

        result = get_floating_pool_entries(transactional_db, admin)
        assert isinstance(result, list)


class TestUpdateFloatingPoolEntry:
    """Tests for update_floating_pool_entry function"""

    def test_update_entry_permission_denied(self, transactional_db):
        """Test update entry without supervisor/admin role"""
        from backend.crud.floating_pool import update_floating_pool_entry

        client = TestDataFactory.create_client(transactional_db, client_id="FPU-CL")
        operator = TestDataFactory.create_user(transactional_db, role="operator", client_id="FPU-CL")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            update_floating_pool_entry(transactional_db, 1, {"notes": "Updated"}, operator)
        assert exc_info.value.status_code == 403

    def test_update_entry_not_found(self, transactional_db):
        """Test update non-existent entry"""
        from backend.crud.floating_pool import update_floating_pool_entry

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            update_floating_pool_entry(transactional_db, 99999, {"notes": "Updated"}, admin)
        assert exc_info.value.status_code == 404


class TestDeleteFloatingPoolEntry:
    """Tests for delete_floating_pool_entry function"""

    def test_delete_entry_permission_denied(self, transactional_db):
        """Test delete entry without supervisor/admin role"""
        from backend.crud.floating_pool import delete_floating_pool_entry

        client = TestDataFactory.create_client(transactional_db, client_id="FPD-CL")
        operator = TestDataFactory.create_user(transactional_db, role="operator", client_id="FPD-CL")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            delete_floating_pool_entry(transactional_db, 1, operator)
        assert exc_info.value.status_code == 403

    def test_delete_entry_not_found(self, transactional_db):
        """Test delete non-existent entry"""
        from backend.crud.floating_pool import delete_floating_pool_entry

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            delete_floating_pool_entry(transactional_db, 99999, admin)
        assert exc_info.value.status_code == 404


class TestAssignFloatingPoolToClient:
    """Tests for assign_floating_pool_to_client function"""

    def test_assign_permission_denied(self, transactional_db):
        """Test assign without supervisor/admin role"""
        from backend.crud.floating_pool import assign_floating_pool_to_client

        client = TestDataFactory.create_client(transactional_db, client_id="FPA-CL")
        operator = TestDataFactory.create_user(transactional_db, role="operator", client_id="FPA-CL")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            assign_floating_pool_to_client(transactional_db, 1, "FPA-CL", None, None, operator)
        assert exc_info.value.status_code == 403

    def test_assign_employee_not_found(self, transactional_db):
        """Test assign non-existent employee"""
        from backend.crud.floating_pool import assign_floating_pool_to_client

        client = TestDataFactory.create_client(transactional_db, client_id="FPANF-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="FPANF-CL")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            assign_floating_pool_to_client(transactional_db, 99999, "FPANF-CL", None, None, admin)
        assert exc_info.value.status_code == 404


class TestUnassignFloatingPoolFromClient:
    """Tests for unassign_floating_pool_from_client function"""

    def test_unassign_permission_denied(self, transactional_db):
        """Test unassign without supervisor/admin role"""
        from backend.crud.floating_pool import unassign_floating_pool_from_client

        client = TestDataFactory.create_client(transactional_db, client_id="FPUA-CL")
        operator = TestDataFactory.create_user(transactional_db, role="operator", client_id="FPUA-CL")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            unassign_floating_pool_from_client(transactional_db, 1, operator)
        assert exc_info.value.status_code == 403

    def test_unassign_not_found(self, transactional_db):
        """Test unassign non-existent entry"""
        from backend.crud.floating_pool import unassign_floating_pool_from_client

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            unassign_floating_pool_from_client(transactional_db, 99999, admin)
        assert exc_info.value.status_code == 404


class TestIsEmployeeAvailableForAssignment:
    """Tests for is_employee_available_for_assignment function"""

    def test_availability_check_no_assignment(self, transactional_db):
        """Test availability check for unassigned employee"""
        from backend.crud.floating_pool import is_employee_available_for_assignment

        result = is_employee_available_for_assignment(transactional_db, 99999)
        assert result["is_available"] is True
        assert result["current_assignment"] is None

    def test_availability_check_with_dates(self, transactional_db):
        """Test availability check with proposed dates"""
        from backend.crud.floating_pool import is_employee_available_for_assignment

        result = is_employee_available_for_assignment(
            transactional_db, 99999, proposed_start=datetime.now(tz=timezone.utc), proposed_end=datetime.now(tz=timezone.utc) + timedelta(days=7)
        )
        assert "is_available" in result

    def test_availability_check_assigned_employee(self, transactional_db):
        """Test availability check for assigned employee"""
        from backend.crud.floating_pool import is_employee_available_for_assignment

        client = TestDataFactory.create_client(transactional_db, client_id="AVAIL-CL")
        emp = TestDataFactory.create_employee(transactional_db, client_id="AVAIL-CL", is_floating_pool=True)
        transactional_db.flush()

        TestDataFactory.create_floating_pool_assignment(
            transactional_db,
            employee_id=emp.employee_id,
            client_id="AVAIL-CL",
            current_assignment="AVAIL-CL",
        )
        transactional_db.commit()

        result = is_employee_available_for_assignment(transactional_db, emp.employee_id)
        assert "is_available" in result


class TestGetAvailableFloatingPoolEmployees:
    """Tests for get_available_floating_pool_employees function"""

    def test_get_available_employees(self, transactional_db):
        """Test get available floating pool employees"""
        from backend.crud.floating_pool import get_available_floating_pool_employees

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_available_floating_pool_employees(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_available_employees_as_of_date(self, transactional_db):
        """Test get available employees as of specific date"""
        from backend.crud.floating_pool import get_available_floating_pool_employees

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_available_floating_pool_employees(transactional_db, admin, as_of_date=datetime.now(tz=timezone.utc))
        assert isinstance(result, list)


class TestGetFloatingPoolAssignmentsByClient:
    """Tests for get_floating_pool_assignments_by_client function"""

    def test_get_assignments_by_client(self, transactional_db):
        """Test get assignments for client"""
        from backend.crud.floating_pool import get_floating_pool_assignments_by_client

        client = TestDataFactory.create_client(transactional_db, client_id="FPABC-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="FPABC-CL")
        transactional_db.commit()

        result = get_floating_pool_assignments_by_client(transactional_db, "FPABC-CL", admin)
        assert isinstance(result, list)


class TestGetFloatingPoolSummary:
    """Tests for get_floating_pool_summary function"""

    def test_get_summary(self, transactional_db):
        """Test get floating pool summary"""
        from backend.crud.floating_pool import get_floating_pool_summary

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_floating_pool_summary(transactional_db, admin)
        assert "total_floating_pool_employees" in result
        assert "currently_available" in result
        assert "currently_assigned" in result
        assert "available_employees" in result
