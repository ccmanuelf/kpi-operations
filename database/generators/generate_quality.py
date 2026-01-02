#!/usr/bin/env python3
"""
Generate realistic quality inspection sample data for KPIs #4-7 (PPM, DPMO, FPY, RTY)
Creates 200+ quality entries with defects, rework, and repair scenarios
"""

import random
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'kpi_operations',
    'user': 'root',
    'password': 'root'
}

# Sample work orders from seed data
WORK_ORDERS = [
    'WO-2025-001', 'WO-2025-002', 'WO-2025-003', 'WO-2025-004', 'WO-2025-005',
    'WO-2025-006', 'WO-2025-007', 'WO-2025-008', 'WO-2025-009', 'WO-2025-010',
    'WO-2025-011', 'WO-2025-012', 'WO-2025-013', 'WO-2025-014', 'WO-2025-015',
    'WO-2025-016', 'WO-2025-017', 'WO-2025-018', 'WO-2025-019'
]

CLIENTS = ['BOOT-LINE-A', 'CLIENT-B', 'CLIENT-C']

# Products from seed data (product_id 1-5)
PRODUCTS = [1, 2, 3, 4, 5]

OPERATIONS = [
    'INCOMING_MATERIAL',
    'IN_PROCESS_QC_CUTTING',
    'IN_PROCESS_QC_SEWING',
    'IN_PROCESS_QC_ASSEMBLY',
    'FINAL_INSPECTION',
    'PRE_SHIPMENT_AUDIT'
]

DEFECT_CATEGORIES = [
    'Stitching:crooked_seam',
    'Stitching:loose_thread',
    'Stitching:skipped_stitch',
    'Color:mismatch',
    'Color:fading',
    'Sizing:undersized',
    'Sizing:oversized',
    'Material:hole_tear',
    'Material:stain',
    'Material:texture_defect',
    'Assembly:misaligned_parts',
    'Assembly:missing_component',
    'Finishing:rough_edges',
    'Finishing:incomplete_coating',
    'Packaging:damaged_box',
    'Packaging:missing_label'
]

INSPECTION_METHODS = ['VISUAL', 'MEASUREMENT', 'FUNCTIONAL_TEST', 'SAMPLE_CHECK', '100_PERCENT_INSPECTION']


def generate_part_opportunities():
    """Generate part opportunities data (for DPMO calculation)"""
    opportunities = []

    # Define opportunities per unit for each product
    # Complex products have more opportunities for defects
    product_opportunities = {
        1: 15,  # WDG-001 Standard widget - moderate complexity
        2: 20,  # WDG-002 Premium widget - more complex
        3: 30,  # ASM-100 Assembly - high complexity
        4: 47,  # ASM-200 Advanced assembly - very complex (like western boot)
        5: 10   # PART-500 Generic part - simple
    }

    descriptions = {
        1: 'Standard widget: stitching (5), assembly (3), finish (4), packaging (3)',
        2: 'Premium widget: stitching (7), assembly (5), finish (5), packaging (3)',
        3: 'Assembly A100: seams (8), alignment (6), fit (8), finish (5), packaging (3)',
        4: 'Assembly A200: seams (12), alignment (10), components (10), fit (8), finish (5), packaging (2)',
        5: 'Generic part: surface (5), dimensions (3), packaging (2)'
    }

    for product_id, opps in product_opportunities.items():
        opportunity = {
            'product_id': product_id,
            'opportunities_per_unit': opps,
            'description': descriptions[product_id],
            'updated_by_user_id': 2,  # Supervisor
            'notes': f'Opportunities based on product complexity and critical check points'
        }
        opportunities.append(opportunity)

    return opportunities


def insert_part_opportunities(opportunities):
    """Insert part opportunities into database"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO part_opportunities (
                product_id, opportunities_per_unit, description, updated_by_user_id, notes
            ) VALUES (
                %(product_id)s, %(opportunities_per_unit)s, %(description)s,
                %(updated_by_user_id)s, %(notes)s
            )
        """

        cursor.executemany(insert_query, opportunities)
        connection.commit()

        print(f"✅ Successfully inserted {cursor.rowcount} part opportunity definitions")

        cursor.close()
        connection.close()

        return True

    except Error as e:
        print(f"❌ Database error inserting part opportunities: {e}")
        return False


