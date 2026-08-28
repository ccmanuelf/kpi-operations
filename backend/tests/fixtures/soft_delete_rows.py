"""One row of each auto-filtered transaction table, on a real Alembic schema.

Shared by the endpoint round-trip suite (tests/test_routes/
test_transaction_soft_delete.py) and the ORM-level enforcement suite
(tests/test_db/test_soft_delete_auto_filter.py) so both prove the same rows.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.orm import ClientType
from backend.tests.fixtures.factories import TestDataFactory

#: table name -> primary-key attribute, for the seven auto-filtered models.
PK_ATTR: Dict[str, str] = {
    "ATTENDANCE_ENTRY": "attendance_entry_id",
    "DEFECT_DETAIL": "defect_detail_id",
    "DOWNTIME_ENTRY": "downtime_entry_id",
    "HOLD_ENTRY": "hold_entry_id",
    "PRODUCTION_ENTRY": "production_entry_id",
    "QUALITY_ENTRY": "quality_entry_id",
    "WORK_ORDER": "work_order_id",
}


def build_transaction_rows(session: Session, client_id: str = "SD-CLIENT") -> Dict[str, Any]:
    """Create the supporting graph plus exactly one row per auto-filtered table.

    Returns a dict with the seven rows keyed by table name, plus the ``client``,
    ``supervisor``, ``employee``, ``product`` and ``shift`` they hang off.
    """
    TestDataFactory.reset_counters()

    client = TestDataFactory.create_client(
        session, client_id=client_id, client_name=f"{client_id} Co", client_type=ClientType.HOURLY_RATE
    )
    supervisor = TestDataFactory.create_user(
        session,
        user_id=f"{client_id}-super",
        username=f"{client_id}_supervisor",
        role="supervisor",
        client_id=client.client_id,
    )
    employee = TestDataFactory.create_employee(session, client_id=client.client_id, employee_name="SD Worker")
    product = TestDataFactory.create_product(
        session, client_id=client.client_id, product_code=f"{client_id}-P1", product_name="SD Product"
    )
    shift = TestDataFactory.create_shift(
        session, client_id=client.client_id, shift_name="SD Shift", start_time="06:00:00", end_time="14:00:00"
    )
    session.flush()

    work_order = TestDataFactory.create_work_order(session, client_id=client.client_id)
    production = TestDataFactory.create_production_entry(
        session,
        client_id=client.client_id,
        product_id=product.product_id,
        shift_id=shift.shift_id,
        entered_by=supervisor.user_id,
        production_date=date.today(),
    )
    hold = TestDataFactory.create_hold_entry(
        session, work_order_id=work_order.work_order_id, client_id=client.client_id, created_by=supervisor.user_id
    )
    downtime = TestDataFactory.create_downtime_entry(
        session,
        client_id=client.client_id,
        reported_by=supervisor.user_id,
        work_order_id=work_order.work_order_id,
        shift_date=datetime.now(tz=timezone.utc),
    )
    attendance = TestDataFactory.create_attendance_entry(
        session, employee_id=employee.employee_id, client_id=client.client_id, shift_id=shift.shift_id
    )
    quality = TestDataFactory.create_quality_entry(
        session,
        work_order_id=work_order.work_order_id,
        client_id=client.client_id,
        inspector_id=supervisor.user_id,
    )
    defect = TestDataFactory.create_defect_detail(
        session, quality_entry_id=quality.quality_entry_id, client_id_fk=client.client_id
    )
    session.commit()

    return {
        "client": client,
        "supervisor": supervisor,
        "employee": employee,
        "product": product,
        "shift": shift,
        "ATTENDANCE_ENTRY": attendance,
        "DEFECT_DETAIL": defect,
        "DOWNTIME_ENTRY": downtime,
        "HOLD_ENTRY": hold,
        "PRODUCTION_ENTRY": production,
        "QUALITY_ENTRY": quality,
        "WORK_ORDER": work_order,
    }
