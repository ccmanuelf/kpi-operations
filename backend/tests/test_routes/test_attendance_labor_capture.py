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

    def test_replace_on_write_resubmit_identical_list(self, labor_setup):
        """Regression (fix round 1, CRITICAL): resubmitting the exact same allocations list
        must not crash with an IntegrityError on UniqueConstraint(entry, category). Without
        the clear-then-flush fix, SQLAlchemy could flush the new INSERT before the old row's
        delete-orphan DELETE, since both rows share the 'training' category.
        """
        s = labor_setup
        payload = _base_payload(s, actual_hours="8.0", allocations=[{"category": "training", "hours": "1.0"}])
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        attendance_id = create_resp.json()["attendance_entry_id"]

        resubmit_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={"allocations": [{"category": "training", "hours": "1.0"}]},
            headers=s["headers"],
        )

        assert resubmit_resp.status_code == 200
        data = resubmit_resp.json()
        assert len(data["allocations"]) == 1
        assert data["allocations"][0]["category"] == "training"
        assert _dec(data["allocations"][0]["hours"]) == Decimal("1.0")

    def test_replace_on_write_same_category_new_hours(self, labor_setup):
        """Regression (fix round 1, CRITICAL): same category, different hours -> 200 with the
        new hours (not a crash, not the stale value)."""
        s = labor_setup
        payload = _base_payload(s, actual_hours="8.0", allocations=[{"category": "training", "hours": "1.0"}])
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        attendance_id = create_resp.json()["attendance_entry_id"]

        update_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={"allocations": [{"category": "training", "hours": "3.0"}]},
            headers=s["headers"],
        )

        assert update_resp.status_code == 200
        data = update_resp.json()
        assert len(data["allocations"]) == 1
        assert data["allocations"][0]["category"] == "training"
        assert _dec(data["allocations"][0]["hours"]) == Decimal("3.0")


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


class TestListAndGetEnrichment:
    """Regression (fix round 1, IMPORTANT / Task 7 blocker): GET /api/attendance (the grid's
    feed) and GET /api/attendance/{id} must return the real derived values, not the response
    schema's bare defaults (allocations=[], billed_hours=0, available_for_efficiency_hours=None,
    effective_labor_class=None) that a raw, unenriched ORM object would produce.
    """

    def _create_seeded_entry(self, s):
        payload = _base_payload(
            s,
            actual_hours="8.0",
            allocations=[
                {"category": "billed_production", "hours": "5.0"},
                {"category": "training", "hours": "1.0"},
            ],
        )
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        return create_resp.json()["attendance_entry_id"]

    def test_get_by_id_returns_real_derived_values(self, labor_setup):
        s = labor_setup
        attendance_id = self._create_seeded_entry(s)

        get_resp = s["test_client"].get(f"/api/attendance/{attendance_id}", headers=s["headers"])

        assert get_resp.status_code == 200
        data = get_resp.json()
        assert len(data["allocations"]) == 2
        assert _dec(data["billed_hours"]) == Decimal("5.0")
        assert _dec(data["available_for_efficiency_hours"]) == Decimal("7.0")
        assert data["effective_labor_class"] == "direct"

    def test_list_returns_real_derived_values(self, labor_setup):
        s = labor_setup
        attendance_id = self._create_seeded_entry(s)

        list_resp = s["test_client"].get(
            "/api/attendance", params={"employee_id": s["employee"].employee_id}, headers=s["headers"]
        )

        assert list_resp.status_code == 200
        records = list_resp.json()
        record = next(r for r in records if r["attendance_entry_id"] == attendance_id)
        assert len(record["allocations"]) == 2
        assert _dec(record["billed_hours"]) == Decimal("5.0")
        assert _dec(record["available_for_efficiency_hours"]) == Decimal("7.0")
        assert record["effective_labor_class"] == "direct"


class TestBulkCreateOTSplitValidation:
    """Regression (fix round 1, IMPORTANT): POST /api/attendance/bulk must enforce the OT
    split invariant per-row (a bad split must not persist silently, bypassing validate_ot_split).
    """

    def test_valid_and_invalid_split_rows_partitioned(self, labor_setup):
        """One valid-split row + one bad-split row -> the valid one persists, the bad one is
        reported failed with its own error entry (bulk is per-row, not all-or-nothing)."""
        s = labor_setup
        valid_row = _base_payload(s, actual_hours="8.0", normal_hours="8.0", double_hours="0.0", triple_hours="0.0")
        invalid_row = _base_payload(s, actual_hours="8.0", normal_hours="8.0", double_hours="1.0", triple_hours="0.0")

        response = s["test_client"].post("/api/attendance/bulk", json=[valid_row, invalid_row], headers=s["headers"])

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 1
        assert data["failed"] == 1
        assert data["errors"][0]["index"] == 1
        assert len(data["created_ids"]) == 1


