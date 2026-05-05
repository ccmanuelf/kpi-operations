"""
Integration tests for the calculation_assumptions REST API.

Real DB (in-memory SQLite), no mocks. Pattern matches test_capacity_routes_crud
in this directory: a TestApp with dependency overrides so each test can pin a
specific authenticated user role.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.orm.user import User
from backend.routes.calculation_assumptions import router as assumptions_router
from backend.tests.fixtures.factories import TestDataFactory


CLIENT_ID = "ASSUM-TEST-CLIENT"


def _build_app(db_session, current_user: User) -> FastAPI:
    app = FastAPI()
    app.include_router(assumptions_router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: current_user
    return app


@pytest.fixture
def seeded(transactional_db):
    client = TestDataFactory.create_client(transactional_db, client_id=CLIENT_ID)
    admin = TestDataFactory.create_user(transactional_db, role="admin", client_id=client.client_id)
    poweruser = TestDataFactory.create_user(transactional_db, role="poweruser", client_id=client.client_id)
    leader = TestDataFactory.create_user(transactional_db, role="leader", client_id=client.client_id)
    transactional_db.commit()
    return {
        "db": transactional_db,
        "client": client,
        "admin": admin,
        "poweruser": poweruser,
        "leader": leader,
    }


class TestCatalog:
    def test_returns_v1_catalog(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["leader"]))
        resp = client.get("/api/assumptions/catalog")
        assert resp.status_code == 200
        names = {entry["name"] for entry in resp.json()}
        assert {
            "ideal_cycle_time_source",
            "setup_treatment",
            "scrap_classification_rule",
            "otd_carrier_buffer_pct",
            "yield_baseline_source",
            "planned_production_time_basis",
        }.issubset(names)


class TestPropose:
    def test_poweruser_201(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        resp = client.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "ideal_cycle_time_source",
                "value": "engineering_standard",
                "rationale": "use engineering standard",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "proposed"
        assert body["value"] == "engineering_standard"

    def test_leader_403(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["leader"]))
        resp = client.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "ideal_cycle_time_source",
                "value": "engineering_standard",
            },
        )
        assert resp.status_code == 403

    def test_unknown_name_400(self, seeded):
        client = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        resp = client.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "not_in_catalog",
                "value": "x",
            },
        )
        assert resp.status_code == 400


class TestApproveRetire:
    def test_lifecycle_propose_approve_retire(self, seeded):
        # propose
        pclient = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        resp = pclient.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "setup_treatment",
                "value": "count_as_downtime",
            },
        )
        assert resp.status_code == 201
        assumption_id = resp.json()["assumption_id"]

        # approve (admin)
        aclient = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = aclient.post(f"/api/assumptions/{assumption_id}/approve", json={"change_reason": "ok"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        # retire (admin)
        resp = aclient.post(f"/api/assumptions/{assumption_id}/retire", json={"change_reason": "obsolete"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "retired"

    def test_poweruser_cannot_approve(self, seeded):
        pclient = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        resp = pclient.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "yield_baseline_source",
                "value": "theoretical",
            },
        )
        assumption_id = resp.json()["assumption_id"]

        resp = pclient.post(f"/api/assumptions/{assumption_id}/approve")
        assert resp.status_code == 403


class TestUpdateProposal:
    def test_proposer_updates_own_proposal(self, seeded):
        pclient = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        resp = pclient.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "setup_treatment",
                "value": "count_as_downtime",
            },
        )
        assumption_id = resp.json()["assumption_id"]

        resp = pclient.patch(
            f"/api/assumptions/{assumption_id}",
            json={"value": "exclude_from_availability", "change_reason": "reconsidered"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["value"] == "exclude_from_availability"


class TestEffectiveSet:
    def test_returns_active_only(self, seeded):
        # Propose + approve one
        pclient = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        resp = pclient.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "setup_treatment",
                "value": "count_as_downtime",
            },
        )
        assumption_id = resp.json()["assumption_id"]

        aclient = TestClient(_build_app(seeded["db"], seeded["admin"]))
        aclient.post(f"/api/assumptions/{assumption_id}/approve")

        # Propose another but don't approve
        pclient.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "yield_baseline_source",
                "value": "theoretical",
            },
        )

        # Effective set should include only the approved one
        resp = aclient.get(f"/api/assumptions/effective?client_id={CLIENT_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert "setup_treatment" in body["assumptions"]
        assert "yield_baseline_source" not in body["assumptions"]


class TestHistory:
    def test_history_endpoint_returns_changes(self, seeded):
        pclient = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        resp = pclient.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "setup_treatment",
                "value": "count_as_downtime",
            },
        )
        assumption_id = resp.json()["assumption_id"]

        aclient = TestClient(_build_app(seeded["db"], seeded["admin"]))
        aclient.post(f"/api/assumptions/{assumption_id}/approve")

        resp = aclient.get(f"/api/assumptions/{assumption_id}/history")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2  # propose + approve
        # newest first
        assert rows[0]["new_status"] == "active"
        assert rows[1]["new_status"] == "proposed"


class TestVarianceEndpoint:
    def test_returns_active_rows(self, seeded):
        # Approve one assumption that deviates from default + one that matches.
        pclient = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        aclient = TestClient(_build_app(seeded["db"], seeded["admin"]))

        for value in ("exclude_from_availability", "count_as_downtime"):
            resp = pclient.post(
                "/api/assumptions",
                json={
                    "client_id": CLIENT_ID,
                    "assumption_name": (
                        "setup_treatment" if value == "exclude_from_availability" else "scrap_classification_rule"
                    ),
                    "value": value if value == "exclude_from_availability" else "rework_counted_as_good",
                },
            )
            assert resp.status_code == 201, resp.text
            aclient.post(f"/api/assumptions/{resp.json()['assumption_id']}/approve")

        resp = aclient.get("/api/assumptions/variance")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2

        by_name = {r["assumption_name"]: r for r in rows}
        assert by_name["setup_treatment"]["deviates_from_default"] is True
        assert by_name["setup_treatment"]["deviation_magnitude"] == 1.0
        assert by_name["scrap_classification_rule"]["deviates_from_default"] is False

    def test_stale_threshold_query_param_respected(self, seeded):
        # Create + approve, then verify default 365 makes it not stale.
        pclient = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        aclient = TestClient(_build_app(seeded["db"], seeded["admin"]))

        resp = pclient.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "setup_treatment",
                "value": "exclude_from_availability",
            },
        )
        aclient.post(f"/api/assumptions/{resp.json()['assumption_id']}/approve")

        # With a 1-day threshold, a fresh approval is NOT stale
        rows = aclient.get("/api/assumptions/variance?stale_after_days=1").json()
        assert rows[0]["is_stale"] is False  # less than 1 day old

    def test_route_path_does_not_collide_with_id_route(self, seeded):
        # /variance must not be parsed as /{assumption_id}
        aclient = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = aclient.get("/api/assumptions/variance")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestList:
    def test_filter_by_status(self, seeded):
        pclient = TestClient(_build_app(seeded["db"], seeded["poweruser"]))
        pclient.post(
            "/api/assumptions",
            json={
                "client_id": CLIENT_ID,
                "assumption_name": "setup_treatment",
                "value": "count_as_downtime",
            },
        )

        aclient = TestClient(_build_app(seeded["db"], seeded["admin"]))
        resp = aclient.get(f"/api/assumptions?client_id={CLIENT_ID}&status=proposed")
        assert resp.status_code == 200
        body = resp.json()
        assert all(r["status"] == "proposed" for r in body)
        assert len(body) >= 1
