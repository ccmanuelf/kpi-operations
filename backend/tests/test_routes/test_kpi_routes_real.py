"""
KPI Routes Tests with Real Database Integration
Target: Increase routes/kpi.py coverage to 75%+
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import get_db
from backend.orm import ClientType
from backend.routes.kpi import router as kpi_router, thresholds_router
from backend.tests.fixtures.factories import TestDataFactory
from backend.tests.conftest import clone_template_engine


def create_test_app(db_session):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(kpi_router)
    app.include_router(thresholds_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def kpi_db():
    """Create a fresh database for each test."""
    engine = clone_template_engine()
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture
def kpi_setup(kpi_db):
    """Create standard test data for KPI tests."""
    db = kpi_db

    # Create client
    client = TestDataFactory.create_client(
        db, client_id="KPI-TEST-CLIENT", client_name="KPI Test Client", client_type=ClientType.HOURLY_RATE
    )

    # Create users
    admin = TestDataFactory.create_user(db, user_id="kpi-admin-001", username="kpi_admin", role="admin", client_id=None)

    supervisor = TestDataFactory.create_user(
        db, user_id="kpi-super-001", username="kpi_supervisor", role="supervisor", client_id=client.client_id
    )

    # Create product
    product = TestDataFactory.create_product(
        db,
        client_id=client.client_id,
        product_code="KPI-PROD-001",
        product_name="KPI Test Product",
        ideal_cycle_time=Decimal("0.10"),
    )

    # Create shift
    shift = TestDataFactory.create_shift(
        db, client_id=client.client_id, shift_name="KPI Test Shift", start_time="06:00:00", end_time="14:00:00"
    )

    db.flush()

    # Create production entries for trend data
    from backend.orm.production_entry import ProductionEntry

    for i in range(10):
        entry_date = datetime.combine(date.today() - timedelta(days=i), datetime.min.time())
        entry = ProductionEntry(
            production_entry_id=f"PE-KPI-{i:03d}",
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=entry_date,
            shift_date=entry_date,
            units_produced=100 + i * 10,
            run_time_hours=Decimal("8.0"),
            entered_by="kpi-super-001",
            defect_count=i,
            scrap_count=0,
            employees_assigned=5,
            efficiency_percentage=Decimal("85") + Decimal(i),
            performance_percentage=Decimal("90") + Decimal(i),
        )
        db.add(entry)

    # Create work orders for OTD testing
    from backend.orm.work_order import WorkOrder
    from backend.orm import WorkOrderStatus

    # On-time work order
    on_time_wo = WorkOrder(
        work_order_id="WO-KPI-001",
        client_id=client.client_id,
        style_model="STYLE-001",
        status=WorkOrderStatus.COMPLETED,
        required_date=datetime.now(tz=timezone.utc) + timedelta(days=5),
        actual_delivery_date=datetime.now(tz=timezone.utc) - timedelta(days=1),
        planned_quantity=100,
    )
    db.add(on_time_wo)

    # Late work order
    late_wo = WorkOrder(
        work_order_id="WO-KPI-002",
        client_id=client.client_id,
        style_model="STYLE-002",
        status=WorkOrderStatus.COMPLETED,
        required_date=datetime.now(tz=timezone.utc) - timedelta(days=5),
        actual_delivery_date=datetime.now(tz=timezone.utc) - timedelta(days=2),
        planned_quantity=100,
    )
    db.add(late_wo)

    # Pending work order (not yet delivered, but not late)
    pending_wo = WorkOrder(
        work_order_id="WO-KPI-003",
        client_id=client.client_id,
        style_model="STYLE-003",
        status=WorkOrderStatus.IN_PROGRESS,
        required_date=datetime.now(tz=timezone.utc) + timedelta(days=10),
        actual_delivery_date=None,
        planned_quantity=100,
    )
    db.add(pending_wo)

    db.commit()

    return {
        "db": db,
        "client": client,
        "admin": admin,
        "supervisor": supervisor,
        "product": product,
        "shift": shift,
    }


@pytest.fixture
def admin_client(kpi_setup):
    """Create an admin test client."""
    db = kpi_setup["db"]
    user = kpi_setup["admin"]
    app = create_test_app(db)

    from backend.auth.jwt import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user

    return TestClient(app), kpi_setup


@pytest.fixture
def supervisor_client(kpi_setup):
    """Create a supervisor test client."""
    db = kpi_setup["db"]
    user = kpi_setup["supervisor"]
    app = create_test_app(db)

    from backend.auth.jwt import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user

    return TestClient(app), kpi_setup


class TestKPIThresholds:
    """Tests for KPI threshold routes."""

    def test_get_kpi_thresholds_global(self, admin_client):
        """Test getting global KPI thresholds."""
        client, setup = admin_client

        response = client.get("/api/kpi-thresholds")

        assert response.status_code == 200
        data = response.json()
        assert "client_id" in data
        assert "thresholds" in data
        assert isinstance(data["thresholds"], dict)

    def test_get_kpi_thresholds_with_client_id(self, admin_client):
        """Test getting KPI thresholds for a specific client."""
        client, setup = admin_client
        client_id = setup["client"].client_id

        response = client.get(f"/api/kpi-thresholds?client_id={client_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == client_id

    def test_update_kpi_thresholds_admin(self, admin_client):
        """Test admin updating KPI thresholds."""
        client, setup = admin_client
        client_id = setup["client"].client_id

        response = client.put(
            "/api/kpi-thresholds",
            json={
                "client_id": client_id,
                "thresholds": {
                    "efficiency": {"target_value": 90.0, "warning_threshold": 80.0, "critical_threshold": 70.0}
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Updated 1 thresholds"
        assert data["client_id"] == client_id
        assert "efficiency" in data["updated_kpis"]

    def test_update_kpi_thresholds_forbidden_supervisor(self, supervisor_client):
        """Test supervisor cannot update KPI thresholds."""
        client, setup = supervisor_client

        response = client.put(
            "/api/kpi-thresholds", json={"client_id": None, "thresholds": {"efficiency": {"target_value": 99.0}}}
        )

        assert response.status_code == 403


class TestKPIDashboard:
    """Tests for KPI dashboard routes."""

    def test_get_dashboard_default_dates(self, supervisor_client):
        """Test getting dashboard with default dates."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/dashboard")

        assert response.status_code == 200

    def test_get_dashboard_with_date_range(self, supervisor_client):
        """Test getting dashboard with date range."""
        client, setup = supervisor_client
        start = date.today() - timedelta(days=30)
        end = date.today()

        response = client.get(f"/api/kpi/dashboard?start_date={start}&end_date={end}")

        assert response.status_code == 200

    def test_get_dashboard_with_client_id(self, admin_client):
        """Test getting dashboard with client filter."""
        client, setup = admin_client
        client_id = setup["client"].client_id

        response = client.get(f"/api/kpi/dashboard?client_id={client_id}")

        assert response.status_code == 200


