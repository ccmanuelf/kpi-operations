#!/usr/bin/env python3
"""
Comprehensive Data Generator for KPI Operations Dashboard

Generates realistic, process-flow-accurate sample data with proper FK relationships.
Uses raw SQL to match the actual SQLite database schema.

Requirements:
- 5 Clients (each with unique characteristics)
- 25+ Work Orders (5+ per client)
- 50-100 Jobs (1-12 per work order)
- 20+ Employees (mix of regular and floating pool)
- 3 Shifts
- 10 Products
- 30 days of data entries
- Edge cases (rush orders, holds, quality issues, absences)

Process Flow Order (CRITICAL):
1. Create Clients (5)
2. Create Shifts (3: Morning, Afternoon, Night)
3. Create Products (10 with varying cycle times)
4. Create Employees (20+: some floating pool, assigned to clients)
5. Create Work Orders (5+ per client, with proper dates)
6. Create Jobs (1-12 per work order, with part_number, quantities)
7. Create Part Opportunities (link to job part_numbers)
8. Create Production Entries (link to work_order)
9. Create Quality Entries (link to work_order)
10. Create Attendance Entries (30 days, with some absences)
11. Create Shift Coverage Entries
12. Create Downtime Entries (various reasons)
13. Create Hold Entries (some ON_HOLD, some RESUMED)
14. Create Defect Details (linked to quality entries)

Author: KPI Operations Platform
Version: 2.0.0
"""

import os
import sys
import random
import sqlite3
from datetime import datetime, timedelta, time, date
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(PROJECT_ROOT, 'database', 'kpi_platform.db')

# Seed for reproducible data (change for different datasets)
RANDOM_SEED = 42

# Date range for data generation
DATA_START_DATE = datetime.now() - timedelta(days=30)
DATA_END_DATE = datetime.now()

# ============================================================================
# Data Templates
# ============================================================================

CLIENT_DATA = [
    {
        "client_id": "ACME-MFG",
        "client_name": "ACME Manufacturing Corp",
        "client_type": "Piece Rate",
        "timezone": "US/Eastern",
        "characteristics": {"products": ["automotive", "industrial"], "volume": "high"}
    },
    {
        "client_id": "TEXTIL-PRO",
        "client_name": "Textile Professionals Inc",
        "client_type": "Piece Rate",
        "timezone": "US/Pacific",
        "characteristics": {"products": ["garments", "uniforms"], "volume": "medium"}
    },
    {
        "client_id": "ELEC-ASSY",
        "client_name": "Electronic Assembly Solutions",
        "client_type": "Hourly Rate",
        "timezone": "US/Central",
        "characteristics": {"products": ["electronics", "pcb"], "volume": "low"}
    },
    {
        "client_id": "PACK-SHIP",
        "client_name": "PackShip Logistics LLC",
        "client_type": "Hybrid",
        "timezone": "US/Central",
        "characteristics": {"products": ["packaging", "shipping"], "volume": "high"}
    },
    {
        "client_id": "MEDDEV-INC",
        "client_name": "Medical Devices International",
        "client_type": "Service",
        "timezone": "US/Eastern",
        "characteristics": {"products": ["medical", "precision"], "volume": "low"}
    }
]

SHIFT_DATA = [
    {"shift_id": 1, "shift_name": "Morning Shift", "start_time": "06:00:00", "end_time": "14:00:00"},
    {"shift_id": 2, "shift_name": "Afternoon Shift", "start_time": "14:00:00", "end_time": "22:00:00"},
    {"shift_id": 3, "shift_name": "Night Shift", "start_time": "22:00:00", "end_time": "06:00:00"}
]

PRODUCT_DATA = [
    {"product_code": "PROD-AUTO-001", "product_name": "Automotive Harness Assembly", "ideal_cycle_time": 0.25},
    {"product_code": "PROD-GARM-001", "product_name": "Standard Uniform Shirt", "ideal_cycle_time": 0.50},
    {"product_code": "PROD-GARM-002", "product_name": "Premium Blazer", "ideal_cycle_time": 1.25},
    {"product_code": "PROD-ELEC-001", "product_name": "PCB Assembly Type A", "ideal_cycle_time": 0.15},
    {"product_code": "PROD-ELEC-002", "product_name": "Sensor Module", "ideal_cycle_time": 0.35},
    {"product_code": "PROD-PACK-001", "product_name": "Standard Packaging Kit", "ideal_cycle_time": 0.08},
    {"product_code": "PROD-PACK-002", "product_name": "Custom Box Assembly", "ideal_cycle_time": 0.12},
    {"product_code": "PROD-MED-001", "product_name": "Surgical Instrument Kit", "ideal_cycle_time": 2.00},
    {"product_code": "PROD-MED-002", "product_name": "Diagnostic Device Assembly", "ideal_cycle_time": 3.50},
    {"product_code": "PROD-IND-001", "product_name": "Industrial Valve Assembly", "ideal_cycle_time": 0.75}
]

