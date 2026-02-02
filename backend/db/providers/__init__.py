"""
Database Providers Package

Provides provider implementations for different database backends:
- SQLite: Development and demo database
- MariaDB: Primary production target
- MySQL: Secondary production option
- PostgreSQL: Tertiary option (planned)
"""
from backend.db.providers.base import DatabaseProvider
from backend.db.providers.sqlite import SQLiteProvider
from backend.db.providers.mariadb import MariaDBProvider
from backend.db.providers.mysql import MySQLProvider

__all__ = [
    "DatabaseProvider",
    "SQLiteProvider",
    "MariaDBProvider",
    "MySQLProvider",
]
