"""
Comprehensive tests for all 7 capacity planning service classes.
Uses real in-memory SQLite database (NO mocks).

Services tested:
1. BOMService - Bill of Materials explosion
2. MRPService - Component availability checking
3. CapacityAnalysisService - 12-step capacity calculation
4. SchedulingService - Production schedule generation
5. ScenarioService - What-if scenario analysis (8 types)
6. KPIIntegrationService - KPI commitments and variance
7. CapacityPlanningService - Main orchestration service
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.tests.fixtures.factories import TestDataFactory
from backend.schemas.client import Client, ClientType
from backend.schemas.capacity.calendar import CapacityCalendar
from backend.schemas.capacity.production_lines import CapacityProductionLine
from backend.schemas.capacity.orders import (
    CapacityOrder, OrderPriority, OrderStatus,
)
from backend.schemas.capacity.standards import CapacityProductionStandard
from backend.schemas.capacity.bom import CapacityBOMHeader, CapacityBOMDetail
from backend.schemas.capacity.stock import CapacityStockSnapshot
from backend.schemas.capacity.component_check import (
    CapacityComponentCheck, ComponentStatus,
)
from backend.schemas.capacity.analysis import CapacityAnalysis
from backend.schemas.capacity.schedule import (
    CapacitySchedule, CapacityScheduleDetail, ScheduleStatus,
)
from backend.schemas.capacity.scenario import CapacityScenario
from backend.schemas.capacity.kpi_commitment import CapacityKPICommitment

from backend.services.capacity.bom_service import BOMService, BOMExplosionResult
from backend.services.capacity.mrp_service import MRPService, MRPRunResult
from backend.services.capacity.analysis_service import (
    CapacityAnalysisService, CapacityAnalysisResult, LineCapacityResult,
)
from backend.services.capacity.scheduling_service import (
    SchedulingService, GeneratedSchedule, ScheduleSummary,
)
from backend.services.capacity.scenario_service import (
    ScenarioService, ScenarioType, ScenarioResult, ScenarioComparison,
    SCENARIO_DEFAULTS,
)
from backend.services.capacity.kpi_integration_service import (
    KPIIntegrationService, KPIActual, KPIVariance, STANDARD_KPIS,
)
from backend.services.capacity.capacity_service import CapacityPlanningService

from backend.exceptions.domain_exceptions import BOMExplosionError, SchedulingError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CLIENT_ID = "CAP-TEST"
TODAY = date.today()
PERIOD_START = TODAY
PERIOD_END = TODAY + timedelta(days=29)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def cap_db():
    """Create a fresh in-memory database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    session = TestingSession()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _create_client(db) -> Client:
    """Create the tenant client for capacity tests."""
    client = Client(
        client_id=CLIENT_ID,
        client_name="Capacity Test Client",
        client_type=ClientType.HOURLY_RATE,
        is_active=1,
    )
    db.add(client)
    db.flush()
    return client


def _seed_calendar(db, days: int = 30) -> list:
    """Seed calendar with working-day entries."""
    entries = []
    for i in range(days):
        cal_date = TODAY + timedelta(days=i)
        is_working = cal_date.weekday() < 5  # Mon-Fri
        cal = CapacityCalendar(
            client_id=CLIENT_ID,
            calendar_date=cal_date,
            is_working_day=is_working,
            shifts_available=2 if is_working else 0,
            shift1_hours=8.0 if is_working else 0,
            shift2_hours=8.0 if is_working else 0,
            shift3_hours=0,
        )
        db.add(cal)
        entries.append(cal)
    db.flush()
    return entries


def _seed_production_lines(db) -> list:
    """Seed 3 production lines."""
    lines = []
    for code, dept in [("SEW-01", "SEWING"), ("SEW-02", "SEWING"), ("CUT-01", "CUTTING")]:
        line = CapacityProductionLine(
            client_id=CLIENT_ID,
            line_code=code,
            line_name=f"Line {code}",
            department=dept,
            standard_capacity_units_per_hour=50,
            max_operators=10,
            efficiency_factor=0.85,
            absenteeism_factor=0.05,
            is_active=True,
        )
        db.add(line)
        lines.append(line)
    db.flush()
    return lines


def _seed_orders(db, count: int = 3) -> list:
    """Seed capacity orders."""
    orders = []
    for i in range(count):
        order = CapacityOrder(
            client_id=CLIENT_ID,
            order_number=f"ORD-{i + 1:03d}",
            customer_name=f"Customer {i + 1}",
            style_code=f"STYLE-{chr(65 + i)}",
            order_quantity=500 * (i + 1),
            completed_quantity=0,
            order_date=TODAY,
            required_date=TODAY + timedelta(days=14 + i * 7),
            status=OrderStatus.CONFIRMED,
            priority=OrderPriority.NORMAL,
        )
        db.add(order)
        orders.append(order)
    db.flush()
    return orders


def _seed_standards(db, style_codes: list) -> list:
    """Seed production standards (SAM) for given style codes."""
    stds = []
    for style in style_codes:
        for op_code, op_name, sam in [
            ("CUT", "Cutting", 2.0),
            ("SEW", "Sewing", 5.5),
            ("FIN", "Finishing", 1.5),
        ]:
            std = CapacityProductionStandard(
                client_id=CLIENT_ID,
                style_code=style,
                operation_code=op_code,
                operation_name=op_name,
                department=op_name.upper(),
                sam_minutes=Decimal(str(sam)),
            )
            db.add(std)
            stds.append(std)
    db.flush()
    return stds


def _seed_bom(db, parent_item_code: str, style_code: str) -> CapacityBOMHeader:
    """Seed a BOM header with 3 component details."""
    header = CapacityBOMHeader(
        client_id=CLIENT_ID,
        parent_item_code=parent_item_code,
        parent_item_description=f"Finished {parent_item_code}",
        style_code=style_code,
        revision="1.0",
        is_active=True,
    )
    db.add(header)
    db.flush()

    components = [
        ("FABRIC-001", "Main Fabric", 1.5, 5.0, "FABRIC"),
        ("TRIM-001", "Trim Tape", 3.0, 2.0, "TRIM"),
        ("BTN-001", "Buttons", 6.0, 0.0, "ACCESSORY"),
    ]
    for item_code, desc, qty_per, waste, comp_type in components:
        detail = CapacityBOMDetail(
            header_id=header.id,
            client_id=CLIENT_ID,
            component_item_code=item_code,
            component_description=desc,
            quantity_per=Decimal(str(qty_per)),
            waste_percentage=Decimal(str(waste)),
            unit_of_measure="EA",
            component_type=comp_type,
        )
        db.add(detail)
    db.flush()
    return header


def _seed_stock(db) -> list:
    """Seed stock snapshots for component items."""
    stocks = []
    items = [
        ("FABRIC-001", 2000, 200, 500),
        ("TRIM-001", 5000, 100, 0),
        ("BTN-001", 10000, 500, 0),
    ]
    for item_code, on_hand, allocated, on_order in items:
        stock = CapacityStockSnapshot(
            client_id=CLIENT_ID,
            snapshot_date=TODAY,
            item_code=item_code,
            item_description=f"Stock {item_code}",
            on_hand_quantity=on_hand,
            allocated_quantity=allocated,
            on_order_quantity=on_order,
            available_quantity=on_hand - allocated + on_order,
        )
        db.add(stock)
        stocks.append(stock)
    db.flush()
    return stocks


