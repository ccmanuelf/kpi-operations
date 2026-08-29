"""Nothing may attach itself to a row that has been soft-deleted.

The 409 blocking rule (backend/db/soft_delete_cascade.py) holds the invariant
"no visible row references a hidden parent" *at delete time*. On its own that
is not enough, and review proved it in two API calls::

    DELETE /api/work-orders/WO-0002   -> 204   (parent hidden)
    POST   /api/jobs {work_order_id: "WO-0002"}  -> 201  (child visible)

The database FK is satisfied — the parent row physically exists, it is only
invisible — and no CRUD create looked the parent up through a filtered read.
The KPI-moving symptom came straight back: the new production entry counted 1
in a plain read and 0 through the analytics inner join.

So the invariant needs a second half, enforced on the write side. This is a
``before_flush`` listener on the Session class rather than a check added to the
create functions, for the same reason the read filter is a session event: there
are ten-plus write paths that set one of these foreign keys (per-row creates,
updates, bulk endpoints, CSV upload), and "remember to validate" is the exact
failure mode this whole change exists to remove.

What it checks, and only this:

* every NEW object's FK values that point at an auto-filtered table;
* every DIRTY object's FK values **that this flush is changing**.

An unchanged FK on a dirty row is deliberately not checked: cascade-hiding a
child writes to that child while its parent is on its way out in the same
flush, and re-validating a link nobody is creating would reject it. The guard
is about *attaching*, not about existing links.

The rule is narrow on purpose: **you may not attach to a row that has been
deleted.** Whether you may attach to a row that never existed is the foreign
key's job, and is deliberately left alone — several existing tests build
orphan FK values that SQLite accepts and MariaDB would reject on its own, and
turning those into a different error is not this change's business. So the
check looks for parents that exist AND are inactive, not for parents that are
merely unfindable.

A parent being INSERTed in the same flush is therefore covered for free: it is
not deleted. A parent being soft-deleted in the same flush IS treated as
hidden, so a child cannot slip in alongside its parent's removal.

The 422 payload names each blocked parent as ``{"table": ..., "id": ...}`` rather
than a pre-formatted string. The string form ("WORK_ORDER 'WO-0002'") carried a
raw table name and Python repr quoting into the API, forcing any consumer that
wants a friendly label to regex-parse it back apart. `id` is stringified so the
field has one type across int and str primary keys; `message` still carries the
human sentence for consumers that just want text.

KNOWN GAPS, not fixed. Stated here rather than left to be discovered:

* Core-level ``connection.execute(insert(...))`` bypasses the ORM unit of work
  entirely and therefore this listener. The seeder writes that way, which is
  safe because it only ever creates active parents.
* ORM bulk insert — ``session.execute(insert(Job), [{...}, ...])`` — also
  bypasses it: those rows never become ``session.new`` objects. No call site
  does this today; it is latent, not live.
* An FK set through a *relationship* assignment (``job.work_order = wo``) is
  still ``None`` on the column at ``before_flush`` time, so it is not checked.
  That shape appears at ``crud/attendance.py:133,325`` but is unreachable for a
  hidden parent, because the read filter 404s the parent before any assignment
  happens.
"""

from typing import Any, Dict, List, Set, Tuple

from fastapi import HTTPException
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from backend.db.soft_delete_filter import INCLUDE_INACTIVE
from backend.db.soft_delete_registry import AUTO_FILTERED_TABLES

#: (attribute key, parent table name) per mapped class, resolved once.
_FK_ATTRS_CACHE: Dict[Any, Tuple[Tuple[str, str], ...]] = {}


def _fk_attrs(mapper: Any) -> Tuple[Tuple[str, str], ...]:
    """Attribute keys on this mapper whose column is an FK to an auto-filtered table."""
    cached = _FK_ATTRS_CACHE.get(mapper.class_)
    if cached is not None:
        return cached
    found: List[Tuple[str, str]] = []
    for prop in mapper.column_attrs:
        for column in prop.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name in AUTO_FILTERED_TABLES:
                    found.append((prop.key, fk.column.table.name))
    resolved = tuple(sorted(set(found)))
    _FK_ATTRS_CACHE[mapper.class_] = resolved
    return resolved


