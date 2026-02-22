"""
Route Tests — Break Times API
Uses mini FastAPI app with overridden auth, function-scoped real DB.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.routes.break_times import router as break_times_router
from backend.tests.fixtures.factories import TestDataFactory


def create_test_app(db_session, user):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(break_times_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def get_mock_user():
        return user

    def get_mock_supervisor():
        return user

    from backend.auth.jwt import get_current_user, get_current_active_supervisor

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_current_active_supervisor] = get_mock_supervisor
    return app


@pytest.fixture(scope="function")
def break_time_db():
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
def break_time_setup(break_time_db):
    """Seed base data: client, shift, supervisor user."""
    db = break_time_db

    client = TestDataFactory.create_client(
        db, client_id="RT-BRK", client_name="Route Test Client"
    )
    shift = TestDataFactory.create_shift(
        db, client_id="RT-BRK", shift_name="Day Shift"
    )
    supervisor = TestDataFactory.create_user(
        db,
        username="brk_supervisor",
        role="supervisor",
        client_id="RT-BRK",
    )
    db.commit()

    return {
        "db": db,
        "client": client,
        "shift": shift,
        "supervisor": supervisor,
    }


@pytest.fixture
def authenticated_client(break_time_setup):
    """Create an authenticated TestClient for break-time routes."""
    db = break_time_setup["db"]
    user = break_time_setup["supervisor"]
    app = create_test_app(db, user)
    return TestClient(app), break_time_setup


@pytest.fixture
def unauthenticated_client(break_time_setup):
    """Create an unauthenticated TestClient (no auth override)."""
    db = break_time_setup["db"]
    app = FastAPI()
    app.include_router(break_times_router)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _break_payload(shift_id, **overrides):
    """Helper to build a valid break creation payload."""
    payload = {
        "shift_id": shift_id,
        "client_id": "RT-BRK",
        "break_name": "Test Break",
        "start_offset_minutes": 120,
        "duration_minutes": 15,
        "applies_to": "ALL",
    }
    payload.update(overrides)
    return payload


# ===========================================================================
# POST /api/break-times
# ===========================================================================


class TestCreateBreak:
    """POST /api/break-times"""

    def test_create_break_201(self, authenticated_client):
        """Supervisor can create a break time, returns 201."""
        client, setup = authenticated_client
        payload = _break_payload(setup["shift"].shift_id, break_name="Morning Break")
        resp = client.post("/api/break-times", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["break_name"] == "Morning Break"
        assert body["duration_minutes"] == 15
        assert body["is_active"] is True
        assert "break_id" in body

    def test_create_break_invalid_shift_404(self, authenticated_client):
        """Creating a break for a non-existent shift returns 404."""
        client, setup = authenticated_client
        payload = _break_payload(99999)
        resp = client.post("/api/break-times", json=payload)
        assert resp.status_code == 404

    def test_create_break_validation_error_empty_body(self, authenticated_client):
        """Missing required fields returns 422."""
        client, _ = authenticated_client
        resp = client.post("/api/break-times", json={})
        assert resp.status_code == 422

    def test_create_break_duration_must_be_positive(self, authenticated_client):
        """duration_minutes must be >= 1."""
        client, setup = authenticated_client
        payload = _break_payload(setup["shift"].shift_id, duration_minutes=0)
        resp = client.post("/api/break-times", json=payload)
        assert resp.status_code == 422

    def test_create_break_applies_to_invalid(self, authenticated_client):
        """applies_to must be one of ALL, EMPLOYEE, LINE."""
        client, setup = authenticated_client
        payload = _break_payload(setup["shift"].shift_id, applies_to="INVALID")
        resp = client.post("/api/break-times", json=payload)
        assert resp.status_code == 422

    def test_create_break_employee_type(self, authenticated_client):
        """Can create a break with applies_to=EMPLOYEE."""
        client, setup = authenticated_client
        payload = _break_payload(
            setup["shift"].shift_id,
            break_name="Employee Break",
            applies_to="EMPLOYEE",
        )
        resp = client.post("/api/break-times", json=payload)
        assert resp.status_code == 201
        assert resp.json()["applies_to"] == "EMPLOYEE"

    def test_create_break_line_type(self, authenticated_client):
        """Can create a break with applies_to=LINE."""
        client, setup = authenticated_client
        payload = _break_payload(
            setup["shift"].shift_id,
            break_name="Line Break",
            applies_to="LINE",
        )
        resp = client.post("/api/break-times", json=payload)
        assert resp.status_code == 201
        assert resp.json()["applies_to"] == "LINE"


# ===========================================================================
# GET /api/break-times
# ===========================================================================


class TestListBreaks:
    """GET /api/break-times"""

    def test_list_breaks_empty(self, authenticated_client):
        """List returns empty when no breaks exist."""
        client, setup = authenticated_client
        resp = client.get(
            "/api/break-times",
            params={"shift_id": setup["shift"].shift_id, "client_id": "RT-BRK"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_breaks_with_data(self, authenticated_client):
        """List returns created breaks."""
        client, setup = authenticated_client
        shift_id = setup["shift"].shift_id

        for name in ["Morning", "Lunch"]:
            client.post(
                "/api/break-times",
                json=_break_payload(shift_id, break_name=name),
            )

        resp = client.get(
            "/api/break-times",
            params={"shift_id": shift_id, "client_id": "RT-BRK"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_breaks_by_client_only(self, authenticated_client):
        """List with only client_id returns all client breaks across shifts."""
        client, setup = authenticated_client
        client.post(
            "/api/break-times",
            json=_break_payload(setup["shift"].shift_id, break_name="Client Break"),
        )

        resp = client.get("/api/break-times", params={"client_id": "RT-BRK"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_list_breaks_no_params_uses_user_client(self, authenticated_client):
        """Without params, uses the user's assigned client."""
        client, setup = authenticated_client
        client.post(
            "/api/break-times",
            json=_break_payload(setup["shift"].shift_id, break_name="Auto Break"),
        )

        resp = client.get("/api/break-times")
        assert resp.status_code == 200
        # Supervisor is assigned to RT-BRK, so should see the break
        data = resp.json()
        assert len(data) >= 1


