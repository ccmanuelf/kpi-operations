"""Labor-hours capture columns + allocation table (Cycle 3 PR-A).

Revision ID: 0004_labor_hours
Revises: 0003_justified_delay
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_labor_hours"
down_revision: Union[str, None] = "0003_justified_delay"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ATTENDANCE_ENTRY", sa.Column("normal_hours", sa.Numeric(5, 2), nullable=True))
    op.add_column("ATTENDANCE_ENTRY", sa.Column("double_hours", sa.Numeric(5, 2), nullable=True))
    op.add_column("ATTENDANCE_ENTRY", sa.Column("triple_hours", sa.Numeric(5, 2), nullable=True))
    op.add_column("ATTENDANCE_ENTRY", sa.Column("labor_class_override", sa.String(length=10), nullable=True))
    op.add_column("EMPLOYEE", sa.Column("labor_class", sa.String(length=10), nullable=True))
    op.create_table(
        "ATTENDANCE_HOUR_ALLOCATION",
        sa.Column("allocation_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attendance_entry_id", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("hours", sa.Numeric(5, 2), nullable=False),
        sa.ForeignKeyConstraint(["attendance_entry_id"], ["ATTENDANCE_ENTRY.attendance_entry_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("allocation_id"),
        sa.UniqueConstraint("attendance_entry_id", "category", name="uq_attendance_allocation_category"),
    )
    op.create_index(
        op.f("ix_ATTENDANCE_HOUR_ALLOCATION_attendance_entry_id"),
        "ATTENDANCE_HOUR_ALLOCATION",
        ["attendance_entry_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ATTENDANCE_HOUR_ALLOCATION_attendance_entry_id"), table_name="ATTENDANCE_HOUR_ALLOCATION")
    op.drop_table("ATTENDANCE_HOUR_ALLOCATION")
    op.drop_column("EMPLOYEE", "labor_class")
    op.drop_column("ATTENDANCE_ENTRY", "labor_class_override")
    op.drop_column("ATTENDANCE_ENTRY", "triple_hours")
    op.drop_column("ATTENDANCE_ENTRY", "double_hours")
    op.drop_column("ATTENDANCE_ENTRY", "normal_hours")
