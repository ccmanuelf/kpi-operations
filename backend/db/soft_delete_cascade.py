"""What blocks a soft delete, and why anything blocks it at all.

Hiding a parent while its children stay readable is incoherent: a hold that
references a work order nobody can see is a dangling row a user cannot explain
or clean up. Cascading the hide instead removes rows from KPIs that nobody
asked to delete, and does it silently.

The decided rule is the third option: **refuse the delete while anything
visible still references the row**, and say what. That failure is loud and
reversible — the caller is told exactly which children block, and can delete
them or leave the parent alone — where the alternatives fail silently.

The blocking set is derived from ``Base.metadata``'s foreign keys, not listed,
so a new table pointing at an auto-filtered parent starts blocking without
anyone remembering to declare it. Undeclared means INDEPENDENT means blocking —
the default refuses rather than removes.

Two declared kinds are cascaded instead of blocking (``ChildKind`` in the
registry carries the full reasoning): rows OWNED by the parent, whose FK to it
is NOT NULL so they cannot exist without it, and DERIVED rows that are
regenerable and therefore stale rather than lost once the parent is hidden.
Both had to be cascaded rather than merely stop blocking: a child that no
longer blocks but stays visible is precisely the dangling reference the 409
exists to prevent.

"Visible" is the operative word in the count: blockers are counted through the
ORM, so ``soft_delete_filter``'s criteria applies and an already-soft-deleted
child does not block. Deleting the children then the parent works; a parent
whose children are all gone is deletable again.

Concurrency — DOCUMENTED, NOT FIXED
-----------------------------------
The blocker count and the flag flip run in one transaction, but nothing
serialises them against a concurrent child INSERT in another transaction. Under
READ COMMITTED (MariaDB's effective default here) two sessions can interleave:
A counts zero blockers for a work order while B inserts a job against it, and
both commit. The result is a hidden parent with one visible child — the state
this module exists to prevent.

What narrows it in practice: ``backend/db/soft_delete_writes.py`` re-checks
parent visibility inside the *child's* own transaction at flush time, so any
child whose insert flushes after the delete commits is rejected. The residual
window is genuinely simultaneous transactions, not sequential API calls.

What would close it: ``SELECT ... FOR UPDATE`` on the parent row in both paths
(the delete taking the lock before counting, the child insert taking it before
flushing), or a database trigger. Neither is done. Row locks on WORK_ORDER
across every child write is a real throughput decision, not a mechanical fix,
and it belongs with someone who can weigh it against this deployment's actual
concurrency.
"""

from typing import Any, Dict, List, Tuple

from backend.database import Base
from backend.db.soft_delete_registry import (
    AUTO_FILTERED_TABLES,
    CASCADE_KINDS,
    CHILD_CLASSIFICATION,
    ChildKind,
)


def _model_for(table_name: str) -> Any:
    for mapper in Base.registry.mappers:
        if mapper.class_.__tablename__ == table_name:
            return mapper.class_
    return None


def kind_of(child_table: str) -> ChildKind:
    """Declared kind, defaulting to INDEPENDENT for anything unclassified."""
    entry = CHILD_CLASSIFICATION.get(child_table)
    return entry[0] if entry else ChildKind.INDEPENDENT


def _dependents(table_name: str) -> List[Tuple[str, str, str]]:
    """(child table, child FK column, parent PK column), read off the FK graph
    every call rather than cached, so a metadata change cannot leave a stale
    answer behind in a long-lived process."""
    dependents = []
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table.name == table_name:
                dependents.append((table.name, fk.parent.name, fk.column.name))
    return sorted(dependents)


def blocking_dependents(table_name: str) -> List[Tuple[str, str, str]]:
    """Dependents that refuse the parent's delete (the INDEPENDENT ones)."""
    return [d for d in _dependents(table_name) if kind_of(d[0]) is ChildKind.INDEPENDENT]


def cascade_dependents(table_name: str) -> List[Tuple[str, str, str]]:
    """Dependents hidden along with the parent (OWNED and DERIVED)."""
    return [d for d in _dependents(table_name) if kind_of(d[0]) in CASCADE_KINDS]


def cascade_children(db: Any, entity: Any) -> List[Any]:
    """Still-visible rows that must be hidden along with ``entity``.

    Only rows that CAN be hidden are returned: the three append-only logs and
    the allocation table have no ``is_active`` column and no endpoint of their
    own, so they become unreachable with their parent and there is nothing to
    write. Returning them would imply a hide that does not happen.
    """
    table_name = entity.__tablename__
    if table_name not in AUTO_FILTERED_TABLES:
        return []

    children: List[Any] = []
    for child_table, fk_column, parent_column in cascade_dependents(table_name):
        if child_table not in AUTO_FILTERED_TABLES:
            continue
        child_model = _model_for(child_table)
        if child_model is None:
            continue
        parent_value = getattr(entity, parent_column, None)
        if parent_value is None:
            continue
        child_fk = getattr(child_model, fk_column, None)
        if child_fk is None:
            continue
        children.extend(db.query(child_model).filter(child_fk == parent_value).all())
    return children


def visible_child_blockers(db: Any, entity: Any) -> Dict[str, int]:
    """Count the still-visible rows that reference ``entity``, per child table.

    Empty dict means the delete is allowed.
    """
    from sqlalchemy import func

    table_name = entity.__tablename__
    if table_name not in AUTO_FILTERED_TABLES:
        return {}

    blockers: Dict[str, int] = {}
    for child_table, fk_column, parent_column in blocking_dependents(table_name):
        child_model = _model_for(child_table)
        if child_model is None:
            continue
        parent_value = getattr(entity, parent_column, None)
        if parent_value is None:
            continue
        child_fk = getattr(child_model, fk_column, None)
        if child_fk is None:
            continue
        # Counted through the ORM on purpose: the auto-filter applies, so a
        # child that has itself been soft-deleted is not a blocker.
        count = db.query(func.count()).select_from(child_model).filter(child_fk == parent_value).scalar()
        if count:
            blockers[child_table] = int(count)
    return blockers
