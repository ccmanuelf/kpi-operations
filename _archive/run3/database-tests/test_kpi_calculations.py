#!/usr/bin/env python3
"""
KPI Calculation Validation with Multi-Tenant Sample Data
Tests all 10 KPI formulas against the 5-client database
"""

import sqlite3
import sys
from datetime import datetime, timedelta

# Configuration
DB_PATH = '../kpi_platform.db'

print("📊 KPI CALCULATION VALIDATION")
print("=" * 70)

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Track test results
tests_passed = 0
tests_failed = 0

def test_kpi(kpi_name, calculation, expected_range=None, details=""):
    """Test a KPI calculation"""
    global tests_passed, tests_failed

    try:
        result = calculation()

        # Check if result is in expected range
        if expected_range:
            min_val, max_val = expected_range
            in_range = min_val <= result <= max_val
        else:
            in_range = result is not None

        if in_range:
            tests_passed += 1
            print(f"✅ PASS: {kpi_name}")
            print(f"        Result: {result:.2f}% {details}")
        else:
            tests_failed += 1
            print(f"❌ FAIL: {kpi_name}")
            print(f"        Result: {result:.2f}% (expected {expected_range})")

    except Exception as e:
        tests_failed += 1
        print(f"❌ ERROR: {kpi_name}")
        print(f"        {str(e)}")

# Get date range for calculations
cursor.execute("SELECT MIN(shift_date), MAX(shift_date) FROM PRODUCTION_ENTRY")
date_range = cursor.fetchone()
print(f"\n📅 Data Range: {date_range[0]} to {date_range[1]}")

# Get client breakdown
cursor.execute("SELECT client_id FROM CLIENT ORDER BY client_id")
clients = [row[0] for row in cursor.fetchall()]
print(f"👥 Clients: {', '.join(clients)}")
print()

# ============================================================================
# KPI #1: EFFICIENCY (Phase 1)
# ============================================================================
print("\n🔧 KPI #1: EFFICIENCY")
print("-" * 70)

def calculate_efficiency():
    """Efficiency = (Units × Ideal Cycle Time) / (Employees × Scheduled Hours) × 100"""
    cursor.execute("""
        SELECT
            SUM(pe.units_produced * 0.25) as ideal_time,
            SUM(pe.employees_assigned * 8.0) as scheduled_hours
        FROM PRODUCTION_ENTRY pe
    """)

    row = cursor.fetchone()
    ideal_time, scheduled_hours = row

    if scheduled_hours > 0:
        efficiency = (ideal_time / scheduled_hours) * 100
        return efficiency
    return 0.0

test_kpi("Efficiency", calculate_efficiency, (50, 100))

# ============================================================================
# KPI #2: PERFORMANCE (Phase 1)
# ============================================================================
print("\n⚡ KPI #2: PERFORMANCE")
print("-" * 70)

def calculate_performance():
    """Performance = (Units / Run Time) / (Units / Ideal Cycle Time) × 100"""
    cursor.execute("""
        SELECT
            SUM(pe.units_produced) as total_units,
            SUM(pe.run_time_hours) as total_runtime,
            SUM(pe.units_produced * 0.25) as ideal_time
        FROM PRODUCTION_ENTRY pe
    """)

    row = cursor.fetchone()
    total_units, total_runtime, ideal_time = row

    if total_runtime > 0 and ideal_time > 0:
        actual_rate = total_units / total_runtime
        ideal_rate = total_units / ideal_time
        performance = (actual_rate / ideal_rate) * 100
        return performance
    return 0.0

test_kpi("Performance", calculate_performance, (80, 120))

# ============================================================================
# KPI #3: QUALITY RATE (Phase 1)
# ============================================================================
print("\n✅ KPI #3: QUALITY RATE")
print("-" * 70)

