#!/usr/bin/env python3
"""
Generate realistic downtime sample data for KPI #8 (Availability)
Creates 100+ downtime entries across different reasons and durations
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

DOWNTIME_REASONS = {
    'EQUIPMENT_FAILURE': [
        'Sewing machine needle jammed',
        'Conveyor belt malfunction',
        'Hydraulic press failure',
        'CNC machine calibration error',
        'Power supply interruption'
    ],
    'MATERIAL_SHORTAGE': [
        'Fabric supplier delivery delayed',
        'Thread stock depleted',
        'Missing raw material batch',
        'Supplier quality issue - material rejected',
        'Inventory discrepancy - recount needed'
    ],
    'CHANGEOVER_SETUP': [
        'Switching product lines',
        'Tool change for new SKU',
        'Machine reconfiguration',
        'Color changeover - cleaning required',
        'Size adjustment setup'
    ],
    'LACK_OF_ORDERS': [
        'Customer order cancellation',
        'Seasonal demand reduction',
        'Waiting for customer confirmation',
        'Production schedule gap',
        'Inventory buildup - holding production'
    ],
    'MAINTENANCE_SCHEDULED': [
        'Preventive maintenance - weekly schedule',
        'Annual equipment calibration',
        'Safety inspection required',
        'Oil change and lubrication',
        'Filter replacement'
    ],
    'QC_HOLD': [
        'Quality inspection in progress',
        'Defect investigation ongoing',
        'Customer quality audit',
        'Pending material certification',
        'Compliance verification required'
    ],
    'MISSING_SPECIFICATION': [
        'Waiting for Engineering specs',
        'Customer approval needed for design change',
        'Technical drawing incomplete',
        'Material specification unclear',
        'Process documentation missing'
    ],
    'OTHER': [
        'Employee training session',
        'Safety drill',
        'Shift handover delay',
        'Computer system downtime',
        'Unexpected visitor tour'
    ]
}

# Realistic downtime durations by reason (minutes)
DURATION_RANGES = {
    'EQUIPMENT_FAILURE': (15, 180),      # 15 min to 3 hours
    'MATERIAL_SHORTAGE': (30, 240),      # 30 min to 4 hours
    'CHANGEOVER_SETUP': (20, 90),        # 20 min to 1.5 hours
    'LACK_OF_ORDERS': (60, 480),         # 1 hour to full shift
    'MAINTENANCE_SCHEDULED': (30, 120),  # 30 min to 2 hours
    'QC_HOLD': (45, 180),                # 45 min to 3 hours
    'MISSING_SPECIFICATION': (60, 360),  # 1 hour to 6 hours
    'OTHER': (10, 60)                    # 10 min to 1 hour
}


def generate_downtime_entries(count=150):
    """Generate realistic downtime entries"""
    entries = []
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    for i in range(count):
        # Random date in last 90 days
        random_days = random.randint(0, 90)
        shift_date = end_date - timedelta(days=random_days)

        # Select shift (1=Morning, 2=Afternoon, 3=Night)
        shift_id = random.randint(1, 3)

        # Select work order
        work_order = random.choice(WORK_ORDERS)
        client = random.choice(CLIENTS)

        # Select downtime reason
        reason = random.choice(list(DOWNTIME_REASONS.keys()))
        reason_detail = random.choice(DOWNTIME_REASONS[reason])

        # Generate duration based on reason
        min_duration, max_duration = DURATION_RANGES[reason]
        duration = random.randint(min_duration, max_duration)

        # Generate start time based on shift
        if shift_id == 1:  # Morning
            hour = random.randint(7, 13)
        elif shift_id == 2:  # Afternoon
            hour = random.randint(14, 20)
        else:  # Night
            hour = random.randint(22, 23) if random.random() > 0.5 else random.randint(0, 5)

        minute = random.randint(0, 59)
        start_time = f"{hour:02d}:{minute:02d}:00"

        # Responsible person and reporter (users 2-4 from seed data)
        responsible_person = random.choice([2, 3, 4]) if random.random() > 0.3 else None
        reported_by = random.choice([2, 3, 4])

        # Most downtime is resolved
        is_resolved = 1 if random.random() > 0.05 else 0

        # Resolution notes (only if resolved)
        resolution_notes = None
        if is_resolved:
            resolutions = [
                'Machine repaired by maintenance',
                'Material arrived and production resumed',
                'Setup completed successfully',
                'Engineering provided specification',
                'QC inspection completed - cleared to proceed',
                'Scheduled maintenance completed',
                'Issue resolved, back to normal operation'
            ]
            resolution_notes = random.choice(resolutions)

        # Calculate impact on WIP (assuming average 3 employees affected)
        employees_affected = random.randint(2, 5)
        impact_hours = round((duration / 60) * employees_affected, 2)

        entry = {
            'work_order_number': work_order,
            'client_name': client,
            'shift_date': shift_date,
            'shift_id': shift_id,
            'downtime_reason': reason,
            'downtime_reason_detail': reason_detail,
            'downtime_duration_minutes': duration,
            'downtime_start_time': start_time,
            'responsible_person_id': responsible_person,
            'reported_by_user_id': reported_by,
            'is_resolved': is_resolved,
            'resolution_notes': resolution_notes,
            'impact_on_wip_hours': impact_hours
        }

        entries.append(entry)

    return entries


def insert_downtime_entries(entries):
    """Insert downtime entries into database"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO downtime_entry (
                work_order_number, client_name, shift_date, shift_id,
                downtime_reason, downtime_reason_detail, downtime_duration_minutes,
                downtime_start_time, responsible_person_id, reported_by_user_id,
                is_resolved, resolution_notes, impact_on_wip_hours
            ) VALUES (
                %(work_order_number)s, %(client_name)s, %(shift_date)s, %(shift_id)s,
                %(downtime_reason)s, %(downtime_reason_detail)s, %(downtime_duration_minutes)s,
                %(downtime_start_time)s, %(responsible_person_id)s, %(reported_by_user_id)s,
                %(is_resolved)s, %(resolution_notes)s, %(impact_on_wip_hours)s
            )
        """

        cursor.executemany(insert_query, entries)
        connection.commit()

        print(f"✅ Successfully inserted {cursor.rowcount} downtime entries")

        # Statistics
        total_downtime_hours = sum(e['downtime_duration_minutes'] / 60 for e in entries)
        avg_duration = total_downtime_hours / len(entries)

        print(f"\n📊 Statistics:")
        print(f"   Total downtime hours: {total_downtime_hours:.2f}")
        print(f"   Average downtime per entry: {avg_duration:.2f} hours")

        cursor.close()
        connection.close()

    except Error as e:
        print(f"❌ Database error: {e}")


if __name__ == "__main__":
    print("🔧 Generating downtime sample data...")
    entries = generate_downtime_entries(150)
    insert_downtime_entries(entries)
    print("✅ Downtime data generation complete!")