# ===========================================================================
# PUT /api/break-times/{break_id}
# ===========================================================================


class TestUpdateBreak:
    """PUT /api/break-times/{break_id}"""

    def test_update_break(self, authenticated_client):
        """Supervisor can update a break time."""
        client, setup = authenticated_client
        create_resp = client.post(
            "/api/break-times",
            json=_break_payload(setup["shift"].shift_id, break_name="Old Name"),
        )
        break_id = create_resp.json()["break_id"]

        update_resp = client.put(
            f"/api/break-times/{break_id}",
            json={"break_name": "New Name", "duration_minutes": 25},
        )
        assert update_resp.status_code == 200
        body = update_resp.json()
        assert body["break_name"] == "New Name"
        assert body["duration_minutes"] == 25
        # Unchanged fields
        assert body["start_offset_minutes"] == 120

    def test_update_break_not_found(self, authenticated_client):
        """Updating non-existent break returns 404."""
        client, _ = authenticated_client
        resp = client.put("/api/break-times/99999", json={"break_name": "Nope"})
        assert resp.status_code == 404

    def test_update_break_deactivate(self, authenticated_client):
        """Can set is_active=False via update."""
        client, setup = authenticated_client
        create_resp = client.post(
            "/api/break-times",
            json=_break_payload(setup["shift"].shift_id, break_name="Deactivate Me"),
        )
        break_id = create_resp.json()["break_id"]

        update_resp = client.put(
            f"/api/break-times/{break_id}", json={"is_active": False}
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["is_active"] is False


# ===========================================================================
# DELETE /api/break-times/{break_id}
# ===========================================================================


class TestDeleteBreak:
    """DELETE /api/break-times/{break_id}"""

    def test_delete_break_204(self, authenticated_client):
        """Supervisor can soft-delete a break, returns 204."""
        client, setup = authenticated_client
        create_resp = client.post(
            "/api/break-times",
            json=_break_payload(setup["shift"].shift_id, break_name="To Delete"),
        )
        break_id = create_resp.json()["break_id"]

        del_resp = client.delete(f"/api/break-times/{break_id}")
        assert del_resp.status_code == 204

        # Verify no longer in list
        list_resp = client.get(
            "/api/break-times",
            params={"shift_id": setup["shift"].shift_id, "client_id": "RT-BRK"},
        )
        assert all(b["break_id"] != break_id for b in list_resp.json())

    def test_delete_break_not_found(self, authenticated_client):
        """Deleting non-existent break returns 404."""
        client, _ = authenticated_client
        resp = client.delete("/api/break-times/99999")
        assert resp.status_code == 404


# ===========================================================================
# Auth: unauthenticated requests
# ===========================================================================


class TestUnauthenticated:
    """Requests without authentication."""

    def test_unauthenticated_get(self, unauthenticated_client):
        """GET without auth returns 401."""
        resp = unauthenticated_client.get(
            "/api/break-times", params={"client_id": "RT-BRK"}
        )
        assert resp.status_code == 401

    def test_unauthenticated_post(self, unauthenticated_client):
        """POST without auth returns 401."""
        payload = _break_payload(1)
        resp = unauthenticated_client.post("/api/break-times", json=payload)
        assert resp.status_code == 401