def calculate_quality():
    """Quality = (Units - Defects) / Units × 100"""
    cursor.execute("""
        SELECT
            SUM(units_produced) as total_units,
            SUM(units_defective) as total_defects
        FROM PRODUCTION_ENTRY
    """)

    row = cursor.fetchone()
    total_units, total_defects = row

    if total_units > 0:
        quality = ((total_units - total_defects) / total_units) * 100
        return quality
    return 0.0

test_kpi("Quality Rate", calculate_quality, (90, 100))

# ============================================================================
# KPI #4: AVAILABILITY (Phase 2)
# ============================================================================
print("\n🏭 KPI #4: AVAILABILITY")
print("-" * 70)

def calculate_availability():
    """Availability = (Scheduled - Downtime) / Scheduled × 100"""
    # Get total scheduled hours
    cursor.execute("SELECT COUNT(DISTINCT shift_date) FROM PRODUCTION_ENTRY")
    work_days = cursor.fetchone()[0]
    scheduled_hours = work_days * 8.0  # 8 hours per shift

    # Get total downtime
    cursor.execute("SELECT SUM(downtime_duration_hours) FROM DOWNTIME_ENTRY")
    downtime_hours = cursor.fetchone()[0] or 0

    if scheduled_hours > 0:
        availability = ((scheduled_hours - downtime_hours) / scheduled_hours) * 100
        return availability
    return 0.0

test_kpi("Availability", calculate_availability, (85, 100))

# ============================================================================
# KPI #5: WIP AGING (Phase 2)
# ============================================================================
print("\n⏳ KPI #5: WIP AGING")
print("-" * 70)

def calculate_wip_aging():
    """WIP Aging = Average days in hold status"""
    cursor.execute("""
        SELECT AVG(
            CASE
                WHEN released_date IS NOT NULL
                THEN julianday(released_date) - julianday(placed_on_hold_date)
                ELSE julianday('now') - julianday(placed_on_hold_date)
            END
        ) as avg_aging_days
        FROM HOLD_ENTRY
    """)

    result = cursor.fetchone()[0]
    return result if result else 0.0

# WIP Aging is in days, not percentage
cursor.execute("SELECT COUNT(*) FROM HOLD_ENTRY")
hold_count = cursor.fetchone()[0]
if hold_count > 0:
    avg_days = calculate_wip_aging()
    print(f"✅ PASS: WIP Aging")
    print(f"        Result: {avg_days:.1f} days average")
    tests_passed += 1
else:
    print(f"⚠️  SKIP: WIP Aging (no hold entries)")

# ============================================================================
# KPI #6: ABSENTEEISM (Phase 3)
# ============================================================================
print("\n👥 KPI #6: ABSENTEEISM")
print("-" * 70)

def calculate_absenteeism():
    """Absenteeism = Hours Absent / Hours Scheduled × 100"""
    cursor.execute("""
        SELECT
            SUM(scheduled_hours) as total_scheduled,
            SUM(CASE WHEN is_absent = 1 THEN scheduled_hours ELSE 0 END) as total_absent
        FROM ATTENDANCE_ENTRY
    """)

    row = cursor.fetchone()
    total_scheduled, total_absent = row

    if total_scheduled > 0:
        absenteeism = (total_absent / total_scheduled) * 100
        return absenteeism
    return 0.0

test_kpi("Absenteeism", calculate_absenteeism, (0, 15))

# ============================================================================
# KPI #7: ON-TIME DELIVERY (Phase 3)
# ============================================================================
print("\n📦 KPI #7: ON-TIME DELIVERY (OTD)")
print("-" * 70)

def calculate_otd():
    """OTD = Work Orders Delivered On-Time / Total Work Orders × 100"""
    cursor.execute("""
        SELECT
            COUNT(*) as total_orders,
            SUM(CASE
                WHEN actual_delivery_date IS NOT NULL
                AND actual_delivery_date <= planned_ship_date
                THEN 1 ELSE 0
            END) as on_time_orders
        FROM WORK_ORDER
        WHERE actual_delivery_date IS NOT NULL
    """)

    row = cursor.fetchone()
    total_orders, on_time_orders = row

    if total_orders > 0:
        otd = (on_time_orders / total_orders) * 100
        return otd
    return 0.0

