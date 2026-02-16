"""
Integration Tests for CRUD Modules
These tests validate CRUD operations using real database sessions (transactional_db fixture).
Migrated from mock-based tests to real DB tests per project policy.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal

from backend.tests.fixtures.factories import TestDataFactory
from backend.crud.client import get_clients, get_client, create_client, update_client, delete_client
from backend.crud.quality import get_quality_inspections
from backend.crud.downtime import get_downtime_events
from backend.crud.attendance import get_attendance_records
from backend.crud.coverage import get_shift_coverages
from backend.crud.job import get_jobs
from fastapi import HTTPException


# =============================================================================
# CLIENT CRUD INTEGRATION
# =============================================================================
class TestClientCRUDIntegration:
    """Integration tests for client CRUD operations using real DB"""

    def test_client_list_returns_created_clients(self, transactional_db):
        """Test client listing returns real clients from DB"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        c1 = TestDataFactory.create_client(transactional_db, client_id="INT-A", client_name="Alpha Client")
        c2 = TestDataFactory.create_client(transactional_db, client_id="INT-B", client_name="Beta Client")
        transactional_db.commit()

        result = get_clients(transactional_db, admin)
        client_ids = [c.client_id for c in result]
        assert "INT-A" in client_ids
        assert "INT-B" in client_ids

    def test_client_get_by_id(self, transactional_db):
        """Test getting a specific client by ID"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="GET-TEST", client_name="Get Test Client")
        transactional_db.commit()

        result = get_client(transactional_db, "GET-TEST", admin)
        assert result.client_id == "GET-TEST"
        assert result.client_name == "Get Test Client"

    def test_client_get_not_found_raises_404(self, transactional_db):
        """Test getting non-existent client raises 404"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_client(transactional_db, "NONEXISTENT", admin)
        assert exc_info.value.status_code == 404

    def test_client_create_by_admin(self, transactional_db):
        """Test admin can create clients"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        data = {"client_id": "NEW-CL", "client_name": "New Client", "client_type": "Hourly Rate", "is_active": 1}
        result = create_client(transactional_db, data, admin)
        assert result.client_id == "NEW-CL"
        assert result.client_name == "New Client"

    def test_client_create_by_non_admin_raises_403(self, transactional_db):
        """Test non-admin cannot create clients"""
        client = TestDataFactory.create_client(transactional_db, client_id="OP-CL")
        operator = TestDataFactory.create_user(transactional_db, role="operator", client_id="OP-CL")
        transactional_db.commit()

        data = {"client_id": "FAIL-CL", "client_name": "Fail Client"}
        with pytest.raises(HTTPException) as exc_info:
            create_client(transactional_db, data, operator)
        assert exc_info.value.status_code == 403

    def test_client_create_duplicate_raises_400(self, transactional_db):
        """Test creating duplicate client raises 400"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="DUP-CL")
        transactional_db.commit()

        data = {"client_id": "DUP-CL", "client_name": "Duplicate"}
        with pytest.raises(HTTPException) as exc_info:
            create_client(transactional_db, data, admin)
        assert exc_info.value.status_code == 400

    def test_client_update(self, transactional_db):
        """Test updating client"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="UPD-CL", client_name="Original")
        transactional_db.commit()

        result = update_client(transactional_db, "UPD-CL", {"client_name": "Updated"}, admin)
        assert result.client_name == "Updated"

    def test_client_delete_soft(self, transactional_db):
        """Test soft deleting client"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        TestDataFactory.create_client(transactional_db, client_id="DEL-CL")
        transactional_db.commit()

        result = delete_client(transactional_db, "DEL-CL", admin)
        assert result is True


