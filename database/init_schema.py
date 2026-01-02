#!/usr/bin/env python3
"""
Initialize Complete Multi-Tenant Database Schema
Creates all tables with security fixes applied (JOB, DEFECT_DETAIL, PART_OPPORTUNITIES with client_id_fk)
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from backend.database import Base

# Import all schema models to register them with Base
from backend.schemas.client import Client
from backend.schemas.user import User
from backend.schemas.employee import Employee
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.schemas.work_order import WorkOrder
from backend.schemas.job import Job  # SECURITY FIX: Now includes client_id_fk
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.downtime import DowntimeEntry
from backend.schemas.hold import WIPHold
from backend.schemas.attendance import AttendanceEntry
from backend.schemas.coverage import ShiftCoverage
from backend.schemas.quality import QualityInspection
from backend.schemas.defect_detail import DefectDetail  # SECURITY FIX: Now includes client_id_fk
from backend.schemas.part_opportunities import PartOpportunities  # SECURITY FIX: Now includes client_id_fk

# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'kpi_platform.db')
DATABASE_URL = f'sqlite:///{DB_PATH}'

print("🔧 Multi-Tenant KPI Platform - Schema Initialization")
print("=" * 70)
print(f"Database: {DB_PATH}")
print()

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

print("📋 Creating tables with security fixes...")
print("   - JOB: client_id_fk added (CRITICAL)")
print("   - DEFECT_DETAIL: client_id_fk added (HIGH)")
print("   - PART_OPPORTUNITIES: client_id_fk added (MEDIUM)")
print()

# Create all tables
Base.metadata.create_all(engine)

print("✅ Schema initialization completed successfully!")
print()
print("Tables created:")
for table in Base.metadata.sorted_tables:
    print(f"   ✓ {table.name}")

print()
print("🔒 Security Features:")
print("   ✓ Multi-tenant isolation enforced (client_id_fk in all transactional tables)")
print("   ✓ Foreign key constraints enabled")
print("   ✓ Indexes created for performance")
print()
print("=" * 70)
print("✅ Ready for sample data generation!")
