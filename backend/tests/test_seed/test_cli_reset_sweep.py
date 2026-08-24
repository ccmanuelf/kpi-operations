"""How the --reset sweep TRAVERSES foreign keys to reach the right rows:
client-scoped children the seeder never wrote, grandchildren reachable only
through DEPENDENT_SWEEPS, and the nullable-tenant / foreign-tenant edges the
sweep must not cross.

Split out of test_cli.py's original body. test_cli.py keeps the CLI surface
and contract tests; test_cli_reset.py covers what a re-seed must preserve;
test_cli_derived_sets.py covers the structural guards over derived table sets.
"""

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, insert, select

from backend.database import Base
from backend.seed.cli import seed
from backend.tests.test_seed._reset_row_builders import (
    CHILD_ROW_BUILDERS,
    _insert_alert_history,
    _insert_null_tenant_alert_history,
)


@pytest.mark.parametrize("case", sorted(CHILD_ROW_BUILDERS))
def test_reset_clears_a_client_scoped_row_the_seeder_never_wrote(seed_engine, case):
    """--reset on an ordinary live demo, not a pristine one.

    The plan restricted the sweep to `SEEDED` -- what the seeder WRITES --
    while --reset must clear what the tenant OWNS. 45 tables hold a
    ForeignKey into CLIENT and the seeder writes 23, so every one of the
    other 22 held rows that RESTRICT the final DELETE FROM "CLIENT". All four
    cases below raised `IntegrityError: FOREIGN KEY constraint failed`
    before the sweep was widened to cli.CLIENT_SCOPED_TABLES; MariaDB/InnoDB
    enforces foreign keys unconditionally, so the VM path failed identically.
    """
    builder, table_name, column = CHILD_ROW_BUILDERS[case]
    table = Base.metadata.tables[table_name]
    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))

    seed(seed_engine, reset=False, **kwargs)
    with seed_engine.begin() as conn:
        builder(conn, "DEMO-PIECE")

    # Must not raise. This is the C-2 repro.
    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        left = conn.execute(select(func.count()).select_from(table).where(table.c[column] == "DEMO-PIECE")).scalar_one()

    assert left == 0, f"{table_name} rows for a reset client survived the sweep"


def test_cli_subprocess_reset_sweeps_grandchildren_on_the_production_engine(tmp_path):
    """--reset on the engine configuration that actually ships.

    Every other reset test runs on `seed_engine`, which switches SQLite's
    `PRAGMA foreign_keys=ON`. main() builds a bare `create_engine(url)`, which
    leaves them OFF, and the one subprocess test omitted --reset -- so the
    production path ran a reset in no test at all. The fixture is the stricter
    of the two for detecting a RESTRICT, but it cannot see this failure mode:
    with foreign keys OFF, an unswept ALERT_HISTORY row is not rejected when
    its ALERT parent is deleted, it is silently ORPHANED. That is precisely
    why DEPENDENT_SWEEPS clears the three grandchildren explicitly instead of
    relying on the two that declare ondelete=CASCADE.

    Seeds, plants BOTH grandchild shapes a live demo grows -- the
    ALERT/ALERT_HISTORY pair the alerting feature writes (ondelete=None, which
    RESTRICTs under the fixture) and an ATTENDANCE_HOUR_ALLOCATION row the
    labour-hours API writes (ondelete=CASCADE, which the fixture cleans up for
    free) -- then re-runs the real CLI with --reset in a fresh process.

    The CASCADE one is the case only this test can see. Skip
    ATTENDANCE_HOUR_ALLOCATION in _reset's dependent loop and every FK-ON test
    stays green, because SQLite cascades the delete itself; on main()'s engine
    the cascade never fires and the row is silently orphaned under a client id
    that has just been handed back.
    """
    repo_root = Path(__file__).resolve().parents[3]
    url = f"sqlite:///{tmp_path / 'reset.db'}"

    from backend.db.migrate import upgrade_to_head

    upgrade_to_head(url)

    env = dict(os.environ)
    env["DATABASE_URL"] = url
    argv = [
        sys.executable,
        "-m",
        "backend.seed.cli",
        "--client",
        "DEMO-PIECE",
        "--profile",
        "smoke",
        "--as-of",
        "2026-08-18",
    ]

    first = subprocess.run(argv, cwd=str(repo_root), env=env, capture_output=True, text=True, timeout=180)
    assert first.returncode == 0, f"stdout={first.stdout}\nstderr={first.stderr}"

    engine = create_engine(url)
    attendance = Base.metadata.tables["ATTENDANCE_ENTRY"]
    allocation = Base.metadata.tables["ATTENDANCE_HOUR_ALLOCATION"]
    try:
        with engine.begin() as conn:
            _insert_alert_history(conn, "DEMO-PIECE")
            attendance_entry_id = conn.execute(
                select(attendance.c.attendance_entry_id).where(attendance.c.client_id == "DEMO-PIECE").limit(1)
            ).scalar_one()
            conn.execute(
                insert(allocation),
                [{"attendance_entry_id": attendance_entry_id, "category": "billed_production", "hours": 8}],
            )

        second = subprocess.run(
            argv + ["--reset"], cwd=str(repo_root), env=env, capture_output=True, text=True, timeout=180
        )
        assert second.returncode == 0, f"stdout={second.stdout}\nstderr={second.stderr}"

        with engine.connect() as conn:
            alerts = conn.execute(select(func.count()).select_from(Base.metadata.tables["ALERT"])).scalar_one()
            history = conn.execute(select(func.count()).select_from(Base.metadata.tables["ALERT_HISTORY"])).scalar_one()
            allocations = conn.execute(select(func.count()).select_from(allocation)).scalar_one()
            clients = conn.execute(select(func.count()).select_from(Base.metadata.tables["CLIENT"])).scalar_one()
    finally:
        engine.dispose()

    assert alerts == 0
    assert history == 0, "ALERT_HISTORY survived --reset on the engine main() actually builds"
    assert allocations == 0, "ATTENDANCE_HOUR_ALLOCATION survived --reset with no cascade to clean it up"
    assert clients == 1


