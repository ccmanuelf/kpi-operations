"""Justified-delay classification columns (Cycle 2) — first DDL since baseline.

Three nullable WORK_ORDER columns; no data pass (NULL = unclassified default).

Revision ID: 0003_justified_delay
Revises: 0002_downtime_taxonomy
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_justified_delay"
down_revision: Union[str, None] = "0002_downtime_taxonomy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("WORK_ORDER", sa.Column("delay_classification", sa.String(length=20), nullable=True))
    op.add_column("WORK_ORDER", sa.Column("justified_delay_reason", sa.String(length=40), nullable=True))
    op.add_column("WORK_ORDER", sa.Column("delay_classification_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("WORK_ORDER", "delay_classification_note")
    op.drop_column("WORK_ORDER", "justified_delay_reason")
    op.drop_column("WORK_ORDER", "delay_classification")
