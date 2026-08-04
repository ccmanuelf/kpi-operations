"""
Regression coverage for the demo seeder's downtime taxonomy (CI seed crash).

CI's "Seed demo database" step (.github/workflows/ci.yml) — and the
e2e-sqlite job's auto-seed — run this script directly against a file-based
DATABASE_URL: ``PYTHONPATH=. python backend/scripts/init_demo_database.py``.
PR #157 added ORM validators on DowntimeEntry (downtime_reason must be in
DowntimeReasonEnum; root_cause_category in DowntimeCategoryEnum or NULL —
see backend/orm/downtime_entry.py). The seeder's downtime block (Step 7,
"Downtime entries") wrote a bare ``"OPERATOR_ABSENT"`` literal — not a valid
enum value — which crashed both jobs on every run.

This test runs the real seeder end-to-end (subprocess, throwaway sqlite
file — the exact invocation CI uses) and asserts every DOWNTIME_ENTRY row it
writes is enum-valid, so a future hardcoded/typo'd literal in the seed data
fails loudly here instead of in CI. See also
backend/tests/test_scripts/test_seed_sample_client.py::
test_seeded_downtime_entries_are_valid_taxonomy_pairs_with_an_override for
the equivalent guard on the other demo seeder (_seed_operations.py).
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from backend.orm.downtime_taxonomy import DowntimeCategoryEnum, DowntimeReasonEnum

# Root of the repo (…/kpi-operations), matching how CI invokes the script
# from the repo root with PYTHONPATH=.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SEEDER_SCRIPT = REPO_ROOT / "backend" / "scripts" / "init_demo_database.py"


def test_demo_seeder_produces_enum_valid_downtime_entries(tmp_path):
    """Run the real demo seeder against a throwaway sqlite file (the same
    invocation CI uses) and assert every DOWNTIME_ENTRY row it writes has a
    canonical, non-NULL (downtime_reason, root_cause_category) pair."""
    db_path = tmp_path / "demo_seed_regression.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["PYTHONPATH"] = "."

    result = subprocess.run(
        [sys.executable, str(SEEDER_SCRIPT)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"demo seeder crashed (exit {result.returncode})\n"
        f"--- stdout tail ---\n{result.stdout[-2000:]}\n"
        f"--- stderr tail ---\n{result.stderr[-2000:]}"
    )

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT downtime_reason, root_cause_category FROM DOWNTIME_ENTRY").fetchall()
    finally:
        conn.close()

    assert rows, "expected the demo seeder to have written DOWNTIME_ENTRY rows"

    valid_reasons = {r.value for r in DowntimeReasonEnum}
    valid_categories = {c.value for c in DowntimeCategoryEnum}
    for reason, category in rows:
        assert reason in valid_reasons, f"invalid downtime_reason {reason!r} in demo seed data"
        assert category is not None, f"demo seed downtime row (reason={reason!r}) is missing root_cause_category"
        assert category in valid_categories, f"invalid root_cause_category {category!r} in demo seed data"
