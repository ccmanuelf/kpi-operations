"""
Tests for Onboarding API routes.
Uses real in-memory SQLite database -- NO mocks for DB layer.
"""

import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.auth.jwt import get_current_user
from backend.orm.user import User
from backend.orm.capacity.orders import CapacityOrder, OrderStatus, OrderPriority
from backend.routes.onboarding import router as onboarding_router
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test App Factory and Fixtures
# =============================================================================

CLIENT_ID = "ONBOARD-C1"
OTHER_CLIENT_ID = "ONBOARD-C2"


def _create_test_app(db_session, role="operator", client_id=CLIENT_ID):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(onboarding_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    mock_user = User(
        user_id=f"test-onboard-{role}-001",
        username=f"onboard_test_{role}",
        email=f"onboard_{role}@test.com",
        role=role,
        client_id_assigned=client_id if role not in ("admin", "poweruser") else None,
        is_active=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user

    return app


@pytest.fixture(scope="function")
def onboard_db():
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
def operator_client(onboard_db):
    """TestClient authenticated as operator with CLIENT_ID."""
    TestDataFactory.create_client(onboard_db, client_id=CLIENT_ID, client_name="Onboarding Test Client")
    onboard_db.commit()
    app = _create_test_app(onboard_db, role="operator", client_id=CLIENT_ID)
    return TestClient(app), onboard_db


@pytest.fixture
def admin_client(onboard_db):
    """TestClient authenticated as admin (no client_id_assigned)."""
    TestDataFactory.create_client(onboard_db, client_id=CLIENT_ID, client_name="Onboarding Test Client")
    TestDataFactory.create_client(onboard_db, client_id=OTHER_CLIENT_ID, client_name="Other Client")
    onboard_db.commit()
    app = _create_test_app(onboard_db, role="admin")
    return TestClient(app), onboard_db


# =============================================================================
# Helper: Seed data for onboarding steps
# =============================================================================


def _seed_shift(db):
    """Seed a shift for CLIENT_ID."""
    return TestDataFactory.create_shift(db, client_id=CLIENT_ID, shift_name="Day Shift")


def _seed_product(db):
    """Seed a product for CLIENT_ID."""
    return TestDataFactory.create_product(db, client_id=CLIENT_ID)


def _seed_work_order(db):
    """Seed a work order for CLIENT_ID."""
    return TestDataFactory.create_work_order(db, client_id=CLIENT_ID)


def _seed_production_entry(db, product, shift):
    """Seed a production entry for CLIENT_ID."""
    return TestDataFactory.create_production_entry(
        db,
        client_id=CLIENT_ID,
        product_id=product.product_id,
        shift_id=shift.shift_id,
        entered_by="test-onboard-operator-001",
    )


def _seed_capacity_order(db):
    """Seed a capacity order for CLIENT_ID directly (no factory method)."""
    from datetime import date

    order = CapacityOrder(
        client_id=CLIENT_ID,
        order_number=f"CAP-ORD-{CLIENT_ID}-001",
        style_model="TEST-STYLE-001",
        order_quantity=100,
        order_date=date.today(),
        required_date=date.today(),
        status=OrderStatus.DRAFT,
        priority=OrderPriority.NORMAL,
    )
    db.add(order)
    db.flush()
    return order


# =============================================================================
# Tests: GET /api/onboarding/status
# =============================================================================


class TestOnboardingStatusEmpty:
    """Tests with an empty client (no data seeded)."""

    def test_returns_all_steps_false_for_empty_client(self, operator_client):
        """All onboarding steps should be false when no data exists."""
        client, _ = operator_client
        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})

        assert resp.status_code == 200
        data = resp.json()

        assert data["steps"]["shifts_configured"] is False
        assert data["steps"]["products_added"] is False
        assert data["steps"]["work_orders_created"] is False
        assert data["steps"]["production_data_entered"] is False
        assert data["steps"]["capacity_plan_created"] is False

        assert data["completed_count"] == 0
        assert data["total_steps"] == 5
        assert data["all_complete"] is False

    def test_returns_five_steps(self, operator_client):
        """Response should always contain exactly 5 steps."""
        client, _ = operator_client
        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})

        assert resp.status_code == 200
        assert len(resp.json()["steps"]) == 5

    def test_operator_uses_assigned_client_when_no_param(self, operator_client):
        """Operator should fall back to their assigned client_id."""
        client, _ = operator_client
        resp = client.get("/api/onboarding/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_steps"] == 5
        assert data["completed_count"] == 0


