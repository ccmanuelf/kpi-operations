import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, create_engine, func, insert, select

from backend.database import Base
from backend.seed.cli import (
    ALLOWLIST,
    CLIENT_SCOPED_TABLES,
    DEPENDENT_SWEEPS,
    AmbiguousClientScope,
    SeedError,
    _derive_client_scoped_tables,
    main,
    seed,
)


def test_allowlist_is_exactly_the_four_scenario_clients():
    # Verbatim from the brief; left as-is (Minor, reviewer's call to make) --
    # it recomputes the same formula that defines ALLOWLIST, so it cannot
    # catch a wrong formula, only a drift between this literal and cli.py's.
    # That drift is exactly what test_main's argparse/SeedError-path tests
    # exercise from the other direction (an unlisted client is refused).
    from backend.seed.scenarios import SCENARIOS

    assert ALLOWLIST == frozenset(s.client_id for s in SCENARIOS)


def test_a_client_outside_the_allowlist_is_refused(seed_engine):
    """The prod-safety guard: this seeder must be unable to touch a real
    tenant's rows even when handed its id."""
    with pytest.raises(SeedError) as exc:
        seed(
            seed_engine,
            client_ids=("REAL-CUSTOMER",),
            profile_name="smoke",
            seed_value=1234,
            as_of=date(2026, 8, 18),
            reset=False,
        )

    assert "REAL-CUSTOMER" in str(exc.value)


def test_reset_deletes_only_allowlisted_client_rows(seed_engine):
    """--reset must leave every other tenant untouched.

    REAL-CUSTOMER is given a CHILD row here, in a client-scoped table the
    seeder never writes. Without it this test proved almost nothing about the
    scoped sweep: a bare CLIENT row is deleted last and blocks nothing, which
    is precisely why C-2 -- a --reset that crashed the moment any demo tenant
    owned a row outside `SEEDED` -- reached review with a green suite.

    It is also given a PRODUCTION_LINE hierarchy, because --reset does not
    only DELETE any more: SELF_REFERENTIAL_SWEEPS issues an UPDATE that NULLs
    parent_line_id. An UPDATE with no tenant filter is silent -- it raises
    nothing, changes no row count, and leaves every assertion above green
    while quietly flattening a real customer's line hierarchy across the whole
    database. Dropping `.where(...)` from that one statement is an ordinary
    refactor slip with cross-tenant consequences on the production VM, so it
    gets an assertion rather than a comment.
    """
    client = Base.metadata.tables["CLIENT"]
    alert_config = Base.metadata.tables["ALERT_CONFIG"]
    production_line = Base.metadata.tables["PRODUCTION_LINE"]
    with seed_engine.begin() as conn:
        conn.execute(
            insert(client),
            [{"client_id": "REAL-CUSTOMER", "client_name": "Real", "client_type": "Hourly Rate", "is_active": True}],
        )
        _insert_alert_config(conn, "REAL-CUSTOMER")
        parent_id = conn.execute(
            insert(production_line).values(client_id="REAL-CUSTOMER", line_code="REAL-L1", line_name="Real Parent Line")
        ).inserted_primary_key[0]
        conn.execute(
            insert(production_line).values(
                client_id="REAL-CUSTOMER",
                line_code="REAL-L1-A",
                line_name="Real Child Line",
                parent_line_id=parent_id,
            )
        )

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=True, **kwargs)
    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        survivors = conn.execute(select(client.c.client_id).where(client.c.client_id == "REAL-CUSTOMER")).all()
        real_configs = conn.execute(
            select(func.count()).select_from(alert_config).where(alert_config.c.client_id == "REAL-CUSTOMER")
        ).scalar_one()
        demo = conn.execute(
            select(func.count()).select_from(client).where(client.c.client_id == "DEMO-PIECE")
        ).scalar_one()
        real_parents = (
            conn.execute(
                select(production_line.c.parent_line_id).where(
                    production_line.c.client_id == "REAL-CUSTOMER",
                    production_line.c.line_code == "REAL-L1-A",
                )
            )
            .scalars()
            .all()
        )

    assert len(survivors) == 1
    assert real_configs == 1, "the widened sweep reached a tenant that was never asked for"
    assert demo == 1, "a second --reset seed must not duplicate the client row"
    assert real_parents == [parent_id], "the self-referential UPDATE flattened a tenant that was never asked for"


