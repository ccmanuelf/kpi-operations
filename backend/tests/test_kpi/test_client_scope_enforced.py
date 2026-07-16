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
