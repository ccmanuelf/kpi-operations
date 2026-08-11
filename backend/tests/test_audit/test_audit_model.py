"""AUDIT_ENTRY shape and migration parity."""

from datetime import datetime, timezone

from backend.database import Base
from backend.orm.audit_entry import AuditEntry, AuditOperation


def test_table_is_registered_with_expected_columns():
    table = Base.metadata.tables["AUDIT_ENTRY"]
    expected = {
        "entry_id",
        "occurred_at",
        "actor_user_id",
        "actor_username",
        "table_name",
        "record_pk",
        "operation",
        "changes",
        "client_id",
        "request_method",
        "request_path",
    }
    assert set(table.columns.keys()) == expected


def test_lookup_indexes_exist():
    """(table_name, record_pk) backs the entity-history query."""
    table = Base.metadata.tables["AUDIT_ENTRY"]
    indexed = {tuple(c.name for c in idx.columns) for idx in table.indexes}
    assert ("table_name", "record_pk") in indexed


def test_row_round_trips(transactional_db):
    entry = AuditEntry(
        occurred_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        actor_user_id="user-1",
        actor_username="alice",
        table_name="HOLD_ENTRY",
        record_pk="HOLD-1",
        operation=AuditOperation.UPDATE,
        changes={"hold_status": {"old": "ON_HOLD", "new": "RELEASED"}},
        client_id="CLIENT-1",
        request_method="PUT",
        request_path="/api/holds/HOLD-1",
    )
    transactional_db.add(entry)
    transactional_db.flush()

    stored = transactional_db.query(AuditEntry).filter_by(record_pk="HOLD-1").one()
    assert stored.operation == AuditOperation.UPDATE
    assert stored.changes["hold_status"]["new"] == "RELEASED"
    assert stored.actor_username == "alice"
