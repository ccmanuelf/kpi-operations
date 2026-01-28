#!/usr/bin/env python3
"""
Comprehensive Data Regeneration Script for KPI Operations Platform

CRITICAL: This script PRESERVES the USER table (11 existing users)
and regenerates ALL other tables with realistic, coherent data.

Requirements:
- Preserve all 11 users in USER table
- Regenerate all other tables with proper FK relationships
- ALERT_HISTORY must be populated (currently empty)
- PRODUCTION_ENTRY: 700+ entries
- QUALITY_ENTRY: 100+ entries
- ATTENDANCE_ENTRY: 5000+ entries spanning 60-90 days
- DOWNTIME_ENTRY: 100+ events
- HOLD_ENTRY: 50+ events
- WORK_ORDER: 50+ orders

Author: KPI Operations Platform
Version: 3.0.0
"""

import os
import sys
import random
import sqlite3
import uuid
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(PROJECT_ROOT, 'database', 'kpi_platform.db')

# Seed for reproducible data (change for different datasets)
RANDOM_SEED = 2026

# Date range for data generation - 90 days
DATA_END_DATE = datetime.now()
DATA_START_DATE = DATA_END_DATE - timedelta(days=90)

# ============================================================================
# Data Templates
# ============================================================================

# Use existing clients from the database
EXISTING_CLIENTS = [
    "CONFEC-DELTA",
    "GARMENT-PLUS",
    "MAQUILA-PRIME",
    "NOVALINK-MTY",
    "TEXTIL-NORTE"
]

SHIFT_DATA = [
    {"shift_id": 1, "shift_name": "Morning Shift", "start_time": "06:00:00", "end_time": "14:00:00"},
    {"shift_id": 2, "shift_name": "Afternoon Shift", "start_time": "14:00:00", "end_time": "22:00:00"},
    {"shift_id": 3, "shift_name": "Night Shift", "start_time": "22:00:00", "end_time": "06:00:00"}
]

PRODUCT_DATA = [
    {"product_code": "PROD-SHIRT-001", "product_name": "Standard T-Shirt Assembly", "ideal_cycle_time": 0.15},
    {"product_code": "PROD-POLO-001", "product_name": "Polo Shirt Production", "ideal_cycle_time": 0.25},
    {"product_code": "PROD-JACKET-001", "product_name": "Work Jacket Assembly", "ideal_cycle_time": 0.50},
    {"product_code": "PROD-PANTS-001", "product_name": "Industrial Pants Line", "ideal_cycle_time": 0.35},
    {"product_code": "PROD-UNIFORM-001", "product_name": "Complete Uniform Set", "ideal_cycle_time": 0.75},
    {"product_code": "PROD-DRESS-001", "product_name": "Formal Dress Production", "ideal_cycle_time": 0.60},
    {"product_code": "PROD-BLAZER-001", "product_name": "Business Blazer Line", "ideal_cycle_time": 0.80},
    {"product_code": "PROD-VEST-001", "product_name": "Safety Vest Assembly", "ideal_cycle_time": 0.20},
    {"product_code": "PROD-COVERALL-001", "product_name": "Industrial Coverall", "ideal_cycle_time": 0.55},
    {"product_code": "PROD-APRON-001", "product_name": "Work Apron Production", "ideal_cycle_time": 0.18}
]

EMPLOYEE_NAMES = [
    "Maria Garcia", "Juan Rodriguez", "Carlos Martinez", "Ana Lopez", "Pedro Hernandez",
    "Rosa Gonzalez", "Miguel Sanchez", "Elena Torres", "Luis Ramirez", "Carmen Flores",
    "Fernando Diaz", "Patricia Moreno", "Roberto Castro", "Lucia Ortiz", "Andres Vargas",
    "Sofia Romero", "Diego Mendoza", "Laura Reyes", "Oscar Guerrero", "Isabel Herrera",
    "Alejandro Silva", "Veronica Ruiz", "Ricardo Jimenez", "Gabriela Molina", "Jorge Navarro",
    "Andrea Ramos", "Eduardo Soto", "Monica Cruz", "Raul Delgado", "Teresa Medina",
    "Victor Rojas", "Daniela Aguirre", "Alberto Campos", "Natalia Vega", "Pablo Rios",
    "Valeria Gutierrez", "Sergio Perez", "Mariana Santos", "Hector Luna", "Adriana Pineda",
    "Gustavo Dominguez", "Claudia Espinoza", "Armando Fuentes", "Yolanda Coronado", "Enrique Velazquez",
    "Beatriz Pacheco", "Manuel Rangel", "Lorena Ibarra", "Francisco Acosta", "Gloria Salazar",
    "Javier Trejo", "Marisol Valencia", "Ramon Ochoa", "Leticia Cardenas", "Felipe Estrada",
    "Norma Paredes", "Arturo Cervantes", "Irene Sandoval", "Cesar Maldonado", "Silvia Cortez",
    "Mauricio Zuniga", "Rocio Bautista", "Ernesto Lara", "Angelica Ponce", "Benjamin Villegas",
    "Alicia Serrano", "Nicolas Cabrera", "Carolina Duran", "Julian Montes", "Fabiola Orozco",
    "Ignacio Solis", "Jessica Gallegos", "Rodrigo Contreras", "Diana Lozano", "Adrian Padilla",
    "Rebeca Miranda", "Gonzalo Olvera", "Miriam Tapia", "Tomas Villanueva", "Brenda Salas",
    "Samuel Carrillo", "Cecilia Avila", "Ismael Nunez", "Pamela Arellano", "Leonel Escobar",
    "Martha Cazares", "Hugo Barajas", "Araceli Tovar", "Rafael Quintero", "Perla Alvarado",
    "Irving Huerta", "Viviana Meza", "Gerardo Cisneros", "Sandra Camacho", "Oswaldo Barrera",
    "Nayeli Rivera", "Reynaldo Gil", "Karla Zamora", "Saul Figueroa", "Dulce Becerra"
]

