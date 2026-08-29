"""Soft-delete columns on the twelve soft-deletable tables (S1).

Revision ID: 0007_transaction_soft_delete
Revises: 0006_hold_status_history
Create Date: 2026-08-27

Eleven DELETE endpoints returned 404 for every id, valid ones included: the
CRUD layer soft-deletes by setting ``is_active = False`` and none of these
models had the column.

Seven were found by the contract harness. The other four — ``/api/jobs``,
``/api/coverage``, ``/api/floating-pool``, ``/api/part-opportunities`` — have
the identical defect and were invisible to it only because the seeder writes no
rows for them, so they were filed as a seed gap rather than a 404. One defect,
sorted into two buckets by an accident of test data.

Existing rows default to active (``server_default="1"``), so the upgrade is a
no-op for live data. No index: the column is ~100% true on high-volume tables,
so a single-column index would never be selective enough to be chosen and would
only cost write throughput.

``deleted_at`` / ``deleted_by`` come with it, because ``is_active`` alone makes
a soft-deleted row indistinguishable from one that was never active — worse
than a hard delete, which at least leaves an absence someone might notice. Both
are nullable with no default: NULL means "not deleted", which is exactly true
of every existing row.
"""

import os
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_transaction_soft_delete"
down_revision: Union[str, None] = "0006_hold_status_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Kept in lockstep with backend/db/soft_delete_registry.AUTO_FILTERED_TABLES;
#: tests/test_db/test_soft_delete_registry_guards.py fails if they diverge.
TABLES: tuple[str, ...] = (
    "ATTENDANCE_ENTRY",
    "DEFECT_DETAIL",
    "DOWNTIME_ENTRY",
    "FLOATING_POOL",
    "HOLD_ENTRY",
    "JOB",
    "PART_OPPORTUNITIES",
    "PRODUCTION_ENTRY",
    "QUALITY_ENTRY",
    "WORK_ORDER",
    "shift_coverage",
    # No DELETE endpoint of its own; soft-deletable so a work order's delete can
    # cascade the hide to its stale, regenerable alerts.
    "ALERT",
)


#: Column names in add order; the downgrade drops them in reverse.
COLUMN_NAMES: tuple[str, ...] = ("is_active", "deleted_at", "deleted_by")


def _columns() -> list:
    """Fresh Column objects per call.

    A module-level tuple of Columns cannot be reused across ``op.add_column``
    calls (a Column binds to the first table it is added to), and ``.copy()``
    is deprecated in SQLAlchemy 2.0 — which this suite treats as an error.

    ``deleted_by`` carries no FK to USER on purpose: it is a historical record
    that must stay readable after that user is renamed or deactivated, matching
    AUDIT_ENTRY.actor_user_id. It also keeps this a plain ADD COLUMN, where a FK
    constraint would need a SQLite batch table rebuild on 37k rows.
    """
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(length=50), nullable=True),
    ]


def upgrade() -> None:
    for table in TABLES:
        for column in _columns():
            op.add_column(table, column)


#: Downgrading DROPS ``is_active``, which makes every soft-deleted row visible
#: again and puts it straight back into KPI aggregates. It does so *silently*:
#: ``deleted_at`` and ``deleted_by`` are dropped in the same breath, so a
#: resurrected row becomes indistinguishable from one that was never deleted,
#: and nothing records that it came back. That is a data-integrity event, not a
#: schema step, so the downgrade refuses while any such row exists. Set this to
#: "1" to acknowledge the resurrection and proceed anyway.
ACKNOWLEDGE_RESURRECTION_ENV = "ALLOW_SOFT_DELETE_DOWNGRADE"


def _soft_deleted_counts() -> dict:
    """Rows each table would resurrect, counted through the live connection.

    Built with ``sa.table``/``sa.column`` rather than a ``text()`` string so
    identifier quoting is the dialect's own: these names are mixed-case
    (``shift_coverage`` beside ``WORK_ORDER``), and SQLite and MariaDB do not
    quote them the same way.

    Only ``is_active = 0`` is counted, not NULL. Cross-model review asked for a
    NULL branch as defence against schema drift; there is nothing for it to
    defend. The column is created NOT NULL here and both dialects enforce it —
    SQLite rejects the write outright — so no test can reach that branch, and an
    unreachable branch is decoration rather than a guard. If a later revision
    ever makes the column nullable, this predicate is what it must revisit.

    This count is not atomic with the DROP COLUMNs that follow it: a row
    soft-deleted in between is not counted and comes back with no
    deleted_at/deleted_by trace. Run migrations with the application stopped,
    which is the assumption every destructive migration here already makes.
    """
    bind = op.get_bind()
    present = {name for name in TABLES if _has_soft_delete_columns(bind, name)}
    if present and len(present) != len(TABLES):
        missing = sorted(set(TABLES) - present)
        raise RuntimeError(
            "This database is stamped at 0007 but only some tables carry the soft-delete "
            f"columns, so it was migrated by an earlier, since-edited version of this "
            f"revision. Tables still missing them: {missing}. Run "
            "`alembic stamp 0006_hold_status_history` and then upgrade again."
        )

    counts = {}
    for name in TABLES:
        table = sa.table(name, sa.column("is_active"))
        statement = sa.select(sa.func.count()).select_from(table).where(table.c.is_active == 0)
        count = bind.execute(statement).scalar() or 0
        if count:
            counts[name] = int(count)
    return counts


def _has_soft_delete_columns(bind: Any, table_name: str) -> bool:
    """Whether ``table_name`` carries all three columns this revision adds.

    Asked before counting so a half-applied 0007 fails with an instruction
    instead of a raw driver error about an unknown column.
    """
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    return set(COLUMN_NAMES) <= existing


def downgrade() -> None:
    counts = _soft_deleted_counts()
    if counts and os.environ.get(ACKNOWLEDGE_RESURRECTION_ENV) != "1":
        listed = ", ".join(f"{table} ({count})" for table, count in sorted(counts.items()))
        raise RuntimeError(
            f"Refusing to downgrade: {sum(counts.values())} soft-deleted row(s) would become "
            f"visible again and re-enter KPI aggregates — {listed}. Their deleted_at/deleted_by "
            f"are dropped with the columns, so the resurrection would leave no trace. Hard-delete "
            f"them first, or set {ACKNOWLEDGE_RESURRECTION_ENV}=1 for this one command. Do not "
            "export it persistently: it would silence this check for every future downgrade."
        )
    for table in reversed(TABLES):
        for name in reversed(COLUMN_NAMES):
            op.drop_column(table, name)
