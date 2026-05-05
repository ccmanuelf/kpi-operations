"""
Tests for D3 — SimulationScenario CRUD + run endpoints.

Coverage:
  - Create / list / get / update / delete (soft) / duplicate / run
  - Tenant isolation (operator vs leader vs admin)
  - Permission gate (operator denied on writes)
  - Validation: invalid stored config returns 422 on run
  - Roundtrip integrity (config_json preserved bit-exactly)
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.main import app


def _user(role: str, *, client_id_assigned: str | None = "ACME-MFG", username: str | None = None) -> MagicMock:
    """Helper for the dependency-override mock user. Real string fields
    matter where Pydantic serializes the user (e.g. /api/auth/me)."""
    u = MagicMock()
    u.role = role
    u.username = username or f"test_{role}"
    u.user_id = f"USER-TEST-{role.upper()}"
    u.client_id_assigned = client_id_assigned
    u.is_active = True
    u.email = f"{role}@test.local"
    u.full_name = role.title()
    return u


@pytest.fixture
def client():
    return TestClient(app)


def _override_user(client: TestClient, role: str, client_id_assigned: str | None = "ACME-MFG") -> TestClient:
    """Switch the dependency override on the SAME TestClient. Tests
    that need multiple personas in one flow use this rather than
    multiple fixtures (which collide because dependency_overrides is a
    single dict on the app instance)."""
    app.dependency_overrides[get_current_user] = lambda: _user(role, client_id_assigned=client_id_assigned)
    return client


@pytest.fixture
def shared_client():
    """One TestClient whose persona we switch within the test via
    `_override_user(client, role)`. Cleans up the override afterwards."""
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def admin_client(shared_client: TestClient) -> TestClient:
    return _override_user(shared_client, "admin", client_id_assigned=None)


@pytest.fixture
def leader_client(shared_client: TestClient) -> TestClient:
    return _override_user(shared_client, "leader", client_id_assigned="ACME-MFG")


@pytest.fixture
def operator_client(shared_client: TestClient) -> TestClient:
    return _override_user(shared_client, "operator", client_id_assigned="ACME-MFG")


@pytest.fixture
def cross_tenant_leader_client(shared_client: TestClient) -> TestClient:
    return _override_user(shared_client, "leader", client_id_assigned="TEXTILE-PRO")


def _sample_config() -> Dict[str, Any]:
    return {
        "operations": [
            {
                "product": "A",
                "step": 1,
                "operation": "Cut",
                "machine_tool": "M1",
                "sam_min": 1.0,
                "operators": 1,
            }
        ],
        "schedule": {
            "shifts_enabled": 1,
            "shift1_hours": 8,
            "work_days": 5,
            "ot_enabled": False,
        },
        "demands": [{"product": "A", "bundle_size": 10, "daily_demand": 100}],
        "mode": "demand-driven",
        "horizon_days": 1,
    }


# =============================================================================
# Auth & permission
# =============================================================================


def test_unauthenticated_listing_blocked(client: TestClient) -> None:
    response = client.get("/api/v2/simulation/scenarios")
    assert response.status_code == 401


def test_operator_can_list_but_not_create(operator_client: TestClient) -> None:
    """Operators read scenarios but cannot create them — they're data
    collectors, not planners."""
    list_resp = operator_client.get("/api/v2/simulation/scenarios")
    assert list_resp.status_code == 200

    create_resp = operator_client.post(
        "/api/v2/simulation/scenarios",
        json={
            "name": "operator-attempt",
            "client_id": "ACME-MFG",
            "config_json": _sample_config(),
        },
    )
    assert create_resp.status_code == 403


def test_operator_cannot_run_scenario(shared_client: TestClient) -> None:
    """Run is a write operation — operators should be 403'd."""
    # Leader creates
    _override_user(shared_client, "leader")
    create = shared_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "test-op-run", "client_id": "ACME-MFG", "config_json": _sample_config()},
    )
    assert create.status_code == 201
    scenario_id = create.json()["id"]

    # Operator attempts run
    _override_user(shared_client, "operator")
    run_resp = shared_client.post(f"/api/v2/simulation/scenarios/{scenario_id}/run")
    assert run_resp.status_code == 403

    # Leader cleanup
    _override_user(shared_client, "leader")
    shared_client.delete(f"/api/v2/simulation/scenarios/{scenario_id}")