def test_the_same_inputs_produce_the_same_row_counts(seed_engine, tmp_path):
    """Determinism is what lets the dataset be asserted against rather than
    eyeballed (spec section 9)."""
    from sqlalchemy import create_engine

    from backend.db.migrate import upgrade_to_head

    first = seed(
        seed_engine,
        client_ids=tuple(ALLOWLIST),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 18),
        reset=False,
    )

    url = f"sqlite:///{tmp_path / 'second.db'}"
    upgrade_to_head(url)
    other = create_engine(url)
    second = seed(
        other,
        client_ids=tuple(ALLOWLIST),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 18),
        reset=False,
    )
    other.dispose()

    assert first == second


def test_as_of_is_required_to_be_explicit_or_defaulted_visibly(capsys):
    """A test that pins --as-of does not drift with the calendar; the CLI's
    default does. Assert the default is TODAY rather than a hardcoded date, so
    the seeder still anchors to its run date in production (spec section 9)."""
    from backend.seed.cli import build_parser

    args = build_parser().parse_args([])

    assert args.as_of == date.today()


def test_main_refuses_an_unknown_profile():
    assert main(["--profile", "gigantic"]) == 2


# --- Additional coverage: traps the brief's own tests do not exercise ------


def test_reset_preserves_a_users_saved_filter_across_reseed(seed_engine):
    """The reviewer's repro. A live survey of every FK into USER.user_id found
    ~10 tables outside S1b's declared scope (SAVED_FILTER,
    ALERT.acknowledged_by/resolved_by, IMPORT_LOG, COVERAGE_ENTRY,
    CALCULATION_ASSUMPTION, METRIC_CALCULATION_RESULT, SIMULATION_SCENARIO,
    EVENT_STORE) with no ondelete cascade -- an unconditional USER delete on
    --reset RESTRICTs the moment a demo user has used one of those features.
    This seeds, inserts a SAVED_FILTER row for USR-DEMO-OP exactly as the live
    app does when a user saves a dashboard filter, then --reset + reseeds:
    must not raise, and the filter must survive (USER is never deleted, so
    its child row never becomes an orphan)."""
    saved_filter = Base.metadata.tables["SAVED_FILTER"]
    kwargs = dict(client_ids=tuple(ALLOWLIST), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))

    seed(seed_engine, reset=False, **kwargs)

    with seed_engine.begin() as conn:
        conn.execute(
            insert(saved_filter),
            [
                {
                    "user_id": "USR-DEMO-OP",
                    "filter_name": "My Dashboard",
                    "filter_type": "dashboard",
                    "filter_config": '{"client_id": "DEMO-PIECE"}',
                }
            ],
        )

    # Must not raise -- this is the reviewer's repro (previously a
    # sqlite3.IntegrityError: FOREIGN KEY constraint failed deleting USER).
    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        survivors = conn.execute(
            select(func.count()).select_from(saved_filter).where(saved_filter.c.user_id == "USR-DEMO-OP")
        ).scalar_one()

    assert survivors == 1


def test_reset_reseed_cycle_keeps_exactly_six_users_and_never_collides(seed_engine):
    """User creation is idempotent (seed() drops UserCreated events for ids
    that already exist), not delete-then-recreate. Run seed / --reset+seed /
    --reset+seed and assert exactly six users survive at every step, with no
    PK-collision IntegrityError anywhere in the cycle."""
    user = Base.metadata.tables["USER"]
    kwargs = dict(client_ids=tuple(ALLOWLIST), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))

    def count_users() -> int:
        with seed_engine.connect() as conn:
            return int(conn.execute(select(func.count()).select_from(user)).scalar_one())

    seed(seed_engine, reset=False, **kwargs)
    assert count_users() == 6

    seed(seed_engine, reset=True, **kwargs)
    assert count_users() == 6

    seed(seed_engine, reset=True, **kwargs)
    assert count_users() == 6


def test_reset_does_not_duplicate_kpi_thresholds_on_reseed(seed_engine):
    """KPI_THRESHOLD is client-scoped (real client_id under
    UniqueConstraint(client_id, kpi_key)) and is swept generically by _reset
    like any other client-scoped table -- no special-casing needed. A --reset
    bug here is silent (re-seed duplication), so assert the count directly:
    seed, reset+reseed twice, and confirm exactly one threshold set survives
    per client rather than eyeballing that the run didn't raise."""
    from backend.seed.scenarios import THRESHOLDS

    threshold = Base.metadata.tables["KPI_THRESHOLD"]
    kwargs = dict(
        client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18), reset=True
    )

    seed(seed_engine, **kwargs)
    seed(seed_engine, **kwargs)

    with seed_engine.connect() as conn:
        count = conn.execute(
            select(func.count()).select_from(threshold).where(threshold.c.client_id == "DEMO-PIECE")
        ).scalar_one()

    assert count == len(THRESHOLDS)


