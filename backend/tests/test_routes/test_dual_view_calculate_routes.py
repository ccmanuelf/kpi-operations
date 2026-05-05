"""
Integration tests for Phase 4c on-demand calculation endpoints.

Pattern matches test_metric_results_routes.py: dependency overrides for
get_db + get_current_user, real in-memory SQLite via transactional_db.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.orm.user import User
from backend.routes.dual_view_calculate import router as calc_router
from backend.services.assumption_service import AssumptionService
from backend.tests.fixtures.factories import TestDataFactory


CLIENT_ID = "DV-CALC-CLIENT"


def _build_app(db_session, current_user: User) -> FastAPI:
    app = FastAPI()
    app.include_router(calc_router)
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


def _approve(db, poweruser, admin, name, value, client_id=CLIENT_ID):
    record = AssumptionService(db, poweruser).propose(client_id=client_id, assumption_name=name, value=value)
    AssumptionService(db, admin).approve(record.assumption_id)
    return record


def _oee_body() -> dict:
    return {
        "client_id": CLIENT_ID,
        "period_start": "2026-04-01T00:00:00+00:00",
        "period_end": "2026-04-30T00:00:00+00:00",
        "raw_inputs": {
            "scheduled_hours": "80",
            "downtime_hours": "8",
            "setup_minutes": "60",
            "scheduled_maintenance_hours": "4",
            "units_produced": 900,
            "run_time_hours": "72",
            "ideal_cycle_time_hours": "0.076",
            "defect_count": 30,
            "scrap_count": 20,
            "units_reworked": 15,
        },
    }


def _otd_body() -> dict:
    return {
        "client_id": CLIENT_ID,
        "period_start": "2026-04-01T00:00:00+00:00",
        "period_end": "2026-04-30T00:00:00+00:00",
        "raw_inputs": {
            "orders": [
                {"delay_pct": "0.0"},
                {"delay_pct": "0.0"},
                {"delay_pct": "0.03"},
                {"delay_pct": "0.10"},
            ],
        },
    }


def _fpy_body() -> dict:
    return {
        "client_id": CLIENT_ID,
        "period_start": "2026-04-01T00:00:00+00:00",
        "period_end": "2026-04-30T00:00:00+00:00",
        "raw_inputs": {
            "total_inspected": 100,
            "units_passed_first_time": 80,
            "units_reworked": 10,
        },
    }


class TestOEEEndpoint:
    def test_returns_result_id_and_persists(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.post("/api/metrics/calculate/oee", json=_oee_body())
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["metric_name"] == "oee"
        assert body["result_id"] is not None

        row = (
            seeded["db"]
            .query(MetricCalculationResult)
            .filter(MetricCalculationResult.result_id == body["result_id"])
            .first()
        )
        assert row is not None
        assert row.client_id == CLIENT_ID

    def test_assumption_count_reflects_active_set(self, seeded):
        _approve(
            seeded["db"], seeded["poweruser"], seeded["admin"], "scrap_classification_rule", "rework_counted_as_good"
        )

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        body = client.post("/api/metrics/calculate/oee", json=_oee_body()).json()
        assert body["assumptions_applied_count"] == 1

    def test_invalid_period_400(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        bad = _oee_body()
        bad["period_start"] = "2026-05-01T00:00:00+00:00"
        bad["period_end"] = "2026-04-01T00:00:00+00:00"
        resp = client.post("/api/metrics/calculate/oee", json=bad)
        assert resp.status_code == 400


class TestOTDEndpoint:
    def test_otd_with_buffer(self, seeded):
        _approve(seeded["db"], seeded["poweruser"], seeded["admin"], "otd_carrier_buffer_pct", 5)

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.post("/api/metrics/calculate/otd", json=_otd_body())
        assert resp.status_code == 201
        body = resp.json()
        # 2/4 standard on-time (50%), buffer 5% promotes the 3% late → 3/4 = 75%
        assert body["site_adjusted_value"] == "75.00"
        assert body["standard_value"] == "50.00"


class TestFPYEndpoint:
    def test_fpy_returns_result(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.post("/api/metrics/calculate/fpy", json=_fpy_body())
        assert resp.status_code == 201
        body = resp.json()
        assert body["metric_name"] == "fpy"
        assert body["standard_value"] == "80.00"

    def test_fpy_with_rule_diverges(self, seeded):
        _approve(
            seeded["db"], seeded["poweruser"], seeded["admin"], "scrap_classification_rule", "rework_counted_as_good"
        )

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        body = client.post("/api/metrics/calculate/fpy", json=_fpy_body()).json()
        assert body["standard_value"] == "80.00"
        assert body["site_adjusted_value"] == "90.00"


class TestFromPeriodEndpoints:
    """F.1 — calculate-from-period variants that aggregate live data first."""

    def test_oee_from_period_runs_against_empty_data(self, seeded):
        # Empty period (no production entries) → service runs with zero inputs.
        # The OEE orchestrator validates ideal_cycle_time_hours > 0 and the
        # aggregator falls back to 0.25h, so the call succeeds with 0% OEE.
        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        body = {
            "client_id": CLIENT_ID,
            "period_start": "2026-04-01T00:00:00+00:00",
            "period_end": "2026-04-30T00:00:00+00:00",
        }
        resp = client.post("/api/metrics/calculate/from-period/oee", json=body)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["metric_name"] == "oee"
        assert data["result_id"] is not None

    def test_otd_from_period_empty_returns_zero(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.post(
            "/api/metrics/calculate/from-period/otd",
            json={
                "client_id": CLIENT_ID,
                "period_start": "2026-04-01T00:00:00+00:00",
                "period_end": "2026-04-30T00:00:00+00:00",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["standard_value"] == "0.00"

    def test_fpy_from_period_empty_returns_zero(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.post(
            "/api/metrics/calculate/from-period/fpy",
            json={
                "client_id": CLIENT_ID,
                "period_start": "2026-04-01T00:00:00+00:00",
                "period_end": "2026-04-30T00:00:00+00:00",
            },
        )
        assert resp.status_code == 201
        # FPY pure helper returns Decimal("0") (not quantized) when total_inspected == 0
        assert resp.json()["standard_value"] in ("0", "0.00")

    def test_from_period_invalid_period_400(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = client.post(
            "/api/metrics/calculate/from-period/oee",
            json={
                "client_id": CLIENT_ID,
                "period_start": "2026-05-01T00:00:00+00:00",
                "period_end": "2026-04-01T00:00:00+00:00",
            },
        )
        assert resp.status_code == 400


class TestManualTrigger:
    """F.4 — POST /run-nightly admin-only manual trigger."""

    def test_admin_can_trigger(self, seeded):
        from unittest.mock import patch

        client = TestClient(_build_app(seeded["db"], seeded["admin"]))
        with patch("backend.tasks.dual_view_calculation.run_nightly_dual_view_calculations") as mock_run:
            mock_run.return_value = {"FAKE": {"oee": 1, "otd": 2, "fpy": 3}}
            resp = client.post("/api/metrics/calculate/run-nightly")
            assert resp.status_code == 202
            assert resp.json()["status"] == "completed"
            mock_run.assert_called_once()

    def test_poweruser_cannot_trigger(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        resp = client.post("/api/metrics/calculate/run-nightly")
        assert resp.status_code == 403


class TestTenantIsolation:
    def test_operator_cannot_calculate_other_client(self, seeded):
        # Make a second client; operator's client_id_assigned is CLIENT_ID
        other = TestDataFactory.create_client(seeded["db"], client_id="OTHER-CLIENT")
        seeded["db"].commit()

        body = _fpy_body()
        body["client_id"] = other.client_id

        client = TestClient(_build_app(seeded["db"], seeded["operator"]))
        resp = client.post("/api/metrics/calculate/fpy", json=body)
        assert resp.status_code == 403
