#!/usr/bin/env python3
"""
KPI Operations Platform - Comprehensive Demo Data Generator
Phase 10.5: Creates demonstration-ready sample data for all modules

This generator creates realistic scenarios for platform demonstrations:
- OTD at-risk work orders
- Quality alerts (low FPY)
- Capacity alerts (overload scenarios)
- Floating pool coverage workflows
- Hold approval workflows
- Active alerts for dashboard demonstration

Author: KPI Operations Platform
Version: 3.1.0 (Phase 10.5 - Schema Aligned)
Date: 2026-01-26
"""

import os
import sys
import random
import sqlite3
import json
import uuid
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(PROJECT_ROOT, 'database', 'kpi_platform.db')

# Seed for reproducible data
RANDOM_SEED = 2026

# Date range - 90 days of historical data
DATA_END_DATE = datetime.now()
DATA_START_DATE = DATA_END_DATE - timedelta(days=90)

# ============================================================================
# Data Templates
# ============================================================================

CLIENTS = [
    {
        "client_id": "NOVALINK-MTY",
        "client_name": "Novalink Matamoros",
        "client_type": "Piece Rate",
        "timezone": "America/Mexico_City",
        "efficiency_target": 85.0,
        "otd_target": 95.0,
        "fpy_target": 98.0
    },
    {
        "client_id": "TEXTIL-NORTE",
        "client_name": "Textiles del Norte SA",
        "client_type": "Piece Rate",
        "timezone": "America/Mexico_City",
        "efficiency_target": 82.0,
        "otd_target": 92.0,
        "fpy_target": 96.0
    },
    {
        "client_id": "CONFEC-DELTA",
        "client_name": "Confecciones Delta",
        "client_type": "Hourly Rate",
        "timezone": "America/Mexico_City",
        "efficiency_target": 80.0,
        "otd_target": 90.0,
        "fpy_target": 95.0
    },
    {
        "client_id": "MAQUILA-PRIME",
        "client_name": "Maquila Prime Industries",
        "client_type": "Hybrid",
        "timezone": "America/Mexico_City",
        "efficiency_target": 88.0,
        "otd_target": 98.0,
        "fpy_target": 99.0
    },
    {
        "client_id": "GARMENT-PLUS",
        "client_name": "Garment Plus LLC",
        "client_type": "Piece Rate",
        "timezone": "America/Chicago",
        "efficiency_target": 83.0,
        "otd_target": 94.0,
        "fpy_target": 97.0
    }
]

SHIFTS = [
    {"shift_id": 1, "shift_name": "1st Shift (Morning)", "start_time": "06:00:00", "end_time": "14:00:00"},
    {"shift_id": 2, "shift_name": "2nd Shift (Afternoon)", "start_time": "14:00:00", "end_time": "22:00:00"},
    {"shift_id": 3, "shift_name": "3rd Shift (Night)", "start_time": "22:00:00", "end_time": "06:00:00"}
]

PRODUCTS = [
    {"product_code": "POLO-STD", "product_name": "Standard Polo Shirt", "ideal_cycle_time": 0.35},
    {"product_code": "POLO-PRE", "product_name": "Premium Polo Shirt", "ideal_cycle_time": 0.45},
    {"product_code": "TSHIRT-BAS", "product_name": "Basic T-Shirt", "ideal_cycle_time": 0.25},
    {"product_code": "JEANS-STD", "product_name": "Standard Jeans", "ideal_cycle_time": 0.60},
    {"product_code": "JEANS-PRE", "product_name": "Premium Jeans", "ideal_cycle_time": 0.75},
    {"product_code": "JACKET-LT", "product_name": "Light Jacket", "ideal_cycle_time": 0.90},
    {"product_code": "JACKET-HV", "product_name": "Heavy Jacket", "ideal_cycle_time": 1.20},
    {"product_code": "DRESS-CAS", "product_name": "Casual Dress", "ideal_cycle_time": 0.55},
    {"product_code": "UNIFORM-IND", "product_name": "Industrial Uniform", "ideal_cycle_time": 0.40},
    {"product_code": "SCRUBS-MED", "product_name": "Medical Scrubs Set", "ideal_cycle_time": 0.50}
]

EMPLOYEE_FIRST_NAMES = [
    "Maria", "Jose", "Juan", "Ana", "Carlos", "Laura", "Miguel", "Rosa", "Luis", "Carmen",
    "Pedro", "Sofia", "Diego", "Elena", "Fernando", "Patricia", "Roberto", "Guadalupe", "Ricardo", "Martha",
    "Alejandro", "Veronica", "Francisco", "Adriana", "Jorge", "Monica", "Antonio", "Claudia", "Eduardo", "Sandra"
]

EMPLOYEE_LAST_NAMES = [
    "Garcia", "Rodriguez", "Martinez", "Lopez", "Hernandez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres",
    "Flores", "Rivera", "Gomez", "Diaz", "Reyes", "Cruz", "Morales", "Ortiz", "Gutierrez", "Chavez"
]

HOLD_REASONS = [
    ("QUALITY_ISSUE", "Quality Issue - Requires Rework"),
    ("MATERIAL_SHORTAGE", "Material Shortage"),
    ("CUSTOMER_CHANGE", "Customer Design Change Request"),
    ("EQUIPMENT_DOWN", "Equipment Down for Maintenance"),
    ("SPEC_CLARIFICATION", "Specification Clarification Needed"),
    ("CAPACITY_CONSTRAINT", "Capacity Constraint")
]

DOWNTIME_CATEGORIES = [
    ("EQUIPMENT_FAILURE", "Equipment Failure"),
    ("MATERIAL_SHORTAGE", "Material Shortage"),
    ("SETUP_CHANGEOVER", "Setup/Changeover"),
    ("QUALITY_HOLD", "Quality Hold"),
    ("MAINTENANCE", "Preventive Maintenance"),
    ("POWER_OUTAGE", "Power Outage"),
    ("OTHER", "Other")
]

