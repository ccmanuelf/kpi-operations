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
    conn = op.get_bind()

    # BEFORE any DDL, and deliberately so. MariaDB commits DDL implicitly, so a
    # refusal raised after add_column would leave the column behind with the
    # revision unrecorded -- and the re-run, once the duplicates were resolved,
    # would fail on "duplicate column name" instead of doing the work. Nothing
    # has been mutated at this point, so refusing here leaves the database
    # exactly as it was found.
    #
    # Failing with the rows NAMED beats a bare 1062 partway through a deploy.
    # The constraint cannot be added over contradictory data, and picking a
    # winner between two coverage records is not a migration's decision to
    # make -- whoever entered them has to say which one is right.
    duplicates = (
        conn.execute(
            sa.text(
                "SELECT client_id, coverage_date, shift_id, COUNT(*) AS n "
                # `WHERE is_active`, not `is_active = 1`: it has to agree with the
                # backfill below, which marks rows by the same truthiness. A
                # predicate that disagreed would let a row the backfill treats as
                # active go uncounted here, and the constraint would then fail on
                # data this check had already passed.
                "FROM shift_coverage WHERE is_active "
                "GROUP BY client_id, coverage_date, shift_id HAVING COUNT(*) > 1"
            )
        )
        .mappings()
        .all()
    )
    if duplicates:
        listed = ", ".join(
            f"(client {r['client_id']}, {r['coverage_date']}, shift {r['shift_id']}: {r['n']} rows)"
            for r in duplicates[:10]
        )
        raise RuntimeError(
            f"shift_coverage holds {len(duplicates)} duplicated active key(s); "
            f"uq_shift_coverage_active cannot be added until each is resolved. "
            f"First: {listed}"
        )

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
        # Keeps the marker meaningful: an active row must be marked and a
        # deleted one must not. Without it a raw INSERT of
        # (is_active=1, active_marker=NULL) is an active row the unique index
        # never sees, since NULLs do not collide -- the duplicate the
        # constraint above exists to forbid.
        batch.create_check_constraint(
            "ck_shift_coverage_active_marker",
            (
                "(is_active = 1 AND active_marker IS NOT NULL AND active_marker = 1)"
                " OR (is_active = 0 AND active_marker IS NULL)"
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("shift_coverage") as batch:
        batch.drop_constraint("ck_shift_coverage_active_marker", type_="check")
        batch.drop_constraint("uq_shift_coverage_active", type_="unique")
    op.drop_column("shift_coverage", "active_marker")
