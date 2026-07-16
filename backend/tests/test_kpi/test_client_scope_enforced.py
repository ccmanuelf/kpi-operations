import pytest
from fastapi.testclient import TestClient
from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.main import app


@pytest.fixture
def _bind(transactional_db):
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


def _as(user):
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_operator_cannot_read_other_clients_trend(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/efficiency/trend", params={"client_id": "CLIENT-B"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_can_read_own_trend(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/efficiency/trend", params={"client_id": "CLIENT-A"})
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_narrow_to_any_client(_bind, admin_user):
    c = _as(admin_user)
    try:
        r = c.get("/api/kpi/efficiency/trend", params={"client_id": "CLIENT-B"})
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_cause(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert (
            c.get("/api/kpi/availability/cause", params={"date": "2026-07-14", "client_id": "CLIENT-B"}).status_code
            == 403
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_efficiency_by_shift(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi/efficiency/by-shift", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_dashboard(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi/dashboard/aggregated", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_defects(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/quality/kpi/defects-by-type", params={"client_id": "CLIENT-B"}).status_code == 403
        assert c.get("/api/quality/kpi/top-defects", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_multi_client_leader_dashboard_quality_not_degraded(_bind, leader_user_multi_client):
    # A multi-client leader with no client_id must not trip the ClientConfig
    # gate into raising HTTPException(400) (which was swallowed and degraded
    # the quality section to a zeroed "Calculation error" payload).
    c = _as(leader_user_multi_client)
    try:
        r = c.get("/api/kpi/dashboard/aggregated")
        assert r.status_code == 200
        quality = r.json()["quality"]
        assert "error" not in quality
        assert quality["opportunities_per_unit"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)
