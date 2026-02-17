#!/usr/bin/env python3
"""
Generate realistic hold/resume sample data for KPI #1 (WIP Aging)
Creates 50+ hold entries with varying durations and statuses
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

HOLD_REASONS = {
    'MATERIAL_INSPECTION': [
        'Pending fabric color match approval',
        'Material quality verification in progress',
        'Supplier certification review',
        'Chemical composition test pending',
        'Dimensional stability test ongoing'
    ],
    'QUALITY_ISSUE': [
        'QC found stitching defects, rework required',
        'Color inconsistency detected',
        'Sizing out of specification',
        'Surface finish quality concerns',
        'Structural integrity issues identified'
    ],
    'ENGINEERING_REVIEW': [
        'Waiting for customer approval on design change',
        'Technical specification clarification needed',
        'Dimensional tolerance review',
        'Process validation required',
        'Design modification pending'
    ],
    'CUSTOMER_REQUEST': [
        'Customer requested hold for inventory review',
        'Waiting for customer payment confirmation',
        'Customer scheduling change',
        'Order modification in progress',
        'Customer quality audit scheduled'
    ],
    'MISSING_SPECIFICATION': [
        'Technical drawing incomplete',
        'Material specification not finalized',
        'Process parameters undefined',
        'Quality acceptance criteria missing',
        'Packaging requirements unclear'
    ],
    'EQUIPMENT_UNAVAILABLE': [
        'Required machinery under maintenance',
        'Specialized tooling not available',
        'Test equipment calibration due',
        'Production line occupied with priority order',
        'Facility capacity constraint'
    ],
    'CAPACITY_CONSTRAINT': [
        'Production schedule full - delayed start',
        'Resource allocation pending',
        'Waiting for line availability',
        'Shift coverage issue',
        'Workforce shortage temporary hold'
    ],
    'OTHER': [
        'Seasonal production pause',
        'Inventory reconciliation hold',
        'System upgrade in progress',
        'Document control freeze',
        'Regulatory compliance review'
    ]
}


def generate_hold_entries(count=80):
    """Generate realistic hold/resume entries"""
    entries = []
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    for i in range(count):
        # Random hold date in last 90 days
        random_days = random.randint(0, 85)
        hold_date = end_date - timedelta(days=random_days)

        # Select work order
        work_order = random.choice(WORK_ORDERS)
        client = random.choice(CLIENTS)

        # Select hold reason
        reason = random.choice(list(HOLD_REASONS.keys()))
        reason_detail = random.choice(HOLD_REASONS[reason])

        # Generate hold time
        hour = random.randint(7, 17)
        minute = random.randint(0, 59)
        hold_time = f"{hour:02d}:{minute:02d}:00"

        # Approved by (supervisor - user 2)
        approved_by = 2

        # Determine hold status (70% resumed, 25% still on hold, 5% cancelled)
        status_roll = random.random()
        if status_roll < 0.70:
            status = 'RESUMED'
        elif status_roll < 0.95:
            status = 'ON_HOLD'
        else:
            status = 'CANCELLED'

        # Resume date and duration (only if resumed)
        resume_date = None
        resume_time = None
        resume_approved_by = None
        hold_duration = None
        resume_notes = None

        if status == 'RESUMED':
            # Hold duration between 1-14 days for most, some longer
            if random.random() < 0.8:
                duration_days = random.randint(1, 14)
            else:
                duration_days = random.randint(15, 45)

            resume_date = hold_date + timedelta(days=duration_days)

            # Ensure resume date is not in future
            if resume_date > end_date:
                resume_date = end_date

            resume_hour = random.randint(7, 17)
            resume_minute = random.randint(0, 59)
            resume_time = f"{resume_hour:02d}:{resume_minute:02d}:00"

            resume_approved_by = 2  # Same supervisor

            # Calculate duration in hours
            day_diff = (resume_date - hold_date).days
            # Add hour difference
            hold_hour = int(hold_time.split(':')[0])
            resume_hour_int = int(resume_time.split(':')[0])
            hour_diff = resume_hour_int - hold_hour

            hold_duration = round((day_diff * 24) + hour_diff, 2)

            resume_notes = random.choice([
                'Material inspection completed - approved to proceed',
                'Quality issues resolved through rework',
                'Engineering approved design with modifications',
                'Customer confirmation received',
                'Equipment now available - production resumed',
                'Specification provided - cleared to manufacture'
            ])

        # Hold notes
        if status == 'ON_HOLD':
            notes = f"Currently on hold - {reason_detail}. Expected resolution pending."
        elif status == 'CANCELLED':
            notes = f"Hold cancelled - {reason_detail}. Order modification or cancellation."
        else:
            notes = resume_notes

        entry = {
            'work_order_number': work_order,
            'client_name': client,
            'hold_status': status,
            'hold_date': hold_date,
            'hold_time': hold_time,
            'hold_reason': reason,
            'hold_reason_detail': reason_detail,
            'hold_approved_by_user_id': approved_by,
            'resume_date': resume_date,
            'resume_time': resume_time,
            'resume_approved_by_user_id': resume_approved_by,
            'total_hold_duration_hours': hold_duration,
            'hold_notes': notes
        }

        entries.append(entry)

    return entries


def insert_hold_entries(entries):
    """Insert hold entries into database"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO hold_entry (
                work_order_number, client_name, hold_status, hold_date, hold_time,
                hold_reason, hold_reason_detail, hold_approved_by_user_id,
                resume_date, resume_time, resume_approved_by_user_id,
                total_hold_duration_hours, hold_notes
            ) VALUES (
                %(work_order_number)s, %(client_name)s, %(hold_status)s, %(hold_date)s, %(hold_time)s,
                %(hold_reason)s, %(hold_reason_detail)s, %(hold_approved_by_user_id)s,
                %(resume_date)s, %(resume_time)s, %(resume_approved_by_user_id)s,
                %(total_hold_duration_hours)s, %(hold_notes)s
            )
        """

        cursor.executemany(insert_query, entries)
        connection.commit()

        print(f"✅ Successfully inserted {cursor.rowcount} hold entries")

        # Statistics
        resumed = sum(1 for e in entries if e['hold_status'] == 'RESUMED')
        on_hold = sum(1 for e in entries if e['hold_status'] == 'ON_HOLD')
        cancelled = sum(1 for e in entries if e['hold_status'] == 'CANCELLED')

        total_hold_hours = sum(e['total_hold_duration_hours'] for e in entries if e['total_hold_duration_hours'])
        avg_duration = total_hold_hours / resumed if resumed > 0 else 0

        print(f"\n📊 Statistics:")
        print(f"   Resumed: {resumed} ({resumed/len(entries)*100:.1f}%)")
        print(f"   Still on hold: {on_hold} ({on_hold/len(entries)*100:.1f}%)")
        print(f"   Cancelled: {cancelled} ({cancelled/len(entries)*100:.1f}%)")
        print(f"   Total hold hours (resumed items): {total_hold_hours:.2f}")
        print(f"   Average hold duration: {avg_duration:.2f} hours ({avg_duration/24:.1f} days)")

        cursor.close()
        connection.close()

    except Error as e:
        print(f"❌ Database error: {e}")


if __name__ == "__main__":
    print("⏸️  Generating hold/resume sample data...")
    entries = generate_hold_entries(80)
    insert_hold_entries(entries)
    print("✅ Hold data generation complete!")
