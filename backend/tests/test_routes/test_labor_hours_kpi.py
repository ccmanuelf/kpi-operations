"""
Tests for GET /api/kpi/labor-hours (Cycle 3 PR-B Task 2).

Mirrors test_kpi_routes_real.py's harness (FastAPI app + dependency-override
TestClient). The exact-value scenario in TestLaborHoursSummary reuses the
derivation from test_calculations/test_labor_hours.py::TestSummarizeLaborHours
::test_summary_with_derivations verbatim (3 entries, 2 employees, one
labor_class_override) -- see that test's docstring for the full derivation;
this file cites only the resulting totals.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database import get_db
from backend.orm import ClientType
from backend.orm.attendance_hour_allocation import AttendanceHourAllocation
from backend.routes.kpi import router as kpi_router
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.factories import TestDataFactory


def create_test_app(db_session):
    """Create a FastAPI test app with overridden dependencies (no auth override --
    callers add app.dependency_overrides[get_current_user] themselves, or don't,
    to exercise the 401 path)."""
    app = FastAPI()
    app.include_router(kpi_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def lh_db():
    """Fresh database for each test."""
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


def _authed_client(db, user):
    from backend.auth.jwt import get_current_user

    app = create_test_app(db)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


class TestLaborHoursSummary:
    """Exact-value scenario, pinned by test_labor_hours.py's derivation."""

    def test_summary_exact_float_leaves(self, lh_db):
        """Same 3-entry scenario as
        TestSummarizeLaborHours.test_summary_with_derivations: entry A (E1
        direct, actual 10, split 8/2/0, billed_production 7 + training 1),
        entry B (E2 indirect, actual 8, unsplit, billed_production 8), entry
        C (E1 with labor_class_override='indirect', actual 8, split 8/0/0,
        no allocations). Derivation (cited verbatim from that test):
        totals = {scheduled 24, actual 26, normal 16, double 2, triple 0,
        billed 15, available_for_efficiency 25}. The route must return these
        as JSON floats (Decimal->float coercion), not strings.
        """
        db = lh_db
        client = TestDataFactory.create_client(db, client_id="LH-RT-CL", client_type=ClientType.HOURLY_RATE)
        shift = TestDataFactory.create_shift(db, client_id=client.client_id)
        admin = TestDataFactory.create_user(
            db, user_id="lh-admin-001", username="lh_admin", role="admin", client_id=None
        )

        e1 = TestDataFactory.create_employee(db, client_id=client.client_id, employee_name="E1 Direct")
        e1.labor_class = "direct"
        e2 = TestDataFactory.create_employee(db, client_id=client.client_id, employee_name="E2 Indirect")
        e2.labor_class = "indirect"
        db.flush()

        shift_date = date(2026, 8, 1)

        entry_a = TestDataFactory.create_attendance_entry(
            db,
            employee_id=e1.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("10.00"),
        )
        entry_a.normal_hours = Decimal("8.00")
        entry_a.double_hours = Decimal("2.00")
        entry_a.triple_hours = Decimal("0.00")
        entry_a.hour_allocations = [
            AttendanceHourAllocation(category="billed_production", hours=Decimal("7.00")),
            AttendanceHourAllocation(category="training", hours=Decimal("1.00")),
        ]

        entry_b = TestDataFactory.create_attendance_entry(
            db,
            employee_id=e2.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("8.00"),
        )
        entry_b.hour_allocations = [
            AttendanceHourAllocation(category="billed_production", hours=Decimal("8.00")),
        ]

        entry_c = TestDataFactory.create_attendance_entry(
            db,
            employee_id=e1.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("8.00"),
        )
        entry_c.normal_hours = Decimal("8.00")
        entry_c.double_hours = Decimal("0.00")
        entry_c.triple_hours = Decimal("0.00")
        entry_c.labor_class_override = "indirect"

        db.commit()

        http_client = _authed_client(db, admin)
        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01", "client_id": client.client_id},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["totals"] == {
            "scheduled": 24.0,
            "actual": 26.0,
            "normal": 16.0,
            "double": 2.0,
            "triple": 0.0,
            "billed": 15.0,
            "available_for_efficiency": 25.0,
        }
        assert data["by_labor_class"] == {
            "direct": {"actual": 10.0, "billed": 7.0, "available_for_efficiency": 9.0},
            "indirect": {"actual": 16.0, "billed": 8.0, "available_for_efficiency": 16.0},
            "unclassified": {"actual": 0.0, "billed": 0.0, "available_for_efficiency": 0.0},
        }
        assert data["by_category"] == {"billed_production": 15.0, "training": 1.0}
        assert data["entry_counts"] == {"total": 3, "with_split": 2, "with_allocations": 2}

        # Every leaf under totals/by_labor_class/by_category is a JSON number,
        # never a string -- pins the Decimal->float coercion at the boundary.
        for value in data["totals"].values():
            assert isinstance(value, float)
        for bucket in data["by_labor_class"].values():
            for value in bucket.values():
                assert isinstance(value, float)
        for value in data["by_category"].values():
            assert isinstance(value, float)


