"""
API Tests for Database Configuration Endpoints

Tests for /api/admin/database/* endpoints.
All endpoints require supervisor or admin authentication.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.schemas.user import User


@pytest.fixture(scope="module")
def supervisor_headers(test_client):
    """
    Create supervisor auth headers compatible with get_current_active_supervisor.

    The register endpoint uppercases roles (e.g. "supervisor" -> "SUPERVISOR")
    but get_current_active_supervisor checks for lowercase. This fixture
    registers a user, corrects the role case in the DB, then logs in.
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
    assert register_resp.status_code in [200, 201], f"Registration failed: {register_resp.json()}"

    # Fix role case: get_current_active_supervisor requires lowercase "supervisor"
    db_override = app.dependency_overrides.get(get_db)
    if db_override:
        db_gen = db_override()
        db = next(db_gen)
        try:
            user = db.query(User).filter(User.username == user_data["username"]).first()
            if user:
                user.role = "supervisor"
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

    def test_get_providers_returns_available(self, test_client, supervisor_headers):
        """Test GET /providers returns provider info."""
        response = test_client.get("/api/admin/database/providers", headers=supervisor_headers)
        assert response.status_code == 200

        data = response.json()
        assert "providers" in data
        assert "sqlite" in data["providers"]
        assert "mariadb" in data["providers"]

    def test_test_connection_requires_url(self, test_client, supervisor_headers):
        """Test POST /test-connection validates input."""
        response = test_client.post("/api/admin/database/test-connection", json={}, headers=supervisor_headers)
        assert response.status_code == 422  # Validation error

    def test_test_connection_with_valid_sqlite(self, test_client, supervisor_headers, tmp_path):
        """Test connection testing with SQLite."""
        db_path = tmp_path / "test.db"
        response = test_client.post(
            "/api/admin/database/test-connection",
            json={"target_url": f"sqlite:///{db_path}"},
            headers=supervisor_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "sqlite"

    def test_test_connection_with_invalid_url(self, test_client, supervisor_headers):
        """Test connection testing with invalid URL."""
        response = test_client.post(
            "/api/admin/database/test-connection",
            json={"target_url": "invalid://not-a-real-url"},
            headers=supervisor_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False

    def test_migrate_requires_confirmation(self, test_client, supervisor_headers):
        """Test POST /migrate requires MIGRATE confirmation."""
        response = test_client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mariadb", "target_url": "mysql://test", "confirmation_text": "wrong"},
            headers=supervisor_headers,
        )
        assert response.status_code == 400
        assert "MIGRATE" in response.json()["detail"]

    def test_migrate_requires_valid_provider(self, test_client, supervisor_headers):
        """Test POST /migrate validates provider."""
        response = test_client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "invalid", "target_url": "mysql://test", "confirmation_text": "MIGRATE"},
            headers=supervisor_headers,
        )
        assert response.status_code == 400

    @patch("backend.routes.database_config.ProviderStateManager")
    def test_migrate_blocks_if_not_sqlite(self, mock_manager_class, test_client, supervisor_headers):
        """Test migration blocked if current provider is not SQLite."""
        mock_manager = MagicMock()
        mock_manager.get_current_provider.return_value = "mariadb"
        mock_manager_class.return_value = mock_manager

        response = test_client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mysql", "target_url": "mysql://localhost/db", "confirmation_text": "MIGRATE"},
            headers=supervisor_headers,
        )
        assert response.status_code == 400
        assert "SQLite" in response.json()["detail"]

    @patch("backend.routes.database_config.ProviderStateManager")
    def test_migrate_blocks_if_locked(self, mock_manager_class, test_client, supervisor_headers):
        """Test migration blocked if already in progress."""
        mock_manager = MagicMock()
        mock_manager.get_current_provider.return_value = "sqlite"
        mock_manager.acquire_migration_lock.return_value = False
        mock_manager_class.return_value = mock_manager

        response = test_client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mariadb", "target_url": "mysql://localhost/db", "confirmation_text": "MIGRATE"},
            headers=supervisor_headers,
        )
        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]

    def test_migration_status_returns_idle(self, test_client, supervisor_headers):
        """Test GET /migration/status returns idle when no migration."""
        response = test_client.get("/api/admin/database/migration/status", headers=supervisor_headers)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data

    def test_full_status_returns_complete_info(self, test_client, supervisor_headers):
        """Test GET /full-status returns complete info."""
        response = test_client.get("/api/admin/database/full-status", headers=supervisor_headers)
        assert response.status_code == 200

        data = response.json()
        assert "current_provider" in data
        assert "migration_locked" in data
        assert "migration_history" in data


class TestMigrationRequestValidation:
    """Tests for MigrationRequest validation."""

    def test_missing_target_provider(self, test_client, supervisor_headers):
        """Test missing target_provider field."""
        response = test_client.post(
            "/api/admin/database/migrate",
            json={"target_url": "mysql://test", "confirmation_text": "MIGRATE"},
            headers=supervisor_headers,
        )
        assert response.status_code == 422

    def test_missing_target_url(self, test_client, supervisor_headers):
        """Test missing target_url field."""
        response = test_client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mariadb", "confirmation_text": "MIGRATE"},
            headers=supervisor_headers,
        )
        assert response.status_code == 422

    def test_missing_confirmation_text(self, test_client, supervisor_headers):
        """Test missing confirmation_text field."""
        response = test_client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mariadb", "target_url": "mysql://test"},
            headers=supervisor_headers,
        )
        assert response.status_code == 422

    def test_case_sensitive_confirmation(self, test_client, supervisor_headers):
        """Test confirmation is case-sensitive."""
        response = test_client.post(
            "/api/admin/database/migrate",
            json={
                "target_provider": "mariadb",
                "target_url": "mysql://test",
                "confirmation_text": "migrate",  # lowercase
            },
            headers=supervisor_headers,
        )
        assert response.status_code == 400
        assert "MIGRATE" in response.json()["detail"]

    def test_confirmation_with_spaces(self, test_client, supervisor_headers):
        """Test confirmation rejects extra spaces."""
        response = test_client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mariadb", "target_url": "mysql://test", "confirmation_text": " MIGRATE "},
            headers=supervisor_headers,
        )
        assert response.status_code == 400
