"""Structural gates for the S1b seed engine: no clock in the write layer, no
seed module reachable from the application's import graph.

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
    file and test_purity.py clean before WRITE_LAYER was derived."""
    assert "identity.py" in WRITE_LAYER
    assert "cli.py" not in WRITE_LAYER
    assert set(WRITE_LAYER) | set(CLOCK_EXEMPT) == set(EXEMPTED_MODULE_PATHS)


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
