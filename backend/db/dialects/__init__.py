"""
SQL Dialect Adapters Package

Provides dialect-specific SQL generation for differences between databases:
- Last insert ID retrieval
- Upsert (INSERT ... ON CONFLICT) syntax
- Boolean literals
- Auto-increment definitions
"""

from backend.db.dialects.base import DialectAdapter
from backend.db.dialects.sqlite import SQLiteDialect
from backend.db.dialects.mariadb import MariaDBDialect
from backend.db.dialects.mysql import MySQLDialect

__all__ = [
    "DialectAdapter",
    "SQLiteDialect",
    "MariaDBDialect",
    "MySQLDialect",
]