# =============================================================================
# CRUD happy path
# =============================================================================


def test_create_list_get_roundtrip(leader_client: TestClient) -> None:
    config = _sample_config()
    create_resp = leader_client.post(
        "/api/v2/simulation/scenarios",
        json={
            "name": "roundtrip",
            "client_id": "ACME-MFG",
            "description": "Test",
            "config_json": config,
            "tags": ["unit-test"],
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    scenario_id = created["id"]
    assert created["name"] == "roundtrip"
    assert created["config_json"] == config  # exact roundtrip
    assert created["tags"] == ["unit-test"]
    assert created["is_active"] is True

    # Get returns full payload
    get_resp = leader_client.get(f"/api/v2/simulation/scenarios/{scenario_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["config_json"] == config

    # List returns the lightweight summary (no config_json key)
    list_resp = leader_client.get("/api/v2/simulation/scenarios")
    assert list_resp.status_code == 200
    summaries = list_resp.json()
    matching = [s for s in summaries if s["id"] == scenario_id]
    assert len(matching) == 1
    assert "config_json" not in matching[0]  # summary shape, not full
    assert matching[0]["name"] == "roundtrip"

    # Cleanup
    leader_client.delete(f"/api/v2/simulation/scenarios/{scenario_id}")


def test_update_partial_fields(leader_client: TestClient) -> None:
    create = leader_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "old-name", "client_id": "ACME-MFG", "config_json": _sample_config()},
    )
    sid = create.json()["id"]

    update = leader_client.put(
        f"/api/v2/simulation/scenarios/{sid}",
        json={"name": "new-name", "tags": ["renamed"]},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "new-name"
    assert update.json()["tags"] == ["renamed"]
    # Untouched fields remain
    assert update.json()["config_json"] == _sample_config()

    leader_client.delete(f"/api/v2/simulation/scenarios/{sid}")


def test_soft_delete_hides_from_default_list(leader_client: TestClient) -> None:
    create = leader_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "to-delete", "client_id": "ACME-MFG", "config_json": _sample_config()},
    )
    sid = create.json()["id"]

    delete = leader_client.delete(f"/api/v2/simulation/scenarios/{sid}")
    assert delete.status_code == 204

    # Default list (active only) excludes the soft-deleted scenario
    active = leader_client.get("/api/v2/simulation/scenarios")
    assert sid not in [s["id"] for s in active.json()]

    # include_inactive=True surfaces it
    all_ = leader_client.get("/api/v2/simulation/scenarios?include_inactive=true")
    assert sid in [s["id"] for s in all_.json()]


def test_duplicate_creates_new_record_with_optional_name(leader_client: TestClient) -> None:
    create = leader_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "src", "client_id": "ACME-MFG", "config_json": _sample_config()},
    )
    src_id = create.json()["id"]

    dup_resp = leader_client.post(f"/api/v2/simulation/scenarios/{src_id}/duplicate")
    assert dup_resp.status_code == 201
    dup = dup_resp.json()
    assert dup["id"] != src_id
    assert dup["name"] == "src (copy)"
    assert dup["config_json"] == _sample_config()

    # Custom name
    dup2_resp = leader_client.post(
        f"/api/v2/simulation/scenarios/{src_id}/duplicate?new_name=My%20Variant"
    )
    assert dup2_resp.status_code == 201
    assert dup2_resp.json()["name"] == "My Variant"

    # Cleanup
    for sid in (src_id, dup["id"], dup2_resp.json()["id"]):
        leader_client.delete(f"/api/v2/simulation/scenarios/{sid}")


def test_run_persists_summary(leader_client: TestClient) -> None:
    create = leader_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "run-test", "client_id": "ACME-MFG", "config_json": _sample_config()},
    )
    sid = create.json()["id"]
    assert create.json()["last_run_summary"] is None
    assert create.json()["last_run_at"] is None

    run = leader_client.post(f"/api/v2/simulation/scenarios/{sid}/run")
    assert run.status_code == 200
    body = run.json()
    summary = body["last_run_summary"]
    assert summary is not None
    assert summary["daily_throughput_pcs"] is not None
    assert summary["daily_coverage_pct"] is not None
    assert body["last_run_at"] is not None

    # Subsequent GET reflects the persisted summary
    get_resp = leader_client.get(f"/api/v2/simulation/scenarios/{sid}")
    assert get_resp.json()["last_run_summary"]["daily_throughput_pcs"] == summary["daily_throughput_pcs"]

    leader_client.delete(f"/api/v2/simulation/scenarios/{sid}")