def test_reset_sweeps_the_history_of_an_alert_only_pass_two_deletes(seed_engine):
    """Pass 1 must select every parent row the reset DELETES, not merely the
    in-scope ones -- the two passes used to disagree about which those are.

    Pass 1 (DEPENDENT_SWEEPS) clears ALERT_HISTORY by subquery over ALERT rows
    whose own client_id is in scope. Pass 2 (NULLABLE_TENANT_SWEEPS) then
    deletes ADDITIONAL ALERT rows -- those with client_id NULL pointing at an
    in-scope WORK_ORDER. ALERT is the single table naming both passes (pinned
    by test_the_widened_reset_parents_are_exactly_the_known_one), so pass 1
    never visited those extra rows' children.

    This is the FK-ENFORCED half, which is production's semantics:
    ALERT_HISTORY.alert_id is NOT NULL with no ondelete, so InnoDB (and SQLite
    under the fixture's PRAGMA foreign_keys=ON) REFUSES the delete rather than
    orphaning. Against the unfixed pass 1 this raised, and engine.begin()
    rolled the entire reset+reseed back:

        sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError)
        FOREIGN KEY constraint failed
        [SQL: DELETE FROM "ALERT" WHERE ...]

    On the DEMO_MODE boot path that exception is swallowed by run_best_effort
    (bootstrap/lifecycle.py:319), so the demo simply stops re-seeding behind a
    warning. Hence `seed(reset=True)` unguarded here: raising IS the failure.
    """
    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=False, **kwargs)

    alert = Base.metadata.tables["ALERT"]
    history = Base.metadata.tables["ALERT_HISTORY"]
    with seed_engine.begin() as conn:
        _insert_null_tenant_alert_history(conn, "DEMO-PIECE")

    # Must not raise. This is the FK-enforced repro.
    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        alerts = conn.execute(select(func.count()).select_from(alert)).scalar_one()
        histories = conn.execute(select(func.count()).select_from(history)).scalar_one()

    assert alerts == 0
    assert histories == 0


def test_reset_orphans_no_alert_history_on_the_engine_main_actually_builds(tmp_path):
    """The same pass-1/pass-2 disagreement with foreign keys OFF, where it is
    SILENT instead of loud.

    main() builds a bare create_engine(url), which leaves SQLite's foreign
    keys off, and that is the configuration the VM and the DEMO_MODE boot path
    run. There the unswept ALERT_HISTORY row is not rejected when its ALERT
    parent disappears -- it is ORPHANED, under a client id that has just been
    handed back to the next re-seed. Measured against the unfixed pass 1 on
    exactly this setup: `ALERT=0 ALERT_HISTORY=1 ORPHANED=1`.

    A bare engine rather than the `seed_engine` fixture is the whole point:
    the fixture's PRAGMA turns this into the IntegrityError the test above
    asserts, and no count is ever reached. Direct rather than by subprocess
    because the assertion here is about the ENGINE's foreign-key setting, not
    about argument parsing, which the subprocess test above already covers.
    """
    from backend.db.migrate import upgrade_to_head

    url = f"sqlite:///{tmp_path / 'orphan.db'}"
    upgrade_to_head(url)
    engine = create_engine(url)

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    alert = Base.metadata.tables["ALERT"]
    history = Base.metadata.tables["ALERT_HISTORY"]
    try:
        seed(engine, reset=False, **kwargs)
        with engine.begin() as conn:
            _insert_null_tenant_alert_history(conn, "DEMO-PIECE")

        seed(engine, reset=True, **kwargs)

        with engine.connect() as conn:
            alerts = conn.execute(select(func.count()).select_from(alert)).scalar_one()
            orphans = conn.execute(
                select(func.count()).select_from(history).where(history.c.alert_id.notin_(select(alert.c.alert_id)))
            ).scalar_one()
    finally:
        engine.dispose()

    assert alerts == 0
    assert orphans == 0


