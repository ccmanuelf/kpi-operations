"""Hold-status transition history (Cycle 4 PR-C1).

Revision ID: 0006_hold_status_history
Revises: 0005_audit_trail
Create Date: 2026-08-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_hold_status_history"
down_revision: Union[str, None] = "0005_audit_trail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "HOLD_STATUS_TRANSITION",
        sa.Column("transition_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hold_entry_id", sa.String(length=50), nullable=False),
        sa.Column("client_id", sa.String(length=50), nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=False),
        sa.Column("transitioned_by", sa.String(length=50), nullable=True),
        sa.Column("transitioned_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["hold_entry_id"], ["HOLD_ENTRY.hold_entry_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["CLIENT.client_id"]),
        sa.ForeignKeyConstraint(["transitioned_by"], ["USER.user_id"]),
        sa.PrimaryKeyConstraint("transition_id"),
    )
    op.create_index("ix_hold_transition_hold", "HOLD_STATUS_TRANSITION", ["hold_entry_id"])
    op.create_index("ix_hold_transition_client_date", "HOLD_STATUS_TRANSITION", ["client_id", "transitioned_at"])
    op.create_index("ix_hold_transition_status", "HOLD_STATUS_TRANSITION", ["to_status", "transitioned_at"])
    # Covers active_as_of's correlated subquery (ORDER BY transitioned_at DESC,
    # transition_id DESC LIMIT 1 per hold_entry_id) -- observed as a per-hold
    # filesort on live MariaDB without it; /wip-aging/trend runs one
    # correlated evaluation per hold PER DAY in the range.
    op.create_index(
        "ix_hold_transition_hold_asof", "HOLD_STATUS_TRANSITION", ["hold_entry_id", "transitioned_at", "transition_id"]
    )
    op.create_index(op.f("ix_HOLD_STATUS_TRANSITION_transitioned_at"), "HOLD_STATUS_TRANSITION", ["transitioned_at"])


def downgrade() -> None:
    # Do NOT drop the explicit indexes first: on MariaDB/InnoDB, the FKs on
    # hold_entry_id and client_id have no other covering index once those
    # are dropped, so `DROP INDEX ix_hold_transition_client_date` (etc.)
    # fails with errno 1553 ("needed in a foreign key constraint") before
    # `drop_table` ever runs. MySQL DDL is not transactional, so that failure
    # leaves the DB at neither 0006 nor 0005. `drop_table` alone removes the
    # table's indexes along with it.
    op.drop_table("HOLD_STATUS_TRANSITION")
