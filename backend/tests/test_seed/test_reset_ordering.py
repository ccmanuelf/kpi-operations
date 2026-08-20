"""What `--reset` executes, in what ORDER, and the one SELF-REFERENTIAL
foreign key no order can satisfy.

"Order-safe" is NOT the same as "reset-safe", and this module only proves the
first. See `_reset`'s docstring in backend/seed/cli.py for the second
unorderable shape -- a swept child with a NULLABLE tenant column -- which no
sequence can fix and which nothing here asserts.

The rest of the --reset guarding lives in test_cli.py and asserts on SETS:
CLIENT_SCOPED_TABLES is complete, DEPENDENT_SWEEPS is complete, every swept
table receives a DELETE. None of that says anything about SEQUENCE, which is
the entire reason `_reset` walks `reversed(INSERT_ORDER)` -- so it gets its
own module rather than another paragraph in a file already well past 500
lines.
"""

from datetime import date

from sqlalchemy import event, func, insert, select
from sqlalchemy.sql import Delete

from backend.database import Base
from backend.seed.cli import CLIENT_SCOPED_TABLES, DEPENDENT_SWEEPS, SELF_REFERENTIAL_SWEEPS, seed

SWEPT = set(CLIENT_SCOPED_TABLES) | {child for child, _, _, _ in DEPENDENT_SWEEPS}


def _seed_smoke(engine, *, reset: bool) -> None:
    """A smoke seed of one client, which is enough for both tests here: the
    ordering assertion reads the statements _reset issues, not the rows they
    hit. A function rather than a shared `**kwargs` dict so the call keeps its
    declared parameter types."""
    seed(
        engine,
        client_ids=("DEMO-PIECE",),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 18),
        reset=reset,
    )


#: A parent line and a section under it, named so the PARENT SORTS FIRST.
#:
#: That is not decoration, it is the whole reproduction. `DELETE FROM
#: PRODUCTION_LINE WHERE client_id IN (...)` is planned by MariaDB 11.4 over
#: uq_production_line_client_code (client_id, line_code), so InnoDB visits the
#: matching rows in LINE_CODE order and checks the self-referential foreign key
#: as it goes. Parent first means the child still points at it: ERROR 1451,
#: `Cannot delete or update a parent row`. Child first happens to succeed.
#:
#: Measured against a live mariadb:11.4.12 container, one plain DELETE per
#: pair, foreign keys on: 'SEW-01' + 'SEW-01-A' raises 1451; the same pair
#: named 'RESET-PARENT' + 'RESET-CHILD' does not, purely because 'C' < 'P'.
#: A guard planted with the second naming is green either way and proves
#: nothing -- and the failing naming is the ORDINARY one, since a section is
#: conventionally named after the line it belongs to.
PARENT_LINE_CODE = "SEW-01"
CHILD_LINE_CODE = "SEW-01-A"


def _required_delete_order() -> list:
    """(child, column, parent) for every ForeignKey between two SWEPT tables.

    The partial order `_reset` must respect, DERIVED from live metadata rather
    than restated as a table list: a child's rows must be deleted before the
    parent rows they point at, or the DELETE is RESTRICTed (MariaDB/InnoDB
    always; SQLite whenever `PRAGMA foreign_keys=ON`). Self-references are
    excluded -- no table-level ordering can resolve one, which is what
    SELF_REFERENTIAL_SWEEPS is for.
    """
    edges = []
    for table in Base.metadata.sorted_tables:
        if table.name not in SWEPT:
            continue
        for column in table.columns:
            for fk in column.foreign_keys:
                parent = fk.column.table.name
                if parent in SWEPT and parent != table.name:
                    edges.append((table.name, column.name, parent))
    return sorted(edges)


def _executed_deletes(seed_engine) -> list:
    """Table names in the order `--reset` issues DELETEs against them."""
    deleted = []

    @event.listens_for(seed_engine, "before_execute")
    def _capture(conn, clauseelement, multiparams, params, execution_options):  # noqa: ANN001, ARG001
        if isinstance(clauseelement, Delete):
            deleted.append(clauseelement.table.name)

    try:
        _seed_smoke(seed_engine, reset=True)
    finally:
        event.remove(seed_engine, "before_execute", _capture)
    return deleted