def test_run_invalid_config_returns_422(leader_client: TestClient) -> None:
    """Saving an invalid config is allowed (engine version drift); the
    error surfaces only when the user tries to RUN it."""
    bad_config: Dict[str, Any] = {"operations": "this is not a list"}  # invalid
    create = leader_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "bad-config", "client_id": "ACME-MFG", "config_json": bad_config},
    )
    assert create.status_code == 201
    sid = create.json()["id"]

    run = leader_client.post(f"/api/v2/simulation/scenarios/{sid}/run")
    assert run.status_code == 422
    assert "incompatible" in run.json()["detail"].lower() or "validation" in str(run.json()).lower()

    leader_client.delete(f"/api/v2/simulation/scenarios/{sid}")


# =============================================================================
# Tenant isolation
# =============================================================================


def test_cross_tenant_leader_cannot_see_other_clients_scenarios(shared_client: TestClient) -> None:
    """A scenario saved under ACME-MFG is invisible to a leader assigned
    only to TEXTILE-PRO."""
    _override_user(shared_client, "leader", client_id_assigned="ACME-MFG")
    create = shared_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "acme-only", "client_id": "ACME-MFG", "config_json": _sample_config()},
    )
    sid = create.json()["id"]

    _override_user(shared_client, "leader", client_id_assigned="TEXTILE-PRO")
    list_resp = shared_client.get("/api/v2/simulation/scenarios")
    assert sid not in [s["id"] for s in list_resp.json()]
    get_resp = shared_client.get(f"/api/v2/simulation/scenarios/{sid}")
    assert get_resp.status_code == 404

    _override_user(shared_client, "leader", client_id_assigned="ACME-MFG")
    shared_client.delete(f"/api/v2/simulation/scenarios/{sid}")


def test_non_admin_cannot_create_global_scenario(leader_client: TestClient) -> None:
    """Global (NULL client_id) scenarios are admin-tier."""
    create = leader_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "global-attempt", "client_id": None, "config_json": _sample_config()},
    )
    assert create.status_code == 403


def test_non_admin_cannot_create_in_unassigned_client(leader_client: TestClient) -> None:
    """Leader assigned to ACME can't create in TEXTILE-PRO."""
    create = leader_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "wrong-client", "client_id": "TEXTILE-PRO", "config_json": _sample_config()},
    )
    assert create.status_code == 403


def test_admin_can_create_global(admin_client: TestClient) -> None:
    create = admin_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "global-template", "client_id": None, "config_json": _sample_config()},
    )
    assert create.status_code == 201
    assert create.json()["client_id"] is None
    sid = create.json()["id"]
    admin_client.delete(f"/api/v2/simulation/scenarios/{sid}")


def test_global_scenario_visible_to_all(shared_client: TestClient) -> None:
    """A global (NULL client_id) scenario is a shared template — every
    user sees it on their list."""
    _override_user(shared_client, "admin", client_id_assigned=None)
    create = shared_client.post(
        "/api/v2/simulation/scenarios",
        json={"name": "shared-template", "client_id": None, "config_json": _sample_config()},
    )
    sid = create.json()["id"]

    for client_id in ("ACME-MFG", "TEXTILE-PRO"):
        _override_user(shared_client, "leader", client_id_assigned=client_id)
        list_resp = shared_client.get("/api/v2/simulation/scenarios")
        assert sid in [s["id"] for s in list_resp.json()], (
            f"Global scenario should be visible to leader@{client_id}"
        )

    _override_user(shared_client, "admin", client_id_assigned=None)
    shared_client.delete(f"/api/v2/simulation/scenarios/{sid}")


# =============================================================================
# 404 handling
# =============================================================================


def test_get_nonexistent_returns_404(leader_client: TestClient) -> None:
    assert leader_client.get("/api/v2/simulation/scenarios/999999").status_code == 404


def test_delete_nonexistent_returns_404(leader_client: TestClient) -> None:
    assert leader_client.delete("/api/v2/simulation/scenarios/999999").status_code == 404


def test_run_nonexistent_returns_404(leader_client: TestClient) -> None:
    assert leader_client.post("/api/v2/simulation/scenarios/999999/run").status_code == 404
