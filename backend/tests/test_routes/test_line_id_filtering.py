"""
Tests for line_id FK on operational tables.

Validates that line_id is properly added to:
- Shift
- ProductionEntry
- DowntimeEntry
- AttendanceEntry

Tests backward compatibility (None accepted) and Pydantic model validation.
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.orm.production_line import ProductionLine
from backend.orm.client import Client, ClientType
from backend.orm.user import User, UserRole
from backend.orm.product import Product
from backend.orm.shift import Shift
from backend.orm.production_entry import ProductionEntry
from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.work_order import WorkOrder
from backend.orm.employee import Employee

from backend.schemas.production import (
    ProductionEntryCreate,
    ProductionEntryUpdate,
    ProductionEntryResponse,
)
from backend.schemas.downtime import (
    DowntimeEventCreate,
    DowntimeEventUpdate,
    DowntimeEventResponse,
)
from backend.schemas.attendance import (
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceRecordResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def line_test_db():
    """In-memory SQLite session with all tables created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def seed_base_data(line_test_db):
    """Seed minimal data required for FK constraints."""
    db = line_test_db

    # Client
    client = Client(
        client_id="LINE-TEST",
        client_name="Line Test Co",
        client_contact="Tester",
        client_email="line@test.com",
        client_type=ClientType.PIECE_RATE,
        is_active=1,
    )
    db.add(client)
    db.flush()

    # User (for entered_by FK)
    user = User(
        user_id="line-user-001",
        username="line_user",
        email="lineuser@test.com",
        password_hash="hashed",
        role=UserRole.OPERATOR,
        is_active=1,
        client_id_assigned="LINE-TEST",
    )
    db.add(user)
    db.flush()

    # Product
    product = Product(
        client_id="LINE-TEST",
        product_code="LP-001",
        product_name="Line Product",
        unit_of_measure="pieces",
        is_active=True,
    )
    db.add(product)
    db.flush()

    # Shift
    from datetime import time as dt_time

    shift = Shift(
        client_id="LINE-TEST",
        shift_name="Day",
        start_time=dt_time(6, 0),
        end_time=dt_time(14, 0),
        is_active=True,
    )
    db.add(shift)
    db.flush()

    # Work order
    wo = WorkOrder(
        work_order_id="WO-LINE-001",
        client_id="LINE-TEST",
        style_model="LP-001",
        planned_quantity=100,
        status="RECEIVED",
    )
    db.add(wo)
    db.flush()

    # Employee
    emp = Employee(
        employee_code="EMP-LINE-001",
        employee_name="Line Worker",
        client_id_assigned="LINE-TEST",
        is_active=1,
    )
    db.add(emp)
    db.flush()

    # Production Line
    line = ProductionLine(
        client_id="LINE-TEST",
        line_code="SEW-01",
        line_name="Sewing Line 1",
        department="SEWING",
        line_type="DEDICATED",
        is_active=True,
    )
    db.add(line)
    db.flush()

    db.commit()

    return {
        "client": client,
        "user": user,
        "product": product,
        "shift": shift,
        "work_order": wo,
        "employee": emp,
        "line": line,
        "db": db,
    }


# ---------------------------------------------------------------------------
# Schema column existence tests
# ---------------------------------------------------------------------------


class TestLineIdColumnExists:
    """Verify line_id column exists on all 4 operational tables."""

    def test_shift_has_line_id_column(self):
        columns = [c.name for c in Shift.__table__.columns]
        assert "line_id" in columns

    def test_production_entry_has_line_id_column(self):
        columns = [c.name for c in ProductionEntry.__table__.columns]
        assert "line_id" in columns

    def test_downtime_entry_has_line_id_column(self):
        columns = [c.name for c in DowntimeEntry.__table__.columns]
        assert "line_id" in columns

    def test_attendance_entry_has_line_id_column(self):
        columns = [c.name for c in AttendanceEntry.__table__.columns]
        assert "line_id" in columns

    def test_line_id_is_nullable_on_shift(self):
        col = Shift.__table__.columns["line_id"]
        assert col.nullable is True

    def test_line_id_is_nullable_on_production_entry(self):
        col = ProductionEntry.__table__.columns["line_id"]
        assert col.nullable is True

    def test_line_id_is_nullable_on_downtime_entry(self):
        col = DowntimeEntry.__table__.columns["line_id"]
        assert col.nullable is True

    def test_line_id_is_nullable_on_attendance_entry(self):
        col = AttendanceEntry.__table__.columns["line_id"]
        assert col.nullable is True

    def test_line_id_is_indexed_on_production_entry(self):
        col = ProductionEntry.__table__.columns["line_id"]
        assert col.index is True

    def test_line_id_has_fk_to_production_line(self):
        col = ProductionEntry.__table__.columns["line_id"]
        fk_targets = [fk.target_fullname for fk in col.foreign_keys]
        assert "PRODUCTION_LINE.line_id" in fk_targets