class TestKPIDashboardEfficiencyAvailableBasis:
    """Task 3 (Cycle 3 PR-B): additive `efficiency_available_basis` field on
    GET /api/kpi/dashboard.

    This is the endpoint the KPI dashboard's efficiency card actually
    consumes -- traced (not guessed) via frontend/src/stores/kpi.ts
    (fetchEfficiency -> api.getEfficiency) -> frontend/src/services/api/kpi.ts
    (getEfficiency composes GET /api/kpi/dashboard + /efficiency/by-shift +
    /efficiency/by-product; `current` -- the headline number rendered on the
    card -- comes exclusively from this /dashboard endpoint's avg_efficiency).
    `/api/kpi/calculate/{entry_id}` and `/api/kpi/dashboard/aggregated` were
    confirmed UNUSED by the dashboard (grep across frontend/src turned up no
    callers besides a dead unit test / the aggregated route's own test file),
    so neither is the target here.

    Each scenario uses its own client_id and a single production_entry/day so
    `avg_efficiency` is exactly that one entry's efficiency_percentage --
    keeping the "existing value unchanged" pin exact.
    """

    def _make_client_and_admin(self, db, client_id):
        client = TestDataFactory.create_client(db, client_id=client_id)
        admin = TestDataFactory.create_user(
            db, user_id=f"{client_id}-admin", username=f"{client_id}_admin".lower(), role="admin", client_id=None
        )
        return client, admin

    def _authed_client(self, db, user):
        from backend.auth.jwt import get_current_user

        app = create_test_app(db)
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    def test_available_less_than_scheduled_basis_above_current(self, kpi_db):
        """One entry with a training allocation: available (6.00) < scheduled
        (9.00) -> efficiency_available_basis must exceed the UNCHANGED
        avg_efficiency (the pre-existing scheduled-basis figure).

        avg_efficiency (pinned, unchanged) = 80.0
        AttendanceEntry: scheduled_hours=9.00, actual_hours=9.00,
          allocations=[training 3.00] (non-productive)
          -> available_for_efficiency = actual - nonproductive = 9.00 - 3.00 = 6.00
        efficiency_available_basis = avg_efficiency * (scheduled / available)
                                    = 80.0 * (9.00 / 6.00) = 80.0 * 1.5 = 120.00
        """
        from backend.orm.attendance_hour_allocation import AttendanceHourAllocation
        from backend.orm.production_entry import ProductionEntry

        db = kpi_db
        client, admin = self._make_client_and_admin(db, "KPI-AVB-1")
        product = TestDataFactory.create_product(db, client_id=client.client_id)
        shift = TestDataFactory.create_shift(db, client_id=client.client_id)
        employee = TestDataFactory.create_employee(db, client_id=client.client_id)
        db.flush()

        entry_date = datetime.combine(date(2026, 8, 1), datetime.min.time())
        db.add(
            ProductionEntry(
                production_entry_id="PE-AVB-1",
                client_id=client.client_id,
                product_id=product.product_id,
                shift_id=shift.shift_id,
                production_date=entry_date,
                shift_date=entry_date,
                units_produced=100,
                run_time_hours=Decimal("8.0"),
                entered_by=admin.user_id,
                defect_count=0,
                scrap_count=0,
                employees_assigned=5,
                efficiency_percentage=Decimal("80.00"),
                performance_percentage=Decimal("90.00"),
            )
        )

        attendance_entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=date(2026, 8, 1),
            scheduled_hours=Decimal("9.00"),
            actual_hours=Decimal("9.00"),
        )
        attendance_entry.hour_allocations = [
            AttendanceHourAllocation(category="training", hours=Decimal("3.00")),
        ]
        db.commit()

        response = self._authed_client(db, admin).get(
            "/api/kpi/dashboard",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01", "client_id": client.client_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        row = data[0]

        # Pre-existing fields byte-identical (pinned exact pre-existing values)
        assert row["avg_efficiency"] == 80.0
        assert row["avg_performance"] == 90.0
        assert row["total_units"] == 100
        assert row["entry_count"] == 1

        # New additive field
        assert row["efficiency_available_basis"] == 120.0
        assert row["efficiency_available_basis"] > row["avg_efficiency"]

    def test_no_allocation_data_uses_actual_hours_basis(self, kpi_db):
        """No HourAllocation rows at all: Task 1's `available_for_efficiency_hours`
        conservative default makes available == actual_hours (entries without
        allocation data contribute full actual hours). With actual != scheduled,
        this exercises the entries' actual-hours-basis efficiency distinctly from
        the (unchanged) scheduled-basis avg_efficiency.

        avg_efficiency (pinned, unchanged) = 75.0
        AttendanceEntry: scheduled_hours=8.00, actual_hours=10.00, no allocations
          -> available_for_efficiency = actual (conservative default) = 10.00
        efficiency_available_basis = 75.0 * (8.00 / 10.00) = 75.0 * 0.8 = 60.00
        """
        from backend.orm.production_entry import ProductionEntry

        db = kpi_db
        client, admin = self._make_client_and_admin(db, "KPI-AVB-2")
        product = TestDataFactory.create_product(db, client_id=client.client_id)
        shift = TestDataFactory.create_shift(db, client_id=client.client_id)
        employee = TestDataFactory.create_employee(db, client_id=client.client_id)
        db.flush()

        entry_date = datetime.combine(date(2026, 8, 1), datetime.min.time())
        db.add(
            ProductionEntry(
                production_entry_id="PE-AVB-2",
                client_id=client.client_id,
                product_id=product.product_id,
                shift_id=shift.shift_id,
                production_date=entry_date,
                shift_date=entry_date,
                units_produced=100,
                run_time_hours=Decimal("8.0"),
                entered_by=admin.user_id,
                defect_count=0,
                scrap_count=0,
                employees_assigned=5,
                efficiency_percentage=Decimal("75.00"),
                performance_percentage=Decimal("90.00"),
            )
        )

        TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=date(2026, 8, 1),
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("10.00"),
        )
        db.commit()

        response = self._authed_client(db, admin).get(
            "/api/kpi/dashboard",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01", "client_id": client.client_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        row = data[0]

        assert row["avg_efficiency"] == 75.0
        assert row["efficiency_available_basis"] == 60.0

    def test_no_attendance_data_is_none(self, kpi_db):
        """Zero AttendanceEntry rows anywhere in the window: never fabricate a
        denominator -> efficiency_available_basis must be None, while the
        pre-existing avg_efficiency stays exactly its pinned value.
        """
        from backend.orm.production_entry import ProductionEntry

        db = kpi_db
        client, admin = self._make_client_and_admin(db, "KPI-AVB-3")
        product = TestDataFactory.create_product(db, client_id=client.client_id)
        shift = TestDataFactory.create_shift(db, client_id=client.client_id)
        db.flush()

        entry_date = datetime.combine(date(2026, 8, 1), datetime.min.time())
        db.add(
            ProductionEntry(
                production_entry_id="PE-AVB-3",
                client_id=client.client_id,
                product_id=product.product_id,
                shift_id=shift.shift_id,
                production_date=entry_date,
                shift_date=entry_date,
                units_produced=100,
                run_time_hours=Decimal("8.0"),
                entered_by=admin.user_id,
                defect_count=0,
                scrap_count=0,
                employees_assigned=5,
                efficiency_percentage=Decimal("70.00"),
                performance_percentage=Decimal("90.00"),
            )
        )
        db.commit()

        response = self._authed_client(db, admin).get(
            "/api/kpi/dashboard",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01", "client_id": client.client_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        row = data[0]

        assert row["avg_efficiency"] == 70.0
        assert row["efficiency_available_basis"] is None


class TestEfficiencyRoutes:
    """Tests for efficiency KPI routes."""

    def test_get_efficiency_by_shift(self, supervisor_client):
        """Test getting efficiency aggregated by shift."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/efficiency/by-shift")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have data from our test entries
        if data:
            assert "shift_id" in data[0]
            assert "efficiency" in data[0]

    def test_get_efficiency_by_shift_with_dates(self, supervisor_client):
        """Test efficiency by shift with date filter."""
        client, setup = supervisor_client
        start = date.today() - timedelta(days=30)
        end = date.today()

        response = client.get(f"/api/kpi/efficiency/by-shift?start_date={start}&end_date={end}")

        assert response.status_code == 200

    def test_get_efficiency_by_product(self, supervisor_client):
        """Test getting efficiency aggregated by product."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/efficiency/by-product")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "product_id" in data[0]
            assert "efficiency" in data[0]

    def test_get_efficiency_by_product_with_limit(self, supervisor_client):
        """Test efficiency by product with limit."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/efficiency/by-product?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5

    def test_get_efficiency_trend(self, supervisor_client):
        """Test getting efficiency trend."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/efficiency/trend")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # We created 10 days of data
        if data:
            assert "date" in data[0]
            assert "value" in data[0]