OPERATION_TEMPLATES = [
    {"code": "CUT", "name": "Cutting", "description": "Cut materials to specifications"},
    {"code": "SEW", "name": "Sewing", "description": "Assemble components by sewing"},
    {"code": "ASSY", "name": "Assembly", "description": "Manual assembly operations"},
    {"code": "FUSE", "name": "Fusing", "description": "Heat-seal interlining"},
    {"code": "TEST", "name": "Testing", "description": "Functional testing"},
    {"code": "QC", "name": "Quality Check", "description": "Quality inspection"},
    {"code": "PACK", "name": "Packaging", "description": "Final packaging"},
    {"code": "PRESS", "name": "Pressing", "description": "Steam pressing and finishing"},
    {"code": "TRIM", "name": "Trimming", "description": "Trim excess materials"},
    {"code": "LABEL", "name": "Labeling", "description": "Apply labels and tags"},
    {"code": "BUTTON", "name": "Buttoning", "description": "Attach buttons and fasteners"},
    {"code": "EMBROIDER", "name": "Embroidery", "description": "Embroidery operations"}
]

HOLD_REASONS = [
    "Material Inspection Pending",
    "Quality Issue - Rework Required",
    "Customer Design Change Request",
    "Missing Specifications",
    "Equipment Maintenance",
    "Capacity Constraint",
    "Supplier Delay",
    "Engineering Review",
    "Customer Approval Required",
    "Inventory Discrepancy"
]

HOLD_REASON_CATEGORIES = [
    "QUALITY",
    "MATERIAL",
    "CUSTOMER",
    "ENGINEERING",
    "PRODUCTION",
    "OTHER"
]

DOWNTIME_REASONS = [
    "EQUIPMENT_FAILURE",
    "MATERIAL_SHORTAGE",
    "SETUP_CHANGEOVER",
    "QUALITY_HOLD",
    "MAINTENANCE",
    "OTHER"
]

DOWNTIME_DESCRIPTIONS = {
    "EQUIPMENT_FAILURE": ["Motor failure", "Sensor malfunction", "Belt replacement", "Needle break", "Thread tension issue"],
    "MATERIAL_SHORTAGE": ["Fabric delay", "Thread stockout", "Button shortage", "Zipper shortage", "Label stockout"],
    "SETUP_CHANGEOVER": ["Style changeover", "Color change", "Size change", "Product line switch", "Equipment setup"],
    "QUALITY_HOLD": ["Inspection required", "Rework pending", "Customer hold", "Defect investigation", "QC review"],
    "MAINTENANCE": ["Scheduled maintenance", "Lubrication", "Calibration", "Cleaning", "Preventive service"],
    "OTHER": ["Power outage", "Training session", "Safety drill", "Team meeting", "Inventory count"]
}

DEFECT_TYPES = ["Stitching", "Fabric", "Measurement", "Color", "Pilling", "Hole", "Stain", "Label", "Button", "Zipper", "Seam", "Thread", "Other"]
DEFECT_SEVERITIES = ["CRITICAL", "MAJOR", "MINOR"]
DEFECT_LOCATIONS = ["Front", "Back", "Sleeve", "Collar", "Hem", "Pocket", "Seam", "Edge", "Center", "Cuff"]

ALERT_CATEGORIES = ["production", "quality", "delivery", "attendance", "efficiency", "maintenance"]
ALERT_SEVERITIES = ["critical", "high", "medium", "low"]
ALERT_STATUSES = ["active", "acknowledged", "resolved"]


# ============================================================================
# Generator Class
# ============================================================================