def test_cli_subprocess_actually_writes_rows(tmp_path):
    """The CLI is a fresh process. INSERT_ORDER is derived at import from
    Base.metadata.sorted_tables; if nothing imports backend.orm first, the
    metadata is empty, flush() iterates nothing, and the seeder writes ZERO
    rows, raises nothing, and reports success. materialize.py fixes this by
    importing backend.orm for its registration side effect, but the CLI is
    the exact caller that would hit that trap in a real process. An in-process
    call to seed()/main() cannot prove this fix holds -- this test process
    already imported backend.orm via conftest.py, long before cli.py's own
    import runs. Only a real subprocess, with its own fresh interpreter and
    import order, proves it."""
    repo_root = Path(__file__).resolve().parents[3]
    db_path = tmp_path / "e2e.db"
    url = f"sqlite:///{db_path}"

    from backend.db.migrate import upgrade_to_head

    upgrade_to_head(url)

    env = dict(os.environ)
    env["DATABASE_URL"] = url

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.seed.cli",
            "--client",
            "DEMO-PIECE",
            "--profile",
            "smoke",
            "--as-of",
            "2026-08-18",
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    engine = create_engine(url)
    client = Base.metadata.tables["CLIENT"]
    production = Base.metadata.tables["PRODUCTION_ENTRY"]
    user = Base.metadata.tables["USER"]
    try:
        with engine.connect() as conn:
            client_count = conn.execute(select(func.count()).select_from(client)).scalar_one()
            production_count = conn.execute(select(func.count()).select_from(production)).scalar_one()
            user_count = conn.execute(select(func.count()).select_from(user)).scalar_one()
    finally:
        engine.dispose()

    assert client_count == 1
    assert production_count == 36  # smoke profile, single client: deterministic, not just non-zero
    assert user_count == 6


# --- C-2: --reset must clear every client-scoped table, not just SEEDED ------


def _insert_alert_config(conn, client_id):
    """Exactly what the alert-configuration API writes the first time anyone
    edits a threshold on the demo."""
    conn.execute(
        insert(Base.metadata.tables["ALERT_CONFIG"]),
        [
            {
                "config_id": f"AC-{client_id}",
                "client_id": client_id,
                "alert_type": "OEE_LOW",
                "warning_threshold": 70.0,
                "critical_threshold": 60.0,
                "created_at": datetime(2026, 8, 1),
                "updated_at": datetime(2026, 8, 1),
            }
        ],
    )


def _insert_job(conn, client_id):
    """A JOB is a child of WORK_ORDER, so it blocks a different DELETE than
    ALERT_CONFIG does -- one inside the sweep rather than at CLIENT."""
    work_order = Base.metadata.tables["WORK_ORDER"]
    work_order_id = conn.execute(
        select(work_order.c.work_order_id).where(work_order.c.client_id == client_id).limit(1)
    ).scalar_one()
    conn.execute(
        insert(Base.metadata.tables["JOB"]),
        [
            {
                "job_id": f"JOB-{client_id}",
                "work_order_id": work_order_id,
                "client_id_fk": client_id,
                "operation_name": "OP10",
                "sequence_number": 10,
                "created_at": datetime(2026, 8, 1),
                "updated_at": datetime(2026, 8, 1),
            }
        ],
    )


def _insert_capacity_calendar(conn, client_id):
    """One of the 13 capacity_* tables the retiring seeder swept and the plan
    dropped."""
    conn.execute(
        insert(Base.metadata.tables["capacity_calendar"]),
        [
            {
                "client_id": client_id,
                "calendar_date": date(2026, 8, 3),
                "is_working_day": True,
                "shifts_available": 2,
                "created_at": datetime(2026, 8, 1),
                "updated_at": datetime(2026, 8, 1),
            }
        ],
    )


