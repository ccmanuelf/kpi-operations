"""
Database Provider Configuration

Centralized configuration for database providers with environment-aware defaults.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import os


@dataclass
class PoolConfig:
    """Connection pool configuration."""
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True


@dataclass
class DatabaseConfig:
    """Database configuration with provider-specific settings.

    This class holds all configuration needed for database connection
    and pool management.
    """
    # Connection settings
    url: str = ""
    provider_type: str = "sqlite"

    # Pool configuration
    pool_config: PoolConfig = field(default_factory=PoolConfig)

    # Debug settings
    echo: bool = False
    echo_pool: bool = False

    # State file location
    state_dir: str = "database"

    @classmethod
    def from_environment(cls) -> "DatabaseConfig":
        """Create configuration from environment variables.

        Returns:
            DatabaseConfig: Configuration instance with env values.
        """
        return cls(
            url=os.environ.get("DATABASE_URL", ""),
            provider_type=os.environ.get("DATABASE_PROVIDER", "sqlite"),
            pool_config=PoolConfig(
                pool_size=int(os.environ.get("DATABASE_POOL_SIZE", "20")),
                max_overflow=int(os.environ.get("DATABASE_MAX_OVERFLOW", "10")),
                pool_timeout=int(os.environ.get("DATABASE_POOL_TIMEOUT", "30")),
                pool_recycle=int(os.environ.get("DATABASE_POOL_RECYCLE", "3600")),
                pool_pre_ping=os.environ.get("DATABASE_POOL_PRE_PING", "true").lower() == "true",
            ),
            echo=os.environ.get("DATABASE_ECHO", "false").lower() == "true",
            state_dir=os.environ.get("DATABASE_STATE_DIR", "database"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dict[str, Any]: Configuration as dictionary.
        """
        return {
            "url": self.url,
            "provider_type": self.provider_type,
            "pool_config": {
                "pool_size": self.pool_config.pool_size,
                "max_overflow": self.pool_config.max_overflow,
                "pool_timeout": self.pool_config.pool_timeout,
                "pool_recycle": self.pool_config.pool_recycle,
                "pool_pre_ping": self.pool_config.pool_pre_ping,
            },
            "echo": self.echo,
            "state_dir": self.state_dir,
        }


# Default pool configurations by provider type
DEFAULT_POOL_CONFIGS: Dict[str, PoolConfig] = {
    "sqlite": PoolConfig(
        pool_size=0,  # NullPool doesn't use these
        max_overflow=0,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=False,  # SQLite doesn't need pre-ping
    ),
    "mariadb": PoolConfig(
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    ),
    "mysql": PoolConfig(
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    ),
    "postgresql": PoolConfig(
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    ),
}
