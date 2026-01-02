#!/usr/bin/env python3
"""
Multi-Tenant Isolation Validation for SQLite Database
Tests client data isolation across all phases
"""

import sqlite3
import sys
from collections import defaultdict

# Configuration
DB_PATH = '../kpi_platform.db'

print("🔒 MULTI-TENANT ISOLATION VALIDATION")
print("=" * 70)

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Track test results
tests_passed = 0
tests_failed = 0
test_details = []

def test_result(test_name, passed, details=""):
    """Record test result"""
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        status = "✅ PASS"
    else:
        tests_failed += 1
        status = "❌ FAIL"
    test_details.append((test_name, status, details))
    print(f"{status}: {test_name}")
    if details and not passed:
        print(f"        {details}")

# TEST 1: Verify 5 Clients Exist
print("\n📋 TEST 1: Client Foundation")
cursor.execute("SELECT COUNT(*) FROM CLIENT")
client_count = cursor.fetchone()[0]
test_result(
    "5 Clients Created",
    client_count == 5,
    f"Expected 5 clients, found {client_count}"
)

# Get client list
cursor.execute("SELECT client_id FROM CLIENT ORDER BY client_id")
clients = [row[0] for row in cursor.fetchall()]
print(f"        Clients: {', '.join(clients)}")

# TEST 2: Verify Work Orders Distribution
print("\n📦 TEST 2: Work Order Distribution")
cursor.execute("""
    SELECT client_id_fk, COUNT(*) as count
    FROM WORK_ORDER
    GROUP BY client_id_fk
    ORDER BY client_id_fk
""")
wo_distribution = cursor.fetchall()

all_have_5 = all(count == 5 for _, count in wo_distribution)
test_result(
    "Each Client Has Exactly 5 Work Orders",
    all_have_5 and len(wo_distribution) == 5,
    f"Distribution: {dict(wo_distribution)}"
)

# TEST 3: Verify NO Cross-Client Work Order Leakage
print("\n🔐 TEST 3: Work Order Isolation")
cursor.execute("""
    SELECT COUNT(*) FROM WORK_ORDER
    WHERE client_id_fk NOT IN (SELECT client_id FROM CLIENT)
""")
orphaned_wo = cursor.fetchone()[0]
test_result(
    "No Orphaned Work Orders",
    orphaned_wo == 0,
    f"Found {orphaned_wo} work orders with invalid client_id"
)

# TEST 4: Verify Production Entry Isolation
print("\n🏭 TEST 4: Production Entry Isolation")
cursor.execute("""
    SELECT client_id_fk, COUNT(*) as count
    FROM PRODUCTION_ENTRY
    GROUP BY client_id_fk
    ORDER BY client_id_fk
""")
prod_distribution = cursor.fetchall()

cursor.execute("""
    SELECT COUNT(*) FROM PRODUCTION_ENTRY pe
    LEFT JOIN WORK_ORDER wo ON pe.work_order_id_fk = wo.work_order_id
    WHERE pe.client_id_fk != wo.client_id_fk
""")
mismatched_prod = cursor.fetchone()[0]

test_result(
    "Production Entries Match Work Order Clients",
    mismatched_prod == 0,
    f"Found {mismatched_prod} production entries with mismatched client_id"
)

# TEST 5: Verify Quality Entry Isolation
print("\n✅ TEST 5: Quality Entry Isolation")
cursor.execute("""
    SELECT COUNT(*) FROM QUALITY_ENTRY qe
    LEFT JOIN WORK_ORDER wo ON qe.work_order_id_fk = wo.work_order_id
    WHERE qe.client_id_fk != wo.client_id_fk
""")
mismatched_quality = cursor.fetchone()[0]

test_result(
    "Quality Entries Match Work Order Clients",
    mismatched_quality == 0,
    f"Found {mismatched_quality} quality entries with mismatched client_id"
)

# TEST 6: Verify Employee Assignment
print("\n👥 TEST 6: Employee Assignment")
cursor.execute("""
    SELECT client_id_assigned, COUNT(*) as count
    FROM EMPLOYEE
    WHERE is_floating_pool = 0
    GROUP BY client_id_assigned
    ORDER BY client_id_assigned
""")
emp_distribution = cursor.fetchall()

