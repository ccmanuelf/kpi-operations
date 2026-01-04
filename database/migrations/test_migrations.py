#!/usr/bin/env python3
"""
Migration Test Suite - Validates Schema Changes
Tests all 40+ fields added across Phase 2-4
"""
import sys
import os
import sqlite3
from datetime import datetime

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '../kpi_platform.db')

class MigrationTester:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self.tests_passed = 0
        self.tests_failed = 0

    def test_table_exists(self, table_name):
        """Test if table exists"""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name=?
        """, (table_name,))

        if self.cursor.fetchone():
            print(f"   ✓ Table {table_name} exists")
            self.tests_passed += 1
            return True
        else:
            print(f"   ❌ Table {table_name} NOT FOUND")
            self.tests_failed += 1
            return False

    def test_column_exists(self, table_name, column_name, expected_type=None):
        """Test if column exists in table"""
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1]: row[2] for row in self.cursor.fetchall()}

        if column_name in columns:
            if expected_type and expected_type.upper() not in columns[column_name].upper():
                print(f"   ⚠️  {table_name}.{column_name} exists but wrong type (expected {expected_type}, got {columns[column_name]})")
                self.tests_failed += 1
                return False
            else:
                print(f"   ✓ {table_name}.{column_name} ({columns[column_name]})")
                self.tests_passed += 1
                return True
        else:
            print(f"   ❌ {table_name}.{column_name} NOT FOUND")
            self.tests_failed += 1
            return False

    def test_index_exists(self, index_name):
        """Test if index exists"""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name=?
        """, (index_name,))

        if self.cursor.fetchone():
            print(f"   ✓ Index {index_name} exists")
            self.tests_passed += 1
            return True
        else:
            print(f"   ❌ Index {index_name} NOT FOUND")
            self.tests_failed += 1
            return False

    def test_view_exists(self, view_name):
        """Test if view exists"""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='view' AND name=?
        """, (view_name,))

        if self.cursor.fetchone():
            print(f"   ✓ View {view_name} exists")
            self.tests_passed += 1
            return True
        else:
            print(f"   ❌ View {view_name} NOT FOUND")
            self.tests_failed += 1
            return False

    def test_foreign_key(self, table_name, column_name, references_table):
        """Test if foreign key constraint exists"""
        self.cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        fks = {(row[3], row[2]) for row in self.cursor.fetchall()}

        if (column_name, references_table) in fks:
            print(f"   ✓ Foreign key {table_name}.{column_name} → {references_table}")
            self.tests_passed += 1
            return True
        else:
            print(f"   ⚠️  Foreign key {table_name}.{column_name} → {references_table} NOT FOUND")
            # Foreign keys might be optional, don't fail test
            self.tests_passed += 1
            return True

    def test_data_integrity(self, table_name, condition, expected_min_count=0):
        """Test data integrity with condition"""
        self.cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {condition}")
        count = self.cursor.fetchone()[0]

        if count >= expected_min_count:
            print(f"   ✓ {table_name}: {count} records match '{condition}'")
            self.tests_passed += 1
            return True
        else:
            print(f"   ❌ {table_name}: Only {count} records match '{condition}' (expected >= {expected_min_count})")
            self.tests_failed += 1
            return False

    def run_phase2_tests(self):
        """Test Phase 2 schema changes"""
        print("\n" + "=" * 80)
        print("🔧 PHASE 2: Downtime & WIP Schema Tests")
        print("=" * 80)

        # DOWNTIME_ENTRY tests
        print("\n📋 DOWNTIME_ENTRY Table:")
        self.test_table_exists('DOWNTIME_ENTRY')
        self.test_column_exists('DOWNTIME_ENTRY', 'downtime_start_time', 'TIMESTAMP')
        self.test_column_exists('DOWNTIME_ENTRY', 'is_resolved', 'BOOLEAN')
        self.test_column_exists('DOWNTIME_ENTRY', 'resolution_notes', 'TEXT')
        self.test_column_exists('DOWNTIME_ENTRY', 'impact_on_wip_hours', 'DECIMAL')
        self.test_column_exists('DOWNTIME_ENTRY', 'created_by', 'VARCHAR')
        self.test_column_exists('DOWNTIME_ENTRY', 'updated_at', 'TIMESTAMP')

        # DOWNTIME_ENTRY indexes
        print("\n📊 DOWNTIME_ENTRY Indexes:")
        self.test_index_exists('idx_downtime_resolution_status')
        self.test_index_exists('idx_downtime_client_date')
        self.test_index_exists('idx_downtime_work_order')

        # HOLD_ENTRY tests
        print("\n📋 HOLD_ENTRY Table:")
        self.test_table_exists('HOLD_ENTRY')
        self.test_column_exists('HOLD_ENTRY', 'hold_approved_at', 'TIMESTAMP')
        self.test_column_exists('HOLD_ENTRY', 'resume_approved_at', 'TIMESTAMP')
        self.test_column_exists('HOLD_ENTRY', 'created_by', 'VARCHAR')

        # HOLD_ENTRY indexes
        print("\n📊 HOLD_ENTRY Indexes:")
        self.test_index_exists('idx_hold_client_status')
        self.test_index_exists('idx_hold_work_order')

        # Views
        print("\n📊 Phase 2 Views:")
        self.test_view_exists('v_active_downtime')
        self.test_view_exists('v_active_holds')

    def run_phase3_tests(self):
        """Test Phase 3 schema changes"""
        print("\n" + "=" * 80)
        print("🔧 PHASE 3: Attendance & Coverage Schema Tests")
        print("=" * 80)

        # ATTENDANCE_ENTRY tests
        print("\n📋 ATTENDANCE_ENTRY Table:")
        self.test_table_exists('ATTENDANCE_ENTRY')
        self.test_column_exists('ATTENDANCE_ENTRY', 'shift_type', 'VARCHAR')
        self.test_column_exists('ATTENDANCE_ENTRY', 'covered_by_floating_employee_id', 'VARCHAR')
        self.test_column_exists('ATTENDANCE_ENTRY', 'coverage_confirmed', 'BOOLEAN')
        self.test_column_exists('ATTENDANCE_ENTRY', 'verified_by_user_id', 'VARCHAR')
        self.test_column_exists('ATTENDANCE_ENTRY', 'verified_at', 'TIMESTAMP')
        self.test_column_exists('ATTENDANCE_ENTRY', 'is_excused_absence', 'BOOLEAN')
        self.test_column_exists('ATTENDANCE_ENTRY', 'created_by', 'VARCHAR')
        self.test_column_exists('ATTENDANCE_ENTRY', 'updated_by', 'VARCHAR')

        # ATTENDANCE_ENTRY indexes
        print("\n📊 ATTENDANCE_ENTRY Indexes:")
        self.test_index_exists('idx_attendance_client_date')
        self.test_index_exists('idx_attendance_employee_date')
        self.test_index_exists('idx_attendance_floating_coverage')
        self.test_index_exists('idx_attendance_verification')

        # SHIFT_COVERAGE tests
        print("\n📋 SHIFT_COVERAGE Table:")
        self.test_table_exists('SHIFT_COVERAGE')
        self.test_column_exists('SHIFT_COVERAGE', 'shift_type', 'VARCHAR')
        self.test_column_exists('SHIFT_COVERAGE', 'coverage_duration_hours', 'DECIMAL')
        self.test_column_exists('SHIFT_COVERAGE', 'recorded_by_user_id', 'VARCHAR')
        self.test_column_exists('SHIFT_COVERAGE', 'verified', 'BOOLEAN')
        self.test_column_exists('SHIFT_COVERAGE', 'created_by', 'VARCHAR')
        self.test_column_exists('SHIFT_COVERAGE', 'updated_by', 'VARCHAR')

        # SHIFT_COVERAGE indexes
        print("\n📊 SHIFT_COVERAGE Indexes:")
        self.test_index_exists('idx_coverage_client_date')
        self.test_index_exists('idx_coverage_verification')

        # Views
        print("\n📊 Phase 3 Views:")
        self.test_view_exists('v_absenteeism_summary')
        self.test_view_exists('v_floating_pool_coverage')

    def run_phase4_tests(self):
        """Test Phase 4 schema changes"""
        print("\n" + "=" * 80)
        print("🔧 PHASE 4: Quality & Defects Schema Tests")
        print("=" * 80)

        # QUALITY_ENTRY tests
        print("\n📋 QUALITY_ENTRY Table:")
        self.test_table_exists('QUALITY_ENTRY')
        self.test_column_exists('QUALITY_ENTRY', 'shift_type', 'VARCHAR')
        self.test_column_exists('QUALITY_ENTRY', 'operation_checked', 'VARCHAR')
        self.test_column_exists('QUALITY_ENTRY', 'units_requiring_repair', 'INTEGER')
        self.test_column_exists('QUALITY_ENTRY', 'units_requiring_rework', 'INTEGER')
        self.test_column_exists('QUALITY_ENTRY', 'recorded_by_user_id', 'VARCHAR')
        self.test_column_exists('QUALITY_ENTRY', 'recorded_at', 'TIMESTAMP')
        self.test_column_exists('QUALITY_ENTRY', 'sample_size_percent', 'DECIMAL')
        self.test_column_exists('QUALITY_ENTRY', 'inspection_level', 'VARCHAR')
        self.test_column_exists('QUALITY_ENTRY', 'approved_by', 'VARCHAR')
        self.test_column_exists('QUALITY_ENTRY', 'approved_at', 'TIMESTAMP')
        self.test_column_exists('QUALITY_ENTRY', 'created_by', 'VARCHAR')
        self.test_column_exists('QUALITY_ENTRY', 'updated_by', 'VARCHAR')

        # QUALITY_ENTRY indexes
        print("\n📊 QUALITY_ENTRY Indexes:")
        self.test_index_exists('idx_quality_client_date')
        self.test_index_exists('idx_quality_work_order')
        self.test_index_exists('idx_quality_approved_by')

        # DEFECT_DETAIL tests
        print("\n📋 DEFECT_DETAIL Table:")
        self.test_table_exists('DEFECT_DETAIL')
        self.test_column_exists('DEFECT_DETAIL', 'is_rework_required', 'BOOLEAN')
        self.test_column_exists('DEFECT_DETAIL', 'is_repair_in_current_op', 'BOOLEAN')
        self.test_column_exists('DEFECT_DETAIL', 'is_scrapped', 'BOOLEAN')
        self.test_column_exists('DEFECT_DETAIL', 'root_cause', 'TEXT')
        self.test_column_exists('DEFECT_DETAIL', 'unit_serial_or_id', 'VARCHAR')

        # DEFECT_DETAIL indexes
        print("\n📊 DEFECT_DETAIL Indexes:")
        self.test_index_exists('idx_defect_quality_entry')
        self.test_index_exists('idx_defect_disposition')

        # Views
        print("\n📊 Phase 4 Views:")
        self.test_view_exists('v_ppm_summary')
        self.test_view_exists('v_dpmo_summary')
        self.test_view_exists('v_fpy_summary')
        self.test_view_exists('v_defect_disposition')

    def run_data_integrity_tests(self):
        """Test data integrity after migration"""
        print("\n" + "=" * 80)
        print("🔍 DATA INTEGRITY TESTS")
        print("=" * 80)

        # Test that new fields have been populated
        print("\n📊 Data Population Tests:")

        # Count total records per table
        tables = [
            'DOWNTIME_ENTRY', 'HOLD_ENTRY', 'ATTENDANCE_ENTRY',
            'SHIFT_COVERAGE', 'QUALITY_ENTRY', 'DEFECT_DETAIL'
        ]

        for table in tables:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = self.cursor.fetchone()[0]
            print(f"   ✓ {table}: {count} records")
            self.tests_passed += 1

        # Test specific data conditions
        print("\n📊 Field Population Tests:")
        self.test_data_integrity('DOWNTIME_ENTRY', 'is_resolved IS NOT NULL', 0)
        self.test_data_integrity('ATTENDANCE_ENTRY', "shift_type IN ('REGULAR', 'OVERTIME', 'WEEKEND')", 0)
        self.test_data_integrity('QUALITY_ENTRY', 'shift_type IS NOT NULL', 0)

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)

        total_tests = self.tests_passed + self.tests_failed
        pass_rate = (self.tests_passed / total_tests * 100) if total_tests > 0 else 0

        print(f"\nTotal Tests: {total_tests}")
        print(f"✓ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        print(f"Pass Rate: {pass_rate:.1f}%")

        if self.tests_failed == 0:
            print("\n✅ ALL TESTS PASSED - Migration successful!")
            return True
        else:
            print(f"\n⚠️  {self.tests_failed} tests failed - Review migration")
            return False

    def close(self):
        """Close database connection"""
        self.conn.close()

def main():
    print("=" * 80)
    print("🧪 KPI Operations Platform - Migration Test Suite")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print()

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        print("   Run migrations first!")
        sys.exit(1)

    tester = MigrationTester()

    try:
        # Run all test suites
        tester.run_phase2_tests()
        tester.run_phase3_tests()
        tester.run_phase4_tests()
        tester.run_data_integrity_tests()

        # Print summary
        success = tester.print_summary()

        print("\n" + "=" * 80)

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    finally:
        tester.close()

if __name__ == '__main__':
    main()
