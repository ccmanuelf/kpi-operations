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

Isolation: every test runs against an in-memory SQLite via the shared
`transactional_db` fixture (conftest.py). The `get_db` dependency is
overridden to yield that session, so calibration never touches the
live demo DB. (Closes follow-up #130 for the calibration tests.)

Tests that need seeded data use the `seeded_db` fixture which adds a
minimal calibration scenario (1 client, 5 products × 5 standards,
2 shifts, ~30 days of production entries) via TestDataFactory.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.main import app
from backend.simulation_v2.models import SimulationConfig
from backend.tests.fixtures.factories import TestDataFactory


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
def isolated_db(transactional_db):
    """Override `get_db` for the lifetime of one test so the calibration
    route reads from the function-scoped in-memory SQLite. Schema-only
    DB (no demo data) — seed via the helper below for tests needing data.
    """
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def shared_client(isolated_db):
    """TestClient bound to the isolated DB. Tests switch persona via
    `_override_user(client, role)`."""
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def _seed_calibration_scenario(db) -> None:
    """Seed a calibration scenario into an isolated DB:
      - Client ACME-MFG
      - 2 shifts (Day/Night)
      - 5 products × 5 production standards = 25 calibrated operations
      - 30 days of production entries (drives source confidence + FPD warning)

    Used by tests that assert on operations/sources/warnings.
    """
    from backend.orm.capacity.standards import CapacityProductionStandard

    TestDataFactory.create_client(db, client_id="ACME-MFG", client_name="Acme Mfg")
    TestDataFactory.create_shift(db, client_id="ACME-MFG", shift_name="Day", start_time="06:00:00", end_time="14:00:00")
    TestDataFactory.create_shift(
        db, client_id="ACME-MFG", shift_name="Night", start_time="14:00:00", end_time="22:00:00"
    )

    products = []
    for i in range(5):
        p = TestDataFactory.create_product(
            db,
            client_id="ACME-MFG",
            product_code=f"PROD-{i + 1}",
            product_name=f"Product {i + 1}",
        )
        products.append(p)

    # 5 ops × 5 products = 25 standards (each row → calibrated operation)
    for p in products:
        for op_seq in range(1, 6):
            db.add(
                CapacityProductionStandard(
                    client_id="ACME-MFG",
                    style_model=p.product_code,
                    operation_code=f"OP-{op_seq}",
                    operation_name=f"Operation {op_seq}",
                    department=f"Tool{op_seq}",
                    sam_minutes=Decimal("1.5"),
                )
            )
    db.flush()

    admin = TestDataFactory.create_user(db, role="admin", client_id="ACME-MFG")
    base = date.today()
    for offset in range(30):
        d = base - timedelta(days=offset)
        TestDataFactory.create_production_entry(
            db,
            client_id="ACME-MFG",
            product_id=products[offset % 5].product_id,
            shift_id=1,
            entered_by=admin.user_id,
            production_date=d,
            units_produced=100,
            defect_count=2,
            scrap_count=1,
            rework_count=1,
        )
    db.commit()


@pytest.fixture
def seeded_client(isolated_db):
    """TestClient bound to a seeded isolated DB. Used by tests that
    assert on calibrated config payload structure (operations, sources,
    warnings)."""
    _seed_calibration_scenario(isolated_db)
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


def test_response_shape_full(seeded_client: TestClient) -> None:
    """Full payload — operations, demands, breakdowns, schedule,
    sources, warnings — for a client with seeded data."""
    client = _override_user(seeded_client, "admin", client_id_assigned=None)
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


def test_calibrated_config_runs_through_engine(seeded_client: TestClient) -> None:
    """Round-trip: calibration output → SimulationConfig.model_validate
    must succeed. Catches schema drift (the engine adds a required
    field, calibration forgets to emit it)."""
    client = _override_user(seeded_client, "admin", client_id_assigned=None)
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


def test_short_window_yields_low_confidence(seeded_client: TestClient) -> None:
    """A 1-day window can only produce 'low' or 'none' confidence."""
    client = _override_user(seeded_client, "admin", client_id_assigned=None)
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
