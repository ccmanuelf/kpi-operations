"""
SQLite Database Provider

Provides SQLite-specific engine configuration with NullPool
(no connection pooling) due to SQLite's threading limitations.
"""
from typing import Dict, Any, List

from sqlalchemy import create_engine, Engine, event, text
from sqlalchemy.pool import NullPool

from backend.db.providers.base import DatabaseProvider
from backend.db.dialects.sqlite import SQLiteDialect
import logging

logger = logging.getLogger(__name__)


class SQLiteProvider(DatabaseProvider):
    """SQLite database provider.

    SQLite is the default development and demo database. It uses NullPool
    since SQLite doesn't benefit from connection pooling and has threading
    limitations.

    Note: SQLite cannot receive migrations (only migrate FROM).
    """

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "sqlite"

    @property
    def supports_migrations_from(self) -> List[str]:
        """SQLite cannot receive migrations from other providers."""
        return []  # SQLite is always the source, never the target

    def create_engine(self, url: str, **kwargs) -> Engine:
        """Create SQLAlchemy engine with SQLite-specific settings.

        Configures:
        - NullPool (no pooling)
        - check_same_thread=False for multi-threaded access
        - Foreign key pragma enabled

        Args:
            url: SQLite database URL (e.g., sqlite:///path/to/db.sqlite)
            **kwargs: Additional engine options.

        Returns:
            Engine: Configured SQLAlchemy engine.
        """
        # Extract echo setting
        echo = kwargs.pop('echo', False)

        engine = create_engine(
            url,
            echo=echo,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
            **kwargs
        )

        # Enable foreign keys on connect
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            """Enable foreign key constraints."""
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        logger.info("SQLite engine created with NullPool and foreign keys enabled")
        return engine

    def get_pool_config(self) -> Dict[str, Any]:
        """Return pool configuration (NullPool for SQLite).

        Returns:
            Dict[str, Any]: Pool configuration.
        """
        return {
            "poolclass": NullPool,
            "pool_pre_ping": False,  # Not needed for NullPool
        }

    def validate_connection(self, engine: Engine) -> bool:
        """Test SQLite connection.

        Args:
            engine: SQLAlchemy engine to test.

        Returns:
            bool: True if connection is valid.
        """
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT sqlite_version()"))
                version = result.scalar()
                logger.debug(f"SQLite version: {version}")
            return True
        except Exception as e:
            logger.error(f"SQLite connection validation failed: {e}")
            return False

    def get_dialect_adapter(self) -> SQLiteDialect:
        """Return SQLite dialect adapter.

        Returns:
            SQLiteDialect: SQLite-specific SQL adapter.
        """
        return SQLiteDialect()

    def get_connection_info(self, engine: Engine) -> Dict[str, Any]:
        """Get SQLite-specific connection info.

        Args:
            engine: SQLAlchemy engine.

        Returns:
            Dict[str, Any]: Connection information.
        """
        url = engine.url
        db_path = url.database or ":memory:"

        return {
            "provider": self.provider_name,
            "database": db_path,
            "driver": "sqlite3",
            "in_memory": db_path == ":memory:" or not db_path,
        }
