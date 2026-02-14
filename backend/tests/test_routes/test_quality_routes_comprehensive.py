"""
Comprehensive Quality Routes Tests
Tests API endpoints with authenticated clients and real database.
Target: Increase routes/quality.py coverage from 21% to 80%+
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.schemas import ClientType
from backend.routes.quality import router as quality_router
from backend.tests.fixtures.factories import TestDataFactory


def create_test_app(db_session):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(quality_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def quality_db():
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
def quality_setup(quality_db):
    """Create standard test data for quality tests."""
    db = quality_db

    # Create client
    client = TestDataFactory.create_client(
        db, client_id="QUALITY-TEST", client_name="Quality Test Client", client_type=ClientType.HOURLY_RATE
    )

    # Create users
    admin = TestDataFactory.create_user(
        db, user_id="qual-admin-001", username="qual_admin", role="admin", client_id=None
    )

    supervisor = TestDataFactory.create_user(
        db, user_id="qual-super-001", username="qual_supervisor", role="supervisor", client_id=client.client_id
    )

    operator = TestDataFactory.create_user(
        db, user_id="qual-oper-001", username="qual_operator", role="operator", client_id=client.client_id
    )

    # Create product
    product = TestDataFactory.create_product(
        db,
        client_id=client.client_id,
        product_code="QUAL-PROD-001",
        product_name="Quality Test Product",
        ideal_cycle_time=Decimal("0.15"),
    )

    # Create shift
    shift = TestDataFactory.create_shift(
        db, client_id=client.client_id, shift_name="Quality Shift", start_time="06:00:00", end_time="14:00:00"
    )

    db.flush()

    db.commit()

    return {
        "db": db,
        "client": client,
        "admin": admin,
        "supervisor": supervisor,
        "operator": operator,
        "product": product,
        "shift": shift,
    }


@pytest.fixture
def authenticated_client(quality_setup):
    """Create an authenticated test client."""
    db = quality_setup["db"]
    user = quality_setup["supervisor"]
    app = create_test_app(db)

    # Mock auth dependencies
    from backend.auth.jwt import get_current_user, get_current_active_supervisor

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_active_supervisor] = lambda: user

    return TestClient(app), quality_setup


@pytest.fixture
def admin_client(quality_setup):
    """Create an admin test client."""
    db = quality_setup["db"]
    user = quality_setup["admin"]
    app = create_test_app(db)

    from backend.auth.jwt import get_current_user, get_current_active_supervisor

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_active_supervisor] = lambda: user

    return TestClient(app), quality_setup


class TestListQualityInspections:
    """Tests for GET /api/quality endpoint."""

    def test_list_quality_success(self, authenticated_client):
        """Test listing quality inspections."""
        client, setup = authenticated_client

        response = client.get("/api/quality")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_quality_with_pagination(self, authenticated_client):
        """Test pagination."""
        client, setup = authenticated_client

        response = client.get("/api/quality?skip=0&limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2

    def test_list_quality_filter_by_date(self, authenticated_client):
        """Test filtering by date range."""
        client, setup = authenticated_client
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(f"/api/quality?start_date={week_ago}&end_date={today}")

        assert response.status_code == 200


class TestGetQualityInspection:
    """Tests for GET /api/quality/{inspection_id} endpoint."""

    def test_get_quality_not_found(self, authenticated_client):
        """Test error when inspection doesn't exist."""
        client, _ = authenticated_client

        response = client.get("/api/quality/99999")

        assert response.status_code == 404


class TestUpdateQualityInspection:
    """Tests for PUT /api/quality/{inspection_id} endpoint."""

    def test_update_quality_not_found(self, authenticated_client):
        """Test error when inspection doesn't exist."""
        client, _ = authenticated_client

        response = client.put("/api/quality/99999", json={"units_inspected": 100})

        assert response.status_code == 404


class TestDeleteQualityInspection:
    """Tests for DELETE /api/quality/{inspection_id} endpoint."""

    def test_delete_quality_not_found(self, authenticated_client):
        """Test error when inspection doesn't exist."""
        client, _ = authenticated_client

        response = client.delete("/api/quality/99999")

        assert response.status_code == 404


