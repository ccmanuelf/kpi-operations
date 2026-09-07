"""One ACTIVE shift-coverage record per client, date and shift.

Nothing stopped two coverage rows for the same client, date and shift, which
is two contradictory answers to one question -- and the application-level
check that now rejects the common case is SELECT-then-INSERT, so two creates
racing inside the same millisecond both pass it. The database is the only
place the invariant can actually hold.

A plain UNIQUE on the three business columns will not do it: the table is soft
deleted, so a removed row would hold its slot forever and a
mistakenly-entered-then-deleted record could never be re-entered. The partial
index that would express "unique among active rows" does not exist on MariaDB.

So the constraint includes ``active_marker``, which is 1 while the row is live
and NULL once it is soft deleted. Both dialects exclude NULLs from uniqueness,
which was verified against MariaDB 11.4 rather than assumed:

    second live row for the same key   -> ERROR 1062
    delete, then enter it again        -> allowed
    many deleted rows sharing a key    -> allowed (3 coexisted)

The column is derived from ``is_active`` by a mapper event in
backend/orm/coverage.py, so no code path that flips one can leave the other
stale.

Backfill: existing rows are marked from their current ``is_active`` before the
constraint is added, or every one of them would carry NULL and the index would
be built against a column that means nothing. Checked first on the live data
-- 112 active rows, 0 duplicate keys -- so the constraint applies cleanly.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_coverage_active_uniqueness"
down_revision: Union[str, None] = "0007_transaction_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shift_coverage", sa.Column("active_marker", sa.Integer(), nullable=True))

    # Derive from the existing soft-delete state BEFORE the constraint exists,
    # so the index is built over meaningful values.
    op.execute("UPDATE shift_coverage SET active_marker = CASE WHEN is_active THEN 1 ELSE NULL END")

    # batch_alter_table, because SQLite cannot ALTER a table to add a
    # constraint -- it needs the copy-and-move strategy. On MariaDB this
    # compiles to a plain ALTER, so one code path serves both dialects.
    with op.batch_alter_table("shift_coverage") as batch:
        batch.create_unique_constraint(
            "uq_shift_coverage_active",
            ["client_id", "coverage_date", "shift_id", "active_marker"],
        )


def downgrade() -> None:
    with op.batch_alter_table("shift_coverage") as batch:
        batch.drop_constraint("uq_shift_coverage_active", type_="unique")
    op.drop_column("shift_coverage", "active_marker")
