#!/usr/bin/env python3
"""
Sample Data Generator for KPI Platform - Phases 2-4
Generates realistic fake data to validate all 8 pending KPIs:
- KPI #1: WIP Aging
- KPI #2: On-Time Delivery
- KPI #4: Quality PPM
- KPI #5: Quality DPMO
- KPI #6: Quality FPY
- KPI #7: Quality RTY
- KPI #8: Availability
- KPI #10: Absenteeism
"""

import sqlite3
import random
from datetime import datetime, timedelta
from typing import List, Dict
import json

# Configuration
DB_PATH = "../kpi_platform.db"
NUM_WORK_ORDERS = 150
NUM_EMPLOYEES = 50
NUM_QUALITY_ENTRIES = 200
DATE_RANGE_DAYS = 90

# Client configuration
CLIENTS = [
    {"client_id": "BOOT-LINE-A", "name": "Boot Manufacturing Line A"},
    {"client_id": "CLIENT-B", "name": "Apparel Client B"},
    {"client_id": "CLIENT-C", "name": "Textile Client C"}
]

# Style/Model configurations
STYLES = [
    {"style": "T-SHIRT-001", "cycle_time": 0.15, "opportunities": 8},  # 9 min = 0.15 hrs
    {"style": "POLO-002", "cycle_time": 0.20, "opportunities": 12},    # 12 min = 0.20 hrs
    {"style": "JACKET-003", "cycle_time": 0.50, "opportunities": 25},  # 30 min = 0.50 hrs
    {"style": "PANTS-004", "cycle_time": 0.25, "opportunities": 15},   # 15 min = 0.25 hrs
    {"style": "DRESS-005", "cycle_time": 0.35, "opportunities": 20}    # 21 min = 0.35 hrs
]

# Downtime reasons distribution
DOWNTIME_REASONS = [
    ("EQUIPMENT_FAILURE", 25),
    ("MATERIAL_SHORTAGE", 20),
    ("SETUP_CHANGEOVER", 30),
    ("QUALITY_HOLD", 15),
    ("MAINTENANCE", 10)
]

# Absence types distribution
ABSENCE_TYPES = [
    ("UNSCHEDULED_ABSENCE", 40),
    ("VACATION", 30),
    ("MEDICAL_LEAVE", 20),
    ("PERSONAL_LEAVE", 10)
]

def get_db_connection():
    """Create database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def random_date(start_days_ago: int, end_days_ago: int = 0) -> str:
    """Generate random date in YYYY-MM-DD format"""
    days_ago = random.randint(end_days_ago, start_days_ago)
    date = datetime.now() - timedelta(days=days_ago)
    return date.strftime('%Y-%m-%d')

def weighted_choice(choices: List[tuple]) -> str:
    """Make weighted random choice from (value, weight) tuples"""
    total = sum(weight for _, weight in choices)
    r = random.randint(1, total)
    cumulative = 0
    for value, weight in choices:
        cumulative += weight
        if r <= cumulative:
            return value
    return choices[0][0]

def generate_work_orders(conn: sqlite3.Connection) -> List[str]:
    """Generate work orders for Phase 2"""
    print(f"Generating {NUM_WORK_ORDERS} work orders...")

    work_order_ids = []
    cursor = conn.cursor()

    for i in range(NUM_WORK_ORDERS):
        client = random.choice(CLIENTS)
        style = random.choice(STYLES)

        # Generate dates ensuring logical flow
        start_days_ago = random.randint(10, DATE_RANGE_DAYS)
        actual_start = random_date(start_days_ago, start_days_ago - 5)
        planned_ship = random_date(start_days_ago - 7, 0)

        # 70% on-time, 30% late for OTD validation
        if random.random() < 0.7:
            actual_delivery = random_date(start_days_ago - 7, start_days_ago - 10)
        else:
            actual_delivery = random_date(start_days_ago - 5, 0)

        wo_id = f"WO-{i+1:05d}"
        planned_qty = random.randint(500, 5000)
        actual_qty = int(planned_qty * random.uniform(0.85, 1.0))

        # Status distribution
        status_choices = [
            ("COMPLETED", 50),
            ("ACTIVE", 30),
            ("ON_HOLD", 10),
            ("CANCELLED", 5),
            ("REJECTED", 5)
        ]
        status = weighted_choice(status_choices)

        cursor.execute("""
            INSERT INTO work_order (
                work_order_id, client_id, style_model,
                planned_quantity, actual_quantity,
                actual_start_date, planned_ship_date, actual_delivery_date,
                ideal_cycle_time, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            wo_id, client["client_id"], style["style"],
            planned_qty, actual_qty,
            actual_start, planned_ship, actual_delivery if status == "COMPLETED" else None,
            style["cycle_time"], status,
            datetime.now().isoformat()
        ))

        work_order_ids.append(wo_id)

    conn.commit()
    print(f"✓ Created {len(work_order_ids)} work orders")
    return work_order_ids