class TestQualityStatistics:
    """Tests for GET /api/quality/statistics/summary endpoint."""

    def test_get_quality_statistics_success(self, authenticated_client):
        """Test getting quality statistics."""
        client, setup = authenticated_client
        today = date.today()
        month_ago = today - timedelta(days=30)

        response = client.get(f"/api/quality/statistics/summary?start_date={month_ago}&end_date={today}")

        assert response.status_code == 200
        data = response.json()
        assert "start_date" in data
        assert "end_date" in data
        assert "total_units_inspected" in data

    def test_get_quality_statistics_with_filters(self, authenticated_client):
        """Test statistics with product/shift filters."""
        client, setup = authenticated_client
        product = setup["product"]
        today = date.today()
        month_ago = today - timedelta(days=30)

        response = client.get(
            f"/api/quality/statistics/summary?start_date={month_ago}&end_date={today}&product_id={product.product_id}"
        )

        assert response.status_code == 200


class TestPPMCalculation:
    """Tests for GET /api/quality/kpi/ppm endpoint."""

    def test_calculate_ppm_default_dates(self, authenticated_client):
        """Test PPM calculation with default dates."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/ppm")

        assert response.status_code == 200
        data = response.json()
        assert "ppm" in data
        assert "total_units_inspected" in data
        assert "total_defects" in data
        assert "defect_rate_percentage" in data
        assert "inference" in data

    def test_calculate_ppm_with_dates(self, authenticated_client):
        """Test PPM calculation with specific dates."""
        client, setup = authenticated_client
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(f"/api/quality/kpi/ppm?start_date={week_ago}&end_date={today}")

        assert response.status_code == 200
        data = response.json()
        assert data["start_date"] == str(week_ago)
        assert data["end_date"] == str(today)

    def test_calculate_ppm_with_product_filter(self, authenticated_client):
        """Test PPM calculation with product filter."""
        client, setup = authenticated_client
        product = setup["product"]

        response = client.get(f"/api/quality/kpi/ppm?product_id={product.product_id}")

        assert response.status_code == 200

    def test_calculate_ppm_inference_metadata(self, authenticated_client):
        """Test PPM includes inference metadata."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/ppm")

        assert response.status_code == 200
        data = response.json()
        assert "inference" in data
        inference = data["inference"]
        assert "is_estimated" in inference
        assert "confidence_score" in inference
        assert "inference_source" in inference


