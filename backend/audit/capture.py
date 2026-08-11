"""SQLAlchemy before_flush/after_flush capture of entity-level changes.

before_flush rather than solely after_flush for two reasons that matter: old
values are still present in attribute history before the flush completes, and
staged audit rows join the SAME transaction -- so a rolled-back change can
never leave an entry behind, and a committed change can never lack one.

Autoincrement primary keys (EMPLOYEE, EMPLOYEE_CLIENT_ASSIGNMENT) are the one
wrinkle: at before_flush time the database has not assigned them yet, so the
row's identity does not exist. Building the INSERT audit row then would bake
in a useless "None" record_pk. Those two cases are deferred: before_flush
records everything an insert needs EXCEPT its primary key, and after_flush --
once the INSERT has executed and the real key is sitting on the Python
instance -- builds the row and adds it to the session. Per SQLAlchemy's own
session-events docs, objects added inside after_flush are not part of the
flush that is just finishing, but they DO participate in the next one
(explicit, autoflush-on-query, or the implicit flush inside commit()), so
this still lands in the same transaction as the row it describes, in exactly
one INSERT. This was verified directly against SQLAlchemy 2.0.51 semantics
before relying on it (see task-4-report.md).
"""

import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from backend.audit.context import get_actor, is_suppressed
from backend.audit.registry import REDACTED_FIELDS, is_audited
from backend.orm.audit_entry import AuditEntry, AuditOperation

_REDACTED = "[redacted]"
_listener_registered = False

#: session.info key holding (obj, changes) pairs for INSERTs whose primary
#: key was not yet assigned at before_flush time. Populated in before_flush,
#: drained in after_flush once identities exist.
_PENDING_INSERTS_KEY = "_audit_pending_inserts"


