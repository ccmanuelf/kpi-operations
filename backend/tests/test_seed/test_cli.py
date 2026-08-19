import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, insert, select

from backend.database import Base
from backend.seed.cli import ALLOWLIST, SeedError, main, seed


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
    """--reset must leave every other tenant untouched."""
    client = Base.metadata.tables["CLIENT"]
    with seed_engine.begin() as conn:
        conn.execute(
            insert(client),
            [{"client_id": "REAL-CUSTOMER", "client_name": "Real", "client_type": "Hourly Rate", "is_active": True}],
        )

    seed(
        seed_engine,
        client_ids=("DEMO-PIECE",),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 18),
        reset=True,
    )
    seed(
        seed_engine,
        client_ids=("DEMO-PIECE",),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 18),
        reset=True,
    )

    with seed_engine.connect() as conn:
        survivors = conn.execute(select(client.c.client_id).where(client.c.client_id == "REAL-CUSTOMER")).all()
        demo = conn.execute(
            select(func.count()).select_from(client).where(client.c.client_id == "DEMO-PIECE")
        ).scalar_one()

    assert len(survivors) == 1
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
