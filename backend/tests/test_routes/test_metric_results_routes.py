"""
Inspector API integration tests — Phase 4 dual-view UI prerequisite.

Real DB (in-memory SQLite), no mocks. Verifies the two endpoints route the
right data through the lineage expansion (assumption metadata, formula text,
inputs snapshot).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.orm.user import User
from backend.routes.metric_results import router as results_router
from backend.services.assumption_service import AssumptionService
from backend.services.dual_view.fpy_service import FPYCalculationService, FPYRawInputs
from backend.services.dual_view.oee_service import OEECalculationService, OEERawInputs
from backend.tests.fixtures.factories import TestDataFactory


CLIENT_ID = "INSPECT-CLIENT"


def _build_app(db_session, current_user: User) -> FastAPI:
    app = FastAPI()
    app.include_router(results_router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: current_user
    return app


@pytest.fixture
def seeded(transactional_db):
    client = TestDataFactory.create_client(transactional_db, client_id=CLIENT_ID)
    admin = TestDataFactory.create_user(transactional_db, role="admin", client_id=client.client_id)
    poweruser = TestDataFactory.create_user(transactional_db, role="poweruser", client_id=client.client_id)
    operator = TestDataFactory.create_user(transactional_db, role="operator", client_id=client.client_id)
    transactional_db.commit()
    return {
        "db": transactional_db,
        "client": client,
        "admin": admin,
        "poweruser": poweruser,
        "operator": operator,
    }


def _seed_oee_with_assumption(seeded) -> int:
    """Approve scrap_classification_rule + persist one OEE result. Returns result_id."""
    db = seeded["db"]
    rec = AssumptionService(db, seeded["poweruser"]).propose(
        client_id=CLIENT_ID,
        assumption_name="scrap_classification_rule",
        value="rework_counted_as_good",
        rationale="Reworked units ship; count them as first-pass for OEE.",
    )
    AssumptionService(db, seeded["admin"]).approve(rec.assumption_id)

    inputs = OEERawInputs(
        scheduled_hours=Decimal("80"),
        downtime_hours=Decimal("8"),
        units_produced=900,
        run_time_hours=Decimal("72"),
        ideal_cycle_time_hours=Decimal("0.076"),
        defect_count=30,
        scrap_count=20,
        units_reworked=15,
    )
    result = OEECalculationService(db, seeded["admin"]).calculate(
        client_id=CLIENT_ID,
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 4, 30, tzinfo=timezone.utc),
        raw_inputs=inputs,
        persist=True,
    )
    assert result.result_id is not None  # persist=True guarantees an id
    return result.result_id


def _seed_fpy_no_assumption(seeded) -> int:
    db = seeded["db"]
    inputs = FPYRawInputs(total_inspected=100, units_passed_first_time=80, units_reworked=10)
    result = FPYCalculationService(db, seeded["admin"]).calculate(
        client_id=CLIENT_ID,
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 4, 30, tzinfo=timezone.utc),
        raw_inputs=inputs,
        persist=True,
    )
    assert result.result_id is not None
    return result.result_id


class TestList:
    def test_admin_sees_all(self, seeded):
        _seed_oee_with_assumption(seeded)
        _seed_fpy_no_assumption(seeded)

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.get("/api/metrics/results")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        names = {r["metric_name"] for r in body}
        assert names == {"oee", "fpy"}

    def test_filter_by_metric(self, seeded):
        _seed_oee_with_assumption(seeded)
        _seed_fpy_no_assumption(seeded)

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.get("/api/metrics/results?metric_name=oee")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["metric_name"] == "oee"
        assert rows[0]["has_assumptions"] is True

    def test_operator_sees_only_assigned_client(self, seeded):
        _seed_oee_with_assumption(seeded)
        # Other-client result that should NOT show up for the operator.
        other = TestDataFactory.create_client(seeded["db"], client_id="OTHER-CLIENT")
        other_admin = TestDataFactory.create_user(seeded["db"], role="admin", client_id=other.client_id)
        seeded["db"].commit()
        FPYCalculationService(seeded["db"], other_admin).calculate(
            client_id=other.client_id,
            period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 4, 30, tzinfo=timezone.utc),
            raw_inputs=FPYRawInputs(total_inspected=10, units_passed_first_time=8),
            persist=True,
        )

        client = TestClient(_build_app(seeded["db"], seeded["operator"]))
        resp = client.get("/api/metrics/results")
        assert resp.status_code == 200
        rows = resp.json()
        assert all(r["client_id"] == CLIENT_ID for r in rows)


class TestGetLineage:
    def test_lineage_includes_formula_and_metadata(self, seeded):
        result_id = _seed_oee_with_assumption(seeded)

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.get(f"/api/metrics/results/{result_id}")
        assert resp.status_code == 200
        body = resp.json()

        assert body["metric_name"] == "oee"
        assert body["metric_display_name"] == "Overall Equipment Effectiveness"
        assert "OEE = " in body["formula"]
        assert body["description"]

    def test_lineage_includes_inputs_snapshot(self, seeded):
        result_id = _seed_oee_with_assumption(seeded)

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        body = client.get(f"/api/metrics/results/{result_id}").json()

        # Inputs snapshot was persisted at calculation time
        assert "scheduled_hours" in body["inputs"]
        assert body["inputs"]["units_produced"] == 900
        # Each input has a help description from METRIC_METADATA
        assert "scheduled_hours" in body["inputs_help"]

    def test_lineage_expands_assumption_metadata(self, seeded):
        result_id = _seed_oee_with_assumption(seeded)

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        body = client.get(f"/api/metrics/results/{result_id}").json()

        applied = body["assumptions_applied"]
        assert len(applied) == 1
        a = applied[0]
        assert a["name"] == "scrap_classification_rule"
        assert a["value"] == "rework_counted_as_good"
        assert a["description"]  # from V1_CATALOG
        assert a["rationale"] == "Reworked units ship; count them as first-pass for OEE."
        assert a["approved_by"] == seeded["admin"].user_id
        assert a["assumption_id"] is not None

    def test_lineage_with_no_assumptions(self, seeded):
        result_id = _seed_fpy_no_assumption(seeded)

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        body = client.get(f"/api/metrics/results/{result_id}").json()

        assert body["assumptions_applied"] == []
        assert body["delta"] == 0  # no assumption → no divergence

    def test_lineage_404_on_missing(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.get("/api/metrics/results/99999")
        assert resp.status_code == 404
