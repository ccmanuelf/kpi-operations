"""
Abstract Base Database Provider

Defines the interface that all database providers must implement.
This enables runtime selection of SQLite, MariaDB/MySQL, or PostgreSQL.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from backend.db.dialects.base import DialectAdapter


class DatabaseProvider(ABC):
    """Abstract base class for database providers.

    All database providers must implement this interface to ensure
    consistent behavior across different database backends.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (sqlite, mariadb, mysql, postgresql).

        Returns:
            str: Unique identifier for this provider type.
        """
        pass

    @property
    @abstractmethod
    def supports_migrations_from(self) -> List[str]:
        """List of providers this can migrate FROM.

        Returns:
            List[str]: Provider names that can be migrated to this provider.
                      Empty list means no migrations supported.
        """
        pass

    @abstractmethod
    def create_engine(self, url: str, **kwargs) -> "Engine":
        """Create SQLAlchemy engine with provider-specific settings.

        Args:
            url: Database connection URL.
            **kwargs: Additional engine configuration options.

        Returns:
            Engine: Configured SQLAlchemy engine instance.
        """
        pass

    @abstractmethod
    def get_pool_config(self) -> Dict[str, Any]:
        """Return optimal pool configuration for this provider.

        Returns:
            Dict[str, Any]: Pool configuration parameters including
                          poolclass, pool_size, max_overflow, etc.
        """
        pass

    @abstractmethod
    def validate_connection(self, engine: "Engine") -> bool:
        """Test connection and return True if valid.

        Args:
            engine: SQLAlchemy engine to test.

        Returns:
            bool: True if connection is valid, False otherwise.
        """
        pass

    @abstractmethod
    def get_dialect_adapter(self) -> "DialectAdapter":
        """Return dialect-specific SQL adapter.

        Returns:
            DialectAdapter: Adapter for handling SQL dialect differences.
        """
        pass

    def get_connection_info(self, engine: "Engine") -> Dict[str, Any]:
        """Get connection information for display purposes.

        Args:
            engine: SQLAlchemy engine instance.

        Returns:
            Dict[str, Any]: Connection information dictionary.
        """
        url = engine.url
        return {
            "provider": self.provider_name,
            "host": url.host or "localhost",
            "port": url.port,
            "database": url.database,
            "driver": url.drivername,
        }
