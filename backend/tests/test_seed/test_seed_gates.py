"""Structural gates for the S1b seed engine: no clock in the write layer, no
seed module reachable from the application's import graph, and no seed-suite
fixture that silently degrades off the database it was pointed at.

These are guards, not feature tests -- each one carries its own non-vacuity
control (a case proving the guard CAN fail) alongside the real assertion,
because a guard that only ever passes proves nothing about the files it is
supposed to be watching.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from backend.tests.test_seed.conftest import seed_engine, seed_engine_module
from backend.tests.test_seed.test_purity import EXEMPTED_MODULE_PATHS

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"

#: cli.py is the ONE module allowed a clock: --as-of defaults to date.today()
#: so a production run anchors to its actual run date (spec section 9).
CLOCK_EXEMPT = frozenset({"cli.py"})

#: The write layer, DERIVED from test_purity's exemption list rather than
#: restated. The two were hand-maintained and had already drifted: test_purity
#: exempts five modules from the no-clock check, this file listed three, and
#: identity.py sat in NEITHER -- exempted from the purity guard for talking to
#: a live Connection, and never added here, so a func.now() in it was caught by
#: nothing at all. Deriving one from the other closes that seam permanently: a
#: module can only leave the purity guard by entering this one.
WRITE_LAYER = tuple(sorted(EXEMPTED_MODULE_PATHS - CLOCK_EXEMPT))

BANNED_CALLS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("date", "today"),
    ("func", "now"),
    ("func", "current_timestamp"),
}


def _banned_clock_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and (owner.id, node.func.attr) in BANNED_CALLS:
            found.append(f"{path.name}:{node.lineno} {owner.id}.{node.func.attr}()")
    return found


@pytest.mark.parametrize("filename", WRITE_LAYER)
def test_the_write_layer_contains_no_clock(filename):
    """Every timestamp originates in its event. This is the defect that
    collapsed all 40 existing transition chains into a single instant."""
    assert _banned_clock_calls(SEED_DIR / filename) == []


def test_the_write_layer_derivation_covers_identity_and_excludes_only_cli():
    """A parametrize over an empty tuple collects ZERO tests and reports
    green, so the derivation's membership is pinned rather than trusted.

    identity.py is named explicitly: it is the module the two hand-maintained
    lists disagreed about, and a planted `func.now()` in it passed both this
    file and test_purity.py clean before WRITE_LAYER was derived.

    BOTH SIDES OF THE SPLIT ARE PINNED, not only their union. The union
    assertion alone holds for ANY partition of EXEMPTED_MODULE_PATHS: adding
    one name to CLOCK_EXEMPT walks that module out of the purity guard (it is
    exempt there) AND out of the clock guard (it is subtracted here), with
    every assertion in this file still green. Reproduced -- CLOCK_EXEMPT =
    {"cli.py", "writers_operations.py"} plus a planted func.now() in
    writers_operations.py collected 11 tests instead of 12 and all 11 passed,
    the only trace being a collection count nothing asserts on. Pinning
    CLOCK_EXEMPT to its exact value makes widening it a deliberate,
    reviewable edit; pinning WRITE_LAYER to its exact tuple makes the
    parametrize collapsing to fewer cases a failure rather than a
    disappearance."""
    assert "identity.py" in WRITE_LAYER
    assert "cli.py" not in WRITE_LAYER
    assert set(WRITE_LAYER) | set(CLOCK_EXEMPT) == set(EXEMPTED_MODULE_PATHS)
    assert CLOCK_EXEMPT == frozenset({"cli.py"})
    assert WRITE_LAYER == ("identity.py", "materialize.py", "writers_master.py", "writers_operations.py")


def test_the_cli_holds_exactly_one_clock_call_and_it_is_the_as_of_default():
    """cli.py's exemption is ONE CALL wide, not one file wide.

    The spec sanctions exactly one thing: `date.today()` as --as-of's argparse
    default, so a production run anchors to its actual run date (section 9).
    The blanket file exemption sanctioned all 254 lines, which just moved the
    gap M-3 closed one file over: `as_of = datetime.utcnow().date()` planted
    immediately before the generate() call inside seed() -- which discards the
    caller's --as-of and re-anchors the run to wall-clock time, so
    `--as-of 2026-01-01` produces two different databases on two different
    days and the seeder's whole reproducibility premise is gone -- left all
    151 tests green. cli.py was the one module of thirteen covered by neither
    the purity guard nor the clock guard.

    COUNTING is what defeats that plant, so the count is what is pinned. The
    line number deliberately is not: an unrelated edit above the parser would
    make this fail for the wrong reason, and the next person would "fix" it by
    loosening the guard. Call SHAPES with the count pinned instead -- a second
    clock call of any shape, anywhere in the file, appends a second element."""
    calls = [call.split(" ", 1)[1] for call in _banned_clock_calls(SEED_DIR / "cli.py")]

    assert calls == ["date.today()"]


def test_the_clock_guard_is_not_vacuous(tmp_path):
    """A guard that cannot fail proves nothing. Feed it a file that violates
    the rule and require a hit."""
    bad = tmp_path / "bad.py"
    bad.write_text("from datetime import datetime\nx = datetime.utcnow()\n")

    assert _banned_clock_calls(bad) != []


def test_importing_the_app_pulls_in_no_seed_module():
    """S1b changes no runtime behaviour: backend.seed must stay unreachable
    from the application's import graph, exactly as S1a verified. Run in a
    fresh interpreter (subprocess, not in-process import) so an already-warm
    sys.modules from an earlier test in this suite cannot mask the result."""
    code = "import backend.main;" "import sys;" "print([m for m in sys.modules if m.startswith('backend.seed')])"
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(SEED_DIR.parents[1]),
        check=True,
    )

    assert out.stdout.strip().endswith("[]")


@pytest.mark.parametrize("bad_url", ["", "sqlite:///seed-guard-should-never-build-this.db"])
def test_the_seed_fixtures_refuse_a_seed_test_database_url_that_is_not_mariadb(
    monkeypatch, tmp_path, tmp_path_factory, bad_url
):
    """SEED_TEST_DATABASE_URL must never degrade to SQLite in silence.

    Both fixtures used to read it with a bare `if url:`, so an empty or
    unresolved value took the SQLite branch with no skip and no error. With
    the MariaDB container stopped and the CI step run verbatim as
    `SEED_TEST_DATABASE_URL= pytest tests/test_seed/`, that gave 151 passed /
    exit 0 / zero skipped and no database anywhere -- the step's entire stated
    purpose (this repo's recurring MariaDB-only bug class) unenforced. An
    empty `${{ env.DATABASE_URL }}` is one renamed job-level `env:` key away.

    Driven through the REAL fixture bodies (`__wrapped__` is the undecorated
    function pytest keeps), not through the helper they call, so a future edit
    that re-inlines the environment read into a fixture is caught too. Both
    the empty string and a well-formed SQLite URL must raise: "set to
    something unusable" and "set to the wrong dialect" are the same bug."""
    monkeypatch.setenv("SEED_TEST_DATABASE_URL", bad_url)

    for fixture, argument in (
        (seed_engine, tmp_path),
        (seed_engine_module, tmp_path_factory),
    ):
        generator = fixture.__wrapped__(argument)
        with pytest.raises(RuntimeError) as exc:
            next(generator)

        assert "SEED_TEST_DATABASE_URL" in str(exc.value)


def test_the_seed_fixture_falls_back_to_sqlite_only_when_the_variable_is_unset(monkeypatch, tmp_path):
    """The non-vacuity control for the refusal above: a guard that raised
    unconditionally would also pass that test while breaking every developer
    laptop. UNSET is the one input allowed to reach the SQLite branch."""
    monkeypatch.delenv("SEED_TEST_DATABASE_URL", raising=False)

    generator = seed_engine.__wrapped__(tmp_path)
    engine = next(generator)
    try:
        backend_name = engine.url.get_backend_name()
    finally:
        generator.close()

    assert backend_name == "sqlite"
