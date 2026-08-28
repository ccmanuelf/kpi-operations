"""Soft-delete flag on the seven transaction tables (S1).

Revision ID: 0007_transaction_soft_delete
Revises: 0006_hold_status_history
Create Date: 2026-08-27

DELETE /api/{attendance,defects,downtime,holds,production,quality,work-orders}
returned 404 for every id, valid ones included: the CRUD layer soft-deletes by
setting ``is_active = False`` and none of these seven models had the column.

Existing rows default to active (``server_default="1"``), so the upgrade is a
no-op for live data. No index: the column is ~100% true on high-volume tables,
so a single-column index would never be selective enough to be chosen and would
only cost write throughput.
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
    "HOLD_ENTRY",
    "PRODUCTION_ENTRY",
    "QUALITY_ENTRY",
    "WORK_ORDER",
)


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_column(table, "is_active")