# ---------------------------------------------------------------------------
# Backward compatibility: records without line_id
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Existing records without line_id should still work (NULL accepted)."""

    def test_production_entry_without_line_id(self, seed_base_data):
        db = seed_base_data["db"]
        now = datetime.utcnow()
        entry = ProductionEntry(
            production_entry_id="PE-NOLN-001",
            client_id="LINE-TEST",
            product_id=seed_base_data["product"].product_id,
            shift_id=seed_base_data["shift"].shift_id,
            production_date=now,
            shift_date=now,
            units_produced=100,
            run_time_hours=Decimal("7.5"),
            employees_assigned=4,
            defect_count=2,
            scrap_count=1,
            entered_by=1,
            # line_id intentionally omitted (defaults to NULL)
        )
        db.add(entry)
        db.commit()

        fetched = db.query(ProductionEntry).filter_by(
            production_entry_id="PE-NOLN-001"
        ).one()
        assert fetched.line_id is None

    def test_downtime_entry_without_line_id(self, seed_base_data):
        db = seed_base_data["db"]
        now = datetime.utcnow()
        entry = DowntimeEntry(
            downtime_entry_id="DT-NOLN-001",
            client_id="LINE-TEST",
            work_order_id="WO-LINE-001",
            shift_date=now,
            downtime_reason="Equipment Maintenance",
            downtime_duration_minutes=30,
        )
        db.add(entry)
        db.commit()

        fetched = db.query(DowntimeEntry).filter_by(
            downtime_entry_id="DT-NOLN-001"
        ).one()
        assert fetched.line_id is None

    def test_attendance_entry_without_line_id(self, seed_base_data):
        db = seed_base_data["db"]
        now = datetime.utcnow()
        entry = AttendanceEntry(
            attendance_entry_id="ATT-NOLN-001",
            client_id="LINE-TEST",
            employee_id=seed_base_data["employee"].employee_id,
            shift_date=now,
            scheduled_hours=Decimal("8.0"),
            is_absent=0,
        )
        db.add(entry)
        db.commit()

        fetched = db.query(AttendanceEntry).filter_by(
            attendance_entry_id="ATT-NOLN-001"
        ).one()
        assert fetched.line_id is None

    def test_shift_without_line_id(self, seed_base_data):
        """The existing seeded shift should have line_id=None."""
        shift = seed_base_data["shift"]
        assert shift.line_id is None


# ---------------------------------------------------------------------------
# Records WITH line_id
# ---------------------------------------------------------------------------


class TestWithLineId:
    """Records can include a valid line_id."""

    def test_production_entry_with_line_id(self, seed_base_data):
        db = seed_base_data["db"]
        line = seed_base_data["line"]
        now = datetime.utcnow()

        entry = ProductionEntry(
            production_entry_id="PE-LN-001",
            client_id="LINE-TEST",
            product_id=seed_base_data["product"].product_id,
            shift_id=seed_base_data["shift"].shift_id,
            production_date=now,
            shift_date=now,
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=1,
            scrap_count=0,
            entered_by=1,
            line_id=line.line_id,
        )
        db.add(entry)
        db.commit()

        fetched = db.query(ProductionEntry).filter_by(
            production_entry_id="PE-LN-001"
        ).one()
        assert fetched.line_id == line.line_id

    def test_downtime_entry_with_line_id(self, seed_base_data):
        db = seed_base_data["db"]
        line = seed_base_data["line"]
        now = datetime.utcnow()

        entry = DowntimeEntry(
            downtime_entry_id="DT-LN-001",
            client_id="LINE-TEST",
            work_order_id="WO-LINE-001",
            shift_date=now,
            downtime_reason="Material Shortage",
            downtime_duration_minutes=45,
            line_id=line.line_id,
        )
        db.add(entry)
        db.commit()

        fetched = db.query(DowntimeEntry).filter_by(
            downtime_entry_id="DT-LN-001"
        ).one()
        assert fetched.line_id == line.line_id

    def test_attendance_entry_with_line_id(self, seed_base_data):
        db = seed_base_data["db"]
        line = seed_base_data["line"]
        now = datetime.utcnow()

        entry = AttendanceEntry(
            attendance_entry_id="ATT-LN-001",
            client_id="LINE-TEST",
            employee_id=seed_base_data["employee"].employee_id,
            shift_date=now,
            scheduled_hours=Decimal("8.0"),
            is_absent=0,
            line_id=line.line_id,
        )
        db.add(entry)
        db.commit()

        fetched = db.query(AttendanceEntry).filter_by(
            attendance_entry_id="ATT-LN-001"
        ).one()
        assert fetched.line_id == line.line_id

    def test_shift_with_line_id(self, seed_base_data):
        db = seed_base_data["db"]
        line = seed_base_data["line"]
        from datetime import time as dt_time

        shift = Shift(
            client_id="LINE-TEST",
            shift_name="Night",
            start_time=dt_time(22, 0),
            end_time=dt_time(6, 0),
            is_active=True,
            line_id=line.line_id,
        )
        db.add(shift)
        db.commit()

        fetched = db.query(Shift).filter_by(shift_name="Night").one()
        assert fetched.line_id == line.line_id


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestPydanticModels:
    """Pydantic create/update/response models accept line_id."""

    # --- ProductionEntry ---

    def test_production_create_without_line_id(self):
        model = ProductionEntryCreate(
            client_id="C1",
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
        )
        assert model.line_id is None

    def test_production_create_with_line_id(self):
        model = ProductionEntryCreate(
            client_id="C1",
            product_id=1,
            shift_id=1,
            production_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            line_id=42,
        )
        assert model.line_id == 42

    def test_production_update_with_line_id(self):
        model = ProductionEntryUpdate(line_id=7)
        assert model.line_id == 7

    def test_production_update_without_line_id(self):
        model = ProductionEntryUpdate(units_produced=50)
        assert model.line_id is None

    def test_production_response_includes_line_id(self):
        model = ProductionEntryResponse(
            production_entry_id="PE-001",
            client_id="C1",
            product_id=1,
            shift_id=1,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=100,
            run_time_hours=Decimal("8"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            line_id=3,
        )
        assert model.line_id == 3

    def test_production_response_line_id_none(self):
        model = ProductionEntryResponse(
            production_entry_id="PE-002",
            client_id="C1",
            product_id=1,
            shift_id=1,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=100,
            run_time_hours=Decimal("8"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
        )
        assert model.line_id is None

    # --- DowntimeEvent ---

    def test_downtime_create_without_line_id(self):
        model = DowntimeEventCreate(
            client_id="C1",
            work_order_id="WO-001",
            shift_date=date.today(),
            downtime_reason="EQUIPMENT_FAILURE",
            downtime_duration_minutes=30,
        )
        assert model.line_id is None

    def test_downtime_create_with_line_id(self):
        model = DowntimeEventCreate(
            client_id="C1",
            work_order_id="WO-001",
            shift_date=date.today(),
            downtime_reason="MAINTENANCE",
            downtime_duration_minutes=60,
            line_id=10,
        )
        assert model.line_id == 10

    def test_downtime_update_with_line_id(self):
        model = DowntimeEventUpdate(line_id=5)
        assert model.line_id == 5

    def test_downtime_response_includes_line_id(self):
        model = DowntimeEventResponse(
            downtime_entry_id="DT-001",
            client_id="C1",
            work_order_id="WO-001",
            shift_date=datetime.now(),
            downtime_reason="MAINTENANCE",
            downtime_duration_minutes=45,
            line_id=8,
        )
        assert model.line_id == 8

    # --- AttendanceRecord ---

    def test_attendance_create_without_line_id(self):
        model = AttendanceRecordCreate(
            client_id="C1",
            employee_id=1,
            shift_date=date.today(),
            scheduled_hours=Decimal("8.0"),
        )
        assert model.line_id is None

    def test_attendance_create_with_line_id(self):
        model = AttendanceRecordCreate(
            client_id="C1",
            employee_id=1,
            shift_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            line_id=15,
        )
        assert model.line_id == 15

    def test_attendance_update_with_line_id(self):
        model = AttendanceRecordUpdate(line_id=3)
        assert model.line_id == 3

    def test_attendance_response_includes_line_id(self):
        model = AttendanceRecordResponse(
            attendance_entry_id="ATT-001",
            client_id="C1",
            employee_id=1,
            shift_date=datetime.now(),
            scheduled_hours=Decimal("8.0"),
            is_absent=0,
            line_id=12,
        )
        assert model.line_id == 12


# ---------------------------------------------------------------------------
# shift_date model_validator still works (regression check)
# ---------------------------------------------------------------------------


class TestShiftDateValidatorPreserved:
    """Ensure the model_validator for shift_date auto-default is intact."""

    def test_shift_date_defaults_to_production_date(self):
        today = date.today()
        model = ProductionEntryCreate(
            client_id="C1",
            product_id=1,
            shift_id=1,
            production_date=today,
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
        )
        assert model.shift_date == today

    def test_shift_date_explicit_overrides_default(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        model = ProductionEntryCreate(
            client_id="C1",
            product_id=1,
            shift_id=1,
            production_date=today,
            shift_date=yesterday,
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
        )
        assert model.shift_date == yesterday
