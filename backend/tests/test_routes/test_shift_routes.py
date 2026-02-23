"""
Tests for Shift API routes.
Uses real in-memory SQLite database -- NO mocks for DB layer.
Follows the pattern from test_capacity_routes_crud.py.
"""

import pytest
from datetime import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User, UserRole
from backend.routes.shifts import router as shifts_router
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test App Factory and Fixtures
# =============================================================================

CLIENT_ID = "SHIFT-RT-C1"


def _create_test_app(db_session, role="supervisor"):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(shifts_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    mock_user = User(
        user_id=f"test-shift-{role}-001",
        username=f"shift_test_{role}",
        email=f"shift_{role}@test.com",
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
def shift_db():
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
def supervisor_client(shift_db):
    """TestClient authenticated as supervisor."""
    TestDataFactory.create_client(shift_db, client_id=CLIENT_ID, client_name="Shift Route Test Client")
    shift_db.commit()
    app = _create_test_app(shift_db, role="supervisor")
    return TestClient(app), shift_db


@pytest.fixture
def admin_client(shift_db):
    """TestClient authenticated as admin."""
    TestDataFactory.create_client(shift_db, client_id=CLIENT_ID, client_name="Shift Route Test Client")
    shift_db.commit()
    app = _create_test_app(shift_db, role="admin")
    return TestClient(app), shift_db


@pytest.fixture
def operator_client(shift_db):
    """TestClient authenticated as operator (no write access)."""
    TestDataFactory.create_client(shift_db, client_id=CLIENT_ID, client_name="Shift Route Test Client")
    shift_db.commit()
    app = _create_test_app(shift_db, role="operator")
    return TestClient(app), shift_db


def _create_shift(db, shift_name="1st", start="06:00:00", end="14:00:00"):
    """Helper to seed a shift directly in the DB."""
    shift = TestDataFactory.create_shift(
        db,
        client_id=CLIENT_ID,
        shift_name=shift_name,
        start_time=start,
        end_time=end,
    )
    db.commit()
    return shift


# ============================================================================
# TestShiftListEndpoint
# ============================================================================
class TestShiftListEndpoint:
    """Tests for GET /api/shifts/"""

    def test_list_shifts_as_supervisor(self, supervisor_client):
        """Supervisor can list shifts for their client."""
        client, db = supervisor_client
        _create_shift(db, "1st", "06:00:00", "14:00:00")
        _create_shift(db, "2nd", "14:00:00", "22:00:00")

        response = client.get("/api/shifts/", params={"client_id": CLIENT_ID})
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        names = [s["shift_name"] for s in data]
        assert "1st" in names
        assert "2nd" in names

    def test_list_shifts_empty(self, supervisor_client):
        """List returns empty array when no shifts exist."""
        client, db = supervisor_client
        response = client.get("/api/shifts/", params={"client_id": CLIENT_ID})
        assert response.status_code == 200
        assert response.json() == []


# ============================================================================
# TestShiftCreateEndpoint
# ============================================================================
class TestShiftCreateEndpoint:
    """Tests for POST /api/shifts/"""

    def test_create_shift_as_supervisor(self, supervisor_client):
        """Supervisor can create a shift."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            "shift_name": "2nd",
            "start_time": "14:00:00",
            "end_time": "22:00:00",
        }
        response = client.post("/api/shifts/", json=payload)
        assert response.status_code == 201

        body = response.json()
        data = body["data"]
        assert data["shift_name"] == "2nd"
        assert data["start_time"] == "14:00:00"
        assert data["end_time"] == "22:00:00"
        assert data["is_active"] is True
        assert "shift_id" in data
        assert "created_at" in data
        assert "warnings" in body
        assert isinstance(body["warnings"], list)

    def test_create_shift_as_admin(self, admin_client):
        """Admin can create a shift."""
        client, db = admin_client

        payload = {
            "client_id": CLIENT_ID,
            "shift_name": "Night",
            "start_time": "22:00:00",
            "end_time": "06:00:00",
        }
        response = client.post("/api/shifts/", json=payload)
        assert response.status_code == 201
        assert response.json()["data"]["shift_name"] == "Night"

    def test_create_shift_as_operator_forbidden(self, operator_client):
        """Operator cannot create a shift (no supervisor override = 403/500)."""
        client, db = operator_client

        payload = {
            "client_id": CLIENT_ID,
            "shift_name": "Blocked",
            "start_time": "06:00:00",
            "end_time": "14:00:00",
        }
        response = client.post("/api/shifts/", json=payload)
        # Without supervisor dependency override, FastAPI tries real dependency
        # which returns 403 for operators
        assert response.status_code in (403, 500)

    def test_create_duplicate_shift_conflict(self, supervisor_client):
        """Creating a duplicate shift returns 409 Conflict."""
        client, db = supervisor_client
        _create_shift(db, "1st")

        payload = {
            "client_id": CLIENT_ID,
            "shift_name": "1st",  # Already exists
            "start_time": "06:00:00",
            "end_time": "14:00:00",
        }
        response = client.post("/api/shifts/", json=payload)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_shift_validation_error(self, supervisor_client):
        """Missing required fields returns 422."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            # Missing shift_name, start_time, end_time
        }
        response = client.post("/api/shifts/", json=payload)
        assert response.status_code == 422


# ============================================================================
# TestShiftGetEndpoint
# ============================================================================
class TestShiftGetEndpoint:
    """Tests for GET /api/shifts/{shift_id}"""

    def test_get_shift_by_id(self, supervisor_client):
        """Get a single shift by ID."""
        client, db = supervisor_client
        shift = _create_shift(db, "1st")

        response = client.get(f"/api/shifts/{shift.shift_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["shift_id"] == shift.shift_id
        assert data["shift_name"] == "1st"
        assert data["client_id"] == CLIENT_ID
        assert data["is_active"] is True

    def test_get_shift_not_found(self, supervisor_client):
        """Get nonexistent shift returns 404."""
        client, db = supervisor_client
        response = client.get("/api/shifts/999999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Shift not found"


# ============================================================================
# TestShiftUpdateEndpoint
# ============================================================================
class TestShiftUpdateEndpoint:
    """Tests for PUT /api/shifts/{shift_id}"""

    def test_update_shift_name(self, supervisor_client):
        """Supervisor can update shift name."""
        client, db = supervisor_client
        shift = _create_shift(db, "Before")

        payload = {"shift_name": "After"}
        response = client.put(f"/api/shifts/{shift.shift_id}", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["shift_name"] == "After"
        assert "warnings" in body

    def test_update_shift_times(self, supervisor_client):
        """Update start_time and end_time."""
        client, db = supervisor_client
        shift = _create_shift(db, "Flex")

        payload = {"start_time": "07:00:00", "end_time": "15:00:00"}
        response = client.put(f"/api/shifts/{shift.shift_id}", json=payload)
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["start_time"] == "07:00:00"
        assert data["end_time"] == "15:00:00"

    def test_update_shift_is_active(self, supervisor_client):
        """Update is_active flag."""
        client, db = supervisor_client
        shift = _create_shift(db, "Toggle")

        payload = {"is_active": False}
        response = client.put(f"/api/shifts/{shift.shift_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["data"]["is_active"] is False

    def test_update_nonexistent_shift(self, supervisor_client):
        """Updating nonexistent shift returns 404."""
        client, db = supervisor_client

        payload = {"shift_name": "Ghost"}
        response = client.put("/api/shifts/999999", json=payload)
        assert response.status_code == 404


# ============================================================================
# TestShiftDeleteEndpoint
# ============================================================================
class TestShiftDeleteEndpoint:
    """Tests for DELETE /api/shifts/{shift_id}"""

    def test_delete_shift_as_supervisor(self, supervisor_client):
        """Supervisor can soft-delete a shift (204)."""
        client, db = supervisor_client
        shift = _create_shift(db, "ToDelete")

        response = client.delete(f"/api/shifts/{shift.shift_id}")
        assert response.status_code == 204

        # Verify shift is deactivated but still exists
        get_response = client.get(f"/api/shifts/{shift.shift_id}")
        assert get_response.status_code == 200
        assert get_response.json()["is_active"] is False

    def test_delete_shift_no_longer_in_active_list(self, supervisor_client):
        """Deleted shift does not appear in active list."""
        client, db = supervisor_client
        shift = _create_shift(db, "WillVanish")

        client.delete(f"/api/shifts/{shift.shift_id}")

        list_response = client.get("/api/shifts/", params={"client_id": CLIENT_ID})
        assert list_response.status_code == 200
        names = [s["shift_name"] for s in list_response.json()]
        assert "WillVanish" not in names

    def test_delete_nonexistent_shift(self, supervisor_client):
        """Deleting nonexistent shift returns 404."""
        client, db = supervisor_client
        response = client.delete("/api/shifts/999999")
        assert response.status_code == 404


# ============================================================================
# TestShiftOverlapOnCreate
# ============================================================================
class TestShiftOverlapOnCreate:
    """Tests for overlap warnings on POST /api/shifts/"""

    def test_create_non_overlapping_no_warning(self, supervisor_client):
        """Creating a non-overlapping shift returns empty warnings."""
        client, db = supervisor_client
        _create_shift(db, "1st", "06:00:00", "14:00:00")

        payload = {
            "client_id": CLIENT_ID,
            "shift_name": "2nd",
            "start_time": "14:00:00",
            "end_time": "22:00:00",
        }
        response = client.post("/api/shifts/", json=payload)
        assert response.status_code == 201

        body = response.json()
        assert body["warnings"] == []
        assert body["data"]["shift_name"] == "2nd"

    def test_create_overlapping_returns_warning_and_saves(self, supervisor_client):
        """Creating an overlapping shift returns a warning but still saves."""
        client, db = supervisor_client
        _create_shift(db, "1st", "06:00:00", "14:00:00")

        payload = {
            "client_id": CLIENT_ID,
            "shift_name": "Overlap",
            "start_time": "10:00:00",
            "end_time": "18:00:00",
        }
        response = client.post("/api/shifts/", json=payload)
        assert response.status_code == 201

        body = response.json()
        assert len(body["warnings"]) == 1
        assert "1st" in body["warnings"][0]
        assert "06:00" in body["warnings"][0]
        assert "14:00" in body["warnings"][0]

        # Verify the shift was actually saved
        assert body["data"]["shift_name"] == "Overlap"
        assert body["data"]["shift_id"] is not None

    def test_create_overlapping_multiple_warnings(self, supervisor_client):
        """Creating a shift that overlaps with multiple existing shifts returns multiple warnings."""
        client, db = supervisor_client
        _create_shift(db, "Morning", "06:00:00", "12:00:00")
        _create_shift(db, "Midday", "10:00:00", "16:00:00")

        payload = {
            "client_id": CLIENT_ID,
            "shift_name": "Wide",
            "start_time": "08:00:00",
            "end_time": "14:00:00",
        }
        response = client.post("/api/shifts/", json=payload)
        assert response.status_code == 201

        body = response.json()
        assert len(body["warnings"]) == 2


# ============================================================================
# TestShiftOverlapOnUpdate
# ============================================================================
class TestShiftOverlapOnUpdate:
    """Tests for overlap warnings on PUT /api/shifts/{shift_id}"""

    def test_update_no_overlap_no_warning(self, supervisor_client):
        """Updating a shift without creating overlap returns empty warnings."""
        client, db = supervisor_client
        _create_shift(db, "1st", "06:00:00", "14:00:00")
        shift2 = _create_shift(db, "2nd", "14:00:00", "22:00:00")

        payload = {"start_time": "15:00:00"}
        response = client.put(f"/api/shifts/{shift2.shift_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["warnings"] == []

    def test_update_creating_overlap_returns_warning(self, supervisor_client):
        """Updating a shift to overlap with another returns a warning but saves."""
        client, db = supervisor_client
        _create_shift(db, "1st", "06:00:00", "14:00:00")
        shift2 = _create_shift(db, "2nd", "14:00:00", "22:00:00")

        # Move 2nd shift to overlap with 1st
        payload = {"start_time": "10:00:00"}
        response = client.put(f"/api/shifts/{shift2.shift_id}", json=payload)
        assert response.status_code == 200

        body = response.json()
        assert len(body["warnings"]) == 1
        assert "1st" in body["warnings"][0]
        # Shift was still saved
        assert body["data"]["start_time"] == "10:00:00"

    def test_update_self_not_flagged(self, supervisor_client):
        """Updating a shift's name (same times) does NOT flag self-overlap."""
        client, db = supervisor_client
        shift = _create_shift(db, "1st", "06:00:00", "14:00:00")

        payload = {"shift_name": "Renamed"}
        response = client.put(f"/api/shifts/{shift.shift_id}", json=payload)
        assert response.status_code == 200
        assert response.json()["warnings"] == []
        assert response.json()["data"]["shift_name"] == "Renamed"


# ============================================================================
# TestCheckOverlapEndpoint
# ============================================================================
class TestCheckOverlapEndpoint:
    """Tests for POST /api/shifts/check-overlap"""

    def test_check_overlap_no_overlaps(self, supervisor_client):
        """check-overlap returns no overlaps for non-conflicting times."""
        client, db = supervisor_client
        _create_shift(db, "1st", "06:00:00", "14:00:00")

        payload = {
            "client_id": CLIENT_ID,
            "start_time": "14:00:00",
            "end_time": "22:00:00",
        }
        response = client.post("/api/shifts/check-overlap", json=payload)
        assert response.status_code == 200

        body = response.json()
        assert body["has_overlaps"] is False
        assert body["overlaps"] == []

    def test_check_overlap_detects_conflict(self, supervisor_client):
        """check-overlap detects overlapping shifts."""
        client, db = supervisor_client
        existing = _create_shift(db, "1st", "06:00:00", "14:00:00")

        payload = {
            "client_id": CLIENT_ID,
            "start_time": "10:00:00",
            "end_time": "18:00:00",
        }
        response = client.post("/api/shifts/check-overlap", json=payload)
        assert response.status_code == 200

        body = response.json()
        assert body["has_overlaps"] is True
        assert len(body["overlaps"]) == 1
        assert body["overlaps"][0]["shift_id"] == existing.shift_id
        assert body["overlaps"][0]["shift_name"] == "1st"
        assert body["overlaps"][0]["start_time"] == "06:00:00"
        assert body["overlaps"][0]["end_time"] == "14:00:00"

    def test_check_overlap_exclude_shift_id(self, supervisor_client):
        """check-overlap excludes the specified shift (for update scenarios)."""
        client, db = supervisor_client
        shift = _create_shift(db, "1st", "06:00:00", "14:00:00")

        payload = {
            "client_id": CLIENT_ID,
            "start_time": "06:00:00",
            "end_time": "14:00:00",
            "exclude_shift_id": shift.shift_id,
        }
        response = client.post("/api/shifts/check-overlap", json=payload)
        assert response.status_code == 200

        body = response.json()
        assert body["has_overlaps"] is False

    def test_check_overlap_empty_client(self, supervisor_client):
        """check-overlap returns no overlaps when client has no shifts."""
        client, db = supervisor_client

        payload = {
            "client_id": CLIENT_ID,
            "start_time": "06:00:00",
            "end_time": "14:00:00",
        }
        response = client.post("/api/shifts/check-overlap", json=payload)
        assert response.status_code == 200
        assert response.json()["has_overlaps"] is False

    def test_check_overlap_overnight_shift(self, supervisor_client):
        """check-overlap correctly handles overnight shifts."""
        client, db = supervisor_client
        _create_shift(db, "Night", "22:00:00", "06:00:00")

        # Check a shift that overlaps with the early morning portion
        payload = {
            "client_id": CLIENT_ID,
            "start_time": "04:00:00",
            "end_time": "08:00:00",
        }
        response = client.post("/api/shifts/check-overlap", json=payload)
        assert response.status_code == 200
        assert response.json()["has_overlaps"] is True
        assert response.json()["overlaps"][0]["shift_name"] == "Night"