class TestLaborHoursClientScope:
    """Pins the #144 regression class: a leader assigned to multiple clients
    must get 200 aggregated data, never a 400 from scope.as_single()."""

    def test_leader_with_two_clients_no_client_id_aggregates(self, lh_db):
        db = lh_db
        client_one = TestDataFactory.create_client(db, client_id="LH-MULTI-ONE")
        client_two = TestDataFactory.create_client(db, client_id="LH-MULTI-TWO")
        shift_one = TestDataFactory.create_shift(db, client_id=client_one.client_id)
        shift_two = TestDataFactory.create_shift(db, client_id=client_two.client_id)
        emp_one = TestDataFactory.create_employee(db, client_id=client_one.client_id)
        emp_two = TestDataFactory.create_employee(db, client_id=client_two.client_id)

        shift_date = date(2026, 8, 1)
        TestDataFactory.create_attendance_entry(
            db,
            employee_id=emp_one.employee_id,
            client_id=client_one.client_id,
            shift_id=shift_one.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("8.00"),
        )
        TestDataFactory.create_attendance_entry(
            db,
            employee_id=emp_two.employee_id,
            client_id=client_two.client_id,
            shift_id=shift_two.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("8.00"),
        )

        leader = TestDataFactory.create_user(
            db,
            user_id="lh-leader-001",
            username="lh_leader",
            role="leader",
            client_id=f"{client_one.client_id},{client_two.client_id}",
        )
        db.commit()

        http_client = _authed_client(db, leader)
        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["totals"]["actual"] == 16.0
        assert data["entry_counts"]["total"] == 2


