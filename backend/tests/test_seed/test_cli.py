"""CLI surface and contract: argument parsing, the allowlist guard,
determinism, and the process-level (subprocess) smoke test.

Split out of this same module's original body; test_cli_reset.py covers
--reset behavior and test_cli_derived_sets.py covers the structural guards
over derived table sets.
"""

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

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
