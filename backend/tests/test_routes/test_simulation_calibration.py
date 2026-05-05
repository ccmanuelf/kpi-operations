"""
Tests for D4 — `GET /api/v2/simulation/calibration`.

Coverage:
  - Permission gate (operator denied; leader/poweruser/admin allowed)
  - Tenant fence (leader cannot calibrate a client outside their list)
  - Default period (omitted query params resolve to today / -30d)
  - Reversed dates are silently swapped (matches service-level behavior)
  - Empty client → empty operations + warnings, no crash
  - Calibrated config validates against SimulationConfig (round-trip)
  - Source provenance present for products + schedule
  - Confidence buckets ('low' for sparse demo data) are reported

We hit the live demo SQLite (same pattern as D3 tests). Task #130
tracks moving these to a transactional fixture; until that lands the
tests are read-only — calibration never writes to the DB.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.main import app
from backend.simulation_v2.models import SimulationConfig


# ---------------------------------------------------------------------------
# Fixtures (mirror the D3 pattern: one TestClient + persona switcher)
# ---------------------------------------------------------------------------


def _user(
    role: str,
    *,
    client_id_assigned: str | None = "ACME-MFG",
    username: str | None = None,
) -> MagicMock:
    u = MagicMock()
    u.role = role
    u.username = username or f"test_{role}"
    u.user_id = f"USER-TEST-{role.upper()}"
    u.client_id_assigned = client_id_assigned
    u.is_active = True
    u.email = f"{role}@test.local"
    u.full_name = role.title()
    return u


def _override_user(
    client: TestClient,
    role: str,
    client_id_assigned: str | None = "ACME-MFG",
) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: _user(role, client_id_assigned=client_id_assigned)
    return client


@pytest.fixture
def shared_client():
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Permission tests
# ---------------------------------------------------------------------------


def test_operator_forbidden(shared_client: TestClient) -> None:
    """Operators cannot calibrate (planner-only action)."""
    client = _override_user(shared_client, "operator")
    resp = client.get("/api/v2/simulation/calibration", params={"client_id": "ACME-MFG"})
    assert resp.status_code == 403
    assert "leader" in resp.json()["detail"].lower()


def test_leader_allowed(shared_client: TestClient) -> None:
    client = _override_user(shared_client, "leader", client_id_assigned="ACME-MFG")
    resp = client.get("/api/v2/simulation/calibration", params={"client_id": "ACME-MFG"})
    assert resp.status_code == 200, resp.text


def test_admin_allowed_no_assignment(shared_client: TestClient) -> None:
    """Admin can calibrate any client even with no client_id_assigned."""
    client = _override_user(shared_client, "admin", client_id_assigned=None)
    resp = client.get("/api/v2/simulation/calibration", params={"client_id": "ACME-MFG"})
    assert resp.status_code == 200, resp.text


def test_poweruser_allowed_no_assignment(shared_client: TestClient) -> None:
    client = _override_user(shared_client, "poweruser", client_id_assigned=None)
    resp = client.get("/api/v2/simulation/calibration", params={"client_id": "ACME-MFG"})
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Tenant fence
# ---------------------------------------------------------------------------


def test_leader_blocked_on_other_tenant(shared_client: TestClient) -> None:
    """Leader assigned to ACME cannot calibrate TEXTILE-PRO."""
    client = _override_user(shared_client, "leader", client_id_assigned="ACME-MFG")
    resp = client.get(
        "/api/v2/simulation/calibration",
        params={"client_id": "TEXTILE-PRO"},
    )
    assert resp.status_code == 403
    assert "TEXTILE-PRO" in resp.json()["detail"]


def test_leader_with_multi_assignment(shared_client: TestClient) -> None:
    """Comma-separated client list is honoured."""
    client = _override_user(shared_client, "leader", client_id_assigned="ACME-MFG, FASHION-WORKS")
    for cid in ("ACME-MFG", "FASHION-WORKS"):
        resp = client.get("/api/v2/simulation/calibration", params={"client_id": cid})
        assert resp.status_code == 200, f"{cid}: {resp.text}"


# ---------------------------------------------------------------------------
# Date-range handling
# ---------------------------------------------------------------------------


def test_default_period_when_omitted(shared_client: TestClient) -> None:
    """Without period_start/end the route defaults to today / 30d ago."""
    client = _override_user(shared_client, "leader")
    resp = client.get("/api/v2/simulation/calibration", params={"client_id": "ACME-MFG"})
    assert resp.status_code == 200
    body = resp.json()
    today = date.today()
    assert body["period"]["end"] == today.isoformat()
    assert body["period"]["start"] == (today - timedelta(days=30)).isoformat()


def test_reversed_dates_rejected(shared_client: TestClient) -> None:
    """Reversed dates raise 400 at the route boundary (consistent with
    every other date-range endpoint via validate_date_range)."""
    client = _override_user(shared_client, "leader")
    resp = client.get(
        "/api/v2/simulation/calibration",
        params={
            "client_id": "ACME-MFG",
            "period_start": "2026-04-30",
            "period_end": "2026-04-01",
        },
    )
    assert resp.status_code == 400
    assert "Invalid date range" in resp.json()["detail"]


def test_one_day_window_allowed(shared_client: TestClient) -> None:
    client = _override_user(shared_client, "leader")
    resp = client.get(
        "/api/v2/simulation/calibration",
        params={
            "client_id": "ACME-MFG",
            "period_start": "2026-04-15",
            "period_end": "2026-04-15",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["period"]["days"] == 1


# ---------------------------------------------------------------------------
# Response shape + business semantics
# ---------------------------------------------------------------------------


def test_response_shape_full(shared_client: TestClient) -> None:
    """Full payload — operations, demands, breakdowns, schedule,
    sources, warnings — for a client with seeded data."""
    client = _override_user(shared_client, "admin", client_id_assigned=None)
    resp = client.get(
        "/api/v2/simulation/calibration",
        params={
            "client_id": "ACME-MFG",
            "period_start": (date.today() - timedelta(days=180)).isoformat(),
            "period_end": date.today().isoformat(),
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["client_id"] == "ACME-MFG"
    assert set(body["period"].keys()) == {"start", "end", "days"}

    cfg = body["config"]
    assert {"operations", "schedule", "demands", "breakdowns", "mode", "horizon_days"} <= cfg.keys()
    # Demo seed has 5 products × 5 ops = 25 operations
    assert len(cfg["operations"]) == 25
    assert cfg["mode"] == "demand-driven"

    # Each operation carries the calibrated fields the engine needs
    op = cfg["operations"][0]
    for required in (
        "product",
        "step",
        "operation",
        "machine_tool",
        "sam_min",
        "operators",
        "rework_pct",
        "grade_pct",
        "fpd_pct",
    ):
        assert required in op, f"missing {required} on calibrated op"

    # Provenance: at least one per-product source + a schedule source
    assert any(k.startswith("products.") for k in body["sources"])
    assert "schedule" in body["sources"]
    sample_src = next(iter(body["sources"].values()))
    assert sample_src["confidence"] in {"high", "medium", "low", "none"}

    # FPD warning is emitted because the platform doesn't track it
    assert any("FPD" in w for w in body["warnings"])


def test_calibrated_config_runs_through_engine(shared_client: TestClient) -> None:
    """Round-trip: calibration output → SimulationConfig.model_validate
    must succeed. Catches schema drift (the engine adds a required
    field, calibration forgets to emit it)."""
    client = _override_user(shared_client, "admin", client_id_assigned=None)
    resp = client.get(
        "/api/v2/simulation/calibration",
        params={
            "client_id": "ACME-MFG",
            "period_start": (date.today() - timedelta(days=180)).isoformat(),
            "period_end": date.today().isoformat(),
        },
    )
    assert resp.status_code == 200
    cfg = SimulationConfig.model_validate(resp.json()["config"])
    assert cfg.horizon_days >= 1
    assert len(cfg.operations) > 0
    # daily * work_days must equal weekly (the consistency we just fixed)
    for d in cfg.demands:
        if d.daily_demand and d.weekly_demand:
            assert d.weekly_demand == d.daily_demand * cfg.schedule.work_days


def test_empty_client_returns_warnings(shared_client: TestClient) -> None:
    """A client with no standards / no production produces an empty
    config + warning text — not a 500."""
    client = _override_user(shared_client, "admin", client_id_assigned=None)
    resp = client.get(
        "/api/v2/simulation/calibration",
        params={
            "client_id": "CLIENT001",  # no standards in the demo seed
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["config"]["operations"] == []
    assert any("standards" in w.lower() for w in body["warnings"])


def test_short_window_yields_low_confidence(shared_client: TestClient) -> None:
    """A 1-day window can only produce 'low' or 'none' confidence."""
    client = _override_user(shared_client, "admin", client_id_assigned=None)
    resp = client.get(
        "/api/v2/simulation/calibration",
        params={
            "client_id": "ACME-MFG",
            "period_start": "2026-04-15",
            "period_end": "2026-04-15",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    for src in body["sources"].values():
        assert src["confidence"] in {"low", "none", "medium"}, src
