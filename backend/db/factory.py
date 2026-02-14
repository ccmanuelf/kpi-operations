"""
Database Provider Factory

Singleton factory for creating database providers based on connection URL.
Handles provider detection and engine lifecycle management.
"""

from typing import Optional, Dict, Type, Any
import logging
import re

from sqlalchemy import Engine

from backend.db.providers.base import DatabaseProvider
from backend.db.providers.sqlite import SQLiteProvider
from backend.db.providers.mariadb import MariaDBProvider
from backend.db.providers.mysql import MySQLProvider
from backend.db.dialects.base import DialectAdapter

logger = logging.getLogger(__name__)


class DatabaseProviderFactory:
    """Factory for creating database providers based on URL.

    This is a singleton factory that manages provider instances
    and engine lifecycle. It detects the appropriate provider
    from the database URL and creates configured engines.
    """

    # Provider class registry
    _providers: Dict[str, Type[DatabaseProvider]] = {
        "sqlite": SQLiteProvider,
        "mariadb": MariaDBProvider,
        "mysql": MySQLProvider,
        "mysql+pymysql": MariaDBProvider,  # PyMySQL driver -> MariaDB provider
        "mysql+mysqlconnector": MySQLProvider,  # MySQL Connector
        "mysql+mariadbconnector": MariaDBProvider,  # MariaDB Connector
    }

    # Singleton instance
    _instance: Optional["DatabaseProviderFactory"] = None

    # Instance state
    _current_provider: Optional[DatabaseProvider] = None
    _engine: Optional[Engine] = None
    _current_url: Optional[str] = None

    def __new__(cls) -> "DatabaseProviderFactory":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "DatabaseProviderFactory":
        """Get singleton factory instance.

        Returns:
            DatabaseProviderFactory: Singleton instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state (for testing).

        Disposes engine and clears cached provider/engine.
        """
        if cls._instance is not None:
            if cls._instance._engine is not None:
                try:
                    cls._instance._engine.dispose()
                except Exception as e:
                    logger.warning(f"Error disposing engine: {e}")
            cls._instance._current_provider = None
            cls._instance._engine = None
            cls._instance._current_url = None
        cls._instance = None

    def detect_provider(self, url: str) -> str:
        """Detect provider type from database URL.

        Args:
            url: Database connection URL.

        Returns:
            str: Provider identifier ('sqlite', 'mariadb', 'mysql').

        Raises:
            ValueError: If provider cannot be detected from URL.
        """
        url_lower = url.lower()

        # SQLite detection
        if "sqlite" in url_lower:
            return "sqlite"

        # MariaDB explicit detection
        if "mariadb" in url_lower:
            return "mariadb"

        # MySQL/MariaDB by driver
        if "mysql+pymysql" in url_lower:
            return "mysql+pymysql"  # Use MariaDB provider

        if "mysql+mysqlconnector" in url_lower:
            return "mysql+mysqlconnector"

        if "mysql+mariadbconnector" in url_lower:
            return "mysql+mariadbconnector"

        # Generic MySQL
        if "mysql" in url_lower:
            return "mysql"

        # PostgreSQL (planned)
        if "postgresql" in url_lower or "postgres" in url_lower:
            raise ValueError("PostgreSQL support is planned but not yet implemented")

        raise ValueError(f"Unknown database provider in URL: {url}")

    def create_provider(self, url: str) -> DatabaseProvider:
        """Create appropriate provider for URL.

        Args:
            url: Database connection URL.

        Returns:
            DatabaseProvider: Configured provider instance.

        Raises:
            ValueError: If no provider available for the URL.
        """
        provider_key = self.detect_provider(url)
        provider_class = self._providers.get(provider_key)

        if not provider_class:
            raise ValueError(f"No provider registered for: {provider_key}")

        provider = provider_class()
        logger.info(f"Created {provider.provider_name} provider for URL")
        return provider

    def get_engine(self, url: str, echo: bool = False, **kwargs) -> Engine:
        """Get or create engine for URL.

        Returns cached engine if URL matches, otherwise creates new engine.

        Args:
            url: Database connection URL.
            echo: Enable SQL echo logging.
            **kwargs: Additional engine configuration.

        Returns:
            Engine: SQLAlchemy engine instance.
        """
        # Return cached engine if URL matches
        if self._engine is not None and self._current_url == url:
            return self._engine

        # Create new provider and engine
        if self._engine is not None:
            logger.info("Disposing previous engine")
            try:
                self._engine.dispose()
            except Exception as e:
                logger.warning(f"Error disposing engine: {e}")

        self._current_provider = self.create_provider(url)
        self._engine = self._current_provider.create_engine(url, echo=echo, **kwargs)
        self._current_url = url

        logger.info(f"Created engine for {self._current_provider.provider_name}")
        return self._engine

    def get_current_provider(self) -> Optional[DatabaseProvider]:
        """Get currently active provider.

        Returns:
            Optional[DatabaseProvider]: Current provider or None.
        """
        return self._current_provider

    def get_dialect_adapter(self) -> Optional[DialectAdapter]:
        """Get dialect adapter for current provider.

        Returns:
            Optional[DialectAdapter]: Dialect adapter or None.
        """
        if self._current_provider:
            return self._current_provider.get_dialect_adapter()
        return None

    def validate_connection(self, url: str) -> Dict[str, Any]:
        """Test connection to a database URL.

        Creates a temporary provider and engine to test connection.
        Does not affect the current engine.

        Args:
            url: Database connection URL to test.

        Returns:
            Dict[str, Any]: Validation result with success status and info.
        """
        try:
            provider = self.create_provider(url)
            engine = provider.create_engine(url)

            is_valid = provider.validate_connection(engine)
            conn_info = provider.get_connection_info(engine) if is_valid else {}

            # Clean up test engine
            engine.dispose()

            return {
                "success": is_valid,
                "provider": provider.provider_name,
                "connection_info": conn_info,
                "message": "Connection successful" if is_valid else "Connection validation failed",
            }
        except Exception as e:
            return {
                "success": False,
                "provider": None,
                "connection_info": {},
                "message": str(e),
            }

    def get_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available providers.

        Returns:
            Dict[str, Dict[str, Any]]: Provider information by name.
        """
        # Deduplicate by provider name
        seen = set()
        providers = {}

        for key, provider_class in self._providers.items():
            provider = provider_class()
            if provider.provider_name not in seen:
                seen.add(provider.provider_name)
                providers[provider.provider_name] = {
                    "name": provider.provider_name,
                    "supports_migrations_from": provider.supports_migrations_from,
                    "drivers": [k for k, v in self._providers.items() if v == provider_class],
                }

        return providers