def _insert_alert_history(conn, client_id):
    """The one grandchild with NO ondelete: ALERT_HISTORY.alert_id -> ALERT
    RESTRICTs, so deleting the tenant's ALERT rows fails unless the subquery
    sweep in DEPENDENT_SWEEPS clears it first."""
    conn.execute(
        insert(Base.metadata.tables["ALERT"]),
        [
            {
                "alert_id": f"ALRT-{client_id}",
                "category": "KPI",
                "severity": "HIGH",
                "status": "ACTIVE",
                "title": "OEE below target",
                "message": "m",
                "client_id": client_id,
                "created_at": datetime(2026, 8, 1),
            }
        ],
    )
    conn.execute(
        insert(Base.metadata.tables["ALERT_HISTORY"]),
        [
            {
                "history_id": f"AH-{client_id}",
                "alert_id": f"ALRT-{client_id}",
                "prediction_date": datetime(2026, 8, 1),
                "created_at": datetime(2026, 8, 1),
            }
        ],
    )


CHILD_ROW_BUILDERS = {
    "ALERT_CONFIG": (_insert_alert_config, "ALERT_CONFIG", "client_id"),
    "JOB": (_insert_job, "JOB", "client_id_fk"),
    "capacity_calendar": (_insert_capacity_calendar, "capacity_calendar", "client_id"),
    "ALERT_HISTORY": (_insert_alert_history, "ALERT", "client_id"),
}


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


def _foreign_keys_into(scoped: set, swept: set) -> list:
    """Every (table.column -> parent) FK held by a table OUTSIDE `swept` that
    points at a table INSIDE `scoped`. Each one is a row --reset would orphan
    or be RESTRICTed by."""
    offenders = []
    for table in Base.metadata.sorted_tables:
        if table.name in swept:
            continue
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name in scoped:
                    offenders.append(f"{table.name}.{column.name} -> {fk.column.table.name}")
    return sorted(offenders)


def test_no_table_outside_the_reset_sweep_holds_a_foreign_key_into_it():
    """The anti-rot guard, and the reason C-2 cannot come back.

    A table added later with a ForeignKey to CLIENT is picked up by
    _derive_client_scoped_tables automatically. A GRANDCHILD -- a table whose
    only link is an FK into a client-scoped table, the ALERT_HISTORY shape --
    is not derivable and must be declared in DEPENDENT_SWEEPS. This asserts
    the declaration is complete against live metadata, so the next one fails
    the build instead of failing --reset on a customer's VM.

    TARGETS ARE `swept`, NOT `scoped`, and the difference is the whole guard.
    The first version skipped tables in `swept` as SOURCES but only counted
    tables in `scoped` as TARGETS, and the three DEPENDENT_SWEEPS children are
    in `swept` and not in `scoped` -- so a future table holding an FK into
    ALERT_HISTORY / ASSUMPTION_CHANGE / ATTENDANCE_HOUR_ALLOCATION was
    invisible to it, while its docstring claimed "no table outside the sweep
    holds a ForeignKey into it". Since _reset deletes those three parents by
    subquery, such a table would RESTRICT --reset on a customer's VM: C-2 back
    through a side door. Injecting a synthetic table with an FK into
    ALERT_HISTORY passed the old form and is named by this one, and the
    stricter form costs nothing against the live schema today.
    """
    scoped = set(CLIENT_SCOPED_TABLES)
    swept = scoped | {child for child, _, _, _ in DEPENDENT_SWEEPS}

    assert _foreign_keys_into(swept, swept) == []


def test_the_reset_sweep_completeness_guard_is_not_vacuous():
    """A guard that cannot fail proves nothing. Withdraw ALERT_HISTORY from
    the swept set and the scan must name exactly the FK that C-2's fourth
    repro case exercises. Target set matches the guard above (`swept`), so the
    two cannot drift into asserting different things."""
    scoped = set(CLIENT_SCOPED_TABLES)
    swept = scoped | {child for child, _, _, _ in DEPENDENT_SWEEPS}

    assert _foreign_keys_into(swept, swept - {"ALERT_HISTORY"}) == ["ALERT_HISTORY.alert_id -> ALERT"]


#: The three column names this schema uses to scope a row to a tenant. Salvaged
#: from seed_sample_client.py (removed in S1c), which was the only place all
#: three were ever written down together.
CLIENT_SCOPE_COLUMN_NAMES = {"client_id", "client_id_fk", "client_id_assigned"}

#: Tenant-NAMED string columns that scope nothing -- CLIENT's own descriptive
#: fields. Pinned so the derivation below can assert on a closed set without
#: having to guess which side of the line a new `client_*` column falls on.
CLIENT_DESCRIPTIVE_COLUMN_NAMES = {"client_contact", "client_email", "client_name", "client_phone", "client_type"}


