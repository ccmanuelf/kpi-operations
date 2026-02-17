"""
Demo Data Seeder

Seeds demo data after schema creation during migration.
Creates sample data for demonstration and testing purposes.

Phase C.2: Added capacity planning demo data seeding.
"""
from typing import Callable, Optional, List, Any
from datetime import datetime, timedelta, date, timezone
from decimal import Decimal
import random
import logging
import uuid

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """Hash password for demo data using bcrypt.

    Uses the same hashing mechanism as the auth system
    to ensure compatibility with login verification.

    Args:
        password: Plain text password.

    Returns:
        str: Bcrypt hashed password.
    """
    # Use bcrypt from auth module for compatibility with login
    from backend.auth.jwt import get_password_hash
    return get_password_hash(password)


class DemoDataSeeder:
    """Seed demo data after schema creation.

    Creates sample data for all main entities in the correct order
    to satisfy foreign key constraints.
    """

    def __init__(self, session: Session):
        """Initialize seeder.

        Args:
            session: SQLAlchemy session for target database.
        """
        self.session = session
        self._seeded_counts = {}

    def seed_all(
        self,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> dict:
        """Seed all demo data in correct order.

        Args:
            progress_callback: Optional callback(entity_name) for progress.

        Returns:
            dict: Counts of seeded records by entity.
        """
        seeders = [
            ("clients", self._seed_clients),
            ("users", self._seed_users),
            ("employees", self._seed_employees),
            ("products", self._seed_products),
            ("shifts", self._seed_shifts),
            ("work_orders", self._seed_work_orders),
            ("jobs", self._seed_jobs),
            ("production_entries", self._seed_production_entries),
            ("downtime_entries", self._seed_downtime_entries),
            ("attendance_entries", self._seed_attendance_entries),
            ("quality_entries", self._seed_quality_entries),
            ("hold_entries", self._seed_hold_entries),
            ("defect_type_catalog", self._seed_defect_type_catalog),
            # Phase 6.3: Floating Pool & Coverage
            ("floating_pool", self._seed_floating_pool),
            ("coverage_entries", self._seed_coverage_entries),
            # Phase 10: Workflow Transitions
            ("workflow_transitions", self._seed_workflow_transitions),
            # Phase 3: Domain Events
            ("event_store", self._seed_event_store),
            # Phase C.2: Capacity Planning Demo Data
            ("capacity_planning", self._seed_capacity_planning),
        ]

        logger.info(f"Starting demo data seeding ({len(seeders)} entities)")

        for name, seeder_fn in seeders:
            if progress_callback:
                progress_callback(name)

            try:
                count = seeder_fn()
                self._seeded_counts[name] = count
                self.session.commit()
                logger.debug(f"Seeded {count} {name}")
            except Exception as e:
                logger.error(f"Failed to seed {name}: {e}")
                self.session.rollback()
                raise

        logger.info(f"Demo data seeding complete: {self._seeded_counts}")
        return self._seeded_counts

    def _seed_clients(self) -> int:
        """Seed demo clients."""
        from backend.schemas.client import Client, ClientType

        clients = [
            Client(
                client_id="DEMO-001",
                client_name="Demo Manufacturing Co",
                client_contact="John Demo",
                client_email="demo@example.com",
                client_phone="555-0100",
                location="Building A",
                client_type=ClientType.PIECE_RATE,
                timezone="America/New_York",
                is_active=1,
            ),
            Client(
                client_id="TEST-001",
                client_name="Test Corporation",
                client_contact="Jane Test",
                client_email="test@example.com",
                client_phone="555-0200",
                location="Building B",
                client_type=ClientType.HOURLY_RATE,
                timezone="America/Chicago",
                is_active=1,
            ),
            Client(
                client_id="SAMPLE-001",
                client_name="Sample Industries",
                client_contact="Bob Sample",
                client_email="sample@example.com",
                client_phone="555-0300",
                location="Building C",
                client_type=ClientType.HYBRID,
                timezone="America/Los_Angeles",
                is_active=1,
            ),
        ]
        self.session.add_all(clients)
        return len(clients)

    def _seed_users(self) -> int:
        """Seed demo users."""
        from backend.schemas.user import User, UserRole

        users = [
            User(
                user_id="admin-001",
                username="admin",
                email="admin@kpi-platform.com",
                password_hash=_hash_password("admin123"),
                role=UserRole.ADMIN,
                is_active=1,
            ),
            User(
                user_id="supervisor-001",
                username="supervisor",
                email="supervisor@kpi-platform.com",
                password_hash=_hash_password("super123"),
                role=UserRole.LEADER,  # Leader role for multi-client supervisors
                is_active=1,
                client_id_assigned="DEMO-001",
            ),
            User(
                user_id="operator-001",
                username="operator",
                email="operator@kpi-platform.com",
                password_hash=_hash_password("oper123"),
                role=UserRole.OPERATOR,
                is_active=1,
                client_id_assigned="DEMO-001",
            ),
            # E2E test users with standard test passwords
            User(
                user_id="operator1-001",
                username="operator1",
                email="operator1@kpi-platform.com",
                password_hash=_hash_password("password123"),
                role=UserRole.OPERATOR,
                is_active=1,
                client_id_assigned="DEMO-001",
            ),
            User(
                user_id="leader1-001",
                username="leader1",
                email="leader1@kpi-platform.com",
                password_hash=_hash_password("password123"),
                role=UserRole.LEADER,
                is_active=1,
                client_id_assigned="DEMO-001",
            ),
            User(
                user_id="viewer-001",
                username="viewer",
                email="viewer@kpi-platform.com",
                password_hash=_hash_password("view123"),
                role=UserRole.OPERATOR,  # Read-only operator role
                is_active=1,
                client_id_assigned="DEMO-001",
            ),
        ]
        self.session.add_all(users)
        return len(users)

    def _seed_employees(self) -> int:
        """Seed demo employees.

        Creates employees linked to:
        - Client (DEMO-001 or floating pool)
        - Production Entries (via employee_id)
        - Coverage Entries (via employee_id)
        """
        from backend.schemas.employee import Employee

        employees = []
        for i in range(1, 11):
            emp = Employee(
                employee_code=f"EMP-{i:03d}",
                employee_name=f"Employee Demo {i}",
                client_id_assigned="DEMO-001" if i <= 7 else None,  # 8-10 are floating pool
                is_floating_pool=1 if i > 7 else 0,
                is_active=1,
                department=["CUTTING", "SEWING", "FINISHING"][(i - 1) % 3],
                position="Operator" if i <= 7 else "Floating Operator",
                hire_date=datetime(2023, 1, 1) + timedelta(days=i * 30),
            )
            employees.append(emp)

        self.session.add_all(employees)
        return len(employees)

    def _seed_products(self) -> int:
        """Seed demo products (per-client).

        Creates products that link to Capacity Planning BOMs and styles.
        Each client gets the same product catalog with their own product IDs.
        These product codes are used across:
        - Work Orders (style_model)
        - Capacity Orders (style_code)
        - BOM Headers (style_code)
        - Production Standards (style_code)
        """
        from backend.schemas.product import Product
        from backend.schemas.client import Client

        # Products with meaningful names that match capacity planning styles
        products_data = [
            {"code": "TSHIRT-001", "name": "Basic T-Shirt", "uom": "pieces", "cycle_time": 0.15},
            {"code": "POLO-001", "name": "Classic Polo Shirt", "uom": "pieces", "cycle_time": 0.20},
            {"code": "JACKET-001", "name": "Lightweight Jacket", "uom": "pieces", "cycle_time": 0.45},
            {"code": "TSHIRT-002", "name": "Premium T-Shirt", "uom": "pieces", "cycle_time": 0.18},
            {"code": "POLO-002", "name": "Performance Polo", "uom": "pieces", "cycle_time": 0.25},
        ]

        clients = self.session.query(Client).all()
        products = []
        for client in clients:
            for p in products_data:
                products.append(Product(
                    client_id=client.client_id,
                    product_code=p["code"],
                    product_name=p["name"],
                    description=f"Standard {p['name']} for manufacturing operations",
                    unit_of_measure=p["uom"],
                    ideal_cycle_time=Decimal(str(p["cycle_time"])),
                    is_active=True,
                ))
        self.session.add_all(products)
        return len(products)

    def _seed_shifts(self) -> int:
        """Seed demo shifts (per-client).

        Each client gets the same 3 shifts with their own shift IDs.
        """
        from backend.schemas.shift import Shift
        from backend.schemas.client import Client
        from datetime import time as dt_time

        shifts_data = [
            ("Day Shift", dt_time(6, 0, 0), dt_time(14, 0, 0)),
            ("Swing Shift", dt_time(14, 0, 0), dt_time(22, 0, 0)),
            ("Night Shift", dt_time(22, 0, 0), dt_time(6, 0, 0)),
        ]

        clients = self.session.query(Client).all()
        shifts = []
        for client in clients:
            for name, start, end in shifts_data:
                shifts.append(Shift(
                    client_id=client.client_id,
                    shift_name=name,
                    start_time=start,
                    end_time=end,
                    is_active=True,
                ))
        self.session.add_all(shifts)
        return len(shifts)

    def _seed_work_orders(self) -> int:
        """Seed demo work orders.

        Creates work orders that link to:
        - Products (via style_model matching product_code)
        - Capacity Orders (can be conceptually linked via matching style)
        - Production Entries (via work_order_id)
        """
        from backend.schemas.work_order import WorkOrder, WorkOrderStatus

        today = date.today()

        # Work orders matching product/style codes for integrated experience
        work_orders_data = [
            # Active orders (IN_PROGRESS) - link to Capacity Orders
            {"id": "WO-0001", "style": "TSHIRT-001", "qty": 500, "status": WorkOrderStatus.IN_PROGRESS, "days": 14, "priority": "HIGH"},
            {"id": "WO-0002", "style": "POLO-001", "qty": 300, "status": WorkOrderStatus.IN_PROGRESS, "days": 21, "priority": "NORMAL"},
            {"id": "WO-0003", "style": "JACKET-001", "qty": 150, "status": WorkOrderStatus.IN_PROGRESS, "days": 28, "priority": "HIGH"},
            # Released orders (ready for production)
            {"id": "WO-0004", "style": "TSHIRT-002", "qty": 750, "status": WorkOrderStatus.RELEASED, "days": 35, "priority": "NORMAL"},
            {"id": "WO-0005", "style": "POLO-002", "qty": 400, "status": WorkOrderStatus.RELEASED, "days": 42, "priority": "LOW"},
            # Received orders (awaiting release)
            {"id": "WO-0006", "style": "TSHIRT-001", "qty": 1000, "status": WorkOrderStatus.RECEIVED, "days": 56, "priority": "NORMAL"},
            {"id": "WO-0007", "style": "POLO-001", "qty": 600, "status": WorkOrderStatus.RECEIVED, "days": 63, "priority": "LOW"},
        ]

        work_orders = []
        for wo in work_orders_data:
            work_order = WorkOrder(
                work_order_id=wo["id"],
                client_id="DEMO-001",
                style_model=wo["style"],
                planned_quantity=wo["qty"],
                actual_quantity=random.randint(0, wo["qty"] // 3) if wo["status"] == WorkOrderStatus.IN_PROGRESS else 0,
                status=wo["status"],
                planned_ship_date=today + timedelta(days=wo["days"]),
                required_date=today + timedelta(days=wo["days"]),
                received_date=today - timedelta(days=random.randint(7, 14)),
                priority=wo["priority"],
            )
            work_orders.append(work_order)

        self.session.add_all(work_orders)
        return len(work_orders)

    def _seed_jobs(self) -> int:
        """Seed demo jobs.

        Creates jobs (operations) for each work order.
        Operations align with capacity planning departments:
        - CUT: Cutting operation
        - SEW: Sewing operation
        - FIN: Finishing operation

        These match the production standards in Capacity Planning.
        """
        from backend.schemas.job import Job

        # Operations match capacity planning departments
        operations = [
            {"num": 1, "code": "CUT", "name": "CUT - Cutting", "hours": 2.0},
            {"num": 2, "code": "SEW", "name": "SEW - Sewing", "hours": 6.0},
            {"num": 3, "code": "FIN", "name": "FIN - Finishing", "hours": 2.0},
        ]

        jobs = []
        for wo_id in range(1, 8):
            for op in operations:
                job = Job(
                    job_id=f"JOB-{wo_id:04d}-{op['num']:02d}",
                    work_order_id=f"WO-{wo_id:04d}",
                    client_id_fk="DEMO-001",
                    operation_name=op["name"],
                    operation_code=op["code"],
                    sequence_number=op["num"],
                    planned_hours=Decimal(str(round(op["hours"] * random.uniform(0.8, 1.2), 2))),
                )
                jobs.append(job)

        self.session.add_all(jobs)
        return len(jobs)

    def _seed_production_entries(self) -> int:
        """Seed demo production entries.

        Creates production records that link to:
        - Work Orders (WO-0001, WO-0002, WO-0003)
        - Products (via product_id matching per client)
        - Shifts (by shift_id per client)

        This data appears in KPI dashboards and feeds capacity analysis.
        """
        from backend.schemas.production_entry import ProductionEntry
        from backend.schemas.product import Product
        from backend.schemas.shift import Shift

        # Look up DEMO-001's products and shifts by code/name
        client_id = "DEMO-001"
        client_products = self.session.query(Product).filter(Product.client_id == client_id).all()
        client_shifts = self.session.query(Shift).filter(Shift.client_id == client_id).all()

        # Build lookup maps
        product_by_code = {p.product_code: p.product_id for p in client_products}
        shift_by_idx = {i: s.shift_id for i, s in enumerate(client_shifts)}

        wo_product_map = {
            "WO-0001": product_by_code.get("TSHIRT-001", client_products[0].product_id if client_products else 1),
            "WO-0002": product_by_code.get("POLO-001", client_products[1].product_id if len(client_products) > 1 else 1),
            "WO-0003": product_by_code.get("JACKET-001", client_products[2].product_id if len(client_products) > 2 else 1),
        }

        entries = []
        today = datetime.now(tz=timezone.utc)

        entry_num = 1
        for day_offset in range(7):
            entry_date = today - timedelta(days=day_offset)
            for shift_idx in range(3):
                shift_id = shift_by_idx.get(shift_idx, client_shifts[0].shift_id if client_shifts else 1)
                wo_idx = (day_offset % 3) + 1
                wo_id = f"WO-000{wo_idx}"
                product_id = wo_product_map.get(wo_id, client_products[0].product_id if client_products else 1)
                units = random.randint(50, 200)
                defects = random.randint(0, 10)
                scrap = random.randint(0, 5)
                run_hours = random.uniform(6, 8)

                entry = ProductionEntry(
                    production_entry_id=f"PE-{entry_date.strftime('%Y%m%d')}-{entry_num:03d}",
                    client_id=client_id,
                    product_id=product_id,
                    shift_id=shift_id,
                    work_order_id=wo_id,
                    job_id=f"JOB-000{wo_idx}-01",
                    production_date=entry_date,
                    shift_date=entry_date,
                    units_produced=units,
                    run_time_hours=Decimal(str(round(run_hours, 2))),
                    employees_assigned=random.randint(3, 6),
                    defect_count=defects,
                    scrap_count=scrap,
                    entered_by=1,  # Admin user
                )
                entries.append(entry)
                entry_num += 1

        self.session.add_all(entries)
        return len(entries)

    def _seed_downtime_entries(self) -> int:
        """Seed demo downtime entries.

        Creates downtime records linked to Work Orders for Availability KPI.
        """
        from backend.schemas.downtime_entry import DowntimeEntry

        entries = []
        today = datetime.now(tz=timezone.utc)

        for day_offset in range(5):
            entry_date = today - timedelta(days=day_offset)
            wo_num = (day_offset % 3) + 1

            entry = DowntimeEntry(
                downtime_entry_id=f"DT-{entry_date.strftime('%Y%m%d')}-{day_offset + 1:02d}",
                client_id="DEMO-001",
                work_order_id=f"WO-000{wo_num}",
                shift_date=entry_date,
                downtime_reason=random.choice([
                    "Equipment Maintenance",
                    "Material Shortage",
                    "Changeover",
                    "Unplanned Breakdown",
                ]),
                downtime_duration_minutes=random.randint(15, 120),
                machine_id=f"MACHINE-{random.randint(1, 5):02d}",
                reported_by=1,  # Admin user
            )
            entries.append(entry)

        self.session.add_all(entries)
        return len(entries)

    def _seed_attendance_entries(self) -> int:
        """Seed demo attendance entries.

        Creates attendance records for Absenteeism KPI calculation.
        """
        from backend.schemas.attendance_entry import AttendanceEntry, AbsenceType
        from backend.schemas.shift import Shift

        # Look up DEMO-001's Day Shift
        client_id = "DEMO-001"
        day_shift = self.session.query(Shift).filter(
            Shift.client_id == client_id,
            Shift.shift_name == "Day Shift"
        ).first()
        day_shift_id = day_shift.shift_id if day_shift else 1

        entries = []
        today = datetime.now(tz=timezone.utc)

        entry_num = 1
        for day_offset in range(7):
            entry_date = today - timedelta(days=day_offset)
            for emp_id in range(1, 6):
                actual_hours = random.choice([8.0, 8.0, 8.0, 7.5, 0.0])
                is_absent = 1 if actual_hours == 0 else 0
                absence_type = AbsenceType.UNSCHEDULED_ABSENCE if is_absent else None

                entry = AttendanceEntry(
                    attendance_entry_id=f"ATT-{entry_date.strftime('%Y%m%d')}-{entry_num:03d}",
                    client_id=client_id,
                    employee_id=emp_id,  # Integer ID from auto-increment
                    shift_id=day_shift_id,
                    shift_date=entry_date,
                    scheduled_hours=Decimal("8.0"),
                    actual_hours=Decimal(str(actual_hours)),
                    absence_hours=Decimal(str(8.0 - actual_hours)) if actual_hours < 8.0 else Decimal("0"),
                    is_absent=is_absent,
                    absence_type=absence_type,
                    entered_by=1,  # Admin user
                )
                entries.append(entry)
                entry_num += 1

        self.session.add_all(entries)
        return len(entries)

    def _seed_quality_entries(self) -> int:
        """Seed demo quality entries.

        Creates quality inspection records linked to:
        - Work Orders (WO-0001, WO-0002, WO-0003)

        This data feeds quality KPIs (PPM, DPMO, FPY, RTY).
        """
        from backend.schemas.quality_entry import QualityEntry

        entries = []
        today = datetime.now(tz=timezone.utc)

        # Quality inspections for active work orders
        for day_offset in range(5):
            entry_date = today - timedelta(days=day_offset)
            wo_num = (day_offset % 3) + 1
            units_inspected = random.randint(50, 100)
            units_defective = random.randint(0, 5)
            units_passed = units_inspected - units_defective

            entry = QualityEntry(
                quality_entry_id=f"QE-{entry_date.strftime('%Y%m%d')}-{day_offset + 1:02d}",
                client_id="DEMO-001",
                work_order_id=f"WO-000{wo_num}",
                job_id=f"JOB-000{wo_num}-02",  # SEW operation
                shift_date=entry_date,
                inspection_date=entry_date,
                units_inspected=units_inspected,
                units_passed=units_passed,
                units_defective=units_defective,
                total_defects_count=units_defective + random.randint(0, 3),  # May have multiple defects per unit
                inspection_stage="In-Process",
                is_first_pass=1,
                inspector_id="1",  # Admin user as string
            )
            entries.append(entry)

        self.session.add_all(entries)
        return len(entries)

    def _seed_hold_entries(self) -> int:
        """Seed demo hold entries (WIP holds).

        Creates hold records for WIP Aging KPI calculation.
        """
        from backend.schemas.hold_entry import HoldEntry, HoldStatus, HoldReason

        today = datetime.now(tz=timezone.utc)

        entries = [
            HoldEntry(
                hold_entry_id="HE-001",
                client_id="DEMO-001",
                work_order_id="WO-0001",
                job_id="JOB-0001-02",
                hold_status=HoldStatus.ON_HOLD,
                hold_date=today - timedelta(days=2),
                hold_reason=HoldReason.QUALITY_ISSUE,
                hold_reason_description="Quality Hold - Inspection Required",
                hold_initiated_by="1",  # Admin user
            ),
            HoldEntry(
                hold_entry_id="HE-002",
                client_id="DEMO-001",
                work_order_id="WO-0002",
                job_id="JOB-0002-01",
                hold_status=HoldStatus.RESUMED,
                hold_date=today - timedelta(days=5),
                resume_date=today - timedelta(days=1),
                total_hold_duration_hours=Decimal("96"),  # 4 days
                hold_reason=HoldReason.MATERIAL_INSPECTION,
                hold_reason_description="Material Verification",
                hold_initiated_by="1",
                resumed_by="1",
            ),
        ]
        self.session.add_all(entries)
        return len(entries)

    def _seed_defect_type_catalog(self) -> int:
        """Seed demo defect type catalog.

        Creates client-specific defect types for quality tracking.
        """
        from backend.schemas.defect_type_catalog import DefectTypeCatalog

        defect_types = [
            DefectTypeCatalog(
                defect_type_id="DT-DEMO-001",
                client_id="DEMO-001",
                defect_code="DIM-001",
                defect_name="Dimensional Out of Spec",
                description="Part dimensions outside tolerance",
                category="Dimensional",
                severity_default="MAJOR",
                is_active=True,
            ),
            DefectTypeCatalog(
                defect_type_id="DT-DEMO-002",
                client_id="DEMO-001",
                defect_code="SUR-001",
                defect_name="Surface Scratch",
                description="Visible scratch on product surface",
                category="Surface",
                severity_default="MINOR",
                is_active=True,
            ),
            DefectTypeCatalog(
                defect_type_id="DT-DEMO-003",
                client_id="DEMO-001",
                defect_code="SUR-002",
                defect_name="Surface Contamination",
                description="Contamination or foreign material on surface",
                category="Surface",
                severity_default="MAJOR",
                is_active=True,
            ),
            DefectTypeCatalog(
                defect_type_id="DT-DEMO-004",
                client_id="DEMO-001",
                defect_code="ASM-001",
                defect_name="Assembly Error",
                description="Incorrect assembly or misaligned components",
                category="Assembly",
                severity_default="CRITICAL",
                is_active=True,
            ),
        ]
        self.session.add_all(defect_types)
        return len(defect_types)

    def _seed_floating_pool(self) -> int:
        """Seed demo floating pool entries (Phase 6.3).

        Creates floating pool employees who can be assigned across clients.
        """
        from backend.schemas.floating_pool import FloatingPool

        entries = []
        today = datetime.now(tz=timezone.utc)

        # Mark employees 8-10 as floating pool (cross-client resources)
        for emp_num in range(8, 11):
            entry = FloatingPool(
                employee_id=emp_num,
                client_id=None,  # NULL = available for any client
                available_from=today - timedelta(days=30),
                available_to=None,  # Open-ended availability
                current_assignment=None if emp_num == 10 else "DEMO-001",
                notes=f"Floating pool employee {emp_num} - cross-trained for multiple operations"
            )
            entries.append(entry)

        # Add one entry with specific date range assignment
        entries.append(FloatingPool(
            employee_id=7,
            client_id="TEST-001",
            available_from=today - timedelta(days=14),
            available_to=today + timedelta(days=14),
            current_assignment="TEST-001",
            notes="Temporary assignment to TEST-001 for capacity support"
        ))

        self.session.add_all(entries)
        return len(entries)

    def _seed_coverage_entries(self) -> int:
        """Seed demo shift coverage entries.

        Creates records of floating pool employees covering for absent employees.
        """
        from backend.schemas.coverage_entry import CoverageEntry
        from backend.schemas.shift import Shift

        # Look up DEMO-001's shift IDs
        client_id = "DEMO-001"
        client_shift_ids = [
            s.shift_id for s in
            self.session.query(Shift).filter(Shift.client_id == client_id).all()
        ]
        if not client_shift_ids:
            client_shift_ids = [1, 2, 3]  # Fallback

        entries = []
        today = datetime.now(tz=timezone.utc)

        # Create coverage records for past 7 days
        coverage_reasons = [
            "Absence - Sick Leave",
            "Absence - Personal Day",
            "Additional Support - High Volume",
            "Training Coverage",
            "Vacation Coverage"
        ]

        for day_offset in range(7):
            entry_date = today - timedelta(days=day_offset)

            # 50% chance of coverage each day
            if random.random() > 0.5:
                entry = CoverageEntry(
                    coverage_entry_id=f"COV-{entry_date.strftime('%Y%m%d')}-{random.randint(1, 99):02d}",
                    client_id=client_id,
                    floating_employee_id=random.randint(8, 10),  # Floating pool employees
                    covered_employee_id=random.randint(1, 5),    # Regular employees
                    shift_date=entry_date,
                    shift_id=random.choice(client_shift_ids),
                    coverage_start_time=entry_date.replace(hour=6, minute=0),
                    coverage_end_time=entry_date.replace(hour=14, minute=0),
                    coverage_hours=8,
                    coverage_reason=random.choice(coverage_reasons),
                    notes=f"Coverage record for {entry_date.strftime('%Y-%m-%d')}",
                    assigned_by=1  # Admin user
                )
                entries.append(entry)

        self.session.add_all(entries)
        return len(entries)

    def _seed_workflow_transitions(self) -> int:
        """Seed demo workflow transition history (Phase 10).

        Creates realistic status progression for demo work orders.
        """
        from backend.schemas.workflow import WorkflowTransitionLog

        entries = []
        today = datetime.now(tz=timezone.utc)

        # Work order status progressions (realistic business flow)
        status_progressions = {
            "WO-0001": [
                ("RECEIVED", "RELEASED", -5, "Released for production"),
                ("RELEASED", "IN_PROGRESS", -4, "Production started"),
            ],
            "WO-0002": [
                ("RECEIVED", "RELEASED", -7, "Quality review passed"),
                ("RELEASED", "IN_PROGRESS", -6, "Started manufacturing"),
                ("IN_PROGRESS", "QC_REVIEW", -2, "Batch completed, sent for QC"),
            ],
            "WO-0003": [
                ("RECEIVED", "RELEASED", -10, "Materials received"),
                ("RELEASED", "IN_PROGRESS", -9, None),
                ("IN_PROGRESS", "ON_HOLD", -3, "Quality issue detected - pending resolution"),
            ],
            "WO-0004": [
                ("RECEIVED", "RELEASED", -14, "Rush order approved"),
                ("RELEASED", "IN_PROGRESS", -13, None),
                ("IN_PROGRESS", "QC_REVIEW", -8, None),
                ("QC_REVIEW", "COMPLETED", -7, "All inspections passed"),
            ],
            "WO-0005": [
                ("RECEIVED", "CANCELLED", -3, "Customer cancelled order"),
            ],
        }

        transition_id = 1
        for work_order_id, transitions in status_progressions.items():
            from_status = None
            elapsed_from_received = 0

            for idx, (from_st, to_st, days_ago, notes) in enumerate(transitions):
                transition_time = today + timedelta(days=days_ago)
                elapsed_from_received = abs(days_ago) * 24  # Hours

                entry = WorkflowTransitionLog(
                    work_order_id=work_order_id,
                    client_id="DEMO-001",
                    from_status=from_st if idx > 0 else None,
                    to_status=to_st,
                    transitioned_by=random.randint(1, 3),  # User IDs 1-3
                    transitioned_at=transition_time,
                    notes=notes,
                    trigger_source=random.choice(["manual", "automatic", "bulk"]),
                    elapsed_from_received_hours=elapsed_from_received,
                    elapsed_from_previous_hours=24 if idx > 0 else 0,
                )
                entries.append(entry)
                transition_id += 1

        self.session.add_all(entries)
        return len(entries)

    def _seed_event_store(self) -> int:
        """Seed demo domain events (Phase 3).

        Creates sample events for testing event sourcing and audit trails.
        """
        from backend.schemas.event_store import EventStore

        entries = []
        today = datetime.now(tz=timezone.utc)

        # Define sample events that would be generated by domain operations
        sample_events = [
            # Work Order Events
            {
                "event_type": "WorkOrderCreated",
                "aggregate_type": "WorkOrder",
                "aggregate_id": "WO-0001",
                "days_ago": 10,
                "payload": {
                    "work_order_id": "WO-0001",
                    "product_id": "PROD-001",
                    "quantity_ordered": 500,
                    "priority": 3
                }
            },
            {
                "event_type": "WorkOrderStatusChanged",
                "aggregate_type": "WorkOrder",
                "aggregate_id": "WO-0001",
                "days_ago": 8,
                "payload": {
                    "work_order_id": "WO-0001",
                    "from_status": "RECEIVED",
                    "to_status": "RELEASED",
                    "reason": "Materials ready"
                }
            },
            {
                "event_type": "WorkOrderStatusChanged",
                "aggregate_type": "WorkOrder",
                "aggregate_id": "WO-0001",
                "days_ago": 7,
                "payload": {
                    "work_order_id": "WO-0001",
                    "from_status": "RELEASED",
                    "to_status": "IN_PROGRESS",
                    "reason": "Production started"
                }
            },
            # Production Events
            {
                "event_type": "ProductionEntryCreated",
                "aggregate_type": "ProductionEntry",
                "aggregate_id": "PE-0001",
                "days_ago": 6,
                "payload": {
                    "work_order_id": "WO-0001",
                    "quantity_produced": 150,
                    "shift_id": "SHIFT-1"
                }
            },
            {
                "event_type": "ProductionEntryCreated",
                "aggregate_type": "ProductionEntry",
                "aggregate_id": "PE-0002",
                "days_ago": 5,
                "payload": {
                    "work_order_id": "WO-0001",
                    "quantity_produced": 175,
                    "shift_id": "SHIFT-2"
                }
            },
            # Quality Events
            {
                "event_type": "QualityInspectionRecorded",
                "aggregate_type": "QualityEntry",
                "aggregate_id": "QE-0001",
                "days_ago": 4,
                "payload": {
                    "work_order_id": "WO-0001",
                    "quantity_inspected": 100,
                    "quantity_passed": 98,
                    "quantity_failed": 2,
                    "ppm": 20000
                }
            },
            # Hold Events
            {
                "event_type": "HoldCreated",
                "aggregate_type": "HoldEntry",
                "aggregate_id": "HE-0001",
                "days_ago": 3,
                "payload": {
                    "work_order_id": "WO-0003",
                    "quantity_on_hold": 50,
                    "hold_reason": "Quality inspection required"
                }
            },
            {
                "event_type": "HoldResumed",
                "aggregate_type": "HoldEntry",
                "aggregate_id": "HE-0002",
                "days_ago": 1,
                "payload": {
                    "work_order_id": "WO-0002",
                    "quantity_released": 25,
                    "resolution": "Rework completed"
                }
            },
            # KPI Events
            {
                "event_type": "KPIThresholdViolated",
                "aggregate_type": "KPIAlert",
                "aggregate_id": "KPI-EFF-001",
                "days_ago": 2,
                "payload": {
                    "kpi_type": "efficiency",
                    "threshold": 85.0,
                    "actual_value": 78.5,
                    "shift_id": "SHIFT-1",
                    "severity": "warning"
                }
            },
            {
                "event_type": "KPITargetAchieved",
                "aggregate_type": "KPIAlert",
                "aggregate_id": "KPI-QUAL-001",
                "days_ago": 1,
                "payload": {
                    "kpi_type": "first_pass_yield",
                    "target": 95.0,
                    "actual_value": 97.2,
                    "celebration": True
                }
            },
            # Employee Assignment Events
            {
                "event_type": "EmployeeAssignedToFloatingPool",
                "aggregate_type": "Employee",
                "aggregate_id": "EMP-008",
                "days_ago": 14,
                "payload": {
                    "employee_id": "EMP-008",
                    "skills": ["assembly", "inspection", "packaging"],
                    "availability": "full_time"
                }
            },
            {
                "event_type": "EmployeeAssignedToClient",
                "aggregate_type": "Employee",
                "aggregate_id": "EMP-008",
                "days_ago": 5,
                "payload": {
                    "employee_id": "EMP-008",
                    "client_id": "DEMO-001",
                    "assignment_type": "temporary",
                    "duration_days": 14
                }
            },
        ]

        for event_data in sample_events:
            event_time = today - timedelta(days=event_data["days_ago"])

            entry = EventStore(
                event_id=str(uuid.uuid4()),
                event_type=event_data["event_type"],
                aggregate_type=event_data["aggregate_type"],
                aggregate_id=event_data["aggregate_id"],
                client_id="DEMO-001",
                triggered_by=random.randint(1, 3),
                occurred_at=event_time,
                payload=event_data["payload"]
            )
            entries.append(entry)

        self.session.add_all(entries)
        return len(entries)

    def _seed_capacity_planning(self) -> int:
        """Seed demo data for capacity planning module.

        Phase C.2: Capacity Planning Demo Seeding (LINKED DATA)

        Creates INTEGRATED data that connects to existing KPI Operations entities:
        - Master calendar (next 12 weeks)
        - 4 production lines (matching job operations CUT/SEW/FIN)
        - 8 sample capacity orders (3 linked to existing Work Orders)
        - Production standards (for all 5 product styles)
        - 5 BOMs with components (one per product)
        - Stock snapshots for all BOM components

        LINKAGE POINTS:
        - style_code matches Product.product_code
        - Capacity Orders for styles that have active Work Orders
        - Production Standards match Job operations
        """
        from backend.schemas.capacity import (
            CapacityCalendar,
            CapacityProductionLine,
            CapacityOrder,
            CapacityProductionStandard,
            CapacityBOMHeader,
            CapacityBOMDetail,
            CapacityStockSnapshot,
        )
        from backend.schemas.capacity.orders import OrderStatus, OrderPriority

        client_id = "DEMO-001"
        today = date.today()

        logger.info(f"Seeding capacity planning demo data (LINKED) for client: {client_id}")

        # 1. Master Calendar - next 12 weeks (84 days)
        # Includes realistic holidays
        holidays = {
            # Add some sample holidays in the planning horizon
            (today + timedelta(days=30)).isoformat()[:10]: "Company Holiday",
            (today + timedelta(days=60)).isoformat()[:10]: "National Holiday",
        }

        calendar_entries = []
        for i in range(84):
            cal_date = today + timedelta(days=i)
            date_str = cal_date.isoformat()[:10]
            is_weekend = cal_date.weekday() >= 5
            holiday_name = holidays.get(date_str)
            is_working = not is_weekend and not holiday_name

            entry = CapacityCalendar(
                client_id=client_id,
                calendar_date=cal_date,
                is_working_day=is_working,
                shifts_available=2 if is_working else 0,
                shift1_hours=8.0 if is_working else 0,
                shift2_hours=8.0 if is_working else 0,
                shift3_hours=0,
                holiday_name=holiday_name if holiday_name else ("Weekend" if is_weekend else None)
            )
            calendar_entries.append(entry)
        self.session.add_all(calendar_entries)

        # 2. Production Lines - Match operations from Jobs (CUT/SEW/FIN)
        lines_data = [
            {"code": "CUTTING_01", "name": "Cutting Line 1", "dept": "CUTTING", "capacity": 500, "ops": 8},
            {"code": "SEWING_01", "name": "Sewing Line 1", "dept": "SEWING", "capacity": 120, "ops": 25},
            {"code": "SEWING_02", "name": "Sewing Line 2", "dept": "SEWING", "capacity": 100, "ops": 20},
            {"code": "FINISHING_01", "name": "Finishing Line 1", "dept": "FINISHING", "capacity": 200, "ops": 12},
        ]
        line_entries = []
        for line in lines_data:
            line_entry = CapacityProductionLine(
                client_id=client_id,
                line_code=line["code"],
                line_name=line["name"],
                department=line["dept"],
                standard_capacity_units_per_hour=line["capacity"],
                max_operators=line["ops"],
                efficiency_factor=0.85,
                absenteeism_factor=0.05,
                is_active=True
            )
            line_entries.append(line_entry)
        self.session.add_all(line_entries)

        # 3. Sample Capacity Orders - LINKED to Work Orders
        # First 3 orders match active Work Orders (WO-0001, WO-0002, WO-0003)
        # This creates a direct link between operational execution and capacity planning
        orders_data = [
            # LINKED to WO-0001 (TSHIRT-001, IN_PROGRESS)
            {"num": "CPL-WO-0001", "cust": "Demo Manufacturing Co", "style": "TSHIRT-001",
             "qty": 500, "days": 14, "priority": OrderPriority.HIGH, "status": OrderStatus.IN_PROGRESS,
             "notes": "Linked to Work Order WO-0001"},

            # LINKED to WO-0002 (POLO-001, IN_PROGRESS)
            {"num": "CPL-WO-0002", "cust": "Demo Manufacturing Co", "style": "POLO-001",
             "qty": 300, "days": 21, "priority": OrderPriority.NORMAL, "status": OrderStatus.IN_PROGRESS,
             "notes": "Linked to Work Order WO-0002"},

            # LINKED to WO-0003 (JACKET-001, IN_PROGRESS)
            {"num": "CPL-WO-0003", "cust": "Demo Manufacturing Co", "style": "JACKET-001",
             "qty": 150, "days": 28, "priority": OrderPriority.HIGH, "status": OrderStatus.IN_PROGRESS,
             "notes": "Linked to Work Order WO-0003"},

            # Additional capacity planning orders (future orders for planning)
            {"num": "CPL-2024-001", "cust": "ABC Corp", "style": "TSHIRT-001",
             "qty": 5000, "days": 35, "priority": OrderPriority.HIGH, "status": OrderStatus.CONFIRMED,
             "notes": "Large batch for Q2"},

            {"num": "CPL-2024-002", "cust": "XYZ Inc", "style": "POLO-001",
             "qty": 3000, "days": 42, "priority": OrderPriority.NORMAL, "status": OrderStatus.CONFIRMED,
             "notes": "Standard seasonal order"},

            {"num": "CPL-2024-003", "cust": "Fashion Co", "style": "TSHIRT-002",
             "qty": 2000, "days": 49, "priority": OrderPriority.NORMAL, "status": OrderStatus.CONFIRMED,
             "notes": "Premium line expansion"},

            {"num": "CPL-2024-004", "cust": "Style Ltd", "style": "JACKET-001",
             "qty": 1000, "days": 56, "priority": OrderPriority.LOW, "status": OrderStatus.DRAFT,
             "notes": "Winter collection - pending confirmation"},

            {"num": "CPL-2024-005", "cust": "Retail Plus", "style": "POLO-002",
             "qty": 4000, "days": 63, "priority": OrderPriority.LOW, "status": OrderStatus.DRAFT,
             "notes": "Performance line - pending quote"},
        ]
        order_entries = []
        for order in orders_data:
            order_entry = CapacityOrder(
                client_id=client_id,
                order_number=order["num"],
                customer_name=order["cust"],
                style_code=order["style"],
                style_description=f"Standard {order['style']} product line",
                order_quantity=order["qty"],
                required_date=today + timedelta(days=order["days"]),
                priority=order["priority"],
                status=order["status"],
                notes=order.get("notes")
            )
            order_entries.append(order_entry)
        self.session.add_all(order_entries)

        # 4. Production Standards (SAM per operation per style)
        # Covers ALL 5 products, matching Job operations (CUT/SEW/FIN)
        standards_data = [
            # TSHIRT-001 (Basic T-Shirt) - matches Product & WO-0001
            {"style": "TSHIRT-001", "op": "CUT", "dept": "CUTTING", "sam": 0.5, "name": "CUT - Cutting"},
            {"style": "TSHIRT-001", "op": "SEW", "dept": "SEWING", "sam": 8.0, "name": "SEW - Sewing"},
            {"style": "TSHIRT-001", "op": "FIN", "dept": "FINISHING", "sam": 2.0, "name": "FIN - Finishing"},

            # POLO-001 (Classic Polo Shirt) - matches Product & WO-0002
            {"style": "POLO-001", "op": "CUT", "dept": "CUTTING", "sam": 0.6, "name": "CUT - Cutting"},
            {"style": "POLO-001", "op": "SEW", "dept": "SEWING", "sam": 12.0, "name": "SEW - Sewing"},
            {"style": "POLO-001", "op": "FIN", "dept": "FINISHING", "sam": 3.0, "name": "FIN - Finishing"},

            # JACKET-001 (Lightweight Jacket) - matches Product & WO-0003
            {"style": "JACKET-001", "op": "CUT", "dept": "CUTTING", "sam": 1.2, "name": "CUT - Cutting"},
            {"style": "JACKET-001", "op": "SEW", "dept": "SEWING", "sam": 25.0, "name": "SEW - Sewing"},
            {"style": "JACKET-001", "op": "FIN", "dept": "FINISHING", "sam": 5.0, "name": "FIN - Finishing"},

            # TSHIRT-002 (Premium T-Shirt) - matches Product & WO-0004
            {"style": "TSHIRT-002", "op": "CUT", "dept": "CUTTING", "sam": 0.6, "name": "CUT - Cutting"},
            {"style": "TSHIRT-002", "op": "SEW", "dept": "SEWING", "sam": 10.0, "name": "SEW - Sewing"},
            {"style": "TSHIRT-002", "op": "FIN", "dept": "FINISHING", "sam": 2.5, "name": "FIN - Finishing"},

            # POLO-002 (Performance Polo) - matches Product & WO-0005
            {"style": "POLO-002", "op": "CUT", "dept": "CUTTING", "sam": 0.7, "name": "CUT - Cutting"},
            {"style": "POLO-002", "op": "SEW", "dept": "SEWING", "sam": 14.0, "name": "SEW - Sewing"},
            {"style": "POLO-002", "op": "FIN", "dept": "FINISHING", "sam": 3.5, "name": "FIN - Finishing"},
        ]
        standard_entries = []
        for std in standards_data:
            std_entry = CapacityProductionStandard(
                client_id=client_id,
                style_code=std["style"],
                operation_code=std["op"],
                operation_name=std["name"],
                department=std["dept"],
                sam_minutes=std["sam"]
            )
            standard_entries.append(std_entry)
        self.session.add_all(standard_entries)
        self.session.flush()

        # 5. BOMs with components - ALL 5 PRODUCTS
        # Components are shared across products to demonstrate MRP explosion
        boms_data = [
            {
                "item": "TSHIRT-001",
                "desc": "Basic T-Shirt",
                "components": [
                    {"code": "FABRIC-JERSEY", "desc": "Jersey Fabric", "qty": 0.5, "uom": "M", "waste": 5, "type": "FABRIC"},
                    {"code": "THREAD-WHT", "desc": "White Thread", "qty": 50, "uom": "M", "waste": 2, "type": "TRIM"},
                    {"code": "LABEL-CARE", "desc": "Care Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                    {"code": "LABEL-BRAND", "desc": "Brand Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                ]
            },
            {
                "item": "POLO-001",
                "desc": "Classic Polo Shirt",
                "components": [
                    {"code": "FABRIC-PIQUE", "desc": "Pique Fabric", "qty": 0.6, "uom": "M", "waste": 5, "type": "FABRIC"},
                    {"code": "THREAD-WHT", "desc": "White Thread", "qty": 75, "uom": "M", "waste": 2, "type": "TRIM"},
                    {"code": "BUTTON-SM", "desc": "Small Button", "qty": 3, "uom": "EA", "waste": 1, "type": "ACCESSORY"},
                    {"code": "LABEL-CARE", "desc": "Care Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                    {"code": "LABEL-BRAND", "desc": "Brand Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                    {"code": "COLLAR-RIB", "desc": "Ribbed Collar", "qty": 1, "uom": "EA", "waste": 2, "type": "TRIM"},
                ]
            },
            {
                "item": "JACKET-001",
                "desc": "Lightweight Jacket",
                "components": [
                    {"code": "FABRIC-TWILL", "desc": "Twill Fabric", "qty": 1.5, "uom": "M", "waste": 8, "type": "FABRIC"},
                    {"code": "FABRIC-LINING", "desc": "Lining Fabric", "qty": 1.2, "uom": "M", "waste": 5, "type": "FABRIC"},
                    {"code": "THREAD-BLK", "desc": "Black Thread", "qty": 100, "uom": "M", "waste": 2, "type": "TRIM"},
                    {"code": "ZIPPER-LG", "desc": "Large Zipper", "qty": 1, "uom": "EA", "waste": 1, "type": "ACCESSORY"},
                    {"code": "BUTTON-LG", "desc": "Large Button", "qty": 6, "uom": "EA", "waste": 2, "type": "ACCESSORY"},
                    {"code": "LABEL-CARE", "desc": "Care Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                    {"code": "LABEL-BRAND", "desc": "Brand Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                ]
            },
            {
                "item": "TSHIRT-002",
                "desc": "Premium T-Shirt",
                "components": [
                    {"code": "FABRIC-PREMIUM", "desc": "Premium Cotton", "qty": 0.55, "uom": "M", "waste": 5, "type": "FABRIC"},
                    {"code": "THREAD-WHT", "desc": "White Thread", "qty": 60, "uom": "M", "waste": 2, "type": "TRIM"},
                    {"code": "LABEL-CARE", "desc": "Care Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                    {"code": "LABEL-BRAND", "desc": "Brand Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                    {"code": "LABEL-PREMIUM", "desc": "Premium Quality Tag", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                ]
            },
            {
                "item": "POLO-002",
                "desc": "Performance Polo",
                "components": [
                    {"code": "FABRIC-PERF", "desc": "Performance Fabric", "qty": 0.65, "uom": "M", "waste": 5, "type": "FABRIC"},
                    {"code": "THREAD-WHT", "desc": "White Thread", "qty": 80, "uom": "M", "waste": 2, "type": "TRIM"},
                    {"code": "BUTTON-SM", "desc": "Small Button", "qty": 3, "uom": "EA", "waste": 1, "type": "ACCESSORY"},
                    {"code": "LABEL-CARE", "desc": "Care Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                    {"code": "LABEL-BRAND", "desc": "Brand Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                    {"code": "COLLAR-TECH", "desc": "Tech Collar", "qty": 1, "uom": "EA", "waste": 2, "type": "TRIM"},
                    {"code": "ZIPPER-SM", "desc": "Small Zipper", "qty": 1, "uom": "EA", "waste": 1, "type": "ACCESSORY"},
                ]
            },
        ]

        bom_count = 0
        for bom in boms_data:
            header = CapacityBOMHeader(
                client_id=client_id,
                parent_item_code=bom["item"],
                parent_item_description=bom["desc"],
                style_code=bom["item"],
                revision="1.0",
                is_active=True
            )
            self.session.add(header)
            self.session.flush()

            for comp in bom["components"]:
                detail = CapacityBOMDetail(
                    header_id=header.id,
                    client_id=client_id,
                    component_item_code=comp["code"],
                    component_description=comp["desc"],
                    quantity_per=Decimal(str(comp["qty"])),
                    unit_of_measure=comp["uom"],
                    waste_percentage=Decimal(str(comp["waste"])),
                    component_type=comp["type"]
                )
                self.session.add(detail)
                bom_count += 1

        # 6. Stock Snapshots - All components with realistic quantities
        # Some items have LOW STOCK to demonstrate shortage detection in Component Check
        stock_items = [
            # Fabrics
            {"code": "FABRIC-JERSEY", "desc": "Jersey Fabric", "oh": 10000, "uom": "M"},
            {"code": "FABRIC-PIQUE", "desc": "Pique Fabric", "oh": 5000, "uom": "M"},
            {"code": "FABRIC-TWILL", "desc": "Twill Fabric", "oh": 3000, "uom": "M"},
            {"code": "FABRIC-LINING", "desc": "Lining Fabric", "oh": 2500, "uom": "M"},
            {"code": "FABRIC-PREMIUM", "desc": "Premium Cotton", "oh": 1500, "uom": "M"},  # LOW for shortage demo
            {"code": "FABRIC-PERF", "desc": "Performance Fabric", "oh": 800, "uom": "M"},  # LOW for shortage demo

            # Threads
            {"code": "THREAD-WHT", "desc": "White Thread", "oh": 500000, "uom": "M"},
            {"code": "THREAD-BLK", "desc": "Black Thread", "oh": 300000, "uom": "M"},

            # Buttons
            {"code": "BUTTON-SM", "desc": "Small Button", "oh": 50000, "uom": "EA"},
            {"code": "BUTTON-LG", "desc": "Large Button", "oh": 20000, "uom": "EA"},

            # Zippers
            {"code": "ZIPPER-LG", "desc": "Large Zipper", "oh": 5000, "uom": "EA"},
            {"code": "ZIPPER-SM", "desc": "Small Zipper", "oh": 3000, "uom": "EA"},

            # Labels
            {"code": "LABEL-CARE", "desc": "Care Label", "oh": 100000, "uom": "EA"},
            {"code": "LABEL-BRAND", "desc": "Brand Label", "oh": 80000, "uom": "EA"},
            {"code": "LABEL-PREMIUM", "desc": "Premium Quality Tag", "oh": 500, "uom": "EA"},  # LOW for shortage demo

            # Collars
            {"code": "COLLAR-RIB", "desc": "Ribbed Collar", "oh": 15000, "uom": "EA"},
            {"code": "COLLAR-TECH", "desc": "Tech Collar", "oh": 2000, "uom": "EA"},  # LOW for shortage demo
        ]

        stock_entries = []
        for item in stock_items:
            stock_entry = CapacityStockSnapshot(
                client_id=client_id,
                snapshot_date=today,
                item_code=item["code"],
                item_description=item["desc"],
                on_hand_quantity=Decimal(str(item["oh"])),
                allocated_quantity=Decimal("0"),
                on_order_quantity=Decimal("0"),
                available_quantity=Decimal(str(item["oh"])),
                unit_of_measure=item["uom"]
            )
            stock_entries.append(stock_entry)
        self.session.add_all(stock_entries)

        # Calculate total entries seeded
        total_entries = (
            len(calendar_entries) +
            len(line_entries) +
            len(order_entries) +
            len(standard_entries) +
            len(boms_data) + bom_count +  # Headers + Details
            len(stock_entries)
        )

        logger.info(f"Capacity planning demo data seeded: {total_entries} records")
        return total_entries

    def get_seeded_counts(self) -> dict:
        """Get counts of seeded records.

        Returns:
            dict: Record counts by entity name.
        """
        return self._seeded_counts.copy()