class TestUpdatePartialNullSplit:
    """Regression (fix round 3, IMPORTANT): PUT with one OT-split tier explicitly
    nulled and the other two omitted must clear the WHOLE split, not leave the
    omitted tiers at their stale DB values. update_data is built from
    exclude_unset, so only the tier(s) actually in the request body would land
    in it; validate_ot_split resolves the omitted tiers to None too and returns
    None (its "unsplit, nothing to do" signal) — without the fix, that just
    means the omitted tiers' stale values pass through untouched.
    """

    def test_partial_null_forces_full_clear(self, labor_setup):
        """Entry starts fully split (10 = 8 + 2 + 0); PUT {"normal_hours": null}
        alone must null out ALL three columns, not just normal_hours."""
        s = labor_setup
        payload = _base_payload(s, actual_hours="10.0", normal_hours="8.0", double_hours="2.0", triple_hours="0.0")
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        attendance_id = create_resp.json()["attendance_entry_id"]

        update_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={"normal_hours": None},
            headers=s["headers"],
        )

        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["normal_hours"] is None
        assert data["double_hours"] is None
        assert data["triple_hours"] is None

    def test_explicit_null_one_tier_with_values_on_others_normalizes(self, labor_setup):
        """All three keys sent, one explicit null: normal=null defaults to 0,
        double=3 + triple=5 sums to actual_hours(8) -> 200, normalized split."""
        s = labor_setup
        payload = _base_payload(s, actual_hours="8.0", normal_hours="8.0", double_hours="0.0", triple_hours="0.0")
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        attendance_id = create_resp.json()["attendance_entry_id"]

        update_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={"normal_hours": None, "double_hours": "3.0", "triple_hours": "5.0"},
            headers=s["headers"],
        )

        assert update_resp.status_code == 200
        data = update_resp.json()
        assert _dec(data["normal_hours"]) == Decimal("0")
        assert _dec(data["double_hours"]) == Decimal("3.0")
        assert _dec(data["triple_hours"]) == Decimal("5.0")

    def test_explicit_null_one_tier_with_values_mismatch_422(self, labor_setup):
        """Same shape as above, but double+triple no longer sum to actual_hours(8)
        once normal defaults to 0 -> 422 (validate_ot_split invariant), not a
        silently-accepted partial update."""
        s = labor_setup
        payload = _base_payload(s, actual_hours="8.0", normal_hours="8.0", double_hours="0.0", triple_hours="0.0")
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        attendance_id = create_resp.json()["attendance_entry_id"]

        update_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={"normal_hours": None, "double_hours": "3.0", "triple_hours": "10.0"},
            headers=s["headers"],
        )

        assert update_resp.status_code == 422


class TestBulkCreateRejectsAllocations:
    """Regression (fix round 3, IMPORTANT): POST /api/attendance/bulk previously
    silently dropped `allocations` (excluded from model_dump with no error) —
    a row that asked for allocations would persist without them and report
    success. Now fails that row explicitly, per-row (bulk is not all-or-nothing).
    """

    def test_row_with_allocations_fails_sibling_persists(self, labor_setup):
        s = labor_setup
        row_with_allocations = _base_payload(
            s, actual_hours="8.0", allocations=[{"category": "training", "hours": "1.0"}]
        )
        clean_row = _base_payload(s, actual_hours="8.0")

        response = s["test_client"].post(
            "/api/attendance/bulk", json=[row_with_allocations, clean_row], headers=s["headers"]
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 1
        assert data["failed"] == 1
        assert data["errors"][0]["index"] == 0
        assert data["errors"][0]["error"] == (
            "allocations are not supported on the bulk endpoint — use single create/update"
        )
        assert len(data["created_ids"]) == 1


class TestUpdateActualHours:
    """Regression (fix round 3, IMPORTANT): AttendanceRecordUpdate previously had
    no working actual_hours field (`actual_hours_worked` never mapped onto the
    ORM's `actual_hours` attribute — the update loop is a blind hasattr-gated
    setattr, so the name mismatch silently no-opped), and the OT split/
    allocations invariants validated against the STALE stored actual_hours even
    when the same PUT changed it — a grid-style edit sending a consistent new
    actual_hours + split together would 422 against the old value.
    """

    def test_actual_hours_change_with_matching_split_persists_both(self, labor_setup):
        s = labor_setup
        payload = _base_payload(s, actual_hours="8.0", normal_hours="8.0", double_hours="0.0", triple_hours="0.0")
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        attendance_id = create_resp.json()["attendance_entry_id"]

        update_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={
                "actual_hours": "9.0",
                "normal_hours": "9.0",
                "double_hours": "0.0",
                "triple_hours": "0.0",
            },
            headers=s["headers"],
        )

        assert update_resp.status_code == 200
        data = update_resp.json()
        assert _dec(data["actual_hours"]) == Decimal("9.0")
        assert _dec(data["normal_hours"]) == Decimal("9.0")

    def test_actual_hours_change_with_matching_allocations_persists_both(self, labor_setup):
        """Same fix, allocations side: allocations validate against the NEW
        actual_hours in the same request, not the stale stored value."""
        s = labor_setup
        payload = _base_payload(s, actual_hours="8.0")
        create_resp = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])
        assert create_resp.status_code == 201
        attendance_id = create_resp.json()["attendance_entry_id"]

        update_resp = s["test_client"].put(
            f"/api/attendance/{attendance_id}",
            json={
                "actual_hours": "9.0",
                "allocations": [{"category": "billed_production", "hours": "9.0"}],
            },
            headers=s["headers"],
        )

        assert update_resp.status_code == 200
        data = update_resp.json()
        assert _dec(data["actual_hours"]) == Decimal("9.0")
        assert _dec(data["billed_hours"]) == Decimal("9.0")


class TestAllocationsRequireActualHoursMessage:
    """Regression (fix round 3, Minor): allocations sent against a 0/unset
    actual_hours previously raised the same "allocations exceed actual_hours"
    message as a genuine over-actual case, which misleads the caller into
    thinking a real actual_hours value was exceeded rather than never provided.
    """

    def test_message_is_require_not_exceed(self, labor_setup):
        s = labor_setup
        payload = _base_payload(s, actual_hours="0", allocations=[{"category": "training", "hours": "1.0"}])

        response = s["test_client"].post("/api/attendance", json=payload, headers=s["headers"])

        assert response.status_code == 422
        assert response.json()["detail"] == "allocations require actual_hours"
