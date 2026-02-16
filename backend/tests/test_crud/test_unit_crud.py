"""
Comprehensive Unit Tests for CRUD Operations using Real Database.
Migrated to use transactional_db instead of mocks.
Target: 90% coverage for all CRUD modules
"""

import pytest
from datetime import date, timedelta
from fastapi import HTTPException

from backend.tests.fixtures.factories import TestDataFactory


class TestClientCRUD:
    """Tests for client CRUD operations"""

    def test_get_client_by_id(self, transactional_db):
        """Test getting a client by ID"""
        from backend.crud.client import get_client

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="UC-CL1", client_name="Test Client")
        transactional_db.commit()

        result = get_client(transactional_db, "UC-CL1", admin)
        assert result.client_id == "UC-CL1"

    def test_get_client_not_found(self, transactional_db):
        """Test getting a non-existent client raises HTTPException"""
        from backend.crud.client import get_client

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_client(transactional_db, "NONEXISTENT", admin)
        assert exc_info.value.status_code == 404

    def test_get_all_clients(self, transactional_db):
        """Test getting all clients"""
        from backend.crud.client import get_clients

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="UC-CL2")
        TestDataFactory.create_client(transactional_db, client_id="UC-CL3")
        transactional_db.commit()

        result = get_clients(transactional_db, admin)
        assert len(result) >= 2

    def test_create_client(self, transactional_db):
        """Test creating a new client"""
        from backend.crud.client import create_client

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        client_data = {"client_id": "UC-NEW", "client_name": "New Client", "client_type": "Hourly Rate"}
        result = create_client(transactional_db, client_data, admin)
        assert result is not None


