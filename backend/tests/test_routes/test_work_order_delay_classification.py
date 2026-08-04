"""
Tests for the justified-delay classification update-path invariants (spec §5,
Cycle 2, Task 4) and the derived `is_late` field on WorkOrderResponse.

Follows the self-contained-app pattern from test_work_order_capacity_routes.py:
a fresh in-memory SQLite DB per test (clone_template_engine) + a FastAPI app
with get_current_user overridden to a role persona, rather than the module's
JWT-issuing auth flow (there is no shared authenticated-client fixture for
work orders in this test package to mirror more directly).
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.auth.jwt import get_current_active_supervisor, get_current_user
from backend.database import get_db
from backend.orm.user import User
from backend.routes.work_orders import router as work_orders_router
from backend.schemas.work_order import WorkOrderUpdate
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.factories import TestDataFactory

CLIENT_ID = "WO-DELAY-RT-C1"


def _create_test_app(db_session, role: str) -> FastAPI:
    """FastAPI app with only the work-orders router mounted, auth mocked to `role`."""
    app = FastAPI()
    app.include_router(work_orders_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    mock_user = User(
        user_id=f"test-wodelay-{role}",
        username=f"wodelay_{role}",
        email=f"wodelay_{role}@test.com",
        role=role,
        client_id_assigned=None if role in ("admin", "poweruser") else CLIENT_ID,
        is_active=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_active_supervisor] = lambda: mock_user

    return app


@pytest.fixture
def delay_db():
    """Fresh in-memory database for each test."""
    engine = clone_template_engine()
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def _make_late_and_ontime_wos(db):
    """One LATE work order (planned_ship_date 10 days ago, undelivered) and one
    NOT-LATE work order (planned_ship_date 10 days ahead, undelivered) — per
    backend.calculations.otd.is_late: undelivered + inferred planned date
    before `as_of` => late."""
    late_wo = TestDataFactory.create_work_order(
        db,
        client_id=CLIENT_ID,
        work_order_id="WO-DELAY-LATE-001",
        planned_ship_date=datetime.now(timezone.utc) - timedelta(days=10),
    )
    ontime_wo = TestDataFactory.create_work_order(
        db,
        client_id=CLIENT_ID,
        work_order_id="WO-DELAY-ONTIME-001",
        planned_ship_date=datetime.now(timezone.utc) + timedelta(days=10),
    )
    db.commit()
    db.refresh(late_wo)
    db.refresh(ontime_wo)
    return late_wo, ontime_wo


@pytest.fixture
def supervisor_client_with_wos(delay_db):
    TestDataFactory.create_client(delay_db, client_id=CLIENT_ID, client_name="Delay Classification Test Client")
    delay_db.commit()
    late_wo, ontime_wo = _make_late_and_ontime_wos(delay_db)
    app = _create_test_app(delay_db, role="supervisor")
    return TestClient(app), late_wo, ontime_wo


@pytest.fixture
def operator_client_with_wos(delay_db):
    TestDataFactory.create_client(delay_db, client_id=CLIENT_ID, client_name="Delay Classification Test Client")
    delay_db.commit()
    late_wo, ontime_wo = _make_late_and_ontime_wos(delay_db)
    app = _create_test_app(delay_db, role="operator")
    return TestClient(app), late_wo, ontime_wo


class TestDelayClassificationInvariants:
    def test_classify_late_order_as_justified_with_reason_succeeds(self, supervisor_client_with_wos):
        client, late_wo, _ = supervisor_client_with_wos
        r = client.put(
            f"/api/work-orders/{late_wo.work_order_id}",
            json={
                "delay_classification": "justified",
                "justified_delay_reason": "customer_request",
                "delay_classification_note": "Customer asked to hold shipment",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["delay_classification"] == "justified"
        assert body["justified_delay_reason"] == "customer_request"
        assert body["delay_classification_note"] == "Customer asked to hold shipment"
        assert body["is_late"] is True

    def test_classify_non_late_order_returns_422(self, supervisor_client_with_wos):
        client, _, ontime_wo = supervisor_client_with_wos
        r = client.put(
            f"/api/work-orders/{ontime_wo.work_order_id}",
            json={"delay_classification": "unjustified"},
        )
        assert r.status_code == 422

    def test_justified_without_reason_returns_422(self, supervisor_client_with_wos):
        client, late_wo, _ = supervisor_client_with_wos
        r = client.put(
            f"/api/work-orders/{late_wo.work_order_id}",
            json={"delay_classification": "justified"},
        )
        assert r.status_code == 422

    def test_clearing_classification_clears_reason_and_note(self, supervisor_client_with_wos):
        client, late_wo, _ = supervisor_client_with_wos
        setup = client.put(
            f"/api/work-orders/{late_wo.work_order_id}",
            json={
                "delay_classification": "justified",
                "justified_delay_reason": "force_majeure",
                "delay_classification_note": "flood",
            },
        )
        assert setup.status_code == 200

        r = client.put(
            f"/api/work-orders/{late_wo.work_order_id}",
            json={"delay_classification": None},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["delay_classification"] is None
        assert body["justified_delay_reason"] is None
        assert body["delay_classification_note"] is None

    def test_unjustified_clears_reason(self, supervisor_client_with_wos):
        client, late_wo, _ = supervisor_client_with_wos
        setup = client.put(
            f"/api/work-orders/{late_wo.work_order_id}",
            json={"delay_classification": "justified", "justified_delay_reason": "upstream_hold"},
        )
        assert setup.status_code == 200

        r = client.put(
            f"/api/work-orders/{late_wo.work_order_id}",
            json={"delay_classification": "unjustified"},
        )
        assert r.status_code == 200
        assert r.json()["justified_delay_reason"] is None

    def test_operator_touching_classification_fields_returns_403(self, operator_client_with_wos):
        client, late_wo, _ = operator_client_with_wos
        r = client.put(
            f"/api/work-orders/{late_wo.work_order_id}",
            json={"delay_classification": "unjustified"},
        )
        assert r.status_code == 403

    def test_operator_updating_non_classification_field_also_403(self, operator_client_with_wos):
        """NOT a classification-specific finding: `_check_wo_write_permission`
        (routes/work_orders.py, Run 7) blocks operators from PUT
        /api/work-orders/{id} for ANY field, pre-existing and unrelated to
        this task. Documented here (rather than silently dropped) so the
        403 above isn't mistaken for classification-specific gating — the
        route-level guard already denies operators before the request body
        is even inspected."""
        client, late_wo, _ = operator_client_with_wos
        r = client.put(f"/api/work-orders/{late_wo.work_order_id}", json={"priority": "HIGH"})
        assert r.status_code == 403

    def test_response_is_late_false_for_ontime_order(self, supervisor_client_with_wos):
        client, _, ontime_wo = supervisor_client_with_wos
        r = client.get(f"/api/work-orders/{ontime_wo.work_order_id}")
        assert r.status_code == 200
        assert r.json()["is_late"] is False

    def test_response_is_late_true_for_late_order(self, supervisor_client_with_wos):
        client, late_wo, _ = supervisor_client_with_wos
        r = client.get(f"/api/work-orders/{late_wo.work_order_id}")
        assert r.status_code == 200
        assert r.json()["is_late"] is True

    def test_list_endpoint_populates_is_late(self, supervisor_client_with_wos):
        client, late_wo, ontime_wo = supervisor_client_with_wos
        r = client.get("/api/work-orders", params={"client_id": CLIENT_ID})
        assert r.status_code == 200
        by_id = {row["work_order_id"]: row for row in r.json()}
        assert by_id[late_wo.work_order_id]["is_late"] is True
        assert by_id[ontime_wo.work_order_id]["is_late"] is False


class TestWorkOrderUpdateSchemaExcludeUnset:
    """Explicit-null vs omitted nuance for the three new WorkOrderUpdate
    fields: `model_dump(exclude_unset=True)` must keep a key explicitly set
    to None (so "clear this field" round-trips), and drop a key never
    mentioned in the request body at all."""

    def test_explicit_null_is_kept_omitted_is_dropped(self):
        explicit_null = WorkOrderUpdate(delay_classification=None)
        dumped = explicit_null.model_dump(exclude_unset=True)
        assert "delay_classification" in dumped
        assert dumped["delay_classification"] is None

        omitted = WorkOrderUpdate(priority="HIGH")
        dumped_omitted = omitted.model_dump(exclude_unset=True)
        assert "delay_classification" not in dumped_omitted
        assert "justified_delay_reason" not in dumped_omitted
        assert "delay_classification_note" not in dumped_omitted