def generate_quality_entries(count=250):
    """Generate realistic quality inspection entries"""
    entries = []
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    for i in range(count):
        # Random date in last 90 days
        random_days = random.randint(0, 90)
        shift_date = end_date - timedelta(days=random_days)

        # Select shift (1=Morning, 2=Afternoon)
        shift_id = random.choice([1, 1, 1, 2])  # 75% morning, 25% afternoon

        # Select work order, product, client
        work_order = random.choice(WORK_ORDERS)
        product_id = random.choice(PRODUCTS)
        client = random.choice(CLIENTS)

        # Select operation
        operation = random.choice(OPERATIONS)

        # Inspection method (final inspection more thorough)
        if operation == 'FINAL_INSPECTION':
            method = random.choice(['100_PERCENT_INSPECTION', 'FUNCTIONAL_TEST', 'MEASUREMENT'])
            sample_size = 100.0 if method == '100_PERCENT_INSPECTION' else random.uniform(20.0, 50.0)
        else:
            method = random.choice(['VISUAL', 'SAMPLE_CHECK', 'MEASUREMENT'])
            sample_size = random.uniform(5.0, 25.0) if method == 'SAMPLE_CHECK' else 100.0

        # Units inspected (varies by operation and method)
        if method == '100_PERCENT_INSPECTION':
            units_inspected = random.randint(50, 300)
        elif method == 'SAMPLE_CHECK':
            units_inspected = random.randint(10, 100)
        else:
            units_inspected = random.randint(25, 200)

        # Quality scenarios (80% good, 15% minor defects, 5% major defects)
        scenario_roll = random.random()

        if scenario_roll < 0.80:  # Good quality - high pass rate
            pass_rate = random.uniform(0.95, 1.00)
        elif scenario_roll < 0.95:  # Minor defects
            pass_rate = random.uniform(0.85, 0.95)
        else:  # Major quality issues
            pass_rate = random.uniform(0.60, 0.85)

        units_passed = int(units_inspected * pass_rate)
        units_defective = units_inspected - units_passed

        # Distribution of defective units (rework vs repair vs scrap)
        units_rework = 0
        units_repair = 0

        if units_defective > 0:
            # 60% can be repaired in current operation
            # 30% need rework (go back to previous operation)
            # 10% are scrapped
            for _ in range(units_defective):
                defect_roll = random.random()
                if defect_roll < 0.60:
                    units_repair += 1
                elif defect_roll < 0.90:
                    units_rework += 1
                # else: scrapped (neither rework nor repair)

        # Total defects count (for DPMO) - some units may have multiple defects
        # Average 1.2 defects per defective unit
        total_defects = int(units_defective * random.uniform(1.0, 1.5))

        # Generate defect categories
        if units_defective > 0:
            num_categories = min(random.randint(1, 4), units_defective)
            selected_defects = random.sample(DEFECT_CATEGORIES, num_categories)
            defect_categories = '; '.join(selected_defects)
        else:
            defect_categories = None

        # QC inspector and recorder (users 2-4)
        qc_inspector = random.choice([2, 3, 4])
        recorded_by = qc_inspector

        # Verification (70% verified)
        verified_by = 2 if random.random() < 0.70 else None

        # Notes (for defective batches)
        notes = None
        if units_defective > 0:
            if units_defective / units_inspected > 0.15:
                notes = 'High defect rate - root cause investigation initiated'
            elif units_rework > 0:
                notes = f'Rework required for {units_rework} units - operator training scheduled'
            elif units_repair > 0:
                notes = f'Minor defects repaired in current operation'

        entry = {
            'work_order_number': work_order,
            'product_id': product_id,
            'client_name': client,
            'shift_date': shift_date,
            'shift_id': shift_id,
            'operation_checked': operation,
            'units_inspected': units_inspected,
            'units_passed': units_passed,
            'units_defective': units_defective,
            'units_requiring_rework': units_rework,
            'units_requiring_repair': units_repair,
            'total_defects_count': total_defects,
            'defect_categories': defect_categories,
            'qc_inspector_id': qc_inspector,
            'recorded_by_user_id': recorded_by,
            'inspection_method': method,
            'sample_size_percent': round(sample_size, 2),
            'notes': notes,
            'verified_by_user_id': verified_by
        }

        entries.append(entry)

    return entries


def insert_quality_entries(entries):
    """Insert quality entries into database"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO quality_entry (
                work_order_number, product_id, client_name, shift_date, shift_id,
                operation_checked, units_inspected, units_passed, units_defective,
                units_requiring_rework, units_requiring_repair, total_defects_count,
                defect_categories, qc_inspector_id, recorded_by_user_id,
                inspection_method, sample_size_percent, notes, verified_by_user_id
            ) VALUES (
                %(work_order_number)s, %(product_id)s, %(client_name)s, %(shift_date)s, %(shift_id)s,
                %(operation_checked)s, %(units_inspected)s, %(units_passed)s, %(units_defective)s,
                %(units_requiring_rework)s, %(units_requiring_repair)s, %(total_defects_count)s,
                %(defect_categories)s, %(qc_inspector_id)s, %(recorded_by_user_id)s,
                %(inspection_method)s, %(sample_size_percent)s, %(notes)s, %(verified_by_user_id)s
            )
        """

        cursor.executemany(insert_query, entries)
        connection.commit()

        print(f"✅ Successfully inserted {cursor.rowcount} quality entries")

        # Statistics
        total_inspected = sum(e['units_inspected'] for e in entries)
        total_passed = sum(e['units_passed'] for e in entries)
        total_defective = sum(e['units_defective'] for e in entries)
        total_defects = sum(e['total_defects_count'] for e in entries)

        ppm = (total_defective / total_inspected * 1_000_000) if total_inspected > 0 else 0
        fpy = (total_passed / total_inspected * 100) if total_inspected > 0 else 0

        print(f"\n📊 Quality Statistics:")
        print(f"   Total units inspected: {total_inspected:,}")
        print(f"   Units passed first time: {total_passed:,}")
        print(f"   Defective units: {total_defective:,}")
        print(f"   Total defects found: {total_defects:,}")
        print(f"   PPM (Parts Per Million): {ppm:.0f}")
        print(f"   FPY (First Pass Yield): {fpy:.2f}%")

        cursor.close()
        connection.close()

    except Error as e:
        print(f"❌ Database error: {e}")


if __name__ == "__main__":
    print("🔍 Generating quality inspection sample data...")

    # First, insert part opportunities
    opportunities = generate_part_opportunities()
    if insert_part_opportunities(opportunities):
        # Then generate and insert quality entries
        entries = generate_quality_entries(250)
        insert_quality_entries(entries)

    print("✅ Quality data generation complete!")
