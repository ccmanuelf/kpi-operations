"""Regression: DateTime-column vs date-midnight boundary bug (whole class).

A `DateTime` column compared to a bare date (or its `.isoformat()`) on the
`<= end_date` bound drops same-day rows that carry a time component, e.g.
`2026-06-10 08:00 <= 2026-06-10 (00:00)` -> False. These tests seed a row
timestamped on `end_date` at 08:00 and query the range `start_date ==
end_date == that day`, asserting the row IS included. Pre-fix this is a
genuine red (0 rows) on SQLite; post-fix (datetime.combine bounds) it is
green (>=1 row).
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.factories import TestDataFactory
from backend.main import app
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.defect_detail import DefectType
from backend.orm.production_entry import ProductionEntry
from backend.orm.quality_entry import QualityEntry


@pytest.fixture
def db_session(transactional_db):
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(db_session):
    admin = TestDataFactory.create_user(db_session, username="boundary_admin", role="admin")
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


SAME_DAY = date(2026, 6, 10)
INTRADAY = datetime(2026, 6, 10, 8, 0, 0)


def test_defects_by_type_includes_same_day_intraday_row(client, db_session):
    """pareto.py get_defects_by_type: .isoformat() bound variant."""
    test_client = TestDataFactory.create_client(db_session)
    work_order = TestDataFactory.create_work_order(db_session, client_id=test_client.client_id)
    quality_entry = QualityEntry(
        quality_entry_id="QE-BOUND-1",
        client_id=test_client.client_id,
        work_order_id=work_order.work_order_id,
        shift_date=INTRADAY,
        units_inspected=100,
        units_passed=90,
        units_defective=10,
        total_defects_count=10,
    )
    db_session.add(quality_entry)
    db_session.flush()
    TestDataFactory.create_defect_detail(
        db_session,
        quality_entry_id=quality_entry.quality_entry_id,
        defect_type=DefectType.STITCHING,
        defect_count=3,
        client_id_fk=test_client.client_id,
    )
    db_session.commit()

    body = client.get(
        "/api/quality/kpi/defects-by-type",
        params={"start_date": SAME_DAY.isoformat(), "end_date": SAME_DAY.isoformat()},
    ).json()

    assert body, "same-day 08:00 defect row must be included when start_date == end_date"
    assert any(r["defect_type"] == DefectType.STITCHING.value for r in body)


def test_efficiency_by_shift_includes_same_day_intraday_row(client, db_session):
    """efficiency.py get_efficiency_by_shift: bare-date bound variant."""
    test_client = TestDataFactory.create_client(db_session)
    product = TestDataFactory.create_product(db_session, client_id=test_client.client_id)
    shift = TestDataFactory.create_shift(db_session, client_id=test_client.client_id)
    production_entry = ProductionEntry(
        production_entry_id="PE-BOUND-1",
        client_id=test_client.client_id,
        product_id=product.product_id,
        shift_id=shift.shift_id,
        entered_by="tester",
        production_date=INTRADAY,
        shift_date=INTRADAY,
        units_produced=500,
        employees_assigned=5,
        employees_present=5,
        run_time_hours=8,
        defect_count=0,
        scrap_count=0,
        rework_count=0,
    )
    db_session.add(production_entry)
    db_session.commit()

    body = client.get(
        "/api/kpi/efficiency/by-shift",
        params={"start_date": SAME_DAY.isoformat(), "end_date": SAME_DAY.isoformat()},
    ).json()

    assert body, "same-day 08:00 production row must be included when start_date == end_date"


def test_attendance_list_includes_same_day_intraday_row(client, db_session):
    """crud/attendance.py get_attendance_records (guarded if start_date:/if end_date:)."""
    test_client = TestDataFactory.create_client(db_session)
    attendance_entry = AttendanceEntry(
        attendance_entry_id="AE-BOUND-1",
        client_id=test_client.client_id,
        employee_id=1,
        shift_date=INTRADAY,
        scheduled_hours=8,
        is_absent=0,
        absence_hours=0,
    )
    db_session.add(attendance_entry)
    db_session.commit()

    body = client.get(
        "/api/attendance",
        params={"start_date": SAME_DAY.isoformat(), "end_date": SAME_DAY.isoformat()},
    ).json()

    assert body, "same-day 08:00 attendance row must be included when start_date == end_date"


def test_calculate_otd_includes_same_day_intraday_row(db_session):
    """calculations/otd.py calculate_otd: bare-date bound in and_(...), called directly."""
    from backend.calculations.otd import calculate_otd

    test_client = TestDataFactory.create_client(db_session)
    product = TestDataFactory.create_product(db_session, client_id=test_client.client_id)
    shift = TestDataFactory.create_shift(db_session, client_id=test_client.client_id)
    production_entry = ProductionEntry(
        production_entry_id="PE-BOUND-2",
        client_id=test_client.client_id,
        product_id=product.product_id,
        shift_id=shift.shift_id,
        entered_by="tester",
        production_date=INTRADAY,
        shift_date=INTRADAY,
        units_produced=500,
        employees_assigned=5,
        employees_present=5,
        run_time_hours=8,
        defect_count=0,
        scrap_count=0,
        rework_count=0,
    )
    db_session.add(production_entry)
    db_session.commit()

    _otd_percentage, _on_time_count, total_count = calculate_otd(db_session, start_date=SAME_DAY, end_date=SAME_DAY)

    assert total_count >= 1, "same-day 08:00 production row must be included when start_date == end_date"