DEFECT_TYPES = [
    ("STITCH", "Stitching Defect", "Improper or broken stitches"),
    ("FABRIC", "Fabric Defect", "Flaws in fabric material"),
    ("MEASURE", "Measurement Error", "Incorrect dimensions"),
    ("COLOR", "Color Variation", "Color shade mismatch"),
    ("HOLE", "Hole/Tear", "Physical damage to material"),
    ("STAIN", "Stain/Mark", "Unwanted marks or stains"),
    ("ALIGN", "Misalignment", "Pattern or component misalignment"),
    ("SEAM", "Seam Issue", "Seam puckering or opening")
]


class DemoDataGenerator:
    """Generates comprehensive demonstration data for KPI platform."""

    def __init__(self, db_path: str, seed: int = RANDOM_SEED):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        random.seed(seed)

        # Track generated IDs for relationships
        self.client_ids = []
        self.employee_map = {}  # employee_code -> employee_id (integer)
        self.floating_pool_map = {}  # employee_code -> employee_id (integer)
        self.product_map = {}  # product_code -> product_id (integer)
        self.work_order_data = []
        self.user_map = {}  # user_id_str -> user_id (integer or string depending on schema)

    def connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        print(f"Connected to database: {self.db_path}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

    def clear_existing_data(self):
        """Clear existing data to start fresh."""
        print("\n🗑️  Clearing existing data...")

        tables_to_clear = [
            "ALERT_HISTORY", "ALERT_CONFIG", "ALERT",
            "DEFECT_DETAIL", "HOLD_ENTRY", "DOWNTIME_ENTRY",
            "COVERAGE_ENTRY", "SHIFT_COVERAGE", "ATTENDANCE_ENTRY",
            "QUALITY_ENTRY", "PRODUCTION_ENTRY", "JOB",
            "PART_OPPORTUNITIES", "WORK_ORDER", "FLOATING_POOL",
            "EMPLOYEE", "PRODUCT", "SHIFT", "CLIENT",
            "KPI_THRESHOLD", "DEFECT_TYPE_CATALOG"
        ]

        for table in tables_to_clear:
            try:
                self.cursor.execute(f"DELETE FROM {table}")
                print(f"   ✓ Cleared {table}")
            except sqlite3.OperationalError as e:
                print(f"   ⚠ Could not clear {table}: {e}")

        self.conn.commit()

    def generate_users(self):
        """Generate system users."""
        print("\n👤 Generating Users...")

        # Check actual USER table schema
        self.cursor.execute("PRAGMA table_info(USER)")
        columns = {row[1]: row[2] for row in self.cursor.fetchall()}

        users = [
            ("SYSTEM", "system", "system@kpi.local", "System Administrator", "SYSTEM"),
            ("ADMIN-001", "admin", "admin@novalink.mx", "Administrator", "ADMIN"),
            ("SUPER-001", "supervisor1", "supervisor1@novalink.mx", "Maria Garcia (Supervisor)", "SUPERVISOR"),
            ("SUPER-002", "supervisor2", "supervisor2@novalink.mx", "Juan Rodriguez (Supervisor)", "SUPERVISOR"),
            ("LEADER-001", "leader1", "leader1@novalink.mx", "Carlos Martinez (Team Lead)", "LEADER"),
            ("LEADER-002", "leader2", "leader2@novalink.mx", "Ana Lopez (Team Lead)", "LEADER"),
            ("OP-001", "operator1", "operator1@novalink.mx", "Pedro Hernandez (Operator)", "OPERATOR")
        ]

        for user_id, username, email, full_name, role in users:
            try:
                self.cursor.execute("""
                    INSERT OR REPLACE INTO USER (user_id, username, email, full_name, role, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, datetime('now'))
                """, (user_id, username, email, full_name, role))
                self.user_map[user_id] = user_id
            except sqlite3.IntegrityError:
                pass

        self.conn.commit()
        print(f"   ✓ Created {len(users)} users")

    def generate_clients(self):
        """Generate client records."""
        print("\n🏢 Generating Clients...")

        for client in CLIENTS:
            try:
                self.cursor.execute("""
                    INSERT INTO CLIENT (client_id, client_name, client_type, timezone, is_active, created_at)
                    VALUES (?, ?, ?, ?, 1, datetime('now'))
                """, (client["client_id"], client["client_name"], client["client_type"], client["timezone"]))
                self.client_ids.append(client["client_id"])
                print(f"   ✓ {client['client_id']}: {client['client_name']}")
            except sqlite3.IntegrityError:
                self.client_ids.append(client["client_id"])

        self.conn.commit()

    def generate_shifts(self):
        """Generate shift records."""
        print("\n⏰ Generating Shifts...")

        for shift in SHIFTS:
            try:
                self.cursor.execute("""
                    INSERT INTO SHIFT (shift_id, shift_name, start_time, end_time, is_active, created_at)
                    VALUES (?, ?, ?, ?, 1, datetime('now'))
                """, (shift["shift_id"], shift["shift_name"], shift["start_time"], shift["end_time"]))
                print(f"   ✓ {shift['shift_name']}")
            except sqlite3.IntegrityError:
                pass

        self.conn.commit()

    def generate_products(self):
        """Generate product records."""
        print("\n📦 Generating Products...")

        for product in PRODUCTS:
            try:
                self.cursor.execute("""
                    INSERT INTO PRODUCT (product_code, product_name, ideal_cycle_time, unit_of_measure, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, 'pieces', 1, datetime('now'), datetime('now'))
                """, (product["product_code"], product["product_name"], product["ideal_cycle_time"]))

                # Get the auto-generated product_id
                self.cursor.execute("SELECT product_id FROM PRODUCT WHERE product_code = ?", (product["product_code"],))
                row = self.cursor.fetchone()
                if row:
                    self.product_map[product["product_code"]] = row[0]
                print(f"   ✓ {product['product_code']}: {product['product_name']}")
            except sqlite3.IntegrityError:
                # Already exists, get the ID
                self.cursor.execute("SELECT product_id FROM PRODUCT WHERE product_code = ?", (product["product_code"],))
                row = self.cursor.fetchone()
                if row:
                    self.product_map[product["product_code"]] = row[0]

        self.conn.commit()

    def generate_defect_types(self):
        """Generate defect type catalog."""
        print("\n🔍 Generating Defect Type Catalog...")

        count = 0
        for client_id in self.client_ids:
            for defect_code, defect_name, description in DEFECT_TYPES:
                defect_id = f"DEF-{client_id[:4]}-{defect_code}"
                try:
                    self.cursor.execute("""
                        INSERT INTO DEFECT_TYPE_CATALOG (
                            defect_type_id, client_id, defect_code, defect_name, description,
                            severity_default, is_active, created_at
                        ) VALUES (?, ?, ?, ?, ?, 'MINOR', 1, datetime('now'))
                    """, (defect_id, client_id, defect_code, defect_name, description))
                    count += 1
                except sqlite3.IntegrityError:
                    pass

        self.conn.commit()
        print(f"   ✓ Created {count} defect type entries")

    def generate_employees(self):
        """Generate employee records - 80 regular + 20 floating pool."""
        print("\n👥 Generating Employees...")

        emp_count = 0

        # Regular employees: 16 per client
        for client_id in self.client_ids:
            for i in range(16):
                emp_code = f"EMP-{client_id[:4]}-{i+1:03d}"
                first_name = random.choice(EMPLOYEE_FIRST_NAMES)
                last_name = random.choice(EMPLOYEE_LAST_NAMES)
                emp_name = f"{first_name} {last_name}"

                try:
                    self.cursor.execute("""
                        INSERT INTO EMPLOYEE (employee_code, employee_name, client_id_assigned, is_floating_pool, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, 0, 1, datetime('now'), datetime('now'))
                    """, (emp_code, emp_name, client_id))

                    # Get the auto-generated employee_id
                    self.cursor.execute("SELECT employee_id FROM EMPLOYEE WHERE employee_code = ?", (emp_code,))
                    row = self.cursor.fetchone()
                    if row:
                        self.employee_map[emp_code] = {"id": row[0], "client_id": client_id}
                    emp_count += 1
                except sqlite3.IntegrityError:
                    pass

        # Floating pool: 20 employees
        for i in range(20):
            emp_code = f"EMP-FLOAT-{i+1:03d}"
            first_name = random.choice(EMPLOYEE_FIRST_NAMES)
            last_name = random.choice(EMPLOYEE_LAST_NAMES)
            emp_name = f"{first_name} {last_name}"

            try:
                self.cursor.execute("""
                    INSERT INTO EMPLOYEE (employee_code, employee_name, client_id_assigned, is_floating_pool, is_active, created_at, updated_at)
                    VALUES (?, ?, NULL, 1, 1, datetime('now'), datetime('now'))
                """, (emp_code, emp_name))

                # Get the auto-generated employee_id
                self.cursor.execute("SELECT employee_id FROM EMPLOYEE WHERE employee_code = ?", (emp_code,))
                row = self.cursor.fetchone()
                if row:
                    self.floating_pool_map[emp_code] = row[0]
                emp_count += 1
            except sqlite3.IntegrityError:
                pass

        self.conn.commit()
        print(f"   ✓ Created {emp_count} employees ({len(self.employee_map)} regular + {len(self.floating_pool_map)} floating pool)")

    def generate_work_orders(self):
        """Generate work orders with various statuses for demo scenarios."""
        print("\n📋 Generating Work Orders...")

        wo_count = 0
        statuses = {
            "COMPLETED": 0.5,
            "IN_PROGRESS": 0.25,
            "AT_RISK": 0.15,
            "ON_HOLD": 0.10
        }

        for client_idx, client_id in enumerate(self.client_ids):
            for wo_idx in range(10):
                wo_id = f"WO-{client_id[:4]}-{wo_idx+1:04d}"
                product = random.choice(PRODUCTS)

                # Determine status
                rand_status = random.random()
                cumulative = 0
                status = "COMPLETED"
                for s, prob in statuses.items():
                    cumulative += prob
                    if rand_status <= cumulative:
                        status = s
                        break

                # Map AT_RISK to valid enum value
                db_status = "IN_PROGRESS" if status == "AT_RISK" else status

                # Calculate dates
                if status == "COMPLETED":
                    start_date = DATA_START_DATE + timedelta(days=random.randint(0, 60))
                    ship_date = start_date + timedelta(days=random.randint(14, 28))
                    actual_delivery = ship_date + timedelta(days=random.randint(-2, 2))
                elif status in ["IN_PROGRESS", "AT_RISK"]:
                    start_date = DATA_END_DATE - timedelta(days=random.randint(7, 21))
                    ship_date = DATA_END_DATE + timedelta(days=random.randint(1, 14) if status == "AT_RISK" else random.randint(7, 21))
                    actual_delivery = None
                else:  # ON_HOLD
                    start_date = DATA_END_DATE - timedelta(days=random.randint(10, 20))
                    ship_date = DATA_END_DATE + timedelta(days=random.randint(14, 28))
                    actual_delivery = None

                planned_qty = random.randint(500, 2000)

                # Calculate actual quantity for progress tracking
                if status == "COMPLETED":
                    actual_qty = int(planned_qty * random.uniform(0.95, 1.02))
                elif status == "AT_RISK":
                    actual_qty = int(planned_qty * random.uniform(0.3, 0.5))  # Behind schedule
                elif status == "ON_HOLD":
                    actual_qty = int(planned_qty * random.uniform(0.2, 0.4))
                else:
                    actual_qty = int(planned_qty * random.uniform(0.5, 0.8))

                try:
                    self.cursor.execute("""
                        INSERT INTO WORK_ORDER (
                            work_order_id, client_id, style_model, planned_quantity, actual_quantity,
                            actual_start_date, planned_ship_date, actual_delivery_date,
                            ideal_cycle_time, status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        wo_id, client_id, product["product_code"], planned_qty, actual_qty,
                        start_date.strftime('%Y-%m-%d'), ship_date.strftime('%Y-%m-%d'),
                        actual_delivery.strftime('%Y-%m-%d') if actual_delivery else None,
                        product["ideal_cycle_time"], db_status
                    ))
                    self.work_order_data.append({
                        "id": wo_id,
                        "client_id": client_id,
                        "product": product,
                        "start_date": start_date,
                        "ship_date": ship_date,
                        "planned_qty": planned_qty,
                        "actual_qty": actual_qty,
                        "status": status,
                        "db_status": db_status
                    })
                    wo_count += 1
                except sqlite3.IntegrityError as e:
                    print(f"   ⚠ Error creating {wo_id}: {e}")

        self.conn.commit()

        # Count by status
        status_counts = {}
        for wo in self.work_order_data:
            status_counts[wo["status"]] = status_counts.get(wo["status"], 0) + 1

        print(f"   ✓ Created {wo_count} work orders:")
        for status, count in status_counts.items():
            print(f"      - {status}: {count}")

    def generate_jobs(self):
        """Generate JOB records (line items/operations within work orders) for RTY calculation."""
        print("\n🔧 Generating Jobs (Line Items for RTY)...")

        job_count = 0

        # Define typical garment manufacturing operations
        operations = [
            ("CUT", "Cutting", 1),
            ("SEW", "Sewing", 2),
            ("TRIM", "Trimming", 3),
            ("PRESS", "Pressing", 4),
            ("QC", "Quality Check", 5),
            ("PACK", "Packing", 6)
        ]

        for wo in self.work_order_data:
            # Each work order has 3-6 operations (jobs)
            num_ops = random.randint(3, 6)
            selected_ops = operations[:num_ops]

            for op_code, op_name, seq in selected_ops:
                job_id = f"JOB-{wo['id']}-{op_code}"

                # Calculate quantities based on work order progress
                planned_qty = wo["planned_qty"]

                if wo["status"] == "COMPLETED":
                    completed_qty = int(planned_qty * random.uniform(0.95, 1.02))
                    is_completed = 1
                elif wo["status"] in ["IN_PROGRESS", "AT_RISK"]:
                    # Later operations have less completion
                    completion_factor = max(0.2, 1 - (seq * 0.15))
                    completed_qty = int(wo["actual_qty"] * completion_factor)
                    is_completed = 0
                else:  # ON_HOLD
                    completed_qty = int(wo["actual_qty"] * 0.3)
                    is_completed = 0

                # Some scrap at each operation (RTY calculation basis)
                qty_scrapped = int(completed_qty * random.uniform(0.005, 0.025))

                # Hours calculation
                planned_hours = planned_qty * wo["product"]["ideal_cycle_time"] / 60
                actual_hours = completed_qty * wo["product"]["ideal_cycle_time"] / 60 * random.uniform(0.9, 1.2)

                try:
                    self.cursor.execute("""
                        INSERT INTO JOB (
                            job_id, work_order_id, client_id_fk,
                            operation_name, operation_code, sequence_number,
                            part_number, part_description,
                            planned_quantity, completed_quantity, quantity_scrapped,
                            planned_hours, actual_hours, is_completed,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        job_id, wo["id"], wo["client_id"],
                        op_name, op_code, seq,
                        wo["product"]["product_code"],
                        f"{op_name} operation for {wo['product']['product_name']}",
                        planned_qty, completed_qty, qty_scrapped,
                        round(planned_hours, 2), round(actual_hours, 2), is_completed
                    ))
                    job_count += 1
                except sqlite3.IntegrityError as e:
                    print(f"      Warning: Could not insert job {job_id}: {e}")

        self.conn.commit()
        print(f"   ✓ Created {job_count} jobs (operations)")

    def generate_part_opportunities(self):
        """Generate PART_OPPORTUNITIES for accurate DPMO calculation."""
        print("\n🎯 Generating Part Opportunities (for DPMO)...")

        part_count = 0

        # Defect opportunities per product type (based on complexity)
        # Simple items = fewer opportunities, complex items = more
        product_opportunities = {
            "POLO-STD": (15, "Standard polo - collar, buttons, seams"),
            "POLO-PRE": (22, "Premium polo - additional stitching, embroidery"),
            "TSHIRT-BAS": (8, "Basic t-shirt - minimal opportunities"),
            "JEANS-STD": (35, "Standard jeans - rivets, zipper, pockets, seams"),
            "JEANS-PRE": (48, "Premium jeans - detailed stitching, special finishes"),
            "JACKET-LT": (40, "Light jacket - zipper, pockets, lining"),
            "JACKET-HV": (65, "Heavy jacket - complex construction, multiple layers"),
            "DRESS-CAS": (25, "Casual dress - moderate complexity"),
            "UNIFORM-IND": (30, "Industrial uniform - reinforced areas, pockets"),
            "SCRUBS-MED": (18, "Medical scrubs - simple design, functional")
        }

        # Create opportunities for each client's products
        for client_id in ["NOVALINK-MTY", "TEXTIL-NORTE", "CONFEC-DELTA", "MAQUILA-PRIME", "GARMENT-PLUS"]:
            for product_code, (opportunities, description) in product_opportunities.items():
                # Slight variation per client based on their quality standards
                client_modifier = random.uniform(0.9, 1.1)
                adjusted_opportunities = int(opportunities * client_modifier)

                try:
                    self.cursor.execute("""
                        INSERT INTO PART_OPPORTUNITIES (
                            part_number, client_id_fk, opportunities_per_unit,
                            part_description, part_category, notes
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        f"{product_code}-{client_id[:4]}",  # Unique per client
                        client_id,
                        adjusted_opportunities,
                        description,
                        "Garment" if "SHIRT" in product_code or "POLO" in product_code else "Apparel",
                        f"Defect opportunities for {product_code} at {client_id}"
                    ))
                    part_count += 1
                except sqlite3.IntegrityError as e:
                    print(f"      Warning: Could not insert part opportunity: {e}")

        self.conn.commit()
        print(f"   ✓ Created {part_count} part opportunity configurations")

    def generate_production_entries(self):
        """Generate production entries with realistic KPI variations."""
        print("\n🏭 Generating Production Entries...")

        prod_count = 0
        system_user_id = 1  # Default user ID

        # Get SYSTEM user ID
        self.cursor.execute("SELECT user_id FROM USER WHERE username = 'system' LIMIT 1")
        row = self.cursor.fetchone()
        if row:
            system_user_id = row[0]

        for wo in self.work_order_data:
            if wo["status"] == "COMPLETED":
                days_to_generate = min((wo["ship_date"] - wo["start_date"]).days, 25)
            else:
                days_to_generate = min((DATA_END_DATE - wo["start_date"]).days, 20)

            if days_to_generate <= 0:
                continue

            product_id = self.product_map.get(wo["product"]["product_code"])
            if not product_id:
                continue

            remaining_qty = wo["actual_qty"]
            current_date = wo["start_date"]

            for day in range(days_to_generate):
                if remaining_qty <= 0:
                    break

                prod_date = current_date + timedelta(days=day)

                # Skip some weekends
                if prod_date.weekday() >= 5 and random.random() > 0.3:
                    continue

                daily_target = wo["actual_qty"] / max(days_to_generate, 1)
                daily_actual = int(daily_target * random.uniform(0.85, 1.15))
                daily_actual = min(daily_actual, remaining_qty)

                if daily_actual <= 0:
                    continue

                remaining_qty -= daily_actual

                run_time = random.uniform(7.0, 8.5)
                employees = random.randint(4, 8)
                defects = int(daily_actual * random.uniform(0.01, 0.04))
                scrap = int(defects * random.uniform(0.1, 0.3))

                ideal_cycle = wo["product"]["ideal_cycle_time"]
                actual_cycle = run_time / daily_actual if daily_actual > 0 else 0
                efficiency = round(random.uniform(0.75, 0.95), 4)
                quality_rate = round((daily_actual - defects) / daily_actual if daily_actual > 0 else 1.0, 4)
                performance = round(min(ideal_cycle / actual_cycle if actual_cycle > 0 else 0, 1.2), 4)

                prod_id = f"PE-{wo['id']}-{day+1:03d}"

                try:
                    self.cursor.execute("""
                        INSERT INTO PRODUCTION_ENTRY (
                            production_entry_id, client_id, product_id, shift_id,
                            work_order_id, production_date, shift_date,
                            units_produced, run_time_hours, employees_assigned,
                            defect_count, scrap_count, ideal_cycle_time, actual_cycle_time,
                            efficiency_percentage, performance_percentage, quality_rate,
                            entered_by, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        prod_id, wo["client_id"], product_id,
                        random.randint(1, 3), wo["id"],
                        prod_date.strftime('%Y-%m-%d'), prod_date.strftime('%Y-%m-%d'),
                        daily_actual, run_time, employees,
                        defects, scrap, ideal_cycle, actual_cycle,
                        efficiency, performance, quality_rate,
                        system_user_id
                    ))
                    prod_count += 1
                except sqlite3.IntegrityError:
                    pass

        self.conn.commit()
        print(f"   ✓ Created {prod_count} production entries")

    def generate_quality_entries(self):
        """Generate quality entries with some low-FPY scenarios for alerts."""
        print("\n✅ Generating Quality Entries...")

        quality_count = 0

        for wo in self.work_order_data:
            num_entries = random.randint(1, 3)

            for q_idx in range(num_entries):
                q_date = wo["start_date"] + timedelta(days=random.randint(0, 20))
                if q_date > DATA_END_DATE:
                    q_date = DATA_END_DATE

                units_inspected = random.randint(100, 500)

                # Some entries will have low FPY
                if random.random() < 0.15:
                    fpy_rate = random.uniform(0.80, 0.92)
                else:
                    fpy_rate = random.uniform(0.94, 0.99)

                units_passed = int(units_inspected * fpy_rate)
                units_defective = units_inspected - units_passed
                total_defects = units_defective + random.randint(0, int(units_defective * 0.3))

                # Split defective units into: rework (quick fix), repair (resource-intensive), scrap
                # Rework: ~50-60% of defective (minor issues, fixed on line)
                # Repair: ~20-30% of defective (requires off-line repair station)
                # Scrap: remaining (unrecoverable)
                units_reworked = int(units_defective * random.uniform(0.5, 0.6))
                units_requiring_repair = int(units_defective * random.uniform(0.2, 0.3))
                units_scrapped = max(0, units_defective - units_reworked - units_requiring_repair)

                quality_id = f"QE-{wo['id']}-{q_idx+1:02d}"

                try:
                    self.cursor.execute("""
                        INSERT INTO QUALITY_ENTRY (
                            quality_entry_id, client_id, work_order_id,
                            shift_date, inspection_date, units_inspected, units_passed, units_defective,
                            total_defects_count, units_reworked, units_requiring_repair, units_scrapped,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        quality_id, wo["client_id"], wo["id"],
                        q_date.strftime('%Y-%m-%d'), q_date.strftime('%Y-%m-%d'),
                        units_inspected, units_passed, units_defective,
                        total_defects, units_reworked, units_requiring_repair, units_scrapped
                    ))
                    quality_count += 1
                except sqlite3.IntegrityError:
                    pass

        self.conn.commit()
        print(f"   ✓ Created {quality_count} quality entries")

    def generate_attendance_entries(self):
        """Generate 90 days of attendance data with realistic patterns."""
        print("\n📅 Generating Attendance Entries...")

        attendance_count = 0
        entry_num = 0

        for emp_code, emp_data in self.employee_map.items():
            emp_id = emp_data["id"]
            client_id = emp_data["client_id"]

            for day_offset in range(90):
                att_date = DATA_START_DATE + timedelta(days=day_offset)

                # Skip most weekends
                if att_date.weekday() >= 5 and random.random() > 0.2:
                    continue

                is_absent = random.random() < 0.05
                scheduled_hours = 8.0
                actual_hours = 0 if is_absent else random.uniform(7.5, 8.5)

                entry_num += 1
                att_id = f"ATT-{entry_num:08d}"

                try:
                    self.cursor.execute("""
                        INSERT INTO ATTENDANCE_ENTRY (
                            attendance_entry_id, employee_id, client_id, shift_id,
                            shift_date, scheduled_hours, actual_hours,
                            is_absent, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        att_id, emp_id, client_id, random.randint(1, 3),
                        att_date.strftime('%Y-%m-%d'),
                        scheduled_hours, actual_hours,
                        1 if is_absent else 0
                    ))
                    attendance_count += 1
                except sqlite3.IntegrityError:
                    pass

        self.conn.commit()
        print(f"   ✓ Created {attendance_count} attendance entries")

    def generate_coverage_entries(self):
        """Generate floating pool coverage entries."""
        print("\n🔄 Generating Coverage Entries...")

        coverage_count = 0
        entry_num = 0

        # Get list of regular employees who had absences
        absent_employees = []
        for emp_code, emp_data in self.employee_map.items():
            absent_employees.append((emp_data["id"], emp_data["client_id"]))

        floating_ids = list(self.floating_pool_map.values())

        for day_offset in range(30):
            coverage_date = DATA_END_DATE - timedelta(days=day_offset)

            # 3-5 coverage assignments per day
            num_assignments = random.randint(3, 5)

            for _ in range(num_assignments):
                if not floating_ids or not absent_employees:
                    break

                float_emp_id = random.choice(floating_ids)
                covered_emp_id, client_id = random.choice(absent_employees)

                entry_num += 1
                coverage_id = f"COV-{entry_num:08d}"

                try:
                    self.cursor.execute("""
                        INSERT INTO COVERAGE_ENTRY (
                            coverage_entry_id, client_id, floating_employee_id, covered_employee_id,
                            shift_date, shift_id, coverage_hours, coverage_reason,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        coverage_id, client_id, float_emp_id, covered_emp_id,
                        coverage_date.strftime('%Y-%m-%d'), random.randint(1, 2),
                        random.uniform(4.0, 8.0),
                        random.choice(["Absenteeism Coverage", "Production Surge", "Quality Support"])
                    ))
                    coverage_count += 1
                except sqlite3.IntegrityError:
                    pass

        self.conn.commit()
        print(f"   ✓ Created {coverage_count} coverage entries")

    def generate_downtime_entries(self):
        """Generate downtime entries - aligned with actual DOWNTIME_ENTRY schema."""
        print("\n⏸️  Generating Downtime Entries...")

        # Valid downtime_reason enum values (VARCHAR(17))
        downtime_reasons = [
            "MACHINE_BREAKDOWN",
            "MATERIAL_SHORTAGE",
            "QUALITY_ISSUE",
            "CHANGEOVER",
            "MAINTENANCE",
            "POWER_OUTAGE",
            "OTHER"
        ]

        downtime_count = 0
        dt_entry_num = 1

        for wo in self.work_order_data:
            num_downtimes = random.randint(1, 3)

            for dt_idx in range(num_downtimes):
                dt_date = wo["start_date"] + timedelta(days=random.randint(0, 14))
                if dt_date > DATA_END_DATE:
                    dt_date = DATA_END_DATE

                reason = random.choice(downtime_reasons)
                duration_minutes = random.randint(15, 180)

                downtime_id = f"DT-{DATA_END_DATE.strftime('%Y%m')}-{dt_entry_num:05d}"
                dt_entry_num += 1

                try:
                    self.cursor.execute("""
                        INSERT INTO DOWNTIME_ENTRY (
                            downtime_entry_id, client_id, work_order_id,
                            shift_date, downtime_reason, downtime_duration_minutes,
                            machine_id, equipment_code, root_cause_category,
                            corrective_action, notes,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        downtime_id,
                        wo["client_id"],
                        wo["id"],
                        dt_date.strftime('%Y-%m-%d %H:%M:%S'),
                        reason,
                        duration_minutes,
                        f"MACH-{random.randint(1, 20):03d}",
                        f"EQ-{random.choice(['SEW', 'CUT', 'PRESS', 'PACK'])}-{random.randint(1, 10):02d}",
                        reason.replace('_', ' ').title(),
                        f"Resolved by maintenance team. Duration: {duration_minutes} min.",
                        f"Downtime event during production of {wo['id']}"
                    ))
                    downtime_count += 1
                except sqlite3.IntegrityError as e:
                    print(f"      Warning: Could not insert downtime {downtime_id}: {e}")

        self.conn.commit()
        print(f"   ✓ Created {downtime_count} downtime entries")

    def generate_hold_entries(self):
        """Generate hold entries - aligned with actual HOLD_ENTRY schema."""
        print("\n🚫 Generating Hold Entries...")

        # Valid hold_status enum values (VARCHAR(9))
        # Valid hold_reason enum values (VARCHAR(21))
        hold_reasons = [
            ("QUALITY_ISSUE", "Quality Issue"),
            ("MATERIAL_SHORTAGE", "Material Shortage"),
            ("CUSTOMER_REQUEST", "Customer Request"),
            ("ENGINEERING_CHANGE", "Engineering Change"),
            ("PENDING_APPROVAL", "Pending Approval"),
            ("OTHER", "Other")
        ]

        hold_count = 0
        hold_candidates = [wo for wo in self.work_order_data if wo["status"] in ["ON_HOLD", "AT_RISK", "COMPLETED"]]

        for wo in hold_candidates[:15]:
            reason_code, reason_desc = random.choice(hold_reasons)

            hold_date = wo["start_date"] + timedelta(days=random.randint(1, 10))
            if hold_date > DATA_END_DATE:
                hold_date = DATA_END_DATE

            # Determine hold status (VARCHAR(9): ON_HOLD, RESUMED, CANCELLED)
            if wo["status"] == "ON_HOLD" and random.random() < 0.6:
                hold_status = "ON_HOLD"  # Still pending
                resume_date = None
                hold_duration = None
            elif random.random() < 0.7:
                hold_status = "RESUMED"
                resume_date = hold_date + timedelta(days=random.randint(1, 5))
                hold_duration = (resume_date - hold_date).total_seconds() / 3600  # hours
            else:
                hold_status = "ON_HOLD"
                resume_date = None
                hold_duration = None

            hold_id = f"HLD-{wo['id']}-{hold_count+1:02d}"

            try:
                self.cursor.execute("""
                    INSERT INTO HOLD_ENTRY (
                        hold_entry_id, client_id, work_order_id,
                        hold_status, hold_date, resume_date,
                        total_hold_duration_hours,
                        hold_reason_category, hold_reason, hold_reason_description,
                        expected_resolution_date, notes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    hold_id,
                    wo["client_id"],
                    wo["id"],
                    hold_status,
                    hold_date.strftime('%Y-%m-%d %H:%M:%S'),
                    resume_date.strftime('%Y-%m-%d %H:%M:%S') if resume_date else None,
                    hold_duration,
                    reason_desc,  # hold_reason_category
                    reason_code,  # hold_reason (enum)
                    f"Hold due to {reason_desc.lower()} on work order {wo['id']}",
                    (hold_date + timedelta(days=random.randint(2, 7))).strftime('%Y-%m-%d') if hold_status == "ON_HOLD" else None,
                    f"Hold entry for {wo['id']}: {reason_desc}"
                ))
                hold_count += 1
            except sqlite3.IntegrityError as e:
                print(f"      Warning: Could not insert hold {hold_id}: {e}")

        self.conn.commit()
        print(f"   ✓ Created {hold_count} hold entries")

    def generate_alerts(self):
        """Generate sample alerts for dashboard demonstration."""
        print("\n🚨 Generating Alerts...")

        alert_count = 0

        # OTD Risk Alerts
        at_risk_orders = [wo for wo in self.work_order_data if wo["status"] == "AT_RISK"]
        for wo in at_risk_orders:
            alert_id = f"ALT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            days_until_due = (wo["ship_date"] - DATA_END_DATE).days

            if days_until_due <= 2:
                severity = "urgent"
            elif days_until_due <= 5:
                severity = "critical"
            else:
                severity = "warning"

            completion_pct = round(wo["actual_qty"] / wo["planned_qty"] * 100, 1) if wo["planned_qty"] > 0 else 0

            try:
                self.cursor.execute("""
                    INSERT INTO ALERT (
                        alert_id, category, severity, status, title, message, recommendation,
                        client_id, kpi_key, work_order_id, current_value, threshold_value,
                        alert_metadata, created_at
                    ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    alert_id, "otd", severity,
                    f"OTD Risk: {wo['id']} Due in {days_until_due} Days",
                    f"Work order {wo['id']} is at {completion_pct}% completion with only {days_until_due} days until ship date.",
                    "Prioritize this order. Consider overtime or resource reallocation.",
                    wo["client_id"], "otd", wo["id"],
                    completion_pct, 95.0,
                    json.dumps({"days_remaining": days_until_due, "risk_score": 100 - completion_pct})
                ))
                alert_count += 1
            except sqlite3.IntegrityError:
                pass

        # Quality Alerts
        self.cursor.execute("""
            SELECT work_order_id, client_id,
                   CAST(SUM(units_passed) AS FLOAT) / NULLIF(SUM(units_inspected), 0) * 100 as fpy
            FROM QUALITY_ENTRY
            GROUP BY work_order_id, client_id
            HAVING fpy < 95
            LIMIT 5
        """)
        low_fpy_orders = self.cursor.fetchall()

        for wo_id, client_id, fpy in low_fpy_orders:
            if fpy is None:
                continue
            alert_id = f"ALT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

            if fpy < 85:
                severity = "critical"
            elif fpy < 90:
                severity = "warning"
            else:
                severity = "info"

            try:
                self.cursor.execute("""
                    INSERT INTO ALERT (
                        alert_id, category, severity, status, title, message, recommendation,
                        client_id, kpi_key, work_order_id, current_value, threshold_value,
                        created_at
                    ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    alert_id, "quality", severity,
                    f"Low FPY Alert: {fpy:.1f}%",
                    f"First Pass Yield for {wo_id} is {fpy:.1f}%, below 95% target.",
                    "Review quality inspection results and identify root cause.",
                    client_id, "fpy", wo_id,
                    round(fpy, 2), 95.0
                ))
                alert_count += 1
            except sqlite3.IntegrityError:
                pass

        # Efficiency Alert
        alert_id = f"ALT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        try:
            self.cursor.execute("""
                INSERT INTO ALERT (
                    alert_id, category, severity, status, title, message, recommendation,
                    client_id, kpi_key, current_value, threshold_value, created_at
                ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                alert_id, "efficiency", "warning",
                "Efficiency Declining Trend",
                "Production efficiency has declined for 5 consecutive periods. Current: 78.5% vs target: 85%.",
                "Investigate production bottlenecks and equipment performance.",
                self.client_ids[0], "efficiency", 78.5, 85.0
            ))
            alert_count += 1
        except sqlite3.IntegrityError:
            pass

        # Capacity Alert
        alert_id = f"ALT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        try:
            self.cursor.execute("""
                INSERT INTO ALERT (
                    alert_id, category, severity, status, title, message, recommendation,
                    client_id, kpi_key, current_value, threshold_value, alert_metadata, created_at
                ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                alert_id, "capacity", "critical",
                "Capacity Overload Warning",
                "Current load at 112% of capacity. Cannot meet demand without overtime.",
                "Authorize overtime or reallocate resources.",
                self.client_ids[1], "load_percent", 112.0, 95.0,
                json.dumps({"overtime_hours_needed": 24, "bottleneck": "Sewing Line 3"})
            ))
            alert_count += 1
        except sqlite3.IntegrityError:
            pass

        # Hold Alert
        self.cursor.execute("SELECT COUNT(*) FROM HOLD_ENTRY WHERE hold_status = 'ON_HOLD'")
        pending_holds = self.cursor.fetchone()[0]

        if pending_holds > 0:
            alert_id = f"ALT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            try:
                self.cursor.execute("""
                    INSERT INTO ALERT (
                        alert_id, category, severity, status, title, message, recommendation,
                        kpi_key, alert_metadata, created_at
                    ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    alert_id, "hold", "warning",
                    f"{pending_holds} Holds Pending Approval",
                    f"There are {pending_holds} hold entries awaiting review.",
                    "Review and approve/reject pending holds.",
                    "holds_pending",
                    json.dumps({"pending_count": pending_holds})
                ))
                alert_count += 1
            except sqlite3.IntegrityError:
                pass

        self.conn.commit()
        print(f"   ✓ Created {alert_count} alerts")

    def generate_alert_configs(self):
        """Generate alert configurations."""
        print("\n⚙️  Generating Alert Configurations...")

        config_count = 0
        alert_types = ["otd", "quality", "efficiency", "capacity", "attendance", "hold"]

        # Global defaults
        for alert_type in alert_types:
            config_id = f"ACF-GLOBAL-{alert_type.upper()}"

            thresholds = {
                "otd": (90.0, 85.0),
                "quality": (95.0, 90.0),
                "efficiency": (80.0, 70.0),
                "capacity": (100.0, 110.0),
                "attendance": (8.0, 12.0),
                "hold": (None, None)
            }
            warning, critical = thresholds.get(alert_type, (None, None))

            try:
                self.cursor.execute("""
                    INSERT INTO ALERT_CONFIG (
                        config_id, client_id, alert_type, enabled,
                        warning_threshold, critical_threshold,
                        notification_email, check_frequency_minutes, created_at, updated_at
                    ) VALUES (?, NULL, ?, 1, ?, ?, 1, 60, datetime('now'), datetime('now'))
                """, (config_id, alert_type, warning, critical))
                config_count += 1
            except sqlite3.IntegrityError:
                pass

        self.conn.commit()
        print(f"   ✓ Created {config_count} alert configurations")

    def generate_kpi_thresholds(self):
        """Generate KPI threshold configurations - aligned with actual schema."""
        print("\n📊 Generating KPI Thresholds...")

        threshold_count = 0

        # (kpi_key, target, warning, critical, unit, higher_is_better)
        kpi_configs = [
            ("efficiency", 85.0, 80.0, 70.0, "%", "Y"),
            ("otd", 95.0, 90.0, 85.0, "%", "Y"),
            ("fpy", 98.0, 95.0, 90.0, "%", "Y"),
            ("rty", 95.0, 92.0, 88.0, "%", "Y"),
            ("dpmo", 1000.0, 2000.0, 3500.0, "PPM", "N"),
            ("absenteeism", 5.0, 8.0, 12.0, "%", "N"),
            ("load_percent", 90.0, 100.0, 110.0, "%", "N")
        ]

        for kpi_key, target, warning, critical, unit, higher_better in kpi_configs:
            threshold_id = f"THR-{kpi_key.upper()}"

            try:
                self.cursor.execute("""
                    INSERT INTO KPI_THRESHOLD (
                        threshold_id, client_id, kpi_key,
                        target_value, warning_threshold, critical_threshold,
                        unit, higher_is_better, created_at, updated_at
                    ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (threshold_id, kpi_key, target, warning, critical, unit, higher_better))
                threshold_count += 1
            except sqlite3.IntegrityError:
                pass

        self.conn.commit()
        print(f"   ✓ Created {threshold_count} KPI thresholds")

    def print_summary(self):
        """Print summary of generated data."""
        print("\n" + "=" * 70)
        print("✅ DEMO DATA GENERATION COMPLETED!")
        print("=" * 70)

        tables = [
            "CLIENT", "USER", "EMPLOYEE", "SHIFT", "PRODUCT",
            "WORK_ORDER", "JOB", "PART_OPPORTUNITIES",
            "PRODUCTION_ENTRY", "QUALITY_ENTRY",
            "ATTENDANCE_ENTRY", "COVERAGE_ENTRY", "DOWNTIME_ENTRY",
            "HOLD_ENTRY", "ALERT", "ALERT_CONFIG", "KPI_THRESHOLD"
        ]

        print("\nRecord Counts:")
        for table in tables:
            try:
                self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = self.cursor.fetchone()[0]
                print(f"   {table:25} {count:>8,}")
            except sqlite3.OperationalError:
                print(f"   {table:25} {'N/A':>8}")

        # Work order status
        print("\nWork Order Status Breakdown:")
        self.cursor.execute("SELECT status, COUNT(*) FROM WORK_ORDER GROUP BY status")
        for status, count in self.cursor.fetchall():
            print(f"   {status:25} {count:>8}")

        # Alert breakdown
        print("\nAlert Breakdown:")
        self.cursor.execute("SELECT category, severity, COUNT(*) FROM ALERT GROUP BY category, severity")
        for category, severity, count in self.cursor.fetchall():
            print(f"   {category} ({severity}): {count}")

        print("\n" + "=" * 70)
        print(f"Database: {self.db_path}")
        print("=" * 70)

    def run(self, clear_existing: bool = True):
        """Run the full data generation process."""
        self.connect()

        try:
            if clear_existing:
                self.clear_existing_data()

            self.generate_users()
            self.generate_clients()
            self.generate_shifts()
            self.generate_products()
            self.generate_defect_types()
            self.generate_employees()
            self.generate_work_orders()
            self.generate_jobs()  # Phase 6.6: JOB table for RTY
            self.generate_part_opportunities()  # Phase 6.7: PART_OPPORTUNITIES for DPMO
            self.generate_production_entries()
            self.generate_quality_entries()
            self.generate_attendance_entries()
            self.generate_coverage_entries()
            self.generate_downtime_entries()
            self.generate_hold_entries()
            self.generate_alerts()
            self.generate_alert_configs()
            self.generate_kpi_thresholds()

            self.print_summary()

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.conn.rollback()
            raise
        finally:
            self.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="KPI Operations Demo Data Generator")
    parser.add_argument("--db", default=DB_PATH, help="Path to database file")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed")
    parser.add_argument("--no-clear", action="store_true", help="Don't clear existing data")

    args = parser.parse_args()

    print("=" * 70)
    print("KPI Operations Platform - Demo Data Generator v3.2.0")
    print("Phase 10.5: Comprehensive Sample Data Regeneration")
    print("=" * 70)

    generator = DemoDataGenerator(args.db, args.seed)
    generator.run(clear_existing=not args.no_clear)


if __name__ == "__main__":
    main()