def _seed_full_capacity_data(db):
    """Seed a complete set of capacity planning data. Returns useful references."""
    _create_client(db)
    calendar = _seed_calendar(db)
    lines = _seed_production_lines(db)
    orders = _seed_orders(db)
    style_codes = [o.style_code for o in orders]
    standards = _seed_standards(db, style_codes)
    bom_header = _seed_bom(db, parent_item_code="STYLE-A", style_code="STYLE-A")
    stocks = _seed_stock(db)
    db.commit()
    return {
        "calendar": calendar,
        "lines": lines,
        "orders": orders,
        "standards": standards,
        "bom_header": bom_header,
        "stocks": stocks,
        "style_codes": style_codes,
    }


# ===========================================================================
# 1. BOMService Tests
# ===========================================================================

class TestBOMService:
    """Tests for BOM explosion service."""

    def test_construction(self, cap_db):
        svc = BOMService(cap_db)
        assert svc.db is cap_db

    def test_explode_bom_happy_path(self, cap_db):
        _create_client(cap_db)
        _seed_bom(cap_db, "ITEM-A", "STYLE-A")
        cap_db.commit()

        svc = BOMService(cap_db)
        result = svc.explode_bom(CLIENT_ID, "ITEM-A", Decimal("100"))

        assert isinstance(result, BOMExplosionResult)
        assert result.parent_item_code == "ITEM-A"
        assert result.quantity_requested == Decimal("100")
        assert result.total_components == 3
        assert result.explosion_depth == 1

    def test_explode_bom_calculates_quantities(self, cap_db):
        _create_client(cap_db)
        _seed_bom(cap_db, "ITEM-B", "STYLE-B")
        cap_db.commit()

        svc = BOMService(cap_db)
        result = svc.explode_bom(CLIENT_ID, "ITEM-B", Decimal("200"))

        fabric = next(c for c in result.components if c.component_item_code == "FABRIC-001")
        # qty_per=1.5, waste=5% => gross=300, net=300*1.05=315
        assert fabric.gross_required == Decimal("300.0")
        assert fabric.net_required == Decimal("315.000")

    def test_explode_bom_no_waste(self, cap_db):
        _create_client(cap_db)
        _seed_bom(cap_db, "ITEM-C", "STYLE-C")
        cap_db.commit()

        svc = BOMService(cap_db)
        result = svc.explode_bom(CLIENT_ID, "ITEM-C", Decimal("10"))

        btn = next(c for c in result.components if c.component_item_code == "BTN-001")
        # qty_per=6.0, waste=0% => gross=60, net=60
        assert btn.gross_required == Decimal("60.0")
        assert btn.net_required == Decimal("60.000")

    def test_explode_bom_not_found_raises(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = BOMService(cap_db)
        with pytest.raises(BOMExplosionError, match="No active BOM found"):
            svc.explode_bom(CLIENT_ID, "NONEXISTENT", Decimal("1"))

    def test_explode_bom_no_components_raises(self, cap_db):
        _create_client(cap_db)
        header = CapacityBOMHeader(
            client_id=CLIENT_ID,
            parent_item_code="EMPTY-BOM",
            is_active=True,
        )
        cap_db.add(header)
        cap_db.commit()

        svc = BOMService(cap_db)
        with pytest.raises(BOMExplosionError, match="has no components"):
            svc.explode_bom(CLIENT_ID, "EMPTY-BOM", Decimal("1"))

    def test_explode_bom_inactive_ignored(self, cap_db):
        _create_client(cap_db)
        header = CapacityBOMHeader(
            client_id=CLIENT_ID,
            parent_item_code="INACTIVE-BOM",
            is_active=False,
        )
        cap_db.add(header)
        cap_db.commit()

        svc = BOMService(cap_db)
        with pytest.raises(BOMExplosionError):
            svc.explode_bom(CLIENT_ID, "INACTIVE-BOM", Decimal("1"))

    def test_get_bom_structure(self, cap_db):
        _create_client(cap_db)
        _seed_bom(cap_db, "STRUCT-A", "STYLE-A")
        cap_db.commit()

        svc = BOMService(cap_db)
        result = svc.get_bom_structure(CLIENT_ID, "STRUCT-A")

        assert result is not None
        assert result["parent_item_code"] == "STRUCT-A"
        assert len(result["components"]) == 3

    def test_get_bom_structure_not_found(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = BOMService(cap_db)
        result = svc.get_bom_structure(CLIENT_ID, "NOPE")
        assert result is None

    def test_aggregate_component_requirements(self, cap_db):
        _create_client(cap_db)
        _seed_bom(cap_db, "AGG-A", "STYLE-A")
        cap_db.commit()

        svc = BOMService(cap_db)
        r1 = svc.explode_bom(CLIENT_ID, "AGG-A", Decimal("100"))
        r2 = svc.explode_bom(CLIENT_ID, "AGG-A", Decimal("50"))
        aggregated = svc.aggregate_component_requirements([r1, r2])

        assert "FABRIC-001" in aggregated
        # 100*1.5*1.05 + 50*1.5*1.05 = 157.5 + 78.75 = 236.25
        assert float(aggregated["FABRIC-001"]) == pytest.approx(236.25, rel=1e-3)

    def test_explode_multiple_orders(self, cap_db):
        _create_client(cap_db)
        _seed_bom(cap_db, "MULTI-A", "STYLE-A")
        cap_db.commit()

        svc = BOMService(cap_db)
        orders = [
            {"style_code": "MULTI-A", "quantity": 100},
            {"style_code": "NONEXISTENT", "quantity": 50},
        ]
        results = svc.explode_multiple_orders(CLIENT_ID, orders)

        assert "MULTI-A" in results
        assert "NONEXISTENT" not in results

    def test_tenant_isolation(self, cap_db):
        """BOM for one client should not be visible to another."""
        _create_client(cap_db)
        other_client = Client(
            client_id="OTHER-CLIENT",
            client_name="Other",
            client_type=ClientType.HOURLY_RATE,
            is_active=1,
        )
        cap_db.add(other_client)
        _seed_bom(cap_db, "TENANT-A", "STYLE-A")
        cap_db.commit()

        svc = BOMService(cap_db)
        with pytest.raises(BOMExplosionError):
            svc.explode_bom("OTHER-CLIENT", "TENANT-A", Decimal("1"))


# ===========================================================================
# 2. MRPService Tests
# ===========================================================================

class TestMRPService:
    """Tests for MRP / component checking service."""

    def test_construction(self, cap_db):
        svc = MRPService(cap_db)
        assert svc.db is cap_db

    def test_run_component_check_no_orders(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = MRPService(cap_db)
        result = svc.run_component_check(CLIENT_ID)

        assert isinstance(result, MRPRunResult)
        assert result.total_components_checked == 0
        assert result.orders_affected == 0

    def test_run_component_check_with_bom_and_stock(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = MRPService(cap_db)
        # Only check order for STYLE-A which has a BOM
        order_a = next(o for o in data["orders"] if o.style_code == "STYLE-A")
        result = svc.run_component_check(CLIENT_ID, order_ids=[order_a.id])

        assert isinstance(result, MRPRunResult)
        assert result.run_date == date.today()
        # Should have checked the 3 components from BOM
        assert result.total_components_checked == 3

    def test_component_check_detects_shortage(self, cap_db):
        """When stock is insufficient, the check should detect a shortage."""
        _create_client(cap_db)
        _seed_bom(cap_db, "STYLE-A", "STYLE-A")

        # Seed very low stock for FABRIC-001
        stock = CapacityStockSnapshot(
            client_id=CLIENT_ID,
            snapshot_date=TODAY,
            item_code="FABRIC-001",
            on_hand_quantity=1,
            allocated_quantity=0,
            on_order_quantity=0,
            available_quantity=1,
        )
        cap_db.add(stock)
        # Add sufficient stock for other components
        for code in ["TRIM-001", "BTN-001"]:
            cap_db.add(CapacityStockSnapshot(
                client_id=CLIENT_ID,
                snapshot_date=TODAY,
                item_code=code,
                on_hand_quantity=99999,
                allocated_quantity=0,
                on_order_quantity=0,
                available_quantity=99999,
            ))

        # Create large order
        order = CapacityOrder(
            client_id=CLIENT_ID,
            order_number="ORD-LARGE",
            style_code="STYLE-A",
            order_quantity=10000,
            required_date=TODAY + timedelta(days=14),
            status=OrderStatus.CONFIRMED,
        )
        cap_db.add(order)
        cap_db.commit()

        svc = MRPService(cap_db)
        result = svc.run_component_check(CLIENT_ID, order_ids=[order.id])

        assert result.components_short >= 1
        fabric_check = next(
            (c for c in result.components if c.component_item_code == "FABRIC-001"),
            None,
        )
        assert fabric_check is not None
        assert fabric_check.status == ComponentStatus.SHORTAGE
        assert fabric_check.shortage_quantity > 0

    def test_component_check_all_ok(self, cap_db):
        """When stock is ample, all components should report OK."""
        _create_client(cap_db)
        _seed_bom(cap_db, "STYLE-A", "STYLE-A")

        # Seed very high stock
        for code in ["FABRIC-001", "TRIM-001", "BTN-001"]:
            cap_db.add(CapacityStockSnapshot(
                client_id=CLIENT_ID,
                snapshot_date=TODAY,
                item_code=code,
                on_hand_quantity=999999,
                allocated_quantity=0,
                on_order_quantity=0,
                available_quantity=999999,
            ))

        order = CapacityOrder(
            client_id=CLIENT_ID,
            order_number="ORD-SMALL",
            style_code="STYLE-A",
            order_quantity=1,
            required_date=TODAY + timedelta(days=14),
            status=OrderStatus.CONFIRMED,
        )
        cap_db.add(order)
        cap_db.commit()

        svc = MRPService(cap_db)
        result = svc.run_component_check(CLIENT_ID, order_ids=[order.id])

        assert result.components_short == 0
        assert result.components_ok == 3

    def test_get_component_check_history_empty(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = MRPService(cap_db)
        history = svc.get_component_check_history(CLIENT_ID)
        assert history == []

    def test_get_shortages_by_order_empty(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = MRPService(cap_db)
        result = svc.get_shortages_by_order(CLIENT_ID, "NONEXISTENT")
        assert result == []


# ===========================================================================
# 3. CapacityAnalysisService Tests
# ===========================================================================

class TestCapacityAnalysisService:
    """Tests for the 12-step capacity analysis service."""

    def test_construction(self, cap_db):
        svc = CapacityAnalysisService(cap_db)
        assert svc.db is cap_db
        assert svc.bottleneck_threshold == Decimal("95.0")

    def test_analyze_capacity_no_lines(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = CapacityAnalysisService(cap_db)
        result = svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)

        assert isinstance(result, CapacityAnalysisResult)
        assert result.lines_analyzed == 0
        assert result.total_capacity_hours == Decimal("0")

    def test_analyze_capacity_with_lines(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityAnalysisService(cap_db)
        result = svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)

        assert result.lines_analyzed == 3
        assert result.total_capacity_hours > Decimal("0")
        assert len(result.lines) == 3

    def test_analyze_capacity_calculates_gross_net_hours(self, cap_db):
        """Verify the 12-step capacity calculation produces reasonable values."""
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityAnalysisService(cap_db)
        result = svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)

        for line_result in result.lines:
            # gross = working_days * shifts_per_day * hours_per_shift
            assert line_result.gross_hours > Decimal("0")
            # net = gross * efficiency * (1 - absenteeism)
            assert line_result.net_hours > Decimal("0")
            assert line_result.net_hours <= line_result.gross_hours
            # capacity = net * operators
            assert line_result.capacity_hours >= line_result.net_hours

    def test_analyze_capacity_stores_results(self, cap_db):
        """Analysis should persist CapacityAnalysis records in the DB."""
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityAnalysisService(cap_db)
        svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)

        stored = cap_db.query(CapacityAnalysis).filter(
            CapacityAnalysis.client_id == CLIENT_ID
        ).all()
        assert len(stored) == 3  # one per line

    def test_analyze_capacity_zero_demand(self, cap_db):
        """Without schedules, demand should be zero and utilization zero."""
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityAnalysisService(cap_db)
        result = svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)

        assert result.total_demand_hours == Decimal("0")
        assert result.overall_utilization == Decimal("0")
        assert result.bottleneck_count == 0

    def test_analyze_capacity_with_schedule_demand(self, cap_db):
        """When schedule details exist, demand hours should be calculated."""
        data = _seed_full_capacity_data(cap_db)
        lines = data["lines"]

        # Create a committed schedule with details
        schedule = CapacitySchedule(
            client_id=CLIENT_ID,
            schedule_name="Test Schedule",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            status=ScheduleStatus.COMMITTED,
        )
        cap_db.add(schedule)
        cap_db.flush()

        # Add schedule details on line SEW-01 for STYLE-A
        detail = CapacityScheduleDetail(
            schedule_id=schedule.id,
            client_id=CLIENT_ID,
            order_id=data["orders"][0].id,
            order_number="ORD-001",
            style_code="STYLE-A",
            line_id=lines[0].id,
            line_code="SEW-01",
            scheduled_date=PERIOD_START + timedelta(days=1),
            scheduled_quantity=500,
        )
        cap_db.add(detail)
        cap_db.commit()

        svc = CapacityAnalysisService(cap_db)
        result = svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)

        assert result.total_demand_hours > Decimal("0")

    def test_get_line_capacity_found(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityAnalysisService(cap_db)
        line = data["lines"][0]
        result = svc.get_line_capacity(CLIENT_ID, line.id, PERIOD_START, PERIOD_END)

        assert result is not None
        assert result.line_id == line.id
        assert result.line_code == "SEW-01"

    def test_get_line_capacity_not_found(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = CapacityAnalysisService(cap_db)
        result = svc.get_line_capacity(CLIENT_ID, 9999, PERIOD_START, PERIOD_END)
        assert result is None

    def test_identify_bottlenecks_none(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityAnalysisService(cap_db)
        bottlenecks = svc.identify_bottlenecks(CLIENT_ID, PERIOD_START, PERIOD_END)

        # No demand means no bottlenecks
        assert bottlenecks == []

    def test_get_historical_analysis(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityAnalysisService(cap_db)
        # Run analysis first to create records
        svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)

        history = svc.get_historical_analysis(CLIENT_ID)
        assert len(history) == 3

    def test_calendar_fallback_when_empty(self, cap_db):
        """When no calendar data exists, the service should use a default calculation."""
        _create_client(cap_db)
        _seed_production_lines(cap_db)
        cap_db.commit()

        svc = CapacityAnalysisService(cap_db)
        result = svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)

        # Should still produce results using weekday-based defaults
        assert result.lines_analyzed == 3
        assert result.total_capacity_hours > Decimal("0")

    def test_analyze_specific_line_ids(self, cap_db):
        data = _seed_full_capacity_data(cap_db)
        first_line_id = data["lines"][0].id

        svc = CapacityAnalysisService(cap_db)
        result = svc.analyze_capacity(
            CLIENT_ID, PERIOD_START, PERIOD_END, line_ids=[first_line_id]
        )

        assert result.lines_analyzed == 1
        assert result.lines[0].line_id == first_line_id


# ===========================================================================
# 4. SchedulingService Tests
# ===========================================================================

class TestSchedulingService:
    """Tests for the scheduling service."""

    def test_construction(self, cap_db):
        svc = SchedulingService(cap_db)
        assert svc.db is cap_db

    def test_generate_schedule_no_orders(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = SchedulingService(cap_db)
        result = svc.generate_schedule(
            CLIENT_ID, "Empty Schedule", PERIOD_START, PERIOD_END
        )

        assert isinstance(result, GeneratedSchedule)
        assert result.total_scheduled_quantity == 0
        assert result.items == []

    def test_generate_schedule_no_lines(self, cap_db):
        _create_client(cap_db)
        _seed_orders(cap_db)
        cap_db.commit()

        svc = SchedulingService(cap_db)
        result = svc.generate_schedule(
            CLIENT_ID, "No Lines", PERIOD_START, PERIOD_END
        )

        # All orders unscheduled because no lines
        assert result.total_scheduled_quantity == 0
        assert len(result.unscheduled_orders) == 3

    def test_generate_schedule_with_data(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = SchedulingService(cap_db)
        result = svc.generate_schedule(
            CLIENT_ID, "Full Schedule", PERIOD_START, PERIOD_END
        )

        assert result.schedule_name == "Full Schedule"
        assert result.total_scheduled_quantity > 0
        assert len(result.items) > 0

    def test_generate_schedule_priority_sort(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = SchedulingService(cap_db)
        # By required_date (default)
        result_date = svc.generate_schedule(
            CLIENT_ID, "By Date", PERIOD_START, PERIOD_END,
            prioritize_by="required_date",
        )
        # By priority
        result_prio = svc.generate_schedule(
            CLIENT_ID, "By Priority", PERIOD_START, PERIOD_END,
            prioritize_by="priority",
        )

        # Both should schedule items
        assert len(result_date.items) > 0
        assert len(result_prio.items) > 0

    def test_create_schedule(self, cap_db):
        data = _seed_full_capacity_data(cap_db)
        lines = data["lines"]
        orders = data["orders"]

        svc = SchedulingService(cap_db)
        schedule = svc.create_schedule(
            client_id=CLIENT_ID,
            schedule_name="Manual Schedule",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            items=[
                {
                    "order_id": orders[0].id,
                    "order_number": orders[0].order_number,
                    "style_code": orders[0].style_code,
                    "line_id": lines[0].id,
                    "line_code": lines[0].line_code,
                    "scheduled_date": PERIOD_START + timedelta(days=1),
                    "scheduled_quantity": 200,
                    "sequence": 1,
                },
            ],
        )

        assert isinstance(schedule, CapacitySchedule)
        assert schedule.schedule_name == "Manual Schedule"
        assert schedule.status == ScheduleStatus.DRAFT
        assert schedule.id is not None

    def test_commit_schedule(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = SchedulingService(cap_db)
        schedule = svc.create_schedule(
            CLIENT_ID, "To Commit", PERIOD_START, PERIOD_END, items=[]
        )

        committed = svc.commit_schedule(CLIENT_ID, schedule.id, committed_by=1)

        assert committed.status == ScheduleStatus.COMMITTED
        assert committed.committed_at == date.today()
        assert committed.committed_by == 1

    def test_commit_schedule_not_found(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = SchedulingService(cap_db)
        with pytest.raises(SchedulingError, match="not found"):
            svc.commit_schedule(CLIENT_ID, 9999, committed_by=1)

    def test_commit_schedule_not_draft(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = SchedulingService(cap_db)
        schedule = svc.create_schedule(
            CLIENT_ID, "Double Commit", PERIOD_START, PERIOD_END, items=[]
        )
        svc.commit_schedule(CLIENT_ID, schedule.id, committed_by=1)

        with pytest.raises(SchedulingError, match="not in DRAFT"):
            svc.commit_schedule(CLIENT_ID, schedule.id, committed_by=1)

    def test_activate_schedule(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = SchedulingService(cap_db)
        schedule = svc.create_schedule(
            CLIENT_ID, "Activate", PERIOD_START, PERIOD_END, items=[]
        )
        svc.commit_schedule(CLIENT_ID, schedule.id, committed_by=1)
        activated = svc.activate_schedule(CLIENT_ID, schedule.id)

        assert activated.status == ScheduleStatus.ACTIVE

    def test_activate_non_committed_raises(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = SchedulingService(cap_db)
        schedule = svc.create_schedule(
            CLIENT_ID, "Draft", PERIOD_START, PERIOD_END, items=[]
        )

        with pytest.raises(SchedulingError, match="COMMITTED"):
            svc.activate_schedule(CLIENT_ID, schedule.id)

    def test_get_schedule_summary(self, cap_db):
        data = _seed_full_capacity_data(cap_db)
        lines = data["lines"]
        orders = data["orders"]

        svc = SchedulingService(cap_db)
        schedule = svc.create_schedule(
            CLIENT_ID, "Summary Test", PERIOD_START, PERIOD_END,
            items=[
                {
                    "order_id": orders[0].id,
                    "order_number": orders[0].order_number,
                    "style_code": orders[0].style_code,
                    "line_id": lines[0].id,
                    "line_code": lines[0].line_code,
                    "scheduled_date": PERIOD_START + timedelta(days=1),
                    "scheduled_quantity": 300,
                },
            ],
        )

        summary = svc.get_schedule_summary(CLIENT_ID, schedule.id)

        assert isinstance(summary, ScheduleSummary)
        assert summary.schedule_name == "Summary Test"
        assert summary.total_quantity == 300
        assert summary.total_orders >= 1

    def test_get_schedule_summary_not_found(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = SchedulingService(cap_db)
        result = svc.get_schedule_summary(CLIENT_ID, 9999)
        assert result is None

    def test_list_schedules_empty(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = SchedulingService(cap_db)
        result = svc.list_schedules(CLIENT_ID)
        assert result == []

    def test_list_schedules_with_filters(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = SchedulingService(cap_db)
        svc.create_schedule(CLIENT_ID, "Sched1", PERIOD_START, PERIOD_END, items=[])
        s2 = svc.create_schedule(CLIENT_ID, "Sched2", PERIOD_START, PERIOD_END, items=[])
        svc.commit_schedule(CLIENT_ID, s2.id, committed_by=1)

        drafts = svc.list_schedules(CLIENT_ID, status=ScheduleStatus.DRAFT)
        assert len(drafts) == 1

        committed = svc.list_schedules(CLIENT_ID, status=ScheduleStatus.COMMITTED)
        assert len(committed) == 1


# ===========================================================================
# 5. ScenarioService Tests
# ===========================================================================

class TestScenarioService:
    """Tests for the what-if scenario service (8 scenario types)."""

    def test_construction(self, cap_db):
        svc = ScenarioService(cap_db)
        assert svc.db is cap_db

    def test_get_available_scenario_types(self, cap_db):
        svc = ScenarioService(cap_db)
        types = svc.get_available_scenario_types()

        assert len(types) >= 8
        type_values = {t["type"] for t in types}
        assert "OVERTIME" in type_values
        assert "SETUP_REDUCTION" in type_values
        assert "SUBCONTRACT" in type_values
        assert "NEW_LINE" in type_values
        assert "THREE_SHIFT" in type_values
        assert "LEAD_TIME_DELAY" in type_values
        assert "ABSENTEEISM_SPIKE" in type_values
        assert "MULTI_CONSTRAINT" in type_values

    def test_get_scenario_type_defaults_all_types(self, cap_db):
        svc = ScenarioService(cap_db)
        for st in ScenarioType:
            defaults = svc.get_scenario_type_defaults(st)
            assert isinstance(defaults, dict)

    def test_get_scenario_type_defaults_by_string(self, cap_db):
        svc = ScenarioService(cap_db)
        defaults = svc.get_scenario_type_defaults("OVERTIME")
        assert "overtime_percent" in defaults
        assert defaults["overtime_percent"] == 20

    def test_get_scenario_type_defaults_invalid_string(self, cap_db):
        svc = ScenarioService(cap_db)
        defaults = svc.get_scenario_type_defaults("INVALID_TYPE")
        assert defaults == {}

    def test_create_scenario_overtime(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "Overtime +20%", ScenarioType.OVERTIME
        )

        assert scenario.id is not None
        assert scenario.scenario_name == "Overtime +20%"
        assert scenario.scenario_type == "OVERTIME"
        assert scenario.parameters_json is not None
        assert scenario.parameters_json["overtime_percent"] == 20

    def test_create_scenario_with_custom_params(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "Custom OT", ScenarioType.OVERTIME,
            parameters={"overtime_percent": 50},
        )

        assert scenario.parameters_json["overtime_percent"] == 50

    @pytest.mark.parametrize("scenario_type", [
        ScenarioType.OVERTIME,
        ScenarioType.SETUP_REDUCTION,
        ScenarioType.SUBCONTRACT,
        ScenarioType.NEW_LINE,
        ScenarioType.THREE_SHIFT,
        ScenarioType.LEAD_TIME_DELAY,
        ScenarioType.ABSENTEEISM_SPIKE,
        ScenarioType.MULTI_CONSTRAINT,
    ])
    def test_create_each_scenario_type(self, cap_db, scenario_type):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, f"Test {scenario_type.value}", scenario_type
        )

        assert scenario.id is not None
        assert scenario.scenario_type == scenario_type.value

    def test_create_preconfigured_scenario(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_preconfigured_scenario(
            CLIENT_ID, ScenarioType.NEW_LINE
        )

        assert scenario.scenario_type == "NEW_LINE"
        assert scenario.parameters_json["new_line_code"] == "SEWING_NEW"

    def test_apply_scenario_overtime(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "OT Analysis", ScenarioType.OVERTIME
        )
        result = svc.apply_scenario_parameters(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )

        assert isinstance(result, ScenarioResult)
        assert result.scenario_id == scenario.id
        # Overtime should increase capacity
        orig = result.original_metrics["total_capacity_hours"]
        mod = result.modified_metrics["total_capacity_hours"]
        assert mod >= orig

    def test_apply_scenario_setup_reduction(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "Setup Red", ScenarioType.SETUP_REDUCTION
        )
        result = svc.apply_scenario_parameters(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )

        # Setup reduction should increase capacity
        orig = result.original_metrics["total_capacity_hours"]
        mod = result.modified_metrics["total_capacity_hours"]
        assert mod >= orig

    def test_apply_scenario_absenteeism_spike(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "Absent", ScenarioType.ABSENTEEISM_SPIKE
        )
        result = svc.apply_scenario_parameters(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )

        # Absenteeism should reduce capacity
        orig = result.original_metrics["total_capacity_hours"]
        mod = result.modified_metrics["total_capacity_hours"]
        assert mod <= orig

    def test_apply_scenario_lead_time_delay(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "Delay", ScenarioType.LEAD_TIME_DELAY
        )
        result = svc.apply_scenario_parameters(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )

        # Lead time delay should not change capacity hours but affects demand/utilization
        assert "warnings" in result.modified_metrics
        assert len(result.modified_metrics["warnings"]) > 0

    def test_apply_scenario_new_line(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "New Line", ScenarioType.NEW_LINE
        )
        result = svc.apply_scenario_parameters(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )

        # New line adds capacity and a virtual line
        mod_lines = result.modified_metrics.get("lines", [])
        assert len(mod_lines) == 4  # 3 original + 1 new
        assert result.modified_metrics["total_capacity_hours"] > result.original_metrics["total_capacity_hours"]

    def test_apply_scenario_not_found(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = ScenarioService(cap_db)
        with pytest.raises(ValueError, match="not found"):
            svc.apply_scenario_parameters(CLIENT_ID, 9999, PERIOD_START, PERIOD_END)

    def test_apply_scenario_stores_results(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "Stored", ScenarioType.OVERTIME
        )
        svc.apply_scenario_parameters(CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END)

        # Refresh from DB
        cap_db.expire(scenario)
        assert scenario.results_json is not None
        assert "new_capacity_hours" in scenario.results_json

    def test_compare_scenarios(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        s1 = svc.create_scenario(CLIENT_ID, "S1", ScenarioType.OVERTIME)
        s2 = svc.create_scenario(CLIENT_ID, "S2", ScenarioType.SETUP_REDUCTION)

        comparisons = svc.compare_scenarios(
            CLIENT_ID, [s1.id, s2.id], PERIOD_START, PERIOD_END
        )

        assert len(comparisons) == 2
        assert isinstance(comparisons[0], ScenarioComparison)
        assert comparisons[0].scenario_id == s1.id
        assert comparisons[1].scenario_id == s2.id

    def test_get_scenario_results_before_analysis(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(CLIENT_ID, "NoResults", ScenarioType.OVERTIME)

        result = svc.get_scenario_results(CLIENT_ID, scenario.id)
        assert result is None  # Not analyzed yet

    def test_get_scenario_results_after_analysis(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(CLIENT_ID, "WithResults", ScenarioType.OVERTIME)
        svc.apply_scenario_parameters(CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END)

        result = svc.get_scenario_results(CLIENT_ID, scenario.id)
        assert result is not None

    def test_list_scenarios_with_filter(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        svc.create_scenario(CLIENT_ID, "OT1", ScenarioType.OVERTIME)
        svc.create_scenario(CLIENT_ID, "SR1", ScenarioType.SETUP_REDUCTION)

        all_scenarios = svc.list_scenarios(CLIENT_ID)
        assert len(all_scenarios) == 2

        ot_only = svc.list_scenarios(CLIENT_ID, scenario_type="OVERTIME")
        assert len(ot_only) == 1
        assert ot_only[0].scenario_type == "OVERTIME"

    def test_scenario_multi_constraint(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "Multi", ScenarioType.MULTI_CONSTRAINT
        )
        result = svc.apply_scenario_parameters(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )

        # Multi-constraint combines overtime, setup reduction, efficiency, absenteeism
        assert result.impact_summary is not None
        assert "capacity_increase_percent" in result.impact_summary

    def test_scenario_three_shift(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "3-Shift", ScenarioType.THREE_SHIFT
        )
        result = svc.apply_scenario_parameters(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )

        assert result.modified_metrics["total_capacity_hours"] > result.original_metrics["total_capacity_hours"]

    def test_scenario_subcontract(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "Subcontract", ScenarioType.SUBCONTRACT
        )
        result = svc.apply_scenario_parameters(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )

        # Subcontracting reduces demand (not capacity)
        # Total capacity remains same, but demand may differ
        assert result.impact_summary is not None


# ===========================================================================
# 6. KPIIntegrationService Tests
# ===========================================================================

class TestKPIIntegrationService:
    """Tests for KPI integration service."""

    def test_construction(self, cap_db):
        svc = KPIIntegrationService(cap_db)
        assert svc.db is cap_db
        assert svc.variance_threshold == Decimal("10.0")

    def test_construction_custom_threshold(self, cap_db):
        svc = KPIIntegrationService(cap_db, variance_threshold=Decimal("5.0"))
        assert svc.variance_threshold == Decimal("5.0")

    def test_store_kpi_commitments(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        # Create schedule
        sched_svc = SchedulingService(cap_db)
        schedule = sched_svc.create_schedule(
            CLIENT_ID, "KPI Sched", PERIOD_START, PERIOD_END, items=[]
        )

        svc = KPIIntegrationService(cap_db)
        result = svc.store_kpi_commitments(
            CLIENT_ID, schedule.id,
            {
                "efficiency": Decimal("85.0"),
                "quality": Decimal("98.5"),
                "otd": Decimal("95.0"),
            },
        )

        assert result.schedule_id == schedule.id
        assert result.kpis_stored == 3
        assert set(result.kpi_keys) == {"efficiency", "quality", "otd"}

    def test_store_kpi_commitments_schedule_not_found(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = KPIIntegrationService(cap_db)
        with pytest.raises(ValueError, match="not found"):
            svc.store_kpi_commitments(CLIENT_ID, 9999, {"efficiency": Decimal("85")})

    def test_get_kpi_commitments(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        sched_svc = SchedulingService(cap_db)
        schedule = sched_svc.create_schedule(
            CLIENT_ID, "KPI Get", PERIOD_START, PERIOD_END, items=[]
        )

        svc = KPIIntegrationService(cap_db)
        svc.store_kpi_commitments(
            CLIENT_ID, schedule.id, {"efficiency": Decimal("85.0")}
        )

        commitments = svc.get_kpi_commitments(CLIENT_ID, schedule.id)
        assert len(commitments) == 1
        assert commitments[0].kpi_key == "efficiency"
        assert float(commitments[0].committed_value) == 85.0

    def test_get_kpi_commitments_empty(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        sched_svc = SchedulingService(cap_db)
        schedule = sched_svc.create_schedule(
            CLIENT_ID, "Empty KPI", PERIOD_START, PERIOD_END, items=[]
        )

        svc = KPIIntegrationService(cap_db)
        commitments = svc.get_kpi_commitments(CLIENT_ID, schedule.id)
        assert commitments == []

    def test_calculate_variance_no_commitments(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        sched_svc = SchedulingService(cap_db)
        schedule = sched_svc.create_schedule(
            CLIENT_ID, "No Commit", PERIOD_START, PERIOD_END, items=[]
        )

        svc = KPIIntegrationService(cap_db)
        variances = svc.calculate_variance(CLIENT_ID, schedule.id)
        assert variances == []

    def test_calculate_variance_schedule_not_found(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = KPIIntegrationService(cap_db)
        with pytest.raises(ValueError, match="not found"):
            svc.calculate_variance(CLIENT_ID, 9999)

    def test_get_actual_kpis_no_production_data(self, cap_db):
        """With no production data, actuals should be empty."""
        _create_client(cap_db)
        cap_db.commit()

        svc = KPIIntegrationService(cap_db)
        actuals = svc.get_actual_kpis(CLIENT_ID, PERIOD_START, PERIOD_END)

        # No production entries => no actual values
        assert isinstance(actuals, list)

    def test_get_kpi_history_empty(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = KPIIntegrationService(cap_db)
        history = svc.get_kpi_history(CLIENT_ID, "efficiency")
        assert history == []

    def test_get_kpi_history_with_data(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        sched_svc = SchedulingService(cap_db)
        schedule = sched_svc.create_schedule(
            CLIENT_ID, "History", PERIOD_START, PERIOD_END, items=[]
        )

        svc = KPIIntegrationService(cap_db)
        svc.store_kpi_commitments(
            CLIENT_ID, schedule.id, {"efficiency": Decimal("85.0")}
        )

        history = svc.get_kpi_history(CLIENT_ID, "efficiency")
        assert len(history) == 1
        assert history[0]["committed_value"] == 85.0

    def test_store_kpi_commitments_list(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        sched_svc = SchedulingService(cap_db)
        schedule = sched_svc.create_schedule(
            CLIENT_ID, "List KPI", PERIOD_START, PERIOD_END, items=[]
        )

        svc = KPIIntegrationService(cap_db)
        stored = svc.store_kpi_commitments_list(
            CLIENT_ID, schedule.id,
            {"efficiency": Decimal("85.0"), "quality": Decimal("98.0")},
        )

        assert len(stored) == 2
        assert all(isinstance(c, CapacityKPICommitment) for c in stored)
        assert all(c.id is not None for c in stored)

    def test_check_variance_alerts_empty(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        sched_svc = SchedulingService(cap_db)
        schedule = sched_svc.create_schedule(
            CLIENT_ID, "Alert", PERIOD_START, PERIOD_END, items=[]
        )

        svc = KPIIntegrationService(cap_db)
        alerts = svc.check_variance_alerts(CLIENT_ID, schedule.id)
        assert alerts == []

    def test_standard_kpis_constants(self, cap_db):
        """Verify STANDARD_KPIS dict is properly defined."""
        assert "efficiency" in STANDARD_KPIS
        assert "quality" in STANDARD_KPIS
        assert "otd" in STANDARD_KPIS
        assert STANDARD_KPIS["efficiency"]["direction"] == "higher_better"


# ===========================================================================
# 7. CapacityPlanningService Tests (Orchestration)
# ===========================================================================

class TestCapacityPlanningService:
    """Tests for the main orchestration service."""

    def test_construction(self, cap_db):
        svc = CapacityPlanningService(cap_db)
        assert svc.db is cap_db
        assert isinstance(svc.bom_service, BOMService)
        assert isinstance(svc.mrp_service, MRPService)
        assert isinstance(svc.analysis_service, CapacityAnalysisService)
        assert isinstance(svc.scheduling_service, SchedulingService)
        assert isinstance(svc.scenario_service, ScenarioService)
        assert isinstance(svc.kpi_service, KPIIntegrationService)

    def test_explode_bom_delegates(self, cap_db):
        _create_client(cap_db)
        _seed_bom(cap_db, "ORCH-A", "STYLE-A")
        cap_db.commit()

        svc = CapacityPlanningService(cap_db)
        result = svc.explode_bom(CLIENT_ID, "ORCH-A", Decimal("50"))

        assert isinstance(result, BOMExplosionResult)
        assert result.total_components == 3

    def test_get_bom_structure_delegates(self, cap_db):
        _create_client(cap_db)
        _seed_bom(cap_db, "STRUCT-ORCH", "STYLE-A")
        cap_db.commit()

        svc = CapacityPlanningService(cap_db)
        result = svc.get_bom_structure(CLIENT_ID, "STRUCT-ORCH")
        assert result is not None

    def test_run_component_check_delegates(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = CapacityPlanningService(cap_db)
        result = svc.run_component_check(CLIENT_ID)
        assert isinstance(result, MRPRunResult)

    def test_analyze_capacity_delegates(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityPlanningService(cap_db)
        result = svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)
        assert isinstance(result, CapacityAnalysisResult)
        assert result.lines_analyzed == 3

    def test_generate_schedule_delegates(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityPlanningService(cap_db)
        result = svc.generate_schedule(
            CLIENT_ID, "Orch Schedule", PERIOD_START, PERIOD_END
        )
        assert isinstance(result, GeneratedSchedule)

    def test_create_and_commit_schedule(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityPlanningService(cap_db)
        schedule = svc.create_schedule(
            CLIENT_ID, "Orch Create", PERIOD_START, PERIOD_END, items=[]
        )
        assert schedule.status == ScheduleStatus.DRAFT

        committed = svc.commit_schedule(
            CLIENT_ID, schedule.id, committed_by=1,
            kpi_commitments={"efficiency": 85.0, "quality": 98.0},
        )
        assert committed.status == ScheduleStatus.COMMITTED

        # Verify KPI commitments were stored
        kpi_svc = KPIIntegrationService(cap_db)
        commitments = kpi_svc.get_kpi_commitments(CLIENT_ID, schedule.id)
        assert len(commitments) == 2

    def test_create_scenario_delegates(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityPlanningService(cap_db)
        scenario = svc.create_scenario(
            CLIENT_ID, "Orch Scenario", "OVERTIME"
        )
        assert isinstance(scenario, CapacityScenario)

    def test_analyze_scenario_delegates(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityPlanningService(cap_db)
        scenario = svc.create_scenario(CLIENT_ID, "Orch Anal", "OVERTIME")
        result = svc.analyze_scenario(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )
        assert isinstance(result, ScenarioResult)

    def test_list_scenarios_delegates(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityPlanningService(cap_db)
        svc.create_scenario(CLIENT_ID, "LS1", "OVERTIME")

        scenarios = svc.list_scenarios(CLIENT_ID)
        assert len(scenarios) == 1

    def test_get_actual_kpis_delegates(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = CapacityPlanningService(cap_db)
        kpis = svc.get_actual_kpis(CLIENT_ID, PERIOD_START, PERIOD_END)
        assert isinstance(kpis, list)

    def test_get_schedule_summary_delegates(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityPlanningService(cap_db)
        schedule = svc.create_schedule(
            CLIENT_ID, "Sum Test", PERIOD_START, PERIOD_END, items=[]
        )

        summary = svc.get_schedule_summary(CLIENT_ID, schedule.id)
        assert isinstance(summary, ScheduleSummary)

    def test_identify_bottlenecks_delegates(self, cap_db):
        data = _seed_full_capacity_data(cap_db)

        svc = CapacityPlanningService(cap_db)
        bottlenecks = svc.identify_bottlenecks(CLIENT_ID, PERIOD_START, PERIOD_END)
        assert isinstance(bottlenecks, list)

    def test_get_kpi_history_delegates(self, cap_db):
        _create_client(cap_db)
        cap_db.commit()

        svc = CapacityPlanningService(cap_db)
        history = svc.get_kpi_history(CLIENT_ID, "efficiency")
        assert isinstance(history, list)


# ===========================================================================
# ORM Model Helper Method Tests
# ===========================================================================

class TestORMModelHelpers:
    """Test helper methods defined on ORM model classes."""

    def test_calendar_total_hours_working_day(self):
        cal = CapacityCalendar(
            is_working_day=True,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=4.0,
        )
        assert cal.total_hours() == 20.0

    def test_calendar_total_hours_nonworking_day(self):
        cal = CapacityCalendar(
            is_working_day=False,
            shift1_hours=8.0,
            shift2_hours=8.0,
        )
        assert cal.total_hours() == 0.0

    def test_production_line_effective_capacity(self):
        line = CapacityProductionLine(
            standard_capacity_units_per_hour=100,
            efficiency_factor=0.85,
            absenteeism_factor=0.05,
        )
        # 100 * 0.85 * (1 - 0.05) = 100 * 0.85 * 0.95 = 80.75
        assert line.effective_capacity_per_hour() == pytest.approx(80.75, rel=1e-4)

    def test_order_remaining_quantity(self):
        order = CapacityOrder(order_quantity=1000, completed_quantity=300)
        assert order.remaining_quantity() == 700

    def test_order_completion_percent(self):
        order = CapacityOrder(order_quantity=1000, completed_quantity=250)
        assert order.completion_percent() == pytest.approx(25.0)

    def test_order_completion_percent_zero_quantity(self):
        order = CapacityOrder(order_quantity=0, completed_quantity=0)
        assert order.completion_percent() == 0.0

    def test_standard_total_minutes(self):
        std = CapacityProductionStandard(sam_minutes=5.5)
        assert std.total_minutes() == 5.5

    def test_standard_sam_hours(self):
        std = CapacityProductionStandard(sam_minutes=60.0)
        assert std.sam_hours() == 1.0

    def test_bom_detail_required_quantity(self):
        detail = CapacityBOMDetail(quantity_per=2.0, waste_percentage=10.0)
        # 2.0 * 100 * (1 + 10/100) = 200 * 1.10 = 220
        assert detail.required_quantity(100) == pytest.approx(220.0)

    def test_stock_calculate_available(self):
        stock = CapacityStockSnapshot(
            on_hand_quantity=1000, allocated_quantity=200, on_order_quantity=50
        )
        assert stock.calculate_available() == 850.0

    def test_stock_is_short(self):
        stock = CapacityStockSnapshot(
            on_hand_quantity=100, allocated_quantity=0, on_order_quantity=0
        )
        assert stock.is_short(200) is True
        assert stock.is_short(50) is False

    def test_stock_shortage_quantity(self):
        stock = CapacityStockSnapshot(
            on_hand_quantity=100, allocated_quantity=0, on_order_quantity=0
        )
        assert stock.shortage_quantity(150) == 50.0
        assert stock.shortage_quantity(50) == 0

    def test_component_check_calculate_status(self):
        assert CapacityComponentCheck.calculate_status(100, 200) == ComponentStatus.OK
        assert CapacityComponentCheck.calculate_status(100, 50) == ComponentStatus.PARTIAL
        assert CapacityComponentCheck.calculate_status(100, 0) == ComponentStatus.SHORTAGE

    def test_component_check_coverage_percent(self):
        check = CapacityComponentCheck(required_quantity=200, available_quantity=100)
        assert check.coverage_percent() == pytest.approx(50.0)

    def test_analysis_calculate_metrics(self):
        a = CapacityAnalysis(
            working_days=5,
            shifts_per_day=2,
            hours_per_shift=8.0,
            efficiency_factor=0.85,
            absenteeism_factor=0.05,
            operators_available=10,
            demand_hours=500,
        )
        a.calculate_metrics()

        assert float(a.gross_hours) == 80.0  # 5*2*8
        # net = 80 * 0.85 * 0.95 = 64.6
        assert float(a.net_hours) == pytest.approx(64.6, rel=1e-3)
        # capacity = 64.6 * 10 = 646
        assert float(a.capacity_hours) == pytest.approx(646.0, rel=1e-3)
        # utilization = 500 / 646 * 100 = ~77.4%
        assert float(a.utilization_percent) == pytest.approx(77.4, rel=0.1)
        assert a.is_bottleneck is False

    def test_analysis_bottleneck_detection(self):
        a = CapacityAnalysis(
            working_days=1,
            shifts_per_day=1,
            hours_per_shift=8.0,
            efficiency_factor=1.0,
            absenteeism_factor=0.0,
            operators_available=1,
            demand_hours=10,
        )
        a.calculate_metrics()
        # capacity = 8, demand = 10, utilization = 125% > 95%
        assert a.is_bottleneck is True

    def test_schedule_is_editable(self):
        s = CapacitySchedule(status=ScheduleStatus.DRAFT)
        assert s.is_editable() is True

        s.status = ScheduleStatus.COMMITTED
        assert s.is_editable() is False

    def test_schedule_detail_remaining_quantity(self):
        d = CapacityScheduleDetail(scheduled_quantity=500, completed_quantity=200)
        assert d.remaining_quantity() == 300

    def test_schedule_detail_completion_percent(self):
        d = CapacityScheduleDetail(scheduled_quantity=400, completed_quantity=100)
        assert d.completion_percent() == pytest.approx(25.0)

    def test_scenario_get_parameter(self):
        s = CapacityScenario(parameters_json={"overtime_percent": 20, "foo": "bar"})
        assert s.get_parameter("overtime_percent") == 20
        assert s.get_parameter("missing", "default") == "default"

    def test_scenario_get_result(self):
        s = CapacityScenario(results_json={"capacity_increase_percent": 15.0})
        assert s.capacity_increase_percent() == 15.0
        assert s.cost_impact() == 0.0

    def test_scenario_get_parameter_none_json(self):
        s = CapacityScenario(parameters_json=None)
        assert s.get_parameter("anything", "fallback") == "fallback"

    def test_kpi_commitment_calculate_variance(self):
        c = CapacityKPICommitment(committed_value=85.0, actual_value=90.0)
        c.calculate_variance()
        assert float(c.variance) == pytest.approx(5.0, rel=1e-4)
        assert float(c.variance_percent) == pytest.approx(5.882, rel=0.01)

    def test_kpi_commitment_is_on_target(self):
        c = CapacityKPICommitment(
            committed_value=85.0, actual_value=86.0,
            variance_percent=1.18,
        )
        assert c.is_on_target(tolerance_percent=5.0) is True

    def test_kpi_commitment_above_below_target(self):
        c = CapacityKPICommitment(variance=Decimal("5.0"))
        assert c.is_above_target() is True
        assert c.is_below_target() is False

        c2 = CapacityKPICommitment(variance=Decimal("-3.0"))
        assert c2.is_above_target() is False
        assert c2.is_below_target() is True

    def test_kpi_commitment_variance_zero_committed(self):
        c = CapacityKPICommitment(committed_value=0, actual_value=10.0)
        c.calculate_variance()
        assert float(c.variance) == 10.0
        assert float(c.variance_percent) == 100.0

    def test_kpi_commitment_variance_both_zero(self):
        c = CapacityKPICommitment(committed_value=0, actual_value=0)
        c.calculate_variance()
        assert float(c.variance) == 0.0
        assert float(c.variance_percent) == 0.0


# ===========================================================================
# Cross-Service Integration Tests
# ===========================================================================

class TestCrossServiceIntegration:
    """Integration tests that exercise multiple services together."""

    def test_full_bom_to_mrp_pipeline(self, cap_db):
        """BOM explosion feeds into MRP component check."""
        data = _seed_full_capacity_data(cap_db)

        bom_svc = BOMService(cap_db)
        mrp_svc = MRPService(cap_db)

        # Explode BOM
        explosion = bom_svc.explode_bom(CLIENT_ID, "STYLE-A", Decimal("500"))
        assert explosion.total_components == 3

        # Run MRP check for the same style
        order_a = next(o for o in data["orders"] if o.style_code == "STYLE-A")
        mrp_result = mrp_svc.run_component_check(CLIENT_ID, [order_a.id])
        assert mrp_result.total_components_checked == 3

    def test_analysis_then_scenario(self, cap_db):
        """Run analysis baseline, then apply scenario on top."""
        data = _seed_full_capacity_data(cap_db)

        analysis_svc = CapacityAnalysisService(cap_db)
        scenario_svc = ScenarioService(cap_db)

        baseline = analysis_svc.analyze_capacity(CLIENT_ID, PERIOD_START, PERIOD_END)
        assert baseline.total_capacity_hours > 0

        scenario = scenario_svc.create_scenario(
            CLIENT_ID, "OT After Analysis", ScenarioType.OVERTIME
        )
        result = scenario_svc.apply_scenario_parameters(
            CLIENT_ID, scenario.id, PERIOD_START, PERIOD_END
        )

        assert result.modified_metrics["total_capacity_hours"] >= result.original_metrics["total_capacity_hours"]

    def test_schedule_commit_with_kpi_tracking(self, cap_db):
        """Create schedule, commit it, store KPIs, verify retrieval."""
        data = _seed_full_capacity_data(cap_db)

        sched_svc = SchedulingService(cap_db)
        kpi_svc = KPIIntegrationService(cap_db)

        schedule = sched_svc.create_schedule(
            CLIENT_ID, "KPI Track", PERIOD_START, PERIOD_END, items=[]
        )
        sched_svc.commit_schedule(CLIENT_ID, schedule.id, committed_by=1)

        kpi_svc.store_kpi_commitments(
            CLIENT_ID, schedule.id,
            {
                "efficiency": Decimal("85.0"),
                "quality": Decimal("98.5"),
                "otd": Decimal("95.0"),
            },
        )

        commitments = kpi_svc.get_kpi_commitments(CLIENT_ID, schedule.id)
        assert len(commitments) == 3

        history = kpi_svc.get_kpi_history(CLIENT_ID, "efficiency")
        assert len(history) == 1

    def test_multiple_scenarios_comparison(self, cap_db):
        """Compare three different scenario types side by side."""
        data = _seed_full_capacity_data(cap_db)

        svc = ScenarioService(cap_db)
        s1 = svc.create_scenario(CLIENT_ID, "S1-OT", ScenarioType.OVERTIME)
        s2 = svc.create_scenario(CLIENT_ID, "S2-Setup", ScenarioType.SETUP_REDUCTION)
        s3 = svc.create_scenario(CLIENT_ID, "S3-3Shift", ScenarioType.THREE_SHIFT)

        comparisons = svc.compare_scenarios(
            CLIENT_ID, [s1.id, s2.id, s3.id], PERIOD_START, PERIOD_END
        )

        assert len(comparisons) == 3
        # All should show capacity increase >= 0
        for comp in comparisons:
            assert comp.capacity_increase_percent >= 0

    def test_tenant_isolation_across_services(self, cap_db):
        """Data for one client should not leak to another."""
        data = _seed_full_capacity_data(cap_db)

        # Create another client
        other = Client(
            client_id="OTHER-X",
            client_name="Other X",
            client_type=ClientType.HOURLY_RATE,
            is_active=1,
        )
        cap_db.add(other)
        cap_db.commit()

        # Analysis for OTHER-X should yield no lines
        analysis_svc = CapacityAnalysisService(cap_db)
        result = analysis_svc.analyze_capacity("OTHER-X", PERIOD_START, PERIOD_END)
        assert result.lines_analyzed == 0

        # Schedules for OTHER-X should be empty
        sched_svc = SchedulingService(cap_db)
        schedules = sched_svc.list_schedules("OTHER-X")
        assert schedules == []

        # BOM lookup for OTHER-X should return None
        bom_svc = BOMService(cap_db)
        bom = bom_svc.get_bom_structure("OTHER-X", "STYLE-A")
        assert bom is None
