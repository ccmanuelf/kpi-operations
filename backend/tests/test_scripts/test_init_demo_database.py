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


def test_demo_seeder_classifies_only_late_orders_deterministically(tmp_path):
    """Run the real demo seeder end-to-end (subprocess, throwaway sqlite file
    — same invocation CI uses) and assert its Task 9 (Cycle 2) delay
    classification is sound: only genuinely-late WOs (per the single
    is_late() definition — asserted here, not reimplemented in the seeder)
    ever carry a delay_classification, values are enum-valid, justified rows
    carry a valid reason and non-justified rows don't, and the fixed i % 3
    pattern over the late subset (one late WO per client, per WO_PLAN's
    "shipped_late" row) produces all three outcomes across the 5 demo
    clients: justified, unjustified, and unclassified (NULL).

    Reason coverage (round-1 review, Minor): asserts the EXACT set of
    justified reasons the demo seeder can produce, not "all 6 like the
    sample seeder's equivalent test" — the demo dataset only ever has 5 late
    WOs total (1/client × 5 clients), and the i % 3 pattern above (which must
    keep >=1 unjustified and >=1 unclassified row) caps justified rows at 2
    (late_ct 0 and 3). 6 distinct reasons is therefore mathematically
    unreachable here without restructuring WO_PLAN's 5 fixed,
    MASTER_PRODUCTS-indexed slots (out of scope for this fix; see the
    matching comment in init_demo_database.py). This exact-set assertion is
    still a full regression guard for the round-1 bug class: before the fix,
    reason indexing was `late_ct % 6`, which — because gcd(3, 6) == 3 —
    always produced {CUSTOMER_REQUEST, FORCE_MAJEURE} (indices 0 and 3)
    regardless of scale; the fix's separate justified_ct counter produces
    {CUSTOMER_REQUEST, CUSTOMER_CHANGE_ORDER} (indices 0 and 1) instead, so a
    regression back to the buggy indexing changes the observed set and this
    assertion fails.
    """
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.orm import WorkOrder
    from backend.orm.delay_taxonomy import DelayClassificationEnum, JustifiedDelayReasonEnum
    from backend.calculations.otd import is_late

    db_path = tmp_path / "demo_seed_delay_regression.db"
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

    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        wos = session.query(WorkOrder).all()
    finally:
        session.close()
        engine.dispose()

    assert wos, "expected the demo seeder to have written WorkOrder rows"

    valid_classifications = {c.value for c in DelayClassificationEnum}
    valid_reasons = {r.value for r in JustifiedDelayReasonEnum}
    # All classified WOs here are SHIPPED (delivered), so is_late()'s as_of
    # only matters for undelivered orders — irrelevant to this check, but
    # today() matches what the seeder itself used as "now".
    today = date.today()

    late_wos = [wo for wo in wos if is_late(wo, today)]
    justified_seen = False
    unjustified_seen = False
    unclassified_late_seen = False
    seeded_reasons: set = set()

    for wo in wos:
        if wo.delay_classification is not None:
            assert is_late(wo, today), f"{wo.work_order_id} classified but not late"
            assert wo.delay_classification in valid_classifications
            if wo.delay_classification == DelayClassificationEnum.JUSTIFIED.value:
                justified_seen = True
                assert wo.justified_delay_reason in valid_reasons
                seeded_reasons.add(wo.justified_delay_reason)
            else:
                unjustified_seen = True
                assert wo.justified_delay_reason is None

    for wo in late_wos:
        if wo.delay_classification is None:
            unclassified_late_seen = True

    assert justified_seen, "expected at least one justified late WO"
    assert unjustified_seen, "expected at least one unjustified late WO"
    assert unclassified_late_seen, "expected at least one unclassified (NULL) late WO"
    expected_reasons = {
        JustifiedDelayReasonEnum.CUSTOMER_REQUEST.value,
        JustifiedDelayReasonEnum.CUSTOMER_CHANGE_ORDER.value,
    }
    assert seeded_reasons == expected_reasons, (
        f"expected exactly {sorted(expected_reasons)} (the demo dataset's 2-justified-row ceiling — "
        f"see docstring), got {sorted(seeded_reasons)}"
    )