class ComprehensiveDataRegenerator:
    """Regenerates all data except USER table with proper FK relationships."""

    def __init__(self, db_path: str, seed: int = RANDOM_SEED):
        """Initialize the generator with database connection."""
        random.seed(seed)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = OFF")  # Temporarily disable FK checks
        self.cursor = self.conn.cursor()

        # Storage for generated IDs (for FK references)
        self.client_ids: List[str] = EXISTING_CLIENTS.copy()
        self.shift_ids: List[int] = []
        self.product_ids: List[int] = []
        self.employee_ids: List[int] = []
        self.floating_employee_ids: List[int] = []
        self.regular_employee_ids: List[int] = []
        self.work_order_ids: List[str] = []
        self.job_ids: List[str] = []
        self.part_numbers: List[str] = []
        self.quality_entry_ids: List[str] = []
        self.production_entry_ids: List[str] = []
        self.alert_ids: List[str] = []

        # Maps for relationships
        self.work_order_to_client: Dict[str, str] = {}
        self.job_to_work_order: Dict[str, str] = {}
        self.job_to_client: Dict[str, str] = {}
        self.job_part_numbers: Dict[str, str] = {}
        self.employee_to_client: Dict[int, str] = {}
        self.quality_to_client: Dict[str, str] = {}
        self.quality_to_wo: Dict[str, str] = {}
        self.wo_dates: Dict[str, datetime] = {}

        # Statistics
        self.stats: Dict[str, int] = {}

        # Get user IDs from existing users
        self.user_ids = self._get_existing_user_ids()

        print("=" * 70)
        print("KPI Operations - Comprehensive Data Regeneration")
        print("=" * 70)
        print(f"Database: {db_path}")
        print(f"Random Seed: {seed}")
        print(f"Date Range: {DATA_START_DATE.strftime('%Y-%m-%d')} to {DATA_END_DATE.strftime('%Y-%m-%d')}")
        print(f"Existing Users: {len(self.user_ids)}")
        print("=" * 70)

    def _get_existing_user_ids(self) -> List[str]:
        """Get list of existing user IDs to preserve."""
        self.cursor.execute("SELECT user_id FROM USER")
        return [row[0] for row in self.cursor.fetchall()]

    def _get_random_user_id(self) -> Optional[str]:
        """Get a random user ID for FK references."""
        if self.user_ids:
            return random.choice(self.user_ids)
        return None

    def clear_existing_data(self) -> None:
        """Clear all tables EXCEPT USER."""
        print("\n[Step 0] Clearing existing data (PRESERVING USER table)...")

        # Tables in reverse dependency order (children first)
        tables_to_clear = [
            "ALERT_HISTORY",
            "ALERT_CONFIG",
            "ALERT",
            "DEFECT_DETAIL",
            "SHIFT_COVERAGE",
            "COVERAGE_ENTRY",
            "ATTENDANCE_ENTRY",
            "DOWNTIME_ENTRY",
            "HOLD_ENTRY",
            "QUALITY_ENTRY",
            "PRODUCTION_ENTRY",
            "PART_OPPORTUNITIES",
            "JOB",
            "WORK_ORDER",
            "FLOATING_POOL",
            "EMPLOYEE",
            "PRODUCT",
            "SHIFT",
            # CLIENT is preserved - it has existing data we want to keep
        ]

        for table in tables_to_clear:
            try:
                self.cursor.execute(f"DELETE FROM {table}")
                count = self.cursor.rowcount
                if count > 0:
                    print(f"   Cleared {count} records from {table}")
                else:
                    print(f"   {table}: already empty")
            except Exception as e:
                print(f"   Warning: Could not clear {table}: {e}")

        self.conn.commit()
        print("   Data cleared successfully (USER table preserved).")

    def generate_shifts(self) -> None:
        """Generate 3 shifts: Morning, Afternoon, Night."""
        print("\n[Step 1] Generating Shifts...")

        for shift_data in SHIFT_DATA:
            try:
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
            except sqlite3.IntegrityError:
                self.shift_ids.append(shift_data["shift_id"])
                print(f"   Shift {shift_data['shift_name']} already exists")

        self.conn.commit()
        self.stats["shifts"] = len(self.shift_ids)
        print(f"   Created/verified {len(self.shift_ids)} shifts")

    def generate_products(self) -> None:
        """Generate 10 products with varying cycle times."""
        print("\n[Step 2] Generating Products...")

        for i, prod_data in enumerate(PRODUCT_DATA, 1):
            self.cursor.execute("""
                INSERT INTO PRODUCT (product_code, product_name, ideal_cycle_time, unit_of_measure, is_active, created_at, updated_at)
                VALUES (?, ?, ?, 'units', 1, datetime('now'), datetime('now'))
            """, (
                prod_data["product_code"],
                prod_data["product_name"],
                prod_data["ideal_cycle_time"]
            ))
            product_id = self.cursor.lastrowid
            self.product_ids.append(product_id)

        self.conn.commit()
        self.stats["products"] = len(self.product_ids)
        print(f"   Created {len(self.product_ids)} products")

    def generate_employees(self) -> None:
        """Generate 100 employees: 80 regular + 20 floating pool."""
        print("\n[Step 3] Generating Employees...")

        employee_count = 0

        # Generate 16 regular employees per client (80 total)
        for client_id in self.client_ids:
            for i in range(16):
                if employee_count >= len(EMPLOYEE_NAMES):
                    break

                emp_code = f"EMP-{client_id[:4]}-{i+1:03d}"
                emp_name = EMPLOYEE_NAMES[employee_count]

                self.cursor.execute("""
                    INSERT INTO EMPLOYEE (employee_code, employee_name, client_id_assigned, is_floating_pool, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, 0, 1, datetime('now'), datetime('now'))
                """, (emp_code, emp_name, client_id))

                emp_id = self.cursor.lastrowid
                self.employee_ids.append(emp_id)
                self.regular_employee_ids.append(emp_id)
                self.employee_to_client[emp_id] = client_id
                employee_count += 1

        # Generate 20 floating pool employees
        for i in range(20):
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
        """Generate 60+ work orders (12+ per client) with proper dates."""
        print("\n[Step 4] Generating Work Orders...")

        work_order_count = 0
        priorities = ["HIGH", "MEDIUM", "LOW"]
        statuses = ["ACTIVE", "ON_HOLD", "COMPLETED", "CANCELLED"]
        styles = ["T-SHIRT", "POLO", "JACKET", "PANTS", "UNIFORM", "DRESS", "BLAZER", "VEST", "COVERALL", "APRON"]

        for client_id in self.client_ids:
            # Generate 12-15 work orders per client
            num_orders = random.randint(12, 15)

            for i in range(num_orders):
                wo_id = f"WO-{client_id[:4]}-{DATA_END_DATE.strftime('%Y%m')}-{work_order_count+1:04d}"

                # Calculate dates within our 90-day window
                planned_start = DATA_START_DATE + timedelta(days=random.randint(0, 60))
                actual_start = planned_start + timedelta(days=random.randint(-2, 5))
                planned_ship = planned_start + timedelta(days=random.randint(14, 45))
                required_date = planned_ship - timedelta(days=random.randint(1, 5))

                # Determine status with realistic distribution
                status_roll = random.random()
                if status_roll < 0.45:
                    status = "ACTIVE"
                    actual_delivery = None
                elif status_roll < 0.80:
                    status = "COMPLETED"
                    # Completed orders: 70% on time, 30% late
                    if random.random() < 0.7:
                        actual_delivery = planned_ship - timedelta(days=random.randint(0, 5))
                    else:
                        actual_delivery = planned_ship + timedelta(days=random.randint(1, 10))
                elif status_roll < 0.92:
                    status = "ON_HOLD"
                    actual_delivery = None
                else:
                    status = "CANCELLED"
                    actual_delivery = None

                # Quantities
                planned_qty = random.randint(200, 2000)
                if status == "COMPLETED":
                    actual_qty = int(planned_qty * random.uniform(0.85, 1.0))
                elif status == "ACTIVE":
                    actual_qty = int(planned_qty * random.uniform(0.1, 0.7))
                else:
                    actual_qty = int(planned_qty * random.uniform(0.0, 0.3))

                # Rush orders and priority
                is_rush = random.random() < 0.12
                priority = "HIGH" if is_rush else random.choice(priorities)

                style = random.choice(styles) + f"-{random.randint(100, 999)}"

                self.cursor.execute("""
                    INSERT INTO WORK_ORDER (
                        work_order_id, client_id, style_model, planned_quantity, actual_quantity,
                        planned_start_date, actual_start_date, planned_ship_date, required_date,
                        actual_delivery_date, ideal_cycle_time, status, priority, qc_approved,
                        notes, customer_po_number, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    wo_id, client_id, style,
                    planned_qty, actual_qty,
                    planned_start.strftime('%Y-%m-%d %H:%M:%S'),
                    actual_start.strftime('%Y-%m-%d %H:%M:%S'),
                    planned_ship.strftime('%Y-%m-%d %H:%M:%S'),
                    required_date.strftime('%Y-%m-%d %H:%M:%S'),
                    actual_delivery.strftime('%Y-%m-%d %H:%M:%S') if actual_delivery else None,
                    round(random.uniform(0.15, 0.80), 4),
                    status, priority,
                    1 if status == "COMPLETED" else 0,
                    f"{'RUSH ORDER - ' if is_rush else ''}Work order for {client_id}",
                    f"PO-{random.randint(100000, 999999)}"
                ))

                self.work_order_ids.append(wo_id)
                self.work_order_to_client[wo_id] = client_id
                self.wo_dates[wo_id] = actual_start
                work_order_count += 1

        self.conn.commit()
        self.stats["work_orders"] = len(self.work_order_ids)
        print(f"   Created {len(self.work_order_ids)} work orders across {len(self.client_ids)} clients")

    def generate_jobs(self) -> None:
        """Generate 200+ jobs (2-8 per work order) with part numbers."""
        print("\n[Step 5] Generating Jobs...")

        job_count = 0

        for wo_id in self.work_order_ids:
            client_id = self.work_order_to_client[wo_id]

            # Generate 2-8 jobs per work order
            num_jobs = random.choices(
                range(2, 9),
                weights=[5, 15, 25, 25, 15, 10, 5],
                k=1
            )[0]

            # Select operations for this work order
            selected_ops = random.sample(OPERATION_TEMPLATES, min(num_jobs, len(OPERATION_TEMPLATES)))

            for seq, op in enumerate(selected_ops, 1):
                job_id = f"JOB-{wo_id[-8:]}-{seq:02d}"
                part_number = f"PART-{client_id[:4]}-{op['code']}-{random.randint(100, 999)}"

                planned_qty = random.randint(100, 800)
                completed_qty = random.randint(0, planned_qty) if random.random() > 0.2 else 0
                is_completed = 1 if completed_qty >= planned_qty * 0.95 else 0

                planned_hours = round(random.uniform(4, 24), 2)
                actual_hours = round(planned_hours * random.uniform(0.8, 1.3), 2) if completed_qty > 0 else None

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
                    completed_qty, random.randint(0, 10),
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
        print("\n[Step 6] Generating Part Opportunities...")

        # Group unique part numbers by client
        client_parts: Dict[str, set] = {c: set() for c in self.client_ids}
        for job_id, part_num in self.job_part_numbers.items():
            client_id = self.job_to_client[job_id]
            client_parts[client_id].add(part_num)

        part_opp_count = 0
        for client_id, parts in client_parts.items():
            for part_number in parts:
                opportunities = random.choices(
                    [2, 3, 4, 5, 6, 8, 10, 12],
                    weights=[5, 10, 20, 25, 20, 10, 7, 3],
                    k=1
                )[0]

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
        """Generate 750+ production entries linked to work orders."""
        print("\n[Step 7] Generating Production Entries...")

        prod_entry_count = 0
        target_entries = 750

        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE and prod_entry_count < target_entries:
            # Skip some weekends (70% chance to skip)
            if current_date.weekday() >= 5 and random.random() < 0.7:
                current_date += timedelta(days=1)
                continue

            for client_id in self.client_ids:
                if prod_entry_count >= target_entries:
                    break

                # Get work orders for this client
                client_wos = [wo for wo, c in self.work_order_to_client.items() if c == client_id]

                if not client_wos:
                    continue

                # 2-4 production entries per client per day
                num_entries = random.randint(2, 4)

                for _ in range(num_entries):
                    if prod_entry_count >= target_entries:
                        break

                    wo_id = random.choice(client_wos)
                    job = random.choice([j for j, w in self.job_to_work_order.items() if w == wo_id]) if any(w == wo_id for w in self.job_to_work_order.values()) else None

                    entry_id = f"PROD-{wo_id[-8:]}-{current_date.strftime('%Y%m%d')}-{prod_entry_count+1:05d}"

                    # Production metrics
                    units_produced = random.randint(50, 350)
                    run_time_hours = round(random.uniform(4, 8), 2)
                    employees_assigned = random.randint(3, 12)
                    employees_present = max(1, employees_assigned - random.randint(0, 2))

                    # Quality metrics with realistic defect rates (0.5-4%)
                    defect_rate = random.uniform(0.005, 0.04)
                    defect_count = int(units_produced * defect_rate)
                    scrap_count = int(defect_count * random.uniform(0.1, 0.4))
                    rework_count = defect_count - scrap_count

                    # Calculate efficiency (75-115% of ideal)
                    efficiency = round(random.uniform(75, 115), 2)
                    performance = round(random.uniform(70, 110), 2)
                    quality_rate = round((1 - defect_rate) * 100, 2)

                    ideal_cycle = round(random.uniform(0.15, 0.60), 4)
                    actual_cycle = round(run_time_hours / units_produced if units_produced > 0 else 0, 4)

                    self.cursor.execute("""
                        INSERT INTO PRODUCTION_ENTRY (
                            production_entry_id, client_id, product_id, shift_id, work_order_id, job_id,
                            production_date, shift_date, units_produced, run_time_hours,
                            employees_assigned, employees_present, defect_count, scrap_count, rework_count,
                            setup_time_hours, downtime_hours, ideal_cycle_time, actual_cycle_time,
                            efficiency_percentage, performance_percentage, quality_rate,
                            notes, entered_by, entry_method, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        entry_id, client_id, random.choice(self.product_ids),
                        random.choice(self.shift_ids), wo_id, job,
                        current_date.strftime('%Y-%m-%d'), current_date.strftime('%Y-%m-%d'),
                        units_produced, run_time_hours, employees_assigned, employees_present,
                        defect_count, scrap_count, rework_count,
                        round(random.uniform(0.25, 1.5), 2),
                        round(random.uniform(0, 0.75), 2),
                        ideal_cycle, actual_cycle,
                        efficiency, performance, quality_rate,
                        f"Production entry for {current_date.strftime('%Y-%m-%d')}",
                        1,  # entered_by placeholder
                        "MANUAL_ENTRY"
                    ))

                    self.production_entry_ids.append(entry_id)
                    prod_entry_count += 1

            current_date += timedelta(days=1)

        self.conn.commit()
        self.stats["production_entries"] = len(self.production_entry_ids)
        print(f"   Created {len(self.production_entry_ids)} production entries over 90 days")

    def generate_quality_entries(self) -> None:
        """Generate 120+ quality entries linked to work orders."""
        print("\n[Step 8] Generating Quality Entries...")

        quality_entry_count = 0
        target_entries = 120

        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE and quality_entry_count < target_entries:
            # Skip weekends with 80% probability
            if current_date.weekday() >= 5 and random.random() < 0.8:
                current_date += timedelta(days=1)
                continue

            for client_id in self.client_ids:
                if quality_entry_count >= target_entries:
                    break

                client_wos = [wo for wo, c in self.work_order_to_client.items() if c == client_id]

                if not client_wos:
                    continue

                # 1-2 quality entries per client per day (not every day)
                if random.random() < 0.6:
                    continue

                num_entries = random.randint(1, 2)

                for _ in range(num_entries):
                    if quality_entry_count >= target_entries:
                        break

                    wo_id = random.choice(client_wos)

                    entry_id = f"QE-{wo_id[-8:]}-{current_date.strftime('%Y%m%d')}-{quality_entry_count+1:04d}"

                    units_inspected = random.randint(80, 500)

                    # Calculate defect metrics (1-6% defect rate)
                    defect_rate = random.uniform(0.01, 0.06)
                    units_defective = int(units_inspected * defect_rate)
                    units_passed = units_inspected - units_defective

                    # Total defects can be higher than units (multiple defects per unit)
                    total_defects = int(units_defective * random.uniform(1, 2.5))

                    units_scrapped = int(units_defective * random.uniform(0.1, 0.3))
                    units_reworked = units_defective - units_scrapped

                    inspection_stages = ["INCOMING", "IN_PROCESS", "FINAL", "AUDIT"]

                    self.cursor.execute("""
                        INSERT INTO QUALITY_ENTRY (
                            quality_entry_id, client_id, work_order_id, shift_date, inspection_date,
                            units_inspected, units_passed, units_defective, total_defects_count,
                            inspection_stage, is_first_pass, units_scrapped, units_reworked,
                            inspector_id, notes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        entry_id, client_id, wo_id,
                        current_date.strftime('%Y-%m-%d'),
                        current_date.strftime('%Y-%m-%d'),
                        units_inspected, units_passed, units_defective, total_defects,
                        random.choice(inspection_stages),
                        1 if random.random() > 0.15 else 0,
                        units_scrapped,
                        units_reworked,
                        1,  # inspector_id placeholder
                        f"Quality inspection for {current_date.strftime('%Y-%m-%d')}"
                    ))

                    self.quality_entry_ids.append(entry_id)
                    self.quality_to_client[entry_id] = client_id
                    self.quality_to_wo[entry_id] = wo_id
                    quality_entry_count += 1

            current_date += timedelta(days=1)

        self.conn.commit()
        self.stats["quality_entries"] = len(self.quality_entry_ids)
        print(f"   Created {len(self.quality_entry_ids)} quality entries")

    def generate_attendance_entries(self) -> None:
        """Generate 5500+ attendance entries (90 days for 80 regular employees)."""
        print("\n[Step 9] Generating Attendance Entries...")

        attendance_count = 0
        absent_count = 0

        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE:
            # Skip weekends completely
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            for emp_id in self.regular_employee_ids:
                client_id = self.employee_to_client.get(emp_id)
                if not client_id:
                    continue

                scheduled_hours = 8.00

                # Determine attendance status (88% present, 12% some form of absence)
                attendance_roll = random.random()

                if attendance_roll < 0.88:
                    # Present
                    is_absent = 0
                    actual_hours = scheduled_hours - round(random.uniform(0, 0.5), 2)
                    absence_type = None
                    is_late = 1 if random.random() < 0.08 else 0
                elif attendance_roll < 0.94:
                    # Unscheduled absence
                    is_absent = 1
                    actual_hours = 0
                    absence_type = "UNSCHEDULED_ABSENCE"
                    is_late = 0
                    absent_count += 1
                elif attendance_roll < 0.97:
                    # Medical leave
                    is_absent = 1
                    actual_hours = 0
                    absence_type = "MEDICAL_LEAVE"
                    is_late = 0
                    absent_count += 1
                else:
                    # Vacation or personal leave
                    is_absent = 1
                    actual_hours = 0
                    absence_type = random.choice(["VACATION", "PERSONAL_LEAVE"])
                    is_late = 0
                    absent_count += 1

                att_entry_id = f"ATT-{emp_id}-{current_date.strftime('%Y%m%d')}"

                self.cursor.execute("""
                    INSERT INTO ATTENDANCE_ENTRY (
                        attendance_entry_id, client_id, employee_id, shift_date, shift_id,
                        scheduled_hours, actual_hours, absence_hours, is_absent, absence_type, is_late,
                        entered_by, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    att_entry_id, client_id, emp_id,
                    current_date.strftime('%Y-%m-%d'),
                    random.choice(self.shift_ids),
                    scheduled_hours, actual_hours,
                    scheduled_hours - actual_hours if is_absent else 0,
                    is_absent, absence_type, is_late,
                    1,  # entered_by placeholder
                    absence_type if is_absent else None
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
        print("\n[Step 10] Generating Shift Coverage Entries...")

        coverage_count = 0

        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            for client_id in self.client_ids:
                for shift_id in self.shift_ids:
                    required = random.randint(12, 20)
                    actual = max(0, required - random.randint(0, 4))
                    coverage_pct = round((actual / required) * 100, 2) if required > 0 else 0

                    self.cursor.execute("""
                        INSERT INTO SHIFT_COVERAGE (
                            client_id, shift_id, coverage_date, required_employees,
                            actual_employees, coverage_percentage, entered_by, notes, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (
                        client_id, shift_id, current_date.strftime('%Y-%m-%d'),
                        required, actual, coverage_pct,
                        1,  # entered_by placeholder
                        f"Shift coverage for {current_date.strftime('%Y-%m-%d')}"
                    ))
                    coverage_count += 1

            current_date += timedelta(days=1)

        self.conn.commit()
        self.stats["shift_coverage"] = coverage_count
        print(f"   Created {coverage_count} shift coverage entries")

    def generate_downtime_entries(self) -> None:
        """Generate 120+ downtime entries with various reasons."""
        print("\n[Step 11] Generating Downtime Entries...")

        downtime_count = 0
        target_entries = 120

        current_date = DATA_START_DATE
        while current_date <= DATA_END_DATE and downtime_count < target_entries:
            if current_date.weekday() >= 5 and random.random() < 0.85:
                current_date += timedelta(days=1)
                continue

            for client_id in self.client_ids:
                if downtime_count >= target_entries:
                    break

                client_wos = [wo for wo, c in self.work_order_to_client.items() if c == client_id]

                if not client_wos:
                    continue

                # 25% chance of downtime per client per day
                if random.random() < 0.25:
                    wo_id = random.choice(client_wos)

                    reason = random.choice(DOWNTIME_REASONS)
                    description = random.choice(DOWNTIME_DESCRIPTIONS[reason])

                    # Duration varies by reason type (15 min to 4 hours)
                    duration = random.randint(15, 240)

                    dt_entry_id = f"DT-{wo_id[-8:]}-{current_date.strftime('%Y%m%d')}-{downtime_count+1:04d}"

                    self.cursor.execute("""
                        INSERT INTO DOWNTIME_ENTRY (
                            downtime_entry_id, client_id, work_order_id, shift_date,
                            downtime_reason, downtime_duration_minutes,
                            root_cause_category, reported_by, notes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        dt_entry_id, client_id, wo_id,
                        current_date.strftime('%Y-%m-%d'),
                        reason, duration,
                        reason,
                        1,  # reported_by placeholder
                        description
                    ))
                    downtime_count += 1

            current_date += timedelta(days=1)

        self.conn.commit()
        self.stats["downtime_entries"] = downtime_count
        print(f"   Created {downtime_count} downtime entries")

    def generate_hold_entries(self) -> None:
        """Generate 55+ hold entries (some ON_HOLD, some RELEASED)."""
        print("\n[Step 12] Generating Hold Entries...")

        hold_count = 0
        target_holds = 55

        # Select work orders for holds
        wo_sample = random.sample(self.work_order_ids, min(target_holds + 10, len(self.work_order_ids)))

        for wo_id in wo_sample:
            if hold_count >= target_holds:
                break

            client_id = self.work_order_to_client[wo_id]
            wo_start = self.wo_dates.get(wo_id, DATA_START_DATE)

            hold_date = wo_start + timedelta(days=random.randint(1, 20))
            if hold_date > DATA_END_DATE:
                hold_date = DATA_END_DATE - timedelta(days=random.randint(1, 10))

            # 65% of holds are released
            is_released = random.random() < 0.65
            resume_date = hold_date + timedelta(days=random.randint(1, 14)) if is_released else None
            if resume_date and resume_date > DATA_END_DATE:
                resume_date = DATA_END_DATE

            hold_duration = (resume_date - hold_date).total_seconds() / 3600 if resume_date else None

            hold_entry_id = f"HOLD-{wo_id[-8:]}-{hold_count+1:04d}"
            hold_status = "RESUMED" if is_released else "ON_HOLD"

            hold_reason = random.choice(HOLD_REASONS)
            hold_category = random.choice(HOLD_REASON_CATEGORIES)

            self.cursor.execute("""
                INSERT INTO HOLD_ENTRY (
                    hold_entry_id, client_id, work_order_id, hold_status,
                    hold_date, resume_date, total_hold_duration_hours,
                    hold_reason_category, hold_reason_description,
                    hold_initiated_by, resumed_by, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                hold_entry_id, client_id, wo_id, hold_status,
                hold_date.strftime('%Y-%m-%d'),
                resume_date.strftime('%Y-%m-%d') if resume_date else None,
                round(hold_duration, 2) if hold_duration else None,
                hold_category,
                hold_reason,
                1,  # hold_initiated_by placeholder
                1 if is_released else None,  # resumed_by placeholder
                f"Hold entry: {hold_reason}"
            ))
            hold_count += 1

        self.conn.commit()
        self.stats["hold_entries"] = hold_count
        print(f"   Created {hold_count} hold entries")

    def generate_defect_details(self) -> None:
        """Generate defect details linked to quality entries."""
        print("\n[Step 13] Generating Defect Details...")

        defect_count = 0

        for qe_id in self.quality_entry_ids:
            # 50% of quality entries have detailed defects
            if random.random() < 0.50:
                client_id = self.quality_to_client[qe_id]

                # 1-5 different defect types per quality entry
                num_defects = random.randint(1, 5)

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
                        random.randint(1, 20),
                        random.choice(DEFECT_SEVERITIES),
                        random.choice(DEFECT_LOCATIONS),
                        f"Found {defect_type.lower()} defect during inspection"
                    ))
                    defect_count += 1

        self.conn.commit()
        self.stats["defect_details"] = defect_count
        print(f"   Created {defect_count} defect detail records")

    def generate_alerts(self) -> None:
        """Generate alerts for various KPI issues."""
        print("\n[Step 14] Generating Alerts...")

        alert_count = 0

        alert_templates = [
            ("production", "Production Below Target", "Production output is below the daily target"),
            ("quality", "Quality Rate Below Threshold", "Quality rate has fallen below acceptable levels"),
            ("delivery", "Potential OTD Risk", "Work order at risk of missing delivery date"),
            ("attendance", "High Absenteeism Detected", "Absenteeism rate exceeds threshold"),
            ("efficiency", "Efficiency Drop Detected", "Line efficiency has dropped significantly"),
            ("maintenance", "Equipment Maintenance Required", "Equipment showing signs of wear"),
        ]

        for client_id in self.client_ids:
            # 3-6 alerts per client
            num_alerts = random.randint(3, 6)

            for _ in range(num_alerts):
                category, title, base_message = random.choice(alert_templates)
                severity = random.choice(ALERT_SEVERITIES)
                status = random.choices(ALERT_STATUSES, weights=[0.4, 0.3, 0.3])[0]

                wo_id = random.choice([wo for wo, c in self.work_order_to_client.items() if c == client_id]) if random.random() > 0.3 else None

                alert_id = f"ALT-{client_id[:4]}-{alert_count+1:05d}"

                current_value = round(random.uniform(50, 95), 2)
                threshold_value = round(random.uniform(80, 95), 2)
                predicted_value = round(random.uniform(40, 90), 2) if random.random() > 0.5 else None
                confidence = round(random.uniform(0.6, 0.95), 2) if predicted_value else None

                created_at = DATA_START_DATE + timedelta(days=random.randint(0, 85))
                acknowledged_at = created_at + timedelta(hours=random.randint(1, 24)) if status in ["acknowledged", "resolved"] else None
                resolved_at = acknowledged_at + timedelta(hours=random.randint(1, 48)) if status == "resolved" else None

                self.cursor.execute("""
                    INSERT INTO ALERT (
                        alert_id, category, severity, status, title, message, recommendation,
                        client_id, kpi_key, work_order_id, current_value, threshold_value,
                        predicted_value, confidence, created_at, acknowledged_at, acknowledged_by,
                        resolved_at, resolved_by, resolution_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert_id, category, severity, status, title,
                    f"{base_message} for {client_id}",
                    f"Review {category} metrics and take corrective action",
                    client_id, f"{category}_rate", wo_id,
                    current_value, threshold_value, predicted_value, confidence,
                    created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    acknowledged_at.strftime('%Y-%m-%d %H:%M:%S') if acknowledged_at else None,
                    self._get_random_user_id() if acknowledged_at else None,
                    resolved_at.strftime('%Y-%m-%d %H:%M:%S') if resolved_at else None,
                    self._get_random_user_id() if resolved_at else None,
                    "Issue addressed and metrics normalized" if status == "resolved" else None
                ))

                self.alert_ids.append(alert_id)
                alert_count += 1

        self.conn.commit()
        self.stats["alerts"] = alert_count
        print(f"   Created {alert_count} alerts")

    def generate_alert_history(self) -> None:
        """Generate alert history records for prediction tracking."""
        print("\n[Step 15] Generating Alert History (CRITICAL - was empty)...")

        history_count = 0

        for alert_id in self.alert_ids:
            # 60% of alerts have history records
            if random.random() < 0.60:
                # 1-4 history records per alert
                num_records = random.randint(1, 4)

                for i in range(num_records):
                    history_id = f"AH-{alert_id[-10:]}-{i+1:02d}"

                    prediction_date = DATA_START_DATE + timedelta(days=random.randint(0, 80))
                    actual_date = prediction_date + timedelta(days=random.randint(1, 7)) if random.random() > 0.2 else None

                    predicted_value = round(random.uniform(50, 95), 2)
                    actual_value = round(predicted_value * random.uniform(0.85, 1.15), 2) if actual_date else None

                    was_accurate = None
                    error_percent = None
                    if actual_value is not None:
                        error_percent = round(abs(predicted_value - actual_value) / predicted_value * 100, 2)
                        was_accurate = 1 if error_percent < 10 else 0

                    self.cursor.execute("""
                        INSERT INTO ALERT_HISTORY (
                            history_id, alert_id, predicted_value, actual_value,
                            prediction_date, actual_date, was_accurate, error_percent, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (
                        history_id, alert_id, predicted_value, actual_value,
                        prediction_date.strftime('%Y-%m-%d %H:%M:%S'),
                        actual_date.strftime('%Y-%m-%d %H:%M:%S') if actual_date else None,
                        was_accurate, error_percent
                    ))
                    history_count += 1

        self.conn.commit()
        self.stats["alert_history"] = history_count
        print(f"   Created {history_count} alert history records")

    def verify_data(self) -> Dict[str, int]:
        """Verify all data was created correctly."""
        print("\n[Step 16] Verifying Data...")

        tables = [
            "USER", "CLIENT", "SHIFT", "PRODUCT", "EMPLOYEE",
            "WORK_ORDER", "JOB", "PART_OPPORTUNITIES",
            "PRODUCTION_ENTRY", "QUALITY_ENTRY", "ATTENDANCE_ENTRY",
            "SHIFT_COVERAGE", "DOWNTIME_ENTRY", "HOLD_ENTRY",
            "DEFECT_DETAIL", "ALERT", "ALERT_HISTORY"
        ]

        counts = {}
        for table in tables:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = self.cursor.fetchone()[0]

        return counts

    def print_summary(self, counts: Dict[str, int]) -> None:
        """Print generation summary with statistics."""
        print("\n" + "=" * 70)
        print("DATA REGENERATION COMPLETE - Summary Statistics")
        print("=" * 70)

        print("\n PRESERVED Tables (not regenerated):")
        print(f"   USER:                 {counts.get('USER', 0):>6} (PRESERVED)")
        print(f"   CLIENT:               {counts.get('CLIENT', 0):>6} (PRESERVED)")

        print("\n Base Tables:")
        print(f"   SHIFT:                {counts.get('SHIFT', 0):>6}")
        print(f"   PRODUCT:              {counts.get('PRODUCT', 0):>6}")
        print(f"   EMPLOYEE:             {counts.get('EMPLOYEE', 0):>6}")

        print("\n Work Order Tables:")
        print(f"   WORK_ORDER:           {counts.get('WORK_ORDER', 0):>6}")
        print(f"   JOB:                  {counts.get('JOB', 0):>6}")
        print(f"   PART_OPPORTUNITIES:   {counts.get('PART_OPPORTUNITIES', 0):>6}")

        print("\n Entry Tables (90 days):")
        print(f"   PRODUCTION_ENTRY:     {counts.get('PRODUCTION_ENTRY', 0):>6}")
        print(f"   QUALITY_ENTRY:        {counts.get('QUALITY_ENTRY', 0):>6}")
        print(f"   ATTENDANCE_ENTRY:     {counts.get('ATTENDANCE_ENTRY', 0):>6}")
        print(f"   SHIFT_COVERAGE:       {counts.get('SHIFT_COVERAGE', 0):>6}")
        print(f"   DOWNTIME_ENTRY:       {counts.get('DOWNTIME_ENTRY', 0):>6}")
        print(f"   HOLD_ENTRY:           {counts.get('HOLD_ENTRY', 0):>6}")
        print(f"   DEFECT_DETAIL:        {counts.get('DEFECT_DETAIL', 0):>6}")

        print("\n Alert Tables:")
        print(f"   ALERT:                {counts.get('ALERT', 0):>6}")
        print(f"   ALERT_HISTORY:        {counts.get('ALERT_HISTORY', 0):>6}")

        total_records = sum(counts.values())
        print(f"\n   TOTAL RECORDS:        {total_records:>6}")
        print("=" * 70)

    def run(self) -> None:
        """Execute the full data regeneration pipeline."""
        try:
            # Clear existing data first (except USER)
            self.clear_existing_data()

            # Generate in proper FK order
            self.generate_shifts()              # Step 1
            self.generate_products()            # Step 2
            self.generate_employees()           # Step 3
            self.generate_work_orders()         # Step 4
            self.generate_jobs()                # Step 5
            self.generate_part_opportunities()  # Step 6
            self.generate_production_entries()  # Step 7
            self.generate_quality_entries()     # Step 8
            self.generate_attendance_entries()  # Step 9
            self.generate_shift_coverage()      # Step 10
            self.generate_downtime_entries()    # Step 11
            self.generate_hold_entries()        # Step 12
            self.generate_defect_details()      # Step 13
            self.generate_alerts()              # Step 14
            self.generate_alert_history()       # Step 15

            # Verify and print summary
            counts = self.verify_data()
            self.print_summary(counts)

            print("\n Data regeneration completed successfully!")
            print(" USER table was PRESERVED with all 11 users intact.")

        except Exception as e:
            self.conn.rollback()
            print(f"\n ERROR: Data regeneration failed: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            self.conn.execute("PRAGMA foreign_keys = ON")  # Re-enable FK checks
            self.conn.close()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for the data regenerator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Regenerate comprehensive sample data for KPI Operations Platform (preserves USER table)"
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

    generator = ComprehensiveDataRegenerator(db_path=args.db, seed=args.seed)
    generator.run()


if __name__ == "__main__":
    main()
