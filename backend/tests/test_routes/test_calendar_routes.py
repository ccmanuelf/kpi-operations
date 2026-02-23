"""
Operational Calendar API Route Tests

Tests the read-only /api/calendar endpoints that expose CapacityCalendar
data for operational KPI context.

Uses real in-memory SQLite database -- NO mocks for DB layer.
"""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.orm import ClientType
from backend.auth.jwt import get_current_user
from backend.orm.user import User, UserRole
from backend.orm.capacity.calendar import CapacityCalendar
from backend.routes.calendar import router as calendar_router
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test App Factory and Fixtures
# =============================================================================

CLIENT_ID = "CAL-TEST-CLIENT"


def create_test_app(db_session):
    """Create a minimal FastAPI app with the calendar router and overridden deps."""
    app = FastAPI()
    app.include_router(calendar_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    mock_user = User(
        user_id="test-cal-admin-001",
        username="cal_test_admin",
        email="cal_admin@test.com",
        role=UserRole.ADMIN.value,
        client_id_assigned=None,
        is_active=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return app


@pytest.fixture(scope="function")
def cal_db():
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
def cal_client(cal_db):
    """Create test client entity in the database and return (TestClient, db)."""
    db = cal_db
    TestDataFactory.create_client(
        db,
        client_id=CLIENT_ID,
        client_name="Calendar Test Client",
        client_type=ClientType.HOURLY_RATE,
    )
    db.commit()

    app = create_test_app(db)
    return TestClient(app), db


# =============================================================================
# Helper: Seed calendar entries
# =============================================================================


def _seed_calendar_entries(db):
    """Seed a mix of working days, a holiday, and a non-working day."""
    entries = [
        CapacityCalendar(
            client_id=CLIENT_ID,
            calendar_date=date(2026, 3, 2),
            is_working_day=True,
            shifts_available=2,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=0,
            holiday_name=None,
            notes="Monday",
        ),
        CapacityCalendar(
            client_id=CLIENT_ID,
            calendar_date=date(2026, 3, 3),
            is_working_day=True,
            shifts_available=1,
            shift1_hours=8.0,
            shift2_hours=0,
            shift3_hours=0,
            holiday_name=None,
            notes="Tuesday",
        ),
        CapacityCalendar(
            client_id=CLIENT_ID,
            calendar_date=date(2026, 3, 4),
            is_working_day=False,
            shifts_available=0,
            shift1_hours=0,
            shift2_hours=0,
            shift3_hours=0,
            holiday_name="National Holiday",
            notes=None,
        ),
        CapacityCalendar(
            client_id=CLIENT_ID,
            calendar_date=date(2026, 3, 5),
            is_working_day=True,
            shifts_available=3,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=6.0,
            holiday_name=None,
            notes="Thursday - triple shift",
        ),
    ]
    for e in entries:
        db.add(e)
    db.commit()
    return entries


# =============================================================================
# GET /api/calendar/working-days
# =============================================================================


class TestGetWorkingDays:
    """Tests for the working-days endpoint."""

    def test_returns_all_entries_in_range(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/working-days",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2026-03-02",
                "end_date": "2026-03-05",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4

    def test_working_day_fields(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/working-days",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2026-03-02",
                "end_date": "2026-03-02",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        day = data[0]
        assert day["calendar_date"] == "2026-03-02"
        assert day["is_working_day"] is True
        assert day["holiday_name"] is None
        assert day["shifts_available"] == 2
        assert day["planned_hours"] == 16.0

    def test_holiday_entry_fields(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/working-days",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2026-03-04",
                "end_date": "2026-03-04",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        day = data[0]
        assert day["is_working_day"] is False
        assert day["holiday_name"] == "National Holiday"
        assert day["planned_hours"] == 0.0

    def test_empty_range_returns_empty_list(self, cal_client):
        """When no calendar data exists for the range, return [] not 404."""
        client, db = cal_client

        resp = client.get(
            "/api/calendar/working-days",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2030-01-01",
                "end_date": "2030-01-31",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_triple_shift_planned_hours(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/working-days",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2026-03-05",
                "end_date": "2026-03-05",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["planned_hours"] == 22.0  # 8 + 8 + 6

    def test_partial_range_returns_subset(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/working-days",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2026-03-03",
                "end_date": "2026-03-04",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["calendar_date"] == "2026-03-03"
        assert data[1]["calendar_date"] == "2026-03-04"


# =============================================================================
# GET /api/calendar/summary
# =============================================================================


class TestGetSummary:
    """Tests for the summary endpoint."""

    def test_summary_counts(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/summary",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2026-03-02",
                "end_date": "2026-03-05",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_days"] == 4
        assert data["working_days"] == 3
        assert data["non_working_days"] == 1

    def test_summary_holidays(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/summary",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2026-03-02",
                "end_date": "2026-03-05",
            },
        )
        data = resp.json()

        assert len(data["holidays"]) == 1
        assert data["holidays"][0]["holiday_date"] == "2026-03-04"
        assert data["holidays"][0]["name"] == "National Holiday"

    def test_summary_total_planned_hours(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/summary",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2026-03-02",
                "end_date": "2026-03-05",
            },
        )
        data = resp.json()

        # Mon 16 + Tue 8 + Wed(holiday) 0 + Thu 22 = 46
        assert data["total_planned_hours"] == 46.0

    def test_summary_empty_range(self, cal_client):
        client, db = cal_client

        resp = client.get(
            "/api/calendar/summary",
            params={
                "client_id": CLIENT_ID,
                "start_date": "2030-06-01",
                "end_date": "2030-06-30",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_days"] == 0
        assert data["working_days"] == 0
        assert data["non_working_days"] == 0
        assert data["holidays"] == []
        assert data["total_planned_hours"] == 0.0


# =============================================================================
# GET /api/calendar/{calendar_date}
# =============================================================================


class TestGetSingleDay:
    """Tests for the single-day detail endpoint."""

    def test_returns_single_working_day(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/2026-03-02",
            params={"client_id": CLIENT_ID},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["calendar_date"] == "2026-03-02"
        assert data["is_working_day"] is True
        assert data["holiday_name"] is None
        assert data["shifts_available"] == 2
        assert data["planned_hours"] == 16.0
        assert data["shift1_hours"] == 8.0
        assert data["shift2_hours"] == 8.0
        assert data["shift3_hours"] == 0.0
        assert data["notes"] == "Monday"

    def test_returns_holiday(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/2026-03-04",
            params={"client_id": CLIENT_ID},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["is_working_day"] is False
        assert data["holiday_name"] == "National Holiday"
        assert data["planned_hours"] == 0.0

    def test_returns_404_for_missing_date(self, cal_client):
        """A date with no calendar entry should return 404."""
        client, db = cal_client

        resp = client.get(
            "/api/calendar/2030-12-25",
            params={"client_id": CLIENT_ID},
        )
        assert resp.status_code == 404
        assert "No calendar entry found" in resp.json()["detail"]

    def test_triple_shift_detail(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        resp = client.get(
            "/api/calendar/2026-03-05",
            params={"client_id": CLIENT_ID},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["shifts_available"] == 3
        assert data["shift1_hours"] == 8.0
        assert data["shift2_hours"] == 8.0
        assert data["shift3_hours"] == 6.0
        assert data["planned_hours"] == 22.0
        assert data["notes"] == "Thursday - triple shift"


# =============================================================================
# Tenant Isolation
# =============================================================================


class TestTenantIsolation:
    """Verify that queries are scoped to the requested client_id."""

    def test_other_client_sees_empty(self, cal_client):
        """Data seeded for CAL-TEST-CLIENT must not appear for OTHER-CLIENT."""
        client, db = cal_client
        _seed_calendar_entries(db)

        # Create a second client so the FK constraint passes
        TestDataFactory.create_client(
            db,
            client_id="OTHER-CLIENT",
            client_name="Other Client",
            client_type=ClientType.HOURLY_RATE,
        )
        db.commit()

        resp = client.get(
            "/api/calendar/working-days",
            params={
                "client_id": "OTHER-CLIENT",
                "start_date": "2026-03-02",
                "end_date": "2026-03-05",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_single_day_404_for_other_client(self, cal_client):
        client, db = cal_client
        _seed_calendar_entries(db)

        TestDataFactory.create_client(
            db,
            client_id="OTHER-CLIENT-2",
            client_name="Other Client 2",
            client_type=ClientType.HOURLY_RATE,
        )
        db.commit()

        resp = client.get(
            "/api/calendar/2026-03-02",
            params={"client_id": "OTHER-CLIENT-2"},
        )
        assert resp.status_code == 404
