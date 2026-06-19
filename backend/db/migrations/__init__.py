"""
Database Migration Infrastructure

Provides complete migration capabilities:
- SchemaInitializer: Create schema on target database from SQLAlchemy models
- DataMigrator: Copy existing data from source to target database

Demo seeding is the canonical backend.scripts.init_demo_database.init_database
(Run 8 unification): seeds the global DB (db=None) or a migration-target session
(db=<session>). The old DemoDataSeeder was removed.

Migration modes supported:
1. Fresh Start: schema + demo data only (for new installations)
2. Preserve Data: schema + copy existing data + optional demo data (for production)
"""

from backend.db.migrations.schema_initializer import SchemaInitializer
from backend.db.migrations.data_migrator import DataMigrator, DataMigrationError

__all__ = [
    "SchemaInitializer",
    "DataMigrator",
    "DataMigrationError",
]
