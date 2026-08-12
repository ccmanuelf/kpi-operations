"""Audit trail table (Project A, PR A1).

Revision ID: 0005_audit_trail
Revises: 0004_labor_hours
Create Date: 2026-08-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_audit_trail"
down_revision: Union[str, None] = "0004_labor_hours"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "AUDIT_ENTRY",
        sa.Column("entry_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=50), nullable=True),
        sa.Column("actor_username", sa.String(length=100), nullable=True),
        sa.Column("table_name", sa.String(length=64), nullable=False),
        sa.Column("record_pk", sa.String(length=64), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("INSERT", "UPDATE", "DELETE", name="auditoperation"),
            nullable=False,
        ),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("client_id", sa.String(length=50), nullable=True),
        sa.Column("request_method", sa.String(length=8), nullable=True),
        sa.Column("request_path", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index("ix_audit_entity", "AUDIT_ENTRY", ["table_name", "record_pk"])
    op.create_index(op.f("ix_AUDIT_ENTRY_occurred_at"), "AUDIT_ENTRY", ["occurred_at"])
    op.create_index(op.f("ix_AUDIT_ENTRY_actor_user_id"), "AUDIT_ENTRY", ["actor_user_id"])
    op.create_index(op.f("ix_AUDIT_ENTRY_table_name"), "AUDIT_ENTRY", ["table_name"])
    op.create_index(op.f("ix_AUDIT_ENTRY_client_id"), "AUDIT_ENTRY", ["client_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_AUDIT_ENTRY_client_id"), table_name="AUDIT_ENTRY")
    op.drop_index(op.f("ix_AUDIT_ENTRY_table_name"), table_name="AUDIT_ENTRY")
    op.drop_index(op.f("ix_AUDIT_ENTRY_actor_user_id"), table_name="AUDIT_ENTRY")
    op.drop_index(op.f("ix_AUDIT_ENTRY_occurred_at"), table_name="AUDIT_ENTRY")
    op.drop_index("ix_audit_entity", table_name="AUDIT_ENTRY")
    op.drop_table("AUDIT_ENTRY")
