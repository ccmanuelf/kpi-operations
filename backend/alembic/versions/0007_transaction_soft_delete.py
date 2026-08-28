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

from typing import Sequence, Union

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


def downgrade() -> None:
    for table in reversed(TABLES):
        for name in reversed(COLUMN_NAMES):
            op.drop_column(table, name)