def test_demo_seeder_labor_hours_capture_is_deterministic(tmp_path):
    """Run the real demo seeder end-to-end (subprocess, throwaway sqlite
    file — same invocation CI uses) and assert its Task 8 (Cycle 3 PR-A)
    labor-hours capture is sound: employees are fully classified
    direct/indirect (majority direct), attendance OT splits sum to
    actual_hours for every split entry, a fixed minority of present entries
    are left UNSPLIT (completeness chip), sparse per-entry class overrides
    exist, hour allocations are enum-valid with per-entry sum <=
    actual_hours, a fixed minority of present entries are left unallocated
    (completeness chip), and the rotating-minority allocation category
    reaches the EXACT set of all 8 HourCategoryEnum values.

    Unlike the demo seeder's delay-classification coverage above (capped at
    2/6 reasons by WO_PLAN's fixed 5-late-WO structure), the attendance
    counters (`attendance_p` / `attendance_alloc_ct`) are declared BEFORE
    the per-client loop in init_demo_database.py and accumulate ACROSS all
    5 clients x 3 employees — a wide enough pool (~90-120 present entries,
    empirically confirmed) that the demo dataset reaches the full 8-category
    set too, not just a subset."""
    from decimal import Decimal

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.orm import AttendanceEntry, AttendanceHourAllocation, Employee
    from backend.orm.labor_taxonomy import HourCategoryEnum, LaborClassEnum

    db_path = tmp_path / "demo_seed_labor_hours_regression.db"
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

    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        employees = session.query(Employee).all()
        entries = session.query(AttendanceEntry).all()
        allocations_by_entry: dict = {}
        for alloc in session.query(AttendanceHourAllocation).all():
            allocations_by_entry.setdefault(alloc.attendance_entry_id, []).append(alloc)
    finally:
        session.close()
        engine.dispose()

    assert employees, "expected the demo seeder to have written Employee rows"
    assert entries, "expected the demo seeder to have written ATTENDANCE_ENTRY rows"

    valid_classes = {c.value for c in LaborClassEnum}
    valid_categories = {c.value for c in HourCategoryEnum}

    classes_seen = set()
    for emp in employees:
        assert emp.labor_class is not None, f"unclassified employee {emp.employee_code}"
        assert emp.labor_class in valid_classes
        classes_seen.add(emp.labor_class)
    assert classes_seen == valid_classes, f"expected both labor classes present, got {classes_seen}"
    assert sum(1 for e in employees if e.labor_class == LaborClassEnum.DIRECT.value) > sum(
        1 for e in employees if e.labor_class == LaborClassEnum.INDIRECT.value
    ), "expected direct labor to be the majority classification"

    override_seen = False
    unsplit_seen = False
    unallocated_seen = False
    seeded_categories: set = set()

    for entry in entries:
        if entry.labor_class_override is not None:
            assert entry.labor_class_override in valid_classes
            override_seen = True

        split_fields = (entry.normal_hours, entry.double_hours, entry.triple_hours)
        if entry.actual_hours and entry.actual_hours > 0 and all(f is None for f in split_fields):
            unsplit_seen = True
        elif any(f is not None for f in split_fields):
            assert all(f is not None for f in split_fields), f"partial OT split on {entry.attendance_entry_id}"
            assert (
                entry.normal_hours + entry.double_hours + entry.triple_hours == entry.actual_hours
            ), f"OT split doesn't sum to actual_hours on {entry.attendance_entry_id}"

        allocations = allocations_by_entry.get(entry.attendance_entry_id, [])
        if not allocations:
            if entry.actual_hours and entry.actual_hours > 0:
                unallocated_seen = True
            continue
        total = Decimal("0")
        for alloc in allocations:
            assert alloc.category in valid_categories
            seeded_categories.add(alloc.category)
            total += alloc.hours
        assert total <= (
            entry.actual_hours or Decimal("0")
        ), f"allocations exceed actual_hours on {entry.attendance_entry_id}"

    assert override_seen, "expected at least one labor_class_override entry"
    assert unsplit_seen, "expected at least one unsplit (all-NULL) OT entry"
    assert unallocated_seen, "expected at least one unallocated (but worked) entry"
    assert (
        seeded_categories == valid_categories
    ), f"expected all 8 HourCategoryEnum values across the demo dataset, got {sorted(seeded_categories)}"
