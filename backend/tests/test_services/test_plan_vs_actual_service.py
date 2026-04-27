"""
Plan vs Actual Service Tests
Tests the service layer for plan vs actual comparison logic.

Uses real in-memory SQLite database -- NO mocks for DB layer.
"""

import pytest
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.orm.capacity.orders import CapacityOrder, OrderStatus, OrderPriority
from backend.orm.work_order import WorkOrder, WorkOrderStatus
from backend.orm.production_entry import ProductionEntry
from backend.orm.production_line import ProductionLine
from backend.orm.user import User, UserRole
from backend.orm.client import Client, ClientType
from backend.orm.product import Product
from backend.orm.shift import Shift
from backend.tests.fixtures.factories import TestDataFactory
from backend.services.plan_vs_actual_service import (
    get_plan_vs_actual,
    get_plan_vs_actual_summary,
    _calculate_risk,
    _project_completion,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLIENT_ID = "PVA-TEST-CLIENT"
CLIENT_B_ID = "PVA-TEST-CLIENT-B"


@pytest.fixture(scope="function")
def pva_db():
    """Create a fresh in-memory database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def admin_user(pva_db):
    """Create an admin user (can see all clients)."""
    client = TestDataFactory.create_client(pva_db, client_id=CLIENT_ID, client_name="PVA Test Client")
    user = TestDataFactory.create_user(
        pva_db,
        username="pva_admin",
        role="admin",
        client_id=None,
    )
    pva_db.commit()
    return user


@pytest.fixture
def operator_user_a(pva_db):
    """Create an operator user scoped to CLIENT_ID."""
    user = TestDataFactory.create_user(
        pva_db,
        username="pva_operator_a",
        role="operator",
        client_id=CLIENT_ID,
    )
    pva_db.commit()
    return user


def _ensure_client(db, client_id, client_name=None):
    """Ensure a CLIENT row exists (idempotent)."""
    existing = db.query(Client).filter(Client.client_id == client_id).first()
    if existing:
        return existing
    return TestDataFactory.create_client(db, client_id=client_id, client_name=client_name or f"Client {client_id}")


def _create_capacity_order(db, client_id, **overrides):
    """Helper to create a CapacityOrder with sensible defaults."""
    _ensure_client(db, client_id)
    defaults = {
        "client_id": client_id,
        "order_number": f"CPL-{TestDataFactory._next_id('CPL')}",
        "style_model": "TEST-STYLE",
        "order_quantity": 1000,
        "required_date": date.today() + timedelta(days=30),
        "status": OrderStatus.CONFIRMED,
        "priority": OrderPriority.NORMAL,
    }
    defaults.update(overrides)
    cap_order = CapacityOrder(**defaults)
    db.add(cap_order)
    db.flush()
    return cap_order


def _create_linked_work_order(db, cap_order, actual_quantity=0, **overrides):
    """Create a WorkOrder linked to a CapacityOrder."""
    wo_id = TestDataFactory._next_id("WO")
    defaults = {
        "work_order_id": wo_id,
        "client_id": cap_order.client_id,
        "style_model": cap_order.style_model,
        "planned_quantity": cap_order.order_quantity,
        "actual_quantity": actual_quantity,
        "capacity_order_id": cap_order.id,
        "origin": "PLANNED",
        "status": WorkOrderStatus.IN_PROGRESS,
        "received_date": datetime.now(tz=timezone.utc),
    }
    defaults.update(overrides)
    wo = WorkOrder(**defaults)
    db.add(wo)
    db.flush()
    return wo


def _create_production_prereqs(db, client_id):
    """Create product, shift, user needed for production entries. Returns (product, shift, user)."""
    _ensure_client(db, client_id)
    product = db.query(Product).filter(Product.client_id == client_id).first()
    if not product:
        product = TestDataFactory.create_product(db, client_id=client_id)
    shift = db.query(Shift).filter(Shift.client_id == client_id).first()
    if not shift:
        shift = TestDataFactory.create_shift(db, client_id=client_id)
    user = db.query(User).filter(User.client_id_assigned == client_id).first()
    if not user:
        user = TestDataFactory.create_user(db, client_id=client_id, role="operator")
    db.flush()
    return product, shift, user


def _create_production_entry(db, client_id, work_order_id, units, product_id, shift_id, entered_by, line_id=None):
    """Create a production entry linked to a work order."""
    entry_id = TestDataFactory._next_id("PE")
    prod_dt = datetime.combine(date.today(), datetime.min.time())
    pe = ProductionEntry(
        production_entry_id=entry_id,
        client_id=client_id,
        product_id=product_id,
        shift_id=shift_id,
        entered_by=entered_by,
        production_date=prod_dt,
        shift_date=prod_dt,
        work_order_id=work_order_id,
        units_produced=units,
        employees_assigned=5,
        run_time_hours=Decimal("8.0"),
        defect_count=0,
        scrap_count=0,
        line_id=line_id,
    )
    db.add(pe)
    db.flush()
    return pe


def _create_production_line(db, client_id, line_code="LINE-01"):
    """Create a ProductionLine and return it."""
    _ensure_client(db, client_id)
    line = ProductionLine(
        client_id=client_id,
        line_code=line_code,
        line_name=f"Test Line {line_code}",
        line_type="DEDICATED",
    )
    db.add(line)
    db.flush()
    return line


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPlanVsActualWithLinkedOrders:
    """Test plan vs actual with linked capacity order -> work order -> production entries."""

    def test_plan_vs_actual_with_linked_orders(self, pva_db, admin_user):
        """CapacityOrder + linked WorkOrder + ProductionEntry -> verify variance."""
        cap = _create_capacity_order(pva_db, CLIENT_ID, order_quantity=1000)
        wo = _create_linked_work_order(pva_db, cap, actual_quantity=400)
        product, shift, user = _create_production_prereqs(pva_db, CLIENT_ID)
        _create_production_entry(
            pva_db, CLIENT_ID, wo.work_order_id, 500, product.product_id, shift.shift_id, user.user_id
        )
        pva_db.commit()

        results = get_plan_vs_actual(pva_db, admin_user, client_id=CLIENT_ID)

        assert len(results) == 1
        entry = results[0]
        assert entry["capacity_order_id"] == cap.id
        assert entry["planned_quantity"] == 1000
        # actual_completed = max(wo_actual=400, production_total=500) = 500
        assert entry["actual_completed"] == 500
        assert entry["variance_quantity"] == 500 - 1000  # -500
        assert entry["variance_percentage"] == -50.0
        assert entry["completion_percentage"] == 50.0
        assert entry["linked_work_orders"] == 1
        assert len(entry["line_breakdown"]) >= 1  # UNASSIGNED entry

    def test_plan_vs_actual_no_production(self, pva_db, admin_user):
        """CapacityOrder + linked WorkOrder but no production entries."""
        cap = _create_capacity_order(pva_db, CLIENT_ID, order_quantity=500)
        wo = _create_linked_work_order(pva_db, cap, actual_quantity=200)
        pva_db.commit()

        results = get_plan_vs_actual(pva_db, admin_user, client_id=CLIENT_ID)

        assert len(results) == 1
        entry = results[0]
        assert entry["planned_quantity"] == 500
        assert entry["actual_completed"] == 200  # Only WO actual_quantity
        assert entry["variance_quantity"] == -300
        assert entry["linked_work_orders"] == 1
        assert entry["line_breakdown"] == []

    def test_plan_vs_actual_multiple_orders(self, pva_db, admin_user):
        """Multiple capacity orders with different statuses."""
        cap1 = _create_capacity_order(pva_db, CLIENT_ID, order_quantity=1000, status=OrderStatus.CONFIRMED)
        cap2 = _create_capacity_order(pva_db, CLIENT_ID, order_quantity=2000, status=OrderStatus.IN_PROGRESS)
        # Draft should be excluded by default
        _create_capacity_order(pva_db, CLIENT_ID, order_quantity=500, status=OrderStatus.DRAFT)
        pva_db.commit()

        results = get_plan_vs_actual(pva_db, admin_user, client_id=CLIENT_ID)

        assert len(results) == 2
        order_ids = {r["capacity_order_id"] for r in results}
        assert cap1.id in order_ids
        assert cap2.id in order_ids


class TestPlanVsActualFilters:
    """Test filtering by date, line, and status."""

    def test_plan_vs_actual_date_filter(self, pva_db, admin_user):
        """Filter by required_date range."""
        today = date.today()
        cap_in_range = _create_capacity_order(pva_db, CLIENT_ID, required_date=today + timedelta(days=10))
        _create_capacity_order(pva_db, CLIENT_ID, required_date=today + timedelta(days=60))
        pva_db.commit()

        results = get_plan_vs_actual(
            pva_db,
            admin_user,
            client_id=CLIENT_ID,
            start_date=today,
            end_date=today + timedelta(days=20),
        )

        assert len(results) == 1
        assert results[0]["capacity_order_id"] == cap_in_range.id

    def test_plan_vs_actual_line_filter(self, pva_db, admin_user):
        """Filter production by line_id."""
        cap = _create_capacity_order(pva_db, CLIENT_ID, order_quantity=1000)
        wo = _create_linked_work_order(pva_db, cap, actual_quantity=0)
        product, shift, user = _create_production_prereqs(pva_db, CLIENT_ID)

        line1 = _create_production_line(pva_db, CLIENT_ID, line_code="LINE-A")
        line2 = _create_production_line(pva_db, CLIENT_ID, line_code="LINE-B")

        _create_production_entry(
            pva_db,
            CLIENT_ID,
            wo.work_order_id,
            300,
            product.product_id,
            shift.shift_id,
            user.user_id,
            line_id=line1.line_id,
        )
        _create_production_entry(
            pva_db,
            CLIENT_ID,
            wo.work_order_id,
            200,
            product.product_id,
            shift.shift_id,
            user.user_id,
            line_id=line2.line_id,
        )
        pva_db.commit()

        # Filter for line1 only
        results = get_plan_vs_actual(pva_db, admin_user, client_id=CLIENT_ID, line_id=line1.line_id)

        assert len(results) == 1
        entry = results[0]
        # Only line1 production (300) is counted, but WO actual (0) is also considered
        assert entry["actual_completed"] == 300
        assert len(entry["line_breakdown"]) == 1
        assert entry["line_breakdown"][0]["line_id"] == str(line1.line_id)

    def test_plan_vs_actual_excludes_draft_and_cancelled(self, pva_db, admin_user):
        """Default filter excludes DRAFT and CANCELLED orders."""
        _create_capacity_order(pva_db, CLIENT_ID, status=OrderStatus.DRAFT)
        _create_capacity_order(pva_db, CLIENT_ID, status=OrderStatus.CANCELLED)
        confirmed = _create_capacity_order(pva_db, CLIENT_ID, status=OrderStatus.CONFIRMED)
        pva_db.commit()

        results = get_plan_vs_actual(pva_db, admin_user, client_id=CLIENT_ID)

        assert len(results) == 1
        assert results[0]["capacity_order_id"] == confirmed.id

    def test_plan_vs_actual_status_filter(self, pva_db, admin_user):
        """Explicit status filter shows only that status (even DRAFT)."""
        draft = _create_capacity_order(pva_db, CLIENT_ID, status=OrderStatus.DRAFT)
        _create_capacity_order(pva_db, CLIENT_ID, status=OrderStatus.CONFIRMED)
        pva_db.commit()

        results = get_plan_vs_actual(pva_db, admin_user, client_id=CLIENT_ID, status_filter="DRAFT")

        assert len(results) == 1
        assert results[0]["capacity_order_id"] == draft.id
        assert results[0]["status"] == "DRAFT"


class TestRiskCalculation:
    """Test _calculate_risk logic."""

    def test_risk_calculation_completed(self, pva_db, admin_user):
        """All units produced -> COMPLETED."""
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=100,
            required_date=date.today() + timedelta(days=30),
        )
        pva_db.commit()

        risk = _calculate_risk(cap, actual_completed=100, planned_quantity=100)
        assert risk == "COMPLETED"

    def test_risk_calculation_overdue(self, pva_db, admin_user):
        """Past required_date and not complete -> OVERDUE."""
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=100,
            required_date=date.today() - timedelta(days=5),
        )
        pva_db.commit()

        risk = _calculate_risk(cap, actual_completed=50, planned_quantity=100)
        assert risk == "OVERDUE"

    def test_risk_calculation_low_ahead_of_schedule(self, pva_db, admin_user):
        """Ahead of schedule -> LOW risk."""
        today = date.today()
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=100,
            planned_start_date=today - timedelta(days=10),
            required_date=today + timedelta(days=10),
        )
        pva_db.commit()

        # 50% elapsed, 90% complete -> well ahead
        risk = _calculate_risk(cap, actual_completed=90, planned_quantity=100)
        assert risk == "LOW"

    def test_risk_calculation_high_behind_schedule(self, pva_db, admin_user):
        """Far behind schedule -> HIGH risk."""
        today = date.today()
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=100,
            planned_start_date=today - timedelta(days=10),
            required_date=today + timedelta(days=10),
        )
        pva_db.commit()

        # 50% elapsed, only 10% complete -> very behind
        risk = _calculate_risk(cap, actual_completed=10, planned_quantity=100)
        assert risk == "HIGH"

    def test_risk_calculation_unknown_no_required_date(self):
        """No required_date -> UNKNOWN."""
        # Use a simple namespace object to avoid NOT NULL constraint on the DB column.
        # _calculate_risk only reads attributes, it does not query the DB.
        from types import SimpleNamespace

        fake_order = SimpleNamespace(
            required_date=None,
            planned_start_date=None,
        )

        risk = _calculate_risk(fake_order, actual_completed=50, planned_quantity=100)
        assert risk == "UNKNOWN"

    def test_risk_calculation_unknown_zero_quantity(self, pva_db, admin_user):
        """Zero planned_quantity -> UNKNOWN."""
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=0,
            required_date=date.today() + timedelta(days=30),
        )
        pva_db.commit()

        risk = _calculate_risk(cap, actual_completed=0, planned_quantity=0)
        assert risk == "UNKNOWN"

    def test_risk_calculation_medium(self, pva_db, admin_user):
        """Moderately behind schedule -> MEDIUM risk."""
        today = date.today()
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=100,
            planned_start_date=today - timedelta(days=10),
            required_date=today + timedelta(days=10),
        )
        pva_db.commit()

        # 50% elapsed, ~37% complete -> expected_pct=0.5, 0.37 >= 0.5*0.7=0.35
        risk = _calculate_risk(cap, actual_completed=37, planned_quantity=100)
        assert risk == "MEDIUM"

    def test_risk_fallback_low(self, pva_db, admin_user):
        """No planned_start_date, high completion -> LOW via fallback."""
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=100,
            required_date=date.today() + timedelta(days=30),
            planned_start_date=None,
        )
        pva_db.commit()

        risk = _calculate_risk(cap, actual_completed=85, planned_quantity=100)
        assert risk == "LOW"


class TestProjectedCompletion:
    """Test _project_completion logic."""

    def test_projected_completion_basic(self, pva_db, admin_user):
        """Verify linear projection logic."""
        today = date.today()
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=1000,
            planned_start_date=today - timedelta(days=10),
            required_date=today + timedelta(days=30),
        )
        pva_db.commit()

        # 500 units in 10 days => 50/day => 500 remaining => 10 more days
        projected = _project_completion(cap, actual_completed=500, planned_quantity=1000)

        assert projected is not None
        projected_date = date.fromisoformat(projected)
        expected_date = today + timedelta(days=10)
        assert projected_date == expected_date

    def test_projected_completion_no_start_date(self, pva_db, admin_user):
        """No planned_start_date -> None."""
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=1000,
            planned_start_date=None,
        )
        pva_db.commit()

        projected = _project_completion(cap, actual_completed=500, planned_quantity=1000)
        assert projected is None

    def test_projected_completion_no_production(self, pva_db, admin_user):
        """Zero actual_completed -> None."""
        cap = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=1000,
            planned_start_date=date.today() - timedelta(days=5),
        )
        pva_db.commit()

        projected = _project_completion(cap, actual_completed=0, planned_quantity=1000)
        assert projected is None


class TestPlanVsActualSummary:
    """Test the aggregate summary function."""

    def test_plan_vs_actual_summary(self, pva_db, admin_user):
        """Aggregate summary with risk distribution."""
        # Order 1: completed
        cap1 = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=100,
            required_date=date.today() + timedelta(days=30),
        )
        wo1 = _create_linked_work_order(pva_db, cap1, actual_quantity=100)

        # Order 2: in progress
        cap2 = _create_capacity_order(
            pva_db,
            CLIENT_ID,
            order_quantity=200,
            required_date=date.today() + timedelta(days=30),
        )
        pva_db.commit()

        summary = get_plan_vs_actual_summary(pva_db, admin_user, client_id=CLIENT_ID)

        assert summary["total_orders"] == 2
        assert summary["total_planned_quantity"] == 300
        assert summary["total_actual_completed"] == 100
        assert summary["overall_variance"] == -200
        assert summary["overall_completion_pct"] == pytest.approx(33.33, abs=0.01)
        assert summary["risk_distribution"]["COMPLETED"] == 1
        assert len(summary["orders"]) == 2


class TestMultiTenantIsolation:
    """Test that multi-tenant isolation works correctly."""

    def test_multi_tenant_isolation(self, pva_db):
        """Operator user can only see their client's data."""
        # Set up two clients
        _ensure_client(pva_db, CLIENT_ID)
        _ensure_client(pva_db, CLIENT_B_ID)

        # Create capacity orders for both clients
        cap_a = _create_capacity_order(pva_db, CLIENT_ID, order_quantity=100)
        cap_b = _create_capacity_order(pva_db, CLIENT_B_ID, order_quantity=200)

        # Create operator user for CLIENT_ID only
        operator = TestDataFactory.create_user(
            pva_db,
            username="pva_op_isolation",
            role="operator",
            client_id=CLIENT_ID,
        )
        pva_db.commit()

        results = get_plan_vs_actual(pva_db, operator)

        # Operator should only see CLIENT_ID orders
        assert len(results) == 1
        assert results[0]["capacity_order_id"] == cap_a.id

    def test_admin_sees_all_clients(self, pva_db, admin_user):
        """Admin user can see all clients' data."""
        _ensure_client(pva_db, CLIENT_B_ID)

        _create_capacity_order(pva_db, CLIENT_ID, order_quantity=100)
        _create_capacity_order(pva_db, CLIENT_B_ID, order_quantity=200)
        pva_db.commit()

        results = get_plan_vs_actual(pva_db, admin_user)

        assert len(results) == 2