class TestDPMOCalculation:
    """Tests for GET /api/quality/kpi/dpmo endpoint."""

    def test_calculate_dpmo_success(self, authenticated_client):
        """Test DPMO calculation."""
        client, setup = authenticated_client
        product = setup["product"]
        shift = setup["shift"]
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(
            f"/api/quality/kpi/dpmo?"
            f"product_id={product.product_id}&"
            f"shift_id={shift.shift_id}&"
            f"start_date={week_ago}&"
            f"end_date={today}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "dpmo" in data
        assert "sigma_level" in data
        assert "total_units" in data
        assert "total_defects" in data
        assert "opportunities_per_unit" in data

    def test_calculate_dpmo_custom_opportunities(self, authenticated_client):
        """Test DPMO with custom opportunities per unit."""
        client, setup = authenticated_client
        product = setup["product"]
        shift = setup["shift"]
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(
            f"/api/quality/kpi/dpmo?"
            f"product_id={product.product_id}&"
            f"shift_id={shift.shift_id}&"
            f"start_date={week_ago}&"
            f"end_date={today}&"
            f"opportunities_per_unit=25"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["opportunities_per_unit"] == 25


class TestDPMOByPart:
    """Tests for GET /api/quality/kpi/dpmo-by-part endpoint."""

    def test_calculate_dpmo_by_part_default(self, authenticated_client):
        """Test DPMO by part with defaults."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/dpmo-by-part")

        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "calculation_timestamp" in data

    def test_calculate_dpmo_by_part_with_dates(self, authenticated_client):
        """Test DPMO by part with date range."""
        client, _ = authenticated_client
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(f"/api/quality/kpi/dpmo-by-part?start_date={week_ago}&end_date={today}")

        assert response.status_code == 200
        data = response.json()
        assert data["period"]["start_date"] == str(week_ago)


class TestFPYRTYCalculation:
    """Tests for GET /api/quality/kpi/fpy-rty endpoint."""

    def test_calculate_fpy_rty_default(self, authenticated_client):
        """Test FPY/RTY calculation with defaults."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/fpy-rty")

        assert response.status_code == 200
        data = response.json()
        assert "fpy_percentage" in data
        assert "rty_percentage" in data
        assert "total_units" in data
        assert "first_pass_good" in data
        assert "final_yield_percentage" in data

    def test_calculate_fpy_rty_with_dates(self, authenticated_client):
        """Test FPY/RTY with specific dates."""
        client, _ = authenticated_client
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(f"/api/quality/kpi/fpy-rty?start_date={week_ago}&end_date={today}")

        assert response.status_code == 200
        data = response.json()
        assert "inference" in data

    def test_calculate_fpy_rty_with_product(self, authenticated_client):
        """Test FPY/RTY with product filter."""
        client, setup = authenticated_client
        product = setup["product"]

        response = client.get(f"/api/quality/kpi/fpy-rty?product_id={product.product_id}")

        assert response.status_code == 200


class TestFPYRTYBreakdown:
    """Tests for GET /api/quality/kpi/fpy-rty-breakdown endpoint."""

    def test_get_fpy_rty_breakdown_default(self, authenticated_client):
        """Test FPY/RTY breakdown with defaults."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/fpy-rty-breakdown")

        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "fpy_breakdown" in data
        assert "rty_breakdown" in data

    def test_get_fpy_rty_breakdown_with_stage(self, authenticated_client):
        """Test FPY/RTY breakdown with inspection stage filter."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/fpy-rty-breakdown?inspection_stage=incoming")

        assert response.status_code == 200
        data = response.json()
        assert data["inspection_stage_filter"] == "incoming"

    def test_get_fpy_rty_breakdown_structure(self, authenticated_client):
        """Test FPY/RTY breakdown response structure."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/fpy-rty-breakdown")

        assert response.status_code == 200
        data = response.json()

        fpy = data["fpy_breakdown"]
        assert "fpy_percentage" in fpy
        assert "rework_rate" in fpy
        assert "repair_rate" in fpy
        assert "scrap_rate" in fpy
        assert "recovery_rate" in fpy

        rty = data["rty_breakdown"]
        assert "rty_percentage" in rty
        assert "interpretation" in rty


class TestQualityScore:
    """Tests for GET /api/quality/kpi/quality-score endpoint."""

    def test_get_quality_score(self, authenticated_client):
        """Test quality score calculation."""
        client, setup = authenticated_client
        product = setup["product"]
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(
            f"/api/quality/kpi/quality-score?"
            f"product_id={product.product_id}&"
            f"start_date={week_ago}&"
            f"end_date={today}"
        )

        assert response.status_code == 200


class TestTopDefects:
    """Tests for GET /api/quality/kpi/top-defects endpoint."""

    def test_get_top_defects_default(self, authenticated_client):
        """Test top defects with defaults."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/top-defects")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    def test_get_top_defects_with_limit(self, authenticated_client):
        """Test top defects with custom limit."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/top-defects?limit=5")

        assert response.status_code == 200


class TestDefectsByType:
    """Tests for GET /api/quality/kpi/defects-by-type endpoint."""

    def test_get_defects_by_type_default(self, authenticated_client):
        """Test defects by type with defaults."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/defects-by-type")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_defects_by_type_with_dates(self, authenticated_client):
        """Test defects by type with date range."""
        client, _ = authenticated_client
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(f"/api/quality/kpi/defects-by-type?start_date={week_ago}&end_date={today}")

        assert response.status_code == 200


class TestQualityByProduct:
    """Tests for GET /api/quality/kpi/by-product endpoint."""

    def test_get_quality_by_product_default(self, authenticated_client):
        """Test quality by product with defaults."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/by-product")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_quality_by_product_with_limit(self, authenticated_client):
        """Test quality by product with custom limit."""
        client, _ = authenticated_client

        response = client.get("/api/quality/kpi/by-product?limit=5")

        assert response.status_code == 200


class TestQualityByWorkOrder:
    """Tests for GET /api/quality/by-work-order/{work_order_id} endpoint."""

    def test_get_quality_by_work_order_empty(self, authenticated_client):
        """Test getting quality by non-existent work order returns empty."""
        client, _ = authenticated_client

        response = client.get("/api/quality/by-work-order/WO-NONEXISTENT")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestAdminAccess:
    """Tests for admin-specific quality access."""

    def test_admin_sees_all_clients(self, admin_client):
        """Test admin can see all client data."""
        client, _ = admin_client

        response = client.get("/api/quality")

        assert response.status_code == 200

    def test_admin_statistics_all_clients(self, admin_client):
        """Test admin can get statistics for all clients."""
        client, _ = admin_client
        today = date.today()
        month_ago = today - timedelta(days=30)

        response = client.get(f"/api/quality/statistics/summary?start_date={month_ago}&end_date={today}")

        assert response.status_code == 200