EMPLOYEE_NAMES = [
    "James Wilson", "Emma Thompson", "Michael Brown", "Sophia Davis", "William Martinez",
    "Isabella Anderson", "Alexander Taylor", "Olivia Thomas", "Daniel Jackson", "Ava White",
    "Matthew Harris", "Mia Martin", "Joseph Garcia", "Charlotte Robinson", "David Clark",
    "Amelia Lewis", "Andrew Lee", "Harper Walker", "Christopher Hall", "Evelyn Allen",
    "Joshua Young", "Abigail King", "Ethan Wright", "Emily Scott", "Ryan Adams"
]

OPERATION_TEMPLATES = [
    {"code": "CUT", "name": "Cutting", "description": "Cut materials to specifications"},
    {"code": "SEW", "name": "Sewing", "description": "Assemble components by sewing"},
    {"code": "ASSY", "name": "Assembly", "description": "Manual assembly operations"},
    {"code": "SOLDER", "name": "Soldering", "description": "Electronic soldering"},
    {"code": "TEST", "name": "Testing", "description": "Functional testing"},
    {"code": "QC", "name": "Quality Check", "description": "Quality inspection"},
    {"code": "PACK", "name": "Packaging", "description": "Final packaging"},
    {"code": "PRESS", "name": "Pressing", "description": "Steam pressing and finishing"},
    {"code": "TRIM", "name": "Trimming", "description": "Trim excess materials"},
    {"code": "LABEL", "name": "Labeling", "description": "Apply labels and tags"},
    {"code": "CLEAN", "name": "Cleaning", "description": "Clean and prepare"},
    {"code": "WELD", "name": "Welding", "description": "Welding operations"}
]

HOLD_REASONS = [
    "Material Inspection Pending",
    "Quality Issue - Rework Required",
    "Customer Design Change Request",
    "Missing Specifications",
    "Equipment Maintenance",
    "Capacity Constraint",
    "Supplier Delay",
    "Engineering Review"
]

DOWNTIME_REASONS = [
    "Equipment Failure - Motor",
    "Equipment Failure - Sensor",
    "Material Shortage",
    "Setup/Changeover",
    "Quality Hold",
    "Preventive Maintenance",
    "Power Issues",
    "Training",
    "Break Time"
]

DOWNTIME_CATEGORIES = [
    "EQUIPMENT_FAILURE",
    "MATERIAL_SHORTAGE",
    "SETUP_CHANGEOVER",
    "QUALITY_HOLD",
    "MAINTENANCE",
    "POWER_OUTAGE",
    "OTHER"
]

DEFECT_TYPES = [
    "Stitching",
    "Fabric Defect",
    "Measurement",
    "Color Shade",
    "Pilling",
    "Hole/Tear",
    "Stain",
    "Other"
]

DEFECT_SEVERITIES = ["CRITICAL", "MAJOR", "MINOR"]
DEFECT_LOCATIONS = ["Front", "Back", "Side", "Top", "Bottom", "Edge", "Center", "Corner"]


# ============================================================================
# Generator Class
# ============================================================================

