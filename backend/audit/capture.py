"""Mapper-level capture of entity-level changes into AUDIT_ENTRY.

Fix round 1 rewrite. The original design used a session-wide before_flush
listener (add fully-resolved UPDATE/DELETE rows, defer INSERT rows needing an
autoincrement PK to session.info) drained by after_flush. Adversarial review
(verified by execution, not by reading) found that shape structurally
unsound: session.info is user-owned state SQLAlchemy does not clear on
rollback, so a failed flush left residue that drained on the *next*
successful flush -- producing a phantom audit row for a record that was
never persisted, attributed to whichever actor happened to be active later,
and aliased to whatever PK got reissued to the next real row. A second,
narrower failure mode: if no flush or commit happened to follow, the
deferred row was silently dropped (commit() rescues it via SQLAlchemy's
after-flush re-flush retries, but that made the guarantee depend on how the
transaction happened to end, not on the design).

This version removes the deferred state entirely rather than patching around
it, using SQLAlchemy's mapper-level persistence events instead of the
session-wide flush events:

- `after_insert(mapper, connection, target)` -- fires per row, once that
  row's own INSERT has executed. The primary key (autoincrement or
  caller-assigned) is guaranteed to be populated on `target` by this point,
  even for EMPLOYEE/EMPLOYEE_CLIENT_ASSIGNMENT's DB-assigned integer PKs.
- `before_update(mapper, connection, target)` -- fires per row, before that
  row's own UPDATE executes, while attribute history is still intact.
- `before_delete(mapper, connection, target)` -- fires per row, before that
  row's own DELETE executes, while attribute values are still on `target`.

Each handler writes its AUDIT_ENTRY row with `connection.execute(...)` --
the same DBAPI connection SQLAlchemy is using for the row's own statement,
inside the same flush, inside the same transaction. There is no window where
the audit row can exist without the change it describes, or vice versa:
transactionality falls out of using one connection, not out of getting a
rollback hook right. This is also the pattern SQLAlchemy's own docs use for
change-data-capture / versioning recipes.

One consequence worth naming: mapper events are global to the process (they
attach to the `Base` class with `propagate=True`, not to a Session).
`register_audit_listener()` is idempotent, but nothing about SQLAlchemy
tears it down automatically -- callers that need isolation (this module's
own test suite) must call `unregister_audit_listener()` when done, or every
later test in the same process silently starts capturing audit rows too.
"""

import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import event, inspect
from sqlalchemy.orm import configure_mappers

from backend.audit.context import get_actor, get_actor_username, get_request_shape, is_suppressed
from backend.audit.registry import REDACTED_FIELDS, is_audited
from backend.database import Base
from backend.orm.audit_entry import AuditEntry, AuditOperation

_REDACTED = "[redacted]"
_listener_registered = False


def _jsonable(value: Any) -> Any:
    """Coerce a column value into something the JSON column accepts.

    Decimal becomes float, not str -- numeric before/after values must stay
    JSON numbers so consumers can compare them arithmetically; stringified
    Decimals are a bug class this codebase has already shipped to production
    once, where MariaDB returned "0.00" and the frontend had to coerce it
    back. Enum is checked *before* the str/int/float/bool primitives: a
    `str`-mixin Enum (this codebase has one -- AuditOperation itself) is also
    an instance of `str`, so checking primitives first would silently return
    the raw enum member instead of its `.value`. It happens to serialize
    correctly by coincidence for str-mixin enums (JSON encodes it as its
    string value anyway) but would be wrong for an IntEnum or a plain Enum,
    so the order is load-bearing, not stylistic.
    """
    if value is None:
        return value
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _mask(field: str, value: Any) -> Any:
    return _REDACTED if field in REDACTED_FIELDS else _jsonable(value)


def _require_pk(obj: Any) -> str:
    """Stringified primary key.

    Every audited table was verified to have a single-column PK, and that
    assumption is pinned by
    tests/test_audit/test_registry_guards.py::test_every_audited_table_has_a_single_column_pk
    so a future composite key fails CI rather than silently losing every
    column after the first. Safe to call unconditionally in all three
    handlers below: `after_insert` only fires once the row's own INSERT has
    executed (autoincrement PKs are populated by then), and
    `before_update`/`before_delete` only ever see already-persisted rows,
    which always have an identity.
    """
    state = inspect(obj)
    identity = state.mapper.primary_key_from_instance(obj)
    value = identity[0]
    if value is None:
        # Would mean this function was called somewhere the timing guarantee
        # above doesn't hold -- a bug in this module, not a legitimate
        # runtime state worth swallowing into a placeholder string.
        raise RuntimeError(f"expected an assigned primary key for {obj.__tablename__!r}, got None")
    return str(value)


