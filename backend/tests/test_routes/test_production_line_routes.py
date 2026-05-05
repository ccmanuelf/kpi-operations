"""
Tests for Production Lines API routes.
Uses real in-memory SQLite database -- NO mocks for DB layer.
Follows the pattern from test_shift_routes.py.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User, UserRole
from backend.orm.production_line import ProductionLine
from backend.routes.production_lines import router as production_lines_router
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test App Factory and Fixtures
# =============================================================================

CLIENT_ID = "PL-RT-C1"


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
        user_id=f"test-pl-{role}-001",
        username=f"pl_test_{role}",
        email=f"pl_{role}@test.com",
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
def pl_db():
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
def supervisor_client(pl_db):
    """TestClient authenticated as supervisor."""
    TestDataFactory.create_client(pl_db, client_id=CLIENT_ID, client_name="PL Route Test Client")
    pl_db.commit()
    app = _create_test_app(pl_db, role="supervisor")
    return TestClient(app), pl_db


@pytest.fixture
def admin_client(pl_db):
    """TestClient authenticated as admin."""
    TestDataFactory.create_client(pl_db, client_id=CLIENT_ID, client_name="PL Route Test Client")
    pl_db.commit()
    app = _create_test_app(pl_db, role="admin")
    return TestClient(app), pl_db


@pytest.fixture
def operator_client(pl_db):
    """TestClient authenticated as operator (no write access)."""
    TestDataFactory.create_client(pl_db, client_id=CLIENT_ID, client_name="PL Route Test Client")
    pl_db.commit()
    app = _create_test_app(pl_db, role="operator")
    return TestClient(app), pl_db


def _create_line(db, line_code="SEW-01", line_name="Sewing Line 1", **kwargs):
    """Helper to seed a production line directly in the DB."""
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


# ============================================================================
# TestListEndpoint
# ============================================================================
class TestListEndpoint:
    """Tests for GET /api/production-lines/"""

    def test_list_lines_as_supervisor(self, supervisor_client):
        """Supervisor can list production lines for their client."""
        client, db = supervisor_client
        _create_line(db, "SEW-01", "Sewing 1")
        _create_line(db, "CUT-01", "Cutting 1")

        response = client.get("/api/production-lines/", params={"client_id": CLIENT_ID})
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        codes = [line["line_code"] for line in data]
        assert "SEW-01" in codes
        assert "CUT-01" in codes

    def test_list_lines_empty(self, supervisor_client):
        """List returns empty array when no lines exist."""
        client, db = supervisor_client
        response = client.get("/api/production-lines/", params={"client_id": CLIENT_ID})
        assert response.status_code == 200
        assert response.json() == []

    def test_list_excludes_inactive(self, supervisor_client):
        """Inactive lines are excluded from the list by default."""
        client, db = supervisor_client
        _create_line(db, "ACT-01", "Active Line")
        _create_line(db, "INACT-01", "Inactive Line", is_active=False)

        response = client.get("/api/production-lines/", params={"client_id": CLIENT_ID})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["line_code"] == "ACT-01"


# ============================================================================
# TestTreeEndpoint
# ============================================================================
class TestTreeEndpoint:
    """Tests for GET /api/production-lines/tree"""

    def test_tree_with_children(self, supervisor_client):
        """Tree endpoint returns parent with nested children."""
        client, db = supervisor_client
        parent = _create_line(db, "SEW-AREA", "Sewing Area", line_type="SECTION")
        _create_line(db, "SEW-01", "Sewing 1", parent_line_id=parent.line_id)
        _create_line(db, "SEW-02", "Sewing 2", parent_line_id=parent.line_id)

        response = client.get("/api/production-lines/tree", params={"client_id": CLIENT_ID})
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["line_code"] == "SEW-AREA"
        assert len(data[0]["children"]) == 2

    def test_tree_empty(self, supervisor_client):
        """Tree returns empty array when no lines exist."""
        client, db = supervisor_client
        response = client.get("/api/production-lines/tree", params={"client_id": CLIENT_ID})
        assert response.status_code == 200
        assert response.json() == []


# ============================================================================
# TestCreateEndpoint
# ============================================================================
class TestCreateEndpoint:
    """Tests for POST /api/production-lines/"""

    def test_create_as_supervisor(self, supervisor_client):
        """Supervisor can create a production line."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            "line_code": "SEW-01",
            "line_name": "Sewing Line 1",
            "department": "SEWING",
            "line_type": "DEDICATED",
            "max_operators": 10,
        }
        response = client.post("/api/production-lines/", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["line_code"] == "SEW-01"
        assert data["line_name"] == "Sewing Line 1"
        assert data["department"] == "SEWING"
        assert data["line_type"] == "DEDICATED"
        assert data["max_operators"] == 10
        assert data["is_active"] is True
        assert "line_id" in data
        assert "created_at" in data

    def test_create_as_admin(self, admin_client):
        """Admin can create a production line."""
        client, db = admin_client

        payload = {
            "client_id": CLIENT_ID,
            "line_code": "CUT-01",
            "line_name": "Cutting Area",
        }
        response = client.post("/api/production-lines/", json=payload)
        assert response.status_code == 201
        assert response.json()["line_code"] == "CUT-01"

    def test_create_as_operator_forbidden(self, operator_client):
        """Operator cannot create a production line."""
        client, db = operator_client

        payload = {
            "client_id": CLIENT_ID,
            "line_code": "BLOCKED-01",
            "line_name": "Blocked Line",
        }
        response = client.post("/api/production-lines/", json=payload)
        assert response.status_code in (403, 500)

    def test_create_duplicate_conflict(self, supervisor_client):
        """Creating a duplicate line returns 409 Conflict."""
        client, db = supervisor_client
        _create_line(db, "SEW-01", "Sewing Line 1")

        payload = {
            "client_id": CLIENT_ID,
            "line_code": "SEW-01",
            "line_name": "Duplicate",
        }
        response = client.post("/api/production-lines/", json=payload)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_validation_error(self, supervisor_client):
        """Missing required fields returns 422."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            # Missing line_code and line_name
        }
        response = client.post("/api/production-lines/", json=payload)
        assert response.status_code == 422

    def test_create_invalid_line_type(self, supervisor_client):
        """Invalid line_type returns 422 validation error."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            "line_code": "BAD-01",
            "line_name": "Bad Type",
            "line_type": "INVALID",
        }
        response = client.post("/api/production-lines/", json=payload)
        assert response.status_code == 422


