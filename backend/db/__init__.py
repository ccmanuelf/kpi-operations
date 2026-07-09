"""
Database Provider Abstraction Layer

This module provides a provider-agnostic database infrastructure enabling
runtime selection of SQLite, MariaDB/MySQL, or PostgreSQL with one-way
migration capability.

Key Components:
- DatabaseProviderFactory: Creates appropriate provider based on URL
- DialectAdapters: Handle SQL dialect differences

Usage:
    from backend.db.factory import DatabaseProviderFactory

    factory = DatabaseProviderFactory.get_instance()
    engine = factory.get_engine(database_url)
"""

from backend.db.factory import DatabaseProviderFactory
from backend.db.config import DatabaseConfig

__all__ = [
    "DatabaseProviderFactory",
    "DatabaseConfig",
]
