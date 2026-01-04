#!/usr/bin/env python3
"""
Migration Runner for Phase 2-4 Schema Fixes
Executes SQL migrations in correct order with validation
"""
import sys
import os
import sqlite3
from datetime import datetime
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '../kpi_platform.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '../backups')

# Migration files
MIGRATIONS = [
    '002_phase2_schema_fix.sql',
    '003_phase3_schema_fix.sql',
    '004_phase4_schema_fix.sql'
]

def create_backup():
    """Create database backup before migration"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)

    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'kpi_platform_pre_migration_{timestamp}.db')

    print(f"📦 Creating backup: {backup_path}")
    shutil.copy2(DB_PATH, backup_path)
    print(f"   ✓ Backup created successfully")

    return backup_path

def run_migration(conn, migration_file):
    """Execute a single migration file"""
    migration_path = os.path.join(os.path.dirname(__file__), migration_file)

    if not os.path.exists(migration_path):
        print(f"   ❌ Migration file not found: {migration_file}")
        return False

    print(f"\n🔧 Running migration: {migration_file}")

    try:
        with open(migration_path, 'r') as f:
            sql = f.read()

        # Execute migration
        cursor = conn.cursor()
        cursor.executescript(sql)
        conn.commit()

        print(f"   ✓ Migration completed successfully")
        return True

    except sqlite3.Error as e:
        print(f"   ❌ Migration failed: {e}")
        conn.rollback()
        return False

def validate_schema(conn, expected_tables):
    """Validate that expected tables and columns exist"""
    cursor = conn.cursor()

    print("\n🔍 Validating schema changes...")

    for table, columns in expected_tables.items():
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name=?
        """, (table,))

        if not cursor.fetchone():
            print(f"   ❌ Table {table} not found")
            return False

        # Check columns
        cursor.execute(f"PRAGMA table_info({table})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        for column in columns:
            if column not in existing_columns:
                print(f"   ❌ Column {table}.{column} not found")
                return False
            else:
                print(f"   ✓ {table}.{column}")

    print("   ✓ All expected schema changes verified")
    return True

def main():
    print("=" * 80)
    print("🚀 KPI Operations Platform - Database Migration Runner")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print(f"Migrations: {len(MIGRATIONS)} files")
    print()

    # Create backup
    backup_path = create_backup()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # Run migrations
    success = True
    for migration in MIGRATIONS:
        if not run_migration(conn, migration):
            success = False
            break

    if not success:
        print("\n❌ Migration failed! Rolling back...")
        conn.close()

        # Restore from backup
        print(f"📦 Restoring from backup: {backup_path}")
        shutil.copy2(backup_path, DB_PATH)
        print("   ✓ Database restored")

        sys.exit(1)

    # Validate schema changes
    expected_schema = {
        'DOWNTIME_ENTRY': [
            'downtime_start_time', 'is_resolved', 'resolution_notes',
            'impact_on_wip_hours', 'created_by'
        ],
        'HOLD_ENTRY': [
            'hold_approved_at', 'resume_approved_at', 'created_by'
        ],
        'ATTENDANCE_ENTRY': [
            'shift_type', 'covered_by_floating_employee_id', 'coverage_confirmed',
            'verified_by_user_id', 'verified_at', 'is_excused_absence',
            'created_by', 'updated_by'
        ],
        'SHIFT_COVERAGE': [
            'shift_type', 'coverage_duration_hours', 'recorded_by_user_id',
            'verified', 'created_by', 'updated_by'
        ],
        'QUALITY_ENTRY': [
            'shift_type', 'operation_checked', 'units_requiring_repair',
            'units_requiring_rework', 'recorded_by_user_id', 'recorded_at',
            'sample_size_percent', 'inspection_level', 'approved_by',
            'approved_at', 'created_by', 'updated_by'
        ],
        'DEFECT_DETAIL': [
            'is_rework_required', 'is_repair_in_current_op', 'is_scrapped',
            'root_cause', 'unit_serial_or_id'
        ]
    }

    if not validate_schema(conn, expected_schema):
        print("\n❌ Schema validation failed!")
        conn.close()
        sys.exit(1)

    # Print statistics
    print("\n📊 Migration Statistics:")
    cursor = conn.cursor()

    tables = ['DOWNTIME_ENTRY', 'HOLD_ENTRY', 'ATTENDANCE_ENTRY',
              'SHIFT_COVERAGE', 'QUALITY_ENTRY', 'DEFECT_DETAIL']

    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {table}: {count} records")

    conn.close()

    print("\n" + "=" * 80)
    print("✅ All migrations completed successfully!")
    print("=" * 80)
    print(f"Backup saved: {backup_path}")
    print()
    print("🎯 Next Steps:")
    print("   1. Update Pydantic models in /backend/models/")
    print("   2. Update API routes to handle new fields")
    print("   3. Update frontend AG Grids with new columns")
    print("   4. Test KPI calculations with new schema")
    print("   5. Run integration tests")
    print()

if __name__ == '__main__':
    main()
