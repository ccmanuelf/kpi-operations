"""
Route tests for labor-hours capture on the Attendance API (Cycle 3 PR-A, Task 4).

Covers OT split invariants, hour-allocation invariants + replace-on-write,
and effective_labor_class resolution end-to-end through POST/PUT /api/attendance.
Uses real database with TestDataFactory and real JWT tokens (mirrors
test_attendance_bulk_routes.py's harness conventions).
"""

from decimal import Decimal
from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import get_db
from backend.orm import ClientType
from backend.routes.attendance import router as attendance_router
from backend.tests.fixtures.factories import TestDataFactory
from backend.tests.fixtures.auth_fixtures import create_test_token
from backend.tests.conftest import clone_template_engine


def _create_test_app(db_session):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(attendance_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def labor_db():
    """Create a fresh database for each test."""
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


@pytest.fixture
def labor_setup(labor_db):
    """Create standard test data: one employee with labor_class='direct'."""
    db = labor_db

    client = TestDataFactory.create_client(
        db, client_id="LABOR-RT-TEST", client_name="Labor Route Test", client_type=ClientType.HOURLY_RATE
    )

    supervisor = TestDataFactory.create_user(
        db, user_id="lrt-super-001", username="lrt_supervisor", role="supervisor", client_id=client.client_id
    )

    shift = TestDataFactory.create_shift(
        db, client_id=client.client_id, shift_name="Labor Day Shift", start_time="06:00:00", end_time="14:00:00"
    )

    employee = TestDataFactory.create_employee(
        db, client_id=client.client_id, employee_name="Labor Employee 1", employee_code="LRT-EMP-001"
    )
    employee.labor_class = "direct"
    db.commit()

    app = _create_test_app(db)
    test_client = TestClient(app)
    supervisor_token = create_test_token(supervisor)

    return {
        "db": db,
        "test_client": test_client,
        "client": client,
        "supervisor": supervisor,
        "shift": shift,
        "employee": employee,
        "headers": {"Authorization": f"Bearer {supervisor_token}"},
    }


def _base_payload(s, **overrides):
    payload = {
        "client_id": s["client"].client_id,
        "employee_id": s["employee"].employee_id,
        "shift_date": date.today().isoformat(),
        "shift_id": s["shift"].shift_id,
        "scheduled_hours": "8.0",
        "actual_hours": "8.0",
        "is_absent": 0,
    }
    payload.update(overrides)
    return payload


def _dec(value) -> Decimal:
    """Compare-safe Decimal coercion regardless of whether the field serialized as a JSON number or string."""
    return Decimal(str(value))


class TestOTSplitCapture:
    """POST /api/attendance — OT split (normal/double/triple) invariants."""

    def test_create_with_valid_split(self, labor_setup):
        """actual 11 = 8 (normal) + 2 (double) + 1 (triple) -> 201, response echoes the split."""
        s = labor_setup
        payload = _base_payload(s, actual_hours="11.0", normal_hours="8.0", double_hours="2.0", triple_hours="1.0")

        response = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])

        assert response.status_code == 201
        data = response.json()
        assert _dec(data["normal_hours"]) == Decimal("8.0")
        assert _dec(data["double_hours"]) == Decimal("2.0")
        assert _dec(data["triple_hours"]) == Decimal("1.0")

    def test_split_sum_mismatch_422(self, labor_setup):
        """8 (normal) + 1 (double) + 0 (triple) = 9 != actual 8 -> 422 (validate_ot_split invariant)."""
        s = labor_setup
        payload = _base_payload(s, actual_hours="8.0", normal_hours="8.0", double_hours="1.0", triple_hours="0.0")

        response = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])

        assert response.status_code == 422

    def test_unsplit_entry_still_works(self, labor_setup):
        """No split fields supplied -> 201, split columns stay null (unsplit)."""
        s = labor_setup
        payload = _base_payload(s)

        response = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])

        assert response.status_code == 201
        data = response.json()
        assert data["normal_hours"] is None
        assert data["double_hours"] is None
        assert data["triple_hours"] is None


