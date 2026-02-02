"""
MySQL Database Provider

Provides MySQL-specific engine configuration with QueuePool
and production-ready connection management.
"""
from typing import Dict, Any, List

from sqlalchemy import create_engine, Engine, text
from sqlalchemy.pool import QueuePool

from backend.db.providers.base import DatabaseProvider
from backend.db.dialects.mysql import MySQLDialect
import logging

logger = logging.getLogger(__name__)


class MySQLProvider(DatabaseProvider):
    """MySQL database provider.

    MySQL is the secondary production database option. It uses QueuePool
    with configurable pool size and pre-ping for connection health checks.

    Supports migrations from SQLite.
    """

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "mysql"

    @property
    def supports_migrations_from(self) -> List[str]:
        """MySQL can receive migrations from SQLite."""
        return ["sqlite"]

    def create_engine(self, url: str, **kwargs) -> Engine:
        """Create SQLAlchemy engine with MySQL-specific settings.

        Configures:
        - QueuePool with production defaults
        - pool_pre_ping for connection health
        - MySQL-specific connect args

        Args:
            url: MySQL connection URL.
            **kwargs: Additional engine options.

        Returns:
            Engine: Configured SQLAlchemy engine.
        """
        # Extract standard options
        echo = kwargs.pop('echo', False)

        # Get pool configuration
        pool_config = self.get_pool_config()

        # Override with any provided kwargs
        pool_size = kwargs.pop('pool_size', pool_config['pool_size'])
        max_overflow = kwargs.pop('max_overflow', pool_config['max_overflow'])
        pool_timeout = kwargs.pop('pool_timeout', pool_config['pool_timeout'])
        pool_recycle = kwargs.pop('pool_recycle', pool_config['pool_recycle'])

        # MySQL-specific connect args
        connect_args = kwargs.pop('connect_args', {})
        if 'charset' not in connect_args:
            connect_args['charset'] = 'utf8mb4'

        engine = create_engine(
            url,
            echo=echo,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,
            connect_args=connect_args,
            **kwargs
        )

        logger.info(
            f"MySQL engine created with QueuePool: "
            f"size={pool_size}, overflow={max_overflow}, "
            f"timeout={pool_timeout}s, recycle={pool_recycle}s"
        )
        return engine

    def get_pool_config(self) -> Dict[str, Any]:
        """Return optimal pool configuration for MySQL.

        Returns:
            Dict[str, Any]: Pool configuration with production defaults.
        """
        return {
            "poolclass": QueuePool,
            "pool_size": 20,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600,
            "pool_pre_ping": True,
        }

    def validate_connection(self, engine: Engine) -> bool:
        """Test MySQL connection.

        Args:
            engine: SQLAlchemy engine to test.

        Returns:
            bool: True if connection is valid.
        """
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT VERSION()"))
                version = result.scalar()
                logger.debug(f"MySQL server version: {version}")
                return True
        except Exception as e:
            logger.error(f"MySQL connection validation failed: {e}")
            return False

    def get_dialect_adapter(self) -> MySQLDialect:
        """Return MySQL dialect adapter.

        Returns:
            MySQLDialect: MySQL-specific SQL adapter.
        """
        return MySQLDialect()

    def get_connection_info(self, engine: Engine) -> Dict[str, Any]:
        """Get MySQL-specific connection info.

        Args:
            engine: SQLAlchemy engine.

        Returns:
            Dict[str, Any]: Connection information.
        """
        url = engine.url
        return {
            "provider": self.provider_name,
            "host": url.host or "localhost",
            "port": url.port or 3306,
            "database": url.database,
            "driver": url.drivername,
            "username": url.username,
        }
