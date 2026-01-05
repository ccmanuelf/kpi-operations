"""
Comprehensive Schema Validation Suite
Tests all 57+ fields across all database tables for production readiness
"""
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Expected schema based on gap analysis
EXPECTED_SCHEMA = {
    "CLIENT": {
        "fields": ["client_id", "client_name", "client_contact", "client_email",
                   "client_phone", "location", "supervisor_id", "planner_id",
                   "engineering_id", "client_type", "timezone", "is_active",
                   "created_at", "updated_at"],
        "count": 14
    },
    "EMPLOYEE": {
        "fields": ["employee_id", "client_id_fk", "first_name", "last_name",
                   "employee_type", "shift_type", "department", "is_active",
                   "is_support_billed", "is_support_included", "hourly_rate",
                   "hire_date", "created_at", "updated_at"],
        "count": 14,
        "missing_in_gap": ["department", "is_active", "is_support_billed",
                           "is_support_included", "hourly_rate", "updated_at"]
    },
    "USER": {
        "fields": ["user_id", "username", "password_hash", "email", "role",
                   "client_id_assigned", "is_active", "created_at", "updated_at"],
        "count": 9,
        "missing_in_gap": ["client_id_assigned"]
    },
    "WORK_ORDER": {
        "fields": ["work_order_id", "client_id_fk", "style_model", "planned_quantity",
                   "planned_start_date", "actual_start_date", "planned_ship_date",
                   "required_date", "ideal_cycle_time", "status", "receipt_date",
                   "acknowledged_date", "priority_level", "created_by", "created_at", "updated_at"],
        "count": 16,
        "missing_in_gap": ["receipt_date", "acknowledged_date", "created_by"]
    },
    "JOB": {
        "fields": ["job_id", "client_id_fk", "work_order_id_fk", "job_number",
                   "operation_sequence", "operation_description", "planned_run_quantity",
                   "quantity_completed", "quantity_scrapped", "status", "priority_level",
                   "created_at", "updated_at"],
        "count": 13,
        "missing_in_gap": ["job_number", "quantity_scrapped", "priority_level"]
    },
    "PART_OPPORTUNITIES": {
        "fields": ["part_id", "client_id_fk", "work_order_id_fk", "operation_id",
                   "total_opportunities", "updated_by_user_id", "notes", "created_at", "updated_at"],
        "count": 9,
        "missing_in_gap": ["updated_by_user_id", "notes"]
    },
    "FLOATING_POOL": {
        "fields": ["employee_id_fk", "base_client_id", "status", "assigned_client_id",
                   "assignment_date", "created_at", "updated_at"],
        "count": 7,
        "missing_in_gap": ["status"]
    },
    "PRODUCTION_ENTRY": {
        "fields": ["entry_id", "client_id_fk", "job_id_fk", "employee_id_fk",
                   "entry_date", "shift_type", "units_produced", "labor_hours_worked",
                   "calculated_efficiency", "calculated_performance", "notes",
                   "recorded_by_user_id", "recorded_at", "created_at", "updated_at"],
        "count": 15
    },
    "DOWNTIME_ENTRY": {
        "fields": ["downtime_id", "client_id_fk", "job_id_fk", "entry_date",
                   "shift_type", "downtime_category", "downtime_reason",
                   "downtime_duration_hours", "downtime_start_time", "is_resolved",
                   "resolution_notes", "impact_on_wip_hours", "recorded_by_user_id",
                   "created_by", "created_at", "updated_at"],
        "count": 16,
        "missing_in_gap": ["downtime_start_time", "is_resolved", "resolution_notes",
                           "impact_on_wip_hours", "created_by", "updated_at"]
    },
    "HOLD_ENTRY": {
        "fields": ["hold_id", "client_id_fk", "job_id_fk", "entry_date",
                   "hold_reason", "hold_initiated_at", "hold_approved_at",
                   "resume_at", "resume_approved_at", "is_currently_on_hold",
                   "recorded_by_user_id", "created_by", "created_at", "updated_at"],
        "count": 14,
        "missing_in_gap": ["hold_approved_at", "resume_approved_at", "created_by"]
    },
    "ATTENDANCE_ENTRY": {
        "fields": ["attendance_id", "client_id_fk", "employee_id_fk", "entry_date",
                   "shift_type", "is_present", "absence_type", "hours_worked",
                   "is_overtime", "covered_by_floating_employee_id", "coverage_confirmed",
                   "notes", "recorded_by_user_id", "verified_by_user_id", "verified_at",
                   "created_at", "updated_at"],
        "count": 17,
        "missing_in_gap": ["shift_type", "covered_by_floating_employee_id", "coverage_confirmed",
                           "notes", "verified_by_user_id", "verified_at", "created_at", "updated_at"]
    },
    "COVERAGE_ENTRY": {
        "fields": ["coverage_id", "client_id_fk", "entry_date", "shift_type",
                   "floating_employee_id_fk", "covered_employee_id", "coverage_duration_hours",
                   "notes", "verified", "recorded_by_user_id", "created_at", "updated_at"],
        "count": 12,
        "missing_in_gap": ["shift_type", "coverage_duration_hours", "notes",
                           "verified", "recorded_by_user_id", "created_at", "updated_at"]
    },
    "QUALITY_ENTRY": {
        "fields": ["quality_id", "client_id_fk", "job_id_fk", "entry_date",
                   "shift_type", "operation_checked", "units_inspected", "units_passed",
                   "units_failed", "units_requiring_repair", "sample_size_percent",
                   "calculated_fpy", "calculated_ppm", "notes", "recorded_by_user_id",
                   "recorded_at", "created_at", "updated_at"],
        "count": 18,
        "missing_in_gap": ["shift_type", "operation_checked", "units_requiring_repair",
                           "sample_size_percent", "notes", "recorded_by_user_id",
                           "recorded_at", "created_at", "updated_at"]
    },
    "DEFECT_DETAIL": {
        "fields": ["defect_id", "quality_id_fk", "defect_type", "defect_count",
                   "is_rework_required", "is_repair_in_current_op", "is_scrapped",
                   "root_cause", "unit_serial_or_id", "recorded_at", "created_at"],
        "count": 11,
        "missing_in_gap": ["is_rework_required", "is_repair_in_current_op",
                           "is_scrapped", "root_cause", "unit_serial_or_id"]
    }
}

class ValidationResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
        self.missing_tables = []
        self.missing_fields = []
        self.extra_fields = []

    def add_pass(self, message: str):
        self.passed.append(f"✅ {message}")

    def add_fail(self, message: str):
        self.failed.append(f"❌ {message}")

    def add_warning(self, message: str):
        self.warnings.append(f"⚠️  {message}")

    def is_production_ready(self) -> bool:
        return len(self.failed) == 0 and len(self.missing_tables) == 0

    def print_report(self):
        print("\n" + "="*80)
        print("DATABASE SCHEMA VALIDATION REPORT")
        print("="*80)

        if self.passed:
            print(f"\n✅ PASSED CHECKS ({len(self.passed)}):")
            for msg in self.passed:
                print(f"   {msg}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for msg in self.warnings:
                print(f"   {msg}")

        if self.failed:
            print(f"\n❌ FAILED CHECKS ({len(self.failed)}):")
            for msg in self.failed:
                print(f"   {msg}")

        if self.missing_tables:
            print(f"\n🚨 MISSING TABLES ({len(self.missing_tables)}):")
            for table in self.missing_tables:
                print(f"   ❌ {table}")

        if self.missing_fields:
            print(f"\n📋 MISSING FIELDS ({len(self.missing_fields)}):")
            for table, fields in self.missing_fields:
                print(f"   ❌ {table}: {', '.join(fields)}")

        if self.extra_fields:
            print(f"\n➕ EXTRA FIELDS ({len(self.extra_fields)}):")
            for table, fields in self.extra_fields:
                print(f"   ℹ️  {table}: {', '.join(fields)}")

        print("\n" + "="*80)
        print(f"PRODUCTION READY: {'✅ YES' if self.is_production_ready() else '❌ NO'}")
        print("="*80 + "\n")

def get_table_info(conn: sqlite3.Connection, table_name: str) -> List[str]:
    """Get column names for a table"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

def validate_database_schema(db_path: str) -> ValidationResult:
    """Validate database schema against expected schema"""
    result = ValidationResult()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        actual_tables = {row[0] for row in cursor.fetchall()}

        # Check each expected table
        for table_name, expected in EXPECTED_SCHEMA.items():
            if table_name not in actual_tables:
                result.missing_tables.append(table_name)
                result.add_fail(f"Table {table_name} does not exist")
                continue

            # Get actual fields
            actual_fields = set(get_table_info(conn, table_name))
            expected_fields = set(expected["fields"])

            # Check for missing fields
            missing = expected_fields - actual_fields
            if missing:
                result.missing_fields.append((table_name, list(missing)))
                result.add_fail(f"{table_name}: Missing {len(missing)} fields - {', '.join(missing)}")
            else:
                result.add_pass(f"{table_name}: All {len(expected_fields)} expected fields present")

            # Check for extra fields (informational)
            extra = actual_fields - expected_fields
            if extra:
                result.extra_fields.append((table_name, list(extra)))

            # Validate field count
            if len(actual_fields) != expected["count"]:
                result.add_warning(f"{table_name}: Field count mismatch (expected {expected['count']}, got {len(actual_fields)})")

        # Check for extra tables
        extra_tables = actual_tables - set(EXPECTED_SCHEMA.keys())
        if extra_tables:
            result.add_warning(f"Extra tables found: {', '.join(extra_tables)}")

        conn.close()

    except sqlite3.Error as e:
        result.add_fail(f"Database error: {str(e)}")
    except Exception as e:
        result.add_fail(f"Validation error: {str(e)}")

    return result

def validate_foreign_keys(db_path: str) -> ValidationResult:
    """Validate foreign key relationships"""
    result = ValidationResult()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check foreign key enforcement
        cursor.execute("PRAGMA foreign_keys")
        fk_enabled = cursor.fetchone()[0]

        if fk_enabled:
            result.add_pass("Foreign keys are enabled")
        else:
            result.add_fail("Foreign keys are NOT enabled (critical for multi-tenant isolation)")

        # Test multi-tenant isolation
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        tenant_tables = [t for t in tables if t not in ['CLIENT', 'USER', 'sqlite_sequence']]

        for table in tenant_tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]

            if 'client_id_fk' in columns:
                result.add_pass(f"{table}: Has client_id_fk for multi-tenant isolation")
            else:
                result.add_fail(f"{table}: Missing client_id_fk for multi-tenant isolation")

        conn.close()

    except Exception as e:
        result.add_fail(f"Foreign key validation error: {str(e)}")

    return result

def validate_indexes(db_path: str) -> ValidationResult:
    """Validate database indexes for performance"""
    result = ValidationResult()

    required_indexes = {
        "idx_client_active",
        "idx_production_client_date",
        "idx_attendance_client_date",
        "idx_quality_client_date",
        "idx_downtime_client_date"
    }

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
        actual_indexes = {row[0] for row in cursor.fetchall()}

        missing_indexes = required_indexes - actual_indexes
        if missing_indexes:
            for idx in missing_indexes:
                result.add_warning(f"Missing recommended index: {idx}")
        else:
            result.add_pass(f"All {len(required_indexes)} recommended indexes present")

        conn.close()

    except Exception as e:
        result.add_fail(f"Index validation error: {str(e)}")

    return result

def main():
    db_path = Path(__file__).parent.parent.parent / "kpi_platform.db"

    if not db_path.exists():
        print(f"\n❌ ERROR: Database not found at {db_path}")
        print("Run database initialization first!")
        sys.exit(1)

    print("\nStarting comprehensive schema validation...")
    print(f"Database: {db_path}")

    # Run all validations
    schema_result = validate_database_schema(str(db_path))
    fk_result = validate_foreign_keys(str(db_path))
    index_result = validate_indexes(str(db_path))

    # Combine results
    final_result = ValidationResult()
    final_result.passed = schema_result.passed + fk_result.passed + index_result.passed
    final_result.failed = schema_result.failed + fk_result.failed + index_result.failed
    final_result.warnings = schema_result.warnings + fk_result.warnings + index_result.warnings
    final_result.missing_tables = schema_result.missing_tables
    final_result.missing_fields = schema_result.missing_fields
    final_result.extra_fields = schema_result.extra_fields

    # Print report
    final_result.print_report()

    # Calculate completeness percentage
    total_expected_fields = sum(schema["count"] for schema in EXPECTED_SCHEMA.values())
    missing_count = sum(len(fields) for _, fields in final_result.missing_fields)
    completeness = ((total_expected_fields - missing_count) / total_expected_fields) * 100

    print(f"Schema Completeness: {completeness:.1f}%")
    print(f"Expected Fields: {total_expected_fields}")
    print(f"Missing Fields: {missing_count}")

    # Exit with appropriate code
    sys.exit(0 if final_result.is_production_ready() else 1)

if __name__ == "__main__":
    main()
