"""
Test Data Factory
Provides factory functions for creating test data with proper FK relationships.
Uses real database transactions instead of mocks.
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

# Import all schemas
from backend.schemas import (
    Client,
    ClientType,
    User,
    UserRole,
    Employee,
    FloatingPool,
    WorkOrder,
    WorkOrderStatus,
    Job,
    PartOpportunities,
    Product,
    Shift,
    ProductionEntry,
    HoldEntry,
    HoldStatus,
    DowntimeEntry,
    AttendanceEntry,
    AbsenceType,
    CoverageEntry,
    QualityEntry,
    DefectDetail,
    DefectType,
    DefectTypeCatalog,
    SavedFilter,
    FilterHistory,
    WorkflowTransitionLog,
)
from backend.auth.jwt import get_password_hash


class TestDataFactory:
    """
    Factory for generating test data with real database transactions.
    All created entities maintain proper FK relationships.
    """

    # Counter for generating unique IDs
    _counters: Dict[str, int] = {}

    @classmethod
    def _next_id(cls, prefix: str) -> str:
        """Generate unique ID with prefix"""
        cls._counters[prefix] = cls._counters.get(prefix, 0) + 1
        return f"{prefix}-{cls._counters[prefix]:04d}"

    @classmethod
    def _next_int(cls, prefix: str) -> int:
        """Generate unique integer for counters"""
        cls._counters[prefix] = cls._counters.get(prefix, 0) + 1
        return cls._counters[prefix]

    @classmethod
    def reset_counters(cls):
        """Reset all ID counters - call at start of each test"""
        cls._counters = {}

    # ========================================================================
    # Core Foundation Entities
    # ========================================================================

    @staticmethod
    def create_client(
        db: Session,
        client_id: Optional[str] = None,
        client_name: Optional[str] = None,
        client_type: ClientType = ClientType.HOURLY_RATE,
        is_active: bool = True,
        **kwargs,
    ) -> Client:
        """Create a test client with minimal required fields"""
        if client_id is None:
            client_id = TestDataFactory._next_id("CLIENT")
        if client_name is None:
            client_name = f"Test Client {client_id}"

        client = Client(
            client_id=client_id,
            client_name=client_name,
            client_type=client_type,
            is_active=1 if is_active else 0,
            client_email=kwargs.get("client_email"),
            client_phone=kwargs.get("client_phone"),
            location=kwargs.get("location"),
        )
        db.add(client)
        db.flush()
        return client

    @staticmethod
    def create_user(
        db: Session,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: str = "TestPass123!",
        role: str = "operator",
        client_id: Optional[str] = None,
        is_active: bool = True,
        **kwargs,
    ) -> User:
        """Create a test user with hashed password"""
        if username is None:
            username = f"testuser_{TestDataFactory._next_int('user')}"
        if email is None:
            email = f"{username}@test.com"

        # User.user_id is a string primary key, generate one
        user_id = kwargs.get("user_id") or TestDataFactory._next_id("USER")

        user = User(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            full_name=kwargs.get("full_name", f"Test User {username}"),
            role=role,
            client_id_assigned=client_id,
            is_active=is_active,
        )
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def create_employee(
        db: Session,
        client_id: Optional[str] = None,
        employee_name: Optional[str] = None,
        employee_code: Optional[str] = None,
        is_floating_pool: bool = False,
        is_active: bool = True,
        **kwargs,
    ) -> Employee:
        """Create a test employee"""
        if employee_code is None:
            employee_code = TestDataFactory._next_id("EMP")
        if employee_name is None:
            employee_name = f"Employee {employee_code}"

        employee = Employee(
            employee_code=employee_code,
            employee_name=employee_name,
            client_id_assigned=client_id,  # Uses client_id_assigned, not client_id
            is_floating_pool=1 if is_floating_pool else 0,  # Integer boolean
            is_active=1 if is_active else 0,  # Integer boolean
            hire_date=kwargs.get("hire_date"),
            department=kwargs.get("department", "Production"),
            position=kwargs.get("position", "Operator"),
            contact_email=kwargs.get("contact_email"),
            contact_phone=kwargs.get("contact_phone"),
        )
        db.add(employee)
        db.flush()
        return employee

    @staticmethod
    def create_floating_pool_assignment(
        db: Session,
        employee_id: int,
        client_id: Optional[str] = None,
        current_assignment: Optional[str] = None,
        **kwargs,
    ) -> FloatingPool:
        """Create a floating pool availability entry"""
        assignment = FloatingPool(
            employee_id=employee_id,
            client_id=client_id,
            current_assignment=current_assignment,
            available_from=kwargs.get("available_from"),
            available_to=kwargs.get("available_to"),
            notes=kwargs.get("notes"),
        )
        db.add(assignment)
        db.flush()
        return assignment

    # ========================================================================
    # Production Setup (Product, Shift) - Multi-tenant (client_id required)
    # ========================================================================

    @staticmethod
    def create_product(
        db: Session,
        client_id: str,
        product_code: Optional[str] = None,
        product_name: Optional[str] = None,
        ideal_cycle_time: Optional[Decimal] = Decimal("0.15"),
        **kwargs,
    ) -> Product:
        """Create a test product scoped to a client"""
        if product_code is None:
            product_code = TestDataFactory._next_id("PROD")
        if product_name is None:
            product_name = f"Test Product {product_code}"

        product = Product(
            client_id=client_id,
            product_code=product_code,
            product_name=product_name,
            ideal_cycle_time=ideal_cycle_time,
            description=kwargs.get("description"),
            unit_of_measure=kwargs.get("unit_of_measure", "units"),
            is_active=kwargs.get("is_active", True),
        )
        db.add(product)
        db.flush()
        return product

    @staticmethod
    def create_shift(
        db: Session,
        client_id: str,
        shift_name: Optional[str] = None,
        start_time: str = "06:00:00",
        end_time: str = "14:00:00",
        **kwargs,
    ) -> Shift:
        """Create a test shift scoped to a client"""
        if shift_name is None:
            shift_name = f"Shift {TestDataFactory._next_int('shift')}"

        from datetime import time

        start = time.fromisoformat(start_time)
        end = time.fromisoformat(end_time)

        shift = Shift(
            client_id=client_id,
            shift_name=shift_name,
            start_time=start,
            end_time=end,
            is_active=kwargs.get("is_active", True),
        )
        db.add(shift)
        db.flush()
        return shift

    # ========================================================================
    # Work Order Management
    # ========================================================================

    @staticmethod
    def create_work_order(
        db: Session,
        client_id: str,
        work_order_id: Optional[str] = None,
        style_model: Optional[str] = None,
        status: WorkOrderStatus = WorkOrderStatus.RECEIVED,
        planned_quantity: int = 1000,
        **kwargs,
    ) -> WorkOrder:
        """Create a test work order"""
        if work_order_id is None:
            work_order_id = TestDataFactory._next_id("WO")
        if style_model is None:
            style_model = f"STYLE-{work_order_id}"

        work_order = WorkOrder(
            work_order_id=work_order_id,
            client_id=client_id,
            style_model=style_model,
            status=status,
            planned_quantity=planned_quantity,
            actual_quantity=kwargs.get("actual_quantity", 0),
            received_date=kwargs.get("received_date", datetime.now()),
            planned_ship_date=kwargs.get("planned_ship_date"),
            priority=kwargs.get("priority", "NORMAL"),
            notes=kwargs.get("notes"),
        )
        db.add(work_order)
        db.flush()
        return work_order

    @staticmethod
    def create_job(
        db: Session,
        work_order_id: str,
        client_id: str,
        job_id: Optional[str] = None,
        part_number: Optional[str] = None,
        quantity_required: int = 100,
        **kwargs,
    ) -> Job:
        """Create a test job under a work order"""
        if job_id is None:
            job_id = TestDataFactory._next_id("JOB")
        if part_number is None:
            part_number = TestDataFactory._next_id("PART")

        job = Job(
            job_id=job_id,
            work_order_id=work_order_id,
            client_id_fk=client_id,  # Use client_id_fk as per schema
            part_number=part_number,
            planned_quantity=quantity_required,  # Use planned_quantity as per schema
            completed_quantity=kwargs.get("quantity_completed", 0),
            operation_code=kwargs.get("operation_code", "ASSY"),
            operation_name=kwargs.get("operation_name", "Assembly"),
            sequence_number=kwargs.get("sequence_number", 1),
        )
        db.add(job)
        db.flush()
        return job

    @staticmethod
    def create_part_opportunities(
        db: Session, part_number: str, client_id: str, opportunities_per_unit: int = 10, **kwargs
    ) -> PartOpportunities:
        """Create part opportunities (defect opportunities per unit)"""
        part_opp = PartOpportunities(
            part_number=part_number,
            client_id_fk=client_id,  # Use client_id_fk as per schema
            opportunities_per_unit=opportunities_per_unit,
            part_description=kwargs.get("description", f"Part {part_number}"),
        )
        db.add(part_opp)
        db.flush()
        return part_opp

    # ========================================================================
    # Production Tracking
    # ========================================================================

    @staticmethod
    def create_production_entry(
        db: Session,
        client_id: str,
        product_id: int,
        shift_id: int,
        entered_by: str,
        production_date: Optional[date] = None,
        units_produced: int = 1000,
        **kwargs,
    ) -> ProductionEntry:
        """Create a production entry with real data"""
        if production_date is None:
            production_date = date.today()

        prod_datetime = datetime.combine(production_date, datetime.min.time())
        entry_id = TestDataFactory._next_id("PE")

        entry = ProductionEntry(
            production_entry_id=entry_id,
            client_id=client_id,
            product_id=product_id,
            shift_id=shift_id,
            entered_by=entered_by,
            production_date=prod_datetime,
            shift_date=prod_datetime,
            units_produced=units_produced,
            employees_assigned=kwargs.get("employees_assigned", 5),
            employees_present=kwargs.get("employees_present", 5),
            run_time_hours=kwargs.get("run_time_hours", Decimal("8.0")),
            defect_count=kwargs.get("defect_count", 0),
            scrap_count=kwargs.get("scrap_count", 0),
            rework_count=kwargs.get("rework_count", 0),
            setup_time_hours=kwargs.get("setup_time_hours"),
            downtime_hours=kwargs.get("downtime_hours"),
            work_order_id=kwargs.get("work_order_id"),
            job_id=kwargs.get("job_id"),
            ideal_cycle_time=kwargs.get("ideal_cycle_time"),
            notes=kwargs.get("notes"),
        )
        db.add(entry)
        db.flush()
        return entry

    # ========================================================================
    # WIP & Downtime
    # ========================================================================

    @staticmethod
    def create_hold_entry(
        db: Session,
        work_order_id: str,
        client_id: str,
        created_by: str,
        hold_reason: str = "QUALITY_ISSUE",
        hold_status: HoldStatus = HoldStatus.PENDING_HOLD_APPROVAL,
        **kwargs,
    ) -> HoldEntry:
        """Create a hold entry"""
        from backend.schemas.hold_entry import HoldReason

        hold_id = TestDataFactory._next_id("HOLD")

        hold = HoldEntry(
            hold_entry_id=hold_id,
            work_order_id=work_order_id,
            client_id=client_id,
            hold_initiated_by=created_by,
            hold_reason=HoldReason[hold_reason] if hold_reason in HoldReason.__members__ else HoldReason.QUALITY_ISSUE,
            hold_reason_category=kwargs.get("hold_reason_category", "QUALITY"),
            hold_status=hold_status,
            hold_date=kwargs.get("hold_date", datetime.now()),
            resume_date=kwargs.get("resume_date"),
            hold_approved_by=kwargs.get("hold_approved_by"),
            job_id=kwargs.get("job_id"),
        )
        db.add(hold)
        db.flush()
        return hold

    @staticmethod
    def create_downtime_entry(
        db: Session,
        client_id: str,
        work_order_id: str,
        reported_by: str,
        downtime_reason: str = "EQUIPMENT_FAILURE",
        shift_date: Optional[datetime] = None,
        duration_minutes: int = 60,
        **kwargs,
    ) -> DowntimeEntry:
        """Create a downtime entry"""
        entry_id = TestDataFactory._next_id("DT")

        if shift_date is None:
            shift_date = datetime.now()

        entry = DowntimeEntry(
            downtime_entry_id=entry_id,
            client_id=client_id,
            work_order_id=work_order_id,
            reported_by=reported_by,
            downtime_reason=downtime_reason,
            shift_date=shift_date,
            downtime_duration_minutes=duration_minutes,
            machine_id=kwargs.get("machine_id", "MACH-001"),
            equipment_code=kwargs.get("equipment_code"),
            notes=kwargs.get("notes", "Test downtime event"),
        )
        db.add(entry)
        db.flush()
        return entry

    # ========================================================================
    # Attendance
    # ========================================================================

    @staticmethod
    def create_attendance_entry(
        db: Session, employee_id: int, client_id: str, shift_id: int, shift_date: Optional[date] = None, **kwargs
    ) -> AttendanceEntry:
        """Create an attendance entry"""
        if shift_date is None:
            shift_date = date.today()

        entry_id = TestDataFactory._next_id("ATT")

        # Convert date to datetime for shift_date field
        from datetime import datetime

        shift_datetime = datetime.combine(shift_date, datetime.min.time())

        entry = AttendanceEntry(
            attendance_entry_id=entry_id,
            employee_id=employee_id,
            client_id=client_id,
            shift_id=shift_id,
            shift_date=shift_datetime,
            scheduled_hours=kwargs.get("scheduled_hours", Decimal("8.0")),
            actual_hours=kwargs.get("actual_hours", Decimal("8.0")),
            absence_hours=kwargs.get("absence_hours", Decimal("0")),
            absence_type=kwargs.get("absence_type"),
            is_absent=kwargs.get("is_absent", 0),  # Integer boolean (0=present, 1=absent)
            arrival_time=kwargs.get("arrival_time"),
            departure_time=kwargs.get("departure_time"),
        )
        db.add(entry)
        db.flush()
        return entry

    @staticmethod
    def create_coverage_entry(
        db: Session, shift_id: int, client_id: str, coverage_date: Optional[date] = None, **kwargs
    ) -> CoverageEntry:
        """Create a shift coverage entry"""
        if coverage_date is None:
            coverage_date = date.today()

        entry_id = TestDataFactory._next_id("COV")

        entry = CoverageEntry(
            coverage_entry_id=entry_id,
            shift_id=shift_id,
            client_id=client_id,
            coverage_date=coverage_date,
            required_headcount=kwargs.get("required_headcount", 10),
            actual_headcount=kwargs.get("actual_headcount", 10),
            coverage_percentage=kwargs.get("coverage_percentage", Decimal("100.0")),
        )
        db.add(entry)
        db.flush()
        return entry

    # ========================================================================
    # Quality
    # ========================================================================

    @staticmethod
    def create_quality_entry(
        db: Session,
        work_order_id: str,
        client_id: str,
        inspector_id: str,
        inspection_date: Optional[date] = None,
        units_inspected: int = 1000,
        **kwargs,
    ) -> QualityEntry:
        """Create a quality entry"""
        if inspection_date is None:
            inspection_date = date.today()

        insp_datetime = datetime.combine(inspection_date, datetime.min.time())
        entry_id = TestDataFactory._next_id("QE")

        units_defective = kwargs.get("units_defective", 5)
        units_passed = units_inspected - units_defective

        entry = QualityEntry(
            quality_entry_id=entry_id,
            work_order_id=work_order_id,
            client_id=client_id,
            inspector_id=inspector_id,
            inspection_date=insp_datetime,
            shift_date=insp_datetime,
            units_inspected=units_inspected,
            units_passed=units_passed,
            units_defective=units_defective,
            total_defects_count=kwargs.get("total_defects_count", units_defective),
            units_scrapped=kwargs.get("units_scrapped", units_defective // 2),
            units_reworked=kwargs.get("units_reworked", units_defective - units_defective // 2),
        )
        db.add(entry)
        db.flush()
        return entry

    @staticmethod
    def create_defect_detail(
        db: Session,
        quality_entry_id: str,
        defect_type: DefectType = DefectType.STITCHING,
        defect_count: int = 1,
        **kwargs,
    ) -> DefectDetail:
        """Create a defect detail record"""
        detail_id = TestDataFactory._next_id("DD")

        detail = DefectDetail(
            defect_detail_id=detail_id,
            quality_entry_id=quality_entry_id,
            defect_type=defect_type,
            defect_count=defect_count,
            severity=kwargs.get("severity", "MINOR"),
            location=kwargs.get("location", "Front"),
            description=kwargs.get("description", "Test defect"),
        )
        db.add(detail)
        db.flush()
        return detail

    @staticmethod
    def create_defect_type_catalog(
        db: Session, client_id: str, defect_code: Optional[str] = None, defect_name: Optional[str] = None, **kwargs
    ) -> DefectTypeCatalog:
        """Create a defect type catalog entry"""
        if defect_code is None:
            defect_code = TestDataFactory._next_id("DEF")
        if defect_name is None:
            defect_name = f"Defect Type {defect_code}"

        catalog = DefectTypeCatalog(
            defect_code=defect_code,
            defect_name=defect_name,
            client_id=client_id,
            category=kwargs.get("category", "VISUAL"),
            severity_default=kwargs.get("severity_default", "MINOR"),
            is_active=kwargs.get("is_active", 1),
        )
        db.add(catalog)
        db.flush()
        return catalog

    # ========================================================================
    # User Preferences & Filters
    # ========================================================================

    @staticmethod
    def create_saved_filter(
        db: Session,
        user_id: str,
        filter_name: Optional[str] = None,
        filter_type: str = "production",
        filter_criteria: Optional[dict] = None,
        **kwargs,
    ) -> SavedFilter:
        """Create a saved filter"""
        if filter_name is None:
            filter_name = f"Filter {TestDataFactory._next_int('filter')}"
        if filter_criteria is None:
            filter_criteria = {"status": "active", "date_range": "last_7_days"}

        import json

        saved_filter = SavedFilter(
            user_id=user_id,
            filter_name=filter_name,
            filter_type=filter_type,
            filter_criteria=json.dumps(filter_criteria),
            is_default=kwargs.get("is_default", 0),
            is_shared=kwargs.get("is_shared", 0),
        )
        db.add(saved_filter)
        db.flush()
        return saved_filter

    # ========================================================================
    # Workflow
    # ========================================================================

    @staticmethod
    def create_workflow_transition(
        db: Session,
        work_order_id: str,
        from_status: str,
        to_status: str,
        transitioned_by: str,
        client_id: str,
        **kwargs,
    ) -> WorkflowTransitionLog:
        """Create a workflow transition log"""
        log_id = TestDataFactory._next_id("TRANS")

        transition = WorkflowTransitionLog(
            transition_log_id=log_id,
            work_order_id=work_order_id,
            from_status=from_status,
            to_status=to_status,
            transitioned_by=transitioned_by,
            client_id=client_id,
            transition_timestamp=kwargs.get("transition_timestamp", datetime.now()),
            reason=kwargs.get("reason", "Test transition"),
            job_id=kwargs.get("job_id"),
        )
        db.add(transition)
        db.flush()
        return transition

    # ========================================================================
    # Batch Creation Helpers
    # ========================================================================

    @classmethod
    def create_production_entries(
        cls, db: Session, count: int = 10, client_id: str = "CLIENT-A", base_date: Optional[date] = None
    ) -> List[ProductionEntry]:
        """
        Backwards-compatible method for creating production entries.
        Creates required dependencies (product, shift, user) automatically.
        """
        # Ensure we have a client
        from backend.schemas import Client, ClientType

        client = db.query(Client).filter(Client.client_id == client_id).first()
        if not client:
            client = cls.create_client(db, client_id=client_id)

        # Create or get product for this client
        from backend.schemas import Product

        product = db.query(Product).filter(Product.client_id == client_id).first()
        if not product:
            product = cls.create_product(db, client_id=client_id)

        # Create or get shift for this client
        from backend.schemas import Shift

        shift = db.query(Shift).filter(Shift.client_id == client_id).first()
        if not shift:
            shift = cls.create_shift(db, client_id=client_id)

        # Create or get user
        from backend.schemas import User

        user = db.query(User).filter(User.client_id_assigned == client_id).first()
        if not user:
            user = cls.create_user(db, client_id=client_id, role="supervisor")

        db.flush()

        return cls.create_production_entries_batch(
            db=db,
            client_id=client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            count=count,
            base_date=base_date,
        )

    @classmethod
    def create_production_entries_batch(
        cls,
        db: Session,
        client_id: str,
        product_id: int,
        shift_id: int,
        entered_by: str,
        count: int = 10,
        base_date: Optional[date] = None,
        work_order_ids: Optional[List[str]] = None,
    ) -> List[ProductionEntry]:
        """Create multiple production entries over consecutive days"""
        if base_date is None:
            base_date = date.today() - timedelta(days=count)

        entries = []
        for i in range(count):
            # Rotate through work orders if provided
            work_order_id = None
            if work_order_ids:
                work_order_id = work_order_ids[i % len(work_order_ids)]

            entry = cls.create_production_entry(
                db,
                client_id=client_id,
                product_id=product_id,
                shift_id=shift_id,
                entered_by=entered_by,
                production_date=base_date + timedelta(days=i),
                units_produced=1000 + (i * 50),
                work_order_id=work_order_id,
            )
            entries.append(entry)

        return entries

    @classmethod
    def create_quality_inspections(
        cls, db: Session, count: int = 10, client_id: str = "CLIENT-A", defect_rate: float = 0.005
    ) -> List[QualityEntry]:
        """
        Backwards-compatible method for creating quality inspections.
        Creates required dependencies (client, work order, user) automatically.
        Uses EXACT defect rate (no variation) for test predictability.
        """
        # Ensure we have a client
        from backend.schemas import Client, ClientType

        client = db.query(Client).filter(Client.client_id == client_id).first()
        if not client:
            client = cls.create_client(db, client_id=client_id)

        # Create or get user
        from backend.schemas import User

        user = db.query(User).filter(User.client_id_assigned == client_id).first()
        if not user:
            user = cls.create_user(db, client_id=client_id, role="supervisor")

        # Create or get work order
        from backend.schemas import WorkOrder

        work_order = db.query(WorkOrder).filter(WorkOrder.client_id == client_id).first()
        if not work_order:
            work_order = cls.create_work_order(db, client_id=client_id)

        db.flush()

        # Create entries with EXACT defect rate (no variation for test predictability)
        base_date = date.today() - timedelta(days=count)
        entries = []
        for i in range(count):
            units = 1000
            defects = int(units * defect_rate)  # Exact rate, no variation

            entry = cls.create_quality_entry(
                db,
                work_order_id=work_order.work_order_id,
                client_id=client_id,
                inspector_id=user.user_id,
                inspection_date=base_date + timedelta(days=i),
                units_inspected=units,
                units_defective=defects,
            )
            entries.append(entry)

        db.commit()
        return entries

    @classmethod
    def create_quality_entries_batch(
        cls,
        db: Session,
        work_order_id: str,
        client_id: str,
        inspector_id: str,
        count: int = 10,
        base_date: Optional[date] = None,
        defect_rate: float = 0.005,
    ) -> List[QualityEntry]:
        """Create multiple quality entries with realistic defect rates"""
        if base_date is None:
            base_date = date.today() - timedelta(days=count)

        entries = []
        for i in range(count):
            units = 1000
            defects = int(units * defect_rate * (1 + (i % 3) * 0.1))

            entry = cls.create_quality_entry(
                db,
                work_order_id=work_order_id,
                client_id=client_id,
                inspector_id=inspector_id,
                inspection_date=base_date + timedelta(days=i),
                units_inspected=units,
                units_defective=defects,
            )
            entries.append(entry)

        return entries

    @classmethod
    def create_attendance_entries_batch(
        cls,
        db: Session,
        employee_id: int,
        client_id: str,
        shift_id: int,
        count: int = 30,
        base_date: Optional[date] = None,
        attendance_rate: float = 0.95,
    ) -> List[AttendanceEntry]:
        """Create multiple attendance entries with realistic attendance patterns"""
        import random

        if base_date is None:
            base_date = date.today() - timedelta(days=count)

        entries = []
        for i in range(count):
            current_date = base_date + timedelta(days=i)
            if current_date.weekday() >= 5:
                continue

            is_present = random.random() < attendance_rate

            entry = cls.create_attendance_entry(
                db,
                employee_id=employee_id,
                client_id=client_id,
                shift_id=shift_id,
                shift_date=current_date,
                is_absent=0 if is_present else 1,
                actual_hours=Decimal("8.0") if is_present else Decimal("0"),
                absence_hours=Decimal("0") if is_present else Decimal("8.0"),
                absence_type=AbsenceType.UNSCHEDULED_ABSENCE if not is_present else None,
            )
            entries.append(entry)

        return entries
