"""
Plan vs Actual Route Tests
Tests the API endpoints for plan vs actual comparison.

Uses real in-memory SQLite database -- NO mocks for DB layer.
Follows the pattern from test_capacity_routes_crud.py (isolated FastAPI app).
"""

import pytest
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.orm.client import Client, ClientType
from backend.orm.capacity.orders import CapacityOrder, OrderStatus, OrderPriority
from backend.orm.work_order import WorkOrder, WorkOrderStatus
from backend.orm.production_entry import ProductionEntry
from backend.orm.user import User, UserRole
from backend.orm.product import Product
from backend.orm.shift import Shift
from backend.auth.jwt import get_current_user
from backend.routes.plan_vs_actual import router as plan_vs_actual_router
from backend.tests.fixtures.factories import TestDataFactory


# ---------------------------------------------------------------------------
# Test App Factory and Fixtures
# ---------------------------------------------------------------------------

CLIENT_ID = "PVA-ROUTE-CLIENT"


def create_test_app(db_session, user_override=None):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(plan_vs_actual_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    mock_user = user_override or User(
        user_id="pva-route-admin-001",
        username="pva_route_admin",
        email="pva_admin@test.com",
        role=UserRole.ADMIN.value,
        client_id_assigned=None,
        is_active=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return app


def create_unauthenticated_app(db_session):
    """Create a FastAPI test app WITHOUT auth overrides (to test 401)."""
    app = FastAPI()
    app.include_router(plan_vs_actual_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Do NOT override get_current_user -- requires real Bearer token
    return app


@pytest.fixture(scope="function")
def pva_route_db():
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
def route_client(pva_route_db):
    """Create test client entity and return (TestClient, db)."""
    db = pva_route_db
    TestDataFactory.create_client(
        db,
        client_id=CLIENT_ID,
        client_name="PVA Route Test Client",
        client_type=ClientType.HOURLY_RATE,
    )
    db.commit()
    app = create_test_app(db)
    return TestClient(app), db


def _create_capacity_order(db, client_id, **overrides):
    """Helper to create a CapacityOrder with sensible defaults."""
    defaults = {
        "client_id": client_id,
        "order_number": f"CPL-{TestDataFactory._next_id('CPL')}",
        "style_model": "ROUTE-STYLE",
        "order_quantity": 1000,
        "required_date": date.today() + timedelta(days=30),
        "status": OrderStatus.CONFIRMED,
        "priority": OrderPriority.NORMAL,
    }
    defaults.update(overrides)
    cap_order = CapacityOrder(**defaults)
    db.add(cap_order)
    db.flush()
    return cap_order


def _create_linked_work_order(db, cap_order, actual_quantity=0, **overrides):
    """Create a WorkOrder linked to a CapacityOrder."""
    wo_id = TestDataFactory._next_id("WO")
    defaults = {
        "work_order_id": wo_id,
        "client_id": cap_order.client_id,
        "style_model": cap_order.style_model,
        "planned_quantity": cap_order.order_quantity,
        "actual_quantity": actual_quantity,
        "capacity_order_id": cap_order.id,
        "origin": "PLANNED",
        "status": WorkOrderStatus.IN_PROGRESS,
        "received_date": datetime.now(tz=timezone.utc),
    }
    defaults.update(overrides)
    wo = WorkOrder(**defaults)
    db.add(wo)
    db.flush()
    return wo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPlanVsActualEndpoint:
    """Test GET /api/plan-vs-actual."""

    def test_plan_vs_actual_endpoint_returns_data(self, route_client):
        """GET /api/plan-vs-actual returns data for existing orders."""
        client, db = route_client
        cap = _create_capacity_order(db, CLIENT_ID, order_quantity=500)
        wo = _create_linked_work_order(db, cap, actual_quantity=250)
        db.commit()

        response = client.get(f"/api/plan-vs-actual?client_id={CLIENT_ID}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["capacity_order_id"] == cap.id
        assert data[0]["planned_quantity"] == 500
        assert data[0]["actual_completed"] == 250
        assert data[0]["linked_work_orders"] == 1

    def test_plan_vs_actual_with_query_filters(self, route_client):
        """Query params filter results correctly."""
        client, db = route_client
        today = date.today()

        cap_in_range = _create_capacity_order(
            db, CLIENT_ID, required_date=today + timedelta(days=10)
        )
        _create_capacity_order(
            db, CLIENT_ID, required_date=today + timedelta(days=60)
        )
        db.commit()

        response = client.get(
            f"/api/plan-vs-actual"
            f"?client_id={CLIENT_ID}"
            f"&start_date={today.isoformat()}"
            f"&end_date={(today + timedelta(days=20)).isoformat()}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["capacity_order_id"] == cap_in_range.id

    def test_plan_vs_actual_with_status_filter(self, route_client):
        """Status query param filters correctly."""
        client, db = route_client
        draft = _create_capacity_order(db, CLIENT_ID, status=OrderStatus.DRAFT)
        _create_capacity_order(db, CLIENT_ID, status=OrderStatus.CONFIRMED)
        db.commit()

        response = client.get(
            f"/api/plan-vs-actual?client_id={CLIENT_ID}&status=DRAFT"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "DRAFT"

    def test_plan_vs_actual_empty(self, route_client):
        """Returns empty list when no matching data."""
        client, db = route_client
        # No capacity orders created
        response = client.get(f"/api/plan-vs-actual?client_id={CLIENT_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestPlanVsActualSummaryEndpoint:
    """Test GET /api/plan-vs-actual/summary."""

    def test_plan_vs_actual_summary_endpoint(self, route_client):
        """GET /api/plan-vs-actual/summary returns aggregate data."""
        client, db = route_client
        cap1 = _create_capacity_order(db, CLIENT_ID, order_quantity=100)
        _create_linked_work_order(db, cap1, actual_quantity=100)
        cap2 = _create_capacity_order(db, CLIENT_ID, order_quantity=200)
        db.commit()

        response = client.get(
            f"/api/plan-vs-actual/summary?client_id={CLIENT_ID}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_orders"] == 2
        assert data["total_planned_quantity"] == 300
        assert data["total_actual_completed"] == 100
        assert data["overall_variance"] == -200
        assert "risk_distribution" in data
        assert "orders" in data
        assert len(data["orders"]) == 2


class TestPlanVsActualAuth:
    """Test authentication requirements."""

    def test_plan_vs_actual_requires_auth(self, pva_route_db):
        """401 without valid token."""
        db = pva_route_db
        TestDataFactory.create_client(
            db, client_id=CLIENT_ID, client_name="Auth Test"
        )
        db.commit()

        app = create_unauthenticated_app(db)
        unauthenticated_client = TestClient(app)

        response = unauthenticated_client.get("/api/plan-vs-actual")
        # Without a Bearer token, get_current_user dependency should fail with 401
        assert response.status_code == 401