def test_reset_clears_a_null_tenant_child_that_would_block_its_parent(seed_engine):
    """A FLOATING_POOL row with client_id NULL is invisible to the scoped DELETE
    and RESTRICTs EMPLOYEE. Reachable in ordinary use: the floating-pool assign
    endpoint omits client_id entirely."""
    from sqlalchemy import insert, select, func
    from backend.database import Base
    from backend.seed.cli import seed

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=False, **kwargs)

    employee = Base.metadata.tables["EMPLOYEE"]
    pool = Base.metadata.tables["FLOATING_POOL"]
    with seed_engine.begin() as conn:
        emp_id = conn.execute(
            select(employee.c.employee_id).where(employee.c.client_id_assigned == "DEMO-PIECE").limit(1)
        ).scalar_one()
        conn.execute(insert(pool).values(employee_id=emp_id, client_id=None))

    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        orphans = conn.execute(select(func.count()).select_from(pool).where(pool.c.employee_id == emp_id)).scalar_one()
    assert orphans == 0


def test_reset_leaves_a_null_tenant_childs_foreign_owner_alone(seed_engine):
    """The parent-subquery sweep must not reach a row explicitly owned by
    another tenant, even when it points at a demo parent.

    DEVIATION FROM THE BRIEF, recorded here rather than silently: the brief's
    version of this test called `seed(reset=True)` unguarded and asserted
    `survivors == 1` with no exception. Run for real, that raises --
    FLOATING_POOL.employee_id is NOT NULL with ondelete=None (RESTRICT), so
    once the sweep correctly leaves REAL-CUSTOMER's row alone, that row still
    references the DEMO-PIECE employee this reset must delete, and the DB
    refuses the delete. No `_reset` strategy can satisfy both "never touch a
    foreign tenant's row" and "the demo parent's delete always succeeds" for
    this edge: the FK cannot be nulled (NOT NULL) and the row cannot be
    deleted (that IS the corruption this predicate exists to prevent). A loud
    IntegrityError is therefore the correct outcome, consistent with this
    module's existing stance elsewhere (see SELF_REFERENTIAL_SWEEPS's
    docstring: "the right failure for a shape that needs a different
    strategy entirely"). The assertion still discriminates the real bug: drop
    the `or_` guard and the REAL-CUSTOMER row is deleted too, nothing blocks
    the EMPLOYEE delete, and `seed()` returns normally -- so `pytest.raises`
    fails exactly when the guard is missing.
    """
    from sqlalchemy import insert, select, func
    from sqlalchemy.exc import IntegrityError
    from backend.database import Base
    from backend.seed.cli import seed

    client = Base.metadata.tables["CLIENT"]
    with seed_engine.begin() as conn:
        conn.execute(
            insert(client).values(
                client_id="REAL-CUSTOMER", client_name="Real", client_type="Hourly Rate", is_active=True
            )
        )

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=False, **kwargs)

    employee = Base.metadata.tables["EMPLOYEE"]
    pool = Base.metadata.tables["FLOATING_POOL"]
    with seed_engine.begin() as conn:
        emp_id = conn.execute(
            select(employee.c.employee_id).where(employee.c.client_id_assigned == "DEMO-PIECE").limit(1)
        ).scalar_one()
        conn.execute(insert(pool).values(employee_id=emp_id, client_id="REAL-CUSTOMER"))

    with pytest.raises(IntegrityError):
        seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        survivors = conn.execute(
            select(func.count()).select_from(pool).where(pool.c.client_id == "REAL-CUSTOMER")
        ).scalar_one()
    assert survivors == 1