def test_reset_deletes_every_swept_table_children_before_parents(seed_engine):
    """What --reset EXECUTES and in WHICH ORDER, not what its constants SAY.

    Two failures, one capture. The membership half is the C-2 anti-rot guard
    this test used to be on its own: only four of the 47 swept tables are
    covered behaviourally by the seed-insert-reset repros in test_cli.py, so a
    per-table hole in the sweep loop passed the whole suite -- `if name ==
    "EQUIPMENT": continue` planted as the loop's first statement gave 151
    passed while a live --reset raised `IntegrityError: FOREIGN KEY constraint
    failed`.

    The ORDER half is what that version threw away. The listener records issue
    order and the assertion then collapsed it with `set(deleted) == expected`,
    so nothing constrained the sequence that is the whole point of walking
    `reversed(INSERT_ORDER)`. A FULL reversal is caught incidentally, and only
    incidentally: 22 of the 47 swept tables hold rows in a smoke seed, so
    walking INSERT_ORDER forwards fails eight OTHER tests in test_cli.py on a
    plain `sqlite3.IntegrityError: FOREIGN KEY constraint failed`. The other
    25 tables are empty in every test in this repo, so reordering just those
    is invisible -- while --reset breaks on any demo where the capacity or BOM
    module has been used. Measured: moving the 13 capacity_* tables to the
    front of the sweep (`sorted(reversed(INSERT_ORDER), key=lambda n: not
    n.startswith("capacity_"))`) left 164 of the seed suite's 165 tests green,
    the single failure being this assertion naming
    PRODUCTION_LINE.capacity_line_id -> capacity_production_lines and
    WORK_ORDER.capacity_order_id -> capacity_orders.

    The information was already in the listener; this stops discarding it.
    Comparing FIRST-issue index per table against the metadata-derived partial
    order covers all 47 at once, which is far cheaper than parametrising the
    seed-insert-reset repro 47 times.

    DEPENDENT_SWEEPS IS FOLDED IN, not exempted. Its three children are
    deleted by subquery in the first pass, before anything else, so they
    already satisfy child-before-parent against their scoped parents (ALERT,
    CALCULATION_ASSUMPTION, ATTENDANCE_ENTRY) and the derivation needs no
    special case. Folding them in also means a future table inside the sweep
    that acquires a ForeignKey INTO one of those three is caught here, since
    it would then have to be deleted before a table the first pass already
    cleared.
    """
    _seed_smoke(seed_engine, reset=False)

    deleted = _executed_deletes(seed_engine)

    first = {}
    for position, name in enumerate(deleted):
        first.setdefault(name, position)

    assert set(deleted) == SWEPT

    edges = _required_delete_order()
    # Non-vacuity: an empty derivation would satisfy the ordering assertion
    # for any sweep order at all. 90 edges today, and edges are only ever
    # added by new tables, so a floor rather than an equality.
    assert len(edges) >= 80

    assert [f"{child}.{column} -> {parent}" for child, column, parent in edges if first[child] > first[parent]] == []


def test_reset_survives_a_line_hierarchy_the_production_lines_api_can_create(seed_engine):
    """The one SELF-REFERENTIAL foreign key no TABLE order can satisfy.

    Not the only unorderable shape in the schema -- see `_reset` for the
    nullable-tenant-column one, which reproduces on SQLite too.

    PRODUCTION_LINE.parent_line_id -> PRODUCTION_LINE.line_id is the only
    self-referential ForeignKey in all 60 tables, it declares no ondelete, and
    it is inside the --reset sweep. InnoDB checks it per row as the DELETE
    visits rows, so whether --reset survives comes down to which row the plan
    reaches first -- and reordering the sweep cannot help, because there is
    only one table involved. See PARENT_LINE_CODE for the measured mechanism
    and the naming that decides it.

    One supervisor-level `POST /api/production-lines/` carrying a
    parent_line_id is the whole reproduction: this test plants exactly that
    pair, then resets. LATENT rather than live before the fix, which is why
    the branch's own MariaDB CI step could not see it -- the seeder writes no
    line hierarchy itself, so the seed suite is green on InnoDB either way.
    `_reset` now NULLs every derived self-reference before the sweep, so the
    visit order stops mattering.

    STATED LIMITATION, measured rather than assumed: this test BITES ON
    MARIADB AND NOT ON SQLITE. With the fix reverted it fails on
    mariadb:11.4.12 with ERROR 1451 and passes on SQLite, whose planner
    reaches the child first for this pair even with PRAGMA foreign_keys=ON.
    It therefore guards the production dialect through
    ci.yml::mariadb-portability's "Seed suite on MariaDB" step and is a
    non-regression smoke test on a developer laptop -- which is exactly why
    that step, and the env block test_ci_workflow_gates pins to it, are load
    bearing rather than decorative.
    """
    _seed_smoke(seed_engine, reset=False)

    line = Base.metadata.tables["PRODUCTION_LINE"]
    with seed_engine.begin() as conn:
        parent_id = conn.execute(
            insert(line).values(
                client_id="DEMO-PIECE", line_code=PARENT_LINE_CODE, line_name="Sewing 1", line_type="SHARED"
            )
        ).inserted_primary_key[0]
        conn.execute(
            insert(line).values(
                client_id="DEMO-PIECE",
                line_code=CHILD_LINE_CODE,
                line_name="Sewing 1 Section A",
                line_type="SECTION",
                parent_line_id=parent_id,
            )
        )

    # Must not raise: this is the repro.
    _seed_smoke(seed_engine, reset=True)

    with seed_engine.connect() as conn:
        planted = conn.execute(
            select(func.count()).select_from(line).where(line.c.line_code.in_((PARENT_LINE_CODE, CHILD_LINE_CODE)))
        ).scalar_one()

    assert planted == 0


def test_the_self_referential_sweep_is_derived_and_names_the_production_line():
    """The derivation, pinned from both sides.

    SELF_REFERENTIAL_SWEEPS is computed from Base.metadata so a second
    self-reference added later is handled without a code change -- which also
    means a derivation that silently computed to () would leave the test above
    passing on SQLite in some future schema while --reset broke on InnoDB.
    Naming the one pair that exists today makes the derivation collapsing an
    explicit failure.
    """
    assert SELF_REFERENTIAL_SWEEPS == (("PRODUCTION_LINE", "parent_line_id"),)