def _client_id(obj: Any) -> Optional[str]:
    """Best-effort tenant scope for this row.

    Most audited tables have a `client_id` column. USER and EMPLOYEE are the
    exception: multi-client actors (leaders, floating-pool staff) are scoped
    via `client_id_assigned` instead, a comma-separated list (or NULL for
    floating pool / unassigned). Captured now because it cannot be
    reconstructed later if the source row is deleted or its assignment
    changes. AUDIT_ENTRY.client_id is a single-tenant admin-read filter, not
    a scoping boundary, so a comma-separated value is trimmed to its first
    listed client rather than dropped -- a best-effort single value beats
    recording nothing.
    """
    value = getattr(obj, "client_id", None)
    if value is None:
        assigned = getattr(obj, "client_id_assigned", None)
        if assigned:
            value = assigned.split(",", 1)[0].strip()
    return str(value) if value else None


def _insert_changes(obj: Any) -> Dict[str, Any]:
    changes: Dict[str, Any] = {}
    for column in inspect(obj).mapper.columns:
        value = getattr(obj, column.key, None)
        if value is None:
            continue
        changes[column.key] = {"old": None, "new": _mask(column.key, value)}
    return changes


def _update_changes(obj: Any) -> Dict[str, Any]:
    """Only genuinely modified columns. A no-op write yields {}.

    Relies on `active_history` being forced on every audited mapper's column
    attributes (see `_force_active_history_for_audited_tables`) -- without
    it, an attribute expired by an earlier commit in the same session
    (SessionLocal uses expire_on_commit=True) reports `old: None` on its
    next change instead of reloading the real pre-expiry value, silently
    corrupting exactly the field this trail exists to preserve.
    """
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
    """Every column's current value, recorded as the "old" side.

    Unlike `_insert_changes`, this does not skip None-valued columns: a
    delete's "before" snapshot should be complete (this is the last chance
    to record what the row looked like), whereas an insert's "before" side
    is always None by definition and a column that was never set is not
    informative enough to justify the row in the changes dict.
    """
    changes: Dict[str, Any] = {}
    for column in inspect(obj).mapper.columns:
        value = getattr(obj, column.key, None)
        changes[column.key] = {"old": _mask(column.key, value), "new": None}
    return changes


def _write_entry(connection: Any, obj: Any, operation: AuditOperation, changes: Dict[str, Any]) -> None:
    """Insert one AUDIT_ENTRY row via Core, on the flush's own connection.

    Deliberately not `session.add()` / ORM: a Core insert on the connection
    the mapper event handed us lands in the exact same transaction as the
    row it describes, with no dependency on a later flush and nothing to
    reconcile if the surrounding transaction rolls back. It also cannot
    recurse into these same listeners -- mapper events only fire for ORM
    session flushes, and this bypasses the ORM entirely.
    """
    actor = get_actor()
    username = get_actor_username()
    method, path = get_request_shape()
    connection.execute(
        AuditEntry.__table__.insert(),
        {
            # Naive UTC, deliberately. AUDIT_ENTRY.occurred_at is a plain
            # `DateTime` column, and neither SQLite nor pymysql/MariaDB can
            # store a UTC offset in one -- both silently discard the tzinfo,
            # so a tz-aware bind produced a naive-UTC row anyway, just via an
            # implicit truncation nobody had stated. Truncating here makes the
            # stored contract explicit and identical on both dialects: every
            # occurred_at value is naive UTC. Range filters (Phase A2) must
            # therefore compare against naive UTC datetimes, never against
            # `datetime.now()` local time and never against an aware value.
            "occurred_at": datetime.now(tz=timezone.utc).replace(tzinfo=None),
            "actor_user_id": actor,
            # "system" means genuinely no actor. A known id with no username
            # is left NULL rather than mislabelled "system" -- only reachable
            # from a direct set_actor(user_id) call with no username (CLI /
            # tests); the request path always carries both.
            "actor_username": username if username else ("system" if actor is None else None),
            "table_name": obj.__tablename__,
            "record_pk": _require_pk(obj),
            "operation": operation,
            "changes": changes,
            "client_id": _client_id(obj),
            # Truncated to the column widths: MariaDB in STRICT mode ERRORS on
            # an over-long value rather than truncating, which would turn a
            # long path into a failed *business* write. The value is
            # scope["path"] only — the query string is NOT included — so
            # overflow means a genuinely long path (deep prefixes, a long
            # path parameter), not query parameters. Losing the tail of a path
            # is acceptable; failing the user's request in order to record the
            # audit of it is not.
            "request_method": method[:8] if method else None,
            "request_path": path[:255] if path else None,
        },
    )