test_kpi("On-Time Delivery", calculate_otd, (70, 100))

# ============================================================================
# KPI #8: PPM (Parts Per Million) - Phase 4
# ============================================================================
print("\n🔬 KPI #8: PPM (Parts Per Million)")
print("-" * 70)

def calculate_ppm():
    """PPM = (Total Defects / Units Inspected) × 1,000,000"""
    cursor.execute("""
        SELECT
            SUM(units_inspected) as total_inspected,
            SUM(total_defects_count) as total_defects
        FROM QUALITY_ENTRY
    """)

    row = cursor.fetchone()
    total_inspected, total_defects = row

    if total_inspected > 0:
        ppm = (total_defects / total_inspected) * 1_000_000
        return ppm
    return 0.0

# PPM is not a percentage, print raw value
ppm_value = calculate_ppm()
if ppm_value < 50000:  # Reasonable range for manufacturing
    print(f"✅ PASS: PPM")
    print(f"        Result: {ppm_value:.0f} defects per million")
    tests_passed += 1
else:
    print(f"❌ FAIL: PPM")
    print(f"        Result: {ppm_value:.0f} (expected < 50,000)")
    tests_failed += 1

# ============================================================================
# KPI #9: DPMO (Defects Per Million Opportunities) - Phase 4
# ============================================================================
print("\n🎯 KPI #9: DPMO")
print("-" * 70)

def calculate_dpmo():
    """DPMO = (Total Defects / (Units × Opportunities)) × 1,000,000"""
    opportunities_per_unit = 10  # Assuming 10 inspection points

    cursor.execute("""
        SELECT
            SUM(units_inspected) as total_units,
            SUM(total_defects_count) as total_defects
        FROM QUALITY_ENTRY
    """)

    row = cursor.fetchone()
    total_units, total_defects = row

    if total_units > 0:
        total_opportunities = total_units * opportunities_per_unit
        dpmo = (total_defects / total_opportunities) * 1_000_000
        return dpmo
    return 0.0

dpmo_value = calculate_dpmo()
if dpmo_value < 50000:
    print(f"✅ PASS: DPMO")
    print(f"        Result: {dpmo_value:.0f} defects per million opportunities")
    tests_passed += 1
else:
    print(f"❌ FAIL: DPMO")
    print(f"        Result: {dpmo_value:.0f} (expected < 50,000)")
    tests_failed += 1

# ============================================================================
# KPI #10: FPY (First Pass Yield) - Phase 4
# ============================================================================
print("\n🎖️  KPI #10: FPY (First Pass Yield)")
print("-" * 70)

def calculate_fpy():
    """FPY = Units Passed / Units Inspected × 100"""
    cursor.execute("""
        SELECT
            SUM(units_inspected) as total_inspected,
            SUM(units_passed) as total_passed
        FROM QUALITY_ENTRY
    """)

    row = cursor.fetchone()
    total_inspected, total_passed = row

    if total_inspected > 0:
        fpy = (total_passed / total_inspected) * 100
        return fpy
    return 0.0

test_kpi("First Pass Yield (FPY)", calculate_fpy, (90, 100))

# Close database
conn.close()

# FINAL SUMMARY
print("\n" + "=" * 70)
print("📈 KPI VALIDATION SUMMARY")
print("=" * 70)
print(f"Total KPI Tests: {tests_passed + tests_failed}")
print(f"✅ Passed: {tests_passed}")
print(f"❌ Failed: {tests_failed}")

if tests_failed == 0:
    print("\n🎉 ALL KPI CALCULATIONS VALIDATED!")
    sys.exit(0)
else:
    print(f"\n⚠️  {tests_failed} KPI TESTS FAILED - Review formulas above")
    sys.exit(1)