class TestProductionCRUD:
    """Tests for production CRUD operations"""

    def test_get_production_entries(self, transactional_db):
        """Test getting production entries"""
        from backend.crud.production import get_production_entries

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_production_entries(
            transactional_db,
            current_user=admin,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
        )
        assert isinstance(result, list)

    def test_get_production_entries_with_data(self, transactional_db):
        """Test getting production entries with seeded data"""
        from backend.crud.production import get_production_entries

        client = TestDataFactory.create_client(transactional_db, client_id="UCPE-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="UCPE-CL")
        product = TestDataFactory.create_product(transactional_db, client_id="UCPE-CL")
        shift = TestDataFactory.create_shift(transactional_db, client_id="UCPE-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="UCPE-CL")
        transactional_db.flush()

        TestDataFactory.create_production_entry(
            transactional_db,
            client_id="UCPE-CL",
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=admin.user_id,
        )
        transactional_db.commit()

        result = get_production_entries(transactional_db, current_user=admin)
        assert len(result) >= 1

    def test_get_daily_summary(self, transactional_db):
        """Test getting daily production summary"""
        from backend.crud.production import get_daily_summary

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_daily_summary(transactional_db, admin, start_date=date.today(), end_date=date.today())
        assert result is not None


class TestQualityCRUD:
    """Tests for quality CRUD operations"""

    def test_get_quality_inspections(self, transactional_db):
        """Test getting quality inspections"""
        from backend.crud.quality import get_quality_inspections

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_quality_inspections(transactional_db, admin)
        assert isinstance(result, list)


class TestAttendanceCRUD:
    """Tests for attendance CRUD operations"""

    def test_get_attendance_records(self, transactional_db):
        """Test getting attendance records"""
        from backend.crud.attendance import get_attendance_records

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_attendance_records(transactional_db, admin)
        assert isinstance(result, list)


class TestDowntimeCRUD:
    """Tests for downtime CRUD operations"""

    def test_get_downtime_events(self, transactional_db):
        """Test getting downtime events"""
        from backend.crud.downtime import get_downtime_events

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert isinstance(result, list)


class TestHoldCRUD:
    """Tests for hold/WIP CRUD operations"""

    def test_get_wip_holds(self, transactional_db):
        """Test getting WIP hold entries"""
        from backend.crud.hold import get_wip_holds

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_wip_holds(transactional_db, admin)
        assert isinstance(result, list)


class TestEmployeeCRUD:
    """Tests for employee CRUD operations"""

    def test_get_employees(self, transactional_db):
        """Test getting employees"""
        from backend.crud.employee import get_employees

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_employees(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_employee_by_id(self, transactional_db):
        """Test getting employee by ID"""
        from backend.crud.employee import get_employee

        client = TestDataFactory.create_client(transactional_db, client_id="UCEBI-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="UCEBI-CL")
        emp = TestDataFactory.create_employee(transactional_db, client_id="UCEBI-CL")
        transactional_db.commit()

        result = get_employee(transactional_db, emp.employee_id, admin)
        assert result is not None
        assert result.employee_id == emp.employee_id


class TestJobCRUD:
    """Tests for job CRUD operations"""

    def test_get_jobs(self, transactional_db):
        """Test getting jobs"""
        from backend.crud.job import get_jobs

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_jobs(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_jobs_with_data(self, transactional_db):
        """Test getting jobs with seeded data"""
        from backend.crud.job import get_jobs

        client = TestDataFactory.create_client(transactional_db, client_id="UCJD-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="UCJD-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="UCJD-CL")
        transactional_db.flush()

        TestDataFactory.create_job(transactional_db, work_order_id=wo.work_order_id, client_id="UCJD-CL")
        transactional_db.commit()

        result = get_jobs(transactional_db, admin)
        assert len(result) >= 1


class TestWorkOrderCRUD:
    """Tests for work order CRUD operations"""

    def test_get_work_orders(self, transactional_db):
        """Test getting work orders"""
        from backend.crud.work_order import get_work_orders

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_work_orders(transactional_db, admin)
        assert isinstance(result, list)


class TestCoverageCRUD:
    """Tests for coverage CRUD operations"""

    def test_get_shift_coverages(self, transactional_db):
        """Test getting shift coverage entries"""
        from backend.crud.coverage import get_shift_coverages

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_shift_coverages(transactional_db, admin)
        assert isinstance(result, list)


class TestFloatingPoolCRUD:
    """Tests for floating pool CRUD operations"""

    def test_get_floating_pool_entries(self, transactional_db):
        """Test getting floating pool entries"""
        from backend.crud.floating_pool import get_floating_pool_entries

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_floating_pool_entries(transactional_db, admin)
        assert isinstance(result, list)


class TestDefectDetailCRUD:
    """Tests for defect detail CRUD operations"""

    def test_get_defect_details(self, transactional_db):
        """Test getting defect details"""
        from backend.crud.defect_detail import get_defect_details

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_defect_details(transactional_db, admin)
        assert isinstance(result, list)


class TestPartOpportunitiesCRUD:
    """Tests for part opportunities CRUD operations"""

    def test_get_part_opportunities(self, transactional_db):
        """Test getting part opportunities"""
        from backend.crud.part_opportunities import get_part_opportunities

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_part_opportunities(transactional_db, admin)
        assert isinstance(result, list)


class TestAnalyticsCRUD:
    """Tests for analytics CRUD operations"""

    def test_get_kpi_time_series_data(self, transactional_db):
        """Test getting KPI time series data"""
        from backend.crud.analytics import get_kpi_time_series_data

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="UCANA-CL")
        transactional_db.commit()

        result = get_kpi_time_series_data(
            transactional_db,
            client_id="UCANA-CL",
            kpi_type="efficiency",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            current_user=admin,
        )
        assert isinstance(result, list)


class TestCRUDPagination:
    """Test CRUD pagination functionality"""

    def test_pagination_skip(self, transactional_db):
        """Test pagination with skip parameter"""
        from backend.crud.client import get_clients

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        for i in range(5):
            TestDataFactory.create_client(transactional_db, client_id=f"PG-CL{i}")
        transactional_db.commit()

        result = get_clients(transactional_db, admin, skip=2, limit=2)
        assert isinstance(result, list)
        assert len(result) <= 2

    def test_pagination_limit(self, transactional_db):
        """Test pagination with limit parameter"""
        from backend.crud.client import get_clients

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        for i in range(10):
            TestDataFactory.create_client(transactional_db, client_id=f"PGL-CL{i}")
        transactional_db.commit()

        result = get_clients(transactional_db, admin, skip=0, limit=5)
        assert isinstance(result, list)
        assert len(result) <= 5


class TestCRUDFiltering:
    """Test CRUD filtering functionality"""

    def test_filter_production_by_date_range(self, transactional_db):
        """Test filtering production entries by date range"""
        from backend.crud.production import get_production_entries

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        start_date = date.today() - timedelta(days=30)
        end_date = date.today()

        result = get_production_entries(transactional_db, admin, start_date=start_date, end_date=end_date)
        assert isinstance(result, list)

    def test_filter_clients_list(self, transactional_db):
        """Test filtering clients list"""
        from backend.crud.client import get_clients

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="FILT-CL1")
        TestDataFactory.create_client(transactional_db, client_id="FILT-CL2")
        transactional_db.commit()

        result = get_clients(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) >= 2
