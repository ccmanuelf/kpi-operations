"""
Unit Tests for Database Providers

Tests for SQLiteProvider, MariaDBProvider, MySQLProvider, and DatabaseProviderFactory.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import Engine
from sqlalchemy.pool import NullPool, QueuePool

from backend.db.providers.base import DatabaseProvider
from backend.db.providers.sqlite import SQLiteProvider
from backend.db.providers.mariadb import MariaDBProvider
from backend.db.providers.mysql import MySQLProvider
from backend.db.factory import DatabaseProviderFactory


class TestSQLiteProvider:
    """Tests for SQLiteProvider."""

    def test_provider_name(self):
        """Test provider name is 'sqlite'."""
        provider = SQLiteProvider()
        assert provider.provider_name == "sqlite"

    def test_supports_no_migrations_from(self):
        """Test SQLite cannot receive migrations."""
        provider = SQLiteProvider()
        assert provider.supports_migrations_from == []

    def test_create_engine_uses_nullpool(self, tmp_path):
        """Test engine uses NullPool for SQLite."""
        provider = SQLiteProvider()
        db_path = tmp_path / "test.db"
        engine = provider.create_engine(f"sqlite:///{db_path}")

        # Verify NullPool is used
        assert isinstance(engine.pool, NullPool)
        engine.dispose()

    def test_create_engine_with_echo(self, tmp_path):
        """Test engine can be created with echo enabled."""
        provider = SQLiteProvider()
        db_path = tmp_path / "test.db"
        engine = provider.create_engine(f"sqlite:///{db_path}", echo=True)

        assert engine.echo is True
        engine.dispose()

    def test_validate_connection_success(self, tmp_path):
        """Test connection validation succeeds for valid database."""
        provider = SQLiteProvider()
        db_path = tmp_path / "test.db"
        engine = provider.create_engine(f"sqlite:///{db_path}")

        assert provider.validate_connection(engine) is True
        engine.dispose()

    def test_get_pool_config(self):
        """Test pool configuration returns NullPool settings."""
        provider = SQLiteProvider()
        config = provider.get_pool_config()

        assert config["poolclass"] == NullPool
        assert config["pool_pre_ping"] is False

    def test_get_dialect_adapter(self):
        """Test dialect adapter is SQLiteDialect."""
        provider = SQLiteProvider()
        adapter = provider.get_dialect_adapter()

        assert adapter.dialect_name == "sqlite"

    def test_get_connection_info(self, tmp_path):
        """Test connection info extraction."""
        provider = SQLiteProvider()
        db_path = tmp_path / "test.db"
        engine = provider.create_engine(f"sqlite:///{db_path}")

        info = provider.get_connection_info(engine)
        assert info["provider"] == "sqlite"
        assert "test.db" in info["database"]
        engine.dispose()


class TestMariaDBProvider:
    """Tests for MariaDBProvider."""

    def test_provider_name(self):
        """Test provider name is 'mariadb'."""
        provider = MariaDBProvider()
        assert provider.provider_name == "mariadb"

    def test_supports_migrations_from_sqlite(self):
        """Test MariaDB supports migrations from SQLite."""
        provider = MariaDBProvider()
        assert "sqlite" in provider.supports_migrations_from

    def test_get_pool_config(self):
        """Test pool configuration for MariaDB."""
        provider = MariaDBProvider()
        config = provider.get_pool_config()

        assert config["poolclass"] == QueuePool
        assert config["pool_size"] == 20
        assert config["max_overflow"] == 10
        assert config["pool_timeout"] == 30
        assert config["pool_recycle"] == 3600
        assert config["pool_pre_ping"] is True

    def test_get_dialect_adapter(self):
        """Test dialect adapter is MariaDBDialect."""
        provider = MariaDBProvider()
        adapter = provider.get_dialect_adapter()

        assert adapter.dialect_name == "mariadb"

    @patch('backend.db.providers.mariadb.create_engine')
    def test_create_engine_with_pool_settings(self, mock_create_engine):
        """Test engine creation with pool settings."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        provider = MariaDBProvider()
        url = "mysql+pymysql://user:pass@localhost/db"
        engine = provider.create_engine(url, pool_size=30)

        mock_create_engine.assert_called_once()
        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs["pool_size"] == 30
        assert call_kwargs["pool_pre_ping"] is True


class TestMySQLProvider:
    """Tests for MySQLProvider."""

    def test_provider_name(self):
        """Test provider name is 'mysql'."""
        provider = MySQLProvider()
        assert provider.provider_name == "mysql"

    def test_supports_migrations_from_sqlite(self):
        """Test MySQL supports migrations from SQLite."""
        provider = MySQLProvider()
        assert "sqlite" in provider.supports_migrations_from

    def test_get_pool_config(self):
        """Test pool configuration for MySQL."""
        provider = MySQLProvider()
        config = provider.get_pool_config()

        assert config["poolclass"] == QueuePool
        assert config["pool_pre_ping"] is True

    def test_get_dialect_adapter(self):
        """Test dialect adapter is MySQLDialect."""
        provider = MySQLProvider()
        adapter = provider.get_dialect_adapter()

        assert adapter.dialect_name == "mysql"