def _tenant_named_string_columns() -> set:
    """Every string column in the schema whose name mentions a tenant.

    The CANDIDATE set, derived from live metadata. CLIENT_SCOPE_COLUMN_NAMES
    above is a closed 3-name literal, so the bare-column guard below pins the
    TABLES those three spellings happen to find and never pins the SPELLINGS
    themselves -- while this schema is itself the proof that spelling drift is
    live, carrying three of them already (client_id, client_id_fk,
    client_id_assigned). A table scoping its rows by a fourth spelling would
    be invisible to BOTH client-column guards and would sit outside the
    --reset sweep entirely, which is the cross-reset tenant-data leak the
    bare-column guard exists to prevent.

    Restricted to string columns because a tenant scope in this schema is
    always a client-id string; an integer column called `client_count` is not
    a scope and should not have to be argued about.
    """
    return {
        column.name
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, String) and ("client" in column.name.lower() or "tenant" in column.name.lower())
    }


def test_no_table_has_an_ambiguous_client_scope():
    """A table with TWO ForeignKeys to CLIENT has no derivable tenant column.

    Raised by the DeepSeek cross-model review of this branch, and worth acting
    on even though the schema is clean today: the original loop assigned inside
    the column walk, so a second ForeignKey would silently win by column order.
    --reset would then filter that table by the wrong column -- deleting rows
    belonging to a client nobody asked for, or leaving the requested client's
    behind to collide on the next re-seed. Neither failure names its cause, and
    both are cross-tenant.

    Two assertions, because either alone is weak. The first pins the live
    schema, which is what makes the guard meaningful now. The second proves the
    derivation REFUSES an ambiguous schema rather than guessing -- without it
    this test would still pass if _derive_client_scoped_tables went back to
    picking whichever ForeignKey came last.
    """
    ambiguous = {}
    for table in Base.metadata.sorted_tables:
        scopes = sorted(c.name for c in table.columns for fk in c.foreign_keys if fk.column.table.name == "CLIENT")
        if len(scopes) > 1:
            ambiguous[table.name] = scopes

    assert ambiguous == {}

    metadata = MetaData()
    Table("CLIENT", metadata, Column("client_id", String(50), primary_key=True))
    Table(
        "TWO_SCOPES",
        metadata,
        Column("row_id", Integer, primary_key=True),
        Column("client_id", String(50), ForeignKey("CLIENT.client_id")),
        Column("owner_client_id", String(50), ForeignKey("CLIENT.client_id")),
    )

    with pytest.raises(AmbiguousClientScope) as exc:
        _derive_client_scoped_tables(metadata)

    assert "TWO_SCOPES" in str(exc.value)

    # The escape hatch the message names must actually work. It did not at
    # first: the raise happens inside the table loop while the override map is
    # applied after it, so naming the table changed nothing and the
    # instruction was a dead end -- caught by the cross-model review of the
    # very commit that added it. Asserting the remedy resolves the error is
    # what keeps that from coming back.
    from backend.seed import cli as cli_module

    original = cli_module._UNDERIVABLE_CLIENT_SCOPE_COLUMNS
    cli_module._UNDERIVABLE_CLIENT_SCOPE_COLUMNS = {**original, "TWO_SCOPES": "owner_client_id"}
    try:
        resolved = _derive_client_scoped_tables(metadata)
    finally:
        cli_module._UNDERIVABLE_CLIENT_SCOPE_COLUMNS = original

    assert resolved["TWO_SCOPES"] == "owner_client_id"


