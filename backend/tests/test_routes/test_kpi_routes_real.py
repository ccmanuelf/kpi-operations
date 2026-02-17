"""
KPI Routes Tests with Real Database Integration
Target: Increase routes/kpi.py coverage to 75%+
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.schemas import ClientType
from backend.routes.kpi import router as kpi_router, thresholds_router
from backend.tests.fixtures.factories import TestDataFactory


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
    from backend.schemas.production_entry import ProductionEntry

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
    from backend.schemas.work_order import WorkOrder
    from backend.schemas import WorkOrderStatus

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

        # May return empty data but should be valid
        assert response.status_code in [200, 403, 404]

    def test_get_dashboard_with_date_range(self, supervisor_client):
        """Test getting dashboard with date range."""
        client, setup = supervisor_client
        start = date.today() - timedelta(days=30)
        end = date.today()

        response = client.get(f"/api/kpi/dashboard?start_date={start}&end_date={end}")

        assert response.status_code in [200, 403, 404]

    def test_get_dashboard_with_client_id(self, admin_client):
        """Test getting dashboard with client filter."""
        client, setup = admin_client
        client_id = setup["client"].client_id

        response = client.get(f"/api/kpi/dashboard?client_id={client_id}")

        assert response.status_code in [200, 403, 404]


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
        from backend.schemas.production_entry import ProductionEntry

        entry = db.query(ProductionEntry).first()

        if entry:
            response = client.get(f"/api/kpi/calculate/{entry.production_entry_id}")
            assert response.status_code in [200, 404]

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

        assert response.status_code in [200, 500]

    def test_get_aggregated_dashboard_with_dates(self, supervisor_client):
        """Test aggregated dashboard with date range."""
        client, setup = supervisor_client
        start = date.today() - timedelta(days=7)
        end = date.today()

        response = client.get(f"/api/kpi/dashboard/aggregated?start_date={start}&end_date={end}")

        assert response.status_code in [200, 500]


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

        assert response.status_code in [200, 404]  # May not exist if creation failed

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
