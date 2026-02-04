"""
Demo Data Seeder

Seeds demo data after schema creation during migration.
Creates sample data for demonstration and testing purposes.

Phase C.2: Added capacity planning demo data seeding.
"""
from typing import Callable, Optional, List, Any
from datetime import datetime, timedelta, date
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
        """Seed demo employees."""
        from backend.schemas.employee import Employee

        employees = []
        for i in range(1, 11):
            emp = Employee(
                employee_id=f"EMP-{i:03d}",
                first_name=f"Employee{i}",
                last_name=f"Demo{i}",
                badge_number=f"BADGE-{i:04d}",
                client_id_assigned="DEMO-001",
                is_active=1,
                hire_date=date(2023, 1, 1) + timedelta(days=i * 30),
            )
            employees.append(emp)

        self.session.add_all(employees)
        return len(employees)

    def _seed_products(self) -> int:
        """Seed demo products."""
        from backend.schemas.product import Product

        products = [
            Product(
                product_code=f"P{i:03d}",
                product_name=f"Product {i}",
                unit_of_measure="pieces",
                is_active=True,
            )
            for i in range(1, 6)
        ]
        self.session.add_all(products)
        return len(products)

    def _seed_shifts(self) -> int:
        """Seed demo shifts."""
        from backend.schemas.shift import Shift

        shifts = [
            Shift(
                shift_name="Day Shift",
                start_time="06:00:00",
                end_time="14:00:00",
                is_active=True,
            ),
            Shift(
                shift_name="Swing Shift",
                start_time="14:00:00",
                end_time="22:00:00",
                is_active=True,
            ),
            Shift(
                shift_name="Night Shift",
                start_time="22:00:00",
                end_time="06:00:00",
                is_active=True,
            ),
        ]
        self.session.add_all(shifts)
        return len(shifts)

    def _seed_work_orders(self) -> int:
        """Seed demo work orders."""
        from backend.schemas.work_order import WorkOrder, WorkOrderStatus

        work_orders = [
            WorkOrder(
                work_order_id=f"WO-{i:04d}",
                client_id="DEMO-001",
                product_id=f"PROD-{(i % 5) + 1:03d}",
                quantity_ordered=random.randint(100, 1000),
                status=WorkOrderStatus.IN_PROGRESS if i <= 3 else WorkOrderStatus.PENDING,
                due_date=date.today() + timedelta(days=i * 7),
                priority=random.randint(1, 5),
            )
            for i in range(1, 8)
        ]
        self.session.add_all(work_orders)
        return len(work_orders)

    def _seed_jobs(self) -> int:
        """Seed demo jobs."""
        from backend.schemas.job import Job

        jobs = []
        for wo_id in range(1, 8):
            for job_num in range(1, 4):
                job = Job(
                    job_id=f"JOB-{wo_id:04d}-{job_num:02d}",
                    work_order_id=f"WO-{wo_id:04d}",
                    operation_name=f"Operation {job_num}",
                    sequence_number=job_num,
                    estimated_hours=random.uniform(2, 8),
                    client_id_fk="DEMO-001",
                )
                jobs.append(job)

        self.session.add_all(jobs)
        return len(jobs)

    def _seed_production_entries(self) -> int:
        """Seed demo production entries."""
        from backend.schemas.production_entry import ProductionEntry

        entries = []
        today = date.today()

        for day_offset in range(7):
            entry_date = today - timedelta(days=day_offset)
            for shift_num in range(1, 4):
                entry = ProductionEntry(
                    client_id="DEMO-001",
                    shift_id=f"SHIFT-{shift_num}",
                    work_order_id=f"WO-000{(day_offset % 3) + 1}",
                    job_id=f"JOB-000{(day_offset % 3) + 1}-01",
                    employee_id=f"EMP-{(shift_num % 5) + 1:03d}",
                    product_id=f"PROD-{(day_offset % 5) + 1:03d}",
                    quantity_produced=random.randint(50, 200),
                    quantity_rejected=random.randint(0, 10),
                    production_date=entry_date,
                    hours_worked=random.uniform(6, 8),
                )
                entries.append(entry)

        self.session.add_all(entries)
        return len(entries)

    def _seed_downtime_entries(self) -> int:
        """Seed demo downtime entries."""
        from backend.schemas.downtime_entry import DowntimeEntry

        entries = []
        today = date.today()

        for day_offset in range(5):
            entry_date = today - timedelta(days=day_offset)
            entry = DowntimeEntry(
                client_id="DEMO-001",
                shift_id="SHIFT-1",
                entry_date=entry_date,
                downtime_reason=random.choice([
                    "Equipment Maintenance",
                    "Material Shortage",
                    "Changeover",
                    "Unplanned Breakdown",
                ]),
                downtime_minutes=random.randint(15, 120),
                employee_id=f"EMP-{random.randint(1, 5):03d}",
            )
            entries.append(entry)

        self.session.add_all(entries)
        return len(entries)

    def _seed_attendance_entries(self) -> int:
        """Seed demo attendance entries."""
        from backend.schemas.attendance_entry import AttendanceEntry, AbsenceType

        entries = []
        today = date.today()

        for day_offset in range(7):
            entry_date = today - timedelta(days=day_offset)
            for emp_id in range(1, 6):
                entry = AttendanceEntry(
                    client_id="DEMO-001",
                    employee_id=f"EMP-{emp_id:03d}",
                    shift_id="SHIFT-1",
                    attendance_date=entry_date,
                    scheduled_hours=8.0,
                    actual_hours=random.choice([8.0, 8.0, 8.0, 7.5, 0.0]),
                    absence_type=AbsenceType.NONE if random.random() > 0.1 else AbsenceType.UNEXCUSED,
                )
                entries.append(entry)

        self.session.add_all(entries)
        return len(entries)

    def _seed_quality_entries(self) -> int:
        """Seed demo quality entries."""
        from backend.schemas.quality_entry import QualityEntry

        entries = []
        today = date.today()

        for day_offset in range(5):
            entry_date = today - timedelta(days=day_offset)
            entry = QualityEntry(
                client_id="DEMO-001",
                shift_id="SHIFT-1",
                inspection_date=entry_date,
                inspector_id=f"EMP-{random.randint(1, 3):03d}",
                work_order_id=f"WO-000{(day_offset % 3) + 1}",
                quantity_inspected=random.randint(50, 100),
                quantity_passed=random.randint(45, 100),
                quantity_failed=random.randint(0, 5),
            )
            entries.append(entry)

        self.session.add_all(entries)
        return len(entries)

    def _seed_hold_entries(self) -> int:
        """Seed demo hold entries (WIP holds)."""
        from backend.schemas.hold_entry import HoldEntry, HoldStatus

        entries = [
            HoldEntry(
                client_id="DEMO-001",
                work_order_id="WO-0001",
                job_id="JOB-0001-01",
                quantity_on_hold=random.randint(10, 50),
                hold_reason="Quality Hold - Inspection Required",
                status=HoldStatus.ACTIVE,
                hold_date=date.today() - timedelta(days=2),
            ),
            HoldEntry(
                client_id="DEMO-001",
                work_order_id="WO-0002",
                job_id="JOB-0002-01",
                quantity_on_hold=random.randint(5, 25),
                hold_reason="Material Verification",
                status=HoldStatus.RELEASED,
                hold_date=date.today() - timedelta(days=5),
                release_date=date.today() - timedelta(days=1),
            ),
        ]
        self.session.add_all(entries)
        return len(entries)

    def _seed_defect_type_catalog(self) -> int:
        """Seed demo defect type catalog."""
        from backend.schemas.defect_type_catalog import DefectTypeCatalog

        defect_types = [
            DefectTypeCatalog(
                client_id="DEMO-001",
                defect_code="DIM-001",
                defect_name="Dimensional Out of Spec",
                category="Dimensional",
                severity="Major",
                is_active=True,
            ),
            DefectTypeCatalog(
                client_id="DEMO-001",
                defect_code="SUR-001",
                defect_name="Surface Scratch",
                category="Surface",
                severity="Minor",
                is_active=True,
            ),
            DefectTypeCatalog(
                client_id="DEMO-001",
                defect_code="SUR-002",
                defect_name="Surface Contamination",
                category="Surface",
                severity="Major",
                is_active=True,
            ),
            DefectTypeCatalog(
                client_id="DEMO-001",
                defect_code="ASM-001",
                defect_name="Assembly Error",
                category="Assembly",
                severity="Critical",
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
        today = datetime.now()

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

        entries = []
        today = datetime.now()

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
                    client_id="DEMO-001",
                    floating_employee_id=random.randint(8, 10),  # Floating pool employees
                    covered_employee_id=random.randint(1, 5),    # Regular employees
                    shift_date=entry_date,
                    shift_id=random.randint(1, 3),
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
        today = datetime.now()

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
        today = datetime.now()

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

        Phase C.2: Capacity Planning Demo Seeding

        Creates:
        - Master calendar (next 12 weeks)
        - 4 production lines
        - 5 sample orders
        - 10 production standards
        - 3 BOMs with components
        - Stock snapshots
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
        entries = []
        today = date.today()

        logger.info(f"Seeding capacity planning demo data for client: {client_id}")

        # 1. Master Calendar - next 12 weeks (84 days)
        calendar_entries = []
        for i in range(84):
            cal_date = today + timedelta(days=i)
            is_working = cal_date.weekday() < 5  # Mon-Fri

            entry = CapacityCalendar(
                client_id=client_id,
                calendar_date=cal_date,
                is_working_day=is_working,
                shifts_available=2 if is_working else 0,
                shift1_hours=8.0 if is_working else 0,
                shift2_hours=8.0 if is_working else 0,
                shift3_hours=0,
                holiday_name=None if is_working else "Weekend"
            )
            calendar_entries.append(entry)
        self.session.add_all(calendar_entries)

        # 2. Production Lines
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

        # 3. Sample Orders
        orders_data = [
            {"num": "ORD-2024-001", "cust": "ABC Corp", "style": "TSHIRT-001", "qty": 5000, "days": 21, "priority": OrderPriority.HIGH},
            {"num": "ORD-2024-002", "cust": "XYZ Inc", "style": "POLO-001", "qty": 3000, "days": 28, "priority": OrderPriority.NORMAL},
            {"num": "ORD-2024-003", "cust": "Fashion Co", "style": "TSHIRT-001", "qty": 2000, "days": 14, "priority": OrderPriority.URGENT},
            {"num": "ORD-2024-004", "cust": "Style Ltd", "style": "JACKET-001", "qty": 1000, "days": 35, "priority": OrderPriority.NORMAL},
            {"num": "ORD-2024-005", "cust": "Retail Plus", "style": "POLO-001", "qty": 4000, "days": 42, "priority": OrderPriority.LOW},
        ]
        order_entries = []
        for order in orders_data:
            order_entry = CapacityOrder(
                client_id=client_id,
                order_number=order["num"],
                customer_name=order["cust"],
                style_code=order["style"],
                order_quantity=order["qty"],
                required_date=today + timedelta(days=order["days"]),
                priority=order["priority"],
                status=OrderStatus.CONFIRMED
            )
            order_entries.append(order_entry)
        self.session.add_all(order_entries)

        # 4. Production Standards (SAM per operation per style)
        standards_data = [
            {"style": "TSHIRT-001", "op": "CUT", "dept": "CUTTING", "sam": 0.5},
            {"style": "TSHIRT-001", "op": "SEW", "dept": "SEWING", "sam": 8.0},
            {"style": "TSHIRT-001", "op": "FINISH", "dept": "FINISHING", "sam": 2.0},
            {"style": "POLO-001", "op": "CUT", "dept": "CUTTING", "sam": 0.6},
            {"style": "POLO-001", "op": "SEW", "dept": "SEWING", "sam": 12.0},
            {"style": "POLO-001", "op": "FINISH", "dept": "FINISHING", "sam": 3.0},
            {"style": "JACKET-001", "op": "CUT", "dept": "CUTTING", "sam": 1.2},
            {"style": "JACKET-001", "op": "SEW", "dept": "SEWING", "sam": 25.0},
            {"style": "JACKET-001", "op": "FINISH", "dept": "FINISHING", "sam": 5.0},
        ]
        standard_entries = []
        for std in standards_data:
            std_entry = CapacityProductionStandard(
                client_id=client_id,
                style_code=std["style"],
                operation_code=std["op"],
                operation_name=f"{std['op']} Operation",
                department=std["dept"],
                sam_minutes=std["sam"]
            )
            standard_entries.append(std_entry)
        self.session.add_all(standard_entries)
        self.session.flush()

        # 5. BOMs with components
        boms_data = [
            {
                "item": "TSHIRT-001",
                "desc": "Basic T-Shirt",
                "components": [
                    {"code": "FABRIC-JERSEY", "desc": "Jersey Fabric", "qty": 0.5, "uom": "M", "waste": 5, "type": "FABRIC"},
                    {"code": "THREAD-WHT", "desc": "White Thread", "qty": 50, "uom": "M", "waste": 2, "type": "TRIM"},
                    {"code": "LABEL-CARE", "desc": "Care Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                ]
            },
            {
                "item": "POLO-001",
                "desc": "Polo Shirt",
                "components": [
                    {"code": "FABRIC-PIQUE", "desc": "Pique Fabric", "qty": 0.6, "uom": "M", "waste": 5, "type": "FABRIC"},
                    {"code": "THREAD-WHT", "desc": "White Thread", "qty": 75, "uom": "M", "waste": 2, "type": "TRIM"},
                    {"code": "BUTTON-SM", "desc": "Small Button", "qty": 3, "uom": "EA", "waste": 1, "type": "ACCESSORY"},
                    {"code": "LABEL-CARE", "desc": "Care Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
                ]
            },
            {
                "item": "JACKET-001",
                "desc": "Basic Jacket",
                "components": [
                    {"code": "FABRIC-TWILL", "desc": "Twill Fabric", "qty": 1.5, "uom": "M", "waste": 8, "type": "FABRIC"},
                    {"code": "FABRIC-LINING", "desc": "Lining Fabric", "qty": 1.2, "uom": "M", "waste": 5, "type": "FABRIC"},
                    {"code": "THREAD-BLK", "desc": "Black Thread", "qty": 100, "uom": "M", "waste": 2, "type": "TRIM"},
                    {"code": "ZIPPER-LG", "desc": "Large Zipper", "qty": 1, "uom": "EA", "waste": 1, "type": "ACCESSORY"},
                    {"code": "BUTTON-LG", "desc": "Large Button", "qty": 6, "uom": "EA", "waste": 2, "type": "ACCESSORY"},
                    {"code": "LABEL-CARE", "desc": "Care Label", "qty": 1, "uom": "EA", "waste": 0, "type": "ACCESSORY"},
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

        # 6. Stock Snapshots
        stock_items = [
            {"code": "FABRIC-JERSEY", "desc": "Jersey Fabric", "oh": 10000, "uom": "M"},
            {"code": "FABRIC-PIQUE", "desc": "Pique Fabric", "oh": 5000, "uom": "M"},
            {"code": "FABRIC-TWILL", "desc": "Twill Fabric", "oh": 3000, "uom": "M"},
            {"code": "FABRIC-LINING", "desc": "Lining Fabric", "oh": 2500, "uom": "M"},
            {"code": "THREAD-WHT", "desc": "White Thread", "oh": 500000, "uom": "M"},
            {"code": "THREAD-BLK", "desc": "Black Thread", "oh": 300000, "uom": "M"},
            {"code": "BUTTON-SM", "desc": "Small Button", "oh": 50000, "uom": "EA"},
            {"code": "BUTTON-LG", "desc": "Large Button", "oh": 20000, "uom": "EA"},
            {"code": "ZIPPER-LG", "desc": "Large Zipper", "oh": 5000, "uom": "EA"},
            {"code": "LABEL-CARE", "desc": "Care Label", "oh": 100000, "uom": "EA"},
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
