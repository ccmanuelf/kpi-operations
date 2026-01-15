#!/usr/bin/env python3
"""
Populate Missing Tables for KPI Operations Platform
This script populates the empty tables: JOB, HOLD_ENTRY, SHIFT_COVERAGE, DEFECT_DETAIL, PART_OPPORTUNITIES
"""

import sqlite3
import random
from datetime import datetime, timedelta
import os

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'kpi_platform.db')

print("🚀 Populating Missing Tables...")
print("=" * 70)
print(f"Database: {os.path.abspath(DB_PATH)}")

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get existing data for foreign keys
cursor.execute("SELECT work_order_id, client_id FROM WORK_ORDER")
work_orders = cursor.fetchall()

cursor.execute("SELECT quality_entry_id, client_id FROM QUALITY_ENTRY")
quality_entries = cursor.fetchall()

cursor.execute("SELECT client_id FROM CLIENT")
clients = [row[0] for row in cursor.fetchall()]

cursor.execute("SELECT employee_id FROM EMPLOYEE WHERE is_floating_pool = 0 LIMIT 20")
employees = [row[0] for row in cursor.fetchall()]

print(f"\n📋 Found {len(work_orders)} work orders, {len(quality_entries)} quality entries, {len(clients)} clients")

try:
    # 1. POPULATE JOB TABLE (Work Order Line Items)
    print("\n📦 Step 1: Creating JOB entries (work order line items)...")
    
    operations = [
        ('CUT', 'Cutting', 'Cut fabric/material to specifications'),
        ('SEW', 'Sewing', 'Assemble garment components'),
        ('PRESS', 'Pressing', 'Steam and press finished items'),
        ('QC', 'Quality Check', 'Inspect for defects'),
        ('PACK', 'Packaging', 'Package for shipment'),
        ('EMBO', 'Embroidery', 'Add embroidered details'),
        ('TRIM', 'Trimming', 'Trim excess threads and materials'),
        ('INSP', 'Inspection', 'Final inspection before shipping')
    ]
    
    job_count = 0
    for wo_id, client_id in work_orders:
        # Each work order has 3-5 jobs
        num_jobs = random.randint(3, 5)
        selected_ops = random.sample(operations, num_jobs)
        
        for seq, (op_code, op_name, op_desc) in enumerate(selected_ops, 1):
            job_id = f"JOB-{wo_id}-{seq:02d}"
            planned_qty = random.randint(100, 500)
            completed_qty = random.randint(0, planned_qty) if random.random() > 0.3 else 0
            planned_hours = round(random.uniform(2, 8), 2)
            actual_hours = round(planned_hours * random.uniform(0.8, 1.3), 2) if completed_qty > 0 else None
            is_completed = 1 if completed_qty >= planned_qty else 0
            completed_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if is_completed else None
            
            try:
                cursor.execute("""
                    INSERT INTO JOB (job_id, work_order_id, client_id, operation_name, operation_code, 
                                    sequence_number, part_number, part_description, planned_quantity, 
                                    completed_quantity, planned_hours, actual_hours, is_completed, 
                                    completed_date, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (job_id, wo_id, client_id, op_name, op_code, seq, f"PART-{op_code}-001", op_desc,
                      planned_qty, completed_qty, planned_hours, actual_hours, is_completed, completed_date,
                      f"Auto-generated job for {op_name}"))
                job_count += 1
            except sqlite3.IntegrityError as e:
                print(f"   ⚠  {job_id} already exists")
    
    print(f"   ✓ Created {job_count} JOB entries")

    # 2. POPULATE HOLD_ENTRY TABLE
    print("\n⏸️  Step 2: Creating HOLD_ENTRY records...")
    
    hold_reasons = [
        'Material Inspection Pending',
        'Quality Issue - Rework Required',
        'Customer Design Change Request',
        'Missing Specifications',
        'Equipment Maintenance',
        'Capacity Constraint',
        'Supplier Delay',
        'Engineering Review'
    ]
    
    hold_count = 0
    for wo_id, client_id in work_orders:
        # 30% of work orders have holds
        if random.random() < 0.3:
            hold_date = datetime.now() - timedelta(days=random.randint(1, 60))
            released = random.random() < 0.6  # 60% are released
            released_date = (hold_date + timedelta(days=random.randint(1, 14))).strftime('%Y-%m-%d') if released else None
            
            try:
                cursor.execute("""
                    INSERT INTO HOLD_ENTRY (client_id, work_order_id, placed_on_hold_date, released_date,
                                           hold_reason, units_on_hold, entered_by, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'SYSTEM', ?, datetime('now'))
                """, (client_id, wo_id, hold_date.strftime('%Y-%m-%d'), released_date,
                      random.choice(hold_reasons), random.randint(10, 100),
                      'Auto-generated hold entry for testing'))
                hold_count += 1
            except sqlite3.IntegrityError as e:
                print(f"   ⚠  Hold for {wo_id} already exists")
    
    print(f"   ✓ Created {hold_count} HOLD_ENTRY records")

    # 3. POPULATE SHIFT_COVERAGE TABLE
    print("\n👥 Step 3: Creating SHIFT_COVERAGE records...")
    
    shift_count = 0
    base_date = datetime.now() - timedelta(days=30)
    
    for client_id in clients:
        # 30 days of coverage data per client
        for day_offset in range(30):
            coverage_date = base_date + timedelta(days=day_offset)
            
            # Skip weekends
            if coverage_date.weekday() >= 5:
                continue
            
            # Each shift (1, 2, 3)
            for shift_id in [1, 2, 3]:
                scheduled = random.randint(15, 25)
                present = max(0, scheduled - random.randint(0, 5))
                coverage_pct = round((present / scheduled) * 100, 2) if scheduled > 0 else 0
                
                try:
                    cursor.execute("""
                        INSERT INTO SHIFT_COVERAGE (client_id, shift_id, coverage_date, employees_scheduled,
                                                   employees_present, coverage_percentage, entered_by, 
                                                   notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, 'SYSTEM', ?, datetime('now'))
                    """, (client_id, shift_id, coverage_date.strftime('%Y-%m-%d'),
                          scheduled, present, coverage_pct,
                          'Auto-generated shift coverage'))
                    shift_count += 1
                except sqlite3.IntegrityError:
                    pass
    
    print(f"   ✓ Created {shift_count} SHIFT_COVERAGE records")

    # 4. POPULATE DEFECT_DETAIL TABLE
    print("\n🔍 Step 4: Creating DEFECT_DETAIL records...")
    
    defect_types = [
        ('STITCH', 'Stitching Defects', ['Loose stitch', 'Skipped stitch', 'Broken thread']),
        ('FABRIC', 'Fabric Defects', ['Tear', 'Stain', 'Color variation']),
        ('SIZE', 'Sizing Issues', ['Too large', 'Too small', 'Inconsistent']),
        ('FINISH', 'Finish Defects', ['Rough edge', 'Poor pressing', 'Wrinkles']),
        ('LABEL', 'Labeling Issues', ['Wrong label', 'Missing label', 'Misplaced label']),
        ('ZIPPER', 'Zipper Defects', ['Stuck zipper', 'Broken teeth', 'Wrong color'])
    ]
    
    severities = ['CRITICAL', 'MAJOR', 'MINOR', 'COSMETIC']
    locations = ['Front', 'Back', 'Sleeve', 'Collar', 'Hem', 'Pocket', 'Button Area']
    
    defect_count = 0
    for qe_id, client_id in quality_entries:
        # 40% of quality entries have defects
        if random.random() < 0.4:
            num_defects = random.randint(1, 4)
            for i in range(num_defects):
                defect_id = f"DEF-{qe_id}-{i+1:02d}"
                defect_type, defect_cat, descriptions = random.choice(defect_types)
                
                try:
                    cursor.execute("""
                        INSERT INTO DEFECT_DETAIL (defect_detail_id, quality_entry_id, client_id,
                                                  defect_type, defect_category, defect_count, 
                                                  severity, location, description, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (defect_id, qe_id, client_id, defect_type, defect_cat,
                          random.randint(1, 10), random.choice(severities),
                          random.choice(locations), random.choice(descriptions)))
                    defect_count += 1
                except sqlite3.IntegrityError:
                    pass
    
    print(f"   ✓ Created {defect_count} DEFECT_DETAIL records")

    # 5. POPULATE PART_OPPORTUNITIES TABLE
    print("\n📊 Step 5: Creating PART_OPPORTUNITIES records...")
    
    parts = [
        ('COLLAR-001', 'Collar Assembly', 'Collar', 5),
        ('SLEEVE-001', 'Sleeve Unit', 'Sleeve', 3),
        ('POCKET-001', 'Pocket Assembly', 'Pocket', 2),
        ('BUTTON-001', 'Button Set', 'Button', 8),
        ('ZIPPER-001', 'Zipper Assembly', 'Zipper', 4),
        ('HEM-001', 'Hem Finish', 'Hem', 2),
        ('CUFF-001', 'Cuff Assembly', 'Cuff', 4),
        ('SEAM-001', 'Seam Construction', 'Seam', 6),
        ('LABEL-001', 'Label Application', 'Label', 3),
        ('BODY-001', 'Body Panel', 'Body', 4)
    ]
    
    part_count = 0
    for client_id in clients:
        for part_num, part_desc, part_cat, opps in parts:
            full_part_num = f"{client_id}-{part_num}"
            
            try:
                cursor.execute("""
                    INSERT INTO PART_OPPORTUNITIES (part_number, client_id, opportunities_per_unit,
                                                   part_description, part_category, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (full_part_num, client_id, opps, part_desc, part_cat,
                      'Auto-generated part opportunity'))
                part_count += 1
            except sqlite3.IntegrityError:
                pass
    
    print(f"   ✓ Created {part_count} PART_OPPORTUNITIES records")

    # Commit all changes
    conn.commit()
    print("\n" + "=" * 70)
    print("✅ All missing tables populated successfully!")
    
    # Print final counts
    print("\n📊 Final Table Counts:")
    tables = ['JOB', 'HOLD_ENTRY', 'SHIFT_COVERAGE', 'DEFECT_DETAIL', 'PART_OPPORTUNITIES']
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {table}: {count} records")

except Exception as e:
    print(f"\n❌ Error: {e}")
    conn.rollback()

finally:
    conn.close()
    print("\n🔒 Database connection closed")
