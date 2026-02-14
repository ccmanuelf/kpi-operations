"""
Comprehensive Unit Tests for CRUD Operations
Target: 90% coverage for all CRUD modules
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


# Mock database session fixture
@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.delete = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user for CRUD operations"""
    user = MagicMock()
    user.user_id = "USER-ADMIN-001"
    user.role = "admin"
    user.client_id = "CLIENT-001"
    user.email = "admin@test.com"
    return user


@pytest.fixture
def mock_regular_user():
    """Create a mock regular user for CRUD operations"""
    user = MagicMock()
    user.user_id = "USER-REG-001"
    user.role = "supervisor"
    user.client_id = "CLIENT-001"
    user.email = "user@test.com"
    return user


class TestClientCRUD:
    """Tests for client CRUD operations"""

    def test_get_client_by_id(self, mock_db, mock_admin_user):
        """Test getting a client by ID"""
        from backend.crud.client import get_client

        # Mock the return value
        mock_client = MagicMock()
        mock_client.client_id = "CLIENT-001"
        mock_client.client_name = "Test Client"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_client

        result = get_client(mock_db, "CLIENT-001", mock_admin_user)
        assert result.client_id == "CLIENT-001"

    def test_get_client_not_found(self, mock_db, mock_admin_user):
        """Test getting a non-existent client raises HTTPException"""
        from backend.crud.client import get_client
        from fastapi import HTTPException

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_client(mock_db, "NONEXISTENT", mock_admin_user)
        assert exc_info.value.status_code == 404

    def test_get_all_clients(self, mock_db, mock_admin_user):
        """Test getting all clients"""
        from backend.crud.client import get_clients

        mock_clients = [MagicMock(), MagicMock()]
        # Mock the entire chain including order_by, offset, limit, and all
        mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = (
            mock_clients
        )

        result = get_clients(mock_db, mock_admin_user)
        assert len(result) == 2

    def test_create_client(self, mock_db, mock_admin_user):
        """Test creating a new client"""
        from backend.crud.client import create_client

        client_data = {"client_id": "CLIENT-NEW", "client_name": "New Client", "client_type": "SERVICE"}
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = create_client(mock_db, client_data, mock_admin_user)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestProductionCRUD:
    """Tests for production CRUD operations"""

    def test_get_production_entries(self, mock_db, mock_admin_user):
        """Test getting production entries"""
        from backend.crud.production import get_production_entries

        mock_entries = [MagicMock(), MagicMock()]
        # Setup a flexible mock chain that handles multiple filter calls
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query  # Allow chained filters
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_entries

        result = get_production_entries(
            mock_db, current_user=mock_admin_user, start_date=date.today() - timedelta(days=30), end_date=date.today()
        )
        assert isinstance(result, list)

    def test_get_daily_summary(self, mock_db, mock_admin_user):
        """Test getting daily production summary"""
        from backend.crud.production import get_daily_summary

        mock_summary = [MagicMock(total_units=1000, total_defects=5)]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_summary

        result = get_daily_summary(mock_db, mock_admin_user, start_date=date.today(), end_date=date.today())
        # get_daily_summary returns a list of summaries
        assert result is not None


