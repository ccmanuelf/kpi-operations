#!/usr/bin/env python3
"""
Initialize Demo Database
Creates tables and seeds with comprehensive demo data for platform demonstration.
Run: python -m scripts.init_demo_database

Documentation requirements (from LAUNCH_GUIDE_FINAL.md and QUICKSTART.md):
- Admin credentials: admin / admin123
- 5 clients visible in dropdown
- Users: admin, supervisor1, operator1, operator2 with password123
- Global settings: USER_PREFERENCES, DASHBOARD_WIDGET_DEFAULTS, ALERT_CONFIG
"""
import sys
import os
import uuid
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


def init_database():
    """Initialize database with schema and comprehensive demo data."""
    print("=" * 70)
    print("KPI Operations Platform - Comprehensive Database Initialization")
    print("=" * 70)

    # Step 1: Create all tables
    print("\n[1/7] Creating database schema...")
    Base.metadata.create_all(bind=engine)
    print("  ✓ All tables created")

    db = SessionLocal()

    try:
        # ================================================================
        # Step 2: Create 5 Clients (Companies)
        # ================================================================
        print("\n[2/7] Creating 5 clients (companies)...")

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

        print(f"  ✓ Created {len(clients)} clients")

        # Create CLIENT_CONFIG for each client (required for workflow)
        print("  Creating client configurations...")
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
        print(f"  ✓ Created {len(clients)} client configurations")

        # ================================================================
        # Step 3: Create Users (matching documentation)
        # ================================================================
        print("\n[3/7] Creating users with documented credentials...")

        # Import User schema and password hashing
        from backend.schemas.user import User
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        users_data = [
            # (username, password, role, client_id, full_name)
            ("admin", "admin123", "admin", None, "System Administrator"),
            ("supervisor1", "password123", "supervisor", "ACME-MFG", "John Supervisor"),
            ("supervisor2", "password123", "supervisor", "TEXTILE-PRO", "Jane Supervisor"),
            ("operator1", "password123", "operator", "ACME-MFG", "Mike Operator"),
            ("operator2", "password123", "operator", "ACME-MFG", "Sarah Operator"),
            ("operator3", "password123", "operator", "TEXTILE-PRO", "Tom Operator"),
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
        print(f"  ✓ Created {len(users)} users")
        print("    Admin: admin / admin123")
        print("    Others: supervisor1, operator1, etc. / password123")

        # ================================================================
        # Step 4: Create Products and Shifts (Global)
        # ================================================================
        print("\n[4/7] Creating products and shifts...")

        products_data = [
            ("PROD-SHIRT-001", "T-Shirt Assembly", Decimal("0.15")),
            ("PROD-POLO-001", "Polo Shirt Production", Decimal("0.25")),
            ("PROD-JACKET-001", "Work Jacket Assembly", Decimal("0.50")),
            ("PROD-PANTS-001", "Work Pants Assembly", Decimal("0.35")),
            ("PROD-DRESS-001", "Dress Production", Decimal("0.45")),
        ]

        products = []
        for code, name, cycle_time in products_data:
            prod = TestDataFactory.create_product(db, product_code=code, product_name=name, ideal_cycle_time=cycle_time)
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
        print(f"  ✓ Created {len(products)} products and {len(shifts)} shifts")

        # ================================================================
        # Step 5: Create Employees for each Client
        # ================================================================
        print("\n[5/7] Creating employees for each client...")

        all_employees = {}
        for client_id in clients.keys():
            client_employees = []
            for i in range(8):  # 8 employees per client
                emp = TestDataFactory.create_employee(
                    db,
                    client_id=client_id,
                    employee_name=f"Employee {client_id[:4]}-{i+1:02d}",
                    employee_code=f"EMP-{client_id[:4]}-{i+1:03d}",
                    is_floating_pool=(i >= 6)  # Last 2 are floating pool
                )
                client_employees.append(emp)
            all_employees[client_id] = client_employees

        total_employees = sum(len(v) for v in all_employees.values())
        print(f"  ✓ Created {total_employees} employees across {len(clients)} clients")

        # ================================================================
        # Step 6: Create Work Orders, Jobs, and Related Data
        # ================================================================
        print("\n[6/7] Creating work orders and comprehensive production data...")

        base_date = date.today() - timedelta(days=30)
        all_work_orders = {}

        for client_id, client in clients.items():
            client_work_orders = []
            # 3 work orders per client
            for i in range(3):
                wo = TestDataFactory.create_work_order(
                    db,
                    client_id=client_id,
                    work_order_id=f"WO-{client_id[:4]}-{i+1:03d}",
                    style_model=f"STYLE-{client_id[:4]}-{i+1:03d}",
                    status=WorkOrderStatus.IN_PROGRESS if i < 2 else WorkOrderStatus.RECEIVED,
                    planned_quantity=1000 * (i + 1),
                    received_date=datetime.combine(base_date + timedelta(days=i * 5), datetime.min.time()),
                    planned_ship_date=datetime.combine(base_date + timedelta(days=30 + i * 5), datetime.min.time()),
                )
                client_work_orders.append(wo)

                # Create 2 jobs per work order
                for j in range(2):
                    job = TestDataFactory.create_job(
                        db,
                        work_order_id=wo.work_order_id,
                        client_id=client_id,
                        job_id=f"JOB-{client_id[:4]}-{i+1:03d}-{j+1}",
                        part_number=f"PART-{client_id[:4]}-{i+1:03d}-{j+1}",
                        quantity_required=wo.planned_quantity // 2 if wo.planned_quantity else 500
                    )
                    # Create part opportunities
                    TestDataFactory.create_part_opportunities(
                        db,
                        part_number=job.part_number,
                        client_id=client_id,
                        opportunities_per_unit=10
                    )

            all_work_orders[client_id] = client_work_orders

            # Get supervisor for this client
            supervisor_user = None
            for u in users.values():
                if u.role == "supervisor" and u.client_id_assigned and client_id in u.client_id_assigned:
                    supervisor_user = u
                    break
            if not supervisor_user:
                supervisor_user = users["admin"]

            # Create production entries (10 per client)
            wo_ids = [wo.work_order_id for wo in client_work_orders]
            TestDataFactory.create_production_entries_batch(
                db,
                client_id=client_id,
                product_id=products[0].product_id,
                shift_id=shifts[0].shift_id,
                entered_by=supervisor_user.user_id,
                count=10,
                work_order_ids=wo_ids,
            )

            # Create quality entries
            if client_work_orders:
                TestDataFactory.create_quality_entries_batch(
                    db,
                    work_order_id=client_work_orders[0].work_order_id,
                    client_id=client_id,
                    inspector_id=supervisor_user.user_id,
                    count=5,
                    defect_rate=0.005
                )

            # Create attendance entries
            for emp in all_employees[client_id][:3]:
                TestDataFactory.create_attendance_entries_batch(
                    db,
                    employee_id=emp.employee_id,
                    client_id=client_id,
                    shift_id=shifts[0].shift_id,
                    count=10,
                    attendance_rate=0.92
                )

            # Create downtime entries
            if client_work_orders:
                operator_user = None
                for u in users.values():
                    if u.role == "operator" and u.client_id_assigned and client_id in u.client_id_assigned:
                        operator_user = u
                        break
                if not operator_user:
                    operator_user = supervisor_user

                downtime_reasons = ["EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "SETUP_CHANGEOVER", "MAINTENANCE", "QUALITY_ISSUE"]
                for i, reason in enumerate(downtime_reasons[:3]):
                    TestDataFactory.create_downtime_entry(
                        db,
                        client_id=client_id,
                        work_order_id=client_work_orders[0].work_order_id,
                        reported_by=operator_user.user_id,
                        downtime_reason=reason,
                    )

            # Create hold entry
            if client_work_orders:
                TestDataFactory.create_hold_entry(
                    db,
                    work_order_id=client_work_orders[0].work_order_id,
                    client_id=client_id,
                    created_by=supervisor_user.user_id,
                    hold_reason="QUALITY_ISSUE",
                    hold_status=HoldStatus.ON_HOLD,
                )

        total_work_orders = sum(len(v) for v in all_work_orders.values())
        print(f"  ✓ Created {total_work_orders} work orders with jobs, production, quality data")

        # ================================================================
        # Step 7: Create Global Settings and Configurations
        # ================================================================
        print("\n[7/7] Creating global settings and configurations...")

        # Dashboard Widget Defaults
        from backend.schemas.user_preferences import DashboardWidgetDefaults, UserPreferences

        widget_configs = [
            # Admin widgets
            ("admin", "kpi_summary", "KPI Summary", 1, True, '{"refreshInterval": 300}'),
            ("admin", "production_chart", "Production Chart", 2, True, '{"chartType": "bar"}'),
            ("admin", "quality_metrics", "Quality Metrics", 3, True, '{}'),
            ("admin", "alerts_panel", "Alerts Panel", 4, True, '{}'),
            ("admin", "efficiency_gauge", "Efficiency Gauge", 5, True, '{}'),
            # Supervisor widgets
            ("supervisor", "production_chart", "Production Chart", 1, True, '{"chartType": "line"}'),
            ("supervisor", "quality_metrics", "Quality Metrics", 2, True, '{}'),
            ("supervisor", "attendance_summary", "Attendance Summary", 3, True, '{}'),
            ("supervisor", "alerts_panel", "Alerts Panel", 4, True, '{}'),
            # Operator widgets
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

        print(f"  ✓ Created {len(widget_configs)} dashboard widget defaults")

        # Alert Configurations
        from backend.models.alert import AlertConfig

        alert_configs = [
            (None, "efficiency", True, 75.0, 60.0),  # Global defaults
            (None, "quality_ppm", True, 5000.0, 10000.0),
            (None, "otd", True, 90.0, 80.0),
            (None, "absenteeism", True, 5.0, 10.0),
            ("ACME-MFG", "efficiency", True, 80.0, 65.0),  # Client-specific
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

        print(f"  ✓ Created {len(alert_configs)} alert configurations")

        # KPI Thresholds (global defaults)
        kpi_thresholds = [
            # (kpi_key, target, warning, critical, unit, higher_is_better)
            ("efficiency", 85.0, 75.0, 60.0, "%", "Y"),
            ("performance", 95.0, 85.0, 70.0, "%", "Y"),
            ("quality_rate", 99.0, 97.0, 95.0, "%", "Y"),
            ("oee", 85.0, 75.0, 60.0, "%", "Y"),
            ("ppm", 5000.0, 10000.0, 20000.0, "ppm", "N"),  # Lower is better
            ("fpy", 95.0, 90.0, 85.0, "%", "Y"),
            ("availability", 90.0, 80.0, 70.0, "%", "Y"),
            ("absenteeism", 3.0, 5.0, 10.0, "%", "N"),  # Lower is better
            ("otd", 95.0, 90.0, 80.0, "%", "Y"),
        ]

        threshold_count = 0
        for kpi_key, target, warning, critical, unit, higher in kpi_thresholds:
            threshold = KPIThreshold(
                threshold_id=f"KPI-TH-{kpi_key.upper()}",
                client_id=None,  # Global default
                kpi_key=kpi_key,
                target_value=target,
                warning_threshold=warning,
                critical_threshold=critical,
                unit=unit,
                higher_is_better=higher,
            )
            db.add(threshold)
            threshold_count += 1

        print(f"  ✓ Created {threshold_count} KPI thresholds (global defaults)")

        # Defect Type Catalog (global + per client)
        from backend.schemas.defect_type_catalog import DefectTypeCatalog

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

        print(f"  ✓ Created {len(defect_types) * len(clients)} defect type catalog entries")

        # Active Alerts
        from backend.models.alert import Alert

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

        print(f"  ✓ Created {len(alert_data)} demo alerts")

        db.commit()

        # ================================================================
        # Summary
        # ================================================================
        from backend.schemas.client import Client
        from backend.schemas.employee import Employee
        from backend.schemas.work_order import WorkOrder
        from backend.schemas.production_entry import ProductionEntry
        from backend.schemas.quality_entry import QualityEntry
        from backend.schemas.attendance_entry import AttendanceEntry
        from backend.schemas.downtime_entry import DowntimeEntry
        from backend.schemas.hold_entry import HoldEntry
        from backend.schemas.job import Job

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
        print("  Admin:       admin / admin123 (Full access)")
        print("  Supervisor:  supervisor1 / password123 (ACME-MFG)")
        print("  Operator:    operator1 / password123 (ACME-MFG)")
        print("  Leader:      leader1 / password123 (Multi-client)")
        print("  Power User:  poweruser / password123 (Full access)")
        print("-" * 70)
        print("\nClients Available:")
        for client_id, client in clients.items():
            print(f"  {client_id}: {client.client_name}")
        print("-" * 70)

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
