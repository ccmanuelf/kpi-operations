"""
Demo Data Seeder

Seeds demo data after schema creation during migration.
Creates sample data for demonstration and testing purposes.
"""
from typing import Callable, Optional, List, Any
from datetime import datetime, timedelta, date
import random
import logging
import hashlib

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """Simple password hash for demo data.

    Note: In production, use proper bcrypt hashing.
    This is just for seeding demo data.

    Args:
        password: Plain text password.

    Returns:
        str: Hashed password.
    """
    # Use sha256 for demo - actual app uses bcrypt
    return hashlib.sha256(password.encode()).hexdigest()


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
                role=UserRole.SUPERVISOR,
                is_active=1,
                client_id="DEMO-001",
            ),
            User(
                user_id="operator-001",
                username="operator",
                email="operator@kpi-platform.com",
                password_hash=_hash_password("oper123"),
                role=UserRole.OPERATOR,
                is_active=1,
                client_id="DEMO-001",
            ),
            User(
                user_id="viewer-001",
                username="viewer",
                email="viewer@kpi-platform.com",
                password_hash=_hash_password("view123"),
                role=UserRole.VIEWER,
                is_active=1,
                client_id="DEMO-001",
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
                client_id="DEMO-001",
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
                product_id=f"PROD-{i:03d}",
                product_name=f"Product {i}",
                product_code=f"P{i:03d}",
                client_id="DEMO-001",
                standard_rate=random.uniform(50, 150),
                unit_of_measure="pieces",
                is_active=1,
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
                shift_id="SHIFT-1",
                shift_name="Day Shift",
                start_time="06:00:00",
                end_time="14:00:00",
                client_id="DEMO-001",
                is_active=1,
            ),
            Shift(
                shift_id="SHIFT-2",
                shift_name="Swing Shift",
                start_time="14:00:00",
                end_time="22:00:00",
                client_id="DEMO-001",
                is_active=1,
            ),
            Shift(
                shift_id="SHIFT-3",
                shift_name="Night Shift",
                start_time="22:00:00",
                end_time="06:00:00",
                client_id="DEMO-001",
                is_active=1,
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
                    client_id="DEMO-001",
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

    def get_seeded_counts(self) -> dict:
        """Get counts of seeded records.

        Returns:
            dict: Record counts by entity name.
        """
        return self._seeded_counts.copy()
