#!/usr/bin/env python3
"""
Initialize Demo Database
Creates tables and seeds with comprehensive demo data for platform demonstration.
Run: python -m scripts.init_demo_database

Business Workflow Order:
  Capacity Planning (plan) -> KPI Operations (execute) -> Simulation (analyze)

Documentation requirements (from LAUNCH_GUIDE_FINAL.md and QUICKSTART.md):
- Admin credentials: admin / admin123
- 5 clients visible in dropdown
- Users: admin, supervisor1, operator1, operator2 with password123
- Global settings: USER_PREFERENCES, DASHBOARD_WIDGET_DEFAULTS, ALERT_CONFIG
"""
import sys
import os
import uuid
import json
import random
from datetime import datetime, date, timedelta
from decimal import Decimal
import random

# Ensure backend module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import engine, Base, SessionLocal
from backend.tests.fixtures.factories import TestDataFactory
from backend.schemas import ClientType, WorkOrderStatus, HoldStatus

# Import all models to ensure they're registered with Base
from backend.schemas.client import Client
from backend.schemas.user import User
from backend.schemas.employee import Employee
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.schemas.work_order import WorkOrder
from backend.schemas.job import Job
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.quality_entry import QualityEntry
from backend.schemas.attendance_entry import AttendanceEntry
from backend.schemas.downtime_entry import DowntimeEntry
from backend.schemas.hold_entry import HoldEntry
from backend.schemas.defect_type_catalog import DefectTypeCatalog
from backend.schemas.defect_detail import DefectDetail
from backend.schemas.part_opportunities import PartOpportunities
from backend.schemas.floating_pool import FloatingPool
from backend.schemas.coverage_entry import CoverageEntry
from backend.schemas.saved_filter import SavedFilter, FilterHistory
from backend.schemas.workflow import WorkflowTransitionLog
from backend.schemas.user_preferences import UserPreferences, DashboardWidgetDefaults
from backend.models.alert import Alert, AlertConfig, AlertHistory
from backend.schemas.client_config import ClientConfig, OTDMode
from backend.schemas.kpi_threshold import KPIThreshold

# Import ALL capacity planning models
from backend.schemas.capacity import (
    CapacityCalendar,
    CapacityProductionLine,
    CapacityOrder, OrderPriority, OrderStatus,
    CapacityProductionStandard,
    CapacityBOMHeader, CapacityBOMDetail,
    CapacityStockSnapshot,
    CapacityComponentCheck, ComponentStatus,
    CapacityAnalysis,
    CapacitySchedule, CapacityScheduleDetail, ScheduleStatus,
    CapacityScenario,
    CapacityKPICommitment,
)

# ============================================================================
# MASTER PRODUCT CATALOG
# Single source of truth for product data used across ALL modules.
# Total SAM / 60 = cycle_time_hours (e.g., 9.0/60 = 0.15h)
# ============================================================================
MASTER_PRODUCTS = [
    {
        "code": "TSHIRT-100",
        "name": "Basic T-Shirt Assembly",
        "cycle_h": Decimal("0.15"),
        "sam": {"CUT": 0.6, "SEW": 7.5, "FIN": 0.9},
        "bom": [
            {"code": "FABRIC-JERSEY", "desc": "Jersey Fabric", "qty": Decimal("0.5"), "uom": "M", "waste": Decimal("5"), "type": "FABRIC"},
            {"code": "THREAD-POLY", "desc": "Polyester Thread", "qty": Decimal("60"), "uom": "M", "waste": Decimal("2"), "type": "TRIM"},
            {"code": "LABEL-CARE", "desc": "Care Label", "qty": Decimal("1"), "uom": "EA", "waste": Decimal("0"), "type": "ACCESSORY"},
        ],
    },
    {
        "code": "POLO-200",
        "name": "Polo Shirt Production",
        "cycle_h": Decimal("0.25"),
        "sam": {"CUT": 0.8, "SEW": 12.5, "FIN": 1.7},
        "bom": [
            {"code": "FABRIC-PIQUE", "desc": "Pique Fabric", "qty": Decimal("0.7"), "uom": "M", "waste": Decimal("6"), "type": "FABRIC"},
            {"code": "THREAD-POLY", "desc": "Polyester Thread", "qty": Decimal("80"), "uom": "M", "waste": Decimal("2"), "type": "TRIM"},
            {"code": "BUTTON-POLO", "desc": "Polo Buttons", "qty": Decimal("3"), "uom": "EA", "waste": Decimal("1"), "type": "ACCESSORY"},
            {"code": "LABEL-CARE", "desc": "Care Label", "qty": Decimal("1"), "uom": "EA", "waste": Decimal("0"), "type": "ACCESSORY"},
        ],
    },
    {
        "code": "JACKET-300",
        "name": "Work Jacket Assembly",
        "cycle_h": Decimal("0.50"),
        "sam": {"CUT": 1.5, "SEW": 25.0, "FIN": 3.5},
        "bom": [
            {"code": "FABRIC-TWILL", "desc": "Twill Fabric", "qty": Decimal("1.5"), "uom": "M", "waste": Decimal("8"), "type": "FABRIC"},
            {"code": "THREAD-HEAVY", "desc": "Heavy-Duty Thread", "qty": Decimal("120"), "uom": "M", "waste": Decimal("3"), "type": "TRIM"},
            {"code": "ZIPPER-MAIN", "desc": "Main Zipper", "qty": Decimal("1"), "uom": "EA", "waste": Decimal("1"), "type": "ACCESSORY"},
            {"code": "LABEL-CARE", "desc": "Care Label", "qty": Decimal("1"), "uom": "EA", "waste": Decimal("0"), "type": "ACCESSORY"},
        ],
    },
    {
        "code": "PANTS-400",
        "name": "Work Pants Assembly",
        "cycle_h": Decimal("0.35"),
        "sam": {"CUT": 1.0, "SEW": 17.5, "FIN": 2.5},
        "bom": [
            {"code": "FABRIC-TWILL", "desc": "Twill Fabric", "qty": Decimal("1.2"), "uom": "M", "waste": Decimal("7"), "type": "FABRIC"},
            {"code": "THREAD-HEAVY", "desc": "Heavy-Duty Thread", "qty": Decimal("100"), "uom": "M", "waste": Decimal("3"), "type": "TRIM"},
            {"code": "ZIPPER-FLY", "desc": "Fly Zipper", "qty": Decimal("1"), "uom": "EA", "waste": Decimal("1"), "type": "ACCESSORY"},
            {"code": "BUTTON-METAL", "desc": "Metal Button", "qty": Decimal("1"), "uom": "EA", "waste": Decimal("1"), "type": "ACCESSORY"},
            {"code": "LABEL-CARE", "desc": "Care Label", "qty": Decimal("1"), "uom": "EA", "waste": Decimal("0"), "type": "ACCESSORY"},
        ],
    },
    {
        "code": "DRESS-500",
        "name": "Dress Production",
        "cycle_h": Decimal("0.45"),
        "sam": {"CUT": 1.2, "SEW": 22.0, "FIN": 3.8},
        "bom": [
            {"code": "FABRIC-CREPE", "desc": "Crepe Fabric", "qty": Decimal("1.8"), "uom": "M", "waste": Decimal("10"), "type": "FABRIC"},
            {"code": "THREAD-FINE", "desc": "Fine Thread", "qty": Decimal("110"), "uom": "M", "waste": Decimal("2"), "type": "TRIM"},
            {"code": "ZIPPER-INVIS", "desc": "Invisible Zipper", "qty": Decimal("1"), "uom": "EA", "waste": Decimal("1"), "type": "ACCESSORY"},
            {"code": "LABEL-CARE", "desc": "Care Label", "qty": Decimal("1"), "uom": "EA", "waste": Decimal("0"), "type": "ACCESSORY"},
        ],
    },
]

