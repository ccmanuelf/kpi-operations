"""
Tests for actual CRUD module functions with real database sessions.
Migrated to use transactional_db instead of mocks.
Target: Cover crud/ directory to reach 85% overall coverage.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import HTTPException

from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# CLIENT CRUD TESTS
# =============================================================================
class TestClientCRUD:
    """Tests for crud/client.py using real DB"""

    def test_create_client_as_non_admin(self, transactional_db):
        """Test non-admin cannot create client"""
        from backend.crud.client import create_client

        operator = TestDataFactory.create_user(transactional_db, role="operator")
        transactional_db.commit()

        client_data = {"client_id": "NEW-CLIENT", "client_name": "Test"}

        with pytest.raises(HTTPException) as exc_info:
            create_client(transactional_db, client_data, operator)
        assert exc_info.value.status_code == 403

    def test_create_client_duplicate_id(self, transactional_db):
        """Test creating client with duplicate ID fails"""
        from backend.crud.client import create_client

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="EXISTING")
        transactional_db.commit()

        client_data = {"client_id": "EXISTING", "client_name": "Test"}

        with pytest.raises(HTTPException) as exc_info:
            create_client(transactional_db, client_data, admin)
        assert exc_info.value.status_code == 400

    def test_get_client_not_found(self, transactional_db):
        """Test getting non-existent client raises 404"""
        from backend.crud.client import get_client

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_client(transactional_db, "NON-EXISTENT", admin)
        assert exc_info.value.status_code == 404

    def test_get_clients_empty(self, transactional_db):
        """Test getting all clients when none exist"""
        from backend.crud.client import get_clients

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_clients(transactional_db, admin)
        assert isinstance(result, list)


# =============================================================================
# INTEGRATION WITH ACTUAL MODULES (Import tests)
# =============================================================================
class TestCRUDModuleImports:
    """Test that CRUD modules can be imported"""

    def test_import_production_crud(self):
        """Test production CRUD imports"""
        from backend.crud import production

        assert hasattr(production, "create_production_entry")
        assert hasattr(production, "get_production_entry")
        assert hasattr(production, "get_production_entries")
        assert hasattr(production, "update_production_entry")
        assert hasattr(production, "delete_production_entry")

    def test_import_client_crud(self):
        """Test client CRUD imports"""
        from backend.crud import client

        assert hasattr(client, "create_client")
        assert hasattr(client, "get_client")
        assert hasattr(client, "get_clients")
        assert hasattr(client, "update_client")
        assert hasattr(client, "delete_client")

    def test_import_employee_crud(self):
        """Test employee CRUD imports"""
        from backend.crud import employee

        assert hasattr(employee, "create_employee")
        assert hasattr(employee, "get_employee")

    def test_import_quality_crud(self):
        """Test quality CRUD imports"""
        from backend.crud import quality

        assert hasattr(quality, "create_quality_inspection")
        assert hasattr(quality, "get_quality_inspections")

    def test_import_downtime_crud(self):
        """Test downtime CRUD imports"""
        from backend.crud import downtime

        assert hasattr(downtime, "create_downtime_event")
        assert hasattr(downtime, "get_downtime_events")

    def test_import_hold_crud(self):
        """Test hold CRUD imports"""
        from backend.crud import hold

        assert hasattr(hold, "create_wip_hold")
        assert hasattr(hold, "get_wip_holds")

    def test_import_work_order_crud(self):
        """Test work order CRUD imports"""
        from backend.crud import work_order

        assert hasattr(work_order, "create_work_order")
        assert hasattr(work_order, "get_work_orders")

    def test_import_attendance_crud(self):
        """Test attendance CRUD imports"""
        from backend.crud import attendance

        assert hasattr(attendance, "create_attendance_record")
        assert hasattr(attendance, "get_attendance_records")

    def test_import_coverage_crud(self):
        """Test coverage CRUD imports"""
        from backend.crud import coverage

        assert hasattr(coverage, "create_shift_coverage")
        assert hasattr(coverage, "get_shift_coverages")

    def test_import_analytics_crud(self):
        """Test analytics CRUD imports"""
        from backend.crud import analytics

        assert hasattr(analytics, "get_kpi_time_series_data")
        assert hasattr(analytics, "get_shift_heatmap_data")

    def test_import_saved_filter_crud(self):
        """Test saved filter CRUD imports"""
        from backend.crud import saved_filter

        assert hasattr(saved_filter, "create_saved_filter")
        assert hasattr(saved_filter, "get_saved_filters")

    def test_import_preferences_crud(self):
        """Test preferences CRUD imports"""
        from backend.crud import preferences

        assert hasattr(preferences, "get_user_dashboard_preferences")
        assert hasattr(preferences, "save_user_dashboard_preferences")

    def test_import_job_crud(self):
        """Test job CRUD imports"""
        from backend.crud import job

        assert hasattr(job, "create_job")
        assert hasattr(job, "get_jobs")

    def test_import_defect_type_crud(self):
        """Test defect type CRUD imports"""
        from backend.crud import defect_type_catalog

        assert hasattr(defect_type_catalog, "get_defect_types_by_client")
        assert hasattr(defect_type_catalog, "create_defect_type")

    def test_import_floating_pool_crud(self):
        """Test floating pool CRUD imports"""
        from backend.crud import floating_pool

        assert hasattr(floating_pool, "create_floating_pool_entry")
        assert hasattr(floating_pool, "get_floating_pool_entries")


# =============================================================================
# BASIC FUNCTION EXECUTION TESTS (with real DB)
# =============================================================================
class TestCRUDBasicExecution:
    """Test CRUD functions can be called with real DB"""

    def test_get_clients(self, transactional_db):
        """Test getting all clients"""
        from backend.crud.client import get_clients

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="EXEC-CL1")
        transactional_db.commit()

        result = get_clients(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_client(self, transactional_db):
        """Test getting a client by ID"""
        from backend.crud.client import get_client

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="EXEC-CL2")
        transactional_db.commit()

        result = get_client(transactional_db, "EXEC-CL2", admin)
        assert result is not None
        assert result.client_id == "EXEC-CL2"

    def test_get_quality_inspections(self, transactional_db):
        """Test getting quality inspections"""
        from backend.crud.quality import get_quality_inspections

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_quality_inspections(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_downtime_events(self, transactional_db):
        """Test getting downtime events"""
        from backend.crud.downtime import get_downtime_events

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_wip_holds(self, transactional_db):
        """Test getting wip holds"""
        from backend.crud.hold import get_wip_holds

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_wip_holds(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_work_orders(self, transactional_db):
        """Test getting work orders"""
        from backend.crud.work_order import get_work_orders

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_work_orders(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_attendance_records(self, transactional_db):
        """Test getting attendance records"""
        from backend.crud.attendance import get_attendance_records

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_attendance_records(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_shift_coverages(self, transactional_db):
        """Test getting shift coverages"""
        from backend.crud.coverage import get_shift_coverages

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_shift_coverages(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_jobs(self, transactional_db):
        """Test getting jobs"""
        from backend.crud.job import get_jobs

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_jobs(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_defect_types_by_client(self, transactional_db):
        """Test getting defect types by client"""
        from backend.crud.defect_type_catalog import get_defect_types_by_client

        client = TestDataFactory.create_client(transactional_db, client_id="EXEC-DTC")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="EXEC-DTC")
        transactional_db.commit()

        result = get_defect_types_by_client(transactional_db, "EXEC-DTC", admin)
        assert isinstance(result, list)

    def test_get_saved_filters(self, transactional_db):
        """Test getting user's saved filters"""
        from backend.crud.saved_filter import get_saved_filters

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_saved_filters(transactional_db, admin.user_id)
        assert isinstance(result, list)

    def test_get_user_dashboard_preferences(self, transactional_db):
        """Test getting user dashboard preferences returns defaults when no prefs exist"""
        from backend.crud.preferences import get_user_dashboard_preferences

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_user_dashboard_preferences(transactional_db, admin.user_id)
        assert isinstance(result, tuple)
        assert result[0] is None  # No preference_id when using defaults

    def test_get_floating_pool_entries(self, transactional_db):
        """Test getting floating pool entries"""
        from backend.crud.floating_pool import get_floating_pool_entries

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_floating_pool_entries(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_production_entries(self, transactional_db):
        """Test getting production entries"""
        from backend.crud.production import get_production_entries

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_production_entries(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_production_entry_not_found(self, transactional_db):
        """Test getting a non-existent production entry"""
        from backend.crud.production import get_production_entry

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_production_entry(transactional_db, 99999, admin)
        assert exc_info.value.status_code == 404

    def test_get_employee_not_found(self, transactional_db):
        """Test getting a non-existent employee raises 404"""
        from backend.crud.employee import get_employee

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_employee(transactional_db, 99999, admin)
        assert exc_info.value.status_code == 404


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================
class TestCRUDEdgeCases:
    """Test CRUD edge cases and error handling"""

    def test_get_production_entries_empty(self, transactional_db):
        """Test getting production entries when none exist"""
        from backend.crud.production import get_production_entries

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_production_entries(transactional_db, admin)
        assert result == []

    def test_get_downtime_events_empty(self, transactional_db):
        """Test getting downtime events when none exist"""
        from backend.crud.downtime import get_downtime_events

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert result == []

    def test_get_wip_holds_empty(self, transactional_db):
        """Test getting wip holds when none exist"""
        from backend.crud.hold import get_wip_holds

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_wip_holds(transactional_db, admin)
        assert result == []
