#!/usr/bin/env python3
"""
Initialize SQLite Database Schema with All Security Fixes
Standalone script that doesn't require backend configuration
"""

import sys
import os
import sqlite3

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'kpi_platform.db')

print("🔧 Multi-Tenant KPI Platform - SQLite Schema Initialization")
print("=" * 70)
print(f"Database: {DB_PATH}")
print()

# Remove existing database to start fresh
if os.path.exists(DB_PATH):
    print("⚠️  Removing existing database to apply security fixes...")
    os.remove(DB_PATH)
    print("   ✓ Removed")
    print()

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Enable foreign keys
cursor.execute("PRAGMA foreign_keys = ON")

print("📋 Creating tables with security fixes...")

# ============================================================================
# CORE TABLES
# ============================================================================

# CLIENT table (Multi-tenant foundation)
cursor.execute("""
CREATE TABLE CLIENT (
    client_id VARCHAR(50) PRIMARY KEY,
    client_name VARCHAR(255) NOT NULL,
    client_type VARCHAR(100),
    timezone VARCHAR(10),
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
)
""")
print("   ✓ CLIENT")

# USER table
cursor.execute("""
CREATE TABLE USER (
    user_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    full_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    role VARCHAR(20) CHECK(role IN ('ADMIN', 'POWERUSER', 'LEADER', 'OPERATOR', 'SYSTEM')),
    client_id_assigned VARCHAR(50),
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (client_id_assigned) REFERENCES CLIENT(client_id)
)
""")
print("   ✓ USER")

# EMPLOYEE table
cursor.execute("""
CREATE TABLE EMPLOYEE (
    employee_id VARCHAR(50) PRIMARY KEY,
    employee_name VARCHAR(255) NOT NULL,
    client_id_assigned VARCHAR(50),
    is_floating_pool INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (client_id_assigned) REFERENCES CLIENT(client_id)
)
""")
print("   ✓ EMPLOYEE")

