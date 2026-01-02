#!/usr/bin/env python3
"""
Multi-Tenant Sample Data Generator
Creates comprehensive sample data for 5 clients with realistic production scenarios
"""

import sqlite3
from datetime import datetime, timedelta
import random
import os

# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'kpi_platform.db')

print("🚀 Starting Multi-Tenant Sample Data Generation...")
print("=" * 70)

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # 0. CREATE SYSTEM USER (for foreign key requirements)
    print("\n👤 Step 0: Creating System User...")
    try:
        cursor.execute("""
            INSERT INTO USER (user_id, username, full_name, email, role, is_active, created_at)
            VALUES ('SYSTEM', 'system', 'System Administrator', 'system@kpi.local', 'SYSTEM', 1, datetime('now'))
        """)
        print("   ✓ Created SYSTEM user")
    except sqlite3.IntegrityError:
        print("   ⚠  SYSTEM user already exists")

    # 1. CREATE 5 CLIENTS
    print("\n📋 Step 1: Creating 5 Clients...")
    clients = [
        ('BOOT-LINE-A', 'Boot Line A Manufacturing', 'Piece Rate'),
        ('APPAREL-B', 'Apparel B Production', 'Hourly Rate'),
        ('TEXTILE-C', 'Textile C Industries', 'Hybrid'),
        ('FOOTWEAR-D', 'Footwear D Factory', 'Piece Rate'),
        ('GARMENT-E', 'Garment E Suppliers', 'Hourly Rate')
    ]

    client_count = 0
    for client_id, client_name, client_type in clients:
        try:
            cursor.execute("""
                INSERT INTO CLIENT (client_id, client_name, client_type, timezone, is_active, created_at)
                VALUES (?, ?, ?, 'US/Eastern', 1, datetime('now'))
            """, (client_id, client_name, client_type))
            client_count += 1
            print(f"   ✓ {client_id}: {client_name}")
        except sqlite3.IntegrityError:
            print(f"   ⚠  {client_id} already exists")

    # 2. CREATE 100 EMPLOYEES
    print("\n👥 Step 2: Creating 100 Employees...")
    print("   - 80 regular employees (16 per client)")
    print("   - 20 floating pool employees")

    employee_count = 0

    # Regular employees (16 per client = 80 total)
    for client_id, _, _ in clients:
        for j in range(16):
            emp_id = f"EMP-{client_id}-{j+1:03d}"
            emp_name = f"Employee {client_id}-{j+1:03d}"
            try:
                cursor.execute("""
                    INSERT INTO EMPLOYEE (employee_id, employee_name, client_id_assigned, is_floating_pool, created_at)
                    VALUES (?, ?, ?, 0, datetime('now'))
                """, (emp_id, emp_name, client_id))
                employee_count += 1
            except sqlite3.IntegrityError:
                pass

    # Floating pool (20 employees)
    for k in range(20):
        emp_id = f"EMP-FLOAT-{k+1:03d}"
        emp_name = f"Floating Employee {k+1}"
        try:
            cursor.execute("""
                INSERT INTO EMPLOYEE (employee_id, employee_name, client_id_assigned, is_floating_pool, created_at)
                VALUES (?, ?, NULL, 1, datetime('now'))
            """, (emp_id, emp_name))
            employee_count += 1
        except sqlite3.IntegrityError:
            pass

    print(f"   ✓ Created {employee_count} employees")

    # 3. CREATE 25 WORK ORDERS (5 per client)
    print("\n📦 Step 3: Creating 25 Work Orders (5 per client)...")
    styles = ['T-SHIRT', 'POLO', 'JACKET', 'PANTS', 'DRESS']
    base_date = datetime.now() - timedelta(days=90)

    work_order_count = 0
    work_orders_list = []

    for client_idx, (client_id, _, _) in enumerate(clients):
        for wo_idx in range(5):
            work_order_id = f"WO-{client_id}-{wo_idx+1:03d}"
            style = styles[wo_idx % len(styles)]

            start_date = base_date + timedelta(days=wo_idx*15)
            ship_date = start_date + timedelta(days=20)
            delivery_date = ship_date + timedelta(days=random.randint(-5, 5))

            planned_qty = random.randint(800, 1200)
            actual_qty = int(planned_qty * random.uniform(0.92, 0.98))

            try:
                cursor.execute("""
                    INSERT INTO WORK_ORDER (
                        work_order_id, client_id, style_model, planned_quantity,
                        actual_start_date, planned_ship_date,
                        ideal_cycle_time, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'COMPLETED', datetime('now'))
                """, (
                    work_order_id, client_id, style, planned_qty,
                    start_date.strftime('%Y-%m-%d'), ship_date.strftime('%Y-%m-%d'),
                    0.25  # 15 minutes = 0.25 hours
                ))
                work_orders_list.append((work_order_id, client_id, start_date, planned_qty))
                work_order_count += 1
            except sqlite3.IntegrityError as e:
                print(f"   ⚠  Error inserting work order {work_order_id}: {e}")
                pass

    print(f"   ✓ Created {work_order_count} work orders")

    # 4. CREATE SHIFTS FIRST (required for foreign key)
    print("\n⏰ Step 4: Creating Shifts...")
    shifts = [
        (1, '1st Shift', '06:00', '14:00'),
        (2, '2nd Shift', '14:00', '22:00'),
        (3, '3rd Shift', '22:00', '06:00')
    ]

    shift_count = 0
    for shift_id, shift_name, start_time, end_time in shifts:
        try:
            cursor.execute("""
                INSERT INTO SHIFT (shift_id, shift_name, start_time, end_time, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (shift_id, shift_name, start_time, end_time))
            shift_count += 1
            print(f"   ✓ {shift_name}")
        except sqlite3.IntegrityError:
            print(f"   ⚠  {shift_name} already exists")

    # 5. CREATE PRODUCTS (required for foreign key)
    print("\n📦 Step 5: Creating Products...")
    products_list = []
    product_count = 0

    for i in range(10):
        product_id = f"PROD-{i+1:03d}"
        product_name = f"Product {i+1}"
        ideal_cycle_time = round(random.uniform(0.15, 0.35), 4)  # 9-21 minutes

        try:
            cursor.execute("""
                INSERT INTO PRODUCT (product_id, product_name, ideal_cycle_time, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (product_id, product_name, ideal_cycle_time))
            products_list.append((product_id, ideal_cycle_time))
            product_count += 1
        except sqlite3.IntegrityError:
            pass

    print(f"   ✓ Created {product_count} products")

    # 6. CREATE PRODUCTION ENTRIES (3 per work order = 75 total)
    print("\n🏭 Step 6: Creating Production Entries (3 per work order)...")
    production_count = 0

    for work_order_id, client_id, start_date, total_qty in work_orders_list:
        remaining_qty = total_qty
        for prod_idx in range(3):
            prod_entry_id = f"PE-{work_order_id}-{prod_idx+1}"
            prod_date = start_date + timedelta(days=prod_idx*5)

            # Distribute production across 3 entries
            if prod_idx == 2:  # Last entry gets remaining
                units_produced = remaining_qty
            else:
                units_produced = int(total_qty * random.uniform(0.30, 0.35))
                remaining_qty -= units_produced

            run_time = random.uniform(7.5, 8.5)
            employees = random.randint(4, 6)
            defects = random.randint(0, int(units_produced * 0.02))

            # Get random product
            product_id, ideal_cycle = random.choice(products_list)

            # Calculate metrics
            actual_cycle = round(run_time / units_produced if units_produced > 0 else 0, 4)
            efficiency = round(random.uniform(0.85, 0.95), 4)
            performance = round(min(ideal_cycle / actual_cycle if actual_cycle > 0 else 0, 1.0), 4)
            quality_rate = round((units_produced - defects) / units_produced if units_produced > 0 else 0, 4)

            try:
                cursor.execute("""
                    INSERT INTO PRODUCTION_ENTRY (
                        production_entry_id, client_id, product_id, shift_id,
                        work_order_id, production_date, shift_date,
                        units_produced, run_time_hours, employees_assigned,
                        defect_count, scrap_count, ideal_cycle_time, actual_cycle_time,
                        efficiency_percentage, performance_percentage, quality_rate,
                        entered_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SYSTEM', datetime('now'))
                """, (
                    prod_entry_id, client_id, product_id, 1,
                    work_order_id, prod_date.strftime('%Y-%m-%d'), prod_date.strftime('%Y-%m-%d'),
                    units_produced, run_time, employees,
                    defects, random.randint(0, int(defects * 0.3)), ideal_cycle, actual_cycle,
                    efficiency, performance, quality_rate
                ))
                production_count += 1
            except sqlite3.IntegrityError as e:
                print(f"   ⚠  Error inserting production entry: {e}")
                pass

    print(f"   ✓ Created {production_count} production entries")

    # 7. CREATE QUALITY ENTRIES (1 per work order = 25 total)
    print("\n✅ Step 7: Creating Quality Entries (1 per work order)...")
    quality_count = 0

    for work_order_id, client_id, start_date, total_qty in work_orders_list:
        quality_id = f"QE-{work_order_id}-001"
        units_inspected = total_qty
        units_passed = int(units_inspected * random.uniform(0.94, 0.98))
        units_failed = units_inspected - units_passed
        total_defects = units_failed + random.randint(0, int(units_failed * 0.2))

        try:
            cursor.execute("""
                INSERT INTO QUALITY_ENTRY (
                    quality_entry_id, client_id, work_order_id,
                    inspection_date, units_inspected, units_passed, units_failed,
                    total_defects_count, entered_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SYSTEM', datetime('now'))
            """, (
                quality_id, client_id, work_order_id, start_date.strftime('%Y-%m-%d'),
                units_inspected, units_passed, units_failed, total_defects
            ))
            quality_count += 1
        except sqlite3.IntegrityError as e:
            print(f"   ⚠  Error inserting quality entry: {e}")
            pass

    print(f"   ✓ Created {quality_count} quality entries")

    # 8. CREATE ATTENDANCE ENTRIES (60 days per employee)
    print("\n📅 Step 8: Creating Attendance Entries (60 days per employee)...")
    attendance_count = 0
    attendance_base_date = datetime.now() - timedelta(days=60)

    for client_id, _, _ in clients:
        # Get employees for this client
        cursor.execute("SELECT employee_id FROM EMPLOYEE WHERE client_id_assigned = ?", (client_id,))
        employees = cursor.fetchall()

        for employee_id, in employees:
            for day in range(60):
                attendance_date = attendance_base_date + timedelta(days=day)

                # 95% attendance rate
                is_present = random.random() < 0.95
                scheduled = 8.0
                actual_hours = random.uniform(7.5, 8.5) if is_present else 0

                try:
                    cursor.execute("""
                        INSERT INTO ATTENDANCE_ENTRY (
                            employee_id, client_id, shift_id,
                            attendance_date, scheduled_hours, actual_hours,
                            is_absent, entered_by, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SYSTEM', datetime('now'))
                    """, (
                        employee_id, client_id, 1,
                        attendance_date.strftime('%Y-%m-%d'),
                        scheduled, actual_hours, 0 if is_present else 1
                    ))
                    attendance_count += 1
                except sqlite3.IntegrityError:
                    pass

    print(f"   ✓ Created {attendance_count} attendance entries")

    # 9. CREATE DOWNTIME ENTRIES (2-3 per work order)
    print("\n⏸️  Step 9: Creating Downtime Entries (2-3 per work order)...")
    downtime_count = 0
    downtime_reasons = [
        'EQUIPMENT_FAILURE', 'MATERIAL_SHORTAGE', 'CHANGEOVER_SETUP',
        'MAINTENANCE_SCHEDULED', 'QC_HOLD', 'OTHER'
    ]

    for work_order_id, client_id, start_date, _ in work_orders_list:
        num_downtimes = random.randint(2, 3)
        for dt_idx in range(num_downtimes):
            downtime_date = start_date + timedelta(days=random.randint(0, 15))
            downtime_minutes = int(random.uniform(30, 180))
            reason = random.choice(downtime_reasons)

            try:
                cursor.execute("""
                    INSERT INTO DOWNTIME_ENTRY (
                        client_id, work_order_id, shift_id,
                        downtime_date, downtime_reason, downtime_duration_minutes,
                        entered_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'SYSTEM', datetime('now'))
                """, (
                    client_id, work_order_id, 1,
                    downtime_date.strftime('%Y-%m-%d'),
                    reason, downtime_minutes
                ))
                downtime_count += 1
            except sqlite3.IntegrityError:
                pass

    print(f"   ✓ Created {downtime_count} downtime entries")

    # Commit all changes
    conn.commit()

    # SUMMARY
    print("\n" + "=" * 70)
    print("✅ SAMPLE DATA GENERATION COMPLETED!")
    print("=" * 70)
    print(f"""
SUMMARY:
   - 5 Clients: {', '.join([c[0] for c in clients])}
   - {employee_count} Employees (80 regular + 20 floating pool)
   - {shift_count} Shifts (1st, 2nd, 3rd)
   - {product_count} Products
   - {work_order_count} Work Orders (5 per client)
   - {production_count} Production Entries (3 per work order)
   - {quality_count} Quality Entries (1 per work order)
   - {attendance_count} Attendance Entries (60 days × employees)
   - {downtime_count} Downtime Entries (2-3 per work order)

Database: {DB_PATH}
""")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
    raise

finally:
    conn.close()
