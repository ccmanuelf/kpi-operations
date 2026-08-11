"""Audit capture: diffs, redaction, suppression, transactionality."""

from backend.audit.capture import register_audit_listener
from backend.audit.context import audit_suppressed, set_actor, current_actor
from datetime import datetime, timezone

from backend.orm.audit_entry import AuditEntry, AuditOperation
from backend.orm.kpi_threshold import KPIThreshold
from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.tests.fixtures.factories import TestDataFactory


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

    from backend.orm.employee import Employee

    assert transactional_db.query(Employee).filter(Employee.employee_id == employee_id).first() is None
    assert [e for e in _entries(transactional_db) if e.table_name == "EMPLOYEE"] == []

    # The session must still be usable: a write after rollback is captured normally.
    survivor = TestDataFactory.create_employee(transactional_db, employee_code="AUD-E3", employee_name="Survivor")
    rows = [e for e in _entries(transactional_db) if e.table_name == "EMPLOYEE"]
    assert len(rows) == 1
    assert rows[0].record_pk == str(survivor.employee_id)
