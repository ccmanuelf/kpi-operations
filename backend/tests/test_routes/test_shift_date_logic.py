"""
Tests for Task 1.4: Shift Date Auto-Default + Midnight-Crossing Logic

Covers:
1. Pydantic model_validator: shift_date auto-defaults to production_date
2. POST /api/production without shift_date -> auto-defaulted
3. POST /api/production with explicit shift_date -> uses provided value
4. Midnight-crossing logic adjusts shift_date when server time is post-midnight
5. Backward compatibility: existing entries with both dates still work
"""

import pytest
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.schemas.production import ProductionEntryCreate
from backend.routes.production import router as production_router
from backend.orm import ClientType
from backend.tests.fixtures.factories import TestDataFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_test_app(db_session):
    """Create a minimal FastAPI app wired to production routes."""
    app = FastAPI()
    app.include_router(production_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def shift_date_db():
    """Fresh in-memory database per test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def shift_date_setup(shift_date_db):
    """Seed client, user, product, day-shift, and night-shift."""
    db = shift_date_db

    client = TestDataFactory.create_client(
        db,
        client_id="SHIFTDATE-CLIENT",
        client_name="Shift Date Test Client",
        client_type=ClientType.HOURLY_RATE,
    )

    supervisor = TestDataFactory.create_user(
        db,
        username="sd_supervisor",
        role="supervisor",
        client_id=client.client_id,
    )

    product = TestDataFactory.create_product(
        db,
        client_id=client.client_id,
        product_code="SD-PROD-001",
        product_name="Shift Date Test Product",
        ideal_cycle_time=Decimal("0.10"),
    )

    # Day shift: 06:00-14:00 (does NOT cross midnight)
    day_shift = TestDataFactory.create_shift(
        db,
        client_id=client.client_id,
        shift_name="Day Shift",
        start_time="06:00:00",
        end_time="14:00:00",
    )

    # Night shift: 22:00-06:00 (CROSSES midnight)
    night_shift = TestDataFactory.create_shift(
        db,
        client_id=client.client_id,
        shift_name="Night Shift",
        start_time="22:00:00",
        end_time="06:00:00",
    )

    db.commit()

    return {
        "db": db,
        "client": client,
        "supervisor": supervisor,
        "product": product,
        "day_shift": day_shift,
        "night_shift": night_shift,
    }


@pytest.fixture
def authenticated_sd_client(shift_date_setup):
    """Authenticated TestClient wired to the shift-date database."""
    db = shift_date_setup["db"]
    user = shift_date_setup["supervisor"]

    app = _create_test_app(db)

    from backend.auth.jwt import get_current_user, get_current_active_supervisor

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_active_supervisor] = lambda: user

    return TestClient(app), shift_date_setup


# ---------------------------------------------------------------------------
# 1. Pydantic model_validator tests
# ---------------------------------------------------------------------------


class TestShiftDateModelValidator:
    """Verify that the model_validator defaults shift_date to production_date."""

    def test_shift_date_defaults_to_production_date_when_absent(self):
        """shift_date should equal production_date when not provided."""
        entry = ProductionEntryCreate(
            client_id="TEST-CLIENT",
            product_id=1,
            shift_id=1,
            production_date=date(2026, 1, 15),
            # shift_date intentionally omitted
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
        )
        assert entry.shift_date == date(2026, 1, 15)

    def test_shift_date_defaults_when_none(self):
        """Explicitly passing shift_date=None should still default."""
        entry = ProductionEntryCreate(
            client_id="TEST-CLIENT",
            product_id=1,
            shift_id=1,
            production_date=date(2026, 3, 10),
            shift_date=None,
            units_produced=200,
            run_time_hours=Decimal("6.5"),
            employees_assigned=4,
        )
        assert entry.shift_date == date(2026, 3, 10)

    def test_explicit_shift_date_preserved(self):
        """When shift_date is explicitly provided, it must be kept as-is."""
        entry = ProductionEntryCreate(
            client_id="TEST-CLIENT",
            product_id=1,
            shift_id=1,
            production_date=date(2026, 1, 16),
            shift_date=date(2026, 1, 15),  # Explicit — different from production_date
            units_produced=150,
            run_time_hours=Decimal("7.0"),
            employees_assigned=3,
        )
        assert entry.shift_date == date(2026, 1, 15)

    def test_from_legacy_csv_still_works(self):
        """Existing from_legacy_csv path must remain backward-compatible."""
        csv_data = {
            "client_id": "TEST-CLIENT",
            "product_id": 1,
            "shift_id": 1,
            "production_date": date(2026, 2, 20),
            "shift_date": None,  # CSV sometimes passes None
            "units_produced": 300,
            "run_time_hours": "8.0",
            "employees_assigned": 5,
        }
        entry = ProductionEntryCreate.from_legacy_csv(csv_data)
        assert entry.shift_date == date(2026, 2, 20)


# ---------------------------------------------------------------------------
# 2. Route-level tests: auto-default via POST
# ---------------------------------------------------------------------------


class TestCreateEntryShiftDateAutoDefault:
    """POST /api/production without shift_date should auto-default it."""

    def test_post_without_shift_date_auto_defaults(self, authenticated_sd_client):
        """Omitting shift_date in the JSON body should default to production_date."""
        client, setup = authenticated_sd_client
        today = str(date.today())

        response = client.post(
            "/api/production",
            json={
                "client_id": setup["client"].client_id,
                "product_id": setup["product"].product_id,
                "shift_id": setup["day_shift"].shift_id,
                "production_date": today,
                # shift_date intentionally omitted
                "units_produced": 250,
                "run_time_hours": "8.0",
                "employees_assigned": 5,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        # shift_date should match production_date
        assert data["shift_date"].startswith(today)

    def test_post_with_explicit_shift_date(self, authenticated_sd_client):
        """Providing an explicit shift_date should use that value unchanged."""
        client, setup = authenticated_sd_client
        prod_date = "2026-02-20"
        shift_date = "2026-02-19"

        response = client.post(
            "/api/production",
            json={
                "client_id": setup["client"].client_id,
                "product_id": setup["product"].product_id,
                "shift_id": setup["day_shift"].shift_id,
                "production_date": prod_date,
                "shift_date": shift_date,
                "units_produced": 300,
                "run_time_hours": "7.5",
                "employees_assigned": 4,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["shift_date"].startswith(shift_date)


# ---------------------------------------------------------------------------
# 3. Route-level tests: midnight-crossing logic
# ---------------------------------------------------------------------------


class TestMidnightCrossingLogic:
    """Midnight-crossing heuristic for night shifts that span two calendar dates."""

    @patch("backend.routes.production.datetime")
    def test_night_shift_post_midnight_adjusts_shift_date(self, mock_datetime, authenticated_sd_client):
        """
        When server time is 02:00 UTC (between midnight and end_time 06:00),
        and the shift crosses midnight, shift_date should be set to
        production_date - 1 day.
        """
        client, setup = authenticated_sd_client

        # Simulate server time at 02:00 UTC (post-midnight, within night shift)
        simulated_now = datetime(2026, 1, 6, 2, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = simulated_now
        # Ensure datetime.now(tz=...) works via side_effect approach is unnecessary;
        # the mock replaces .now() which is what the route calls.

        prod_date = "2026-01-06"

        response = client.post(
            "/api/production",
            json={
                "client_id": setup["client"].client_id,
                "product_id": setup["product"].product_id,
                "shift_id": setup["night_shift"].shift_id,
                "production_date": prod_date,
                # shift_date omitted -> defaults to production_date, then midnight logic kicks in
                "units_produced": 180,
                "run_time_hours": "8.0",
                "employees_assigned": 6,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        # shift_date should be adjusted to 2026-01-05 (previous day)
        assert data["shift_date"].startswith("2026-01-05")

    @patch("backend.routes.production.datetime")
    def test_night_shift_before_midnight_no_adjustment(self, mock_datetime, authenticated_sd_client):
        """
        When server time is 23:00 UTC (before midnight, at the start of the
        night shift), shift_date should NOT be adjusted.
        """
        client, setup = authenticated_sd_client

        # Simulate server time at 23:00 UTC (before midnight)
        simulated_now = datetime(2026, 1, 5, 23, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = simulated_now

        prod_date = "2026-01-05"

        response = client.post(
            "/api/production",
            json={
                "client_id": setup["client"].client_id,
                "product_id": setup["product"].product_id,
                "shift_id": setup["night_shift"].shift_id,
                "production_date": prod_date,
                "units_produced": 200,
                "run_time_hours": "8.0",
                "employees_assigned": 5,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        # No adjustment — shift_date stays as production_date
        assert data["shift_date"].startswith("2026-01-05")

    def test_day_shift_no_midnight_crossing(self, authenticated_sd_client):
        """Day shift (no midnight crossing) should never adjust shift_date."""
        client, setup = authenticated_sd_client
        prod_date = "2026-02-20"

        response = client.post(
            "/api/production",
            json={
                "client_id": setup["client"].client_id,
                "product_id": setup["product"].product_id,
                "shift_id": setup["day_shift"].shift_id,
                "production_date": prod_date,
                "units_produced": 400,
                "run_time_hours": "8.0",
                "employees_assigned": 5,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        # shift_date should equal production_date (no midnight crossing)
        assert data["shift_date"].startswith(prod_date)

    @patch("backend.routes.production.datetime")
    def test_explicit_shift_date_overrides_midnight_logic(self, mock_datetime, authenticated_sd_client):
        """
        When shift_date is explicitly provided and differs from production_date,
        midnight-crossing logic should NOT override it.
        """
        client, setup = authenticated_sd_client

        # Simulate post-midnight time
        simulated_now = datetime(2026, 1, 6, 3, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = simulated_now

        response = client.post(
            "/api/production",
            json={
                "client_id": setup["client"].client_id,
                "product_id": setup["product"].product_id,
                "shift_id": setup["night_shift"].shift_id,
                "production_date": "2026-01-06",
                "shift_date": "2026-01-04",  # Explicit override
                "units_produced": 150,
                "run_time_hours": "7.0",
                "employees_assigned": 4,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        # Explicit shift_date should be preserved (not overridden by midnight logic)
        assert data["shift_date"].startswith("2026-01-04")


# ---------------------------------------------------------------------------
# 4. Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Ensure existing callers that provide both dates continue to work."""

    def test_both_dates_provided_same_value(self, authenticated_sd_client):
        """Providing production_date == shift_date should just work."""
        client, setup = authenticated_sd_client
        today = str(date.today())

        response = client.post(
            "/api/production",
            json={
                "client_id": setup["client"].client_id,
                "product_id": setup["product"].product_id,
                "shift_id": setup["day_shift"].shift_id,
                "production_date": today,
                "shift_date": today,
                "units_produced": 500,
                "run_time_hours": "8.0",
                "employees_assigned": 5,
                "defect_count": 2,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["units_produced"] == 500
        assert data["shift_date"].startswith(today)

    def test_both_dates_provided_different_values(self, authenticated_sd_client):
        """production_date != shift_date should be preserved."""
        client, setup = authenticated_sd_client

        response = client.post(
            "/api/production",
            json={
                "client_id": setup["client"].client_id,
                "product_id": setup["product"].product_id,
                "shift_id": setup["day_shift"].shift_id,
                "production_date": "2026-02-22",
                "shift_date": "2026-02-21",
                "units_produced": 350,
                "run_time_hours": "7.5",
                "employees_assigned": 4,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["shift_date"].startswith("2026-02-21")