class TestOnboardingStatusPopulated:
    """Tests with seeded data to verify step completion detection."""

    def test_shift_configured_shows_true(self, operator_client):
        """shifts_configured should be True when shifts exist."""
        client, db = operator_client
        _seed_shift(db)
        db.commit()

        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})
        assert resp.status_code == 200
        assert resp.json()["steps"]["shifts_configured"] is True
        assert resp.json()["completed_count"] == 1

    def test_product_added_shows_true(self, operator_client):
        """products_added should be True when products exist."""
        client, db = operator_client
        _seed_product(db)
        db.commit()

        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})
        assert resp.status_code == 200
        assert resp.json()["steps"]["products_added"] is True

    def test_work_order_created_shows_true(self, operator_client):
        """work_orders_created should be True when work orders exist."""
        client, db = operator_client
        _seed_work_order(db)
        db.commit()

        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})
        assert resp.status_code == 200
        assert resp.json()["steps"]["work_orders_created"] is True

    def test_production_data_entered_shows_true(self, operator_client):
        """production_data_entered should be True when production entries exist."""
        client, db = operator_client
        product = _seed_product(db)
        shift = _seed_shift(db)
        _seed_production_entry(db, product, shift)
        db.commit()

        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})
        assert resp.status_code == 200
        assert resp.json()["steps"]["production_data_entered"] is True

    def test_capacity_plan_created_shows_true(self, operator_client):
        """capacity_plan_created should be True when capacity orders exist."""
        client, db = operator_client
        _seed_capacity_order(db)
        db.commit()

        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})
        assert resp.status_code == 200
        assert resp.json()["steps"]["capacity_plan_created"] is True

    def test_all_complete_when_all_data_exists(self, operator_client):
        """all_complete should be True when all 5 steps have data."""
        client, db = operator_client

        shift = _seed_shift(db)
        product = _seed_product(db)
        _seed_work_order(db)
        _seed_production_entry(db, product, shift)
        _seed_capacity_order(db)
        db.commit()

        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})
        assert resp.status_code == 200

        data = resp.json()
        assert data["completed_count"] == 5
        assert data["total_steps"] == 5
        assert data["all_complete"] is True
        assert all(data["steps"].values())


class TestOnboardingAuth:
    """Tests for authentication and authorization."""

    def test_unauthenticated_returns_422_without_override(self, onboard_db):
        """Without auth override, endpoint should fail (no token)."""
        TestDataFactory.create_client(onboard_db, client_id=CLIENT_ID, client_name="Auth Test")
        onboard_db.commit()

        # Create app WITHOUT dependency overrides for auth
        app = FastAPI()
        app.include_router(onboarding_router)

        def override_get_db():
            try:
                yield onboard_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        # NOTE: get_current_user NOT overridden — will require real token

        test_client = TestClient(app)
        resp = test_client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})

        # Without a valid token, should get 401
        assert resp.status_code == 401

    def test_admin_requires_client_id_param(self, admin_client):
        """Admin users (no client_id_assigned) must provide client_id."""
        client, _ = admin_client
        resp = client.get("/api/onboarding/status")

        assert resp.status_code == 400
        assert "client_id" in resp.json()["detail"].lower()

    def test_admin_with_client_id_succeeds(self, admin_client):
        """Admin can query any client's onboarding status."""
        client, _ = admin_client
        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})

        assert resp.status_code == 200
        assert resp.json()["total_steps"] == 5


class TestOnboardingClientIsolation:
    """Tests for multi-tenant data isolation."""

    def test_data_from_other_client_not_visible(self, operator_client):
        """Data from another client should not affect onboarding status."""
        client, db = operator_client

        # Seed data for OTHER client
        TestDataFactory.create_client(db, client_id=OTHER_CLIENT_ID, client_name="Other Client")
        TestDataFactory.create_shift(db, client_id=OTHER_CLIENT_ID, shift_name="Other Shift")
        TestDataFactory.create_product(db, client_id=OTHER_CLIENT_ID)
        db.commit()

        # Query for OUR client -- should still be empty
        resp = client.get("/api/onboarding/status", params={"client_id": CLIENT_ID})
        assert resp.status_code == 200
        assert resp.json()["completed_count"] == 0
        assert resp.json()["steps"]["shifts_configured"] is False
        assert resp.json()["steps"]["products_added"] is False
