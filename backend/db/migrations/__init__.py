"""
Database Migration Infrastructure

Provides complete migration capabilities:
- SchemaInitializer: Create schema on target database from SQLAlchemy models
- DemoDataSeeder: Seed demo data after schema creation
- DataMigrator: Copy existing data from source to target database

Migration modes supported:
1. Fresh Start: schema + demo data only (for new installations)
2. Preserve Data: schema + copy existing data + optional demo data (for production)
"""
from backend.db.migrations.schema_initializer import SchemaInitializer
from backend.db.migrations.demo_seeder import DemoDataSeeder
from backend.db.migrations.data_migrator import DataMigrator, DataMigrationError

__all__ = [
    "SchemaInitializer",
    "DemoDataSeeder",
    "DataMigrator",
    "DataMigrationError",
]
