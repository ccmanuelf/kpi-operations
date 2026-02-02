"""
Database Migration Infrastructure

Provides simplified migration capabilities:
- SchemaInitializer: Create schema on target database from SQLAlchemy models
- DemoDataSeeder: Seed demo data after schema creation

Note: Since SQLite contains only demo data, we skip complex data migration.
Instead: create schema on target → seed demo data → switch provider.
"""
from backend.db.migrations.schema_initializer import SchemaInitializer
from backend.db.migrations.demo_seeder import DemoDataSeeder

__all__ = [
    "SchemaInitializer",
    "DemoDataSeeder",
]
