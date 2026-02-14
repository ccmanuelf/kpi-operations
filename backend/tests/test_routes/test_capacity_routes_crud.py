"""
Capacity Routes CRUD Integration Tests
Tests 24 CRUD endpoints on the capacity router for: Calendar (5), Production Lines (5),
Orders (7), Standards (7).

Uses real in-memory SQLite database -- NO mocks for DB layer.
Follows the exact pattern from test_kpi_routes_real.py.
"""
import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.schemas import ClientType
from backend.auth.jwt import get_current_user
from backend.schemas.user import User, UserRole
from backend.routes.capacity import router as capacity_router
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test App Factory and Fixtures
# =============================================================================

CLIENT_ID = "CAP-TEST-CLIENT"


def create_test_app(db_session):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(capacity_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Create an admin user that has access to any client (role check in middleware)
    mock_user = User(
        user_id="test-cap-admin-001",
        username="cap_test_admin",
        email="cap_admin@test.com",
        role=UserRole.ADMIN.value,
        client_id_assigned=None,
        is_active=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return app


@pytest.fixture(scope="function")
def cap_db():
    """Create a fresh in-memory database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def cap_client(cap_db):
    """Create test client entity in the database and return (TestClient, db)."""
    db = cap_db
    # Create the CLIENT row that ForeignKey references require
    TestDataFactory.create_client(
        db,
        client_id=CLIENT_ID,
        client_name="Capacity Test Client",
        client_type=ClientType.HOURLY_RATE,
    )
    db.commit()

    app = create_test_app(db)
    return TestClient(app), db


# =============================================================================
# Helper: Create entities via API
# =============================================================================

def _create_calendar_entry(client, cal_date=None, **overrides):
    """Helper to POST a calendar entry and return the response."""
    payload = {
        "calendar_date": (cal_date or date.today()).isoformat(),
        "is_working_day": True,
        "shifts_available": 2,
        "shift1_hours": 8.0,
        "shift2_hours": 8.0,
        "shift3_hours": 0,
        "holiday_name": None,
        "notes": "test entry",
    }
    payload.update(overrides)
    return client.post(f"/api/capacity/calendar?client_id={CLIENT_ID}", json=payload)


def _create_production_line(client, code=None, **overrides):
    """Helper to POST a production line and return the response."""
    payload = {
        "line_code": code or "LINE-A",
        "line_name": "Assembly Line A",
        "department": "SEWING",
        "standard_capacity_units_per_hour": 120,
        "max_operators": 15,
        "efficiency_factor": 0.85,
        "absenteeism_factor": 0.05,
        "is_active": True,
        "notes": "test line",
    }
    payload.update(overrides)
    return client.post(f"/api/capacity/lines?client_id={CLIENT_ID}", json=payload)


def _create_order(client, order_number=None, **overrides):
    """Helper to POST an order and return the response."""
    payload = {
        "order_number": order_number or "ORD-001",
        "style_code": "STYLE-A",
        "order_quantity": 500,
        "required_date": (date.today() + timedelta(days=30)).isoformat(),
        "customer_name": "Acme Corp",
        "style_description": "Summer T-Shirt",
        "order_date": date.today().isoformat(),
        "priority": "NORMAL",
        "status": "DRAFT",
        "notes": "test order",
    }
    payload.update(overrides)
    return client.post(f"/api/capacity/orders?client_id={CLIENT_ID}", json=payload)


def _create_standard(client, style_code=None, operation_code=None, **overrides):
    """Helper to POST a standard and return the response."""
    payload = {
        "style_code": style_code or "STYLE-A",
        "operation_code": operation_code or "OP-10",
        "sam_minutes": 2.5,
        "operation_name": "Front Stitch",
        "department": "SEWING",
        "setup_time_minutes": 0.5,
        "machine_time_minutes": 1.5,
        "manual_time_minutes": 0.5,
        "notes": "test standard",
    }
    payload.update(overrides)
    return client.post(f"/api/capacity/standards?client_id={CLIENT_ID}", json=payload)


# =============================================================================
# Calendar CRUD Tests
# =============================================================================

class TestCalendarCreate:
    """POST /api/capacity/calendar"""

    def test_create_calendar_entry_success(self, cap_client):
        client, _ = cap_client
        resp = _create_calendar_entry(client)
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == CLIENT_ID
        assert data["is_working_day"] is True
        assert data["shifts_available"] == 2
        assert data["shift1_hours"] == 8.0
        assert data["shift2_hours"] == 8.0
        assert data["id"] is not None

    def test_create_calendar_entry_holiday(self, cap_client):
        client, _ = cap_client
        resp = _create_calendar_entry(
            client,
            cal_date=date(2026, 12, 25),
            is_working_day=False,
            holiday_name="Christmas",
            shifts_available=0,
            shift1_hours=0,
            shift2_hours=0,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_working_day"] is False
        assert data["holiday_name"] == "Christmas"

    def test_create_calendar_entry_missing_client_id(self, cap_client):
        client, _ = cap_client
        resp = client.post("/api/capacity/calendar", json={
            "calendar_date": date.today().isoformat(),
        })
        assert resp.status_code == 422


class TestCalendarList:
    """GET /api/capacity/calendar"""

    def test_list_calendar_empty(self, cap_client):
        client, _ = cap_client
        resp = client.get(f"/api/capacity/calendar?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_calendar_with_data(self, cap_client):
        client, _ = cap_client
        _create_calendar_entry(client, cal_date=date(2026, 3, 1))
        _create_calendar_entry(client, cal_date=date(2026, 3, 2))

        resp = client.get(f"/api/capacity/calendar?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_calendar_with_pagination(self, cap_client):
        client, _ = cap_client
        for i in range(5):
            _create_calendar_entry(client, cal_date=date(2026, 4, 1) + timedelta(days=i))

        resp = client.get(f"/api/capacity/calendar?client_id={CLIENT_ID}&skip=2&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_calendar_date_range_filter(self, cap_client):
        client, _ = cap_client
        _create_calendar_entry(client, cal_date=date(2026, 5, 1))
        _create_calendar_entry(client, cal_date=date(2026, 5, 15))
        _create_calendar_entry(client, cal_date=date(2026, 6, 1))

        resp = client.get(
            f"/api/capacity/calendar?client_id={CLIENT_ID}"
            f"&start_date=2026-05-01&end_date=2026-05-31"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


class TestCalendarGetSingle:
    """GET /api/capacity/calendar/{entry_id}"""

    def test_get_calendar_success(self, cap_client):
        client, _ = cap_client
        created = _create_calendar_entry(client).json()
        entry_id = created["id"]

        resp = client.get(f"/api/capacity/calendar/{entry_id}?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json()["id"] == entry_id

    def test_get_calendar_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.get(f"/api/capacity/calendar/99999?client_id={CLIENT_ID}")
        assert resp.status_code == 404


class TestCalendarUpdate:
    """PUT /api/capacity/calendar/{entry_id}"""

    def test_update_calendar_success(self, cap_client):
        client, _ = cap_client
        created = _create_calendar_entry(client).json()
        entry_id = created["id"]

        resp = client.put(
            f"/api/capacity/calendar/{entry_id}?client_id={CLIENT_ID}",
            json={"shifts_available": 3, "shift3_hours": 6.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["shifts_available"] == 3
        assert data["shift3_hours"] == 6.0

    def test_update_calendar_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.put(
            f"/api/capacity/calendar/99999?client_id={CLIENT_ID}",
            json={"shifts_available": 1},
        )
        assert resp.status_code == 404

    def test_update_calendar_partial(self, cap_client):
        client, _ = cap_client
        created = _create_calendar_entry(client).json()
        entry_id = created["id"]

        resp = client.put(
            f"/api/capacity/calendar/{entry_id}?client_id={CLIENT_ID}",
            json={"notes": "updated notes"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "updated notes"
        # Original values unchanged
        assert resp.json()["shifts_available"] == 2


class TestCalendarDelete:
    """DELETE /api/capacity/calendar/{entry_id}"""

    def test_delete_calendar_success(self, cap_client):
        client, _ = cap_client
        created = _create_calendar_entry(client).json()
        entry_id = created["id"]

        resp = client.delete(f"/api/capacity/calendar/{entry_id}?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Calendar entry deleted"

        # Verify gone
        resp2 = client.get(f"/api/capacity/calendar/{entry_id}?client_id={CLIENT_ID}")
        assert resp2.status_code == 404

    def test_delete_calendar_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.delete(f"/api/capacity/calendar/99999?client_id={CLIENT_ID}")
        assert resp.status_code == 404


# =============================================================================
# Production Lines CRUD Tests
# =============================================================================

class TestProductionLineCreate:
    """POST /api/capacity/lines"""

    def test_create_line_success(self, cap_client):
        client, _ = cap_client
        resp = _create_production_line(client, code="LINE-01")
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == CLIENT_ID
        assert data["line_code"] == "LINE-01"
        assert data["line_name"] == "Assembly Line A"
        assert data["department"] == "SEWING"
        assert data["is_active"] is True

    def test_create_line_minimal_fields(self, cap_client):
        client, _ = cap_client
        resp = client.post(
            f"/api/capacity/lines?client_id={CLIENT_ID}",
            json={"line_code": "LINE-MIN", "line_name": "Minimal Line"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["line_code"] == "LINE-MIN"
        assert data["efficiency_factor"] == 0.85  # default
        assert data["max_operators"] == 10  # default

    def test_create_line_missing_required_fields(self, cap_client):
        client, _ = cap_client
        resp = client.post(
            f"/api/capacity/lines?client_id={CLIENT_ID}",
            json={"line_code": "ONLY-CODE"},
        )
        assert resp.status_code == 422


class TestProductionLineList:
    """GET /api/capacity/lines"""

    def test_list_lines_empty(self, cap_client):
        client, _ = cap_client
        resp = client.get(f"/api/capacity/lines?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_lines_with_data(self, cap_client):
        client, _ = cap_client
        _create_production_line(client, code="L-01")
        _create_production_line(client, code="L-02")

        resp = client.get(f"/api/capacity/lines?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_lines_include_inactive(self, cap_client):
        client, _ = cap_client
        _create_production_line(client, code="L-ACTIVE", is_active=True)
        _create_production_line(client, code="L-INACTIVE", is_active=False)

        # Without include_inactive: only active lines
        resp = client.get(f"/api/capacity/lines?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["line_code"] == "L-ACTIVE"

        # With include_inactive=true: all lines
        resp2 = client.get(f"/api/capacity/lines?client_id={CLIENT_ID}&include_inactive=true")
        assert resp2.status_code == 200
        assert len(resp2.json()) == 2

    def test_list_lines_department_filter(self, cap_client):
        client, _ = cap_client
        _create_production_line(client, code="L-SEW", department="SEWING")
        _create_production_line(client, code="L-CUT", department="CUTTING")

        resp = client.get(f"/api/capacity/lines?client_id={CLIENT_ID}&department=SEWING")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["department"] == "SEWING"


class TestProductionLineGetSingle:
    """GET /api/capacity/lines/{line_id}"""

    def test_get_line_success(self, cap_client):
        client, _ = cap_client
        created = _create_production_line(client, code="LINE-GET").json()
        line_id = created["id"]

        resp = client.get(f"/api/capacity/lines/{line_id}?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json()["line_code"] == "LINE-GET"

    def test_get_line_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.get(f"/api/capacity/lines/99999?client_id={CLIENT_ID}")
        assert resp.status_code == 404


class TestProductionLineUpdate:
    """PUT /api/capacity/lines/{line_id}"""

    def test_update_line_success(self, cap_client):
        client, _ = cap_client
        created = _create_production_line(client, code="LINE-UPD").json()
        line_id = created["id"]

        resp = client.put(
            f"/api/capacity/lines/{line_id}?client_id={CLIENT_ID}",
            json={"line_name": "Updated Line", "efficiency_factor": 0.92},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["line_name"] == "Updated Line"
        assert data["efficiency_factor"] == 0.92

    def test_update_line_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.put(
            f"/api/capacity/lines/99999?client_id={CLIENT_ID}",
            json={"line_name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_update_line_deactivate(self, cap_client):
        client, _ = cap_client
        created = _create_production_line(client, code="LINE-DEACT").json()
        line_id = created["id"]

        resp = client.put(
            f"/api/capacity/lines/{line_id}?client_id={CLIENT_ID}",
            json={"is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


class TestProductionLineDelete:
    """DELETE /api/capacity/lines/{line_id} (soft delete by default)"""

    def test_delete_line_success(self, cap_client):
        client, _ = cap_client
        created = _create_production_line(client, code="LINE-DEL").json()
        line_id = created["id"]

        resp = client.delete(f"/api/capacity/lines/{line_id}?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Production line deleted"

    def test_delete_line_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.delete(f"/api/capacity/lines/99999?client_id={CLIENT_ID}")
        assert resp.status_code == 404

    def test_delete_line_soft_preserves_record(self, cap_client):
        client, _ = cap_client
        created = _create_production_line(client, code="LINE-SOFT").json()
        line_id = created["id"]

        # Soft delete (default)
        resp = client.delete(f"/api/capacity/lines/{line_id}?client_id={CLIENT_ID}")
        assert resp.status_code == 200

        # Record still exists but is inactive (include_inactive=true to see it)
        resp2 = client.get(
            f"/api/capacity/lines?client_id={CLIENT_ID}&include_inactive=true"
        )
        assert resp2.status_code == 200
        lines = resp2.json()
        deactivated = [ln for ln in lines if ln["id"] == line_id]
        assert len(deactivated) == 1
        assert deactivated[0]["is_active"] is False


# =============================================================================
# Orders CRUD Tests
# =============================================================================

class TestOrderCreate:
    """POST /api/capacity/orders"""

    def test_create_order_success(self, cap_client):
        client, _ = cap_client
        resp = _create_order(client, order_number="ORD-CREATE-001")
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == CLIENT_ID
        assert data["order_number"] == "ORD-CREATE-001"
        assert data["order_quantity"] == 500
        assert data["completed_quantity"] == 0
        assert data["status"] == "DRAFT"
        assert data["priority"] == "NORMAL"

    def test_create_order_with_all_fields(self, cap_client):
        client, _ = cap_client
        resp = _create_order(
            client,
            order_number="ORD-FULL-001",
            priority="URGENT",
            status="CONFIRMED",
            order_sam_minutes=12.5,
            planned_start_date=(date.today() + timedelta(days=5)).isoformat(),
            planned_end_date=(date.today() + timedelta(days=20)).isoformat(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == "URGENT"
        assert data["status"] == "CONFIRMED"
        assert data["order_sam_minutes"] == 12.5

    def test_create_order_missing_required_fields(self, cap_client):
        client, _ = cap_client
        resp = client.post(
            f"/api/capacity/orders?client_id={CLIENT_ID}",
            json={"order_number": "ORD-INCOMPLETE"},
        )
        assert resp.status_code == 422


class TestOrderList:
    """GET /api/capacity/orders"""

    def test_list_orders_empty(self, cap_client):
        client, _ = cap_client
        resp = client.get(f"/api/capacity/orders?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_orders_with_data(self, cap_client):
        client, _ = cap_client
        _create_order(client, order_number="ORD-L1")
        _create_order(client, order_number="ORD-L2")
        _create_order(client, order_number="ORD-L3")

        resp = client.get(f"/api/capacity/orders?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_orders_with_pagination(self, cap_client):
        client, _ = cap_client
        for i in range(5):
            _create_order(client, order_number=f"ORD-PG-{i:03d}")

        resp = client.get(f"/api/capacity/orders?client_id={CLIENT_ID}&skip=1&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestOrderGetSingle:
    """GET /api/capacity/orders/{order_id}"""

    def test_get_order_success(self, cap_client):
        client, _ = cap_client
        created = _create_order(client, order_number="ORD-GET-001").json()
        order_id = created["id"]

        resp = client.get(f"/api/capacity/orders/{order_id}?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json()["order_number"] == "ORD-GET-001"

    def test_get_order_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.get(f"/api/capacity/orders/99999?client_id={CLIENT_ID}")
        assert resp.status_code == 404


class TestOrderUpdate:
    """PUT /api/capacity/orders/{order_id}"""

    def test_update_order_success(self, cap_client):
        client, _ = cap_client
        created = _create_order(client, order_number="ORD-UPD-001").json()
        order_id = created["id"]

        resp = client.put(
            f"/api/capacity/orders/{order_id}?client_id={CLIENT_ID}",
            json={
                "customer_name": "Updated Customer",
                "order_quantity": 750,
                "priority": "HIGH",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer_name"] == "Updated Customer"
        assert data["order_quantity"] == 750
        assert data["priority"] == "HIGH"

    def test_update_order_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.put(
            f"/api/capacity/orders/99999?client_id={CLIENT_ID}",
            json={"customer_name": "Ghost"},
        )
        assert resp.status_code == 404


class TestOrderStatusUpdate:
    """PATCH /api/capacity/orders/{order_id}/status"""

    def test_update_order_status_success(self, cap_client):
        client, _ = cap_client
        created = _create_order(client, order_number="ORD-STAT-001").json()
        order_id = created["id"]

        resp = client.patch(
            f"/api/capacity/orders/{order_id}/status?client_id={CLIENT_ID}&new_status=CONFIRMED"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "CONFIRMED"

    def test_update_order_status_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.patch(
            f"/api/capacity/orders/99999/status?client_id={CLIENT_ID}&new_status=CONFIRMED"
        )
        assert resp.status_code == 404

    def test_update_order_status_to_completed(self, cap_client):
        client, _ = cap_client
        created = _create_order(client, order_number="ORD-COMP-001").json()
        order_id = created["id"]

        resp = client.patch(
            f"/api/capacity/orders/{order_id}/status?client_id={CLIENT_ID}&new_status=COMPLETED"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"

    def test_update_order_status_to_cancelled(self, cap_client):
        client, _ = cap_client
        created = _create_order(client, order_number="ORD-CANCEL-001").json()
        order_id = created["id"]

        resp = client.patch(
            f"/api/capacity/orders/{order_id}/status?client_id={CLIENT_ID}&new_status=CANCELLED"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"


class TestOrderScheduling:
    """GET /api/capacity/orders/scheduling"""

    def test_scheduling_no_confirmed_orders(self, cap_client):
        client, _ = cap_client
        # Create a DRAFT order (should not appear in scheduling)
        _create_order(client, order_number="ORD-DRAFT-001", status="DRAFT")

        resp = client.get(
            f"/api/capacity/orders/scheduling?client_id={CLIENT_ID}"
            f"&start_date={date.today().isoformat()}"
            f"&end_date={(date.today() + timedelta(days=60)).isoformat()}"
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_scheduling_with_confirmed_orders(self, cap_client):
        client, _ = cap_client
        _create_order(client, order_number="ORD-SCHED-001", status="CONFIRMED")
        _create_order(client, order_number="ORD-SCHED-002", status="CONFIRMED")
        _create_order(client, order_number="ORD-SCHED-003", status="DRAFT")

        resp = client.get(
            f"/api/capacity/orders/scheduling?client_id={CLIENT_ID}"
            f"&start_date={date.today().isoformat()}"
            f"&end_date={(date.today() + timedelta(days=60)).isoformat()}"
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only CONFIRMED orders should appear
        assert len(data) == 2
        statuses = {o["status"] for o in data}
        assert statuses == {"CONFIRMED"}


class TestOrderDelete:
    """DELETE /api/capacity/orders/{order_id}"""

    def test_delete_order_success(self, cap_client):
        client, _ = cap_client
        created = _create_order(client, order_number="ORD-DEL-001").json()
        order_id = created["id"]

        resp = client.delete(f"/api/capacity/orders/{order_id}?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Order deleted"

        # Verify gone
        resp2 = client.get(f"/api/capacity/orders/{order_id}?client_id={CLIENT_ID}")
        assert resp2.status_code == 404

    def test_delete_order_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.delete(f"/api/capacity/orders/99999?client_id={CLIENT_ID}")
        assert resp.status_code == 404


# =============================================================================
# Standards CRUD Tests
# =============================================================================

class TestStandardCreate:
    """POST /api/capacity/standards"""

    def test_create_standard_success(self, cap_client):
        client, _ = cap_client
        resp = _create_standard(client, style_code="STY-01", operation_code="OP-10")
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == CLIENT_ID
        assert data["style_code"] == "STY-01"
        assert data["operation_code"] == "OP-10"
        assert data["sam_minutes"] == 2.5
        assert data["department"] == "SEWING"

    def test_create_standard_minimal(self, cap_client):
        client, _ = cap_client
        resp = client.post(
            f"/api/capacity/standards?client_id={CLIENT_ID}",
            json={
                "style_code": "STY-MIN",
                "operation_code": "OP-MIN",
                "sam_minutes": 1.0,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["setup_time_minutes"] == 0
        assert data["machine_time_minutes"] == 0
        assert data["manual_time_minutes"] == 0

    def test_create_standard_missing_sam(self, cap_client):
        client, _ = cap_client
        resp = client.post(
            f"/api/capacity/standards?client_id={CLIENT_ID}",
            json={"style_code": "STY-X", "operation_code": "OP-X"},
        )
        assert resp.status_code == 422


class TestStandardList:
    """GET /api/capacity/standards"""

    def test_list_standards_empty(self, cap_client):
        client, _ = cap_client
        resp = client.get(f"/api/capacity/standards?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_standards_with_data(self, cap_client):
        client, _ = cap_client
        _create_standard(client, style_code="S1", operation_code="O1")
        _create_standard(client, style_code="S1", operation_code="O2")
        _create_standard(client, style_code="S2", operation_code="O1")

        resp = client.get(f"/api/capacity/standards?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_standards_department_filter(self, cap_client):
        client, _ = cap_client
        _create_standard(client, style_code="SD1", operation_code="OD1", department="SEWING")
        _create_standard(client, style_code="SD2", operation_code="OD2", department="CUTTING")

        resp = client.get(
            f"/api/capacity/standards?client_id={CLIENT_ID}&department=CUTTING"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["department"] == "CUTTING"


class TestStandardGetSingle:
    """GET /api/capacity/standards/{standard_id}"""

    def test_get_standard_success(self, cap_client):
        client, _ = cap_client
        created = _create_standard(client, style_code="SG-1", operation_code="OG-1").json()
        standard_id = created["id"]

        resp = client.get(
            f"/api/capacity/standards/{standard_id}?client_id={CLIENT_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["style_code"] == "SG-1"

    def test_get_standard_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.get(f"/api/capacity/standards/99999?client_id={CLIENT_ID}")
        assert resp.status_code == 404


class TestStandardByStyle:
    """GET /api/capacity/standards/style/{style_code}"""

    def test_get_standards_by_style(self, cap_client):
        client, _ = cap_client
        _create_standard(client, style_code="MATCH-STY", operation_code="OP-A")
        _create_standard(client, style_code="MATCH-STY", operation_code="OP-B")
        _create_standard(client, style_code="OTHER-STY", operation_code="OP-C")

        resp = client.get(
            f"/api/capacity/standards/style/MATCH-STY?client_id={CLIENT_ID}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(s["style_code"] == "MATCH-STY" for s in data)

    def test_get_standards_by_style_empty(self, cap_client):
        client, _ = cap_client
        resp = client.get(
            f"/api/capacity/standards/style/NONEXISTENT?client_id={CLIENT_ID}"
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestStandardTotalSAM:
    """GET /api/capacity/standards/style/{style_code}/total-sam"""

    def test_total_sam_returns_sum(self, cap_client):
        """Total SAM endpoint sums all operations for a style."""
        client, _ = cap_client
        _create_standard(client, style_code="SAM-STY", operation_code="OP-1", sam_minutes=3.0)
        _create_standard(client, style_code="SAM-STY", operation_code="OP-2", sam_minutes=4.5)

        resp = client.get(
            f"/api/capacity/standards/style/SAM-STY/total-sam?client_id={CLIENT_ID}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["style_code"] == "SAM-STY"
        assert data["total_sam_minutes"] == 7.5

    def test_total_sam_with_department_filter(self, cap_client):
        """Total SAM endpoint filters by department when provided."""
        client, _ = cap_client
        _create_standard(client, style_code="SAM-DEP", operation_code="OP-1", sam_minutes=3.0, department="SEWING")
        _create_standard(client, style_code="SAM-DEP", operation_code="OP-2", sam_minutes=4.0, department="CUTTING")

        resp = client.get(
            f"/api/capacity/standards/style/SAM-DEP/total-sam?client_id={CLIENT_ID}&department=SEWING"
        )
        assert resp.status_code == 200
        assert resp.json()["total_sam_minutes"] == 3.0

    def test_total_sam_no_standards(self, cap_client):
        """Total SAM returns 0 when no standards exist for style."""
        client, _ = cap_client
        resp = client.get(
            f"/api/capacity/standards/style/NONEXISTENT/total-sam?client_id={CLIENT_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["total_sam_minutes"] == 0


class TestStandardUpdate:
    """PUT /api/capacity/standards/{standard_id}"""

    def test_update_standard_success(self, cap_client):
        client, _ = cap_client
        created = _create_standard(client, style_code="SU-1", operation_code="OU-1").json()
        standard_id = created["id"]

        resp = client.put(
            f"/api/capacity/standards/{standard_id}?client_id={CLIENT_ID}",
            json={"sam_minutes": 5.0, "operation_name": "Updated Op"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sam_minutes"] == 5.0
        assert data["operation_name"] == "Updated Op"

    def test_update_standard_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.put(
            f"/api/capacity/standards/99999?client_id={CLIENT_ID}",
            json={"sam_minutes": 1.0},
        )
        assert resp.status_code == 404

    def test_update_standard_partial(self, cap_client):
        client, _ = cap_client
        created = _create_standard(
            client, style_code="SP-1", operation_code="OP-P1", sam_minutes=3.0
        ).json()
        standard_id = created["id"]

        resp = client.put(
            f"/api/capacity/standards/{standard_id}?client_id={CLIENT_ID}",
            json={"notes": "partial update only"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "partial update only"
        assert data["sam_minutes"] == 3.0  # unchanged


class TestStandardDelete:
    """DELETE /api/capacity/standards/{standard_id}"""

    def test_delete_standard_success(self, cap_client):
        client, _ = cap_client
        created = _create_standard(client, style_code="DEL-S", operation_code="DEL-O").json()
        standard_id = created["id"]

        resp = client.delete(
            f"/api/capacity/standards/{standard_id}?client_id={CLIENT_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Standard deleted"

        # Verify gone
        resp2 = client.get(
            f"/api/capacity/standards/{standard_id}?client_id={CLIENT_ID}"
        )
        assert resp2.status_code == 404

    def test_delete_standard_not_found(self, cap_client):
        client, _ = cap_client
        resp = client.delete(f"/api/capacity/standards/99999?client_id={CLIENT_ID}")
        assert resp.status_code == 404


# =============================================================================
# Multi-Tenant Isolation Tests
# =============================================================================

class TestMultiTenantIsolation:
    """Verify that data from one client does not leak to another."""

    def test_calendar_tenant_isolation(self, cap_db):
        """Calendar entries for client A should not appear for client B."""
        db = cap_db
        TestDataFactory.create_client(db, client_id="CLIENT-A", client_type=ClientType.HOURLY_RATE)
        TestDataFactory.create_client(db, client_id="CLIENT-B", client_type=ClientType.HOURLY_RATE)
        db.commit()

        app = create_test_app(db)
        tc = TestClient(app)

        # Create entries for CLIENT-A
        tc.post("/api/capacity/calendar?client_id=CLIENT-A", json={
            "calendar_date": "2026-06-01",
            "is_working_day": True,
            "shifts_available": 1,
            "shift1_hours": 8.0,
            "shift2_hours": 0,
            "shift3_hours": 0,
        })

        # CLIENT-B should see no entries
        resp = tc.get("/api/capacity/calendar?client_id=CLIENT-B")
        assert resp.status_code == 200
        assert resp.json() == []

        # CLIENT-A should see its entry
        resp_a = tc.get("/api/capacity/calendar?client_id=CLIENT-A")
        assert resp_a.status_code == 200
        assert len(resp_a.json()) == 1

    def test_orders_tenant_isolation(self, cap_db):
        """Orders for client A should not appear for client B."""
        db = cap_db
        TestDataFactory.create_client(db, client_id="ISO-A", client_type=ClientType.HOURLY_RATE)
        TestDataFactory.create_client(db, client_id="ISO-B", client_type=ClientType.HOURLY_RATE)
        db.commit()

        app = create_test_app(db)
        tc = TestClient(app)

        tc.post("/api/capacity/orders?client_id=ISO-A", json={
            "order_number": "ORD-ISO-001",
            "style_code": "STY-ISO",
            "order_quantity": 100,
            "required_date": (date.today() + timedelta(days=30)).isoformat(),
        })

        resp = tc.get("/api/capacity/orders?client_id=ISO-B")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lines_tenant_isolation(self, cap_db):
        """Production lines for client A should not appear for client B."""
        db = cap_db
        TestDataFactory.create_client(db, client_id="LINE-A", client_type=ClientType.HOURLY_RATE)
        TestDataFactory.create_client(db, client_id="LINE-B", client_type=ClientType.HOURLY_RATE)
        db.commit()

        app = create_test_app(db)
        tc = TestClient(app)

        tc.post("/api/capacity/lines?client_id=LINE-A", json={
            "line_code": "L-ISOL",
            "line_name": "Isolated Line",
        })

        resp = tc.get("/api/capacity/lines?client_id=LINE-B")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_standards_tenant_isolation(self, cap_db):
        """Standards for client A should not appear for client B."""
        db = cap_db
        TestDataFactory.create_client(db, client_id="STD-A", client_type=ClientType.HOURLY_RATE)
        TestDataFactory.create_client(db, client_id="STD-B", client_type=ClientType.HOURLY_RATE)
        db.commit()

        app = create_test_app(db)
        tc = TestClient(app)

        tc.post("/api/capacity/standards?client_id=STD-A", json={
            "style_code": "ISO-STY",
            "operation_code": "ISO-OP",
            "sam_minutes": 2.0,
        })

        resp = tc.get("/api/capacity/standards?client_id=STD-B")
        assert resp.status_code == 200
        assert resp.json() == []


# =============================================================================
# Edge Case & Validation Tests
# =============================================================================

class TestEdgeCases:
    """Edge cases and data integrity checks."""

    def test_create_order_all_priority_values(self, cap_client):
        """All OrderPriority enum values are valid."""
        client, _ = cap_client
        for i, priority in enumerate(["LOW", "NORMAL", "HIGH", "URGENT"]):
            resp = _create_order(
                client,
                order_number=f"ORD-PRI-{priority}",
                priority=priority,
            )
            assert resp.status_code == 201, f"Priority {priority} failed"
            assert resp.json()["priority"] == priority

    def test_create_order_all_status_values(self, cap_client):
        """All OrderStatus enum values are valid for creation."""
        client, _ = cap_client
        for status_val in ["DRAFT", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]:
            resp = _create_order(
                client,
                order_number=f"ORD-STS-{status_val}",
                status=status_val,
            )
            assert resp.status_code == 201, f"Status {status_val} failed"
            assert resp.json()["status"] == status_val

    def test_calendar_entry_with_three_shifts(self, cap_client):
        """Calendar with three shifts fully populated."""
        client, _ = cap_client
        resp = _create_calendar_entry(
            client,
            cal_date=date(2026, 7, 1),
            shifts_available=3,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=6.0,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["shifts_available"] == 3
        assert data["shift3_hours"] == 6.0

    def test_production_line_efficiency_boundaries(self, cap_client):
        """Efficiency factor at boundaries."""
        client, _ = cap_client
        resp = _create_production_line(
            client,
            code="LINE-EFF",
            efficiency_factor=1.0,
            absenteeism_factor=0.0,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["efficiency_factor"] == 1.0
        assert data["absenteeism_factor"] == 0.0

    def test_standard_with_zero_sam(self, cap_client):
        """Standard with zero SAM should be accepted (valid data)."""
        client, _ = cap_client
        resp = _create_standard(
            client,
            style_code="ZERO-STY",
            operation_code="ZERO-OP",
            sam_minutes=0.0,
        )
        assert resp.status_code == 201
        assert resp.json()["sam_minutes"] == 0.0

    def test_order_with_large_quantity(self, cap_client):
        """Order with a very large quantity."""
        client, _ = cap_client
        resp = _create_order(
            client,
            order_number="ORD-BIG",
            order_quantity=999999,
        )
        assert resp.status_code == 201
        assert resp.json()["order_quantity"] == 999999

    def test_update_then_get_reflects_changes(self, cap_client):
        """Ensure GET after PUT returns updated data."""
        client, _ = cap_client
        created = _create_production_line(client, code="LINE-RTN").json()
        line_id = created["id"]

        client.put(
            f"/api/capacity/lines/{line_id}?client_id={CLIENT_ID}",
            json={"max_operators": 25},
        )

        resp = client.get(f"/api/capacity/lines/{line_id}?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json()["max_operators"] == 25

    def test_delete_then_list_excludes_deleted(self, cap_client):
        """Ensure list no longer contains a hard-deleted entity."""
        client, _ = cap_client
        created = _create_order(client, order_number="ORD-GONE").json()
        order_id = created["id"]

        client.delete(f"/api/capacity/orders/{order_id}?client_id={CLIENT_ID}")

        resp = client.get(f"/api/capacity/orders?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        ids = [o["id"] for o in resp.json()]
        assert order_id not in ids

    def test_create_multiple_calendar_entries_different_dates(self, cap_client):
        """Creating multiple entries on different dates works."""
        client, _ = cap_client
        for i in range(7):
            resp = _create_calendar_entry(
                client, cal_date=date(2026, 8, 1) + timedelta(days=i)
            )
            assert resp.status_code == 201

        resp = client.get(f"/api/capacity/calendar?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        assert len(resp.json()) == 7

    def test_order_status_patch_all_transitions(self, cap_client):
        """Test status transitions through the lifecycle."""
        client, _ = cap_client
        created = _create_order(client, order_number="ORD-LIFE-001").json()
        order_id = created["id"]

        for new_status in ["CONFIRMED", "IN_PROGRESS", "COMPLETED"]:
            resp = client.patch(
                f"/api/capacity/orders/{order_id}/status?client_id={CLIENT_ID}"
                f"&new_status={new_status}"
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == new_status
