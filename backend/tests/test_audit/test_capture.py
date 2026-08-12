"""Audit capture: diffs, redaction, suppression, transactionality."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SASession

from backend.audit.capture import _jsonable, register_audit_listener, unregister_audit_listener
from backend.audit.context import audit_suppressed, set_actor, current_actor
from backend.orm.audit_entry import AuditEntry, AuditOperation
from backend.orm.employee import Employee
from backend.orm.kpi_threshold import KPIThreshold
from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.orm.work_order import WorkOrder, WorkOrderStatus
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.factories import TestDataFactory


@pytest.fixture(autouse=True)
def _cleanup_audit_listener():
    """register_audit_listener() attaches process-wide mapper events (not
    Session-scoped), so without teardown every test after this module runs
    with capture silently active -- a real cross-test contamination vector.
    """
    yield
    unregister_audit_listener()


def _entries(db):
    return db.query(AuditEntry).order_by(AuditEntry.entry_id).all()


def test_insert_is_captured_with_no_old_values(transactional_db):
    register_audit_listener()
    token = set_actor("user-1")
    try:
        TestDataFactory.create_client(transactional_db, client_id="AUD-C1", client_name="Audit Co")
        transactional_db.flush()
    finally:
        current_actor.reset(token)

    rows = [e for e in _entries(transactional_db) if e.table_name == "CLIENT"]
    assert len(rows) == 1
    assert rows[0].operation == AuditOperation.INSERT
    assert rows[0].record_pk == "AUD-C1"
    assert rows[0].actor_user_id == "user-1"
    assert rows[0].changes["client_name"]["old"] is None
    assert rows[0].changes["client_name"]["new"] == "Audit Co"


def test_update_records_before_and_after(transactional_db):
    register_audit_listener()
    threshold = KPIThreshold(threshold_id="AUD-T1", kpi_key="efficiency", target_value=80.0)
    transactional_db.add(threshold)
    transactional_db.flush()

    threshold.target_value = 90.0
    transactional_db.flush()

    updates = [
        e
        for e in _entries(transactional_db)
        if e.table_name == "KPI_THRESHOLD" and e.operation == AuditOperation.UPDATE
    ]
    assert len(updates) == 1
    assert updates[0].changes == {"target_value": {"old": 80.0, "new": 90.0}}


def test_no_op_write_produces_no_entry(transactional_db):
    """Setting a field to its existing value is not a change."""
    register_audit_listener()
    threshold = KPIThreshold(threshold_id="AUD-T2", kpi_key="oee", target_value=75.0)
    transactional_db.add(threshold)
    transactional_db.flush()
    before = len(_entries(transactional_db))

    threshold.target_value = 75.0
    transactional_db.flush()

    assert len(_entries(transactional_db)) == before


def test_delete_is_captured(transactional_db):
    register_audit_listener()
    threshold = KPIThreshold(threshold_id="AUD-T3", kpi_key="fpy", target_value=99.0)
    transactional_db.add(threshold)
    transactional_db.flush()

    transactional_db.delete(threshold)
    transactional_db.flush()

    deletes = [e for e in _entries(transactional_db) if e.operation == AuditOperation.DELETE]
    assert len(deletes) == 1
    assert deletes[0].record_pk == "AUD-T3"


def test_unaudited_table_is_ignored(transactional_db):
    """METRIC_CALCULATION_RESULT is excluded; writing one records nothing.

    Actually inserts a METRIC_CALCULATION_RESULT row (not just asserts absence
    of one that was never created) so the exclusion is proven, not assumed.
    """
    register_audit_listener()
    before = len(_entries(transactional_db))
    client = TestDataFactory.create_client(transactional_db, client_id="AUD-C2", client_name="Kept")
    result = MetricCalculationResult(
        client_id=client.client_id,
        metric_name="oee",
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        standard_value_json="1.0",
        site_adjusted_value_json="1.0",
    )
    transactional_db.add(result)
    transactional_db.flush()
    rows = [e for e in _entries(transactional_db) if e.table_name == "METRIC_CALCULATION_RESULT"]
    assert rows == []
    assert len(_entries(transactional_db)) > before  # the CLIENT insert WAS captured


def test_suppressed_writes_are_not_captured(transactional_db):
    register_audit_listener()
    with audit_suppressed():
        TestDataFactory.create_client(transactional_db, client_id="AUD-C3", client_name="Seeded")
        transactional_db.flush()
    assert [e for e in _entries(transactional_db) if e.record_pk == "AUD-C3"] == []


def test_unsuppressed_bulk_write_is_still_captured(transactional_db):
    """The opt-out must stay deliberate: bulk alone does not exempt."""
    register_audit_listener()
    for i in range(3):
        TestDataFactory.create_client(transactional_db, client_id=f"AUD-B{i}", client_name=f"Bulk {i}")
    transactional_db.flush()
    rows = [e for e in _entries(transactional_db) if e.record_pk.startswith("AUD-B")]
    assert len(rows) == 3


def test_password_hash_is_redacted(transactional_db):
    """The field is recorded as changed; neither hash value is persisted."""
    register_audit_listener()
    user = TestDataFactory.create_user(
        transactional_db, user_id="AUD-U1", username="aud_user", role="operator", client_id=None
    )
    transactional_db.flush()

    user.password_hash = "$argon2id$v=19$brand-new-hash"
    transactional_db.flush()

    updates = [e for e in _entries(transactional_db) if e.table_name == "USER" and e.operation == AuditOperation.UPDATE]
    assert len(updates) == 1
    recorded = updates[0].changes["password_hash"]
    assert recorded == {"old": "[redacted]", "new": "[redacted]"}
    assert "argon2" not in str(updates[0].changes)


def test_actor_is_system_when_unset(transactional_db):
    register_audit_listener()
    TestDataFactory.create_client(transactional_db, client_id="AUD-C4", client_name="No Actor")
    transactional_db.flush()
    row = [e for e in _entries(transactional_db) if e.record_pk == "AUD-C4"][0]
    assert row.actor_user_id is None
    assert row.actor_username == "system"


def test_autoincrement_pk_insert_records_real_pk_not_none(transactional_db):
    """EMPLOYEE.employee_id is DB-assigned (autoincrement). At before_flush time
    the PK is still None; a naive implementation would stringify that straight
    into record_pk, producing the literal (and useless) string "None". The
    audit row must instead carry the real integer PK, once the flush has
    assigned it -- as a non-empty string, not "None".
    """
    register_audit_listener()
    employee = TestDataFactory.create_employee(transactional_db, employee_code="AUD-E1", employee_name="Audit Emp")

    assert employee.employee_id is not None  # sanity: DB really did assign one

    rows = [e for e in _entries(transactional_db) if e.table_name == "EMPLOYEE"]
    assert len(rows) == 1
    assert rows[0].operation == AuditOperation.INSERT
    assert rows[0].record_pk == str(employee.employee_id)
    assert rows[0].record_pk != "None"
    assert rows[0].record_pk != ""


def test_rollback_discards_autoincrement_insert_and_its_audit_row(transactional_db):
    """The core transactionality guarantee, exercised on the trickiest path.

    The autoincrement-PK case defers building the audit row to an
    ``after_flush`` handler that calls ``session.add()`` -- exactly the kind
    of construct the brief warns is easy to get wrong in a way that lets an
    audit row outlive the change it describes. Prove it does not: after a
    rollback, neither the EMPLOYEE row nor its audit entry exists, and the
    session is still usable afterward for a fresh write.
    """
    register_audit_listener()
    employee = TestDataFactory.create_employee(transactional_db, employee_code="AUD-E2", employee_name="Rolled Back")
    employee_id = employee.employee_id
    assert employee_id is not None

    transactional_db.rollback()

    assert transactional_db.query(Employee).filter(Employee.employee_id == employee_id).first() is None
    assert [e for e in _entries(transactional_db) if e.table_name == "EMPLOYEE"] == []

    # The session must still be usable: a write after rollback is captured normally.
    survivor = TestDataFactory.create_employee(transactional_db, employee_code="AUD-E3", employee_name="Survivor")
    rows = [e for e in _entries(transactional_db) if e.table_name == "EMPLOYEE"]
    assert len(rows) == 1
    assert rows[0].record_pk == str(survivor.employee_id)


def test_failed_flush_leaves_no_phantom_employee_row_for_the_next_actor(transactional_db):
    """Regression for the pre-rewrite deferred-INSERT design (Critical 1).

    The original capture stashed autoincrement-PK inserts on ``session.info``
    in ``before_flush`` and drained them in ``after_flush``. When a flush
    *fails*, ``after_flush`` never runs and SQLAlchemy does not clear
    user-owned ``session.info`` on rollback, so the stashed EMPLOYEE insert
    survived the rollback and drained on the next *successful* flush --
    writing an audit row for a record that was never created, attributed to
    whichever actor happened to be writing at that later moment, under a PK
    the database would go on to reissue to a real employee.

    Shape: one flush carrying an EMPLOYEE insert plus a failing statement (a
    second EMPLOYEE with a duplicate ``employee_code``, which the unique index
    rejects), rolled back, followed by an unrelated successful write by a
    different actor. Zero EMPLOYEE audit rows may exist afterwards.
    """
    register_audit_listener()

    token_a = set_actor("actor-a")
    try:
        transactional_db.add(Employee(employee_code="AUD-DUP", employee_name="Doomed"))
        transactional_db.add(Employee(employee_code="AUD-DUP", employee_name="Duplicate code"))
        with pytest.raises(IntegrityError):
            transactional_db.flush()
    finally:
        current_actor.reset(token_a)

    transactional_db.rollback()

    token_b = set_actor("actor-b")
    try:
        transactional_db.add(KPIThreshold(threshold_id="AUD-T5", kpi_key="otd", target_value=95.0))
        transactional_db.flush()
    finally:
        current_actor.reset(token_b)

    assert [e for e in _entries(transactional_db) if e.table_name == "EMPLOYEE"] == []

    # Not vacuous: the later, legitimate write really was captured, and only
    # actor-b is attributed to it.
    later = [e for e in _entries(transactional_db) if e.record_pk == "AUD-T5"]
    assert len(later) == 1
    assert later[0].actor_user_id == "actor-b"


def test_update_after_expiry_records_the_real_old_value(transactional_db):
    """Regression for the expire_on_commit=True blind spot (Important 2).

    ``SessionLocal`` (backend/database.py) commits with ``expire_on_commit``
    left at its default of True, so every attribute of an already-committed
    object is expired. Without ``active_history`` forced on audited mappers,
    SQLAlchemy's passive history lookup reports the "old" side as None on the
    next change instead of reloading the pre-expiry value -- silently losing
    exactly the field this trail exists to preserve.
    """
    register_audit_listener()
    threshold = KPIThreshold(threshold_id="AUD-T6", kpi_key="fpy", target_value=50.0)
    transactional_db.add(threshold)
    transactional_db.commit()  # expires every attribute on `threshold`

    threshold.target_value = 70.0
    transactional_db.flush()

    updates = [
        e for e in _entries(transactional_db) if e.record_pk == "AUD-T6" and e.operation == AuditOperation.UPDATE
    ]
    assert len(updates) == 1
    assert updates[0].changes == {"target_value": {"old": 50.0, "new": 70.0}}


def test_column_values_are_recorded_as_json_native_types(transactional_db):
    """Decimal -> JSON number, datetime -> ISO string, Enum -> its .value.

    Asserted on real WORK_ORDER columns, read back through the JSON column so
    the persisted representation is what is checked, not the in-memory one.
    """
    register_audit_listener()
    client = TestDataFactory.create_client(transactional_db, client_id="AUD-C5", client_name="Serialize Co")
    transactional_db.add(
        WorkOrder(
            work_order_id="AUD-WO1",
            client_id=client.client_id,
            style_model="STYLE-AUD",
            planned_quantity=10,
            status=WorkOrderStatus.IN_PROGRESS,
            planned_ship_date=datetime(2026, 3, 4, 5, 6, 7),
            ideal_cycle_time=Decimal("0.2500"),
        )
    )
    transactional_db.flush()

    rows = [e for e in _entries(transactional_db) if e.table_name == "WORK_ORDER"]
    assert len(rows) == 1
    changes = rows[0].changes

    # Decimal must survive as a JSON number, not a stringified "0.2500" --
    # the MariaDB "0.00"-as-string bug class this codebase has already shipped.
    assert type(changes["ideal_cycle_time"]["new"]) is float
    assert changes["ideal_cycle_time"]["new"] == 0.25

    assert changes["planned_ship_date"]["new"] == "2026-03-04T05:06:07"
    assert changes["status"]["new"] == "IN_PROGRESS"

    # Ordering hazard, and the only place it is observable: WorkOrderStatus is
    # a `str`-mixin Enum, so a primitives-before-Enum check in `_jsonable`
    # returns the member itself rather than its `.value`. That happens to
    # serialize to the same JSON text, so the round-tripped assertion above
    # cannot catch it -- this one can, and would break for an IntEnum.
    assert type(_jsonable(WorkOrderStatus.IN_PROGRESS)) is str


def test_employee_audit_row_carries_tenant_from_client_id_assigned(transactional_db):
    """EMPLOYEE has no `client_id` column; tenancy lives in `client_id_assigned`.

    A `getattr(obj, "client_id", None)`-only lookup records `client_id=None`
    for every EMPLOYEE row, dropping the tenant scope AUDIT_ENTRY.client_id
    exists to carry (and which cannot be reconstructed once the employee's
    assignment changes).
    """
    register_audit_listener()
    TestDataFactory.create_employee(
        transactional_db, employee_code="AUD-E4", employee_name="Assigned", client_id="AUD-CX"
    )

    rows = [e for e in _entries(transactional_db) if e.table_name == "EMPLOYEE"]
    assert len(rows) == 1
    assert rows[0].client_id == "AUD-CX"


def test_rolled_back_outer_transaction_leaves_no_change_and_no_audit_row(_txn_engine):
    """The production shape: a plain Session on a real connection-owned
    transaction, no savepoints involved (unlike ``transactional_db``, which
    is savepoint-based and cannot express a genuine outer rollback).

    Roll back a real transaction and both the change and its audit row must
    be gone -- verified from a second, independent connection so the check
    cannot be fooled by anything cached on the writing session.
    """
    register_audit_listener()

    connection = _txn_engine.connect()
    trans = connection.begin()
    session = SASession(bind=connection)
    try:
        session.add(KPIThreshold(threshold_id="AUD-RB1", kpi_key="rty", target_value=95.0))
        session.flush()
        # The audit row exists inside the still-open transaction...
        staged = session.query(AuditEntry).filter_by(record_pk="AUD-RB1").count()
        assert staged == 1
    finally:
        session.close()
        trans.rollback()
        connection.close()

    # ...and is gone, along with the change itself, once the transaction is
    # discarded -- checked from a fresh connection, not the one that wrote it.
    verify_conn = _txn_engine.connect()
    verify_session = SASession(bind=verify_conn)
    try:
        assert verify_session.query(AuditEntry).filter_by(record_pk="AUD-RB1").count() == 0
        assert verify_session.query(KPIThreshold).filter_by(threshold_id="AUD-RB1").count() == 0
    finally:
        verify_session.close()
        verify_conn.close()


def test_committed_outer_transaction_persists_change_and_audit_row_together():
    """The mirror of the rollback test, and just as load-bearing.

    A committed change must never lack its audit entry: without this half,
    an implementation that captured nothing at all (or wrote the audit row
    on a connection other than the flush's own) would still pass the
    rollback-only test above.

    Deliberately NOT on the shared, session-scoped ``_txn_engine``: this test
    commits for real, and ``_txn_engine`` backs the whole ``transactional_db``
    fixture family (``seeded_db``, ``comprehensive_db``, etc.) for the rest of
    the pytest process. A durable row there would be a latent order-dependency
    for any later test asserting exact counts. Uses its own disposable engine
    instead (the same ``clone_template_engine`` pattern already used by
    ~40 other test modules in this suite), so a real commit here can never
    leak into anything else.
    """
    register_audit_listener()
    engine = clone_template_engine()
    try:
        connection = engine.connect()
        trans = connection.begin()
        session = SASession(bind=connection)
        try:
            session.add(KPIThreshold(threshold_id="AUD-CM1", kpi_key="rty", target_value=95.0))
            session.flush()
        except Exception:
            # A real failure here (e.g. a capture bug) has already put the
            # DBAPI transaction in pending-rollback state; committing it
            # would raise a second, masking error. Roll back instead and let
            # the original exception propagate.
            trans.rollback()
            raise
        else:
            trans.commit()
        finally:
            session.close()
            connection.close()

        verify_conn = engine.connect()
        verify_session = SASession(bind=verify_conn)
        try:
            assert verify_session.query(KPIThreshold).filter_by(threshold_id="AUD-CM1").count() == 1
            entries = verify_session.query(AuditEntry).filter_by(record_pk="AUD-CM1").all()
            assert len(entries) == 1
            assert entries[0].operation == AuditOperation.INSERT
        finally:
            verify_session.close()
            verify_conn.close()
    finally:
        engine.dispose()