# Collect all unique BOM component codes across all products for stock seeding
_ALL_COMPONENTS = {}
for _prod in MASTER_PRODUCTS:
    for _comp in _prod["bom"]:
        if _comp["code"] not in _ALL_COMPONENTS:
            _ALL_COMPONENTS[_comp["code"]] = {
                "desc": _comp["desc"],
                "uom": _comp["uom"],
                "type": _comp["type"],
            }


def init_database():
    """Initialize database with schema and comprehensive demo data."""
    print("=" * 70)
    print("KPI Operations Platform - Comprehensive Database Initialization")
    print("=" * 70)

    # ==================================================================
    # Step 1: Create all tables (including capacity planning)
    # ==================================================================
    print("\n[1/10] Creating database schema...")
    Base.metadata.create_all(bind=engine)

    from backend.db.migrations.capacity_planning_tables import create_capacity_tables
    created_tables = create_capacity_tables()
    if created_tables:
        print(f"  + Created {len(created_tables)} capacity planning tables")

    print("  All tables created")

    db = SessionLocal()

    try:
        # ==============================================================
        # Step 2: Foundation Data - Clients, Users, Employees
        # ==============================================================
        print("\n[2/10] Creating clients, users, and employees...")

        clients_data = [
            ("ACME-MFG", "ACME Manufacturing Co.", ClientType.HOURLY_RATE),
            ("TEXTILE-PRO", "Textile Professionals Inc.", ClientType.PIECE_RATE),
            ("FASHION-WORKS", "Fashion Works Ltd.", ClientType.HOURLY_RATE),
            ("QUALITY-STITCH", "Quality Stitch Factory", ClientType.PIECE_RATE),
            ("GLOBAL-APPAREL", "Global Apparel Solutions", ClientType.HOURLY_RATE),
        ]

        clients = {}
        for client_id, client_name, client_type in clients_data:
            client = TestDataFactory.create_client(
                db,
                client_id=client_id,
                client_name=client_name,
                client_type=client_type
            )
            clients[client_id] = client

        # Client configs
        for client_id in clients.keys():
            config = ClientConfig(
                client_id=client_id,
                otd_mode=OTDMode.STANDARD,
                default_cycle_time_hours=0.25,
                efficiency_target_percent=85.0,
                quality_target_ppm=10000.0,
                fpy_target_percent=95.0,
                dpmo_opportunities_default=1,
                availability_target_percent=90.0,
                performance_target_percent=95.0,
                oee_target_percent=85.0,
                absenteeism_target_percent=3.0,
                wip_aging_threshold_days=7,
                wip_critical_threshold_days=14,
            )
            db.add(config)
        db.flush()

        # Users
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        users_data = [
            # (username, password, role, client_id, full_name)
            ("admin", "admin123", "admin", None, "System Administrator"),
            # ACME-MFG
            ("supervisor1", "password123", "supervisor", "ACME-MFG", "John Supervisor"),
            ("operator1", "password123", "operator", "ACME-MFG", "Mike Operator"),
            ("operator2", "password123", "operator", "ACME-MFG", "Sarah Operator"),
            # TEXTILE-PRO
            ("supervisor2", "password123", "supervisor", "TEXTILE-PRO", "Jane Supervisor"),
            ("operator3", "password123", "operator", "TEXTILE-PRO", "Tom Operator"),
            # FASHION-WORKS
            ("supervisor3", "password123", "supervisor", "FASHION-WORKS", "Ana Supervisor"),
            ("operator4", "password123", "operator", "FASHION-WORKS", "Carlos Operator"),
            # QUALITY-STITCH
            ("supervisor4", "password123", "supervisor", "QUALITY-STITCH", "Maria Supervisor"),
            ("operator5", "password123", "operator", "QUALITY-STITCH", "David Operator"),
            # GLOBAL-APPAREL
            ("supervisor5", "password123", "supervisor", "GLOBAL-APPAREL", "Elena Supervisor"),
            ("operator6", "password123", "operator", "GLOBAL-APPAREL", "James Operator"),
            # Multi-client / global roles
            ("leader1", "password123", "leader", "ACME-MFG,TEXTILE-PRO", "Lisa Leader"),
            ("poweruser", "password123", "poweruser", None, "Power User"),
        ]

        users = {}
        for username, password, role, client_id, full_name in users_data:
            user = User(
                user_id=f"USER-{username.upper()}",
                username=username,
                email=f"{username}@kpi-operations.com",
                password_hash=pwd_context.hash(password),
                full_name=full_name,
                role=role,
                client_id_assigned=client_id,
                is_active=True,
            )
            db.add(user)
            users[username] = user
        db.flush()

        # Employees (8 per client, last 2 floating pool)
        all_employees = {}
        for client_id in clients.keys():
            client_employees = []
            for i in range(8):
                emp = TestDataFactory.create_employee(
                    db,
                    client_id=client_id,
                    employee_name=f"Employee {client_id[:4]}-{i+1:02d}",
                    employee_code=f"EMP-{client_id[:4]}-{i+1:03d}",
                    is_floating_pool=(i >= 6)
                )
                client_employees.append(emp)
            all_employees[client_id] = client_employees

        total_employees = sum(len(v) for v in all_employees.values())
        print(f"  Created {len(clients)} clients, {len(users)} users, {total_employees} employees")
        print("    Admin: admin / admin123")
        print("    Others: supervisor1, operator1, etc. / password123")

        # ==============================================================
        # Step 3: Products & Shifts (using MASTER_PRODUCTS)
        # ==============================================================
        print("\n[3/10] Creating products and shifts...")

        products = []
        for mp in MASTER_PRODUCTS:
            prod = TestDataFactory.create_product(
                db,
                product_code=mp["code"],
                product_name=mp["name"],
                ideal_cycle_time=mp["cycle_h"],
            )
            products.append(prod)

        shifts_data = [
            ("Morning Shift", "06:00:00", "14:00:00"),
            ("Afternoon Shift", "14:00:00", "22:00:00"),
            ("Night Shift", "22:00:00", "06:00:00"),
        ]

        shifts = []
        for name, start, end in shifts_data:
            shift = TestDataFactory.create_shift(db, shift_name=name, start_time=start, end_time=end)
            shifts.append(shift)

        db.flush()
        print(f"  Created {len(products)} products and {len(shifts)} shifts")

        # ==============================================================
        # Step 4: Capacity Planning - Core Tables
        # Business drives everything: plan FIRST, then execute.
        # ==============================================================
        print("\n[4/10] Creating Capacity Planning core data (calendar, lines, orders, standards, BOMs, stock)...")

        today = date.today()
        # Track entities we'll need in Step 5 for computed tables
        all_cap_lines = {}   # client_id -> list of CapacityProductionLine
        all_cap_orders = {}  # client_id -> list of CapacityOrder
        capacity_counts = {}

        for client_id in clients.keys():
            # 4a. Master Calendar - 84 days (12 weeks)
            calendar_entries = []
            for i in range(84):
                cal_date = today + timedelta(days=i)
                is_weekend = cal_date.weekday() >= 5
                is_working = not is_weekend
                entry = CapacityCalendar(
                    client_id=client_id,
                    calendar_date=cal_date,
                    is_working_day=is_working,
                    shifts_available=2 if is_working else 0,
                    shift1_hours=8.0 if is_working else 0,
                    shift2_hours=8.0 if is_working else 0,
                    shift3_hours=0,
                    holiday_name="Weekend" if is_weekend else None,
                )
                calendar_entries.append(entry)
            db.add_all(calendar_entries)

            # 4b. Production Lines (4 lines)
            lines_data = [
                {"code": f"{client_id[:4]}_CUT_01", "name": "Cutting Line 1", "dept": "CUTTING", "capacity": 500, "ops": 8},
                {"code": f"{client_id[:4]}_SEW_01", "name": "Sewing Line 1", "dept": "SEWING", "capacity": 120, "ops": 25},
                {"code": f"{client_id[:4]}_SEW_02", "name": "Sewing Line 2", "dept": "SEWING", "capacity": 100, "ops": 20},
                {"code": f"{client_id[:4]}_FIN_01", "name": "Finishing Line 1", "dept": "FINISHING", "capacity": 200, "ops": 12},
            ]
            line_entries = []
            for ld in lines_data:
                line_entry = CapacityProductionLine(
                    client_id=client_id,
                    line_code=ld["code"],
                    line_name=ld["name"],
                    department=ld["dept"],
                    standard_capacity_units_per_hour=ld["capacity"],
                    max_operators=ld["ops"],
                    efficiency_factor=0.85,
                    absenteeism_factor=0.05,
                    is_active=True,
                )
                line_entries.append(line_entry)
            db.add_all(line_entries)
            db.flush()
            all_cap_lines[client_id] = line_entries

            # 4c. Capacity Orders (5 per client, one per MASTER_PRODUCT)
            order_quantities = [1000, 2000, 500, 1500, 800]
            order_entries = []
            for idx, mp in enumerate(MASTER_PRODUCTS):
                order_entry = CapacityOrder(
                    client_id=client_id,
                    order_number=f"CPO-{client_id[:4]}-{idx+1:03d}",
                    customer_name=clients[client_id].client_name,
                    style_code=mp["code"],
                    style_description=mp["name"],
                    order_quantity=order_quantities[idx],
                    required_date=today + timedelta(days=21 + idx * 7),
                    priority=OrderPriority.HIGH if idx == 0 else (OrderPriority.URGENT if idx == 2 else OrderPriority.NORMAL),
                    status=OrderStatus.IN_PROGRESS if idx < 2 else OrderStatus.CONFIRMED,
                    notes=f"Capacity order for {mp['name']}",
                )
                order_entries.append(order_entry)
            db.add_all(order_entries)
            db.flush()
            all_cap_orders[client_id] = order_entries

            # 4d. Production Standards (3 ops per style, using MASTER_PRODUCTS SAM values)
            standards_entries = []
            op_labels = {
                "CUT": "Cutting Operation",
                "SEW": "Sewing Operation",
                "FIN": "Finishing Operation",
            }
            op_depts = {"CUT": "CUTTING", "SEW": "SEWING", "FIN": "FINISHING"}
            for mp in MASTER_PRODUCTS:
                for op_code, sam_val in mp["sam"].items():
                    std_entry = CapacityProductionStandard(
                        client_id=client_id,
                        style_code=mp["code"],
                        operation_code=op_code,
                        operation_name=f"{op_code} - {op_labels[op_code]}",
                        department=op_depts[op_code],
                        sam_minutes=sam_val,
                    )
                    standards_entries.append(std_entry)
            db.add_all(standards_entries)
            db.flush()

            # 4e. BOM Headers + Details (per style)
            bom_count = 0
            for mp in MASTER_PRODUCTS:
                header = CapacityBOMHeader(
                    client_id=client_id,
                    parent_item_code=mp["code"],
                    parent_item_description=f"BOM for {mp['name']}",
                    style_code=mp["code"],
                    revision="1.0",
                    is_active=True,
                )
                db.add(header)
                db.flush()

                for comp in mp["bom"]:
                    detail = CapacityBOMDetail(
                        header_id=header.id,
                        client_id=client_id,
                        component_item_code=comp["code"],
                        component_description=comp["desc"],
                        quantity_per=comp["qty"],
                        unit_of_measure=comp["uom"],
                        waste_percentage=comp["waste"],
                        component_type=comp["type"],
                    )
                    db.add(detail)
                    bom_count += 1
            db.flush()

            # 4f. Stock Snapshots (all unique components across all products)
            stock_quantities = {
                "FABRIC-JERSEY": Decimal("5000"),
                "FABRIC-PIQUE": Decimal("3000"),
                "FABRIC-TWILL": Decimal("4000"),
                "FABRIC-CREPE": Decimal("2000"),
                "THREAD-POLY": Decimal("500000"),
                "THREAD-HEAVY": Decimal("300000"),
                "THREAD-FINE": Decimal("200000"),
                "LABEL-CARE": Decimal("100000"),
                "BUTTON-POLO": Decimal("20000"),
                "BUTTON-METAL": Decimal("15000"),
                "ZIPPER-MAIN": Decimal("5000"),
                "ZIPPER-FLY": Decimal("8000"),
                "ZIPPER-INVIS": Decimal("3000"),
            }
            stock_entries = []
            for comp_code, comp_info in _ALL_COMPONENTS.items():
                oh = stock_quantities.get(comp_code, Decimal("10000"))
                stock_entry = CapacityStockSnapshot(
                    client_id=client_id,
                    snapshot_date=today,
                    item_code=comp_code,
                    item_description=comp_info["desc"],
                    on_hand_quantity=oh,
                    allocated_quantity=Decimal("0"),
                    on_order_quantity=Decimal("0"),
                    available_quantity=oh,
                    unit_of_measure=comp_info["uom"],
                )
                stock_entries.append(stock_entry)
            db.add_all(stock_entries)

            capacity_counts[client_id] = {
                "calendar": len(calendar_entries),
                "lines": len(line_entries),
                "orders": len(order_entries),
                "standards": len(standards_entries),
                "bom_details": bom_count,
                "stock": len(stock_entries),
            }

        db.flush()

        total_core = sum(sum(c.values()) for c in capacity_counts.values())
        print(f"  Created {total_core} capacity planning core records across {len(clients)} clients")
        print("    Per client: Calendar (84d), 4 Lines, 5 Orders, 15 Standards, BOMs, Stock")

        # ==============================================================
        # Step 5: Capacity Planning - Computed Tables (6 previously empty)
        # ==============================================================
        print("\n[5/10] Creating Capacity Planning computed data (component check, analysis, schedule, scenarios, KPI commitments)...")

        computed_counts = {"component_check": 0, "analysis": 0, "schedule": 0, "schedule_detail": 0, "scenario": 0, "kpi_commitment": 0}

        for client_id in clients.keys():
            cap_orders = all_cap_orders[client_id]
            cap_lines = all_cap_lines[client_id]

            # 5a. Component Check - explode BOMs, compare vs stock
            for order in cap_orders:
                mp = next(m for m in MASTER_PRODUCTS if m["code"] == order.style_code)
                for comp in mp["bom"]:
                    waste_mult = 1 + float(comp["waste"]) / 100
                    required = float(comp["qty"]) * order.order_quantity * waste_mult
                    available = float(stock_quantities.get(comp["code"], 10000))
                    shortage = max(0, required - available)
                    status = CapacityComponentCheck.calculate_status(required, available)

                    cc = CapacityComponentCheck(
                        client_id=client_id,
                        run_date=today,
                        order_id=order.id,
                        order_number=order.order_number,
                        component_item_code=comp["code"],
                        component_description=comp["desc"],
                        required_quantity=Decimal(str(round(required, 4))),
                        available_quantity=Decimal(str(available)),
                        shortage_quantity=Decimal(str(round(shortage, 4))),
                        status=status,
                    )
                    db.add(cc)
                    computed_counts["component_check"] += 1

            # 5b. Analysis - 12-step capacity calculation per line
            # Count working days in next 4 weeks
            working_days_4w = sum(
                1 for i in range(28)
                if (today + timedelta(days=i)).weekday() < 5
            )
            # Calculate total demand hours from orders (distribute across departments)
            total_order_qty = sum(o.order_quantity for o in cap_orders)
            # Demand by department from SAM values
            dept_demand_minutes = {"CUTTING": 0, "SEWING": 0, "FINISHING": 0}
            for order in cap_orders:
                mp = next(m for m in MASTER_PRODUCTS if m["code"] == order.style_code)
                dept_demand_minutes["CUTTING"] += mp["sam"]["CUT"] * order.order_quantity
                dept_demand_minutes["SEWING"] += mp["sam"]["SEW"] * order.order_quantity
                dept_demand_minutes["FINISHING"] += mp["sam"]["FIN"] * order.order_quantity

            for line in cap_lines:
                dept = line.department
                # Split sewing demand across 2 lines (SEW_01 gets 55%, SEW_02 gets 45%)
                if dept == "SEWING":
                    sew_total = dept_demand_minutes["SEWING"] / 60  # convert to hours
                    if "SEW_01" in line.line_code:
                        demand_h = sew_total * 0.55
                    else:
                        demand_h = sew_total * 0.45
                elif dept == "CUTTING":
                    demand_h = dept_demand_minutes["CUTTING"] / 60
                else:
                    demand_h = dept_demand_minutes["FINISHING"] / 60

                analysis = CapacityAnalysis(
                    client_id=client_id,
                    analysis_date=today,
                    line_id=line.id,
                    line_code=line.line_code,
                    department=line.department,
                    working_days=working_days_4w,
                    shifts_per_day=2,
                    hours_per_shift=Decimal("8.0"),
                    operators_available=line.max_operators,
                    efficiency_factor=line.efficiency_factor,
                    absenteeism_factor=line.absenteeism_factor,
                    demand_hours=Decimal(str(round(demand_h, 2))),
                    demand_units=total_order_qty if dept != "SEWING" else int(total_order_qty * (0.55 if "SEW_01" in line.line_code else 0.45)),
                )
                analysis.calculate_metrics()
                db.add(analysis)
                computed_counts["analysis"] += 1

            # 5c. Schedule + Details
            period_start = today
            period_end = today + timedelta(days=27)  # 4 weeks
            schedule = CapacitySchedule(
                client_id=client_id,
                schedule_name=f"Week {today.isocalendar()[1]} Plan",
                period_start=period_start,
                period_end=period_end,
                status=ScheduleStatus.DRAFT,
                notes="Auto-generated demo schedule",
            )
            db.add(schedule)
            db.flush()
            computed_counts["schedule"] += 1

            # Schedule details: distribute orders across lines and working days
            work_day_offset = 0
            seq = 1
            for order in cap_orders:
                mp = next(m for m in MASTER_PRODUCTS if m["code"] == order.style_code)
                # Assign to sewing line 1 (main line)
                sew_line = cap_lines[1]  # SEW_01
                # Spread over ~4 working days per order
                daily_qty = order.order_quantity // 4
                remainder = order.order_quantity % 4
                for d in range(4):
                    sched_date = today + timedelta(days=work_day_offset)
                    # Skip weekends
                    while sched_date.weekday() >= 5:
                        work_day_offset += 1
                        sched_date = today + timedelta(days=work_day_offset)

                    qty = daily_qty + (remainder if d == 3 else 0)
                    detail = CapacityScheduleDetail(
                        schedule_id=schedule.id,
                        client_id=client_id,
                        order_id=order.id,
                        order_number=order.order_number,
                        style_code=order.style_code,
                        line_id=sew_line.id,
                        line_code=sew_line.line_code,
                        scheduled_date=sched_date,
                        scheduled_quantity=qty,
                        completed_quantity=0,
                        sequence=seq,
                    )
                    db.add(detail)
                    computed_counts["schedule_detail"] += 1
                    seq += 1
                    work_day_offset += 1

            # 5d. Scenarios (3 per client)
            scenarios_data = [
                {
                    "name": "Overtime on Sewing Lines",
                    "type": "OVERTIME",
                    "params": {
                        "overtime_percent": 20,
                        "affected_lines": [cap_lines[1].line_code, cap_lines[2].line_code],
                        "days": ["MON", "TUE", "WED", "THU", "FRI"],
                    },
                    "results": {
                        "original_capacity_hours": 6400,
                        "new_capacity_hours": 7680,
                        "capacity_increase_percent": 20,
                        "cost_impact": 12500,
                        "utilization_before": 96.5,
                        "utilization_after": 80.4,
                        "bottlenecks_resolved": [cap_lines[1].line_code],
                    },
                },
                {
                    "name": "Add 3rd Sewing Line",
                    "type": "NEW_LINE",
                    "params": {
                        "new_line_code": f"{client_id[:4]}_SEW_03",
                        "new_line_name": "Sewing Line 3",
                        "department": "SEWING",
                        "operators": 20,
                        "capacity_units_per_hour": 100,
                    },
                    "results": {
                        "original_capacity_hours": 6400,
                        "new_capacity_hours": 9600,
                        "capacity_increase_percent": 50,
                        "cost_impact": 45000,
                        "utilization_before": 96.5,
                        "utilization_after": 64.3,
                        "bottlenecks_resolved": [cap_lines[1].line_code, cap_lines[2].line_code],
                    },
                },
                {
                    "name": "Subcontract 40% Cutting",
                    "type": "SUBCONTRACT",
                    "params": {
                        "subcontract_percent": 40,
                        "affected_department": "CUTTING",
                        "cost_per_unit": 2.50,
                        "lead_time_days": 5,
                    },
                    "results": {
                        "original_capacity_hours": 1600,
                        "new_capacity_hours": 2240,
                        "capacity_increase_percent": 40,
                        "cost_impact": 8750,
                        "utilization_before": 72.0,
                        "utilization_after": 51.4,
                        "bottlenecks_resolved": [],
                    },
                },
            ]
            for sd in scenarios_data:
                scenario = CapacityScenario(
                    client_id=client_id,
                    scenario_name=sd["name"],
                    scenario_type=sd["type"],
                    base_schedule_id=schedule.id,
                    parameters_json=sd["params"],
                    results_json=sd["results"],
                    is_active=True,
                    notes=f"Demo scenario: {sd['name']}",
                )
                db.add(scenario)
                computed_counts["scenario"] += 1

            # 5e. KPI Commitments (4 per client, linked to schedule)
            kpi_defs = [
                ("efficiency", "Production Efficiency", Decimal("85.0")),
                ("quality", "Quality Rate", Decimal("98.5")),
                ("otd", "On-Time Delivery", Decimal("95.0")),
                ("utilization", "Capacity Utilization", Decimal("88.0")),
            ]
            for kpi_key, kpi_name, committed_val in kpi_defs:
                commitment = CapacityKPICommitment(
                    client_id=client_id,
                    schedule_id=schedule.id,
                    kpi_key=kpi_key,
                    kpi_name=kpi_name,
                    period_start=period_start,
                    period_end=period_end,
                    committed_value=committed_val,
                    actual_value=None,
                    variance=None,
                    variance_percent=None,
                    notes="Committed with draft schedule",
                )
                db.add(commitment)
                computed_counts["kpi_commitment"] += 1

        db.flush()
        print(f"  Created computed capacity data across {len(clients)} clients:")
        print(f"    Component Checks: {computed_counts['component_check']}")
        print(f"    Analysis Records: {computed_counts['analysis']}")
        print(f"    Schedules: {computed_counts['schedule']}, Details: {computed_counts['schedule_detail']}")
        print(f"    Scenarios: {computed_counts['scenario']}")
        print(f"    KPI Commitments: {computed_counts['kpi_commitment']}")

        db.commit()

        # ==============================================================
        # Step 6: Work Orders, Jobs, and Part Opportunities
        # Style codes match MASTER_PRODUCTS (capacity order alignment)
        # ==============================================================
        print("\n[6/10] Creating work orders, jobs, and part opportunities...")

        base_date = date.today() - timedelta(days=30)
        all_work_orders = {}

        for client_id, client in clients.items():
            client_work_orders = []
            # 3 work orders per client (first 3 MASTER_PRODUCTS)
            for i in range(3):
                mp = MASTER_PRODUCTS[i]
                wo = TestDataFactory.create_work_order(
                    db,
                    client_id=client_id,
                    work_order_id=f"WO-{client_id[:4]}-{i+1:03d}",
                    style_model=mp["code"],
                    status=WorkOrderStatus.IN_PROGRESS if i < 2 else WorkOrderStatus.RECEIVED,
                    planned_quantity=1000 * (i + 1),
                    received_date=datetime.combine(base_date + timedelta(days=i * 5), datetime.min.time()),
                    planned_ship_date=datetime.combine(base_date + timedelta(days=30 + i * 5), datetime.min.time()),
                )
                # Set required_date and actual_delivery_date for OTD calculation
                # Dates must fall within "Last 30 Days" dashboard filter
                if i == 0:
                    # On time: required Feb 7, delivered Feb 6
                    wo.required_date = datetime.combine(base_date + timedelta(days=25), datetime.min.time())
                    wo.actual_delivery_date = datetime.combine(base_date + timedelta(days=24), datetime.min.time())
                    wo.actual_quantity = wo.planned_quantity
                elif i == 1:
                    # Late: required Feb 2, delivered Feb 10 (8 days late)
                    wo.required_date = datetime.combine(base_date + timedelta(days=20), datetime.min.time())
                    wo.actual_delivery_date = datetime.combine(base_date + timedelta(days=28), datetime.min.time())
                    wo.actual_quantity = wo.planned_quantity
                else:
                    # Still in progress: due in 10 days, no delivery yet
                    wo.required_date = datetime.combine(date.today() + timedelta(days=10), datetime.min.time())
                client_work_orders.append(wo)

                # 2 jobs per work order
                for j in range(2):
                    job = TestDataFactory.create_job(
                        db,
                        work_order_id=wo.work_order_id,
                        client_id=client_id,
                        job_id=f"JOB-{client_id[:4]}-{i+1:03d}-{j+1}",
                        part_number=f"PART-{client_id[:4]}-{i+1:03d}-{j+1}",
                        quantity_required=wo.planned_quantity // 2 if wo.planned_quantity else 500,
                    )
                    TestDataFactory.create_part_opportunities(
                        db,
                        part_number=job.part_number,
                        client_id=client_id,
                        opportunities_per_unit=10,
                    )

            all_work_orders[client_id] = client_work_orders

        total_work_orders = sum(len(v) for v in all_work_orders.values())
        print(f"  Created {total_work_orders} work orders with jobs and part opportunities")

        # ==============================================================
        # Step 7: Execution Data (production, quality, attendance, downtime, holds)
        # ==============================================================
        print("\n[7/10] Creating execution data (production, quality, attendance, downtime, holds)...")

        for client_id, client in clients.items():
            client_work_orders = all_work_orders[client_id]

            # Find supervisor for this client
            supervisor_user = None
            for u in users.values():
                if u.role == "supervisor" and u.client_id_assigned and client_id in u.client_id_assigned:
                    supervisor_user = u
                    break
            if not supervisor_user:
                supervisor_user = users["admin"]

            # Production entries (10 per client) with realistic KPI values
            wo_ids = [wo.work_order_id for wo in client_work_orders]
            random.seed(hash(client_id))  # Deterministic per client
            base_date = date.today() - timedelta(days=10)
            for i in range(10):
                prod_idx = i % len(products)
                product = products[prod_idx]
                units = 1000 + (i * 50)
                run_time = Decimal("8.0")
                defects = max(1, int(units * random.uniform(0.003, 0.012)))
                scrap = max(0, defects // 3)
                rework = defects - scrap
                efficiency = Decimal(str(round(random.uniform(78, 95), 2)))
                performance = Decimal(str(round(random.uniform(82, 98), 2)))
                quality = Decimal(str(round(100 - (defects + scrap) / units * 100, 2)))
                ideal_ct = product.ideal_cycle_time or Decimal("0.15")
                actual_ct = run_time / units

                work_order_id = wo_ids[i % len(wo_ids)] if wo_ids else None
                entry = ProductionEntry(
                    production_entry_id=f"PE-{client_id[:4]}-{i+1:03d}",
                    client_id=client_id,
                    product_id=product.product_id,
                    shift_id=shifts[0].shift_id,
                    entered_by=supervisor_user.user_id,
                    production_date=datetime.combine(base_date + timedelta(days=i), datetime.min.time()),
                    shift_date=datetime.combine(base_date + timedelta(days=i), datetime.min.time()),
                    units_produced=units,
                    employees_assigned=5,
                    employees_present=random.choice([4, 5, 5, 5]),
                    run_time_hours=run_time,
                    defect_count=defects,
                    scrap_count=scrap,
                    rework_count=rework,
                    ideal_cycle_time=ideal_ct,
                    actual_cycle_time=actual_ct,
                    efficiency_percentage=efficiency,
                    performance_percentage=performance,
                    quality_rate=quality,
                    work_order_id=work_order_id,
                )
                db.add(entry)

            # Quality entries
            if client_work_orders:
                TestDataFactory.create_quality_entries_batch(
                    db,
                    work_order_id=client_work_orders[0].work_order_id,
                    client_id=client_id,
                    inspector_id=supervisor_user.user_id,
                    count=5,
                    defect_rate=0.005,
                )

            # Attendance entries
            for emp in all_employees[client_id][:3]:
                TestDataFactory.create_attendance_entries_batch(
                    db,
                    employee_id=emp.employee_id,
                    client_id=client_id,
                    shift_id=shifts[0].shift_id,
                    count=10,
                    attendance_rate=0.92,
                )

            # Downtime entries
            if client_work_orders:
                operator_user = None
                for u in users.values():
                    if u.role == "operator" and u.client_id_assigned and client_id in u.client_id_assigned:
                        operator_user = u
                        break
                if not operator_user:
                    operator_user = supervisor_user

                for i, reason in enumerate(["EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "SETUP_CHANGEOVER"]):
                    TestDataFactory.create_downtime_entry(
                        db,
                        client_id=client_id,
                        work_order_id=client_work_orders[0].work_order_id,
                        reported_by=operator_user.user_id,
                        downtime_reason=reason,
                    )

            # Hold entries (varied ages for realistic WIP aging)
            if client_work_orders:
                hold_ages = [3, 8, 15]  # days ago: within target, borderline, overdue
                hold_reasons = ["QUALITY_ISSUE", "MATERIAL_SHORTAGE", "CUSTOMER_REQUEST"]
                for h_idx, (age, reason) in enumerate(zip(hold_ages, hold_reasons)):
                    hold_wo = client_work_orders[h_idx % len(client_work_orders)]
                    TestDataFactory.create_hold_entry(
                        db,
                        work_order_id=hold_wo.work_order_id,
                        client_id=client_id,
                        created_by=supervisor_user.user_id,
                        hold_reason=reason,
                        hold_status=HoldStatus.ON_HOLD,
                        hold_date=datetime.now() - timedelta(days=age),
                    )

        print(f"  Created execution data for {len(clients)} clients")
        db.commit()

        # ==============================================================
        # Step 8: Defect Type Catalog
        # ==============================================================
        print("\n[8/10] Creating defect type catalog...")

        defect_types = [
            ("STITCH", "Stitching Defect", "WORKMANSHIP"),
            ("FABRIC", "Fabric Defect", "MATERIAL"),
            ("SIZING", "Size Variation", "MEASUREMENT"),
            ("COLOR", "Color Variation", "APPEARANCE"),
            ("TRIM", "Trim Defect", "COMPONENT"),
            ("SEAM", "Seam Defect", "WORKMANSHIP"),
            ("PRINT", "Print Defect", "APPEARANCE"),
            ("LABEL", "Label Defect", "COMPONENT"),
        ]

        for client_id in clients.keys():
            for code, name, category in defect_types:
                defect = DefectTypeCatalog(
                    defect_type_id=f"DT-{client_id[:4]}-{code}",
                    client_id=client_id,
                    defect_code=code,
                    defect_name=name,
                    category=category,
                    is_active=True,
                )
                db.add(defect)

        print(f"  Created {len(defect_types) * len(clients)} defect type catalog entries")

        # ==============================================================
        # Step 9: Global Settings & Configurations
        # ==============================================================
        print("\n[9/10] Creating global settings and configurations...")

        # Dashboard Widget Defaults
        widget_configs = [
            ("admin", "kpi_summary", "KPI Summary", 1, True, '{"refreshInterval": 300}'),
            ("admin", "production_chart", "Production Chart", 2, True, '{"chartType": "bar"}'),
            ("admin", "quality_metrics", "Quality Metrics", 3, True, '{}'),
            ("admin", "alerts_panel", "Alerts Panel", 4, True, '{}'),
            ("admin", "efficiency_gauge", "Efficiency Gauge", 5, True, '{}'),
            ("supervisor", "production_chart", "Production Chart", 1, True, '{"chartType": "line"}'),
            ("supervisor", "quality_metrics", "Quality Metrics", 2, True, '{}'),
            ("supervisor", "attendance_summary", "Attendance Summary", 3, True, '{}'),
            ("supervisor", "alerts_panel", "Alerts Panel", 4, True, '{}'),
            ("operator", "my_production", "My Production", 1, True, '{}'),
            ("operator", "shift_summary", "Shift Summary", 2, True, '{}'),
            ("operator", "quality_entry", "Quality Entry", 3, True, '{}'),
        ]

        for role, widget_key, widget_name, order, visible, config in widget_configs:
            widget = DashboardWidgetDefaults(
                role=role,
                widget_key=widget_key,
                widget_name=widget_name,
                widget_order=order,
                is_visible=visible,
                default_config=config,
            )
            db.add(widget)

        print(f"  Created {len(widget_configs)} dashboard widget defaults")

        # Alert Configurations
        alert_configs = [
            (None, "efficiency", True, 75.0, 60.0),
            (None, "quality_ppm", True, 5000.0, 10000.0),
            (None, "otd", True, 90.0, 80.0),
            (None, "absenteeism", True, 5.0, 10.0),
            ("ACME-MFG", "efficiency", True, 80.0, 65.0),
            ("TEXTILE-PRO", "quality_ppm", True, 3000.0, 8000.0),
        ]

        for client_id, alert_type, enabled, warning, critical in alert_configs:
            config = AlertConfig(
                config_id=f"ALERT-CFG-{uuid.uuid4().hex[:8].upper()}",
                client_id=client_id,
                alert_type=alert_type,
                enabled=enabled,
                warning_threshold=warning,
                critical_threshold=critical,
            )
            db.add(config)

        print(f"  Created {len(alert_configs)} alert configurations")

        # KPI Thresholds
        kpi_thresholds = [
            ("efficiency", 85.0, 75.0, 60.0, "%", "Y"),
            ("performance", 95.0, 85.0, 70.0, "%", "Y"),
            ("quality_rate", 99.0, 97.0, 95.0, "%", "Y"),
            ("oee", 85.0, 75.0, 60.0, "%", "Y"),
            ("ppm", 5000.0, 10000.0, 20000.0, "ppm", "N"),
            ("fpy", 95.0, 90.0, 85.0, "%", "Y"),
            ("availability", 90.0, 80.0, 70.0, "%", "Y"),
            ("absenteeism", 3.0, 5.0, 10.0, "%", "N"),
            ("otd", 95.0, 90.0, 80.0, "%", "Y"),
        ]

        for kpi_key, target, warning, critical, unit, higher in kpi_thresholds:
            threshold = KPIThreshold(
                threshold_id=f"KPI-TH-{kpi_key.upper()}",
                client_id=None,
                kpi_key=kpi_key,
                target_value=target,
                warning_threshold=warning,
                critical_threshold=critical,
                unit=unit,
                higher_is_better=higher,
            )
            db.add(threshold)

        print(f"  Created {len(kpi_thresholds)} KPI thresholds (global defaults)")

        # Active Alerts
        alert_data = [
            ("Efficiency Below Target", "efficiency", "warning", "ACME-MFG"),
            ("OTD at Risk", "otd", "warning", "TEXTILE-PRO"),
            ("Quality PPM Elevated", "quality", "warning", "FASHION-WORKS"),
            ("Attendance Below Target", "attendance", "critical", "QUALITY-STITCH"),
            ("Equipment Downtime Alert", "availability", "info", "GLOBAL-APPAREL"),
        ]

        for title, category, severity, client_id in alert_data:
            alert = Alert(
                alert_id=f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                client_id=client_id,
                category=category,
                severity=severity,
                status="active",
                title=title,
                message=f"Demo alert for {category} monitoring in {client_id}",
            )
            db.add(alert)

        print(f"  Created {len(alert_data)} demo alerts")

        db.commit()

        # ==============================================================
        # Step 10: Summary Report
        # ==============================================================
        print("\n[10/10] Generating summary...")

        counts = {
            "Clients": db.query(Client).count(),
            "Users": db.query(User).count(),
            "Employees": db.query(Employee).count(),
            "Products": len(products),
            "Shifts": len(shifts),
            "Work Orders": db.query(WorkOrder).count(),
            "Jobs": db.query(Job).count(),
            "Production Entries": db.query(ProductionEntry).count(),
            "Quality Entries": db.query(QualityEntry).count(),
            "Attendance Entries": db.query(AttendanceEntry).count(),
            "Downtime Entries": db.query(DowntimeEntry).count(),
            "Hold Entries": db.query(HoldEntry).count(),
            "Defect Type Catalog": db.query(DefectTypeCatalog).count(),
            "Dashboard Widget Defaults": db.query(DashboardWidgetDefaults).count(),
            "Alert Configurations": db.query(AlertConfig).count(),
            "Active Alerts": db.query(Alert).count(),
            # Capacity Planning - Core
            "Cap. Calendar Entries": db.query(CapacityCalendar).count(),
            "Cap. Production Lines": db.query(CapacityProductionLine).count(),
            "Cap. Orders": db.query(CapacityOrder).count(),
            "Cap. Standards": db.query(CapacityProductionStandard).count(),
            "Cap. BOM Headers": db.query(CapacityBOMHeader).count(),
            "Cap. BOM Details": db.query(CapacityBOMDetail).count(),
            "Cap. Stock Snapshots": db.query(CapacityStockSnapshot).count(),
            # Capacity Planning - Computed (previously empty)
            "Cap. Component Checks": db.query(CapacityComponentCheck).count(),
            "Cap. Analysis Records": db.query(CapacityAnalysis).count(),
            "Cap. Schedules": db.query(CapacitySchedule).count(),
            "Cap. Schedule Details": db.query(CapacityScheduleDetail).count(),
            "Cap. Scenarios": db.query(CapacityScenario).count(),
            "Cap. KPI Commitments": db.query(CapacityKPICommitment).count(),
        }

        print("\n" + "=" * 70)
        print("Database Initialization Complete!")
        print("=" * 70)
        print("\nComprehensive Data Summary:")
        for entity, count in counts.items():
            print(f"  {entity}: {count}")

        print("\n" + "-" * 70)
        print("Demo Login Credentials:")
        print("-" * 70)
        print("  Admin:        admin / admin123 (Full access)")
        print("  Supervisors:  supervisor1-5 / password123 (one per client)")
        print("  Operators:    operator1-6 / password123 (one+ per client)")
        print("  Leader:       leader1 / password123 (ACME-MFG, TEXTILE-PRO)")
        print("  Power User:   poweruser / password123 (Full access)")
        print("-" * 70)
        print("\nClients Available:")
        for client_id, client in clients.items():
            print(f"  {client_id}: {client.client_name}")
        print("-" * 70)

    except Exception as e:
        db.rollback()
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