class TestPerformanceRoutes:
    """Tests for performance KPI routes."""

    def test_get_performance_trend(self, supervisor_client):
        """Test getting performance trend."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/performance/trend")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "date" in data[0]
            assert "value" in data[0]

    def test_get_performance_by_shift(self, supervisor_client):
        """Test getting performance aggregated by shift."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/performance/by-shift")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_performance_by_product(self, supervisor_client):
        """Test getting performance aggregated by product."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/performance/by-product")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestOTDRoutes:
    """Tests for On-Time Delivery KPI routes."""

    def test_calculate_otd(self, supervisor_client):
        """Test OTD calculation."""
        client, setup = supervisor_client
        start = date.today() - timedelta(days=30)
        end = date.today() + timedelta(days=30)  # Include future dates for pending orders

        response = client.get(f"/api/kpi/otd?start_date={start}&end_date={end}")

        assert response.status_code == 200
        data = response.json()
        assert "otd_percentage" in data
        assert "on_time_count" in data
        assert "total_orders" in data

    def test_calculate_otd_with_client(self, admin_client):
        """Test OTD with client filter."""
        client, setup = admin_client
        client_id = setup["client"].client_id
        start = date.today() - timedelta(days=30)
        end = date.today() + timedelta(days=30)

        response = client.get(f"/api/kpi/otd?start_date={start}&end_date={end}&client_id={client_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == client_id

    def test_calculate_otd_surfaces_justified_delay_metrics(self, supervisor_client):
        """GET /api/kpi/otd surfaces calculate_true_otd's Task 5 keys
        (late_counts, justified_by_reason, true_otd/standard_otd incl.
        net_percentage) verbatim, additive to the route's own pre-existing
        keys.

        Reuses the exact WO-NET-00{1..6} scenario from
        TestCalculateTrueOTDNetOfJustified.test_true_otd_gross_vs_net_with_derivation
        in test_otd_comprehensive.py, so the expected values below are
        pinned by that test's own derivation:
          - WO-NET-001, WO-NET-002: delivered on time (COMPLETED)
          - WO-NET-003: delivered late, justified/customer_request
          - WO-NET-004: delivered late, unjustified
          - WO-NET-005: delivered late, unclassified (NULL)
          - WO-NET-006: undelivered, planned_ship_date before `end` -> past-due
            (unclassified); has no actual_delivery_date so it never enters
            true_otd/standard_otd counts, only late_counts (carried context:
            the undelivered arm has no start_date bound by design).

        late_counts.total = 3 delivered-late (WO3,WO4,WO5) + 1 undelivered
        past-due (WO6) = 4; justified=1 (WO3); unjustified=1 (WO4);
        unclassified=2 (WO5, WO6).
        justified_by_reason = {"customer_request": 1} (WO3 only).
        gross true-OTD = 2 on_time / 5 delivered = 40.00.
        net true-OTD = (2 on_time + 1 justified-late) / 5 delivered = 60.00.
        standard_otd mirrors true_otd here (all 5 delivered orders are
        COMPLETED).
        """
        client, setup = supervisor_client
        db = setup["db"]
        client_obj = setup["client"]

        from backend.orm.work_order import WorkOrder
        from backend.orm import WorkOrderStatus

        wo1 = WorkOrder(
            work_order_id="WO-NET-001",
            client_id=client_obj.client_id,
            style_model="NET-STYLE",
            planned_quantity=10,
            status=WorkOrderStatus.COMPLETED,
            planned_ship_date=datetime(2026, 1, 10, 12, 0),
            actual_delivery_date=datetime(2026, 1, 10, 8, 0),  # before planned -> on time
        )
        wo2 = WorkOrder(
            work_order_id="WO-NET-002",
            client_id=client_obj.client_id,
            style_model="NET-STYLE",
            planned_quantity=10,
            status=WorkOrderStatus.COMPLETED,
            planned_ship_date=datetime(2026, 1, 15, 12, 0),
            actual_delivery_date=datetime(2026, 1, 14, 8, 0),  # before planned -> on time
        )
        wo3 = WorkOrder(
            work_order_id="WO-NET-003",
            client_id=client_obj.client_id,
            style_model="NET-STYLE",
            planned_quantity=10,
            status=WorkOrderStatus.COMPLETED,
            planned_ship_date=datetime(2026, 1, 5, 12, 0),
            actual_delivery_date=datetime(2026, 1, 8, 8, 0),  # after planned -> late
            delay_classification="justified",
            justified_delay_reason="customer_request",
        )
        wo4 = WorkOrder(
            work_order_id="WO-NET-004",
            client_id=client_obj.client_id,
            style_model="NET-STYLE",
            planned_quantity=10,
            status=WorkOrderStatus.COMPLETED,
            planned_ship_date=datetime(2026, 1, 6, 12, 0),
            actual_delivery_date=datetime(2026, 1, 9, 8, 0),  # after planned -> late
            delay_classification="unjustified",
        )
        wo5 = WorkOrder(
            work_order_id="WO-NET-005",
            client_id=client_obj.client_id,
            style_model="NET-STYLE",
            planned_quantity=10,
            status=WorkOrderStatus.COMPLETED,
            planned_ship_date=datetime(2026, 1, 7, 12, 0),
            actual_delivery_date=datetime(2026, 1, 12, 8, 0),  # after planned -> late
            # delay_classification left NULL -> unclassified
        )
        wo6 = WorkOrder(
            work_order_id="WO-NET-006",
            client_id=client_obj.client_id,
            style_model="NET-STYLE",
            planned_quantity=10,
            status=WorkOrderStatus.IN_PROGRESS,
            planned_ship_date=datetime(2026, 1, 3, 12, 0),  # before `end` -> is_late(wo, end) True
            actual_delivery_date=None,
        )

        db.add_all([wo1, wo2, wo3, wo4, wo5, wo6])
        db.commit()

        response = client.get("/api/kpi/otd?start_date=2026-01-01&end_date=2026-01-31")

        assert response.status_code == 200
        data = response.json()

        assert data["late_counts"] == {"total": 4, "justified": 1, "unjustified": 1, "unclassified": 2}
        assert data["justified_by_reason"] == {"customer_request": 1}
        assert data["true_otd"]["percentage"] == 40.0
        assert data["true_otd"]["net_percentage"] == 60.0
        assert data["standard_otd"]["percentage"] == 40.0
        assert data["standard_otd"]["net_percentage"] == 60.0

        # Pre-existing top-level keys stay intact (additive change).
        assert "otd_percentage" in data
        assert "on_time_count" in data
        assert "total_orders" in data

    def test_calculate_otd_admin_no_client_id_omits_justified_delay_metrics(self, admin_client):
        """calculate_true_otd requires a single client_id; an admin request
        with no client_id resolves to an all-clients scope (scope.as_single()
        returns None). The additive keys are then simply omitted rather than
        erroring — the pre-existing (non-Task-5) response shape is untouched."""
        client, setup = admin_client
        start = date.today() - timedelta(days=30)
        end = date.today() + timedelta(days=30)

        response = client.get(f"/api/kpi/otd?start_date={start}&end_date={end}")

        assert response.status_code == 200
        data = response.json()
        assert "late_counts" not in data
        assert "justified_by_reason" not in data
        assert "true_otd" not in data
        assert "standard_otd" not in data
        assert "otd_percentage" in data

    def test_get_late_orders(self, supervisor_client):
        """Test getting late orders."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/late-orders")

        assert response.status_code == 200
        # Returns list of late orders (may be empty)
        assert isinstance(response.json(), (list, dict))

    def test_get_otd_by_client(self, admin_client):
        """Test OTD aggregated by client."""
        client, setup = admin_client

        response = client.get("/api/kpi/otd/by-client")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_late_deliveries(self, supervisor_client):
        """Test getting late deliveries list."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/otd/late-deliveries")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # We created a late work order
        if data:
            assert "work_order" in data[0]
            assert "delay_hours" in data[0]


class TestKPICalculation:
    """Tests for KPI calculation endpoint."""

    def test_calculate_kpis_for_entry(self, supervisor_client):
        """Test KPI calculation for a production entry."""
        client, setup = supervisor_client
        db = setup["db"]

        # Get entry ID from database
        from backend.orm.production_entry import ProductionEntry

        entry = db.query(ProductionEntry).first()

        if entry:
            response = client.get(f"/api/kpi/calculate/{entry.production_entry_id}")
            assert response.status_code == 200

    def test_calculate_kpis_entry_not_found(self, supervisor_client):
        """Test KPI calculation for non-existent entry."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/calculate/99999")

        assert response.status_code == 404


