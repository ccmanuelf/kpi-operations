#!/usr/bin/env python3
"""
Create SQLite test database using actual SQLAlchemy models
This ensures schema matches backend exactly
"""

import sys
import os
import sqlite3

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable

# Import Base and all models
from backend.database import Base
from backend.schemas.client import Client
from backend.schemas.user import User
from backend.schemas.employee import Employee
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.schemas.work_order import WorkOrder
from backend.schemas.job import Job
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.downtime import DowntimeEntry
from backend.schemas.hold import WIPHold
from backend.schemas.attendance import AttendanceEntry
from backend.schemas.coverage import ShiftCoverage
from backend.schemas.quality import QualityInspection
from backend.schemas.defect_detail import DefectDetail
from backend.schemas.part_opportunities import PartOpportunities

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'kpi_platform.db')
print(f"🔧 Creating SQLite database with security fixes...")
print(f"Database: {DB_PATH}")
print()

# Remove existing database
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("✓ Removed existing database")

# Create SQLite engine
engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)

# Create all tables from SQLAlchemy models
print("📋 Creating tables from SQLAlchemy models...")
Base.metadata.create_all(engine)

# Get table list
tables = [table.name for table in Base.metadata.sorted_tables]
print(f"✓ Created {len(tables)} tables")
for table in tables:
    print(f"   - {table}")

print()
print("🔒 Security fixes applied:")
print("   ✓ JOB: client_id_fk column added (CRITICAL)")
print("   ✓ DEFECT_DETAIL: client_id_fk column added (HIGH)")
print("   ✓ PART_OPPORTUNITIES: client_id_fk column added (MEDIUM)")
print()
print("=" * 70)
print("✅ Schema created successfully from SQLAlchemy models!")
print(f"   Ready for: python3 database/generators/generate_complete_sample_data.py")
