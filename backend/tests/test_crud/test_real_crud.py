"""
Tests for actual CRUD module functions with mocked database sessions.
Target: Cover crud/ directory to reach 85% overall coverage.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session
from fastapi import HTTPException


# =============================================================================
# CLIENT CRUD TESTS
# =============================================================================
class TestClientCRUD:
    """Tests for crud/client.py"""

    def test_create_client_as_non_admin(self):
        """Test non-admin cannot create client"""
        from crud.client import create_client

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "operator"

        client_data = {"client_id": "NEW-CLIENT", "client_name": "Test"}

        with pytest.raises(HTTPException) as exc_info:
            create_client(mock_db, client_data, mock_user)

        assert exc_info.value.status_code == 403

    def test_create_client_duplicate_id(self):
        """Test creating client with duplicate ID fails"""
        from crud.client import create_client

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"

        # Mock existing client
        mock_existing = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing

        client_data = {"client_id": "EXISTING", "client_name": "Test"}

        with pytest.raises(HTTPException) as exc_info:
            create_client(mock_db, client_data, mock_user)

        assert exc_info.value.status_code == 400


# =============================================================================
# INTEGRATION WITH ACTUAL MODULES
# These tests import and partially execute actual module code
# =============================================================================
class TestCRUDModuleImports:
    """Test that CRUD modules can be imported"""

    def test_import_production_crud(self):
        """Test production CRUD imports"""
        from crud import production

        assert hasattr(production, "create_production_entry")
        assert hasattr(production, "get_production_entry")
        assert hasattr(production, "get_production_entries")
        assert hasattr(production, "update_production_entry")
        assert hasattr(production, "delete_production_entry")

    def test_import_client_crud(self):
        """Test client CRUD imports"""
        from crud import client

        assert hasattr(client, "create_client")
        assert hasattr(client, "get_client")
        assert hasattr(client, "get_clients")
        assert hasattr(client, "update_client")
        assert hasattr(client, "delete_client")

    def test_import_employee_crud(self):
        """Test employee CRUD imports"""
        from crud import employee

        assert hasattr(employee, "create_employee")
        assert hasattr(employee, "get_employee")

    def test_import_quality_crud(self):
        """Test quality CRUD imports"""
        from crud import quality

        assert hasattr(quality, "create_quality_inspection")
        assert hasattr(quality, "get_quality_inspections")

    def test_import_downtime_crud(self):
        """Test downtime CRUD imports"""
        from crud import downtime

        assert hasattr(downtime, "create_downtime_event")
        assert hasattr(downtime, "get_downtime_events")

    def test_import_hold_crud(self):
        """Test hold CRUD imports"""
        from crud import hold

        assert hasattr(hold, "create_wip_hold")
        assert hasattr(hold, "get_wip_holds")

    def test_import_work_order_crud(self):
        """Test work order CRUD imports"""
        from crud import work_order

        assert hasattr(work_order, "create_work_order")
        assert hasattr(work_order, "get_work_orders")

    def test_import_attendance_crud(self):
        """Test attendance CRUD imports"""
        from crud import attendance

        assert hasattr(attendance, "create_attendance_record")
        assert hasattr(attendance, "get_attendance_records")

    def test_import_coverage_crud(self):
        """Test coverage CRUD imports"""
        from crud import coverage

        assert hasattr(coverage, "create_shift_coverage")
        assert hasattr(coverage, "get_shift_coverages")

    def test_import_analytics_crud(self):
        """Test analytics CRUD imports"""
        from crud import analytics

        assert hasattr(analytics, "get_kpi_time_series_data")
        assert hasattr(analytics, "get_shift_heatmap_data")

    def test_import_saved_filter_crud(self):
        """Test saved filter CRUD imports"""
        from crud import saved_filter

        assert hasattr(saved_filter, "create_saved_filter")
        assert hasattr(saved_filter, "get_saved_filters")

    def test_import_preferences_crud(self):
        """Test preferences CRUD imports"""
        from crud import preferences

        assert hasattr(preferences, "get_user_dashboard_preferences")
        assert hasattr(preferences, "save_user_dashboard_preferences")

    def test_import_job_crud(self):
        """Test job CRUD imports"""
        from crud import job

        assert hasattr(job, "create_job")
        assert hasattr(job, "get_jobs")

    def test_import_defect_type_crud(self):
        """Test defect type CRUD imports"""
        from crud import defect_type_catalog

        assert hasattr(defect_type_catalog, "get_defect_types_by_client")
        assert hasattr(defect_type_catalog, "create_defect_type")

    def test_import_floating_pool_crud(self):
        """Test floating pool CRUD imports"""
        from crud import floating_pool

        assert hasattr(floating_pool, "create_floating_pool_entry")
        assert hasattr(floating_pool, "get_floating_pool_entries")


# =============================================================================
# BASIC FUNCTION EXECUTION TESTS
# =============================================================================
class TestCRUDBasicExecution:
    """Test CRUD functions can be called (with mocked DB)"""

    def test_get_clients(self):
        """Test getting all clients"""
        from crud.client import get_clients

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"

        mock_client1 = MagicMock()
        mock_client1.client_id = "CLIENT-001"
        # get_clients uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_client1]

        result = get_clients(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_client(self):
        """Test getting a client by ID"""
        from crud.client import get_client

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_client = MagicMock()
        mock_client.client_id = "CLIENT-001"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_client

        result = get_client(mock_db, "CLIENT-001", mock_user)
        assert result is not None

    def test_get_quality_inspections(self):
        """Test getting quality inspections"""
        from crud.quality import get_quality_inspections

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_insp = MagicMock()
        # get_quality_inspections uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_insp]

        result = get_quality_inspections(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_downtime_events(self):
        """Test getting downtime events"""
        from crud.downtime import get_downtime_events

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_event = MagicMock()
        # get_downtime_events uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_event]

        result = get_downtime_events(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_wip_holds(self):
        """Test getting wip holds"""
        from crud.hold import get_wip_holds

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_hold = MagicMock()
        mock_hold.is_resolved = False
        # get_wip_holds uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_hold]

        result = get_wip_holds(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_work_orders(self):
        """Test getting work orders"""
        from crud.work_order import get_work_orders

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_wo = MagicMock()
        # get_work_orders uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_wo]

        result = get_work_orders(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_attendance_records(self):
        """Test getting attendance records"""
        from crud.attendance import get_attendance_records

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_record = MagicMock()
        # get_attendance_records uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_record]

        result = get_attendance_records(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_shift_coverages(self):
        """Test getting shift coverages"""
        from crud.coverage import get_shift_coverages

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_entry = MagicMock()
        # get_shift_coverages uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_entry]

        result = get_shift_coverages(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_jobs(self):
        """Test getting jobs"""
        from crud.job import get_jobs

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_job = MagicMock()
        # get_jobs uses: query().filter().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_job]

        result = get_jobs(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_defect_types_by_client(self):
        """Test getting defect types by client"""
        from crud.defect_type_catalog import get_defect_types_by_client

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_type = MagicMock()
        mock_type.defect_type_id = 1
        mock_type.name = "Surface Defect"
        # get_defect_types_by_client uses complex query with filters
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_type]

        result = get_defect_types_by_client(mock_db, "CLIENT-001", mock_user)
        assert isinstance(result, list)

    def test_get_saved_filters(self):
        """Test getting user's saved filters"""
        from crud.saved_filter import get_saved_filters

        mock_db = MagicMock(spec=Session)
        user_id = "1"  # user_id is a string

        mock_filter = MagicMock()
        # get_saved_filters uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_filter]

        result = get_saved_filters(mock_db, user_id)
        assert isinstance(result, list)

    def test_get_user_dashboard_preferences(self):
        """Test getting user dashboard preferences returns defaults when no prefs exist"""
        from crud.preferences import get_user_dashboard_preferences

        mock_db = MagicMock(spec=Session)
        user_id = "1"

        # Return None to trigger default preferences path
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = get_user_dashboard_preferences(mock_db, user_id)
        # Returns tuple (preference_id, DashboardPreferences)
        assert isinstance(result, tuple)
        assert result[0] is None  # No preference_id when using defaults

    def test_get_floating_pool_entries(self):
        """Test getting floating pool entries"""
        from crud.floating_pool import get_floating_pool_entries

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_entry = MagicMock()
        # get_floating_pool_entries uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_entry]

        result = get_floating_pool_entries(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_production_entries(self):
        """Test getting production entries"""
        from crud.production import get_production_entries

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_entry = MagicMock()
        # get_production_entries uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_entry]

        result = get_production_entries(mock_db, mock_user)
        assert isinstance(result, list)

    def test_get_production_entry(self):
        """Test getting a production entry"""
        from crud.production import get_production_entry

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_entry = MagicMock()
        mock_entry.client_id = "CLIENT-001"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry

        result = get_production_entry(mock_db, 1, mock_user)
        assert result is not None

    def test_get_employee(self):
        """Test getting an employee"""
        from crud.employee import get_employee

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        mock_emp = MagicMock()
        mock_emp.client_id = "CLIENT-001"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_emp

        result = get_employee(mock_db, 1, mock_user)
        assert result is not None


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================
class TestCRUDEdgeCases:
    """Test CRUD edge cases and error handling"""

    def test_get_client_not_found(self):
        """Test getting non-existent client raises 404"""
        from crud.client import get_client

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = []

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_client(mock_db, "NON-EXISTENT", mock_user)
        assert exc_info.value.status_code == 404

    def test_get_clients_empty(self):
        """Test getting all clients when none exist"""
        from crud.client import get_clients

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"

        # get_clients uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = get_clients(mock_db, mock_user)
        assert result == []

    def test_get_production_entries_empty(self):
        """Test getting production entries when none exist"""
        from crud.production import get_production_entries

        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock()
        mock_user.role = "admin"
        mock_user.client_ids = ["CLIENT-001"]

        # get_production_entries uses: query().filter().order_by().offset().limit().all()
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = get_production_entries(mock_db, mock_user)
        assert result == []