def test_reset_does_not_delete_an_employee_shared_with_a_foreign_tenant(seed_engine):
    """CASCADE makes the ORIGINAL bug silent rather than loud: deleting a demo
    employee removes a real tenant's assignment with no error and no row count.

    DEVIATION FROM THE BRIEF, recorded here rather than silently -- the same
    kind Task 1 recorded for the FLOATING_POOL/EMPLOYEE edge, but with a
    DIFFERENT root cause. The brief's version of this test called
    `seed(reset=True)` unguarded and asserted `kept == 1` with no exception.
    Run for real, that raises -- not because the guard fails to spare the
    employee (it does; verified directly against `_reset()` in isolation) but
    because sparing it and then re-running `generate()`/`materialize()` for
    the SAME client/profile/seed tries to INSERT a fresh EMPLOYEE row with the
    identical, deterministic `employee_code` the surviving row already holds:
    unlike USER, EMPLOYEE has no re-seed idempotency (`seed()` never checks
    for an existing employee_code before materializing), so the second insert
    collides on EMPLOYEE's GLOBAL unique index. `engine.begin()` wraps the
    whole `_reset()` + `materialize()` call in one transaction, so the
    IntegrityError rolls back everything -- the REAL-CUSTOMER assignment
    that would have survived via the guard also survives via the rollback,
    and the pre-existing employees are untouched. A loud failure that leaves
    the database exactly as it was is the correct outcome for the same reason
    Ruling 3 accepts it for FLOATING_POOL: refusing to proceed beats silently
    destroying a real tenant's row. The assertion still discriminates the
    guard: with `shared_employee_ids` filtering disabled, the demo employee
    (and its cascading REAL-CUSTOMER assignment) is deleted outright, nothing
    survives to collide with, the reseed completes normally, and `kept`
    becomes 0 -- so this fails the way the brief predicted for the WRONG
    code, just reached through `pytest.raises` instead of a bare assertion.
    """
    from sqlalchemy import insert, select, func
    from sqlalchemy.exc import IntegrityError
    from backend.database import Base
    from backend.seed.cli import seed

    client = Base.metadata.tables["CLIENT"]
    with seed_engine.begin() as conn:
        conn.execute(
            insert(client).values(
                client_id="REAL-CUSTOMER", client_name="Real", client_type="Hourly Rate", is_active=True
            )
        )

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=False, **kwargs)

    employee = Base.metadata.tables["EMPLOYEE"]
    eca = Base.metadata.tables["EMPLOYEE_CLIENT_ASSIGNMENT"]
    with seed_engine.begin() as conn:
        emp_id = conn.execute(
            select(employee.c.employee_id).where(employee.c.client_id_assigned == "DEMO-PIECE").limit(1)
        ).scalar_one()
        conn.execute(insert(eca).values(employee_id=emp_id, client_id="REAL-CUSTOMER"))

    with pytest.raises(IntegrityError):
        seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        kept = conn.execute(
            select(func.count()).select_from(eca).where(eca.c.client_id == "REAL-CUSTOMER")
        ).scalar_one()
    assert kept == 1


def test_reset_does_not_delete_a_line_assignment_shared_with_a_foreign_tenant(seed_engine):
    """The EMPLOYEE_LINE_ASSIGNMENT variant of the cascade hazard above --
    same shape, different cascade child, identical root cause and identical
    deviation from the brief (see the EMPLOYEE_CLIENT_ASSIGNMENT test's
    docstring): sparing the employee collides its employee_code on reseed,
    `engine.begin()` rolls the whole operation back, and the REAL-CUSTOMER
    row survives via the rollback rather than via a clean scoped sweep."""
    from sqlalchemy import insert, select, func
    from sqlalchemy.exc import IntegrityError
    from backend.database import Base
    from backend.seed.cli import seed

    client = Base.metadata.tables["CLIENT"]
    with seed_engine.begin() as conn:
        conn.execute(
            insert(client).values(
                client_id="REAL-CUSTOMER", client_name="Real", client_type="Hourly Rate", is_active=True
            )
        )

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=False, **kwargs)

    employee = Base.metadata.tables["EMPLOYEE"]
    production_line = Base.metadata.tables["PRODUCTION_LINE"]
    ela = Base.metadata.tables["EMPLOYEE_LINE_ASSIGNMENT"]
    with seed_engine.begin() as conn:
        emp_id = conn.execute(
            select(employee.c.employee_id).where(employee.c.client_id_assigned == "DEMO-PIECE").limit(1)
        ).scalar_one()
        line_id = conn.execute(
            select(production_line.c.line_id).where(production_line.c.client_id == "DEMO-PIECE").limit(1)
        ).scalar_one()
        conn.execute(
            insert(ela).values(
                employee_id=emp_id, line_id=line_id, client_id="REAL-CUSTOMER", effective_date=date(2026, 8, 18)
            )
        )

    with pytest.raises(IntegrityError):
        seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        kept = conn.execute(
            select(func.count()).select_from(ela).where(ela.c.client_id == "REAL-CUSTOMER")
        ).scalar_one()
    assert kept == 1