class TestLaborHoursEfficiencyAvailableBasis:
    """Fix round 1 (2026-08-06, USER RULING): the honest efficiency_available_basis
    lives here as a TRUE ratio of SUMS -- replaces the reverted dashboard
    bolt-on (backend/routes/kpi/calculations.py), which was live-proven 16
    points off (average-of-averages + mismatched scheduled sources)."""

    def test_ratio_of_sums_two_entries_each_side_earned_80_available_80(self, lh_db):
        """The defining property this class guards: TWO production entries
        with DIFFERENT per-entry ideal_cycle_time, and TWO attendance
        entries, summed on both sides before dividing -- never averaged
        per-entry then averaged again (the bug class that made the reverted
        dashboard variant 16 points off).

        Production: entry1 units=400 x ict=0.10 -> earned 40.00
                     entry2 units=200 x ict=0.20 -> earned 40.00
                     SUM earned_hours = 80.00
        Attendance: entryA actual=50.00, entryB actual=30.00, no allocations
                     -> available_for_efficiency = 50 + 30 = 80.00 (SUM)
        efficiency_available_basis = 80.00 / 80.00 * 100 = 100.00 -> 100.0
        """
        db = lh_db
        client = TestDataFactory.create_client(db, client_id="EAB-RATIO-CL")
        shift = TestDataFactory.create_shift(db, client_id=client.client_id)
        admin = TestDataFactory.create_user(
            db, user_id="eab-admin-001", username="eab_admin1", role="admin", client_id=None
        )
        product = TestDataFactory.create_product(db, client_id=client.client_id, ideal_cycle_time=None)
        e1 = TestDataFactory.create_employee(db, client_id=client.client_id)
        e2 = TestDataFactory.create_employee(db, client_id=client.client_id)
        db.flush()

        shift_date = date(2026, 8, 1)
        TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=admin.user_id,
            production_date=shift_date,
            units_produced=400,
            ideal_cycle_time=Decimal("0.10"),
        )
        TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=admin.user_id,
            production_date=shift_date,
            units_produced=200,
            ideal_cycle_time=Decimal("0.20"),
        )

        TestDataFactory.create_attendance_entry(
            db,
            employee_id=e1.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("50.00"),
            actual_hours=Decimal("50.00"),
        )
        TestDataFactory.create_attendance_entry(
            db,
            employee_id=e2.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("30.00"),
            actual_hours=Decimal("30.00"),
        )
        db.commit()

        http_client = _authed_client(db, admin)
        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01", "client_id": client.client_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["earned_hours"] == 80.0
        assert data["totals"]["available_for_efficiency"] == 80.0
        assert data["excluded_entries"] == 0
        assert data["efficiency_available_basis"] == 100.0

    def test_ratio_with_training_allocation_yields_75(self, lh_db):
        """Single-entry hand-math with a non-trivial (!= 100) result:
        earned = 600 units x 0.10 = 60.00
        available = actual(90.00) - training(10.00) = 80.00
        efficiency_available_basis = 60.00 / 80.00 * 100 = 75.00 -> 75.0
        """
        db = lh_db
        client = TestDataFactory.create_client(db, client_id="EAB-TRAIN-CL")
        shift = TestDataFactory.create_shift(db, client_id=client.client_id)
        admin = TestDataFactory.create_user(
            db, user_id="eab-admin-002", username="eab_admin2", role="admin", client_id=None
        )
        product = TestDataFactory.create_product(db, client_id=client.client_id, ideal_cycle_time=None)
        employee = TestDataFactory.create_employee(db, client_id=client.client_id)
        db.flush()

        shift_date = date(2026, 8, 1)
        TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=admin.user_id,
            production_date=shift_date,
            units_produced=600,
            ideal_cycle_time=Decimal("0.10"),
        )

        attendance_entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("90.00"),
            actual_hours=Decimal("90.00"),
        )
        attendance_entry.hour_allocations = [
            AttendanceHourAllocation(category="training", hours=Decimal("10.00")),
        ]
        db.commit()

        http_client = _authed_client(db, admin)
        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01", "client_id": client.client_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["earned_hours"] == 60.0
        assert data["totals"]["available_for_efficiency"] == 80.0
        assert data["efficiency_available_basis"] == 75.0

    def test_excluded_entries_surfaced_and_not_silently_dropped(self, lh_db):
        """One entry has no ideal_cycle_time anywhere (entry nor product):
        excluded from earned_hours, and excluded_entries == 1 tells the
        caller the ratio isn't complete -- never silently understates it."""
        db = lh_db
        client = TestDataFactory.create_client(db, client_id="EAB-EXCL-CL")
        shift = TestDataFactory.create_shift(db, client_id=client.client_id)
        admin = TestDataFactory.create_user(
            db, user_id="eab-admin-003", username="eab_admin3", role="admin", client_id=None
        )
        product_known = TestDataFactory.create_product(
            db, client_id=client.client_id, product_code="EAB-EXCL-P1", ideal_cycle_time=Decimal("0.10")
        )
        product_unknown = TestDataFactory.create_product(
            db, client_id=client.client_id, product_code="EAB-EXCL-P2", ideal_cycle_time=None
        )
        employee = TestDataFactory.create_employee(db, client_id=client.client_id)
        db.flush()

        shift_date = date(2026, 8, 1)
        TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product_known.product_id,
            shift_id=shift.shift_id,
            entered_by=admin.user_id,
            production_date=shift_date,
            units_produced=400,
            ideal_cycle_time=None,
        )
        TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product_unknown.product_id,
            shift_id=shift.shift_id,
            entered_by=admin.user_id,
            production_date=shift_date,
            units_produced=999,
            ideal_cycle_time=None,
        )
        TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("40.00"),
            actual_hours=Decimal("40.00"),
        )
        db.commit()

        http_client = _authed_client(db, admin)
        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01", "client_id": client.client_id},
        )

        assert response.status_code == 200
        data = response.json()
        # product_known: 400 x 0.10 = 40.00; product_unknown excluded
        assert data["earned_hours"] == 40.0
        assert data["excluded_entries"] == 1
        assert data["efficiency_available_basis"] == 100.0

    def test_no_attendance_data_is_none(self, lh_db):
        """Production entries exist (earned_hours computable) but zero
        AttendanceEntry rows in the window -> efficiency_available_basis
        must be None, never a fabricated denominator."""
        db = lh_db
        client = TestDataFactory.create_client(db, client_id="EAB-NOATT-CL")
        shift = TestDataFactory.create_shift(db, client_id=client.client_id)
        admin = TestDataFactory.create_user(
            db, user_id="eab-admin-004", username="eab_admin4", role="admin", client_id=None
        )
        product = TestDataFactory.create_product(db, client_id=client.client_id, ideal_cycle_time=Decimal("0.10"))
        db.flush()

        shift_date = date(2026, 8, 1)
        TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=admin.user_id,
            production_date=shift_date,
            units_produced=400,
        )
        db.commit()

        http_client = _authed_client(db, admin)
        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01", "client_id": client.client_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["earned_hours"] == 40.0
        assert data["efficiency_available_basis"] is None

    def test_available_hours_zero_is_none_not_div_by_zero(self, lh_db):
        """Attendance exists but is fully allocated to non-productive
        categories -> available_for_efficiency == 0 -> None, not a crash or
        a fabricated 0/0 ratio."""
        db = lh_db
        client = TestDataFactory.create_client(db, client_id="EAB-ZERO-CL")
        shift = TestDataFactory.create_shift(db, client_id=client.client_id)
        admin = TestDataFactory.create_user(
            db, user_id="eab-admin-005", username="eab_admin5", role="admin", client_id=None
        )
        product = TestDataFactory.create_product(db, client_id=client.client_id, ideal_cycle_time=Decimal("0.10"))
        employee = TestDataFactory.create_employee(db, client_id=client.client_id)
        db.flush()

        shift_date = date(2026, 8, 1)
        TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=admin.user_id,
            production_date=shift_date,
            units_produced=400,
        )

        attendance_entry = TestDataFactory.create_attendance_entry(
            db,
            employee_id=employee.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("5.00"),
            actual_hours=Decimal("5.00"),
        )
        attendance_entry.hour_allocations = [
            AttendanceHourAllocation(category="training", hours=Decimal("5.00")),
        ]
        db.commit()

        http_client = _authed_client(db, admin)
        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01", "client_id": client.client_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["totals"]["available_for_efficiency"] == 0.0
        assert data["efficiency_available_basis"] is None

    def test_multi_client_aggregation_sums_earned_and_available_across_clients(self, lh_db):
        """Leader with two clients, no client_id -> earned_hours and
        available_for_efficiency (and thus efficiency_available_basis)
        aggregate across BOTH clients (the #144 regression class: never
        scope.as_single() a multi-client leader down to a 400).

        Client one: entry 100u x ict=0.10 = 10.00 earned; attendance actual 10.00, no alloc -> available 10.00
        Client two: entry 100u x ict=0.10 = 10.00 earned; attendance actual 10.00, no alloc -> available 10.00
        Aggregated: earned 20.00 / available 20.00 * 100 = 100.0
        """
        db = lh_db
        client_one = TestDataFactory.create_client(db, client_id="EAB-MULTI-ONE")
        client_two = TestDataFactory.create_client(db, client_id="EAB-MULTI-TWO")
        shift_one = TestDataFactory.create_shift(db, client_id=client_one.client_id)
        shift_two = TestDataFactory.create_shift(db, client_id=client_two.client_id)
        product_one = TestDataFactory.create_product(
            db, client_id=client_one.client_id, ideal_cycle_time=Decimal("0.10")
        )
        product_two = TestDataFactory.create_product(
            db, client_id=client_two.client_id, ideal_cycle_time=Decimal("0.10")
        )
        emp_one = TestDataFactory.create_employee(db, client_id=client_one.client_id)
        emp_two = TestDataFactory.create_employee(db, client_id=client_two.client_id)

        shift_date = date(2026, 8, 1)
        TestDataFactory.create_production_entry(
            db,
            client_id=client_one.client_id,
            product_id=product_one.product_id,
            shift_id=shift_one.shift_id,
            entered_by="tester",
            production_date=shift_date,
            units_produced=100,
        )
        TestDataFactory.create_production_entry(
            db,
            client_id=client_two.client_id,
            product_id=product_two.product_id,
            shift_id=shift_two.shift_id,
            entered_by="tester",
            production_date=shift_date,
            units_produced=100,
        )
        TestDataFactory.create_attendance_entry(
            db,
            employee_id=emp_one.employee_id,
            client_id=client_one.client_id,
            shift_id=shift_one.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("10.00"),
            actual_hours=Decimal("10.00"),
        )
        TestDataFactory.create_attendance_entry(
            db,
            employee_id=emp_two.employee_id,
            client_id=client_two.client_id,
            shift_id=shift_two.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("10.00"),
            actual_hours=Decimal("10.00"),
        )

        leader = TestDataFactory.create_user(
            db,
            user_id="eab-leader-001",
            username="eab_leader",
            role="leader",
            client_id=f"{client_one.client_id},{client_two.client_id}",
        )
        db.commit()

        http_client = _authed_client(db, leader)
        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["earned_hours"] == 20.0
        assert data["totals"]["available_for_efficiency"] == 20.0
        assert data["efficiency_available_basis"] == 100.0


class TestLaborHoursDateValidation:
    def test_reversed_date_range_is_400(self, lh_db):
        db = lh_db
        admin = TestDataFactory.create_user(
            db, user_id="lh-admin-002", username="lh_admin2", role="admin", client_id=None
        )
        db.commit()

        http_client = _authed_client(db, admin)
        start = date.today()
        end = start - timedelta(days=1)
        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )

        assert response.status_code == 400


class TestLaborHoursUnauthenticated:
    def test_unauthenticated_get_is_401(self, lh_db):
        app = create_test_app(lh_db)

        def override_get_db():
            try:
                yield lh_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        http_client = TestClient(app)

        response = http_client.get(
            "/api/kpi/labor-hours",
            params={"start_date": "2026-08-01", "end_date": "2026-08-01"},
        )

        assert response.status_code == 401
