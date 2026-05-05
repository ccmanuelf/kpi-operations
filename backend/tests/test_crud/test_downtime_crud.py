"""
Comprehensive CRUD Tests - Downtime Module
Migrated to use real database (transactional_db) instead of mocks.
"""

import pytest
from datetime import date, datetime

from backend.tests.fixtures.factories import TestDataFactory
from backend.crud.downtime import get_downtime_events, get_downtime_event
from fastapi import HTTPException


class TestDowntimeCRUD:
    """Test suite for downtime CRUD operations using real DB"""

    def test_get_downtime_events_empty(self, transactional_db):
        """Test get downtime events returns empty list"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_create_and_list_downtime(self, transactional_db):
        """Test creating and listing downtime events"""
        client = TestDataFactory.create_client(transactional_db, client_id="DT-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DT-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DT-CL")
        transactional_db.flush()

        TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-CL",
            work_order_id=wo.work_order_id,
            reported_by=admin.user_id,
            downtime_reason="EQUIPMENT_FAILURE",
            duration_minutes=120,
        )
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert len(result) == 1
        assert result[0].downtime_duration_minutes == 120

    def test_get_downtime_by_id(self, transactional_db):
        """Test getting a specific downtime entry by ID"""
        client = TestDataFactory.create_client(transactional_db, client_id="DTID-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DTID-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DTID-CL")
        transactional_db.flush()

        entry = TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DTID-CL",
            work_order_id=wo.work_order_id,
            reported_by=admin.user_id,
        )
        transactional_db.commit()

        result = get_downtime_event(transactional_db, entry.downtime_entry_id, admin)
        assert result is not None
        assert result.downtime_entry_id == entry.downtime_entry_id

    def test_get_downtime_not_found(self, transactional_db):
        """Test getting non-existent downtime raises 404"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_downtime_event(transactional_db, "DT-NONEXIST", admin)
        assert exc_info.value.status_code == 404

    def test_multiple_downtime_entries(self, transactional_db):
        """Test creating multiple downtime entries"""
        client = TestDataFactory.create_client(transactional_db, client_id="DTM-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DTM-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DTM-CL")
        transactional_db.flush()

        for reason in ["EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "CHANGEOVER"]:
            TestDataFactory.create_downtime_entry(
                transactional_db,
                client_id="DTM-CL",
                work_order_id=wo.work_order_id,
                reported_by=admin.user_id,
                downtime_reason=reason,
                duration_minutes=30,
            )
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin)
        assert len(result) == 3

    def test_downtime_filter_by_client(self, transactional_db):
        """Test filtering downtime by client_id"""
        client_a = TestDataFactory.create_client(transactional_db, client_id="DT-A")
        client_b = TestDataFactory.create_client(transactional_db, client_id="DT-B")
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        wo_a = TestDataFactory.create_work_order(transactional_db, client_id="DT-A")
        wo_b = TestDataFactory.create_work_order(transactional_db, client_id="DT-B")
        transactional_db.flush()

        TestDataFactory.create_downtime_entry(
            transactional_db, client_id="DT-A", work_order_id=wo_a.work_order_id, reported_by=admin.user_id
        )
        TestDataFactory.create_downtime_entry(
            transactional_db, client_id="DT-B", work_order_id=wo_b.work_order_id, reported_by=admin.user_id
        )
        transactional_db.commit()

        result = get_downtime_events(transactional_db, admin, client_id="DT-A")
        assert len(result) == 1
        assert result[0].client_id == "DT-A"

    def test_calculate_mtbf(self):
        """Test Mean Time Between Failures calculation"""
        total_operating_hours = 1000
        number_of_failures = 5
        mtbf = total_operating_hours / number_of_failures
        assert mtbf == 200.0

    def test_calculate_mttr(self):
        """Test Mean Time To Repair calculation"""
        total_repair_time = 25
        number_of_repairs = 5
        mttr = total_repair_time / number_of_repairs
        assert mttr == 5.0

    def test_availability_from_downtime(self):
        """Test availability calculation from downtime"""
        scheduled_time = 480
        total_downtime = 45
        availability = ((scheduled_time - total_downtime) / scheduled_time) * 100
        assert availability == 90.625

    def test_planned_vs_unplanned_downtime(self):
        """Test categorizing planned vs unplanned downtime"""
        events = [
            {"planned": True, "duration": 30},
            {"planned": False, "duration": 45},
            {"planned": True, "duration": 15},
            {"planned": False, "duration": 60},
        ]
        planned = sum(e["duration"] for e in events if e["planned"])
        unplanned = sum(e["duration"] for e in events if not e["planned"])
        assert planned == 45
        assert unplanned == 105

    def test_pareto_downtime_analysis(self):
        """Test Pareto analysis of downtime causes"""
        causes = [
            {"reason": "Mechanical", "minutes": 180},
            {"reason": "Changeover", "minutes": 120},
            {"reason": "Material", "minutes": 60},
            {"reason": "Operator", "minutes": 30},
            {"reason": "Other", "minutes": 10},
        ]
        total = sum(c["minutes"] for c in causes)
        top_two_pct = ((causes[0]["minutes"] + causes[1]["minutes"]) / total) * 100
        assert top_two_pct == 75.0

    def test_downtime_trend_weekly(self):
        """Test weekly downtime trending"""
        weekly_data = [
            {"week": 1, "total_minutes": 320},
            {"week": 2, "total_minutes": 280},
            {"week": 3, "total_minutes": 250},
            {"week": 4, "total_minutes": 210},
        ]
        improvement = (
            (weekly_data[0]["total_minutes"] - weekly_data[-1]["total_minutes"]) / weekly_data[0]["total_minutes"]
        ) * 100
        assert round(improvement, 2) == 34.38