# =============================================================================
# ATTENDANCE CRUD INTEGRATION
# =============================================================================
class TestAttendanceCRUDIntegration:
    """Integration tests for attendance CRUD operations"""

    def test_attendance_list_empty(self, transactional_db):
        """Test getting attendance entries from empty DB"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_attendance_records(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_attendance_list_with_data(self, transactional_db):
        """Test getting attendance entries with seeded data"""
        client = TestDataFactory.create_client(transactional_db, client_id="ATT-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="ATT-CL")
        employee = TestDataFactory.create_employee(transactional_db, client_id="ATT-CL")
        shift = TestDataFactory.create_shift(transactional_db, client_id="ATT-CL")
        transactional_db.flush()

        TestDataFactory.create_attendance_entry(
            transactional_db,
            employee_id=employee.employee_id,
            client_id="ATT-CL",
            shift_id=shift.shift_id,
        )
        transactional_db.commit()

        result = get_attendance_records(transactional_db, admin)
        assert len(result) >= 1

    def test_attendance_hours_calculation(self):
        """Test attendance hours arithmetic"""
        scheduled_hours = 8.0
        hours_worked = 6.5
        hours_absent = scheduled_hours - hours_worked
        assert hours_absent == 1.5


# =============================================================================
# PRODUCTION CRUD INTEGRATION
# =============================================================================
class TestProductionCRUDIntegration:
    """Integration tests for production CRUD operations"""

    def test_production_entry_efficiency_calculation(self):
        """Test production efficiency formula"""
        units_produced = 1000
        employees_assigned = 5
        hours_worked = 8
        ideal_cycle_time = Decimal("0.01")

        efficiency = (units_produced * ideal_cycle_time) / (employees_assigned * hours_worked) * 100
        assert efficiency == Decimal("25.0")

    def test_production_list_empty(self, transactional_db):
        """Test getting production entries from empty DB"""
        from backend.crud.production import get_production_entries

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_production_entries(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_production_list_with_data(self, transactional_db):
        """Test getting production entries with seeded data"""
        from backend.crud.production import get_production_entries

        client = TestDataFactory.create_client(transactional_db, client_id="PROD-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="PROD-CL")
        product = TestDataFactory.create_product(transactional_db, client_id="PROD-CL")
        shift = TestDataFactory.create_shift(transactional_db, client_id="PROD-CL")
        transactional_db.flush()

        TestDataFactory.create_production_entry(
            transactional_db,
            client_id="PROD-CL",
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=admin.user_id,
        )
        transactional_db.commit()

        result = get_production_entries(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# QUALITY CRUD INTEGRATION
# =============================================================================
class TestQualityCRUDIntegration:
    """Integration tests for quality CRUD operations"""

    def test_quality_ppm_calculation(self):
        """Test PPM formula"""
        units_inspected = 1000
        defects_found = 5
        ppm = (defects_found / units_inspected) * 1_000_000
        assert ppm == 5000.0

    def test_quality_dpmo_calculation(self):
        """Test DPMO formula"""
        defects_found = 5
        units_inspected = 1000
        opportunities_per_unit = 10
        dpmo = (defects_found / (units_inspected * opportunities_per_unit)) * 1_000_000
        assert dpmo == 500.0

    def test_quality_list_empty(self, transactional_db):
        """Test getting quality entries from empty DB"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_quality_inspections(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_quality_list_with_data(self, transactional_db):
        """Test getting quality entries with seeded data"""
        client = TestDataFactory.create_client(transactional_db, client_id="QUAL-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="QUAL-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="QUAL-CL")
        transactional_db.flush()

        TestDataFactory.create_quality_entry(
            transactional_db,
            work_order_id=wo.work_order_id,
            client_id="QUAL-CL",
            inspector_id=admin.user_id,
        )
        transactional_db.commit()

        result = get_quality_inspections(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# DOWNTIME CRUD INTEGRATION
# =============================================================================
class TestDowntimeCRUDIntegration:
    """Integration tests for downtime CRUD operations"""

    def test_downtime_duration_calculation(self):
        """Test downtime duration calculation"""
        start_time = datetime(2024, 1, 15, 10, 0, 0)
        end_time = datetime(2024, 1, 15, 11, 30, 0)
        duration_minutes = (end_time - start_time).total_seconds() / 60
        assert duration_minutes == 90.0

    def test_downtime_list_empty(self, transactional_db):
        """Test getting downtime entries from empty DB"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_downtime_list_with_data(self, transactional_db):
        """Test getting downtime entries with seeded data"""
        client = TestDataFactory.create_client(transactional_db, client_id="DT-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DT-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DT-CL")
        transactional_db.flush()

        TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-CL",
            work_order_id=wo.work_order_id,
            reported_by=admin.user_id,
        )
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# EMPLOYEE CRUD INTEGRATION
# =============================================================================
class TestEmployeeCRUDIntegration:
    """Integration tests for employee CRUD operations"""

    def test_employee_list_empty(self, transactional_db):
        """Test getting employees from empty DB"""
        from backend.crud.employee import get_employees

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_employees(transactional_db, admin)
        assert isinstance(result, list)

    def test_employee_list_with_data(self, transactional_db):
        """Test getting employees with seeded data"""
        from backend.crud.employee import get_employees

        client = TestDataFactory.create_client(transactional_db, client_id="EMP-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="EMP-CL")
        TestDataFactory.create_employee(transactional_db, client_id="EMP-CL", employee_name="John Doe")
        transactional_db.commit()

        result = get_employees(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# WORK ORDER CRUD INTEGRATION
# =============================================================================
class TestWorkOrderCRUDIntegration:
    """Integration tests for work order CRUD operations"""

    def test_work_order_list_empty(self, transactional_db):
        """Test getting work orders from empty DB"""
        from backend.crud.work_order import get_work_orders

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_work_orders(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_work_order_create_and_retrieve(self, transactional_db):
        """Test creating and retrieving a work order"""
        from backend.crud.work_order import get_work_orders, create_work_order

        client = TestDataFactory.create_client(transactional_db, client_id="WO-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="WO-CL")
        transactional_db.commit()

        wo_data = {
            "work_order_id": "WO-INT-001",
            "client_id": "WO-CL",
            "style_model": "TEST-STYLE",
            "planned_quantity": 500,
            "status": "RECEIVED",
        }
        created = create_work_order(transactional_db, wo_data, admin)
        assert created.work_order_id == "WO-INT-001"

        result = get_work_orders(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# HOLD CRUD INTEGRATION
# =============================================================================
class TestHoldCRUDIntegration:
    """Integration tests for hold CRUD operations"""

    def test_hold_aging_calculation(self):
        """Test hold aging days calculation"""
        hold_date = date.today() - timedelta(days=15)
        aging_days = (date.today() - hold_date).days
        assert aging_days == 15

    def test_hold_create_and_list(self, transactional_db):
        """Test creating and listing hold entries"""
        from backend.crud.hold import get_wip_holds

        client = TestDataFactory.create_client(transactional_db, client_id="HOLD-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="HOLD-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="HOLD-CL")
        transactional_db.flush()

        TestDataFactory.create_hold_entry(
            transactional_db,
            work_order_id=wo.work_order_id,
            client_id="HOLD-CL",
            created_by=admin.user_id,
        )
        transactional_db.commit()

        result = get_wip_holds(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# FLOATING POOL CRUD INTEGRATION
# =============================================================================
class TestFloatingPoolCRUDIntegration:
    """Integration tests for floating pool CRUD operations"""

    def test_floating_pool_coverage_calculation(self):
        """Test floating pool coverage percentage"""
        total_employees = 100
        floating_pool = 15
        coverage_percentage = (floating_pool / total_employees) * 100
        assert coverage_percentage == 15.0


# =============================================================================
# COVERAGE CRUD INTEGRATION
# =============================================================================
class TestCoverageCRUDIntegration:
    """Integration tests for coverage CRUD operations"""

    def test_coverage_list_empty(self, transactional_db):
        """Test getting coverage entries from empty DB"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_shift_coverages(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0


# =============================================================================
# JOB CRUD INTEGRATION
# =============================================================================
class TestJobCRUDIntegration:
    """Integration tests for job CRUD operations"""

    def test_job_list_empty(self, transactional_db):
        """Test getting jobs from empty DB"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_jobs(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_job_create_and_list(self, transactional_db):
        """Test creating and listing jobs"""
        client = TestDataFactory.create_client(transactional_db, client_id="JOB-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="JOB-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="JOB-CL")
        transactional_db.flush()

        TestDataFactory.create_job(transactional_db, work_order_id=wo.work_order_id, client_id="JOB-CL")
        transactional_db.commit()

        result = get_jobs(transactional_db, admin)
        assert len(result) >= 1


# =============================================================================
# ANALYTICS CRUD INTEGRATION
# =============================================================================
class TestAnalyticsCRUDIntegration:
    """Integration tests for analytics CRUD operations"""

    def test_aggregation_periods(self):
        """Test valid aggregation period names"""
        periods = ["daily", "weekly", "monthly", "quarterly", "yearly"]
        for period in periods:
            assert isinstance(period, str)

    def test_analytics_time_series_empty(self, transactional_db):
        """Test analytics time series with no data"""
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
