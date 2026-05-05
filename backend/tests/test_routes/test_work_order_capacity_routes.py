"""
Tests for Work Order <-> Capacity Order cross-reference API routes (Task 3.1).
Uses real in-memory SQLite database -- NO mocks for DB layer.
Follows the pattern from test_production_line_bridge_routes.py.
"""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User
from backend.orm.work_order import WorkOrder
from backend.orm.capacity.orders import CapacityOrder, OrderStatus, OrderPriority
from backend.routes.work_orders import router as work_orders_router
from backend.routes.capacity import router as capacity_router
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test App Factory and Fixtures
# =============================================================================

CLIENT_ID = "WO-CAP-RT-C1"


def _create_test_app(db_session, role="admin"):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(work_orders_router)
    app.include_router(capacity_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    mock_user = User(
        user_id="test-wocap-001",
        username="wocap_test_admin",
        email="wocap_admin@test.com",
        role=role,
        client_id_assigned=None if role == "admin" else CLIENT_ID,
        is_active=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_active_supervisor] = lambda: mock_user

    return app


@pytest.fixture(scope="function")
def wocap_db():
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
def admin_client(wocap_db):
    """TestClient authenticated as admin."""
    TestDataFactory.create_client(wocap_db, client_id=CLIENT_ID, client_name="WO-Cap Route Test Client")
    wocap_db.commit()
    app = _create_test_app(wocap_db, role="admin")
    return TestClient(app), wocap_db


def _create_capacity_order(db, client_id=CLIENT_ID, order_number="CO-001", **kwargs):
    """Create a CapacityOrder directly in the DB."""
    cap_order = CapacityOrder(
        client_id=client_id,
        order_number=order_number,
        style_model=kwargs.get("style_model", "STYLE-001"),
        order_quantity=kwargs.get("order_quantity", 1000),
        required_date=kwargs.get("required_date", date(2026, 6, 1)),
        priority=kwargs.get("priority", OrderPriority.NORMAL),
        status=kwargs.get("status", OrderStatus.CONFIRMED),
    )
    db.add(cap_order)
    db.commit()
    db.refresh(cap_order)
    return cap_order


def _create_work_order(db, client_id=CLIENT_ID, work_order_id="WO-RT-001", **kwargs):
    """Create a WorkOrder directly in the DB."""
    wo = WorkOrder(
        work_order_id=work_order_id,
        client_id=client_id,
        style_model=kwargs.get("style_model", "STYLE-001"),
        planned_quantity=kwargs.get("planned_quantity", 500),
        actual_quantity=kwargs.get("actual_quantity", 0),
        status=kwargs.get("status", "RECEIVED"),
        capacity_order_id=kwargs.get("capacity_order_id"),
        origin=kwargs.get("origin", "AD_HOC"),
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


# ============================================================================
# TestGetCapacityOrderForWorkOrder (route)
# ============================================================================
class TestGetCapacityOrderForWorkOrderRoute:
    """Tests for GET /api/work-orders/{id}/capacity-order"""

    def test_linked(self, admin_client):
        """Returns capacity order details when work order is linked."""
        client, db = admin_client
        cap_order = _create_capacity_order(db, order_number="CO-RT-LINK-001")
        _create_work_order(
            db,
            work_order_id="WO-RT-LINK-001",
            capacity_order_id=cap_order.id,
            origin="PLANNED",
        )

        response = client.get("/api/work-orders/WO-RT-LINK-001/capacity-order")
        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is True
        assert data["capacity_order"]["id"] == cap_order.id
        assert data["capacity_order"]["order_number"] == "CO-RT-LINK-001"

    def test_not_linked(self, admin_client):
        """Returns linked=false when work order has no capacity link."""
        client, db = admin_client
        _create_work_order(db, work_order_id="WO-RT-ADHOC-001")

        response = client.get("/api/work-orders/WO-RT-ADHOC-001/capacity-order")
        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is False
        assert data["capacity_order"] is None


# ============================================================================
# TestLinkWorkOrderToCapacity (route)
# ============================================================================
class TestLinkWorkOrderToCapacityRoute:
    """Tests for POST /api/work-orders/{id}/link-capacity"""

    def test_link_success(self, admin_client):
        """Successfully link a work order to a capacity order via API."""
        client, db = admin_client
        cap_order = _create_capacity_order(db, order_number="CO-RT-LNK-001")
        _create_work_order(db, work_order_id="WO-RT-LNK-001")

        response = client.post(
            "/api/work-orders/WO-RT-LNK-001/link-capacity",
            json={"capacity_order_id": cap_order.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["capacity_order_id"] == cap_order.id
        assert data["origin"] == "PLANNED"

    def test_link_missing_capacity_order_id(self, admin_client):
        """Returns 400 when capacity_order_id is missing."""
        client, db = admin_client
        _create_work_order(db, work_order_id="WO-RT-LNK-002")

        response = client.post(
            "/api/work-orders/WO-RT-LNK-002/link-capacity",
            json={},
        )
        assert response.status_code == 400
        assert "capacity_order_id" in response.json()["detail"]


# ============================================================================
# TestUnlinkWorkOrderFromCapacity (route)
# ============================================================================
class TestUnlinkWorkOrderFromCapacityRoute:
    """Tests for POST /api/work-orders/{id}/unlink-capacity"""

    def test_unlink_success(self, admin_client):
        """Successfully unlink a work order from its capacity order via API."""
        client, db = admin_client
        cap_order = _create_capacity_order(db, order_number="CO-RT-UNL-001")
        _create_work_order(
            db,
            work_order_id="WO-RT-UNL-001",
            capacity_order_id=cap_order.id,
            origin="PLANNED",
        )

        response = client.post("/api/work-orders/WO-RT-UNL-001/unlink-capacity")
        assert response.status_code == 200
        data = response.json()
        assert data["capacity_order_id"] is None
        assert data["origin"] == "AD_HOC"


# ============================================================================
# TestGetCapacityOrderWorkOrders (capacity route)
# ============================================================================
class TestGetCapacityOrderWorkOrdersRoute:
    """Tests for GET /api/capacity/orders/{order_id}/work-orders"""

    def test_returns_linked_work_orders(self, admin_client):
        """Returns work orders linked to a capacity order."""
        client, db = admin_client
        cap_order = _create_capacity_order(db, order_number="CO-RT-WO-001")
        _create_work_order(
            db,
            work_order_id="WO-RT-WO-001",
            capacity_order_id=cap_order.id,
            origin="PLANNED",
        )
        _create_work_order(
            db,
            work_order_id="WO-RT-WO-002",
            capacity_order_id=cap_order.id,
            origin="PLANNED",
        )

        response = client.get(f"/api/capacity/orders/{cap_order.id}/work-orders")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        wo_ids = {wo["work_order_id"] for wo in data}
        assert wo_ids == {"WO-RT-WO-001", "WO-RT-WO-002"}

    def test_returns_empty_for_no_linked(self, admin_client):
        """Returns empty list when no work orders are linked."""
        client, db = admin_client
        cap_order = _create_capacity_order(db, order_number="CO-RT-EMPTY-001")

        response = client.get(f"/api/capacity/orders/{cap_order.id}/work-orders")
        assert response.status_code == 200
        data = response.json()
        assert data == []
