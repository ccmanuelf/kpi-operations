"""
Downtime availability KPI route test.

Task 4b (downtime-cause-taxonomy cycle) scope expansion: a full-repo grep for
the cast(<DateTime col>, Date) SQLite bug class -- the class this task
eradicates -- turned up one extra site not in the original 6-file/16-site
list: routes/downtime.py's aggregate /api/kpi/availability path used an
aliased import (`cast as sa_cast, Date as SADate`), which hides the pattern
from a naive grep but is the exact same bug. Fixed under the repo's
no-tech-debt rule (any class-eradication pass must actually eradicate the
whole class, not just the originally-listed instances).
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import get_db
from backend.orm import ClientType
from backend.routes.downtime import availability_router
from backend.tests.fixtures.factories import TestDataFactory
from backend.tests.conftest import clone_template_engine


def create_test_app(db_session):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(availability_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def downtime_db():
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
def downtime_setup(downtime_db):
    """Create standard test data for the availability KPI route test."""
    db = downtime_db

    client = TestDataFactory.create_client(
        db, client_id="DT-KPI-TEST", client_name="Downtime KPI Test Client", client_type=ClientType.HOURLY_RATE
    )
    supervisor = TestDataFactory.create_user(
        db, user_id="dt-kpi-super-001", username="dt_kpi_supervisor", role="supervisor", client_id=client.client_id
    )
    db.flush()
    db.commit()

    return {"db": db, "client": client, "supervisor": supervisor}


@pytest.fixture
def authenticated_client(downtime_setup):
    """Create an authenticated test client (resolve_client_scope resolves
    transitively through the overridden get_current_user, same as the
    attendance/quality/kpi route test suites)."""
    db = downtime_setup["db"]
    user = downtime_setup["supervisor"]
    app = create_test_app(db)

    from backend.auth.jwt import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user

    return TestClient(app), downtime_setup


class TestAvailabilityKpiAggregateShiftDateCastBug:
    """Real API-backed coverage for the aggregate branch of GET
    /api/kpi/availability (no work_order_id/target_date) in
    backend/routes/downtime.py.

    Before the fix, both filter predicates used
    sa_cast(DowntimeEntry.shift_date, SADate) -- an aliased import of
    sqlalchemy's cast()/Date -- which mangles on SQLite exactly like the
    unaliased form: numeric column affinity truncates
    CAST('2026-07-01 06:00:00' AS DATE) to just 2026, so a start_date/
    end_date of 2026-07-01 never matched, silently returning zero downtime
    and zero events. func.date(shift_date) is the portable fix.
    """

    def test_availability_kpi_aggregate_matches_shift_date_on_exact_day(self, authenticated_client):
        """The aggregate path must find the seeded downtime entry on the
        exact day, not silently return zero."""
        client, setup = authenticated_client
        db = setup["db"]

        TestDataFactory.create_downtime_entry(
            db,
            client_id=setup["client"].client_id,
            reported_by=setup["supervisor"].user_id,
            downtime_reason="EQUIPMENT_FAILURE",
            shift_date=datetime(2026, 7, 1, 6, 0),
            duration_minutes=90,
        )
        db.commit()

        response = client.get("/api/kpi/availability?start_date=2026-07-01&end_date=2026-07-01")

        assert response.status_code == 200
        data = response.json()
        # Derivation: scheduled = 8.0 * days(1) = 8.0hr; downtime = 90min/60 = 1.5hr;
        # availability = (8.0-1.5)/8.0*100 = 81.25%; one seeded entry -> downtime_events = 1.
        assert data["downtime_events"] == 1
        assert data["total_scheduled_hours"] == 8.0
        assert data["total_downtime_hours"] == 1.5
        assert data["availability_percentage"] == 81.25
