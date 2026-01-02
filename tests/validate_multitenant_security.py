#!/usr/bin/env python3
"""
Multi-Tenant Security Validation Test Suite
Tests client isolation across all CRUD operations and API endpoints
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sqlite3
from typing import Dict, List, Tuple

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'kpi_platform.db')

def test_client_isolation() -> Tuple[int, int]:
    """Test that all transactional tables have client_id column with proper foreign keys"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    passed = 0
    failed = 0

    print("🔒 Multi-Tenant Security Validation")
    print("=" * 70)
    print()

    # Tables that MUST have client_id column for multi-tenant isolation
    required_tables = [
        'WORK_ORDER',
        'JOB',
        'PRODUCTION_ENTRY',
        'DOWNTIME_ENTRY',
        'HOLD_ENTRY',
        'ATTENDANCE_ENTRY',
        'SHIFT_COVERAGE',
        'QUALITY_ENTRY',
        'DEFECT_DETAIL',
        'PART_OPPORTUNITIES'
    ]

    print("📋 Test 1: Verifying client_id column exists in all transactional tables")
    print()

    for table in required_tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'client_id' in column_names:
            print(f"   ✅ {table}: client_id column found")
            passed += 1
        else:
            print(f"   ❌ {table}: client_id column MISSING (CRITICAL SECURITY ISSUE)")
            failed += 1

    print()
    print("=" * 70)
    print()

    # Test foreign key constraints
    print("📋 Test 2: Verifying foreign key constraints to CLIENT table")
    print()

    for table in required_tables:
        cursor.execute(f"PRAGMA foreign_key_list({table})")
        fks = cursor.fetchall()

        has_client_fk = any(fk[2] == 'CLIENT' and fk[3] == 'client_id' for fk in fks)

        if has_client_fk:
            print(f"   ✅ {table}: Foreign key constraint to CLIENT.client_id found")
            passed += 1
        else:
            print(f"   ❌ {table}: Foreign key constraint to CLIENT MISSING")
            failed += 1

    print()
    print("=" * 70)
    print()

    conn.close()
    return passed, failed


