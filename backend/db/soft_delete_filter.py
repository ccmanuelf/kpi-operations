"""Automatic hiding of soft-deleted rows for the tables that declare it.

Why a session event and not a filter per query
----------------------------------------------
The pre-existing convention in this codebase is "remember to add
``.filter(Model.is_active == 1)``", and it is measurably not remembered:
``query(Employee)`` has 33 call sites and 4 nearby filters. On the seven
transaction tables a resurrected row is not a stale dropdown entry, it is a
wrong KPI — a deleted production entry re-entering an efficiency calculation is
silently incorrect data. So enforcement here cannot depend on anyone
remembering.

``with_loader_criteria`` applied from SQLAlchemy's ``do_orm_execute`` event is
the documented mechanism for exactly this. Registered against the ``Session``
*class*, it covers every session in the process — the app's ``SessionLocal``,
the seeder's, the test suite's — so a read cannot escape it by constructing its
own session. Measured coverage (see
tests/test_db/test_soft_delete_auto_filter.py, which asserts each of these):

* ``session.query(Model)`` and ``session.execute(select(Model))``
* column-only reads: ``query(Model.col)``, ``select(Model.col)``
* aggregates: ``query(func.count(Model.pk))`` — the KPI shape that matters most
* explicit joins where the model appears anywhere in the statement
* ``session.get(Model, pk)``

The one read shape it cannot cover is raw ``text()`` SQL, which never passes
through the ORM. ``tests/test_db/test_soft_delete_registry_guards.py`` gates
that: no raw SQL in backend/ may select from an auto-filtered table.

Attribute loads are deliberately exempt (``is_column_load``): a refresh of an
already-loaded object must still work after that object has been soft-deleted,
otherwise ``db.refresh(entity)`` in a delete path would explode.

Seeing inactive rows
--------------------
Two equivalent opt-ins, both explicit::

    session.query(WorkOrder).execution_options(include_inactive=True).all()

    with include_inactive(session):
        ...                      # every read in the block sees inactive rows
"""

from contextlib import contextmanager
from typing import Any, Iterator, Tuple

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, with_loader_criteria

from backend.db.soft_delete_registry import AUTO_FILTERED_TABLES

#: Execution option / session-info key that suppresses the filter.
INCLUDE_INACTIVE = "include_inactive"

#: Resolved at install time so a renamed table fails loudly at import rather
#: than degrading to "nothing is filtered".
_AUTO_FILTERED_MODELS: Tuple[Any, ...] = ()


def _validate_auto_filtered(by_table: dict, tables: Any) -> None:
    """Refuse a schema the filter and the write guard cannot handle correctly.

    Split out from resolution so each rule is exercisable with a fabricated
    mapping: the composite-key rule has no offending model in this schema, and a
    test that can only skip is not a gate.
    """
    missing = sorted(set(tables) - by_table.keys())
    if missing:
        raise RuntimeError(f"AUTO_FILTERED_TABLES names tables with no mapped class: {missing}")

    without_column = sorted(t for t in tables if not hasattr(by_table[t], "is_active"))
    if without_column:
        raise RuntimeError(
            f"AUTO_FILTERED_TABLES names models with no is_active column, so nothing would be hidden: {without_column}"
        )

    # backend/db/soft_delete_writes.py::_parents_being_hidden_now identifies a
    # parent being hidden in the current flush by primary_key_from_instance()[0].
    # That is the whole key today and the check is exact; against a composite key
    # it would silently match on the first column alone and let a child attach to
    # a parent going out in the same flush. Gated here rather than left to be
    # discovered, because the failure is silent: the guard would still run, still
    # pass, and still be wrong.
    composite_pk = sorted(t for t in tables if len(inspect(by_table[t]).primary_key) > 1)
    if composite_pk:
        raise RuntimeError(
            "AUTO_FILTERED_TABLES names models with composite primary keys, which "
            "soft_delete_writes._parents_being_hidden_now cannot identify correctly "
            f"(it compares the first key column only): {composite_pk}"
        )


def _resolve_auto_filtered_models() -> Tuple[Any, ...]:
    from backend.database import Base

    by_table = {mapper.class_.__tablename__: mapper.class_ for mapper in Base.registry.mappers}
    _validate_auto_filtered(by_table, AUTO_FILTERED_TABLES)
    return tuple(by_table[table] for table in sorted(AUTO_FILTERED_TABLES))


def apply_active_row_filter(execute_state: Any) -> None:
    """``do_orm_execute`` listener: hide inactive rows of the declared models."""
    if not execute_state.is_select or execute_state.is_column_load:
        return
    if execute_state.execution_options.get(INCLUDE_INACTIVE) or execute_state.session.info.get(INCLUDE_INACTIVE):
        return
    for model in _AUTO_FILTERED_MODELS:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(model, model.is_active.is_(True), include_aliases=True)
        )


def install_active_row_filter() -> None:
    """Register the listener on the Session class. Idempotent."""
    global _AUTO_FILTERED_MODELS
    if event.contains(Session, "do_orm_execute", apply_active_row_filter):
        return
    _AUTO_FILTERED_MODELS = _resolve_auto_filtered_models()
    event.listen(Session, "do_orm_execute", apply_active_row_filter)


def auto_filtered_models() -> Tuple[Any, ...]:
    """The model classes the installed filter actually hides. Empty until installed."""
    return _AUTO_FILTERED_MODELS


@contextmanager
def include_inactive(session: Session) -> Iterator[Session]:
    """Suspend the filter for one block of reads on ``session``."""
    previous = session.info.get(INCLUDE_INACTIVE)
    session.info[INCLUDE_INACTIVE] = True
    try:
        yield session
    finally:
        if previous is None:
            session.info.pop(INCLUDE_INACTIVE, None)
        else:
            session.info[INCLUDE_INACTIVE] = previous