def _visible_pk_attribute(table_name: str) -> Any:
    """The mapped primary-key attribute of ``table_name``.

    WHAT ACTUALLY CARRIES THE WEIGHT IN THIS CHECK is not this function — it is
    ``.execution_options(include_inactive=True)`` on the query below. Measured:
    replacing this with the Core ``Column`` (``mapper.primary_key[0]``) changes
    nothing, 168 tests still pass; dropping the ``include_inactive`` option
    kills 4. This docstring previously claimed the opposite, and the claim was
    stale rather than merely wrong: the Column form DID break an earlier version
    of the query, which inferred "deleted" from a row's ABSENCE from a filtered
    read, so the ORM filter had to apply. That version is gone. The query now
    reads ``is_active`` explicitly and deliberately turns the filter OFF, in
    order to tell "deleted" apart from "never existed" — and a Core Column works
    identically for that.

    It is kept, and still raises rather than returning None, for a smaller and
    honest reason: an unresolvable parent would make the check silently succeed.
    That is the "error indistinguishable from nothing-to-do" shape this change
    exists to remove, and it costs nothing to close here. It is not the fix.
    """
    from backend.database import Base
    from sqlalchemy.orm.attributes import InstrumentedAttribute

    for mapper in Base.registry.mappers:
        if mapper.class_.__tablename__ != table_name:
            continue
        pk_column = mapper.primary_key[0]
        attribute = mapper.get_property_by_column(pk_column).class_attribute
        if not isinstance(attribute, InstrumentedAttribute):  # pragma: no cover - defensive
            raise RuntimeError(f"{table_name}.{pk_column.name} did not resolve to a mapped attribute")
        return attribute
    raise RuntimeError(f"no mapped class for auto-filtered table {table_name!r}; the write guard cannot verify it")


def _is_active_attribute(table_name: str) -> Any:
    """The mapped ``is_active`` attribute. Same hard-failure rule, same caveat:
    defensive, not the mechanism the check relies on."""
    from backend.database import Base

    for mapper in Base.registry.mappers:
        if mapper.class_.__tablename__ == table_name:
            attribute = getattr(mapper.class_, "is_active", None)
            if attribute is None:  # pragma: no cover - defensive
                raise RuntimeError(f"auto-filtered table {table_name!r} has no is_active attribute")
            return attribute
    raise RuntimeError(f"no mapped class for auto-filtered table {table_name!r}")


def _requested_links(session: Session) -> Dict[str, Set[Any]]:
    """parent table -> the FK values this flush is trying to attach to."""
    wanted: Dict[str, Set[Any]] = {}

    for obj in session.new:
        state = inspect(obj)
        for attr_key, parent_table in _fk_attrs(state.mapper):
            value = getattr(obj, attr_key, None)
            if value is not None:
                wanted.setdefault(parent_table, set()).add(value)

    for obj in session.dirty:
        state = inspect(obj)
        if not state.modified:
            continue
        for attr_key, parent_table in _fk_attrs(state.mapper):
            history = state.attrs[attr_key].history
            if not history.has_changes():
                continue  # an unchanged link is not an attachment
            value = history.added[0] if history.added else None
            if value is not None:
                wanted.setdefault(parent_table, set()).add(value)

    return wanted


def _parents_being_hidden_now(session: Session) -> Dict[str, Set[Any]]:
    """Parents this same flush is soft-deleting.

    The DB still reports them active until the flush lands, so without this a
    child could be attached to a parent in the very flush that hides it.
    """
    hiding: Dict[str, Set[Any]] = {}
    for obj in session.dirty:
        table_name = getattr(obj, "__tablename__", "")
        if table_name not in AUTO_FILTERED_TABLES:
            continue
        state = inspect(obj)
        if "is_active" not in state.attrs:
            continue
        history = state.attrs["is_active"].history
        if not history.has_changes():
            continue
        going_inactive = not (history.added[0] if history.added else True)
        if not going_inactive:
            continue
        identity = state.mapper.primary_key_from_instance(obj)
        if identity and identity[0] is not None:
            hiding.setdefault(table_name, set()).add(identity[0])
    return hiding


def reject_links_to_hidden_parents(session: Session, flush_context: Any = None, instances: Any = None) -> None:
    """``before_flush`` listener: 422 if this flush attaches to a hidden parent."""
    wanted = _requested_links(session)
    if not wanted:
        return
    hiding_now = _parents_being_hidden_now(session)

    violations: List[Dict[str, str]] = []
    with session.no_autoflush:
        for parent_table, values in sorted(wanted.items()):
            pk_attr = _visible_pk_attribute(parent_table)
            is_active_attr = _is_active_attribute(parent_table)
            # include_inactive: this must see deleted rows in order to
            # distinguish "deleted" (rejected here) from "never existed" (the
            # foreign key's business, and deliberately not ours).
            rows = (
                session.query(pk_attr, is_active_attr)
                .filter(pk_attr.in_(values))
                .execution_options(**{INCLUDE_INACTIVE: True})
                .all()
            )
            deleted = {pk for pk, is_active in rows if not is_active}
            deleted |= values & hiding_now.get(parent_table, set())
            for pk in sorted(deleted, key=str):
                violations.append({"table": parent_table, "id": str(pk)})

    if violations:
        listed = ", ".join(f"{v['table']} {v['id']}" for v in violations)
        raise HTTPException(
            status_code=422,  # literal: starlette deprecated the HTTP_422_UNPROCESSABLE_ENTITY alias
            detail={
                "message": (
                    "Cannot reference a deleted record: " + listed + ". "
                    "The referenced record has been deleted and is no longer available."
                ),
                "hidden_parents": violations,
            },
        )


def install_hidden_parent_write_guard() -> None:
    """Register the listener on the Session class. Idempotent."""
    if event.contains(Session, "before_flush", reject_links_to_hidden_parents):
        return
    event.listen(Session, "before_flush", reject_links_to_hidden_parents)
