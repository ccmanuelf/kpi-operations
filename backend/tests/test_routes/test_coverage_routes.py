"""Shift coverage write paths, which were entirely untested.

`create_shift_coverage`, the mutation body of `update_shift_coverage` and both
date-range filter branches never executed anywhere in the suite — the endpoints
existed, the read path had some coverage, and every write was dead code in
test. These pin the four defects that survived that gap:

  * a percentage that overflows the column it is stored in, which SQLite
    accepts and MariaDB rejects,
  * two contradictory coverage records for the same client, date and shift,
  * a coverage row pointing at another tenant's shift, and
  * a response with no client_id, which a multi-client reader cannot attribute.
"""

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.auth.jwt import get_current_active_supervisor, get_current_contributor, get_current_user
from backend.crud.coverage import MAX_COVERAGE_PERCENTAGE
from backend.database import get_db
from backend.orm import ClientType
from backend.routes.coverage import router as coverage_router
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.factories import TestDataFactory

COVERAGE_DATE = date(2026, 5, 12)


@pytest.fixture(scope="function")
def cov_db():
    engine = clone_template_engine()
    session = sessionmaker(bind=engine)()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture
def setup(cov_db):
    """Two tenants, so the cross-tenant checks are not vacuous."""
    db = cov_db
    client_a = TestDataFactory.create_client(
        db, client_id="COV-A", client_name="Coverage A", client_type=ClientType.HOURLY_RATE
    )
    client_b = TestDataFactory.create_client(
        db, client_id="COV-B", client_name="Coverage B", client_type=ClientType.HOURLY_RATE
    )
    admin = TestDataFactory.create_user(db, user_id="cov-admin", username="cov_admin", role="admin", client_id=None)
    operator = TestDataFactory.create_user(
        db, user_id="cov-op", username="cov_op", role="operator", client_id=client_a.client_id
    )
    shift_a = TestDataFactory.create_shift(
        db, client_id=client_a.client_id, shift_name="A day", start_time="06:00:00", end_time="14:00:00"
    )
    shift_b = TestDataFactory.create_shift(
        db, client_id=client_b.client_id, shift_name="B day", start_time="06:00:00", end_time="14:00:00"
    )
    db.commit()
    return {
        "db": db,
        "client_a": client_a,
        "client_b": client_b,
        "admin": admin,
        "operator": operator,
        "shift_a": shift_a,
        "shift_b": shift_b,
    }


def _client_for(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(coverage_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_contributor] = lambda: user
    app.dependency_overrides[get_current_active_supervisor] = lambda: user
    return TestClient(app)


def _body(setup, **over):
    payload = {
        "client_id": setup["client_a"].client_id,
        "shift_id": setup["shift_a"].shift_id,
        "coverage_date": COVERAGE_DATE.isoformat(),
        "required_employees": 8,
        "actual_employees": 8,
    }
    payload.update(over)
    return payload


class TestCreate:
    def test_creates_and_computes_the_percentage(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup, actual_employees=6))
        assert r.status_code == 201
        assert r.json()["coverage_percentage"] == 75.0

    def test_the_response_says_which_client_the_row_belongs_to(self, setup):
        """A leader assigned several clients gets their rows interleaved; with
        no client_id there is no field to attribute them by."""
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup))
        assert r.status_code == 201
        assert r.json()["client_id"] == setup["client_a"].client_id

    def test_an_overstaffed_shift_does_not_overflow_the_column(self, setup):
        """coverage_percentage is Numeric(5, 2): 999.99 is the ceiling.

        One required and fifty present computes 5000.00. SQLite stores that
        silently and MariaDB rejects it in strict mode, so without the clamp
        the whole suite passes and the write 500s in production.
        """
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup, required_employees=1, actual_employees=50))
        assert r.status_code == 201
        assert r.json()["coverage_percentage"] == float(MAX_COVERAGE_PERCENTAGE)

    def test_a_second_record_for_the_same_shift_and_day_is_refused(self, setup):
        """Two rows for one client, date and shift are two contradictory
        answers to the same question."""
        client = _client_for(setup["db"], setup["admin"])
        assert client.post("/api/coverage", json=_body(setup)).status_code == 201

        clash = client.post("/api/coverage", json=_body(setup, actual_employees=3))
        assert clash.status_code == 409
        assert "already exists" in clash.json()["detail"]

    def test_a_different_day_for_the_same_shift_is_fine(self, setup):
        """Two-sided: the guard must not block the next day's record."""
        client = _client_for(setup["db"], setup["admin"])
        assert client.post("/api/coverage", json=_body(setup)).status_code == 201
        nxt = _body(setup, coverage_date=(COVERAGE_DATE + timedelta(days=1)).isoformat())
        assert client.post("/api/coverage", json=nxt).status_code == 201

    def test_a_shift_belonging_to_another_tenant_is_refused(self, setup):
        """The FK only requires the shift to EXIST, so this satisfies every
        database on every dialect and is silently cross-tenant."""
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup, shift_id=setup["shift_b"].shift_id))
        assert r.status_code == 400
        assert "different client" in r.json()["detail"]

    def test_an_unknown_shift_is_refused(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup, shift_id=999999))
        assert r.status_code == 400


class TestUpdate:
    def test_recomputes_the_percentage(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        created = client.post("/api/coverage", json=_body(setup)).json()

        r = client.put(f"/api/coverage/{created['coverage_id']}", json={"actual_employees": 4})
        assert r.status_code == 200
        assert r.json()["coverage_percentage"] == 50.0

    def test_an_edit_cannot_overflow_the_column_either(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        created = client.post("/api/coverage", json=_body(setup)).json()

        r = client.put(
            f"/api/coverage/{created['coverage_id']}",
            json={"required_employees": 1, "actual_employees": 80},
        )
        assert r.status_code == 200
        assert r.json()["coverage_percentage"] == float(MAX_COVERAGE_PERCENTAGE)


class TestList:
    def test_narrows_to_a_date_range(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        client.post("/api/coverage", json=_body(setup))
        later = _body(setup, coverage_date=(COVERAGE_DATE + timedelta(days=10)).isoformat())
        client.post("/api/coverage", json=later)

        r = client.get(
            "/api/coverage",
            params={"start_date": COVERAGE_DATE.isoformat(), "end_date": COVERAGE_DATE.isoformat()},
        )
        assert r.status_code == 200
        assert [row["coverage_date"] for row in r.json()] == [COVERAGE_DATE.isoformat()]

    def test_narrows_to_one_client(self, setup):
        """The CRUD layer always accepted client_id; the route never offered
        it, so a multi-client reader could not narrow to one tenant."""
        client = _client_for(setup["db"], setup["admin"])
        client.post("/api/coverage", json=_body(setup))

        r = client.get("/api/coverage", params={"client_id": setup["client_a"].client_id})
        assert r.status_code == 200
        assert {row["client_id"] for row in r.json()} == {setup["client_a"].client_id}

        empty = client.get("/api/coverage", params={"client_id": setup["client_b"].client_id})
        assert empty.status_code == 200
        assert empty.json() == []

    def test_returns_more_than_a_hundred_rows(self, setup):
        """The old default of 100 silently truncated the 112 seeded rows, so a
        reader could not tell a short month from a clipped page."""
        client = _client_for(setup["db"], setup["admin"])
        for offset in range(105):
            client.post(
                "/api/coverage",
                json=_body(setup, coverage_date=(COVERAGE_DATE + timedelta(days=offset)).isoformat()),
            )

        r = client.get("/api/coverage")
        assert r.status_code == 200
        assert len(r.json()) == 105