def generate_downtime_entries(conn: sqlite3.Connection, work_order_ids: List[str]):
    """Generate downtime entries for Availability KPI"""
    print("Generating downtime entries...")

    cursor = conn.cursor()
    entry_count = 0

    # 60% of work orders have at least one downtime event
    work_orders_with_downtime = random.sample(work_order_ids, int(len(work_order_ids) * 0.6))

    for wo_id in work_orders_with_downtime:
        # 1-3 downtime events per work order
        num_events = random.randint(1, 3)

        for _ in range(num_events):
            downtime_reason = weighted_choice(DOWNTIME_REASONS)
            duration_minutes = random.randint(15, 240)  # 15 min to 4 hours
            shift_date = random_date(DATE_RANGE_DAYS, 0)

            entry_id = f"DT-{entry_count+1:06d}"

            cursor.execute("""
                INSERT INTO downtime_entry (
                    downtime_entry_id, work_order_id, shift_date,
                    downtime_reason, downtime_duration_minutes,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry_id, wo_id, shift_date,
                downtime_reason, duration_minutes,
                datetime.now().isoformat()
            ))

            entry_count += 1

    conn.commit()
    print(f"✓ Created {entry_count} downtime entries")

def generate_hold_entries(conn: sqlite3.Connection, work_order_ids: List[str]):
    """Generate hold/resume entries for WIP Aging KPI"""
    print("Generating hold/resume entries...")

    cursor = conn.cursor()
    entry_count = 0

    # 30% of work orders experience holds
    work_orders_with_holds = random.sample(work_order_ids, int(len(work_order_ids) * 0.3))

    for wo_id in work_orders_with_holds:
        hold_date = random_date(DATE_RANGE_DAYS, 10)

        # 70% are resumed, 30% still on hold
        if random.random() < 0.7:
            resume_date = random_date(5, 0)
            hold_status = "RESUMED"
            hold_duration = random.uniform(24, 240)  # 1-10 days
        else:
            resume_date = None
            hold_status = "ON_HOLD"
            hold_duration = 0

        entry_id = f"HOLD-{entry_count+1:06d}"

        cursor.execute("""
            INSERT INTO hold_entry (
                hold_entry_id, work_order_id, hold_status,
                hold_date, resume_date, total_hold_duration_hours,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id, wo_id, hold_status,
            hold_date, resume_date, hold_duration,
            datetime.now().isoformat()
        ))

        entry_count += 1

    conn.commit()
    print(f"✓ Created {entry_count} hold/resume entries")

def generate_employees(conn: sqlite3.Connection) -> List[int]:
    """Generate employee records for Phase 3"""
    print(f"Generating {NUM_EMPLOYEES} employees...")

    cursor = conn.cursor()
    employee_ids = []

    for i in range(NUM_EMPLOYEES):
        emp_code = f"EMP-{i+1:04d}"
        emp_name = f"Employee {i+1}"

        # 10% are floating pool
        is_floating = 1 if i < int(NUM_EMPLOYEES * 0.1) else 0

        cursor.execute("""
            INSERT INTO employee (
                employee_code, employee_name, is_floating_pool,
                created_at
            ) VALUES (?, ?, ?, ?)
        """, (emp_code, emp_name, is_floating, datetime.now().isoformat()))

        employee_ids.append(cursor.lastrowid)

    conn.commit()
    print(f"✓ Created {len(employee_ids)} employees")
    return employee_ids

def generate_attendance_entries(conn: sqlite3.Connection, employee_ids: List[int]):
    """Generate attendance entries for Absenteeism KPI"""
    print("Generating attendance entries...")

    cursor = conn.cursor()
    entry_count = 0

    # Generate 30 days of attendance for each employee
    for emp_id in employee_ids:
        for day_offset in range(30):
            shift_date = (datetime.now() - timedelta(days=day_offset)).strftime('%Y-%m-%d')
            scheduled_hours = 8.0

            # 15% absenteeism rate (industry typical)
            is_absent = 1 if random.random() < 0.15 else 0

            if is_absent:
                actual_hours = 0.0
                absence_type = weighted_choice(ABSENCE_TYPES)
            else:
                actual_hours = scheduled_hours * random.uniform(0.95, 1.0)
                absence_type = None

            entry_id = f"ATT-{entry_count+1:07d}"

            cursor.execute("""
                INSERT INTO attendance_entry (
                    attendance_entry_id, employee_id, shift_date,
                    scheduled_hours, actual_hours, is_absent,
                    absence_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry_id, emp_id, shift_date,
                scheduled_hours, actual_hours, is_absent,
                absence_type, datetime.now().isoformat()
            ))

            entry_count += 1

    conn.commit()
    print(f"✓ Created {entry_count} attendance entries")

def generate_quality_entries(conn: sqlite3.Connection, work_order_ids: List[str]):
    """Generate quality inspection entries for Quality KPIs"""
    print(f"Generating {NUM_QUALITY_ENTRIES} quality entries...")

    cursor = conn.cursor()

    for i in range(NUM_QUALITY_ENTRIES):
        wo_id = random.choice(work_order_ids)

        # Get style info for opportunities
        cursor.execute("SELECT style_model FROM work_order WHERE work_order_id = ?", (wo_id,))
        style_model = cursor.fetchone()[0]
        style = next((s for s in STYLES if s["style"] == style_model), STYLES[0])

        units_inspected = random.randint(50, 500)

        # Quality distribution: 85% good, 10% minor defects, 5% major defects
        quality_roll = random.random()
        if quality_roll < 0.85:
            # Good quality
            units_passed = units_inspected
            units_defective = 0
            total_defects = 0
        elif quality_roll < 0.95:
            # Minor defects
            units_defective = int(units_inspected * random.uniform(0.02, 0.10))
            units_passed = units_inspected - units_defective
            total_defects = units_defective * random.randint(1, 3)
        else:
            # Major defects
            units_defective = int(units_inspected * random.uniform(0.10, 0.30))
            units_passed = units_inspected - units_defective
            total_defects = units_defective * random.randint(2, 5)

        entry_id = f"QC-{i+1:06d}"
        shift_date = random_date(DATE_RANGE_DAYS, 0)

        cursor.execute("""
            INSERT INTO quality_entry (
                quality_entry_id, work_order_id, shift_date,
                units_inspected, units_passed, units_defective,
                total_defects_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id, wo_id, shift_date,
            units_inspected, units_passed, units_defective,
            total_defects, datetime.now().isoformat()
        ))

    conn.commit()
    print(f"✓ Created {NUM_QUALITY_ENTRIES} quality entries")