def _capture_insert(mapper: Any, connection: Any, target: Any) -> None:
    if is_suppressed():
        return
    if not is_audited(getattr(target, "__tablename__", "")):
        return
    _write_entry(connection, target, AuditOperation.INSERT, _insert_changes(target))


def _capture_update(mapper: Any, connection: Any, target: Any) -> None:
    if is_suppressed():
        return
    if not is_audited(getattr(target, "__tablename__", "")):
        return
    changes = _update_changes(target)
    if not changes:
        return  # no-op write
    _write_entry(connection, target, AuditOperation.UPDATE, changes)


def _capture_delete(mapper: Any, connection: Any, target: Any) -> None:
    if is_suppressed():
        return
    if not is_audited(getattr(target, "__tablename__", "")):
        return
    _write_entry(connection, target, AuditOperation.DELETE, _delete_changes(target))


def _force_active_history_for_audited_tables() -> None:
    """Make expired attributes reload their real value when history is read.

    `SessionLocal` (backend/database.py) uses `expire_on_commit=True`. Any
    object touched again after an earlier commit in the *same* session has
    every attribute expired; SQLAlchemy's default (passive) history lookup
    then reports the "old" side as None instead of reloading it -- verified
    directly: a real old value of 50.0 came back as `{'old': None, 'new':
    70.0}`. `load_history()` does not fix this (also verified); forcing
    `active_history=True` on the attribute implementation does, by making
    SQLAlchemy actively reload the pre-expiry value instead of trusting a
    (now-invalid) cached one. Scoped to audited tables only, and applied
    programmatically here rather than by editing 14 ORM files' column
    definitions, since `active_history` isn't exposed as a `mapped_column()`
    kwarg and this keeps the change contained to the audit module.

    PERMANENT, PROCESS-WIDE, NOT UNDONE BY `unregister_audit_listener()`: this
    sets a flag on the class-level attribute implementation shared by every
    instance of the 14 audited mappers, for the lifetime of the process --
    unlike the event listeners themselves, there is no SQLAlchemy API to
    reverse it. Consequence: setting an attribute on a *detached* instance of
    an audited table whose attributes were expired by an earlier commit now
    raises `DetachedInstanceError` (SQLAlchemy must reload the pre-change
    value to record it, and a detached instance has no session to reload
    from), where the same code previously succeeded silently. See the
    registration-site comment in `backend/bootstrap/app_config.py` for the
    blast-radius check performed when this was wired live.
    """
    configure_mappers()
    for mapper in Base.registry.mappers:
        table = mapper.local_table
        if table is None or not is_audited(table.name):
            continue
        class_manager = mapper.class_manager
        for prop in mapper.column_attrs:
            class_manager[prop.key].impl.active_history = True


def register_audit_listener() -> None:
    """Attach the mapper-level capture listeners. Idempotent."""
    global _listener_registered
    if _listener_registered:
        return

    _force_active_history_for_audited_tables()
    event.listen(Base, "after_insert", _capture_insert, propagate=True)
    event.listen(Base, "before_update", _capture_update, propagate=True)
    event.listen(Base, "before_delete", _capture_delete, propagate=True)
    _listener_registered = True


def unregister_audit_listener() -> None:
    """Detach the mapper-level capture listeners.

    Needed because these attach process-wide (mapper events aren't
    Session-scoped): once registered, they stay live for every later test
    in the same pytest process unless explicitly removed. Safe to call when
    nothing is registered.
    """
    global _listener_registered
    if not _listener_registered:
        return

    event.remove(Base, "after_insert", _capture_insert)
    event.remove(Base, "before_update", _capture_update)
    event.remove(Base, "before_delete", _capture_delete)
    _listener_registered = False
