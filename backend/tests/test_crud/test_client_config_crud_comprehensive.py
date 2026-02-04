"""
Comprehensive Client Config CRUD Tests
Tests CRUD operations with real database transactions.
Target: Increase crud/client_config.py coverage to 85%+
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from backend.database import Base
from backend.schemas import ClientType
from backend.crud import client_config as client_config_crud
from backend.tests.fixtures.factories import TestDataFactory


@pytest.fixture(scope="function")
def config_db():
    """Create a fresh database for each test."""
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
def config_setup(config_db):
    """Create standard test data for config tests."""
    db = config_db

    # Create clients
    client_a = TestDataFactory.create_client(
        db,
        client_id="CONFIG-CLIENT-A",
        client_name="Config Test Client A",
        client_type=ClientType.HOURLY_RATE
    )

    client_b = TestDataFactory.create_client(
        db,
        client_id="CONFIG-CLIENT-B",
        client_name="Config Test Client B",
        client_type=ClientType.PIECE_RATE
    )

    # Create users
    admin = TestDataFactory.create_user(
        db,
        user_id="cfg-admin-001",
        username="config_admin",
        role="admin",
        client_id=None
    )

    supervisor_a = TestDataFactory.create_user(
        db,
        user_id="cfg-super-001",
        username="config_supervisor_a",
        role="supervisor",
        client_id=client_a.client_id
    )

    supervisor_b = TestDataFactory.create_user(
        db,
        user_id="cfg-super-002",
        username="config_supervisor_b",
        role="supervisor",
        client_id=client_b.client_id
    )

    db.commit()

    return {
        "db": db,
        "client_a": client_a,
        "client_b": client_b,
        "admin": admin,
        "supervisor_a": supervisor_a,
        "supervisor_b": supervisor_b,
    }


class TestCreateClientConfig:
    """Tests for create_client_config function."""

    def test_create_client_config_admin_success(self, config_setup):
        """Test admin can create client config."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        config_data = {
            "client_id": client.client_id,
            "efficiency_target_percent": 90.0,
            "quality_target_ppm": 5000.0,
        }

        result = client_config_crud.create_client_config(db, config_data, admin)

        assert result is not None
        assert result.client_id == client.client_id
        assert result.efficiency_target_percent == 90.0

    def test_create_client_config_supervisor_own_client(self, config_setup):
        """Test supervisor can create config for own client."""
        db = config_setup["db"]
        supervisor = config_setup["supervisor_a"]
        client = config_setup["client_a"]

        config_data = {
            "client_id": client.client_id,
            "fpy_target_percent": 98.0,
        }

        result = client_config_crud.create_client_config(db, config_data, supervisor)

        assert result is not None
        assert result.fpy_target_percent == 98.0

    def test_create_client_config_forbidden_other_client(self, config_setup):
        """Test supervisor cannot create config for other client."""
        db = config_setup["db"]
        supervisor_a = config_setup["supervisor_a"]
        client_b = config_setup["client_b"]

        config_data = {
            "client_id": client_b.client_id,
            "efficiency_target_percent": 80.0,
        }

        with pytest.raises(HTTPException) as exc_info:
            client_config_crud.create_client_config(db, config_data, supervisor_a)

        assert exc_info.value.status_code == 403

    def test_create_client_config_client_not_found(self, config_setup):
        """Test error when client doesn't exist."""
        db = config_setup["db"]
        admin = config_setup["admin"]

        config_data = {
            "client_id": "NON-EXISTENT",
            "efficiency_target_percent": 85.0,
        }

        with pytest.raises(HTTPException) as exc_info:
            client_config_crud.create_client_config(db, config_data, admin)

        assert exc_info.value.status_code == 404

    def test_create_client_config_already_exists(self, config_setup):
        """Test error when config already exists."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        config_data = {
            "client_id": client.client_id,
        }

        # Create first config
        client_config_crud.create_client_config(db, config_data, admin)

        # Try to create duplicate
        with pytest.raises(HTTPException) as exc_info:
            client_config_crud.create_client_config(db, config_data, admin)

        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail.lower()


class TestGetClientConfig:
    """Tests for get_client_config function."""

    def test_get_client_config_found(self, config_setup):
        """Test getting existing config."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        # Create config
        config_data = {"client_id": client.client_id}
        client_config_crud.create_client_config(db, config_data, admin)

        result = client_config_crud.get_client_config(
            db, client.client_id, admin
        )

        assert result is not None
        assert result.client_id == client.client_id

    def test_get_client_config_not_found(self, config_setup):
        """Test getting non-existent config."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        result = client_config_crud.get_client_config(
            db, client.client_id, admin, create_if_missing=False
        )

        assert result is None

    def test_get_client_config_create_if_missing(self, config_setup):
        """Test auto-creating config if missing."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        result = client_config_crud.get_client_config(
            db, client.client_id, admin, create_if_missing=True
        )

        assert result is not None
        assert result.client_id == client.client_id

    def test_get_client_config_forbidden_other_client(self, config_setup):
        """Test supervisor cannot get other client's config."""
        db = config_setup["db"]
        supervisor_a = config_setup["supervisor_a"]
        client_b = config_setup["client_b"]

        with pytest.raises(HTTPException) as exc_info:
            client_config_crud.get_client_config(
                db, client_b.client_id, supervisor_a
            )

        assert exc_info.value.status_code == 403


