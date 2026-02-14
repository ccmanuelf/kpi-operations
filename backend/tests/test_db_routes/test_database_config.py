"""
API Tests for Database Configuration Endpoints

Tests for /api/admin/database/* endpoints.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient


class TestDatabaseConfigEndpoints:
    """Tests for database configuration API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app

        return TestClient(app)

    def test_get_status_returns_current_provider(self, client):
        """Test GET /status returns provider info."""
        response = client.get("/api/admin/database/status")
        assert response.status_code == 200

        data = response.json()
        assert "current_provider" in data
        assert "migration_available" in data
        assert "supported_targets" in data
        assert data["current_provider"] in ["sqlite", "mariadb", "mysql"]

    def test_get_providers_returns_available(self, client):
        """Test GET /providers returns provider info."""
        response = client.get("/api/admin/database/providers")
        assert response.status_code == 200

        data = response.json()
        assert "providers" in data
        assert "sqlite" in data["providers"]
        assert "mariadb" in data["providers"]

    def test_test_connection_requires_url(self, client):
        """Test POST /test-connection validates input."""
        response = client.post("/api/admin/database/test-connection", json={})
        assert response.status_code == 422  # Validation error

    def test_test_connection_with_valid_sqlite(self, client, tmp_path):
        """Test connection testing with SQLite."""
        db_path = tmp_path / "test.db"
        response = client.post("/api/admin/database/test-connection", json={"target_url": f"sqlite:///{db_path}"})
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "sqlite"

    def test_test_connection_with_invalid_url(self, client):
        """Test connection testing with invalid URL."""
        response = client.post("/api/admin/database/test-connection", json={"target_url": "invalid://not-a-real-url"})
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False

    def test_migrate_requires_confirmation(self, client):
        """Test POST /migrate requires MIGRATE confirmation."""
        response = client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mariadb", "target_url": "mysql://test", "confirmation_text": "wrong"},
        )
        assert response.status_code == 400
        assert "MIGRATE" in response.json()["detail"]

    def test_migrate_requires_valid_provider(self, client):
        """Test POST /migrate validates provider."""
        response = client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "invalid", "target_url": "mysql://test", "confirmation_text": "MIGRATE"},
        )
        assert response.status_code == 400

    @patch("backend.routes.database_config.ProviderStateManager")
    def test_migrate_blocks_if_not_sqlite(self, mock_manager_class, client):
        """Test migration blocked if current provider is not SQLite."""
        mock_manager = MagicMock()
        mock_manager.get_current_provider.return_value = "mariadb"
        mock_manager_class.return_value = mock_manager

        response = client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mysql", "target_url": "mysql://localhost/db", "confirmation_text": "MIGRATE"},
        )
        assert response.status_code == 400
        assert "SQLite" in response.json()["detail"]

    @patch("backend.routes.database_config.ProviderStateManager")
    def test_migrate_blocks_if_locked(self, mock_manager_class, client):
        """Test migration blocked if already in progress."""
        mock_manager = MagicMock()
        mock_manager.get_current_provider.return_value = "sqlite"
        mock_manager.acquire_migration_lock.return_value = False
        mock_manager_class.return_value = mock_manager

        response = client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mariadb", "target_url": "mysql://localhost/db", "confirmation_text": "MIGRATE"},
        )
        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]

    def test_migration_status_returns_idle(self, client):
        """Test GET /migration/status returns idle when no migration."""
        response = client.get("/api/admin/database/migration/status")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data

    def test_full_status_returns_complete_info(self, client):
        """Test GET /full-status returns complete info."""
        response = client.get("/api/admin/database/full-status")
        assert response.status_code == 200

        data = response.json()
        assert "current_provider" in data
        assert "migration_locked" in data
        assert "migration_history" in data


class TestMigrationRequestValidation:
    """Tests for MigrationRequest validation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app

        return TestClient(app)

    def test_missing_target_provider(self, client):
        """Test missing target_provider field."""
        response = client.post(
            "/api/admin/database/migrate", json={"target_url": "mysql://test", "confirmation_text": "MIGRATE"}
        )
        assert response.status_code == 422

    def test_missing_target_url(self, client):
        """Test missing target_url field."""
        response = client.post(
            "/api/admin/database/migrate", json={"target_provider": "mariadb", "confirmation_text": "MIGRATE"}
        )
        assert response.status_code == 422

    def test_missing_confirmation_text(self, client):
        """Test missing confirmation_text field."""
        response = client.post(
            "/api/admin/database/migrate", json={"target_provider": "mariadb", "target_url": "mysql://test"}
        )
        assert response.status_code == 422

    def test_case_sensitive_confirmation(self, client):
        """Test confirmation is case-sensitive."""
        response = client.post(
            "/api/admin/database/migrate",
            json={
                "target_provider": "mariadb",
                "target_url": "mysql://test",
                "confirmation_text": "migrate",  # lowercase
            },
        )
        assert response.status_code == 400
        assert "MIGRATE" in response.json()["detail"]

    def test_confirmation_with_spaces(self, client):
        """Test confirmation rejects extra spaces."""
        response = client.post(
            "/api/admin/database/migrate",
            json={"target_provider": "mariadb", "target_url": "mysql://test", "confirmation_text": " MIGRATE "},
        )
        assert response.status_code == 400