class RealisticDataGenerator:
    """Generates comprehensive, realistic KPI data with proper FK relationships."""

    def __init__(self, db_path: str, seed: int = RANDOM_SEED):
        """Initialize the generator with database connection."""
        random.seed(seed)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Storage for generated IDs (for FK references)
        self.client_ids: List[str] = []
        self.shift_ids: List[int] = []
        self.product_ids: List[str] = []
        self.employee_ids: List[str] = []
        self.floating_employee_ids: List[str] = []
        self.regular_employee_ids: List[str] = []
        self.work_order_ids: List[str] = []
        self.job_ids: List[str] = []
        self.part_numbers: List[str] = []
        self.quality_entry_ids: List[str] = []
        self.production_entry_ids: List[str] = []

        # Maps for relationships
        self.work_order_to_client: Dict[str, str] = {}
        self.job_to_work_order: Dict[str, str] = {}
        self.job_to_client: Dict[str, str] = {}
        self.job_part_numbers: Dict[str, str] = {}
        self.employee_to_client: Dict[str, str] = {}
        self.quality_to_client: Dict[str, str] = {}

        # Statistics
        self.stats: Dict[str, int] = {}

        print("=" * 70)
        print("KPI Operations - Comprehensive Realistic Data Generator")
        print("=" * 70)
        print(f"Database: {db_path}")
        print(f"Random Seed: {seed}")
        print(f"Date Range: {DATA_START_DATE.strftime('%Y-%m-%d')} to {DATA_END_DATE.strftime('%Y-%m-%d')}")
        print("=" * 70)

    def clear_existing_data(self) -> None:
        """Clear existing sample data except admin users."""
        print("\n[Step 0] Clearing existing sample data...")

        # Tables in reverse dependency order (children first)
        tables_to_clear = [
            "DEFECT_DETAIL",
            "SHIFT_COVERAGE",
            "ATTENDANCE_ENTRY",
            "DOWNTIME_ENTRY",
            "HOLD_ENTRY",
            "QUALITY_ENTRY",
            "PRODUCTION_ENTRY",
            "PART_OPPORTUNITIES",
            "JOB",
            "WORK_ORDER",
            "EMPLOYEE",
            "PRODUCT",
            "SHIFT",
            "CLIENT"
        ]

        for table in tables_to_clear:
            try:
                self.cursor.execute(f"DELETE FROM {table}")
                count = self.cursor.rowcount
                if count > 0:
                    print(f"   Cleared {count} records from {table}")
            except Exception as e:
                print(f"   Warning: Could not clear {table}: {e}")

        # Keep admin users, clear demo users
        try:
            self.cursor.execute("DELETE FROM USER WHERE role != 'ADMIN' OR role IS NULL")
            count = self.cursor.rowcount
            if count > 0:
                print(f"   Cleared {count} non-admin users from USER")
        except Exception as e:
            print(f"   Warning: Could not clear USER table: {e}")

        # Ensure system users exist for FK references
        self._ensure_system_users()

        self.conn.commit()
        print("   Data cleared successfully.")

    def _ensure_system_users(self) -> None:
        """Create system users required for FK references."""
        system_users = [
            ("SYS-001", "system", "system@kpi-ops.local", "System User", "ADMIN"),
            ("ADMIN-001", "admin", "admin@kpi-ops.local", "Administrator", "ADMIN"),
            ("SUPER-001", "supervisor", "supervisor@kpi-ops.local", "Supervisor", "POWERUSER"),
        ]

        for user_id, username, email, full_name, role in system_users:
            try:
                self.cursor.execute("""
                    INSERT OR IGNORE INTO USER (user_id, username, email, full_name, role, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                """, (user_id, username, email, full_name, role))
            except Exception:
                pass  # User might already exist

        # Store system user ID for references (user_id is VARCHAR in USER, but entered_by expects Integer)
        # We'll use NULL for entered_by since the type mismatch makes it problematic
        self.system_user_id = None  # We'll handle this in the entry generators

    def generate_clients(self) -> None:
        """Generate 5 clients with unique characteristics."""
        print("\n[Step 1] Generating Clients...")

        for client_data in CLIENT_DATA:
            self.cursor.execute("""
                INSERT INTO CLIENT (client_id, client_name, client_type, timezone, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, datetime('now'))
            """, (
                client_data["client_id"],
                client_data["client_name"],
                client_data["client_type"],
                client_data["timezone"]
            ))
            self.client_ids.append(client_data["client_id"])

        self.conn.commit()
        self.stats["clients"] = len(self.client_ids)
        print(f"   Created {len(self.client_ids)} clients: {self.client_ids}")

    def generate_shifts(self) -> None:
        """Generate 3 shifts: Morning, Afternoon, Night."""
        print("\n[Step 2] Generating Shifts...")

        for shift_data in SHIFT_DATA:
            self.cursor.execute("""
                INSERT INTO SHIFT (shift_id, shift_name, start_time, end_time, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, datetime('now'))
            """, (
                shift_data["shift_id"],
                shift_data["shift_name"],
                shift_data["start_time"],
                shift_data["end_time"]
            ))
            self.shift_ids.append(shift_data["shift_id"])

        self.conn.commit()
        self.stats["shifts"] = len(self.shift_ids)
        print(f"   Created {len(self.shift_ids)} shifts: {[s['shift_name'] for s in SHIFT_DATA]}")

    def generate_products(self) -> None:
        """Generate 10 products with varying cycle times."""
        print("\n[Step 3] Generating Products...")

        for i, prod_data in enumerate(PRODUCT_DATA, 1):
            self.cursor.execute("""
                INSERT INTO PRODUCT (product_code, product_name, ideal_cycle_time, unit_of_measure, is_active, created_at, updated_at)
                VALUES (?, ?, ?, 'units', 1, datetime('now'), datetime('now'))
            """, (
                prod_data["product_code"],
                prod_data["product_name"],
                prod_data["ideal_cycle_time"]
            ))
            # Get the auto-generated product_id
            product_id = self.cursor.lastrowid
            self.product_ids.append(product_id)

        self.conn.commit()
        self.stats["products"] = len(self.product_ids)
        print(f"   Created {len(self.product_ids)} products with cycle times ranging from "
              f"{min(p['ideal_cycle_time'] for p in PRODUCT_DATA)} to "
              f"{max(p['ideal_cycle_time'] for p in PRODUCT_DATA)} hours")

    def generate_employees(self) -> None:
        """Generate 25 employees: 20 regular + 5 floating pool."""
        print("\n[Step 4] Generating Employees...")

        employee_count = 0

        # Generate 4 regular employees per client (20 total)
        for client_id in self.client_ids:
            for i in range(4):
                if employee_count >= len(EMPLOYEE_NAMES):
                    break

                emp_code = f"EMP-{client_id[:4]}-{i+1:03d}"
                emp_name = EMPLOYEE_NAMES[employee_count]

                self.cursor.execute("""
                    INSERT INTO EMPLOYEE (employee_code, employee_name, client_id_assigned, is_floating_pool, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, 0, 1, datetime('now'), datetime('now'))
                """, (emp_code, emp_name, client_id))

                # Get auto-generated employee_id (Integer PK)
                emp_id = self.cursor.lastrowid
                self.employee_ids.append(emp_id)
                self.regular_employee_ids.append(emp_id)
                self.employee_to_client[emp_id] = client_id
                employee_count += 1

        # Generate 5 floating pool employees
        for i in range(5):
            if employee_count >= len(EMPLOYEE_NAMES):
                break

            emp_code = f"EMP-FLOAT-{i+1:03d}"
            emp_name = EMPLOYEE_NAMES[employee_count]

            self.cursor.execute("""
                INSERT INTO EMPLOYEE (employee_code, employee_name, client_id_assigned, is_floating_pool, is_active, created_at, updated_at)
                VALUES (?, ?, NULL, 1, 1, datetime('now'), datetime('now'))
            """, (emp_code, emp_name))

            emp_id = self.cursor.lastrowid
            self.employee_ids.append(emp_id)
            self.floating_employee_ids.append(emp_id)
            employee_count += 1

        self.conn.commit()
        self.stats["employees"] = len(self.employee_ids)
        self.stats["floating_pool"] = len(self.floating_employee_ids)
        print(f"   Created {len(self.regular_employee_ids)} regular employees")
        print(f"   Created {len(self.floating_employee_ids)} floating pool employees")

    def generate_work_orders(self) -> None:
        """Generate 25+ work orders (5+ per client) with proper dates."""
        print("\n[Step 5] Generating Work Orders...")

        work_order_count = 0
        priorities = ["HIGH", "MEDIUM", "LOW"]
        statuses = ["ACTIVE", "ON_HOLD", "COMPLETED", "CANCELLED"]

        for client_id in self.client_ids:
            # Generate 5-7 work orders per client
            num_orders = random.randint(5, 7)

            for i in range(num_orders):
                wo_id = f"WO-{client_id[:4]}-{datetime.now().strftime('%Y%m')}-{work_order_count+1:04d}"

                # Calculate dates
                planned_start = DATA_START_DATE + timedelta(days=random.randint(0, 15))
                actual_start = planned_start + timedelta(days=random.randint(-2, 3))
                planned_ship = planned_start + timedelta(days=random.randint(10, 30))

                # Determine status with distribution
                status_roll = random.random()
                if status_roll < 0.50:
                    status = "ACTIVE"
                    actual_delivery = None
                elif status_roll < 0.75:
                    status = "COMPLETED"
                    # Completed orders: 70% on time, 30% late
                    if random.random() < 0.7:
                        actual_delivery = planned_ship - timedelta(days=random.randint(0, 3))
                    else:
                        actual_delivery = planned_ship + timedelta(days=random.randint(1, 7))
                elif status_roll < 0.90:
                    status = "ON_HOLD"
                    actual_delivery = None
                else:
                    status = "CANCELLED"
                    actual_delivery = None

                # Quantities
                planned_qty = random.randint(100, 1000)
                actual_qty = int(planned_qty * random.uniform(0.7, 1.0)) if status == "COMPLETED" else int(planned_qty * random.uniform(0.1, 0.6))

                # Rush orders
                is_rush = random.random() < 0.15
                priority = "HIGH" if is_rush else random.choice(priorities)

                self.cursor.execute("""
                    INSERT INTO WORK_ORDER (
                        work_order_id, client_id, style_model, planned_quantity, actual_quantity,
                        planned_start_date, actual_start_date, planned_ship_date, required_date,
                        actual_delivery_date, ideal_cycle_time, status, priority, qc_approved,
                        notes, customer_po_number, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    wo_id, client_id, f"MODEL-{random.randint(1000, 9999)}",
                    planned_qty, actual_qty,
                    planned_start.strftime('%Y-%m-%d %H:%M:%S'),
                    actual_start.strftime('%Y-%m-%d %H:%M:%S'),
                    planned_ship.strftime('%Y-%m-%d %H:%M:%S'),
                    (planned_ship - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
                    actual_delivery.strftime('%Y-%m-%d %H:%M:%S') if actual_delivery else None,
                    round(random.uniform(0.1, 2.0), 4),
                    status, priority,
                    1 if status == "COMPLETED" else 0,
                    f"{'RUSH ORDER - ' if is_rush else ''}Work order for {client_id}",
                    f"PO-{random.randint(100000, 999999)}"
                ))

                self.work_order_ids.append(wo_id)
                self.work_order_to_client[wo_id] = client_id
                work_order_count += 1

        self.conn.commit()
        self.stats["work_orders"] = len(self.work_order_ids)
        print(f"   Created {len(self.work_order_ids)} work orders across {len(self.client_ids)} clients")

    def generate_jobs(self) -> None:
        """Generate 50-100 jobs (1-12 per work order) with part numbers."""
        print("\n[Step 6] Generating Jobs...")

        job_count = 0

        for wo_id in self.work_order_ids:
            client_id = self.work_order_to_client[wo_id]

            # Generate 1-12 jobs per work order
            num_jobs = random.choices(
                range(1, 13),
                weights=[3, 5, 8, 10, 12, 12, 10, 8, 5, 4, 2, 1],
                k=1
            )[0]

            # Select operations for this work order
            selected_ops = random.sample(OPERATION_TEMPLATES, min(num_jobs, len(OPERATION_TEMPLATES)))

            for seq, op in enumerate(selected_ops, 1):
                job_id = f"JOB-{wo_id[-8:]}-{seq:02d}"
                part_number = f"PART-{client_id[:4]}-{op['code']}-{random.randint(100, 999)}"

                planned_qty = random.randint(50, 500)
                completed_qty = random.randint(0, planned_qty) if random.random() > 0.3 else 0
                is_completed = 1 if completed_qty >= planned_qty * 0.95 else 0

                planned_hours = round(random.uniform(2, 16), 2)
                actual_hours = round(planned_hours * random.uniform(0.8, 1.4), 2) if completed_qty > 0 else None

                # Assign employee if available
                client_employees = [e for e, c in self.employee_to_client.items() if c == client_id]
                assigned_employee = random.choice(client_employees) if client_employees else None

                self.cursor.execute("""
                    INSERT INTO JOB (
                        job_id, work_order_id, client_id_fk, operation_name, operation_code,
                        sequence_number, part_number, part_description, planned_quantity,
                        completed_quantity, quantity_scrapped, planned_hours, actual_hours, is_completed,
                        completed_date, assigned_employee_id, assigned_shift_id, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    job_id, wo_id, client_id, op["name"], op["code"],
                    seq, part_number, op["description"], planned_qty,
                    completed_qty, random.randint(0, 5),  # quantity_scrapped
                    planned_hours, actual_hours, is_completed,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S') if is_completed else None,
                    assigned_employee, random.choice(self.shift_ids),
                    f"Job for {op['name']} operation"
                ))

                self.job_ids.append(job_id)
                self.job_to_work_order[job_id] = wo_id
                self.job_to_client[job_id] = client_id
                self.job_part_numbers[job_id] = part_number
                self.part_numbers.append(part_number)
                job_count += 1

        self.conn.commit()
        self.stats["jobs"] = len(self.job_ids)
        print(f"   Created {len(self.job_ids)} jobs with unique part numbers")

    def generate_part_opportunities(self) -> None:
        """Generate part opportunities linked to job part numbers."""
        print("\n[Step 7] Generating Part Opportunities...")

        # Group part numbers by client
        client_parts: Dict[str, set] = {c: set() for c in self.client_ids}
        for job_id, part_num in self.job_part_numbers.items():
            client_id = self.job_to_client[job_id]
            client_parts[client_id].add(part_num)

        part_opp_count = 0
        for client_id, parts in client_parts.items():
            for part_number in parts:
                # Opportunities per unit varies by part complexity
                opportunities = random.choices(
                    [2, 3, 4, 5, 6, 8, 10, 12],
                    weights=[5, 10, 20, 25, 20, 10, 7, 3],
                    k=1
                )[0]

                # Extract category from part number
                part_code = part_number.split("-")[2] if len(part_number.split("-")) > 2 else "GEN"
                part_category = next(
                    (op["name"] for op in OPERATION_TEMPLATES if op["code"] == part_code),
                    "General"
                )

                self.cursor.execute("""
                    INSERT INTO PART_OPPORTUNITIES (
                        part_number, client_id_fk, opportunities_per_unit,
                        part_description, part_category, notes
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    part_number, client_id, opportunities,
                    f"Part opportunities for {part_number}",
                    part_category,
                    f"DPMO calculation: {opportunities} opportunities per unit"
                ))
                part_opp_count += 1

        self.conn.commit()
        self.stats["part_opportunities"] = part_opp_count
        print(f"   Created {part_opp_count} part opportunities records")

    def generate_production_entries(self) -> None:
        """Generate production entries linked to work orders."""
        print("\n[Step 8] Generating Production Entries...")

        prod_entry_count = 0

        # Generate entries for each day in the date range
        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE:
            # Skip weekends with 90% probability
            if current_date.weekday() >= 5 and random.random() < 0.9:
                current_date += timedelta(days=1)
                continue

            # Generate entries for each client
            for client_id in self.client_ids:
                # Get work orders for this client
                client_wos = [wo for wo, c in self.work_order_to_client.items() if c == client_id]

                if not client_wos:
                    continue

                # 1-3 production entries per client per day
                num_entries = random.randint(1, 3)

                for _ in range(num_entries):
                    wo_id = random.choice(client_wos)

                    entry_id = f"PROD-{wo_id[-8:]}-{current_date.strftime('%Y%m%d')}-{prod_entry_count+1:04d}"

                    # Production metrics
                    units_produced = random.randint(20, 200)
                    run_time_hours = round(random.uniform(2, 8), 2)
                    employees_assigned = random.randint(2, 10)

                    # Quality metrics with realistic defect rates (0-5%)
                    defect_rate = random.uniform(0, 0.05)
                    defect_count = int(units_produced * defect_rate)
                    scrap_count = int(defect_count * random.uniform(0.1, 0.3))
                    rework_count = defect_count - scrap_count

                    # Calculate efficiency (80-120% of ideal)
                    efficiency = round(random.uniform(80, 120), 2)
                    performance = round(random.uniform(75, 110), 2)
                    quality_rate = round((1 - defect_rate) * 100, 2)

                    self.cursor.execute("""
                        INSERT INTO PRODUCTION_ENTRY (
                            production_entry_id, client_id, product_id, shift_id, work_order_id,
                            production_date, shift_date, units_produced, run_time_hours,
                            employees_assigned, employees_present, defect_count, scrap_count, rework_count,
                            setup_time_hours, downtime_hours, efficiency_percentage,
                            performance_percentage, quality_rate, notes, entered_by, entry_method, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        entry_id, client_id, random.choice(self.product_ids),  # product_id is now Integer
                        random.choice(self.shift_ids), wo_id,
                        current_date.strftime('%Y-%m-%d'), current_date.strftime('%Y-%m-%d'),
                        units_produced, run_time_hours, employees_assigned,
                        employees_assigned - random.randint(0, 2),  # employees_present
                        defect_count, scrap_count, rework_count,
                        round(random.uniform(0.25, 1.0), 2),
                        round(random.uniform(0, 0.5), 2),
                        efficiency, performance, quality_rate,
                        f"Production entry for {current_date.strftime('%Y-%m-%d')}",
                        1,  # entered_by: placeholder Integer (FK enforcement is off)
                        "MANUAL_ENTRY"
                    ))

                    self.production_entry_ids.append(entry_id)
                    prod_entry_count += 1

            current_date += timedelta(days=1)

        self.conn.commit()
        self.stats["production_entries"] = len(self.production_entry_ids)
        print(f"   Created {len(self.production_entry_ids)} production entries over 30 days")

    def generate_quality_entries(self) -> None:
        """Generate quality entries linked to work orders."""
        print("\n[Step 9] Generating Quality Entries...")

        quality_entry_count = 0

        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE:
            # Skip weekends
            if current_date.weekday() >= 5 and random.random() < 0.9:
                current_date += timedelta(days=1)
                continue

            for client_id in self.client_ids:
                # Get work orders for this client
                client_wos = [wo for wo, c in self.work_order_to_client.items() if c == client_id]

                if not client_wos:
                    continue

                # 1-2 quality entries per client per day
                num_entries = random.randint(1, 2)

                for _ in range(num_entries):
                    wo_id = random.choice(client_wos)

                    entry_id = f"QE-{wo_id[-8:]}-{current_date.strftime('%Y%m%d')}-{quality_entry_count+1:04d}"

                    units_inspected = random.randint(50, 300)

                    # Calculate defect metrics
                    defect_rate = random.uniform(0, 0.08)  # 0-8% defect rate
                    units_failed = int(units_inspected * defect_rate)
                    units_passed = units_inspected - units_failed

                    # Total defects can be higher than units (multiple defects per unit)
                    total_defects = int(units_failed * random.uniform(1, 2.5))

                    self.cursor.execute("""
                        INSERT INTO QUALITY_ENTRY (
                            quality_entry_id, client_id, work_order_id, shift_date, inspection_date,
                            units_inspected, units_passed, units_defective, total_defects_count,
                            inspection_stage, is_first_pass, units_scrapped, units_reworked,
                            inspector_id, notes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        entry_id, client_id, wo_id,
                        current_date.strftime('%Y-%m-%d'),  # shift_date (required)
                        current_date.strftime('%Y-%m-%d'),  # inspection_date
                        units_inspected, units_passed, units_failed, total_defects,
                        random.choice(["INCOMING", "IN_PROCESS", "FINAL"]),  # inspection_stage
                        1 if random.random() > 0.2 else 0,  # is_first_pass
                        int(units_failed * 0.2),  # units_scrapped
                        int(units_failed * 0.8),  # units_reworked
                        1,  # inspector_id: placeholder (FK enforcement off)
                        f"Quality inspection for {current_date.strftime('%Y-%m-%d')}"
                    ))

                    self.quality_entry_ids.append(entry_id)
                    self.quality_to_client[entry_id] = client_id
                    quality_entry_count += 1

            current_date += timedelta(days=1)

        self.conn.commit()
        self.stats["quality_entries"] = len(self.quality_entry_ids)
        print(f"   Created {len(self.quality_entry_ids)} quality entries")

    def generate_attendance_entries(self) -> None:
        """Generate 30 days of attendance entries with realistic absences."""
        print("\n[Step 10] Generating Attendance Entries...")

        attendance_count = 0
        absent_count = 0

        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            for emp_id in self.regular_employee_ids:
                client_id = self.employee_to_client.get(emp_id)
                if not client_id:
                    continue

                scheduled_hours = 8.00

                # Determine attendance status (85% present, 15% some form of absence)
                attendance_roll = random.random()

                if attendance_roll < 0.85:
                    # Present
                    is_absent = 0
                    actual_hours = scheduled_hours - round(random.uniform(0, 0.5), 2)
                    is_late = 1 if random.random() < 0.1 else 0
                elif attendance_roll < 0.92:
                    # Unscheduled absence
                    is_absent = 1
                    actual_hours = 0
                    is_late = 0
                    absent_count += 1
                elif attendance_roll < 0.96:
                    # Medical leave
                    is_absent = 1
                    actual_hours = 0
                    is_late = 0
                    absent_count += 1
                else:
                    # Other absence
                    is_absent = 1
                    actual_hours = 0
                    is_late = 0
                    absent_count += 1

                att_entry_id = f"ATT-{emp_id}-{current_date.strftime('%Y%m%d')}"
                self.cursor.execute("""
                    INSERT INTO ATTENDANCE_ENTRY (
                        attendance_entry_id, client_id, employee_id, shift_date, shift_id,
                        scheduled_hours, actual_hours, absence_hours, is_absent, is_late,
                        entered_by, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    att_entry_id, client_id, emp_id,  # emp_id is now Integer
                    current_date.strftime('%Y-%m-%d'),  # shift_date
                    random.choice(self.shift_ids),
                    scheduled_hours, actual_hours,
                    scheduled_hours - actual_hours if is_absent else 0,  # absence_hours
                    is_absent, is_late,
                    1,  # entered_by: placeholder (FK enforcement off)
                    "Absent" if is_absent else None
                ))

                attendance_count += 1

            current_date += timedelta(days=1)

        self.conn.commit()
        self.stats["attendance_entries"] = attendance_count
        self.stats["absences"] = absent_count
        print(f"   Created {attendance_count} attendance entries")
        print(f"   Including {absent_count} absence records")

    def generate_shift_coverage(self) -> None:
        """Generate shift coverage entries."""
        print("\n[Step 11] Generating Shift Coverage Entries...")

        coverage_count = 0

        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            for client_id in self.client_ids:
                for shift_id in self.shift_ids:
                    scheduled = random.randint(15, 25)
                    present = max(0, scheduled - random.randint(0, 5))
                    coverage_pct = round((present / scheduled) * 100, 2) if scheduled > 0 else 0

                    self.cursor.execute("""
                        INSERT INTO SHIFT_COVERAGE (
                            client_id, shift_id, coverage_date, employees_scheduled,
                            employees_present, coverage_percentage, entered_by, notes, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (
                        client_id, shift_id, current_date.strftime('%Y-%m-%d'),
                        scheduled, present, coverage_pct,
                        "SYSTEM", f"Shift coverage for {current_date.strftime('%Y-%m-%d')}"
                    ))
                    coverage_count += 1

            current_date += timedelta(days=1)

        self.conn.commit()
        self.stats["shift_coverage"] = coverage_count
        print(f"   Created {coverage_count} shift coverage entries")

    def generate_downtime_entries(self) -> None:
        """Generate downtime entries with various reasons."""
        print("\n[Step 12] Generating Downtime Entries...")

        downtime_count = 0

        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE:
            if current_date.weekday() >= 5 and random.random() < 0.9:
                current_date += timedelta(days=1)
                continue

            for client_id in self.client_ids:
                # Get work orders for this client
                client_wos = [wo for wo, c in self.work_order_to_client.items() if c == client_id]

                if not client_wos:
                    continue

                # 20% chance of downtime per client per day
                if random.random() < 0.20:
                    wo_id = random.choice(client_wos)

                    # Select downtime reason
                    reason = random.choice(DOWNTIME_REASONS)
                    category = random.choice(DOWNTIME_CATEGORIES)

                    # Duration varies by reason type
                    duration = random.randint(10, 180)  # 10 min to 3 hours

                    dt_entry_id = f"DT-{wo_id[-8:]}-{current_date.strftime('%Y%m%d')}-{downtime_count+1:04d}"
                    self.cursor.execute("""
                        INSERT INTO DOWNTIME_ENTRY (
                            downtime_entry_id, client_id, work_order_id, shift_date,
                            downtime_reason, downtime_duration_minutes,
                            root_cause_category, reported_by, notes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        dt_entry_id, client_id, wo_id,
                        current_date.strftime('%Y-%m-%d'),  # shift_date
                        reason, duration,
                        category,  # root_cause_category
                        1,  # reported_by: placeholder (FK enforcement off)
                        f"Downtime: {reason}"
                    ))
                    downtime_count += 1

            current_date += timedelta(days=1)

        self.conn.commit()
        self.stats["downtime_entries"] = downtime_count
        print(f"   Created {downtime_count} downtime entries")

    def generate_hold_entries(self) -> None:
        """Generate hold entries (some ON_HOLD, some RELEASED)."""
        print("\n[Step 13] Generating Hold Entries...")

        hold_count = 0

        for wo_id in self.work_order_ids:
            # 25% of work orders have holds
            if random.random() < 0.25:
                client_id = self.work_order_to_client[wo_id]

                hold_date = DATA_START_DATE + timedelta(days=random.randint(0, 20))

                # 60% of holds are released
                is_released = random.random() < 0.60
                release_date = hold_date + timedelta(days=random.randint(1, 10)) if is_released else None

                hold_entry_id = f"HOLD-{wo_id[-8:]}-{hold_count+1:04d}"
                hold_status = "RESUMED" if is_released else "ON_HOLD"

                self.cursor.execute("""
                    INSERT INTO HOLD_ENTRY (
                        hold_entry_id, client_id, work_order_id, hold_status,
                        hold_date, resume_date, hold_reason_category,
                        hold_initiated_by, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    hold_entry_id, client_id, wo_id, hold_status,
                    hold_date.strftime('%Y-%m-%d'),
                    release_date.strftime('%Y-%m-%d') if release_date else None,
                    random.choice(HOLD_REASONS),
                    1,  # hold_initiated_by: placeholder (FK enforcement off)
                    f"Hold entry for {wo_id}"
                ))
                hold_count += 1

        self.conn.commit()
        self.stats["hold_entries"] = hold_count
        print(f"   Created {hold_count} hold entries")

    def generate_defect_details(self) -> None:
        """Generate defect details linked to quality entries."""
        print("\n[Step 14] Generating Defect Details...")

        defect_count = 0

        for qe_id in self.quality_entry_ids:
            # 40% of quality entries have detailed defects
            if random.random() < 0.40:
                client_id = self.quality_to_client[qe_id]

                # 1-4 different defect types per quality entry
                num_defects = random.randint(1, 4)

                for i in range(num_defects):
                    defect_id = f"DEF-{qe_id[-12:]}-{i+1:02d}"

                    defect_type = random.choice(DEFECT_TYPES)

                    self.cursor.execute("""
                        INSERT INTO DEFECT_DETAIL (
                            defect_detail_id, quality_entry_id, client_id_fk,
                            defect_type, defect_category, defect_count,
                            severity, location, description, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (
                        defect_id, qe_id, client_id,
                        defect_type, defect_type,
                        random.randint(1, 15),
                        random.choice(DEFECT_SEVERITIES),
                        random.choice(DEFECT_LOCATIONS),
                        f"Found {defect_type.lower()} defect"
                    ))
                    defect_count += 1

        self.conn.commit()
        self.stats["defect_details"] = defect_count
        print(f"   Created {defect_count} defect detail records")

    def print_summary(self) -> None:
        """Print generation summary with statistics."""
        print("\n" + "=" * 70)
        print("GENERATION COMPLETE - Summary Statistics")
        print("=" * 70)

        print("\n Base Tables:")
        print(f"   Clients:              {self.stats.get('clients', 0):>6}")
        print(f"   Shifts:               {self.stats.get('shifts', 0):>6}")
        print(f"   Products:             {self.stats.get('products', 0):>6}")
        print(f"   Employees (Regular):  {len(self.regular_employee_ids):>6}")
        print(f"   Employees (Floating): {self.stats.get('floating_pool', 0):>6}")

        print("\n Work Order Tables:")
        print(f"   Work Orders:          {self.stats.get('work_orders', 0):>6}")
        print(f"   Jobs:                 {self.stats.get('jobs', 0):>6}")
        print(f"   Part Opportunities:   {self.stats.get('part_opportunities', 0):>6}")

        print("\n Entry Tables (30 days):")
        print(f"   Production Entries:   {self.stats.get('production_entries', 0):>6}")
        print(f"   Quality Entries:      {self.stats.get('quality_entries', 0):>6}")
        print(f"   Attendance Entries:   {self.stats.get('attendance_entries', 0):>6}")
        print(f"   Shift Coverage:       {self.stats.get('shift_coverage', 0):>6}")
        print(f"   Downtime Entries:     {self.stats.get('downtime_entries', 0):>6}")
        print(f"   Hold Entries:         {self.stats.get('hold_entries', 0):>6}")
        print(f"   Defect Details:       {self.stats.get('defect_details', 0):>6}")

        total_records = sum(self.stats.values())
        print(f"\n   TOTAL RECORDS:        {total_records:>6}")
        print("=" * 70)

    def run(self) -> None:
        """Execute the full data generation pipeline."""
        try:
            # Clear existing data first
            self.clear_existing_data()

            # Generate in proper FK order
            self.generate_clients()            # Step 1
            self.generate_shifts()             # Step 2
            self.generate_products()           # Step 3
            self.generate_employees()          # Step 4
            self.generate_work_orders()        # Step 5
            self.generate_jobs()               # Step 6
            self.generate_part_opportunities() # Step 7
            self.generate_production_entries() # Step 8
            self.generate_quality_entries()    # Step 9
            self.generate_attendance_entries() # Step 10
            self.generate_shift_coverage()     # Step 11
            self.generate_downtime_entries()   # Step 12
            self.generate_hold_entries()       # Step 13
            self.generate_defect_details()     # Step 14

            # Print summary
            self.print_summary()

            print("\n Data generation completed successfully!")

        except Exception as e:
            self.conn.rollback()
            print(f"\n ERROR: Data generation failed: {e}")
            raise
        finally:
            self.conn.close()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for the data generator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate comprehensive realistic data for KPI Operations Dashboard"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help=f"Random seed for reproducible data (default: {RANDOM_SEED})"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DB_PATH,
        help=f"Database path (default: {DB_PATH})"
    )

    args = parser.parse_args()

    generator = RealisticDataGenerator(db_path=args.db, seed=args.seed)
    generator.run()


if __name__ == "__main__":
    main()