class TestAllocationCapture:
    """POST/PUT /api/attendance — hour-allocation ledger invariants + replace-on-write."""

    def test_create_with_allocations_and_derived(self, labor_setup):
        """actual 8; billed_production 5 + training 1 -> billed_hours 5.0,
        available = actual(8) - nonproductive_allocated(training=1) = 7.0.
        """
        s = labor_setup
        payload = _base_payload(
            s,
            actual_hours="8.0",
            allocations=[
                {"category": "billed_production", "hours": "5.0"},
                {"category": "training", "hours": "1.0"},
            ],
        )

        response = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])

        assert response.status_code == 201
        data = response.json()
        assert _dec(data["billed_hours"]) == Decimal("5.0")
        assert _dec(data["available_for_efficiency_hours"]) == Decimal("7.0")
        assert len(data["allocations"]) == 2

    def test_duplicate_category_422(self, labor_setup):
        """Same category twice -> 422 (validate_allocations duplicate-category invariant)."""
        s = labor_setup
        payload = _base_payload(
            s,
            actual_hours="8.0",
            allocations=[
                {"category": "training", "hours": "1.0"},
                {"category": "training", "hours": "2.0"},
            ],
        )

        response = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])

        assert response.status_code == 422

    def test_over_actual_422(self, labor_setup):
        """billed_production 5 + training 4 = 9 > actual 8 -> 422 (total-exceeds-actual invariant)."""
        s = labor_setup
        payload = _base_payload(
            s,
            actual_hours="8.0",
            allocations=[
                {"category": "billed_production", "hours": "5.0"},
                {"category": "training", "hours": "4.0"},
            ],
        )

        response = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])

        assert response.status_code == 422

    def test_replace_on_write(self, labor_setup):
        """PUT with a new allocations list replaces the prior one wholesale; an empty list clears it."""
        s = labor_setup
        payload = _base_payload(s, actual_hours="8.0", allocations=[{"category": "training", "hours": "1.0"}])
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        attendance_id = create_resp.json()["attendance_entry_id"]

        replace_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={"allocations": [{"category": "billed_production", "hours": "3.0"}]},
            headers=s["headers"],
        )
        assert replace_resp.status_code == 200
        replace_data = replace_resp.json()
        assert len(replace_data["allocations"]) == 1
        assert replace_data["allocations"][0]["category"] == "billed_production"
        assert _dec(replace_data["allocations"][0]["hours"]) == Decimal("3.0")

        clear_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={"allocations": []},
            headers=s["headers"],
        )
        assert clear_resp.status_code == 200
        assert clear_resp.json()["allocations"] == []

    def test_omitted_allocations_no_change(self, labor_setup):
        """PUT without the 'allocations' key leaves the existing ledger untouched."""
        s = labor_setup
        payload = _base_payload(s, actual_hours="8.0", allocations=[{"category": "training", "hours": "1.0"}])
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        attendance_id = create_resp.json()["attendance_entry_id"]

        update_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={"notes": "unrelated update, no allocations key"},
            headers=s["headers"],
        )

        assert update_resp.status_code == 200
        data = update_resp.json()
        assert len(data["allocations"]) == 1
        assert data["allocations"][0]["category"] == "training"
        assert _dec(data["allocations"][0]["hours"]) == Decimal("1.0")


class TestEffectiveLaborClass:
    """POST /api/attendance — effective_labor_class resolution (override vs. employee default)."""

    def test_override_beats_default(self, labor_setup):
        """Employee default is 'direct'; per-entry override 'indirect' wins."""
        s = labor_setup
        payload = _base_payload(s, labor_class_override="indirect")

        response = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])

        assert response.status_code == 201
        data = response.json()
        assert data["labor_class_override"] == "indirect"
        assert data["effective_labor_class"] == "indirect"

    def test_default_when_no_override(self, labor_setup):
        """No override supplied -> falls back to the employee's default ('direct')."""
        s = labor_setup
        payload = _base_payload(s)

        response = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])

        assert response.status_code == 201
        data = response.json()
        assert data["labor_class_override"] is None
        assert data["effective_labor_class"] == "direct"