def _jsonable(value: Any) -> Any:
    """Coerce a column value into something the JSON column accepts.

    Decimal becomes float, not str. Numeric before/after values must stay JSON
    numbers so consumers can compare them arithmetically -- stringified Decimals
    are a bug class this codebase has already shipped to production once, where
    MariaDB returned "0.00" and the frontend had to coerce it back.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return str(value)


def _mask(field: str, value: Any) -> Any:
    return _REDACTED if field in REDACTED_FIELDS else _jsonable(value)


def _record_pk(obj: Any) -> Optional[str]:
    """Stringified primary key, or None if the database hasn't assigned one yet.

    Caller-assigned PKs (String columns such as WORK_ORDER, CLIENT, USER) are
    already set before flush. Autoincrement PKs are only populated once the
    INSERT statement for that row has actually executed. Every audited table
    was verified to have a single-column PK.
    """
    state = inspect(obj)
    identity = state.mapper.primary_key_from_instance(obj)
    value = identity[0]
    return None if value is None else str(value)


def _require_pk(obj: Any) -> str:
    """Like `_record_pk`, but for contexts where the primary key is
    guaranteed to already be assigned: existing persisted rows (UPDATE,
    DELETE), or a new row after the flush that inserted it has executed.
    Raises if that invariant is somehow violated -- that would be a bug in
    this module, not a legitimate runtime state.
    """
    pk = _record_pk(obj)
    if pk is None:
        raise RuntimeError(f"expected an assigned primary key for {obj.__tablename__!r}, got None")
    return pk


def _client_id(obj: Any) -> Optional[str]:
    value = getattr(obj, "client_id", None)
    return str(value) if value is not None else None


def _insert_changes(obj: Any) -> Dict[str, Any]:
    changes: Dict[str, Any] = {}
    for column in inspect(obj).mapper.columns:
        value = getattr(obj, column.key, None)
        if value is None:
            continue
        changes[column.key] = {"old": None, "new": _mask(column.key, value)}
    return changes


def _update_changes(obj: Any) -> Dict[str, Any]:
    """Only genuinely modified columns. A no-op write yields {}."""
    state = inspect(obj)
    changes: Dict[str, Any] = {}
    for column in state.mapper.columns:
        history = state.attrs[column.key].history
        if not history.has_changes():
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        if old == new:
            continue
        changes[column.key] = {"old": _mask(column.key, old), "new": _mask(column.key, new)}
    return changes


def _delete_changes(obj: Any) -> Dict[str, Any]:
    changes: Dict[str, Any] = {}
    for column in inspect(obj).mapper.columns:
        value = getattr(obj, column.key, None)
        changes[column.key] = {"old": _mask(column.key, value), "new": None}
    return changes


def _build_entry(obj: Any, operation: AuditOperation, changes: Dict[str, Any], record_pk: str) -> AuditEntry:
    actor = get_actor()
    return AuditEntry(
        occurred_at=datetime.now(tz=timezone.utc),
        actor_user_id=actor,
        actor_username=actor if actor else "system",
        table_name=obj.__tablename__,
        record_pk=record_pk,
        operation=operation,
        changes=changes,
        client_id=_client_id(obj),
    )


def build_entries(session: Session) -> List[AuditEntry]:
    """Audit rows resolvable right now: updates, deletes, and inserts whose
    primary key is already known (caller-assigned PK tables). Pure; adds
    nothing to the session.

    Inserts into autoincrement-PK tables are deliberately excluded here --
    their identity does not exist until the flush actually executes -- and
    are instead captured via `_pending_inserts` for after_flush to resolve.
    """
    if is_suppressed():
        return []

    entries: List[AuditEntry] = []

    for obj in session.new:
        if not is_audited(getattr(obj, "__tablename__", "")):
            continue
        pk = _record_pk(obj)
        if pk is None:
            continue  # autoincrement PK not yet assigned; see _pending_inserts
        entries.append(_build_entry(obj, AuditOperation.INSERT, _insert_changes(obj), pk))

    for obj in session.dirty:
        if not is_audited(getattr(obj, "__tablename__", "")):
            continue
        changes = _update_changes(obj)
        if not changes:
            continue  # no-op write
        entries.append(_build_entry(obj, AuditOperation.UPDATE, changes, _require_pk(obj)))

    for obj in session.deleted:
        if not is_audited(getattr(obj, "__tablename__", "")):
            continue
        entries.append(_build_entry(obj, AuditOperation.DELETE, _delete_changes(obj), _require_pk(obj)))

    return entries


def _pending_inserts(session: Session) -> List[Tuple[Any, Dict[str, Any]]]:
    """Autoincrement-PK inserts awaiting their real primary key.

    Values are captured now (before_flush) because attribute history is only
    reliable pre-flush; only the key resolution itself is deferred.
    """
    if is_suppressed():
        return []

    pending: List[Tuple[Any, Dict[str, Any]]] = []
    for obj in session.new:
        if not is_audited(getattr(obj, "__tablename__", "")):
            continue
        if _record_pk(obj) is not None:
            continue  # already handled by build_entries
        pending.append((obj, _insert_changes(obj)))
    return pending


def register_audit_listener() -> None:
    """Attach the before_flush/after_flush listener pair. Idempotent."""
    global _listener_registered
    if _listener_registered:
        return

    @event.listens_for(Session, "before_flush")
    def _before_flush(session: Session, flush_context: Any, instances: Any) -> None:
        for entry in build_entries(session):
            session.add(entry)

        pending = _pending_inserts(session)
        if pending:
            session.info.setdefault(_PENDING_INSERTS_KEY, []).extend(pending)

    @event.listens_for(Session, "after_flush")
    def _after_flush(session: Session, flush_context: Any) -> None:
        pending = session.info.pop(_PENDING_INSERTS_KEY, None)
        if not pending:
            return
        for obj, changes in pending:
            session.add(_build_entry(obj, AuditOperation.INSERT, changes, _require_pk(obj)))

    _listener_registered = True
