"""
Tests for Production Line Bridge API routes (Capacity Planning bridge).
Uses real in-memory SQLite database -- NO mocks for DB layer.
Follows the pattern from test_production_line_routes.py.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User
from backend.orm.production_line import ProductionLine
from backend.orm.capacity.production_lines import CapacityProductionLine
from backend.routes.production_lines import router as production_lines_router
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test App Factory and Fixtures
# =============================================================================

CLIENT_ID = "PLB-RT-C1"


def _create_test_app(db_session, role="supervisor"):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(production_lines_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    mock_user = User(
        user_id=f"test-plb-{role}-001",
        username=f"plb_test_{role}",
        email=f"plb_{role}@test.com",
        role=role,
        client_id_assigned=CLIENT_ID if role != "admin" else None,
        is_active=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user

    if role in ("supervisor", "admin"):
        app.dependency_overrides[get_current_active_supervisor] = lambda: mock_user

    return app


@pytest.fixture(scope="function")
def plb_db():
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
def supervisor_client(plb_db):
    """TestClient authenticated as supervisor."""
    TestDataFactory.create_client(plb_db, client_id=CLIENT_ID, client_name="PLB Route Test Client")
    plb_db.commit()
    app = _create_test_app(plb_db, role="supervisor")
    return TestClient(app), plb_db


@pytest.fixture
def operator_client(plb_db):
    """TestClient authenticated as operator (no write access)."""
    TestDataFactory.create_client(plb_db, client_id=CLIENT_ID, client_name="PLB Route Test Client")
    plb_db.commit()
    app = _create_test_app(plb_db, role="operator")
    return TestClient(app), plb_db


def _create_ops_line(db, line_code="SEW-01", line_name="Sewing Line 1", **kwargs):
    """Helper to seed an operational production line directly in the DB."""
    line = ProductionLine(
        client_id=CLIENT_ID,
        line_code=line_code,
        line_name=line_name,
        department=kwargs.get("department"),
        line_type=kwargs.get("line_type", "DEDICATED"),
        parent_line_id=kwargs.get("parent_line_id"),
        max_operators=kwargs.get("max_operators"),
        is_active=kwargs.get("is_active", True),
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _create_cap_line(db, line_code, client_id=CLIENT_ID, **kwargs):
    """Helper to seed a capacity production line directly in the DB."""
    cap_line = CapacityProductionLine(
        client_id=client_id,
        line_code=line_code,
        line_name=kwargs.get("line_name", f"Cap {line_code}"),
        department=kwargs.get("department"),
        is_active=kwargs.get("is_active", True),
    )
    db.add(cap_line)
    db.commit()
    db.refresh(cap_line)
    return cap_line


# ============================================================================
# TestLinkCapacityEndpoint
# ============================================================================
class TestLinkCapacityEndpoint:
    """Tests for POST /api/production-lines/{line_id}/link-capacity"""

    def test_link_success(self, supervisor_client):
        """Supervisor can link an operational line to a capacity line."""
        client, db = supervisor_client
        ops = _create_ops_line(db, "SEW-01", "Sewing 1")
        cap = _create_cap_line(db, "SEW-01")

        response = client.post(
            f"/api/production-lines/{ops.line_id}/link-capacity",
            json={"capacity_line_id": cap.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["capacity_line_id"] == cap.id
        assert data["line_code"] == "SEW-01"

    def test_link_not_found_ops_line(self, supervisor_client):
        """Linking nonexistent operational line returns 404."""
        client, db = supervisor_client
        cap = _create_cap_line(db, "SEW-01")

        response = client.post(
            "/api/production-lines/999999/link-capacity",
            json={"capacity_line_id": cap.id},
        )
        assert response.status_code == 404

    def test_link_bad_capacity_line(self, supervisor_client):
        """Linking to nonexistent capacity line returns 400."""
        client, db = supervisor_client
        ops = _create_ops_line(db, "SEW-01", "Sewing 1")

        response = client.post(
            f"/api/production-lines/{ops.line_id}/link-capacity",
            json={"capacity_line_id": 999999},
        )
        assert response.status_code == 400
        assert "does not exist" in response.json()["detail"]

    def test_link_requires_supervisor(self, operator_client):
        """Operator cannot link capacity lines."""
        client, db = operator_client
        ops = _create_ops_line(db, "SEW-01", "Sewing 1")
        cap = _create_cap_line(db, "SEW-01")

        response = client.post(
            f"/api/production-lines/{ops.line_id}/link-capacity",
            json={"capacity_line_id": cap.id},
        )
        assert response.status_code in (403, 500)


# ============================================================================
# TestUnlinkCapacityEndpoint
# ============================================================================
class TestUnlinkCapacityEndpoint:
    """Tests for DELETE /api/production-lines/{line_id}/link-capacity"""

    def test_unlink_success(self, supervisor_client):
        """Supervisor can unlink a capacity line."""
        client, db = supervisor_client
        ops = _create_ops_line(db, "SEW-01", "Sewing 1")
        cap = _create_cap_line(db, "SEW-01")

        # Link first
        ops.capacity_line_id = cap.id
        db.commit()

        response = client.delete(f"/api/production-lines/{ops.line_id}/link-capacity")
        assert response.status_code == 200
        data = response.json()
        assert data["capacity_line_id"] is None

    def test_unlink_not_found(self, supervisor_client):
        """Unlinking nonexistent line returns 404."""
        client, db = supervisor_client

        response = client.delete("/api/production-lines/999999/link-capacity")
        assert response.status_code == 404

    def test_unlink_requires_supervisor(self, operator_client):
        """Operator cannot unlink capacity lines."""
        client, db = operator_client
        ops = _create_ops_line(db, "SEW-01", "Sewing 1")

        response = client.delete(f"/api/production-lines/{ops.line_id}/link-capacity")
        assert response.status_code in (403, 500)


# ============================================================================
# TestSyncCapacityEndpoint
# ============================================================================
class TestSyncCapacityEndpoint:
    """Tests for POST /api/production-lines/sync-capacity"""

    def test_sync_matches(self, supervisor_client):
        """Auto-sync matches lines by line_code within the same client."""
        client, db = supervisor_client

        codes = ["SEW-01", "CUT-01", "INS-01"]
        for code in codes:
            _create_ops_line(db, code, f"Ops {code}")
            _create_cap_line(db, code)

        response = client.post(
            "/api/production-lines/sync-capacity",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matched"]) == 3
        assert len(data["unmatched"]) == 0

    def test_sync_partial_match(self, supervisor_client):
        """Sync returns matched and unmatched lists."""
        client, db = supervisor_client

        _create_ops_line(db, "SEW-01", "Sewing")
        _create_ops_line(db, "PKG-01", "Packaging")
        _create_cap_line(db, "SEW-01")  # only SEW-01 has a match

        response = client.post(
            "/api/production-lines/sync-capacity",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matched"]) == 1
        assert len(data["unmatched"]) == 1
        assert data["matched"][0]["line_code"] == "SEW-01"
        assert data["unmatched"][0]["line_code"] == "PKG-01"

    def test_sync_empty(self, supervisor_client):
        """Sync on empty client returns empty result."""
        client, db = supervisor_client

        response = client.post(
            "/api/production-lines/sync-capacity",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["matched"] == []
        assert data["unmatched"] == []

    def test_sync_requires_supervisor(self, operator_client):
        """Operator cannot trigger sync."""
        client, db = operator_client

        response = client.post(
            "/api/production-lines/sync-capacity",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code in (403, 500)

    def test_sync_multi_tenant_isolation(self, supervisor_client):
        """Sync does not cross-match between clients."""
        client, db = supervisor_client

        # Create a second client
        TestDataFactory.create_client(db, client_id="PLB-RT-C2", client_name="Other Client")
        db.commit()

        # Ops line in CLIENT_ID, capacity line in other client
        _create_ops_line(db, "SEW-01", "Sewing")
        _create_cap_line(db, "SEW-01", client_id="PLB-RT-C2")

        response = client.post(
            "/api/production-lines/sync-capacity",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matched"]) == 0
        assert len(data["unmatched"]) == 1


# ============================================================================
# TestUnlinkedEndpoint
# ============================================================================
class TestUnlinkedEndpoint:
    """Tests for GET /api/production-lines/unlinked"""

    def test_all_unlinked(self, supervisor_client):
        """Returns all unlinked lines."""
        client, db = supervisor_client

        _create_ops_line(db, "SEW-01", "Sewing 1")
        _create_ops_line(db, "CUT-01", "Cutting 1")

        response = client.get(
            "/api/production-lines/unlinked",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_linked_excluded(self, supervisor_client):
        """Linked lines are excluded from unlinked endpoint."""
        client, db = supervisor_client

        ops = _create_ops_line(db, "SEW-01", "Sewing 1")
        cap = _create_cap_line(db, "SEW-01")
        _create_ops_line(db, "CUT-01", "Cutting 1")

        ops.capacity_line_id = cap.id
        db.commit()

        response = client.get(
            "/api/production-lines/unlinked",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["line_code"] == "CUT-01"

    def test_unlinked_empty(self, supervisor_client):
        """Empty client returns empty list."""
        client, db = supervisor_client

        response = client.get(
            "/api/production-lines/unlinked",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_unlinked_readable_by_operator(self, operator_client):
        """Operator can read unlinked lines (read-only endpoint)."""
        client, db = operator_client
        _create_ops_line(db, "SEW-01", "Sewing 1")

        response = client.get(
            "/api/production-lines/unlinked",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200


# ============================================================================
# TestExistingEndpointsWithBridgeField
# ============================================================================
class TestExistingEndpointsWithBridgeField:
    """Verify existing endpoints include the new capacity_line_id field."""

    def test_list_includes_capacity_line_id(self, supervisor_client):
        """GET / response includes capacity_line_id field."""
        client, db = supervisor_client
        _create_ops_line(db, "SEW-01", "Sewing 1")

        response = client.get("/api/production-lines/", params={"client_id": CLIENT_ID})
        assert response.status_code == 200
        data = response.json()
        assert "capacity_line_id" in data[0]
        assert data[0]["capacity_line_id"] is None

    def test_get_includes_capacity_line_id(self, supervisor_client):
        """GET /{line_id} response includes capacity_line_id field."""
        client, db = supervisor_client
        ops = _create_ops_line(db, "SEW-01", "Sewing 1")
        cap = _create_cap_line(db, "SEW-01")
        ops.capacity_line_id = cap.id
        db.commit()

        response = client.get(f"/api/production-lines/{ops.line_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["capacity_line_id"] == cap.id

    def test_create_with_capacity_line_id(self, supervisor_client):
        """POST / can accept capacity_line_id."""
        client, db = supervisor_client
        cap = _create_cap_line(db, "SEW-01")

        payload = {
            "client_id": CLIENT_ID,
            "line_code": "SEW-01",
            "line_name": "Sewing Line 1",
            "capacity_line_id": cap.id,
        }
        response = client.post("/api/production-lines/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["capacity_line_id"] == cap.id