class TestGetClientConfigOrDefaults:
    """Tests for get_client_config_or_defaults function."""

    def test_get_client_config_or_defaults_with_config(self, config_setup):
        """Test returns config when it exists."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        # Create config with custom values
        config_data = {
            "client_id": client.client_id,
            "efficiency_target_percent": 92.0,
        }
        client_config_crud.create_client_config(db, config_data, admin)

        result = client_config_crud.get_client_config_or_defaults(
            db, client.client_id
        )

        assert result["efficiency_target_percent"] == 92.0
        assert result["is_default"] is False

    def test_get_client_config_or_defaults_returns_defaults(self, config_setup):
        """Test returns defaults when no config exists."""
        db = config_setup["db"]
        # Use client_b which has no config created (client_a may have cached config from prior test)
        client = config_setup["client_b"]

        # Clear cache to ensure we're testing fresh lookup
        from backend.cache import get_cache, build_cache_key
        cache = get_cache()
        cache_key = build_cache_key("client_config", client.client_id)
        cache.delete(cache_key)

        result = client_config_crud.get_client_config_or_defaults(
            db, client.client_id
        )

        assert result["is_default"] is True
        # Should have default values
        assert "efficiency_target_percent" in result
        assert "quality_target_ppm" in result


class TestUpdateClientConfig:
    """Tests for update_client_config function."""

    def test_update_client_config_success(self, config_setup):
        """Test updating config."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        # Create config
        config_data = {"client_id": client.client_id}
        client_config_crud.create_client_config(db, config_data, admin)

        # Update
        update_data = {"efficiency_target_percent": 95.0}
        result = client_config_crud.update_client_config(
            db, client.client_id, update_data, admin
        )

        assert result.efficiency_target_percent == 95.0

    def test_update_client_config_not_found(self, config_setup):
        """Test updating non-existent config."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        with pytest.raises(HTTPException) as exc_info:
            client_config_crud.update_client_config(
                db, client.client_id, {}, admin
            )

        assert exc_info.value.status_code == 404

    def test_update_client_config_forbidden_other_client(self, config_setup):
        """Test supervisor cannot update other client's config."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        supervisor_a = config_setup["supervisor_a"]
        client_b = config_setup["client_b"]

        # Create config for client_b
        config_data = {"client_id": client_b.client_id}
        client_config_crud.create_client_config(db, config_data, admin)

        # Supervisor A tries to update it
        with pytest.raises(HTTPException) as exc_info:
            client_config_crud.update_client_config(
                db, client_b.client_id, {"efficiency_target_percent": 50.0}, supervisor_a
            )

        assert exc_info.value.status_code == 403


class TestDeleteClientConfig:
    """Tests for delete_client_config function."""

    def test_delete_client_config_admin_success(self, config_setup):
        """Test admin can delete config."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        # Create config
        config_data = {"client_id": client.client_id}
        client_config_crud.create_client_config(db, config_data, admin)

        # Delete
        result = client_config_crud.delete_client_config(
            db, client.client_id, admin
        )

        assert result is True

    def test_delete_client_config_supervisor_forbidden(self, config_setup):
        """Test supervisor cannot delete config."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        supervisor = config_setup["supervisor_a"]
        client = config_setup["client_a"]

        # Create config
        config_data = {"client_id": client.client_id}
        client_config_crud.create_client_config(db, config_data, admin)

        # Supervisor tries to delete
        with pytest.raises(HTTPException) as exc_info:
            client_config_crud.delete_client_config(
                db, client.client_id, supervisor
            )

        assert exc_info.value.status_code == 403

    def test_delete_client_config_not_found(self, config_setup):
        """Test deleting non-existent config."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client = config_setup["client_a"]

        with pytest.raises(HTTPException) as exc_info:
            client_config_crud.delete_client_config(
                db, client.client_id, admin
            )

        assert exc_info.value.status_code == 404


class TestGetAllClientConfigs:
    """Tests for get_all_client_configs function."""

    def test_get_all_client_configs_admin(self, config_setup):
        """Test admin can get all configs."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client_a = config_setup["client_a"]
        client_b = config_setup["client_b"]

        # Create configs for both clients
        client_config_crud.create_client_config(
            db, {"client_id": client_a.client_id}, admin
        )
        client_config_crud.create_client_config(
            db, {"client_id": client_b.client_id}, admin
        )

        results = client_config_crud.get_all_client_configs(db, admin)

        assert len(results) == 2

    def test_get_all_client_configs_supervisor_forbidden(self, config_setup):
        """Test supervisor cannot get all configs."""
        db = config_setup["db"]
        supervisor = config_setup["supervisor_a"]

        with pytest.raises(HTTPException) as exc_info:
            client_config_crud.get_all_client_configs(db, supervisor)

        assert exc_info.value.status_code == 403

    def test_get_all_client_configs_with_pagination(self, config_setup):
        """Test pagination for get_all."""
        db = config_setup["db"]
        admin = config_setup["admin"]
        client_a = config_setup["client_a"]
        client_b = config_setup["client_b"]

        # Create configs
        client_config_crud.create_client_config(
            db, {"client_id": client_a.client_id}, admin
        )
        client_config_crud.create_client_config(
            db, {"client_id": client_b.client_id}, admin
        )

        # Get with limit
        results = client_config_crud.get_all_client_configs(
            db, admin, skip=0, limit=1
        )

        assert len(results) == 1


class TestGetGlobalDefaults:
    """Tests for get_global_defaults function."""

    def test_get_global_defaults(self, config_setup):
        """Test getting global defaults."""
        defaults = client_config_crud.get_global_defaults()

        assert isinstance(defaults, dict)
        assert "efficiency_target_percent" in defaults
        assert "quality_target_ppm" in defaults
        assert "otd_mode" in defaults
        assert defaults["efficiency_target_percent"] == 85.0
