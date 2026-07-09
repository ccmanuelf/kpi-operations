"""
API Tests for Database Configuration Endpoints

Tests for /api/admin/database/* endpoints.
All endpoints require supervisor or admin authentication.
"""

import pytest

from backend.database import get_db
from backend.orm.user import User


@pytest.fixture(scope="module")
def supervisor_headers(test_client):
    """
    Create admin auth headers for the database-config endpoints.

    The database-config endpoints accept the supervisory tier, which admin
    also satisfies. Self-registration always yields role='operator' (Run 7
    C-2), so this fixture registers a user, elevates the role directly in
    the DB (the way an admin would via the users API), then logs in.
    """
    from backend.main import app

    user_data = {
        "username": "dbconfig_supervisor",
        "email": "dbconfig_supervisor@test.com",
        "password": "TestPass123!",
        "full_name": "DB Config Supervisor",
        "role": "supervisor",
    }

    # Register user (stores role as uppercase "SUPERVISOR")
    register_resp = test_client.post("/api/auth/register", json=user_data)
    # Auth /register returns 201 Created on success
    assert register_resp.status_code == 201, f"Registration failed: {register_resp.json()}"

    # Fix role case: get_current_active_supervisor requires lowercase "supervisor"
    db_override = app.dependency_overrides.get(get_db)
    if db_override:
        db_gen = db_override()
        db = next(db_gen)
        try:
            user = db.query(User).filter(User.username == user_data["username"]).first()
            if user:
                user.role = "admin"
                db.commit()
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    # Login to get token
    login_resp = test_client.post(
        "/api/auth/login",
        json={"username": user_data["username"], "password": user_data["password"]},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.json()}"
    token = login_resp.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


class TestDatabaseConfigEndpoints:
    """Tests for database configuration API endpoints."""

    def test_get_status_returns_current_provider(self, test_client, supervisor_headers):
        """Test GET /status returns provider info."""
        response = test_client.get("/api/admin/database/status", headers=supervisor_headers)
        assert response.status_code == 200

        data = response.json()
        assert "current_provider" in data
        assert "migration_available" in data
        assert "supported_targets" in data
        assert data["current_provider"] in ["sqlite", "mariadb", "mysql"]
        assert data["migration_available"] is False
        assert data["supported_targets"] == []

    def test_get_providers_returns_available(self, test_client, supervisor_headers):
        """Test GET /providers returns provider info."""
        response = test_client.get("/api/admin/database/providers", headers=supervisor_headers)
        assert response.status_code == 200

        data = response.json()
        assert "providers" in data
        assert "sqlite" in data["providers"]
        assert "mariadb" in data["providers"]


def test_status_requires_supervisor(test_client):
    r = test_client.get("/api/admin/database/status")
    assert r.status_code == 401


def test_providers_requires_supervisor(test_client):
    r = test_client.get("/api/admin/database/providers")
    assert r.status_code == 401