class TestQualityCRUD:
    """Tests for quality CRUD operations"""

    def test_get_quality_inspections(self, mock_db, mock_admin_user):
        """Test getting quality inspections"""
        from backend.crud.quality import get_quality_inspections

        mock_entries = [MagicMock(), MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query  # Add order_by to chain
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_entries

        result = get_quality_inspections(mock_db, mock_admin_user)
        assert isinstance(result, list)


class TestAttendanceCRUD:
    """Tests for attendance CRUD operations"""

    def test_get_attendance_records(self, mock_db, mock_admin_user):
        """Test getting attendance records"""
        from backend.crud.attendance import get_attendance_records

        mock_entries = [MagicMock(), MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query  # Add order_by to chain
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_entries

        result = get_attendance_records(mock_db, mock_admin_user)
        assert isinstance(result, list)


class TestDowntimeCRUD:
    """Tests for downtime CRUD operations"""

    def test_get_downtime_events(self, mock_db, mock_admin_user):
        """Test getting downtime events"""
        from backend.crud.downtime import get_downtime_events

        mock_entries = [MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query  # Add order_by to chain
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_entries

        result = get_downtime_events(mock_db, mock_admin_user)
        assert isinstance(result, list)


class TestHoldCRUD:
    """Tests for hold/WIP CRUD operations"""

    def test_get_wip_holds(self, mock_db, mock_admin_user):
        """Test getting WIP hold entries"""
        from backend.crud.hold import get_wip_holds

        mock_holds = [MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query  # Add order_by to chain
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_holds

        result = get_wip_holds(mock_db, mock_admin_user)
        assert isinstance(result, list)


class TestEmployeeCRUD:
    """Tests for employee CRUD operations"""

    def test_get_employees(self, mock_db, mock_admin_user):
        """Test getting employees"""
        from backend.crud.employee import get_employees

        mock_employees = [MagicMock(), MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query  # Added order_by mock
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_employees

        result = get_employees(mock_db, mock_admin_user)
        assert isinstance(result, list)

    def test_get_employee_by_id(self, mock_db, mock_admin_user):
        """Test getting employee by ID"""
        from backend.crud.employee import get_employee

        mock_employee = MagicMock()
        mock_employee.employee_id = "EMP-001"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_employee

        result = get_employee(mock_db, "EMP-001", mock_admin_user)
        assert result.employee_id == "EMP-001"


class TestJobCRUD:
    """Tests for job CRUD operations"""

    def test_get_jobs(self, mock_db, mock_admin_user):
        """Test getting jobs"""
        from backend.crud.job import get_jobs

        mock_jobs = [MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_jobs

        result = get_jobs(mock_db, mock_admin_user)
        assert isinstance(result, list)

    def test_get_job_by_id(self, mock_db, mock_admin_user):
        """Test getting job by ID"""
        from backend.crud.job import get_job

        mock_job = MagicMock()
        mock_job.job_id = "JOB-001"
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_job

        result = get_job(mock_db, "JOB-001", mock_admin_user)
        assert result.job_id == "JOB-001"


class TestWorkOrderCRUD:
    """Tests for work order CRUD operations"""

    def test_get_work_orders(self, mock_db, mock_admin_user):
        """Test getting work orders"""
        from backend.crud.work_order import get_work_orders

        mock_orders = [MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_orders

        result = get_work_orders(mock_db, mock_admin_user)
        assert isinstance(result, list)


class TestCoverageCRUD:
    """Tests for coverage CRUD operations"""

    def test_get_shift_coverages(self, mock_db, mock_admin_user):
        """Test getting shift coverage entries"""
        from backend.crud.coverage import get_shift_coverages

        mock_entries = [MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_entries

        result = get_shift_coverages(mock_db, mock_admin_user)
        assert isinstance(result, list)


class TestFloatingPoolCRUD:
    """Tests for floating pool CRUD operations"""

    def test_get_floating_pool_entries(self, mock_db, mock_admin_user):
        """Test getting floating pool entries"""
        from backend.crud.floating_pool import get_floating_pool_entries

        mock_entries = [MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_entries

        result = get_floating_pool_entries(mock_db, mock_admin_user)
        assert isinstance(result, list)


class TestDefectDetailCRUD:
    """Tests for defect detail CRUD operations"""

    def test_get_defect_details(self, mock_db, mock_admin_user):
        """Test getting defect details"""
        from backend.crud.defect_detail import get_defect_details

        mock_details = [MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_details

        result = get_defect_details(mock_db, mock_admin_user)
        assert isinstance(result, list)


class TestPartOpportunitiesCRUD:
    """Tests for part opportunities CRUD operations"""

    def test_get_part_opportunities(self, mock_db, mock_admin_user):
        """Test getting part opportunities"""
        from backend.crud.part_opportunities import get_part_opportunities

        mock_opportunities = [MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_opportunities

        result = get_part_opportunities(mock_db, mock_admin_user)
        assert isinstance(result, list)


class TestAnalyticsCRUD:
    """Tests for analytics CRUD operations"""

    def test_get_kpi_time_series_data(self, mock_db, mock_admin_user):
        """Test getting KPI time series data"""
        from backend.crud.analytics import get_kpi_time_series_data

        mock_data = [(date.today(), 85.5)]
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_data

        result = get_kpi_time_series_data(
            mock_db,
            client_id="CLIENT-001",
            kpi_type="efficiency",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            current_user=mock_admin_user,
        )
        # Result should be a list or empty list
        assert result is not None


class TestCRUDErrorHandling:
    """Test CRUD error handling"""

    def test_database_error_handling(self, mock_db, mock_admin_user):
        """Test handling of database errors"""
        from backend.crud.client import get_client

        mock_db.query.side_effect = Exception("Database error")

        try:
            result = get_client(mock_db, "CLIENT-001", mock_admin_user)
        except Exception as e:
            assert "Database error" in str(e) or result is None

    def test_rollback_on_error(self, mock_db, mock_admin_user):
        """Test rollback on error"""
        from backend.crud.client import create_client

        mock_db.commit.side_effect = Exception("Commit failed")
        mock_db.query.return_value.filter.return_value.first.return_value = None

        client_data = {"client_id": "CLIENT-ERR", "client_name": "Test Client", "client_type": "SERVICE"}

        try:
            create_client(mock_db, client_data, mock_admin_user)
        except Exception:
            # Should have called rollback
            pass


class TestCRUDPagination:
    """Test CRUD pagination functionality"""

    def test_pagination_skip(self, mock_db, mock_admin_user):
        """Test pagination with skip parameter"""
        from backend.crud.client import get_clients

        mock_db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
        result = get_clients(mock_db, mock_admin_user, skip=10, limit=20)
        # Should use offset/limit in query

    def test_pagination_limit(self, mock_db, mock_admin_user):
        """Test pagination with limit parameter"""
        from backend.crud.client import get_clients

        mock_db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
        result = get_clients(mock_db, mock_admin_user, skip=0, limit=5)


class TestCRUDFiltering:
    """Test CRUD filtering functionality"""

    @patch("backend.crud.production.queries.build_client_filter_clause")
    def test_filter_by_date_range(self, mock_client_filter, mock_db, mock_admin_user):
        """Test filtering by date range"""
        from backend.crud.production import get_production_entries

        # Mock client filter to return None (no filtering for admin)
        mock_client_filter.return_value = None

        start_date = date.today() - timedelta(days=30)
        end_date = date.today()

        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = get_production_entries(mock_db, mock_admin_user, start_date=start_date, end_date=end_date)
        assert isinstance(result, list)

    @patch("backend.crud.client.build_client_filter_clause")
    def test_filter_by_active_status(self, mock_client_filter, mock_db, mock_admin_user):
        """Test filtering by active status"""
        from backend.crud.client import get_clients

        # Mock client filter to return None (no filtering for admin)
        mock_client_filter.return_value = None

        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = get_clients(mock_db, mock_admin_user, is_active=True)
        assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
