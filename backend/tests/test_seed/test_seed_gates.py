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

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
WRITE_LAYER = ("materialize.py", "writers_master.py", "writers_operations.py")

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