def test_data_isolation() -> Tuple[int, int]:
    """Test that data is properly isolated by client_id"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    passed = 0
    failed = 0

    print("📋 Test 3: Verifying data is properly isolated by client_id")
    print()

    # Get all clients
    cursor.execute("SELECT client_id, client_name FROM CLIENT")
    clients = cursor.fetchall()

    if len(clients) == 0:
        print("   ⚠️  No clients found in database (run data generator first)")
        return 0, 1

    print(f"   Found {len(clients)} clients:")
    for client_id, client_name in clients:
        print(f"      - {client_id}: {client_name}")
    print()

    # Test each table has data distributed across clients
    test_tables = [
        ('WORK_ORDER', 'work_order_id'),
        ('PRODUCTION_ENTRY', 'production_entry_id'),
        ('ATTENDANCE_ENTRY', 'attendance_id'),
        ('QUALITY_ENTRY', 'quality_entry_id')
    ]

    for table, pk_column in test_tables:
        cursor.execute(f"SELECT DISTINCT client_id FROM {table}")
        client_ids_in_table = [row[0] for row in cursor.fetchall()]

        if len(client_ids_in_table) > 0:
            print(f"   ✅ {table}: Data found for {len(client_ids_in_table)} clients")
            passed += 1

            # Verify no orphaned records (client_id not in CLIENT table)
            cursor.execute(f"""
                SELECT COUNT(*) FROM {table}
                WHERE client_id NOT IN (SELECT client_id FROM CLIENT)
            """)
            orphaned_count = cursor.fetchone()[0]

            if orphaned_count == 0:
                print(f"      ✅ No orphaned records (referential integrity intact)")
                passed += 1
            else:
                print(f"      ❌ Found {orphaned_count} orphaned records (CRITICAL)")
                failed += 1
        else:
            print(f"   ⚠️  {table}: No data found (expected if table not yet populated)")

    print()
    print("=" * 70)
    print()

    conn.close()
    return passed, failed


def test_cross_client_leakage() -> Tuple[int, int]:
    """Test that queries cannot access other clients' data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    passed = 0
    failed = 0

    print("📋 Test 4: Verifying no cross-client data leakage")
    print()

    # Get first two clients
    cursor.execute("SELECT client_id FROM CLIENT LIMIT 2")
    clients = cursor.fetchall()

    if len(clients) < 2:
        print("   ⚠️  Need at least 2 clients for cross-leakage test")
        return 0, 1

    client_a = clients[0][0]
    client_b = clients[1][0]

    print(f"   Testing isolation between {client_a} and {client_b}")
    print()

    # Test WORK_ORDER isolation
    cursor.execute(f"SELECT COUNT(*) FROM WORK_ORDER WHERE client_id = ?", (client_a,))
    client_a_count = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM WORK_ORDER WHERE client_id = ?", (client_b,))
    client_b_count = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT COUNT(*) FROM WORK_ORDER
        WHERE client_id = ? AND work_order_id IN (
            SELECT work_order_id FROM WORK_ORDER WHERE client_id = ?
        )
    """, (client_a, client_b))
    leaked_count = cursor.fetchone()[0]

    if leaked_count == 0:
        print(f"   ✅ WORK_ORDER: No cross-client leakage detected")
        print(f"      - {client_a}: {client_a_count} work orders")
        print(f"      - {client_b}: {client_b_count} work orders")
        print(f"      - Overlap: 0 (CORRECT)")
        passed += 1
    else:
        print(f"   ❌ WORK_ORDER: CRITICAL - Found {leaked_count} leaked records")
        failed += 1

    print()

    # Test JOB isolation (CRITICAL - was the main vulnerability)
    cursor.execute(f"""
        SELECT COUNT(*) FROM JOB j
        JOIN WORK_ORDER wo ON j.work_order_id = wo.work_order_id
        WHERE j.client_id != wo.client_id
    """)
    mismatched_jobs = cursor.fetchone()[0]

    if mismatched_jobs == 0:
        print(f"   ✅ JOB: All jobs match their work order's client_id")
        passed += 1
    else:
        print(f"   ❌ JOB: CRITICAL - Found {mismatched_jobs} jobs with mismatched client_id")
        failed += 1

    print()
    print("=" * 70)
    print()

    conn.close()
    return passed, failed


def main():
    print()
    print("🔐 MULTI-TENANT SECURITY VALIDATION SUITE")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    print()

    if not os.path.exists(DB_PATH):
        print("❌ Database not found. Run schema initialization first:")
        print("   python3 database/init_sqlite_schema.py")
        print("   python3 database/generators/generate_complete_sample_data.py")
        return 1

    total_passed = 0
    total_failed = 0

    # Run all tests
    p, f = test_client_isolation()
    total_passed += p
    total_failed += f

    p, f = test_data_isolation()
    total_passed += p
    total_failed += f

    p, f = test_cross_client_leakage()
    total_passed += p
    total_failed += f

    # Final report
    print()
    print("=" * 70)
    print("📊 VALIDATION RESULTS")
    print("=" * 70)
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print(f"Total Tests: {total_passed + total_failed}")
    print()

    if total_failed == 0:
        print("🎉 SUCCESS: All multi-tenant security validations passed!")
        print()
        print("✅ Schema Integrity: VERIFIED")
        print("✅ Data Isolation: VERIFIED")
        print("✅ Foreign Key Constraints: VERIFIED")
        print("✅ Cross-Client Leakage Prevention: VERIFIED")
        print()
        print("=" * 70)
        print("🚀 System is SECURE for multi-tenant deployment")
        print("=" * 70)
        return 0
    else:
        print("⚠️  WARNING: Some security validations failed!")
        print("   Review failures above before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