# ============================================================================
# TestGetEndpoint
# ============================================================================
class TestGetEndpoint:
    """Tests for GET /api/production-lines/{line_id}"""

    def test_get_by_id(self, supervisor_client):
        """Get a single production line by ID."""
        client, db = supervisor_client
        line = _create_line(db, "SEW-01", "Sewing Line 1", department="SEWING")

        response = client.get(f"/api/production-lines/{line.line_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["line_id"] == line.line_id
        assert data["line_code"] == "SEW-01"
        assert data["line_name"] == "Sewing Line 1"
        assert data["department"] == "SEWING"
        assert data["client_id"] == CLIENT_ID
        assert data["is_active"] is True

    def test_get_not_found(self, supervisor_client):
        """Get nonexistent line returns 404."""
        client, db = supervisor_client
        response = client.get("/api/production-lines/999999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Production line not found"


# ============================================================================
# TestUpdateEndpoint
# ============================================================================
class TestUpdateEndpoint:
    """Tests for PUT /api/production-lines/{line_id}"""

    def test_update_name(self, supervisor_client):
        """Supervisor can update line name."""
        client, db = supervisor_client
        line = _create_line(db, "SEW-01", "Before")

        payload = {"line_name": "After"}
        response = client.put(f"/api/production-lines/{line.line_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["line_name"] == "After"

    def test_update_multiple_fields(self, supervisor_client):
        """Update department, line_type, and max_operators."""
        client, db = supervisor_client
        line = _create_line(db, "GEN-01", "Generic")

        payload = {
            "department": "FINISHING",
            "line_type": "SHARED",
            "max_operators": 25,
        }
        response = client.put(f"/api/production-lines/{line.line_id}", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["department"] == "FINISHING"
        assert data["line_type"] == "SHARED"
        assert data["max_operators"] == 25

    def test_update_is_active(self, supervisor_client):
        """Update is_active flag."""
        client, db = supervisor_client
        line = _create_line(db, "TOG-01", "Toggle")

        payload = {"is_active": False}
        response = client.put(f"/api/production-lines/{line.line_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_update_nonexistent(self, supervisor_client):
        """Updating nonexistent line returns 404."""
        client, db = supervisor_client

        payload = {"line_name": "Ghost"}
        response = client.put("/api/production-lines/999999", json=payload)
        assert response.status_code == 404


# ============================================================================
# TestDeleteEndpoint
# ============================================================================
class TestDeleteEndpoint:
    """Tests for DELETE /api/production-lines/{line_id}"""

    def test_delete_as_supervisor(self, supervisor_client):
        """Supervisor can soft-delete a production line (204)."""
        client, db = supervisor_client
        line = _create_line(db, "DEL-01", "ToDelete")

        response = client.delete(f"/api/production-lines/{line.line_id}")
        assert response.status_code == 204

        # Verify line is deactivated but still exists
        get_response = client.get(f"/api/production-lines/{line.line_id}")
        assert get_response.status_code == 200
        assert get_response.json()["is_active"] is False

    def test_delete_no_longer_in_active_list(self, supervisor_client):
        """Deleted line does not appear in active list."""
        client, db = supervisor_client
        line = _create_line(db, "VANISH-01", "WillVanish")

        client.delete(f"/api/production-lines/{line.line_id}")

        list_response = client.get("/api/production-lines/", params={"client_id": CLIENT_ID})
        assert list_response.status_code == 200
        codes = [item["line_code"] for item in list_response.json()]
        assert "VANISH-01" not in codes

    def test_delete_nonexistent(self, supervisor_client):
        """Deleting nonexistent line returns 404."""
        client, db = supervisor_client
        response = client.delete("/api/production-lines/999999")
        assert response.status_code == 404

    def test_delete_cascades_to_children(self, supervisor_client):
        """Deleting a parent cascades deactivation to children."""
        client, db = supervisor_client
        parent = _create_line(db, "SEW-AREA", "Sewing Area", line_type="SECTION")
        child1 = _create_line(db, "SEW-01", "Sewing 1", parent_line_id=parent.line_id)
        child2 = _create_line(db, "SEW-02", "Sewing 2", parent_line_id=parent.line_id)

        response = client.delete(f"/api/production-lines/{parent.line_id}")
        assert response.status_code == 204

        # Parent deactivated
        parent_resp = client.get(f"/api/production-lines/{parent.line_id}")
        assert parent_resp.json()["is_active"] is False

        # Children deactivated
        child1_resp = client.get(f"/api/production-lines/{child1.line_id}")
        assert child1_resp.json()["is_active"] is False

        child2_resp = client.get(f"/api/production-lines/{child2.line_id}")
        assert child2_resp.json()["is_active"] is False


# ============================================================================
# TestRouteAuth
# ============================================================================
class TestRouteAuth:
    """Test authentication requirements on production line routes."""

    def test_operator_can_read(self, operator_client):
        """Operator can read (GET) production lines."""
        client, db = operator_client
        _create_line(db, "SEW-01", "Sewing Line 1")

        response = client.get("/api/production-lines/", params={"client_id": CLIENT_ID})
        assert response.status_code == 200

    def test_operator_cannot_create(self, operator_client):
        """Operator cannot create (POST) production lines."""
        client, db = operator_client

        payload = {
            "client_id": CLIENT_ID,
            "line_code": "BLOCKED",
            "line_name": "Blocked",
        }
        response = client.post("/api/production-lines/", json=payload)
        assert response.status_code in (403, 500)

    def test_operator_cannot_update(self, operator_client):
        """Operator cannot update (PUT) production lines."""
        client, db = operator_client
        line = _create_line(db, "SEW-01", "Sewing")

        payload = {"line_name": "Modified"}
        response = client.put(f"/api/production-lines/{line.line_id}", json=payload)
        assert response.status_code in (403, 500)

    def test_operator_cannot_delete(self, operator_client):
        """Operator cannot delete production lines."""
        client, db = operator_client
        line = _create_line(db, "SEW-01", "Sewing")

        response = client.delete(f"/api/production-lines/{line.line_id}")
        assert response.status_code in (403, 500)