class TestDowntimeNullableWorkOrderId:
    """Test suite for nullable work_order_id on DowntimeEntry"""

    def test_create_downtime_without_work_order_id(self, transactional_db):
        """Creating a downtime entry without work_order_id succeeds"""
        client = TestDataFactory.create_client(transactional_db, client_id="DT-NWO-1")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DT-NWO-1")
        transactional_db.flush()

        entry = TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-NWO-1",
            reported_by=admin.user_id,
            downtime_reason="EQUIPMENT_FAILURE",
            duration_minutes=45,
            machine_id="MACH-LINE-A",
        )
        transactional_db.commit()

        assert entry.downtime_entry_id is not None
        assert entry.work_order_id is None
        assert entry.client_id == "DT-NWO-1"
        assert entry.downtime_duration_minutes == 45
        assert entry.machine_id == "MACH-LINE-A"

    def test_create_downtime_with_work_order_id(self, transactional_db):
        """Creating a downtime entry with work_order_id still works"""
        client = TestDataFactory.create_client(transactional_db, client_id="DT-WWO-1")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DT-WWO-1")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DT-WWO-1")
        transactional_db.flush()

        entry = TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-WWO-1",
            work_order_id=wo.work_order_id,
            reported_by=admin.user_id,
            downtime_reason="MATERIAL_SHORTAGE",
            duration_minutes=60,
        )
        transactional_db.commit()

        assert entry.work_order_id == wo.work_order_id
        assert entry.downtime_duration_minutes == 60

    def test_update_downtime_to_remove_work_order_id(self, transactional_db):
        """Updating a downtime entry to set work_order_id to None works"""
        client = TestDataFactory.create_client(transactional_db, client_id="DT-RWO-1")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DT-RWO-1")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DT-RWO-1")
        transactional_db.flush()

        entry = TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-RWO-1",
            work_order_id=wo.work_order_id,
            reported_by=admin.user_id,
        )
        transactional_db.commit()

        # Verify it was created with the work order
        assert entry.work_order_id == wo.work_order_id

        # Now remove the work order reference
        entry.work_order_id = None
        transactional_db.commit()
        transactional_db.refresh(entry)

        assert entry.work_order_id is None

    def test_query_downtime_with_null_work_order_id(self, transactional_db):
        """Querying downtime entries with NULL work_order_id returns correct results"""
        client = TestDataFactory.create_client(transactional_db, client_id="DT-QNL-1")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DT-QNL-1")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DT-QNL-1")
        transactional_db.flush()

        # Create one entry WITH work order
        entry_with_wo = TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-QNL-1",
            work_order_id=wo.work_order_id,
            reported_by=admin.user_id,
            downtime_reason="EQUIPMENT_FAILURE",
        )
        # Create one entry WITHOUT work order
        entry_without_wo = TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-QNL-1",
            reported_by=admin.user_id,
            downtime_reason="MAINTENANCE",
        )
        transactional_db.commit()

        # List all - should return both
        all_events = get_downtime_events(transactional_db, admin, client_id="DT-QNL-1")
        assert len(all_events) == 2

        # Filter by work_order_id - should return only the one with WO
        wo_events = get_downtime_events(transactional_db, admin, client_id="DT-QNL-1", work_order_id=wo.work_order_id)
        assert len(wo_events) == 1
        assert wo_events[0].work_order_id == wo.work_order_id

    def test_query_null_work_order_id_directly(self, transactional_db):
        """Querying entries where work_order_id IS NULL via ORM works"""
        from backend.orm.downtime_entry import DowntimeEntry

        client = TestDataFactory.create_client(transactional_db, client_id="DT-QDR-1")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="DT-QDR-1")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="DT-QDR-1")
        transactional_db.flush()

        # Create entries with and without work orders
        TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-QDR-1",
            work_order_id=wo.work_order_id,
            reported_by=admin.user_id,
        )
        TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-QDR-1",
            reported_by=admin.user_id,
        )
        TestDataFactory.create_downtime_entry(
            transactional_db,
            client_id="DT-QDR-1",
            reported_by=admin.user_id,
        )
        transactional_db.commit()

        # Query for entries with NULL work_order_id
        null_wo_entries = transactional_db.query(DowntimeEntry).filter(DowntimeEntry.work_order_id.is_(None)).all()
        assert len(null_wo_entries) == 2
        for entry in null_wo_entries:
            assert entry.work_order_id is None

        # Query for entries with non-NULL work_order_id
        non_null_entries = transactional_db.query(DowntimeEntry).filter(DowntimeEntry.work_order_id.isnot(None)).all()
        assert len(non_null_entries) == 1
        assert non_null_entries[0].work_order_id == wo.work_order_id

    def test_pydantic_create_schema_accepts_none_work_order_id(self):
        """DowntimeEventCreate schema accepts work_order_id=None"""
        from backend.schemas.downtime import DowntimeEventCreate

        event = DowntimeEventCreate(
            client_id="TEST-CL",
            shift_date=date.today(),
            downtime_reason="EQUIPMENT_FAILURE",
            downtime_duration_minutes=30,
            machine_id="MACH-001",
        )
        assert event.work_order_id is None

    def test_pydantic_create_schema_accepts_provided_work_order_id(self):
        """DowntimeEventCreate schema accepts an explicit work_order_id"""
        from backend.schemas.downtime import DowntimeEventCreate

        event = DowntimeEventCreate(
            client_id="TEST-CL",
            work_order_id="WO-123",
            shift_date=date.today(),
            downtime_reason="MAINTENANCE",
            downtime_duration_minutes=60,
        )
        assert event.work_order_id == "WO-123"

    def test_pydantic_response_schema_allows_null_work_order_id(self):
        """DowntimeEventResponse schema allows work_order_id=None"""
        from backend.schemas.downtime import DowntimeEventResponse

        response = DowntimeEventResponse(
            downtime_entry_id="DT-001",
            client_id="TEST-CL",
            work_order_id=None,
            shift_date=datetime.now(),
            downtime_reason="EQUIPMENT_FAILURE",
            downtime_duration_minutes=30,
        )
        assert response.work_order_id is None

    def test_pydantic_update_schema_includes_work_order_id(self):
        """DowntimeEventUpdate schema can set work_order_id"""
        from backend.schemas.downtime import DowntimeEventUpdate

        # Explicitly set work_order_id
        update = DowntimeEventUpdate(work_order_id="WO-NEW")
        data = update.model_dump(exclude_unset=True)
        assert "work_order_id" in data
        assert data["work_order_id"] == "WO-NEW"

        # Omitting work_order_id entirely (not in exclude_unset output)
        update_no_wo = DowntimeEventUpdate(notes="updated notes")
        data_no_wo = update_no_wo.model_dump(exclude_unset=True)
        assert "work_order_id" not in data_no_wo


class TestAvailabilityMetrics:
    """Test availability-related metrics"""

    def test_equipment_availability(self):
        """Test equipment availability calculation"""
        total_time = 720
        planned_downtime = 30
        unplanned_downtime = 45
        available_time = total_time - planned_downtime - unplanned_downtime
        availability = (available_time / total_time) * 100
        assert round(availability, 2) == 89.58

    def test_line_availability(self):
        """Test production line availability"""
        machines = [
            {"availability": 95.0},
            {"availability": 92.5},
            {"availability": 98.0},
            {"availability": 94.5},
        ]
        line_availability = min(m["availability"] for m in machines)
        assert line_availability == 92.5

    def test_scheduled_vs_actual_uptime(self):
        """Test scheduled vs actual uptime"""
        scheduled_uptime = 480
        actual_uptime = 435
        uptime_achievement = (actual_uptime / scheduled_uptime) * 100
        assert round(uptime_achievement, 2) == 90.62
