"""Route tests for /api/pivot (Cycle 4 PR-A): shape, 422 allow-lists, scope
enforcement, CSV parity, JSON-number wire types.

Harness note: the task brief pointed at test_attendance_labor_capture.py for
the TestClient/auth pattern, but that file's `labor_setup` fixture uses a
real JWT (create_test_token) and has no two-client 403 scenario at all.
test_labor_hours_kpi.py (Cycle 3 PR-B) is the actual structural match: it
tests the sibling GET /api/kpi/labor-hours route, which composes the exact
same get_current_user / resolve_client_scope dependencies the pivot routes
reuse verbatim, and it already has the 401 + scoped-403 coverage this file
needs. This file mirrors ITS harness: fresh DB per test via
clone_template_engine (Alembic-schema-only template, no demo data) +
TestDataFactory, auth via app.dependency_overrides[get_current_user] (no
real JWT needed for route-shape/scope tests).
"""

import csv
import io
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database import get_db
from backend.routes.pivot import router as pivot_router
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.factories import TestDataFactory


def _create_test_app(db_session):
    """Create a FastAPI test app with overridden dependencies (no auth override --
    callers add app.dependency_overrides[get_current_user] themselves, or don't,
    to exercise the 401 path)."""
    app = FastAPI()
    app.include_router(pivot_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def pivot_db():
    """Fresh database for each test."""
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


def _authed_client(db, user):
    from backend.auth.jwt import get_current_user

    app = _create_test_app(db)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def admin_client(pivot_db):
    admin = TestDataFactory.create_user(
        pivot_db, user_id="pvt-admin-001", username="pvt_admin", role="admin", client_id=None
    )
    pivot_db.commit()
    return _authed_client(pivot_db, admin)


def test_pivot_labor_month_200_shape(admin_client):
    r = admin_client.get(
        "/api/pivot/labor",
        params={"bucket": "month", "start_date": "2025-01-01", "end_date": "2026-12-31"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dataset"] == "labor"
    assert body["bucket"] == "month"
    assert set(body) >= {"dataset", "bucket", "group_by", "rows", "totals"}
    for row in body["rows"]:
        assert isinstance(row["bucket_start"], str)
        for k, v in row.items():
            if k not in ("bucket_start", "group_key"):
                assert v is None or isinstance(v, (int, float)), (k, type(v))


def test_unknown_dataset_422(admin_client):
    r = admin_client.get(
        "/api/pivot/nope",
        params={"bucket": "month", "start_date": "2026-01-01", "end_date": "2026-02-01"},
    )
    assert r.status_code == 422


def test_unknown_bucket_422(admin_client):
    r = admin_client.get(
        "/api/pivot/production",
        params={"bucket": "fortnight", "start_date": "2026-01-01", "end_date": "2026-02-01"},
    )
    assert r.status_code == 422


def test_unknown_group_by_422_names_allow_list(admin_client):
    r = admin_client.get(
        "/api/pivot/production",
        params={
            "bucket": "month",
            "group_by": "nope",
            "start_date": "2026-01-01",
            "end_date": "2026-02-01",
        },
    )
    assert r.status_code == 422
    assert "group_by" in r.text


def test_unauthenticated_401(pivot_db):
    app = _create_test_app(pivot_db)
    client = TestClient(app)
    r = client.get(
        "/api/pivot/production",
        params={"bucket": "month", "start_date": "2026-01-01", "end_date": "2026-02-01"},
    )
    assert r.status_code == 401


def test_scoped_user_cannot_read_other_client(pivot_db):
    """A scoped (single-client) non-admin user explicitly requesting a
    client_id they aren't assigned to must get 403 from resolve_client_scope
    -- mirrors test_labor_hours_kpi.py::test_operator_foreign_client_id_is_403."""
    own_client = TestDataFactory.create_client(pivot_db, client_id="PVT-RT-OWN")
    foreign_client = TestDataFactory.create_client(pivot_db, client_id="PVT-RT-FOREIGN")
    operator = TestDataFactory.create_user(
        pivot_db,
        user_id="pvt-operator-001",
        username="pvt_operator",
        role="operator",
        client_id=own_client.client_id,
    )
    pivot_db.commit()

    client = _authed_client(pivot_db, operator)
    r = client.get(
        "/api/pivot/production",
        params={
            "bucket": "month",
            "client_id": foreign_client.client_id,
            "start_date": "2026-01-01",
            "end_date": "2026-02-01",
        },
    )
    assert r.status_code == 403


def test_csv_matches_json_rows(admin_client, pivot_db):
    """Seeds real downtime rows (the prior version of this test ran over an
    empty DB, so writer.writerow never executed). Both entries carry
    duration_minutes=0 -- deliberately, so the window's total downtime_hours
    is 0 and share_of_window_pct's zero-denominator rule fires (None in
    JSON), letting the same two rows also pin the None-ratio -> empty-cell
    CSV serialization alongside the plain value round-trip."""
    client = TestDataFactory.create_client(pivot_db, client_id="PVT-RT-CSV")
    pivot_db.commit()
    TestDataFactory.create_downtime_entry(
        pivot_db,
        client_id=client.client_id,
        reported_by="pvt-admin-001",
        shift_date=datetime(2025, 6, 15, 6),
        duration_minutes=0,
    )
    TestDataFactory.create_downtime_entry(
        pivot_db,
        client_id=client.client_id,
        reported_by="pvt-admin-001",
        shift_date=datetime(2026, 6, 15, 6),
        duration_minutes=0,
    )
    pivot_db.commit()

    params = {"bucket": "year", "start_date": "2025-01-01", "end_date": "2026-12-31"}
    j = admin_client.get("/api/pivot/downtime", params=params).json()
    r = admin_client.get("/api/pivot/downtime/csv", params=params)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = [ln for ln in r.text.strip().splitlines() if ln]
    assert len(j["rows"]) == 2
    assert len(lines) == len(j["rows"]) + 1  # header + rows

    csv_rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(csv_rows) == 2
    for json_row, csv_row in zip(j["rows"], csv_rows):
        # Round-trip: the hours cell (a plain Sum component) matches JSON.
        assert float(csv_row["downtime_hours"]) == json_row["downtime_hours"] == 0.0
        assert json_row["events"] == 1
        # None ratio (window total downtime_hours == 0 -> share is None,
        # per the zero-denominator rule) serializes as an empty CSV cell,
        # not the literal string "None".
        assert json_row["share_of_window_pct"] is None
        assert csv_row["share_of_window_pct"] == ""
