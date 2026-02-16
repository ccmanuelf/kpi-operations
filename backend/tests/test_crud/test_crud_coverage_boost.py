"""
Coverage Boost Tests for Low-Coverage CRUD Modules
Migrated to use real database (transactional_db) instead of mocks.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import HTTPException

from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# COVERAGE CRUD Tests
# =============================================================================
class TestCoverageCRUD:
    """Tests for crud/coverage.py using real DB"""

    def test_get_shift_coverages_empty(self, transactional_db):
        """Test get shift coverages returns empty list"""
        from backend.crud.coverage import get_shift_coverages

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_shift_coverages(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_shift_coverage_not_found(self, transactional_db):
        """Test get non-existent shift coverage raises 404"""
        from backend.crud.coverage import get_shift_coverage

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_shift_coverage(transactional_db, 99999, admin)
        assert exc_info.value.status_code == 404

    def test_get_shift_coverages_with_data(self, transactional_db):
        """Test get shift coverages with real data"""
        from backend.crud.coverage import get_shift_coverages

        client = TestDataFactory.create_client(transactional_db, client_id="COV-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="COV-CL")
        shift = TestDataFactory.create_shift(transactional_db, client_id="COV-CL")
        transactional_db.flush()

        TestDataFactory.create_shift_coverage(
            transactional_db, shift_id=shift.shift_id, client_id="COV-CL", entered_by=admin.user_id
        )
        transactional_db.commit()

        result = get_shift_coverages(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# DEFECT DETAIL CRUD Tests
# =============================================================================
class TestDefectDetailCRUD:
    """Tests for crud/defect_detail.py using real DB"""

    def test_get_defect_details_empty(self, transactional_db):
        """Test get defect details returns empty list"""
        from backend.crud.defect_detail import get_defect_details

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_defect_details(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_defect_details_with_data(self, transactional_db):
        """Test get defect details with real data"""
        from backend.crud.defect_detail import get_defect_details

        client = TestDataFactory.create_client(transactional_db, client_id="DD-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DD-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DD-CL")
        transactional_db.flush()

        qe = TestDataFactory.create_quality_entry(
            transactional_db, work_order_id=wo.work_order_id, client_id="DD-CL", inspector_id=admin.user_id
        )
        transactional_db.flush()

        TestDataFactory.create_defect_detail(transactional_db, quality_entry_id=qe.quality_entry_id, client_id="DD-CL")
        transactional_db.commit()

        result = get_defect_details(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# DEFECT TYPE CATALOG CRUD Tests
# =============================================================================
class TestDefectTypeCatalogCRUD:
    """Tests for crud/defect_type_catalog.py using real DB"""

    def test_get_defect_types_by_client_empty(self, transactional_db):
        """Test get defect types returns empty list for new client"""
        from backend.crud.defect_type_catalog import get_defect_types_by_client

        client = TestDataFactory.create_client(transactional_db, client_id="DTC-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DTC-CL")
        transactional_db.commit()

        result = get_defect_types_by_client(transactional_db, "DTC-CL", admin)
        assert isinstance(result, list)

    def test_get_defect_types_with_data(self, transactional_db):
        """Test get defect types with seeded catalog entries"""
        from backend.crud.defect_type_catalog import get_defect_types_by_client

        client = TestDataFactory.create_client(transactional_db, client_id="DTC2-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DTC2-CL")
        TestDataFactory.create_defect_type_catalog(transactional_db, client_id="DTC2-CL", defect_name="Thread Loose")
        transactional_db.commit()

        result = get_defect_types_by_client(transactional_db, "DTC2-CL", admin)
        assert len(result) >= 1


# =============================================================================
# EMPLOYEE CRUD Tests
# =============================================================================
class TestEmployeeCRUD:
    """Tests for crud/employee.py using real DB"""

    def test_get_employees_empty(self, transactional_db):
        """Test get employees returns empty list"""
        from backend.crud.employee import get_employees

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_employees(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_employee_not_found(self, transactional_db):
        """Test get non-existent employee raises 404"""
        from backend.crud.employee import get_employee

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_employee(transactional_db, 99999, admin)
        assert exc_info.value.status_code == 404

    def test_get_employees_with_data(self, transactional_db):
        """Test get employees with seeded data"""
        from backend.crud.employee import get_employees

        client = TestDataFactory.create_client(transactional_db, client_id="EMP-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="EMP-CL")
        TestDataFactory.create_employee(transactional_db, client_id="EMP-CL")
        transactional_db.commit()

        result = get_employees(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# JOB CRUD Tests
# =============================================================================
class TestJobCRUD:
    """Tests for crud/job.py using real DB"""

    def test_get_jobs_empty(self, transactional_db):
        """Test get jobs returns empty list"""
        from backend.crud.job import get_jobs

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_jobs(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_jobs_with_data(self, transactional_db):
        """Test get jobs with seeded data"""
        from backend.crud.job import get_jobs

        client = TestDataFactory.create_client(transactional_db, client_id="JOB-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="JOB-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="JOB-CL")
        transactional_db.flush()

        TestDataFactory.create_job(transactional_db, work_order_id=wo.work_order_id, client_id="JOB-CL")
        transactional_db.commit()

        result = get_jobs(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# PART OPPORTUNITIES CRUD Tests
# =============================================================================
class TestPartOpportunitiesCRUD:
    """Tests for crud/part_opportunities.py using real DB"""

    def test_get_part_opportunities_empty(self, transactional_db):
        """Test get part opportunities returns empty list"""
        from backend.crud.part_opportunities import get_part_opportunities

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_part_opportunities(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0


# =============================================================================
# PREFERENCES CRUD Tests
# =============================================================================
class TestPreferencesCRUD:
    """Tests for crud/preferences.py using real DB"""

    def test_get_user_preferences_returns_defaults(self, transactional_db):
        """Test get user preferences returns defaults when none set"""
        from backend.crud.preferences import get_user_dashboard_preferences

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_user_dashboard_preferences(transactional_db, admin.user_id)
        assert isinstance(result, tuple)
        assert result[0] is None  # No preference_id when using defaults


# =============================================================================
# SAVED FILTER CRUD Tests
# =============================================================================
class TestSavedFilterCRUD:
    """Tests for crud/saved_filter.py using real DB"""

    def test_get_saved_filters_empty(self, transactional_db):
        """Test get saved filters returns empty list"""
        from backend.crud.saved_filter import get_saved_filters

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_saved_filters(transactional_db, admin.user_id)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_saved_filters_with_data(self, transactional_db):
        """Test get saved filters with seeded data"""
        from backend.crud.saved_filter import get_saved_filters

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.flush()

        TestDataFactory.create_saved_filter(transactional_db, user_id=admin.user_id)
        transactional_db.commit()

        result = get_saved_filters(transactional_db, admin.user_id)
        assert len(result) >= 1


# =============================================================================
# QUALITY CRUD Tests
# =============================================================================
class TestQualityCRUD:
    """Tests for crud/quality.py using real DB"""

    def test_get_quality_entries_empty(self, transactional_db):
        """Test get quality entries returns empty list"""
        from backend.crud.quality import get_quality_inspections

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_quality_inspections(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0


# =============================================================================
# PRODUCTION CRUD Tests
# =============================================================================
class TestProductionCRUD:
    """Tests for crud/production.py using real DB"""

    def test_get_production_entries_empty(self, transactional_db):
        """Test get production entries returns empty list"""
        from backend.crud.production import get_production_entries

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_production_entries(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0


# =============================================================================
# DOWNTIME CRUD Tests
# =============================================================================
class TestDowntimeCRUD:
    """Tests for crud/downtime.py using real DB"""

    def test_get_downtime_entries_empty(self, transactional_db):
        """Test get downtime entries returns empty list"""
        from backend.crud.downtime import get_downtime_events

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0


# =============================================================================
# ATTENDANCE CRUD Tests
# =============================================================================
class TestAttendanceCRUD:
    """Tests for crud/attendance.py using real DB"""

    def test_get_attendance_entries_empty(self, transactional_db):
        """Test get attendance entries returns empty list"""
        from backend.crud.attendance import get_attendance_records

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_attendance_records(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0


# =============================================================================
# ANALYTICS CRUD Tests
# =============================================================================
class TestAnalyticsCRUD:
    """Tests for crud/analytics.py using real DB"""

    def test_get_analytics_time_series_empty(self, transactional_db):
        """Test get analytics time series data returns empty list"""
        from backend.crud.analytics import get_kpi_time_series_data

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="ANA-CL")
        transactional_db.commit()

        result = get_kpi_time_series_data(
            transactional_db,
            client_id="ANA-CL",
            kpi_type="efficiency",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            current_user=admin,
        )
        assert isinstance(result, list)


# =============================================================================
# CLIENT CRUD Tests
# =============================================================================
class TestClientCRUD:
    """Tests for crud/client.py using real DB"""

    def test_get_clients_empty(self, transactional_db):
        """Test get clients returns empty list"""
        from backend.crud.client import get_clients

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_clients(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_client_not_found(self, transactional_db):
        """Test get non-existent client raises 404"""
        from backend.crud.client import get_client

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_client(transactional_db, "NONEXISTENT", admin)
        assert exc_info.value.status_code == 404
