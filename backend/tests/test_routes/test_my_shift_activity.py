"""Regression test for F4 (e2e-sweep final review): GET /api/my-shift/summary's
recent_activity entries carried ONLY a hardcoded English `description` string
(e.g. "Quality check: {n} inspected, {d} defects"), rendered as-is under the
ES locale. Fix: the response now also carries a stable `activity_type` key
plus structured `params`, so the frontend can localize the sentence via i18n
(en+es) instead of displaying the server's English text. `description` is
kept for backward compat.

This test drives `get_my_shift_summary()` directly (real in-memory DB via
TestDataFactory, no HTTP layer) and asserts each activity's activity_type/
params match the underlying production/downtime/quality entry.
"""

from datetime import date, datetime, time

from backend.auth.jwt import ClientScope
from backend.routes.my_shift import get_my_shift_summary
from backend.tests.fixtures.factories import TestDataFactory

CLIENT_ID = "MYSHIFT-F4"


def test_recent_activity_carries_structured_activity_type_and_params(transactional_db):
    db = transactional_db
    today = date.today()

    TestDataFactory.create_client(db, client_id=CLIENT_ID)
    user = TestDataFactory.create_user(db, role="operator", client_id=CLIENT_ID)
    shift = TestDataFactory.create_shift(db, client_id=CLIENT_ID)
    product = TestDataFactory.create_product(db, client_id=CLIENT_ID)
    work_order = TestDataFactory.create_work_order(db, client_id=CLIENT_ID)

    TestDataFactory.create_production_entry(
        db,
        client_id=CLIENT_ID,
        product_id=product.product_id,
        shift_id=shift.shift_id,
        entered_by=user.user_id,
        production_date=today,
        units_produced=80,
        work_order_id=work_order.work_order_id,
    )
    TestDataFactory.create_downtime_entry(
        db,
        client_id=CLIENT_ID,
        reported_by=user.user_id,
        downtime_reason="Machine breakdown",
        shift_date=datetime.combine(today, time()),
        duration_minutes=20,
    )
    TestDataFactory.create_quality_entry(
        db,
        work_order_id=work_order.work_order_id,
        client_id=CLIENT_ID,
        inspector_id=user.user_id,
        inspection_date=today,
        units_inspected=10,
        units_defective=2,
    )
    db.commit()

    scope = ClientScope(client_ids=(CLIENT_ID,))
    result = get_my_shift_summary(
        shift_date=today,
        shift_id=None,
        operator_id=None,
        db=db,
        current_user=user,
        scope=scope,
    )

    by_type = {a.type: a for a in result.recent_activity}

    prod = by_type["production"]
    assert prod.activity_type == "production_logged"
    assert prod.params == {"units": 80, "work_order_id": work_order.work_order_id}
    assert prod.description  # backward-compat field still populated

    down = by_type["downtime"]
    assert down.activity_type == "downtime_logged"
    assert down.params == {"reason": "Machine breakdown", "minutes": 20}

    qual = by_type["quality"]
    assert qual.activity_type == "quality_checked"
    assert qual.params == {"inspected": 10, "defects": 2}
