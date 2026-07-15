"""
Tests for the PPM and Throughput-Time daily-trend endpoints (Diagnostic KPI
Charts SP1, Tasks 1-2).

GET /api/quality/kpi/ppm/trend — daily PPM defect-rate series, grouped by
day, mirroring the point /api/quality/kpi/ppm endpoint's client-filter and
date-default logic.

GET /api/kpi/throughput-time/trend — daily average throughput hours,
mirroring the frontend's per-point formula:
min(24, (Σrun_time_hours / Σunits_produced) * 100).

Isolation follows the D3/#130 pattern used by
`tests/test_routes/test_simulation_scenarios.py`: `transactional_db` is
bound to `get_db` so writes land in the function-scoped in-memory SQLite,
and `get_current_user` is overridden with a real admin `User` row (the
endpoint reads `current_user.role` / `current_user.client_id_assigned`
directly, so a DB-backed row — not just a bearer token — is what's
exercised).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.factories import TestDataFactory
from backend.main import app


@pytest.fixture
def db_session(transactional_db):
    """Bind get_db to the isolated in-memory session for this test."""
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(db_session):
    """TestClient authenticated as an admin, bound to db_session."""
    admin = TestDataFactory.create_user(db_session, username="trend_admin", role="admin")
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def _admin(db_session):
    from backend.orm import User

    return db_session.query(User).filter_by(role="admin").first()


def test_ppm_trend_returns_daily_series(client, db_session):
    admin = _admin(db_session)
    TestDataFactory.create_client(db_session, client_id="PPM-T")
    wo = TestDataFactory.create_work_order(db_session, client_id="PPM-T")
    day = date(2026, 6, 15)
    # 2 quality entries same day: 500 inspected, 5 defective each ->
    # 1000 inspected, 10 defective total -> 10000 ppm
    for _ in range(2):
        TestDataFactory.create_quality_entry(
            db_session,
            work_order_id=wo.work_order_id,
            client_id="PPM-T",
            inspector_id=admin.user_id,
            inspection_date=day,
            units_inspected=500,
            units_defective=5,
        )
    db_session.commit()
    r = client.get(
        "/api/quality/kpi/ppm/trend",
        params={"start_date": "2026-06-14", "end_date": "2026-06-16", "client_id": "PPM-T"},
    )
    assert r.status_code == 200
    rows = r.json()
    hit = [row for row in rows if row["date"] == "2026-06-15"]
    assert len(hit) == 1
    assert abs(hit[0]["value"] - 10000.0) < 1.0


def test_ppm_trend_empty_range_is_empty_list(client, db_session):
    r = client.get(
        "/api/quality/kpi/ppm/trend",
        params={"start_date": "2026-01-01", "end_date": "2026-01-02", "client_id": "NOPE"},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_throughput_trend_returns_daily_series(client, db_session):
    admin = _admin(db_session)
    TestDataFactory.create_client(db_session, client_id="TP-T")
    product = TestDataFactory.create_product(db_session, client_id="TP-T")
    shift = TestDataFactory.create_shift(db_session, client_id="TP-T")
    day = date(2026, 6, 15)
    # 100 units, 8 run hours -> (8/100)*100 = 8.0h
    TestDataFactory.create_production_entry(
        db_session,
        client_id="TP-T",
        product_id=product.product_id,
        shift_id=shift.shift_id,
        entered_by=admin.user_id,
        production_date=day,
        units_produced=100,
        run_time_hours=Decimal("8.0"),
    )
    db_session.commit()
    r = client.get(
        "/api/kpi/throughput-time/trend",
        params={"start_date": "2026-06-14", "end_date": "2026-06-16", "client_id": "TP-T"},
    )
    assert r.status_code == 200
    hit = [row for row in r.json() if row["date"] == "2026-06-15"]
    assert len(hit) == 1
    assert abs(hit[0]["value"] - 8.0) < 0.01


def test_throughput_trend_rejects_reversed_range(client, db_session):
    r = client.get(
        "/api/kpi/throughput-time/trend",
        params={"start_date": "2026-06-16", "end_date": "2026-06-14"},
    )
    assert r.status_code == 400


def test_throughput_trend_caps_at_24(client, db_session):
    admin = _admin(db_session)
    TestDataFactory.create_client(db_session, client_id="TP-CAP")
    product = TestDataFactory.create_product(db_session, client_id="TP-CAP")
    shift = TestDataFactory.create_shift(db_session, client_id="TP-CAP")
    TestDataFactory.create_production_entry(
        db_session,
        client_id="TP-CAP",
        product_id=product.product_id,
        shift_id=shift.shift_id,
        entered_by=admin.user_id,
        production_date=date(2026, 6, 15),
        units_produced=1,
        run_time_hours=Decimal("50.0"),  # (50/1)*100 = 5000 -> capped 24
    )
    db_session.commit()
    r = client.get(
        "/api/kpi/throughput-time/trend",
        params={"start_date": "2026-06-14", "end_date": "2026-06-16", "client_id": "TP-CAP"},
    )
    assert r.status_code == 200
    hit = [row for row in r.json() if row["date"] == "2026-06-15"]
    assert hit and hit[0]["value"] == 24.0