# PRODUCT table
cursor.execute("""
CREATE TABLE PRODUCT (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    ideal_cycle_time DECIMAL(10, 4),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
print("   ✓ PRODUCT")

# SHIFT table
cursor.execute("""
CREATE TABLE SHIFT (
    shift_id INTEGER PRIMARY KEY,
    shift_name VARCHAR(100) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
print("   ✓ SHIFT")

# WORK_ORDER table - Matches WorkOrder SQLAlchemy schema
cursor.execute("""
CREATE TABLE WORK_ORDER (
    work_order_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    style_model VARCHAR(100) NOT NULL,
    planned_quantity INTEGER NOT NULL,
    actual_quantity INTEGER DEFAULT 0,
    planned_start_date DATETIME,
    actual_start_date DATETIME,
    planned_ship_date DATETIME,
    required_date DATETIME,
    actual_delivery_date DATETIME,
    ideal_cycle_time DECIMAL(10, 4),
    calculated_cycle_time DECIMAL(10, 4),
    status VARCHAR(50) DEFAULT 'ACTIVE',
    priority VARCHAR(20),
    qc_approved INTEGER DEFAULT 0,
    qc_approved_by INTEGER,
    qc_approved_date DATETIME,
    rejection_reason TEXT,
    rejected_by INTEGER,
    rejected_date DATETIME,
    total_run_time_hours DECIMAL(10, 2),
    total_employees_assigned INTEGER,
    notes TEXT,
    customer_po_number VARCHAR(100),
    internal_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id)
)
""")
print("   ✓ WORK_ORDER")

# JOB table (SECURITY FIX - client_id added)
cursor.execute("""
CREATE TABLE JOB (
    job_id VARCHAR(50) PRIMARY KEY,
    work_order_id VARCHAR(50) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    operation_name VARCHAR(255) NOT NULL,
    operation_code VARCHAR(50),
    sequence_number INTEGER NOT NULL,
    part_number VARCHAR(100),
    part_description VARCHAR(255),
    planned_quantity INTEGER,
    completed_quantity INTEGER DEFAULT 0,
    planned_hours DECIMAL(10, 2),
    actual_hours DECIMAL(10, 2),
    is_completed INTEGER DEFAULT 0,
    completed_date DATETIME,
    assigned_employee_id INTEGER,
    assigned_shift_id INTEGER,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (work_order_id) REFERENCES WORK_ORDER(work_order_id),
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id)
)
""")
print("   ✓ JOB (with client_id - CRITICAL SECURITY FIX)")

# ============================================================================
# PHASE 1 - PRODUCTION TRACKING
# ============================================================================

# PRODUCTION_ENTRY table - Matches ProductionEntry SQLAlchemy schema
cursor.execute("""
CREATE TABLE PRODUCTION_ENTRY (
    production_entry_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    product_id INTEGER,
    shift_id INTEGER NOT NULL,
    work_order_id VARCHAR(50),
    production_date DATETIME NOT NULL,
    shift_date DATETIME NOT NULL,
    units_produced INTEGER NOT NULL,
    run_time_hours DECIMAL(10, 2) NOT NULL,
    employees_assigned INTEGER NOT NULL,
    defect_count INTEGER DEFAULT 0,
    scrap_count INTEGER DEFAULT 0,
    rework_count INTEGER DEFAULT 0,
    setup_time_hours DECIMAL(10, 2),
    downtime_hours DECIMAL(10, 2),
    maintenance_hours DECIMAL(10, 2),
    ideal_cycle_time DECIMAL(10, 4),
    actual_cycle_time DECIMAL(10, 4),
    efficiency_percentage DECIMAL(8, 4),
    performance_percentage DECIMAL(8, 4),
    quality_rate DECIMAL(8, 4),
    notes TEXT,
    entered_by INTEGER,
    confirmed_by INTEGER,
    confirmation_timestamp DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id),
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id),
    FOREIGN KEY (shift_id) REFERENCES SHIFT(shift_id),
    FOREIGN KEY (work_order_id) REFERENCES WORK_ORDER(work_order_id),
    FOREIGN KEY (entered_by) REFERENCES USER(user_id),
    FOREIGN KEY (confirmed_by) REFERENCES USER(user_id)
)
""")
print("   ✓ PRODUCTION_ENTRY")

# ============================================================================
# PHASE 2 - DOWNTIME & WIP
# ============================================================================

# DOWNTIME_ENTRY table
cursor.execute("""
CREATE TABLE DOWNTIME_ENTRY (
    downtime_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) NOT NULL,
    work_order_id VARCHAR(50) NOT NULL,
    shift_id INTEGER NOT NULL,
    downtime_date DATE NOT NULL,
    downtime_reason VARCHAR(255),
    downtime_category VARCHAR(100),
    downtime_duration_minutes INTEGER NOT NULL,
    entered_by VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id),
    FOREIGN KEY (work_order_id) REFERENCES WORK_ORDER(work_order_id)
)
""")
print("   ✓ DOWNTIME_ENTRY")

# HOLD_ENTRY table
cursor.execute("""
CREATE TABLE HOLD_ENTRY (
    hold_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) NOT NULL,
    work_order_id VARCHAR(50) NOT NULL,
    placed_on_hold_date DATE NOT NULL,
    released_date DATE,
    hold_reason VARCHAR(255),
    units_on_hold INTEGER,
    entered_by VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id),
    FOREIGN KEY (work_order_id) REFERENCES WORK_ORDER(work_order_id)
)
""")
print("   ✓ HOLD_ENTRY")

# ============================================================================
# PHASE 3 - ATTENDANCE & COVERAGE
# ============================================================================

# ATTENDANCE_ENTRY table
cursor.execute("""
CREATE TABLE ATTENDANCE_ENTRY (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) NOT NULL,
    employee_id VARCHAR(50) NOT NULL,
    shift_id INTEGER NOT NULL,
    attendance_date DATE NOT NULL,
    is_absent INTEGER DEFAULT 0,
    is_late INTEGER DEFAULT 0,
    scheduled_hours DECIMAL(5, 2),
    actual_hours DECIMAL(5, 2),
    entered_by VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id),
    FOREIGN KEY (employee_id) REFERENCES EMPLOYEE(employee_id)
)
""")
print("   ✓ ATTENDANCE_ENTRY")

# SHIFT_COVERAGE table
cursor.execute("""
CREATE TABLE SHIFT_COVERAGE (
    coverage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) NOT NULL,
    shift_id INTEGER NOT NULL,
    coverage_date DATE NOT NULL,
    employees_scheduled INTEGER,
    employees_present INTEGER,
    coverage_percentage DECIMAL(5, 2),
    entered_by VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id)
)
""")
print("   ✓ SHIFT_COVERAGE")

# ============================================================================
# PHASE 4 - QUALITY INSPECTION
# ============================================================================

# QUALITY_ENTRY table
cursor.execute("""
CREATE TABLE QUALITY_ENTRY (
    quality_entry_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    work_order_id VARCHAR(50) NOT NULL,
    inspection_date DATE NOT NULL,
    units_inspected INTEGER NOT NULL,
    units_passed INTEGER NOT NULL,
    units_failed INTEGER NOT NULL,
    total_defects_count INTEGER DEFAULT 0,
    entered_by VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id),
    FOREIGN KEY (work_order_id) REFERENCES WORK_ORDER(work_order_id)
)
""")
print("   ✓ QUALITY_ENTRY")

# DEFECT_DETAIL table (SECURITY FIX - client_id added)
cursor.execute("""
CREATE TABLE DEFECT_DETAIL (
    defect_detail_id VARCHAR(50) PRIMARY KEY,
    quality_entry_id VARCHAR(50) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    defect_type VARCHAR(50) NOT NULL,
    defect_category VARCHAR(100),
    defect_count INTEGER NOT NULL,
    severity VARCHAR(20),
    location VARCHAR(255),
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quality_entry_id) REFERENCES QUALITY_ENTRY(quality_entry_id),
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id)
)
""")
print("   ✓ DEFECT_DETAIL (with client_id - HIGH SECURITY FIX)")

# PART_OPPORTUNITIES table (SECURITY FIX - client_id added)
cursor.execute("""
CREATE TABLE PART_OPPORTUNITIES (
    part_number VARCHAR(100) PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    opportunities_per_unit INTEGER NOT NULL,
    part_description VARCHAR(255),
    part_category VARCHAR(100),
    notes TEXT,
    FOREIGN KEY (client_id) REFERENCES CLIENT(client_id)
)
""")
print("   ✓ PART_OPPORTUNITIES (with client_id - MEDIUM SECURITY FIX)")

conn.commit()
conn.close()

print()
print("=" * 70)
print("✅ Schema initialization completed successfully!")
print()
print("🔒 Security Features Applied:")
print("   ✓ JOB table: client_id added (CRITICAL - prevents WO line item leakage)")
print("   ✓ DEFECT_DETAIL table: client_id added (HIGH - prevents quality data leakage)")
print("   ✓ PART_OPPORTUNITIES table: client_id added (MEDIUM - prevents DPMO data leakage)")
print("   ✓ PRODUCTION_ENTRY: Uses production_entry_id (STRING) matching SQLAlchemy schema")
print("   ✓ Foreign key constraints enabled")
print("   ✓ Multi-tenant isolation enforced on all transactional tables")
print()
print("=" * 70)
print("✅ Ready for sample data generation!")
print(f"   Run: python3 database/generators/generate_complete_sample_data.py")
