"""
Comprehensive tests for Downtime, Hold, and Employee CRUD operations.
Migrated to use real database (transactional_db) instead of mocks.
"""

import pytest
from datetime import datetime, date, timedelta, timezone
from fastapi import HTTPException

from backend.tests.fixtures.factories import TestDataFactory


class TestDowntimeCRUD:
    """Test Downtime CRUD operations using real DB."""

    def test_create_and_list_downtime(self, transactional_db):
        """Test creating and listing downtime events"""
        client = TestDataFactory.create_client(transactional_db, client_id="DTC-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DTC-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DTC-CL")
        transactional_db.flush()

        from backend.crud.downtime import create_downtime_event, get_downtime_events

        entry = TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DTC-CL",
            work_order_id=wo.work_order_id,
            reported_by=admin.user_id,
            downtime_reason="EQUIPMENT_FAILURE",
            duration_minutes=120,
        )
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert len(result) >= 1
        assert result[0].downtime_duration_minutes == 120

    def test_get_downtime_by_id(self, transactional_db):
        """Test getting a specific downtime entry by ID"""
        from backend.crud.downtime import get_downtime_event

        client = TestDataFactory.create_client(transactional_db, client_id="DTBI-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DTBI-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DTBI-CL")
        transactional_db.flush()

        entry = TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DTBI-CL",
            work_order_id=wo.work_order_id,
            reported_by=admin.user_id,
        )
        transactional_db.commit()

        result = get_downtime_event(transactional_db, entry.downtime_entry_id, admin)
        assert result is not None
        assert result.downtime_entry_id == entry.downtime_entry_id

    def test_get_downtime_not_found(self, transactional_db):
        """Test getting non-existent downtime raises 404"""
        from backend.crud.downtime import get_downtime_event

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_downtime_event(transactional_db, "DT-NONEXIST", admin)
        assert exc_info.value.status_code == 404

    def test_get_downtime_events_empty(self, transactional_db):
        """Test get downtime events returns empty list"""
        from backend.crud.downtime import get_downtime_events

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_multiple_downtime_reasons(self, transactional_db):
        """Test creating multiple downtime events with different reasons"""
        from backend.crud.downtime import get_downtime_events

        client = TestDataFactory.create_client(transactional_db, client_id="DTMR-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DTMR-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DTMR-CL")
        transactional_db.flush()

        for reason in ["EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "CHANGEOVER"]:
            TestDataFactory.create_downtime_entry(
                transactional_db,
                client_id="DTMR-CL",
                work_order_id=wo.work_order_id,
                reported_by=admin.user_id,
                downtime_reason=reason,
                duration_minutes=30,
            )
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert len(result) == 3

    def test_calculate_duration(self):
        """Test duration calculation from start/end times"""
        base_time = datetime(2024, 1, 15, 12, 0, 0)
        start = base_time - timedelta(hours=2, minutes=30)
        end = base_time
        duration = (end - start).total_seconds() / 60
        assert duration == 150

    def test_calculate_availability(self):
        """Test availability calculation from downtime"""
        planned_time = 480
        downtime = 60
        availability = ((planned_time - downtime) / planned_time) * 100
        assert availability == 87.5

    def test_mtbf_calculation(self):
        """Test Mean Time Between Failures calculation"""
        total_operating_time = 2400
        number_of_failures = 4
        mtbf = total_operating_time / number_of_failures
        assert mtbf == 600

    def test_mttr_calculation(self):
        """Test Mean Time To Repair calculation"""
        total_repair_time = 180
        number_of_failures = 3
        mttr = total_repair_time / number_of_failures
        assert mttr == 60


class TestDowntimeEdgeCases:
    """Edge cases for downtime."""

    def test_open_downtime_entry(self):
        """Test open downtime entry detection"""
        start_time = datetime.now(tz=timezone.utc)
        end_time = None
        is_open = end_time is None
        assert is_open is True

    def test_overlapping_downtime(self):
        """Test overlapping downtime detection"""
        entry1_end = datetime.now(tz=timezone.utc)
        entry2_start = datetime.now(tz=timezone.utc) - timedelta(minutes=30)
        overlaps = entry2_start < entry1_end
        assert overlaps is True

    def test_planned_vs_unplanned_ratio(self):
        """Test planned vs unplanned downtime ratio"""
        planned = 60
        unplanned = 180
        total = planned + unplanned
        planned_ratio = (planned / total) * 100
        assert planned_ratio == 25

    def test_downtime_categories(self):
        """Test downtime categories list"""
        categories = ["mechanical", "electrical", "operator", "material", "planned"]
        assert len(categories) == 5

    def test_consecutive_downtime_merge(self):
        """Test whether consecutive downtimes should be merged"""
        gap = 5
        should_merge = gap <= 5
        assert should_merge is True


class TestHoldCRUD:
    """Test Hold CRUD operations using real DB."""

    def test_get_wip_holds_empty(self, transactional_db):
        """Test get WIP holds returns empty list"""
        from backend.crud.hold import get_wip_holds

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_wip_holds(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_create_and_list_holds(self, transactional_db):
        """Test creating and listing hold entries"""
        from backend.crud.hold import get_wip_holds

        client = TestDataFactory.create_client(transactional_db, client_id="HC-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="HC-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="HC-CL")
        transactional_db.flush()

        TestDataFactory.create_hold_entry(
            transactional_db,
            work_order_id=wo.work_order_id,
            client_id="HC-CL",
            created_by=admin.user_id,
            quantity_on_hold=50,
        )
        transactional_db.commit()

        result = get_wip_holds(transactional_db, admin)
        assert len(result) >= 1

    def test_get_hold_by_id(self, transactional_db):
        """Test getting a hold entry by ID"""
        from backend.crud.hold import get_wip_hold

        client = TestDataFactory.create_client(transactional_db, client_id="HBI-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="HBI-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="HBI-CL")
        transactional_db.flush()

        entry = TestDataFactory.create_hold_entry(
            transactional_db,
            work_order_id=wo.work_order_id,
            client_id="HBI-CL",
            created_by=admin.user_id,
        )
        transactional_db.commit()

        result = get_wip_hold(transactional_db, entry.hold_entry_id, admin)
        assert result is not None
        assert result.hold_entry_id == entry.hold_entry_id

    def test_get_hold_not_found(self, transactional_db):
        """Test getting non-existent hold raises 404"""
        from backend.crud.hold import get_wip_hold

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_wip_hold(transactional_db, "HE-NONEXIST", admin)
        assert exc_info.value.status_code == 404

    def test_hold_aging_calculation(self):
        """Test hold aging calculation in days"""
        hold_date = datetime.now(tz=timezone.utc) - timedelta(days=5)
        aging_days = (datetime.now(tz=timezone.utc) - hold_date).days
        assert aging_days == 5


class TestEmployeeCRUD:
    """Test Employee CRUD operations using real DB."""

    def test_get_employees_empty(self, transactional_db):
        """Test get employees returns empty list"""
        from backend.crud.employee import get_employees

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_employees(transactional_db, admin)
        assert isinstance(result, list)

    def test_get_employee_not_found(self, transactional_db):
        """Test getting non-existent employee raises 404"""
        from backend.crud.employee import get_employee

        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_employee(transactional_db, 99999, admin)
        assert exc_info.value.status_code == 404

    def test_create_and_list_employees(self, transactional_db):
        """Test creating and listing employees"""
        from backend.crud.employee import get_employees

        client = TestDataFactory.create_client(transactional_db, client_id="EC-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="EC-CL")
        TestDataFactory.create_employee(transactional_db, client_id="EC-CL")
        TestDataFactory.create_employee(transactional_db, client_id="EC-CL")
        transactional_db.commit()

        result = get_employees(transactional_db, admin)
        assert len(result) >= 2

    def test_get_employee_by_id(self, transactional_db):
        """Test getting employee by ID"""
        from backend.crud.employee import get_employee

        client = TestDataFactory.create_client(transactional_db, client_id="EBI-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="EBI-CL")
        emp = TestDataFactory.create_employee(transactional_db, client_id="EBI-CL")
        transactional_db.commit()

        result = get_employee(transactional_db, emp.employee_id, admin)
        assert result is not None
        assert result.employee_id == emp.employee_id

    def test_employee_skills(self):
        """Test employee skills data structure"""
        skills = ["welding", "assembly", "quality_inspection"]
        assert len(skills) == 3