class TestDatabaseProviderFactory:
    """Tests for DatabaseProviderFactory."""

    def setup_method(self):
        """Reset factory before each test."""
        DatabaseProviderFactory.reset()

    def teardown_method(self):
        """Clean up factory after each test."""
        DatabaseProviderFactory.reset()

    def test_singleton_pattern(self):
        """Test factory is a singleton."""
        f1 = DatabaseProviderFactory.get_instance()
        f2 = DatabaseProviderFactory.get_instance()
        assert f1 is f2

    def test_detect_sqlite(self):
        """Test SQLite provider detection."""
        factory = DatabaseProviderFactory.get_instance()
        assert factory.detect_provider("sqlite:///test.db") == "sqlite"
        assert factory.detect_provider("sqlite:///:memory:") == "sqlite"

    def test_detect_mariadb(self):
        """Test MariaDB provider detection."""
        factory = DatabaseProviderFactory.get_instance()
        assert factory.detect_provider("mariadb+pymysql://user:pass@host/db") == "mariadb"

    def test_detect_mysql_pymysql(self):
        """Test MySQL with PyMySQL driver detection."""
        factory = DatabaseProviderFactory.get_instance()
        assert factory.detect_provider("mysql+pymysql://user:pass@host/db") == "mysql+pymysql"

    def test_detect_mysql_connector(self):
        """Test MySQL with MySQL Connector detection."""
        factory = DatabaseProviderFactory.get_instance()
        result = factory.detect_provider("mysql+mysqlconnector://user:pass@host/db")
        assert result == "mysql+mysqlconnector"

    def test_detect_generic_mysql(self):
        """Test generic MySQL detection."""
        factory = DatabaseProviderFactory.get_instance()
        assert factory.detect_provider("mysql://user:pass@host/db") == "mysql"

    def test_detect_unknown_raises_error(self):
        """Test unknown provider raises ValueError."""
        factory = DatabaseProviderFactory.get_instance()
        with pytest.raises(ValueError, match="Unknown database provider"):
            factory.detect_provider("unknown://test")

    def test_create_sqlite_provider(self):
        """Test creating SQLite provider."""
        factory = DatabaseProviderFactory.get_instance()
        provider = factory.create_provider("sqlite:///test.db")
        assert isinstance(provider, SQLiteProvider)

    def test_create_mariadb_provider(self):
        """Test creating MariaDB provider for PyMySQL driver."""
        factory = DatabaseProviderFactory.get_instance()
        provider = factory.create_provider("mysql+pymysql://user:pass@host/db")
        assert isinstance(provider, MariaDBProvider)

    def test_get_engine_caches_engine(self, tmp_path):
        """Test engine is cached for same URL."""
        factory = DatabaseProviderFactory.get_instance()
        db_path = tmp_path / "test.db"
        url = f"sqlite:///{db_path}"

        engine1 = factory.get_engine(url)
        engine2 = factory.get_engine(url)

        assert engine1 is engine2
        engine1.dispose()

    def test_get_engine_creates_new_for_different_url(self, tmp_path):
        """Test new engine for different URL."""
        factory = DatabaseProviderFactory.get_instance()
        db1 = tmp_path / "test1.db"
        db2 = tmp_path / "test2.db"

        engine1 = factory.get_engine(f"sqlite:///{db1}")
        engine2 = factory.get_engine(f"sqlite:///{db2}")

        # Engine2 should replace engine1 (singleton pattern)
        assert factory._engine is engine2
        engine2.dispose()

    def test_get_current_provider(self, tmp_path):
        """Test getting current provider."""
        factory = DatabaseProviderFactory.get_instance()
        db_path = tmp_path / "test.db"

        factory.get_engine(f"sqlite:///{db_path}")
        provider = factory.get_current_provider()

        assert provider is not None
        assert provider.provider_name == "sqlite"

    def test_validate_connection(self, tmp_path):
        """Test connection validation."""
        factory = DatabaseProviderFactory.get_instance()
        db_path = tmp_path / "test.db"

        result = factory.validate_connection(f"sqlite:///{db_path}")

        assert result["success"] is True
        assert result["provider"] == "sqlite"

    def test_validate_connection_invalid_url(self):
        """Test validation with invalid URL."""
        factory = DatabaseProviderFactory.get_instance()

        result = factory.validate_connection("invalid://url")

        assert result["success"] is False
        assert "Unknown database provider" in result["message"]

    def test_get_available_providers(self):
        """Test getting available providers info."""
        factory = DatabaseProviderFactory.get_instance()
        providers = factory.get_available_providers()

        assert "sqlite" in providers
        assert "mariadb" in providers
        assert "mysql" in providers

        assert providers["sqlite"]["supports_migrations_from"] == []
        assert "sqlite" in providers["mariadb"]["supports_migrations_from"]

    def test_reset_clears_state(self, tmp_path):
        """Test reset clears singleton state."""
        factory = DatabaseProviderFactory.get_instance()
        db_path = tmp_path / "test.db"
        factory.get_engine(f"sqlite:///{db_path}")

        assert factory._engine is not None

        DatabaseProviderFactory.reset()
        new_factory = DatabaseProviderFactory.get_instance()

        assert new_factory._engine is None
        assert new_factory._current_provider is None
