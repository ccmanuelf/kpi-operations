"""Guard: KPI numeric fields that divide a SQL-aggregate must serialize as JSON
numbers (Python float), not Decimal->str. The original defect is MariaDB-only
(SQLite returns int/float already), so these pass on SQLite before and after the
fix — they are a regression contract, not a red->green reproduction. Live MariaDB
verification is the real proof (see the deploy step)."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.factories import TestDataFactory
from backend.main import app
from backend.orm.quality_entry import QualityEntry
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.work_order import WorkOrder, WorkOrderStatus


@pytest.fixture
def db_session(transactional_db):
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(db_session):
    admin = TestDataFactory.create_user(db_session, username="serial_admin", role="admin")
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def _num(v):
    # a JSON number decodes to int/float in Python; a Decimal->str bug decodes to str
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def test_quality_trend_value_is_number(client, db_session):
    db_session.add(
        QualityEntry(
            quality_entry_id="QE1",
            client_id="C1",
            work_order_id="WO1",
            shift_date=datetime(2026, 6, 10, 8),
            units_inspected=100,
            units_passed=90,
            units_defective=10,
            total_defects_count=10,
        )
    )
    db_session.commit()
    body = client.get("/api/kpi/quality/trend", params={"start_date": "2026-06-10", "end_date": "2026-06-10"}).json()
    assert body and _num(body[0]["value"])


def test_otd_trend_value_is_number(client, db_session):
    db_session.add(
        WorkOrder(
            work_order_id="WO1",
            client_id="C1",
            style_model="M1",
            planned_quantity=10,
            status=WorkOrderStatus.SHIPPED,
            required_date=datetime(2026, 6, 10, 8),
            actual_delivery_date=datetime(2026, 6, 12, 8),
        )
    )
    db_session.commit()
    body = client.get(
        "/api/kpi/on-time-delivery/trend", params={"start_date": "2026-06-10", "end_date": "2026-06-10"}
    ).json()
    assert body and _num(body[0]["value"])


def test_absenteeism_trend_value_is_number(client, db_session):
    db_session.add(
        AttendanceEntry(
            attendance_entry_id="AE1",
            client_id="C1",
            employee_id=1,
            shift_date=datetime(2026, 6, 10, 8),
            scheduled_hours=8,
            is_absent=1,
            absence_hours=8,
        )
    )
    db_session.commit()
    body = client.get(
        "/api/kpi/absenteeism/trend", params={"start_date": "2026-06-10", "end_date": "2026-06-10"}
    ).json()
    assert body and _num(body[0]["value"])


def test_otd_by_client_percentage_is_number(client, db_session):
    # otd_by_client INNER JOINs WorkOrder to Client; a Client row is required or the
    # query returns zero rows (revealed by an empty response body during collection).
    TestDataFactory.create_client(db_session, client_id="C1")
    db_session.add(
        WorkOrder(
            work_order_id="WO1",
            client_id="C1",
            style_model="M1",
            planned_quantity=10,
            status=WorkOrderStatus.SHIPPED,
            required_date=datetime(2026, 6, 10, 8),
            actual_delivery_date=datetime(2026, 6, 12, 8),
        )
    )
    db_session.commit()
    body = client.get("/api/kpi/otd/by-client", params={"start_date": "2026-06-01", "end_date": "2026-06-30"}).json()
    assert body and _num(body[0]["otd_percentage"])


def test_quality_by_product_fpy_is_number(client, db_session):
    db_session.add(
        WorkOrder(
            work_order_id="WO1", client_id="C1", style_model="M1", planned_quantity=10, status=WorkOrderStatus.SHIPPED
        )
    )
    db_session.add(
        QualityEntry(
            quality_entry_id="QE1",
            client_id="C1",
            work_order_id="WO1",
            shift_date=datetime(2026, 6, 10, 8),
            units_inspected=100,
            units_passed=90,
            units_defective=10,
            total_defects_count=10,
        )
    )
    db_session.commit()
    body = client.get(
        "/api/quality/kpi/by-product", params={"start_date": "2026-06-10", "end_date": "2026-06-10"}
    ).json()
    assert body and _num(body[0]["fpy"])