def generate_part_opportunities(conn: sqlite3.Connection):
    """Generate part opportunities master data for DPMO calculation"""
    print("Generating part opportunities...")

    cursor = conn.cursor()

    for style in STYLES:
        cursor.execute("""
            INSERT INTO part_opportunities (
                part_number, opportunities_per_unit
            ) VALUES (?, ?)
        """, (style["style"], style["opportunities"]))

    conn.commit()
    print(f"✓ Created {len(STYLES)} part opportunity records")

def validate_data_integrity(conn: sqlite3.Connection):
    """Validate generated data meets KPI requirements"""
    print("\nValidating data integrity...")

    cursor = conn.cursor()

    # Check work orders
    cursor.execute("SELECT COUNT(*) as cnt FROM work_order")
    wo_count = cursor.fetchone()[0]
    print(f"  ✓ Work Orders: {wo_count}")

    # Check downtime entries
    cursor.execute("SELECT COUNT(*) as cnt FROM downtime_entry")
    dt_count = cursor.fetchone()[0]
    print(f"  ✓ Downtime Entries: {dt_count}")

    # Check hold entries
    cursor.execute("SELECT COUNT(*) as cnt FROM hold_entry")
    hold_count = cursor.fetchone()[0]
    print(f"  ✓ Hold Entries: {hold_count}")

    # Check employees
    cursor.execute("SELECT COUNT(*) as cnt FROM employee")
    emp_count = cursor.fetchone()[0]
    print(f"  ✓ Employees: {emp_count}")

    # Check attendance
    cursor.execute("SELECT COUNT(*) as cnt FROM attendance_entry")
    att_count = cursor.fetchone()[0]
    print(f"  ✓ Attendance Entries: {att_count}")

    # Check quality entries
    cursor.execute("SELECT COUNT(*) as cnt FROM quality_entry")
    qc_count = cursor.fetchone()[0]
    print(f"  ✓ Quality Entries: {qc_count}")

    # Check part opportunities
    cursor.execute("SELECT COUNT(*) as cnt FROM part_opportunities")
    po_count = cursor.fetchone()[0]
    print(f"  ✓ Part Opportunities: {po_count}")

    print("\n✓ Data integrity validation complete!")

def main():
    """Main execution"""
    print("=" * 70)
    print("KPI PLATFORM - SAMPLE DATA GENERATOR")
    print("Phases 2-4: WIP, Downtime, Attendance, Quality")
    print("=" * 70)
    print()

    conn = get_db_connection()

    try:
        # Phase 2: Work Orders, Downtime, Holds
        work_order_ids = generate_work_orders(conn)
        generate_downtime_entries(conn, work_order_ids)
        generate_hold_entries(conn, work_order_ids)

        # Phase 3: Employees, Attendance
        employee_ids = generate_employees(conn)
        generate_attendance_entries(conn, employee_ids)

        # Phase 4: Quality, Part Opportunities
        generate_quality_entries(conn, work_order_ids)
        generate_part_opportunities(conn)

        # Validate
        validate_data_integrity(conn)

        print("\n" + "=" * 70)
        print("✓ SAMPLE DATA GENERATION COMPLETE!")
        print("=" * 70)
        print("\nReady to validate 8 pending KPIs:")
        print("  - KPI #1: WIP Aging")
        print("  - KPI #2: On-Time Delivery")
        print("  - KPI #4: Quality PPM")
        print("  - KPI #5: Quality DPMO")
        print("  - KPI #6: Quality FPY")
        print("  - KPI #7: Quality RTY")
        print("  - KPI #8: Availability")
        print("  - KPI #10: Absenteeism")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