class TestQualityTrend:
    """Tests for quality trend routes."""

    def test_get_quality_trend(self, supervisor_client):
        """Test getting quality trend."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/quality/trend")

        assert response.status_code == 200
        # May be empty if no quality entries
        data = response.json()
        assert isinstance(data, list)


class TestAvailabilityRoutes:
    """Tests for availability KPI routes."""

    def test_get_availability_trend(self, supervisor_client):
        """Test getting availability trend."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/availability/trend")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestMultiTenantAccess:
    """Tests for multi-tenant KPI access."""

    def test_admin_sees_all_clients(self, admin_client):
        """Test admin can see all clients in OTD by client."""
        client, setup = admin_client

        response = client.get("/api/kpi/otd/by-client")

        assert response.status_code == 200

    def test_supervisor_filtered_by_client(self, supervisor_client):
        """Test supervisor sees only their client data."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/efficiency/trend")

        assert response.status_code == 200
        # Data should be filtered to supervisor's client


class TestOEETrend:
    """Tests for OEE trend routes."""

    def test_get_oee_trend(self, supervisor_client):
        """Test getting OEE trend."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/oee/trend")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "date" in data[0]
            assert "value" in data[0]

    def test_get_oee_trend_with_dates(self, supervisor_client):
        """Test OEE trend with date filter."""
        client, setup = supervisor_client
        start = date.today() - timedelta(days=14)
        end = date.today()

        response = client.get(f"/api/kpi/oee/trend?start_date={start}&end_date={end}")

        assert response.status_code == 200


