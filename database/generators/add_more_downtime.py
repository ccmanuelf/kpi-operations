#!/usr/bin/env python3
"""Add more downtime entries to reach 100+ target."""

import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = '/Users/mcampos.cerda/Documents/Programming/kpi-operations/database/kpi_platform.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get existing work orders
cursor.execute("SELECT work_order_id, client_id FROM WORK_ORDER")
work_orders = cursor.fetchall()

# Get current count
cursor.execute("SELECT COUNT(*) FROM DOWNTIME_ENTRY")
current_count = cursor.fetchone()[0]
print(f"Current downtime entries: {current_count}")

# Target 115 total
target = 115
to_add = target - current_count

DOWNTIME_REASONS = [
    "EQUIPMENT_FAILURE",
    "MATERIAL_SHORTAGE",
    "SETUP_CHANGEOVER",
    "QUALITY_HOLD",
    "MAINTENANCE",
    "OTHER"
]

DOWNTIME_DESCRIPTIONS = {
    "EQUIPMENT_FAILURE": ["Motor failure", "Sensor malfunction", "Belt replacement", "Needle break"],
    "MATERIAL_SHORTAGE": ["Fabric delay", "Thread stockout", "Button shortage"],
    "SETUP_CHANGEOVER": ["Style changeover", "Color change", "Size change"],
    "QUALITY_HOLD": ["Inspection required", "Rework pending", "Customer hold"],
    "MAINTENANCE": ["Scheduled maintenance", "Lubrication", "Calibration"],
    "OTHER": ["Power outage", "Training session", "Safety drill"]
}

DATA_START = datetime.now() - timedelta(days=90)
DATA_END = datetime.now()

added = 0
for i in range(to_add):
    wo_id, client_id = random.choice(work_orders)

    # Random date in range
    days_offset = random.randint(0, 85)
    shift_date = DATA_START + timedelta(days=days_offset)

    reason = random.choice(DOWNTIME_REASONS)
    description = random.choice(DOWNTIME_DESCRIPTIONS[reason])
    duration = random.randint(20, 200)

    dt_entry_id = f"DT-EXTRA-{current_count + i + 1:05d}"

    cursor.execute("""
        INSERT INTO DOWNTIME_ENTRY (
            downtime_entry_id, client_id, work_order_id, shift_date,
            downtime_reason, downtime_duration_minutes,
            root_cause_category, reported_by, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    """, (
        dt_entry_id, client_id, wo_id,
        shift_date.strftime('%Y-%m-%d'),
        reason, duration, reason, 1, description
    ))
    added += 1

conn.commit()

# Verify
cursor.execute("SELECT COUNT(*) FROM DOWNTIME_ENTRY")
final_count = cursor.fetchone()[0]
print(f"Added {added} downtime entries")
print(f"Final downtime entries: {final_count}")

conn.close()