def test_every_bare_client_column_is_a_deliberate_include_or_exclude():
    """The OTHER half of the anti-rot guard: a tenant column with NO
    ForeignKey.

    _derive_client_scoped_tables finds a table by following ForeignKeys to
    CLIENT.client_id, so a table that scopes rows with a bare column is
    invisible to it -- and that is not hypothetical, it is the shape that
    already bit once: EMPLOYEE.client_id_assigned carries no FK, the pure
    derivation silently dropped it, and only the explicit
    _UNDERIVABLE_CLIENT_SCOPE_COLUMNS entry keeps EMPLOYEE in the sweep.

    Pinning the set exactly means a FIFTH such table fails the build and
    forces a deliberate include-or-exclude decision. Silently excluded, it
    would keep a reset tenant's rows alive under a client id that has just
    been handed back -- a cross-reset tenant-data leak, not a tidiness issue.

    CLIENT is filtered out: CLIENT.client_id is the primary key every one of
    those ForeignKeys points AT, not a bare scope column. The four that remain
    are each argued in cli.py -- EMPLOYEE included via
    _UNDERIVABLE_CLIENT_SCOPE_COLUMNS, USER excluded as user state rather than
    client fixture data (Ruling 17), AUDIT_ENTRY and EVENT_STORE excluded as
    append-only ledgers this seeder writes zero rows to.
    """
    # The SPELLINGS first, derived, then the TABLES they find. Without this
    # line the assertion below is conditional on a closed literal nobody
    # rechecks: a fifth spelling (`client_ref`, `tenant_id`, ...) introduced
    # by a new table simply would not appear in `bare`, and both this guard
    # and _derive_client_scoped_tables would report clean while that table
    # kept a reset tenant's rows alive. Deriving the candidates makes such a
    # column fail the build BY NAME instead.
    assert _tenant_named_string_columns() == CLIENT_SCOPE_COLUMN_NAMES | CLIENT_DESCRIPTIVE_COLUMN_NAMES

    bare = {
        table.name
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if column.name in CLIENT_SCOPE_COLUMN_NAMES and not column.foreign_keys
    } - {"CLIENT"}

    assert bare == {"EMPLOYEE", "USER", "AUDIT_ENTRY", "EVENT_STORE"}


def test_the_reset_sweep_covers_client_scoped_tables_the_seeder_never_writes():
    """Pins the two halves of the derivation that a reader would otherwise
    have to take on trust: the FK-derived set really does reach the blockers
    the review named, and the three bare-column tables are handled by
    deliberate decision rather than by accident."""
    from backend.seed.coverage import SEEDED

    for name in (
        "ALERT",
        "ALERT_CONFIG",
        "JOB",
        "EQUIPMENT",
        "BREAK_TIME",
        "FLOATING_POOL",
        "COVERAGE_ENTRY",
        "shift_coverage",
        "SIMULATION_SCENARIO",
        "CALCULATION_ASSUMPTION",
        "METRIC_CALCULATION_RESULT",
        "PART_OPPORTUNITIES",
        "capacity_calendar",
    ):
        assert name not in SEEDED, f"{name} is seeded after all -- rewrite this test, it proves nothing"
        assert name in CLIENT_SCOPED_TABLES, f"{name} would survive --reset and RESTRICT the CLIENT delete"

    assert len([n for n in CLIENT_SCOPED_TABLES if n.startswith("capacity_")]) == 13

    # EMPLOYEE.client_id_assigned is a bare column with no ForeignKey, so no
    # derivation can find it: only the explicit entry keeps it in the sweep.
    assert CLIENT_SCOPED_TABLES["EMPLOYEE"] == "client_id_assigned"

    # The three other bare client columns, each excluded on purpose. USER is
    # user state, not client fixture data (Ruling 17); AUDIT_ENTRY and
    # EVENT_STORE are append-only ledgers this seeder writes zero rows to.
    assert "USER" not in CLIENT_SCOPED_TABLES
    assert "AUDIT_ENTRY" not in CLIENT_SCOPED_TABLES
    assert "EVENT_STORE" not in CLIENT_SCOPED_TABLES


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


def test_the_nullable_tenant_sweep_set_is_exactly_the_known_two():
    """Pinned so a third such edge fails the build instead of silently
    stranding a tenant's rows or RESTRICTing a reset on a customer VM."""
    from backend.seed.cli import NULLABLE_TENANT_SWEEPS

    assert NULLABLE_TENANT_SWEEPS == (
        ("ALERT", "work_order_id", "client_id", "WORK_ORDER", "work_order_id"),
        ("FLOATING_POOL", "employee_id", "client_id", "EMPLOYEE", "employee_id"),
    )


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


def test_the_employee_cascade_children_are_exactly_the_known_two():
    """A third cascade child of EMPLOYEE must fail the build: it would be a new
    way for a reset to silently delete a real tenant's rows."""
    from backend.seed.cli import CASCADE_CHILDREN_OF_EMPLOYEE

    assert CASCADE_CHILDREN_OF_EMPLOYEE == ("EMPLOYEE_CLIENT_ASSIGNMENT", "EMPLOYEE_LINE_ASSIGNMENT")
