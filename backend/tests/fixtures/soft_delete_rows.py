"""One row of each auto-filtered transaction table, on a real Alembic schema.

Shared by the endpoint round-trip suite (tests/test_routes/
test_transaction_soft_delete.py) and the ORM-level enforcement suite
(tests/test_db/test_soft_delete_auto_filter.py) so both prove the same rows.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.orm import ClientType
from backend.orm.alert import Alert
from backend.tests.fixtures.factories import TestDataFactory

#: table name -> primary-key attribute, for the eleven auto-filtered models.
PK_ATTR: Dict[str, str] = {
    "ATTENDANCE_ENTRY": "attendance_entry_id",
    "DEFECT_DETAIL": "defect_detail_id",
    "DOWNTIME_ENTRY": "downtime_entry_id",
    "FLOATING_POOL": "pool_id",
    "HOLD_ENTRY": "hold_entry_id",
    "JOB": "job_id",
    "PART_OPPORTUNITIES": "part_number",
    "PRODUCTION_ENTRY": "production_entry_id",
    "QUALITY_ENTRY": "quality_entry_id",
    "WORK_ORDER": "work_order_id",
    "shift_coverage": "coverage_id",
    "ALERT": "alert_id",
}


def build_transaction_rows(session: Session, client_id: str = "SD-CLIENT") -> Dict[str, Any]:
    """Create the supporting graph plus exactly one row per auto-filtered table.

    Returns a dict with the eleven rows keyed by table name, plus the
    ``client``, ``supervisor``, ``employee``, ``product`` and ``shift`` they
    hang off.
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
        # Linked on purpose: a production entry belongs to a work order, and it
        # is the child whose disappearance from an analytics KPI was the
        # measured symptom of the incidental cascade.
        work_order_id=work_order.work_order_id,
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
    job = TestDataFactory.create_job(session, work_order_id=work_order.work_order_id, client_id=client.client_id)
    coverage = TestDataFactory.create_shift_coverage(
        session, shift_id=shift.shift_id, client_id=client.client_id, entered_by=supervisor.user_id
    )
    pool = TestDataFactory.create_floating_pool_assignment(
        session, employee_id=employee.employee_id, client_id=client.client_id
    )
    part = TestDataFactory.create_part_opportunities(
        session, part_number=f"{client_id}-PART-1", client_id=client.client_id
    )
    # Hangs off the child-bearing work order, never off the leaf: ALERT is a
    # DERIVED child, so it must NOT appear among that work order's blockers, and
    # the leaf must stay genuinely childless.
    alert = Alert(
        alert_id=f"{client_id}-ALERT-1",
        client_id=client.client_id,
        work_order_id=work_order.work_order_id,
        category="hold",
        severity="high",
        status="active",
        title="SD alert",
        message="SD alert message",
    )
    session.add(alert)

    # A work order whose ONLY child is a derived alert, so the cascade can be
    # proved without an independent child blocking first.
    work_order_alert_only = TestDataFactory.create_work_order(session, client_id=client.client_id)
    alert_only = Alert(
        alert_id=f"{client_id}-ALERT-2",
        client_id=client.client_id,
        work_order_id=work_order_alert_only.work_order_id,
        category="otd",
        severity="warning",
        status="active",
        title="SD stale alert",
        message="regenerable derivation",
    )
    session.add(alert_only)
    # No tenant of its own: routes/alerts/crud.py shows this to EVERY tenant, so
    # one tenant's delete must not remove it. It hangs off the same work order as
    # alert_only so a single delete exercises both sides of the rule.
    alert_system_wide = Alert(
        alert_id=f"{client_id}-ALERT-SYS",
        client_id=None,
        work_order_id=work_order_alert_only.work_order_id,
        category="otd",
        severity="info",
        status="active",
        title="SD system-wide alert",
        message="visible to every tenant",
    )
    session.add(alert_system_wide)
    session.flush()

    # Leaf rows: same tables, nothing referencing them. WORK_ORDER and
    # QUALITY_ENTRY above deliberately DO have children, because the delete is
    # refused with 409 while anything visible still references the row — so a
    # round-trip test needs a childless row of the same table to exercise the
    # success path, and the child-bearing ones exercise the refusal.
    work_order_leaf = TestDataFactory.create_work_order(session, client_id=client.client_id)
    # QUALITY_ENTRY.work_order_id is NOT NULL, so the childless quality entry
    # needs a work order of its own — which is therefore not itself childless,
    # and is deliberately not offered as a deletable leaf.
    work_order_host = TestDataFactory.create_work_order(session, client_id=client.client_id)
    quality_leaf = TestDataFactory.create_quality_entry(
        session,
        work_order_id=work_order_host.work_order_id,
        client_id=client.client_id,
        inspector_id=supervisor.user_id,
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
        "JOB": job,
        "shift_coverage": coverage,
        "FLOATING_POOL": pool,
        "PART_OPPORTUNITIES": part,
        "ALERT": alert,
        "WORK_ORDER_alert_only": work_order_alert_only,
        "ALERT_only": alert_only,
        "ALERT_system_wide": alert_system_wide,
        "WORK_ORDER_leaf": work_order_leaf,
        "QUALITY_ENTRY_leaf": quality_leaf,
    }