class TestOTDTrend:
    """Tests for OTD trend routes."""

    def test_get_otd_trend(self, supervisor_client):
        """Test getting OTD trend."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/on-time-delivery/trend")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestAbsenteeismTrend:
    """Tests for absenteeism trend routes."""

    def test_get_absenteeism_trend(self, supervisor_client):
        """Test getting absenteeism trend."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/absenteeism/trend")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestAggregatedDashboard:
    """Tests for aggregated dashboard."""

    def test_get_aggregated_dashboard(self, supervisor_client):
        """Test getting aggregated dashboard."""
        client, setup = supervisor_client

        response = client.get("/api/kpi/dashboard/aggregated")

        assert response.status_code == 200

    def test_get_aggregated_dashboard_with_dates(self, supervisor_client):
        """Test aggregated dashboard with date range."""
        client, setup = supervisor_client
        start = date.today() - timedelta(days=7)
        end = date.today()

        response = client.get(f"/api/kpi/dashboard/aggregated?start_date={start}&end_date={end}")

        assert response.status_code == 200


class TestThresholdsDelete:
    """Tests for threshold deletion."""

    def test_delete_threshold_admin_success(self, admin_client):
        """Test admin can delete client-specific threshold."""
        client, setup = admin_client
        client_id = setup["client"].client_id

        # First create a threshold
        client.put(
            "/api/kpi-thresholds", json={"client_id": client_id, "thresholds": {"efficiency": {"target_value": 90.0}}}
        )

        # Now delete it
        response = client.delete(f"/api/kpi-thresholds/{client_id}/efficiency")

        assert response.status_code == 200

    def test_delete_threshold_not_found(self, admin_client):
        """Test deleting non-existent threshold."""
        client, setup = admin_client
        client_id = setup["client"].client_id

        response = client.delete(f"/api/kpi-thresholds/{client_id}/nonexistent_kpi")

        assert response.status_code == 404

    def test_delete_threshold_forbidden_supervisor(self, supervisor_client):
        """Test supervisor cannot delete thresholds."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        response = client.delete(f"/api/kpi-thresholds/{client_id}/efficiency")

        assert response.status_code == 403
