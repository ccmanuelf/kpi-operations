import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, insert, select

from backend.database import Base
from backend.seed.cli import ALLOWLIST, CLIENT_SCOPED_TABLES, DEPENDENT_SWEEPS, SeedError, main, seed


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
    """
    client = Base.metadata.tables["CLIENT"]
    alert_config = Base.metadata.tables["ALERT_CONFIG"]
    with seed_engine.begin() as conn:
        conn.execute(
            insert(client),
            [{"client_id": "REAL-CUSTOMER", "client_name": "Real", "client_type": "Hourly Rate", "is_active": True}],
        )
        _insert_alert_config(conn, "REAL-CUSTOMER")

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

    assert len(survivors) == 1
    assert real_configs == 1, "the widened sweep reached a tenant that was never asked for"
    assert demo == 1, "a second --reset seed must not duplicate the client row"


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
    """
    scoped = set(CLIENT_SCOPED_TABLES)
    swept = scoped | {child for child, _, _, _ in DEPENDENT_SWEEPS}

    assert _foreign_keys_into(scoped, swept) == []


def test_the_reset_sweep_completeness_guard_is_not_vacuous():
    """A guard that cannot fail proves nothing. Withdraw ALERT_HISTORY from
    the swept set and the scan must name exactly the FK that C-2's fourth
    repro case exercises."""
    scoped = set(CLIENT_SCOPED_TABLES)
    swept = scoped | {child for child, _, _, _ in DEPENDENT_SWEEPS}

    assert _foreign_keys_into(scoped, swept - {"ALERT_HISTORY"}) == ["ALERT_HISTORY.alert_id -> ALERT"]


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