cursor.execute("SELECT COUNT(*) FROM EMPLOYEE WHERE is_floating_pool = 1")
floating_count = cursor.fetchone()[0]

all_have_employees = all(count == 16 for _, count in emp_distribution)
test_result(
    "Each Client Has 16 Assigned Employees",
    all_have_employees and len(emp_distribution) == 5,
    f"Distribution: {dict(emp_distribution)}"
)

test_result(
    "20 Floating Pool Employees Created",
    floating_count == 20,
    f"Found {floating_count} floating employees"
)

# TEST 7: Verify Attendance Isolation
print("\n📅 TEST 7: Attendance Entry Isolation")
cursor.execute("""
    SELECT COUNT(*) FROM ATTENDANCE_ENTRY ae
    LEFT JOIN EMPLOYEE e ON ae.employee_id_fk = e.employee_id
    WHERE ae.client_id_fk != e.client_id_assigned
    AND e.is_floating_pool = 0
""")
mismatched_attendance = cursor.fetchone()[0]

test_result(
    "Attendance Entries Match Employee Clients",
    mismatched_attendance == 0,
    f"Found {mismatched_attendance} attendance entries with mismatched client_id"
)

# TEST 8: Verify Downtime Isolation
print("\n⏸️  TEST 8: Downtime Entry Isolation")
cursor.execute("""
    SELECT COUNT(*) FROM DOWNTIME_ENTRY de
    LEFT JOIN WORK_ORDER wo ON de.work_order_id_fk = wo.work_order_id
    WHERE de.client_id_fk != wo.client_id_fk
""")
mismatched_downtime = cursor.fetchone()[0]

test_result(
    "Downtime Entries Match Work Order Clients",
    mismatched_downtime == 0,
    f"Found {mismatched_downtime} downtime entries with mismatched client_id"
)

# TEST 9: Cross-Client Data Leakage Check
print("\n🚨 TEST 9: Cross-Client Data Leakage")

leakage_found = False
for client_a in clients:
    for client_b in clients:
        if client_a >= client_b:
            continue

        # Check if any work order from client_a references data from client_b
        cursor.execute("""
            SELECT COUNT(*) FROM WORK_ORDER wo_a
            JOIN PRODUCTION_ENTRY pe ON wo_a.work_order_id = pe.work_order_id_fk
            WHERE wo_a.client_id_fk = ? AND pe.client_id_fk = ?
        """, (client_a, client_b))

        cross_client_refs = cursor.fetchone()[0]
        if cross_client_refs > 0:
            leakage_found = True
            print(f"        ⚠️  WARNING: {client_a} work orders reference {client_b} production data")

test_result(
    "No Cross-Client Data References",
    not leakage_found,
    "Data leakage detected between clients"
)

# TEST 10: Data Completeness
print("\n📊 TEST 10: Data Completeness")
cursor.execute("SELECT COUNT(*) FROM WORK_ORDER")
total_wo = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM PRODUCTION_ENTRY")
total_prod = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM QUALITY_ENTRY")
total_quality = cursor.fetchone()[0]

test_result(
    "25 Work Orders Created (5 per client)",
    total_wo == 25,
    f"Expected 25, found {total_wo}"
)

test_result(
    "75 Production Entries Created (3 per WO)",
    total_prod == 75,
    f"Expected 75, found {total_prod}"
)

test_result(
    "25 Quality Entries Created (1 per WO)",
    total_quality == 25,
    f"Expected 25, found {total_quality}"
)

# Close database
conn.close()

# FINAL SUMMARY
print("\n" + "=" * 70)
print("📈 VALIDATION SUMMARY")
print("=" * 70)
print(f"Total Tests: {tests_passed + tests_failed}")
print(f"✅ Passed: {tests_passed}")
print(f"❌ Failed: {tests_failed}")

if tests_failed == 0:
    print("\n🎉 ALL TESTS PASSED - Multi-tenant isolation is SECURE!")
    sys.exit(0)
else:
    print(f"\n⚠️  {tests_failed} TESTS FAILED - Review security issues above")
    sys.exit(1)
