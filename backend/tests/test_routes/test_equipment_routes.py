"""
Tests for Equipment API routes.
Uses real in-memory SQLite database -- NO mocks for DB layer.
Follows the pattern from test_shift_routes.py.

NOTE: PRODUCTION_LINE FK is not enforced in SQLite by default,
so line_id tests work without the PRODUCTION_LINE table.
After Task 2.1 integration, additional line_id FK tests can be added.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User, UserRole
from backend.schemas.equipment import Equipment
from backend.schemas.production_line import ProductionLine  # noqa: F401 — register table for Base.metadata
from backend.routes.equipment import router as equipment_router
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test App Factory and Fixtures
# =============================================================================

CLIENT_ID = "EQUIP-RT-C1"


def _create_test_app(db_session, role="supervisor"):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(equipment_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    mock_user = User(
        user_id=f"test-equip-{role}-001",
        username=f"equip_test_{role}",
        email=f"equip_{role}@test.com",
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
def equip_db():
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
def supervisor_client(equip_db):
    """TestClient authenticated as supervisor."""
    TestDataFactory.create_client(equip_db, client_id=CLIENT_ID, client_name="Equipment Route Test Client")
    equip_db.commit()
    app = _create_test_app(equip_db, role="supervisor")
    return TestClient(app), equip_db


@pytest.fixture
def admin_client(equip_db):
    """TestClient authenticated as admin."""
    TestDataFactory.create_client(equip_db, client_id=CLIENT_ID, client_name="Equipment Route Test Client")
    equip_db.commit()
    app = _create_test_app(equip_db, role="admin")
    return TestClient(app), equip_db


@pytest.fixture
def operator_client(equip_db):
    """TestClient authenticated as operator (no write access)."""
    TestDataFactory.create_client(equip_db, client_id=CLIENT_ID, client_name="Equipment Route Test Client")
    equip_db.commit()
    app = _create_test_app(equip_db, role="operator")
    return TestClient(app), equip_db


def _seed_equipment(db, equipment_code="MCH-001", equipment_name="Test Machine", is_shared=False, line_id=None):
    """Helper to seed equipment directly in the DB."""
    equip = Equipment(
        client_id=CLIENT_ID,
        line_id=line_id,
        equipment_code=equipment_code,
        equipment_name=equipment_name,
        equipment_type="Sewing Machine",
        is_shared=is_shared,
        status="ACTIVE",
        is_active=True,
    )
    db.add(equip)
    db.commit()
    db.refresh(equip)
    return equip


# ============================================================================
# TestEquipmentListEndpoint
# ============================================================================
class TestEquipmentListEndpoint:
    """Tests for GET /api/equipment/"""

    def test_list_equipment_as_supervisor(self, supervisor_client):
        """Supervisor can list equipment for their client."""
        client, db = supervisor_client
        _seed_equipment(db, "MCH-001", "Machine 1")
        _seed_equipment(db, "MCH-002", "Machine 2")

        response = client.get("/api/equipment/", params={"client_id": CLIENT_ID})
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        codes = [e["equipment_code"] for e in data]
        assert "MCH-001" in codes
        assert "MCH-002" in codes

    def test_list_equipment_empty(self, supervisor_client):
        """List returns empty array when no equipment exists."""
        client, db = supervisor_client
        response = client.get("/api/equipment/", params={"client_id": CLIENT_ID})
        assert response.status_code == 200
        assert response.json() == []

    def test_list_equipment_with_line_filter(self, supervisor_client):
        """Filtering by line_id returns line-specific + shared equipment."""
        client, db = supervisor_client
        _seed_equipment(db, "LINE1-01", "Line 1 Machine", is_shared=False, line_id=1)
        _seed_equipment(db, "SHARED-01", "Shared Machine", is_shared=True, line_id=None)
        _seed_equipment(db, "LINE2-01", "Line 2 Machine", is_shared=False, line_id=2)

        response = client.get("/api/equipment/", params={"client_id": CLIENT_ID, "line_id": 1})
        assert response.status_code == 200

        data = response.json()
        codes = {e["equipment_code"] for e in data}
        assert "LINE1-01" in codes
        assert "SHARED-01" in codes
        assert "LINE2-01" not in codes

    def test_list_equipment_requires_client_id(self, supervisor_client):
        """Omitting client_id returns 422 validation error."""
        client, db = supervisor_client
        response = client.get("/api/equipment/")
        assert response.status_code == 422


# ============================================================================
# TestEquipmentSharedEndpoint
# ============================================================================
class TestEquipmentSharedEndpoint:
    """Tests for GET /api/equipment/shared"""

    def test_list_shared_equipment(self, supervisor_client):
        """Returns only shared equipment."""
        client, db = supervisor_client
        _seed_equipment(db, "NORM-01", "Normal Machine", is_shared=False)
        _seed_equipment(db, "SHR-01", "Shared Forklift", is_shared=True)
        _seed_equipment(db, "SHR-02", "Shared Compressor", is_shared=True)

        response = client.get("/api/equipment/shared", params={"client_id": CLIENT_ID})
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        codes = {e["equipment_code"] for e in data}
        assert codes == {"SHR-01", "SHR-02"}

    def test_list_shared_equipment_empty(self, supervisor_client):
        """Returns empty list when no shared equipment exists."""
        client, db = supervisor_client
        _seed_equipment(db, "NORM-01", "Normal Machine", is_shared=False)

        response = client.get("/api/equipment/shared", params={"client_id": CLIENT_ID})
        assert response.status_code == 200
        assert response.json() == []


# ============================================================================
# TestEquipmentCreateEndpoint
# ============================================================================
class TestEquipmentCreateEndpoint:
    """Tests for POST /api/equipment/"""

    def test_create_equipment_as_supervisor(self, supervisor_client):
        """Supervisor can create equipment."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            "equipment_code": "MCH-NEW",
            "equipment_name": "New Machine",
            "equipment_type": "Press",
            "is_shared": False,
            "status": "ACTIVE",
        }
        response = client.post("/api/equipment/", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["equipment_code"] == "MCH-NEW"
        assert data["equipment_name"] == "New Machine"
        assert data["equipment_type"] == "Press"
        assert data["is_shared"] is False
        assert data["status"] == "ACTIVE"
        assert data["is_active"] is True
        assert "equipment_id" in data
        assert "created_at" in data

    def test_create_equipment_as_admin(self, admin_client):
        """Admin can create equipment."""
        client, db = admin_client

        payload = {
            "client_id": CLIENT_ID,
            "equipment_code": "MCH-ADM",
            "equipment_name": "Admin Machine",
        }
        response = client.post("/api/equipment/", json=payload)
        assert response.status_code == 201
        assert response.json()["equipment_name"] == "Admin Machine"

    def test_create_equipment_as_operator_forbidden(self, operator_client):
        """Operator cannot create equipment (no supervisor override = 403/500)."""
        client, db = operator_client

        payload = {
            "client_id": CLIENT_ID,
            "equipment_code": "MCH-BLK",
            "equipment_name": "Blocked Machine",
        }
        response = client.post("/api/equipment/", json=payload)
        assert response.status_code in (403, 500)

    def test_create_duplicate_equipment_conflict(self, supervisor_client):
        """Creating a duplicate equipment_code returns 409 Conflict."""
        client, db = supervisor_client
        _seed_equipment(db, "MCH-DUP", "Existing Machine")

        payload = {
            "client_id": CLIENT_ID,
            "equipment_code": "MCH-DUP",
            "equipment_name": "Duplicate Machine",
        }
        response = client.post("/api/equipment/", json=payload)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_shared_equipment_with_line_conflict(self, supervisor_client):
        """Creating shared equipment with line_id set returns 409."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            "equipment_code": "MCH-BAD",
            "equipment_name": "Bad Shared Machine",
            "is_shared": True,
            "line_id": 1,
        }
        response = client.post("/api/equipment/", json=payload)
        assert response.status_code == 409
        assert "Shared equipment" in response.json()["detail"]

    def test_create_equipment_validation_error(self, supervisor_client):
        """Missing required fields returns 422."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            # Missing equipment_code, equipment_name
        }
        response = client.post("/api/equipment/", json=payload)
        assert response.status_code == 422

    def test_create_equipment_invalid_status(self, supervisor_client):
        """Invalid status value returns 422."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            "equipment_code": "MCH-INV",
            "equipment_name": "Invalid Status Machine",
            "status": "BROKEN",  # Not in allowed values
        }
        response = client.post("/api/equipment/", json=payload)
        assert response.status_code == 422

    def test_create_shared_equipment_ok(self, supervisor_client):
        """Creating shared equipment (is_shared=True, line_id=None) succeeds."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            "equipment_code": "SHR-OK",
            "equipment_name": "Shared OK Machine",
            "is_shared": True,
        }
        response = client.post("/api/equipment/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["is_shared"] is True
        assert data["line_id"] is None


# ============================================================================
# TestEquipmentGetEndpoint
# ============================================================================
class TestEquipmentGetEndpoint:
    """Tests for GET /api/equipment/{equipment_id}"""

    def test_get_equipment_by_id(self, supervisor_client):
        """Get a single equipment entry by ID."""
        client, db = supervisor_client
        equip = _seed_equipment(db, "MCH-GET", "Getter Machine")

        response = client.get(f"/api/equipment/{equip.equipment_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["equipment_id"] == equip.equipment_id
        assert data["equipment_code"] == "MCH-GET"
        assert data["client_id"] == CLIENT_ID
        assert data["is_active"] is True

    def test_get_equipment_not_found(self, supervisor_client):
        """Get nonexistent equipment returns 404."""
        client, db = supervisor_client
        response = client.get("/api/equipment/999999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Equipment not found"


# ============================================================================
# TestEquipmentUpdateEndpoint
# ============================================================================
class TestEquipmentUpdateEndpoint:
    """Tests for PUT /api/equipment/{equipment_id}"""

    def test_update_equipment_name(self, supervisor_client):
        """Supervisor can update equipment name."""
        client, db = supervisor_client
        equip = _seed_equipment(db, "MCH-UPD", "Before")

        payload = {"equipment_name": "After"}
        response = client.put(f"/api/equipment/{equip.equipment_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["equipment_name"] == "After"

    def test_update_equipment_status(self, supervisor_client):
        """Update equipment status."""
        client, db = supervisor_client
        equip = _seed_equipment(db, "MCH-STS", "Status Machine")

        payload = {"status": "MAINTENANCE"}
        response = client.put(f"/api/equipment/{equip.equipment_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "MAINTENANCE"

    def test_update_equipment_notes(self, supervisor_client):
        """Update notes field."""
        client, db = supervisor_client
        equip = _seed_equipment(db, "MCH-NTE", "Notes Machine")

        payload = {"notes": "Requires recalibration"}
        response = client.put(f"/api/equipment/{equip.equipment_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["notes"] == "Requires recalibration"

    def test_update_equipment_is_active(self, supervisor_client):
        """Update is_active flag."""
        client, db = supervisor_client
        equip = _seed_equipment(db, "MCH-ACT", "Active Machine")

        payload = {"is_active": False}
        response = client.put(f"/api/equipment/{equip.equipment_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_update_nonexistent_equipment(self, supervisor_client):
        """Updating nonexistent equipment returns 404."""
        client, db = supervisor_client

        payload = {"equipment_name": "Ghost"}
        response = client.put("/api/equipment/999999", json=payload)
        assert response.status_code == 404

    def test_update_equipment_as_operator_forbidden(self, operator_client):
        """Operator cannot update equipment."""
        client, db = operator_client
        equip = _seed_equipment(db, "MCH-OP", "Operator Machine")

        payload = {"equipment_name": "Blocked Update"}
        response = client.put(f"/api/equipment/{equip.equipment_id}", json=payload)
        assert response.status_code in (403, 500)


# ============================================================================
# TestEquipmentDeleteEndpoint
# ============================================================================
class TestEquipmentDeleteEndpoint:
    """Tests for DELETE /api/equipment/{equipment_id}"""

    def test_delete_equipment_as_supervisor(self, supervisor_client):
        """Supervisor can soft-delete equipment (204)."""
        client, db = supervisor_client
        equip = _seed_equipment(db, "MCH-DEL", "To Delete")

        response = client.delete(f"/api/equipment/{equip.equipment_id}")
        assert response.status_code == 204

        # Verify equipment is deactivated but still exists
        get_response = client.get(f"/api/equipment/{equip.equipment_id}")
        assert get_response.status_code == 200
        assert get_response.json()["is_active"] is False

    def test_delete_equipment_no_longer_in_active_list(self, supervisor_client):
        """Deleted equipment does not appear in active list."""
        client, db = supervisor_client
        equip = _seed_equipment(db, "MCH-VAN", "Will Vanish")

        client.delete(f"/api/equipment/{equip.equipment_id}")

        list_response = client.get("/api/equipment/", params={"client_id": CLIENT_ID})
        assert list_response.status_code == 200
        codes = [e["equipment_code"] for e in list_response.json()]
        assert "MCH-VAN" not in codes

    def test_delete_nonexistent_equipment(self, supervisor_client):
        """Deleting nonexistent equipment returns 404."""
        client, db = supervisor_client
        response = client.delete("/api/equipment/999999")
        assert response.status_code == 404

    def test_delete_equipment_as_operator_forbidden(self, operator_client):
        """Operator cannot delete equipment."""
        client, db = operator_client
        equip = _seed_equipment(db, "MCH-BLKD", "Blocked Delete")

        response = client.delete(f"/api/equipment/{equip.equipment_id}")
        assert response.status_code in (403, 500)
