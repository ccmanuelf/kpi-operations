from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.factories import TestDataFactory
from backend.main import app
from backend.orm.downtime_entry import DowntimeEntry


@pytest.fixture
def db_session(transactional_db):
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(db_session):
    admin = TestDataFactory.create_user(db_session, username="cause_admin", role="admin")
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_availability_cause_returns_top_downtime(client, db_session):
    db_session.add(
        DowntimeEntry(
            downtime_entry_id="DT1",
            client_id="C1",
            shift_date=datetime(2026, 6, 10, 8),
            downtime_reason="Changeover",
            downtime_duration_minutes=60,
        )
    )
    db_session.commit()
    r = client.get("/api/kpi/availability/cause", params={"date": "2026-06-10", "client_id": "C1"})
    assert r.status_code == 200
    body = r.json()
    assert body["metric"] == "availability" and body["kind"] == "downtime"
    assert body["factor"] == "Changeover" and body["unit"] == "min"


def test_fallback_metric_returns_null_cause(client):
    r = client.get("/api/kpi/efficiency/cause", params={"date": "2026-06-10"})
    assert r.status_code == 200
    assert r.json() == {
        "date": "2026-06-10",
        "metric": "efficiency",
        "kind": None,
        "factor": None,
        "value": None,
        "unit": "",
        "share": None,
    }


def test_real_metric_no_data_returns_null_cause(client):
    r = client.get("/api/kpi/availability/cause", params={"date": "2026-06-10", "client_id": "C1"})
    assert r.status_code == 200 and r.json()["factor"] is None


def test_unknown_metric_422(client):
    r = client.get("/api/kpi/bogus/cause", params={"date": "2026-06-10"})
    assert r.status_code == 422


def test_missing_date_422(client):
    r = client.get("/api/kpi/availability/cause")
    assert r.status_code == 422
