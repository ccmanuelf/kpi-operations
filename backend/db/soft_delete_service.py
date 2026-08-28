"""The single entry point every auto-filtered DELETE path goes through.

Three things have to happen together on a soft delete, and each was previously
either missing or left to whoever wrote the CRUD function:

1. refuse the delete if something visible still references the row (409, with
   the blockers named) — see backend/db/soft_delete_cascade.py;
2. flip ``is_active`` so the row stops being readable;
3. cascade the hide to rows that are part of the parent (OWNED) or are stale
   derivations of it (DERIVED), so nothing visible is left pointing at a hidden
   row;
4. record *who* deleted it and *when*, so a soft-deleted row is distinguishable
   from one that was never active. Without this, soft delete is worse than a
   hard delete in one specific way: a hard delete leaves an absence somebody
   might notice. Cascaded rows are attributed to the same actor and get their
   own AUDIT_ENTRY, so the trail shows everything that disappeared.

Putting all three behind one call is what makes them non-optional.
``tests/test_db/test_soft_delete_registry_guards.py`` scans backend/crud and
fails if a module that soft-deletes an auto-filtered table reaches for the bare
``soft_delete()`` helper instead of this.
"""

from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, status

from backend.db.soft_delete_cascade import cascade_children, visible_child_blockers
from backend.utils.soft_delete import soft_delete_with_timestamp


def _conflict(entity: Any, blockers: Dict[str, int]) -> HTTPException:
    """409 that names what blocks, not a bare status.

    The caller has to be able to act on this without guessing, so the body
    carries the child tables and how many visible rows each still has.
    """
    listed = ", ".join(f"{table} ({count})" for table, count in sorted(blockers.items()))
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": (
                f"Cannot delete this {entity.__tablename__} record while other records still "
                f"reference it. Delete or reassign them first: {listed}."
            ),
            "blocked_by": [{"table": table, "count": count} for table, count in sorted(blockers.items())],
        },
    )


def _cascade_plan(db: Any, entity: Any) -> List[Any]:
    """``entity`` plus every row that must be hidden with it, children first.

    Depth-first with a visited set so a cascade chain (a work order's alerts,
    an inspection's defects) is handled without assuming a depth, and a cycle
    in the FK graph could not loop forever.
    """
    plan: List[Any] = []
    seen: Set[int] = set()

    def visit(row: Any) -> None:
        if id(row) in seen:
            return
        seen.add(id(row))
        for child in cascade_children(db, row):
            visit(child)
        plan.append(row)

    visit(entity)
    return plan


def soft_delete_record(db: Any, entity: Any, current_user: Any = None, commit: bool = True) -> bool:
    """Block, cascade, hide, and attribute — in that order.

    Raises HTTPException 409 when INDEPENDENT children still reference anything
    in the cascade. Returns True on success; the route turns that into its 204.

    Blockers are checked across the WHOLE cascade before anything is written, so
    a refusal leaves nothing half-hidden: if a defect detail were itself blocked,
    the inspection above it must not have been hidden already.
    """
    plan = _cascade_plan(db, entity)

    for row in plan:
        blockers = visible_child_blockers(db, row)
        if blockers:
            raise _conflict(row, blockers)

    deleted_by: Optional[str] = getattr(current_user, "user_id", None) if current_user is not None else None
    for row in plan:
        if not soft_delete_with_timestamp(db, row, commit=False, deleted_by_value=deleted_by):
            return False

    if commit:
        db.commit()
    return True
