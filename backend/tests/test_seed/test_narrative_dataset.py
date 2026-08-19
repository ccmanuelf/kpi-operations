"""Spec section 8's scripted-event assertions, against a FULL seeded database.

Three of the ten are deferred to S2 because S1b does not write their data:
demotions co-located with scheduling downtime (needs WorkOrderDemoted),
one audit row per audited table (needs AUDIT_ENTRY authoring), and the
floating-pool half of the absenteeism assertion (needs COVERAGE_ENTRY).
Everything else runs here -- a dataset whose headline observables nobody
checks is how the current one rotted.

Runs on the FULL profile, not SMOKE: a 14-day smoke window cannot contain a
60-day-old hold or twelve monthly buckets. FULL seeds in ~1.3s on SQLite, so
the module-scoped `full_db` fixture below pays that cost once for the whole
file rather than once per test.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.calculations.otd import calculate_true_otd
from backend.orm import (
    AttendanceEntry,
    DefectDetail,
    HoldEntry,
    ProductionEntry,
    QualityEntry,
    WorkOrder,
)
from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.narrative import window_active
from backend.seed.profiles import FULL
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 18)


@pytest.fixture(scope="module")
def full_db(seed_engine_module):
    events = generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)
    with seed_engine_module.begin() as conn:
        materialize(conn, events, FULL)
    return seed_engine_module


def _dhu(conn, client_id, months):
    """Defects per hundred units over a set of (year, month) buckets."""
    rows = conn.execute(
        select(QualityEntry.shift_date, QualityEntry.total_defects_count, QualityEntry.units_inspected).where(
            QualityEntry.client_id == client_id
        )
    ).all()
    defects = units = 0
    for shift_date, d, u in rows:
        if (shift_date.year, shift_date.month) in months:
            defects += d
            units += u
    return (defects * 100 / units) if units else 0.0


def test_demo_piece_dhu_spikes_in_its_crisis_window(full_db):
    scenario = next(s for s in SCENARIOS if s.client_id == "DEMO-PIECE")
    crisis, baseline = set(), set()
    day = AS_OF - timedelta(days=364)
    while day <= AS_OF:
        bucket = crisis if window_active(scenario, day, AS_OF, "supplier_quality_crisis") else baseline
        bucket.add((day.year, day.month))
        day += timedelta(days=1)
    # A month straddling the window boundary lands in both; drop those so the
    # comparison is between clean populations.
    crisis, baseline = crisis - baseline, baseline - crisis

    with full_db.connect() as conn:
        assert _dhu(conn, "DEMO-PIECE", crisis) >= 2 * _dhu(conn, "DEMO-PIECE", baseline)


def test_at_least_three_holds_are_aged_past_sixty_days(full_db):
    cutoff = AS_OF - timedelta(days=60)
    with full_db.connect() as conn:
        chronic = conn.execute(
            select(func.count())
            .select_from(HoldEntry)
            .where(HoldEntry.resume_date.is_(None), HoldEntry.hold_date < cutoff)
        ).scalar_one()

    assert chronic >= 3


def test_every_client_has_twelve_distinct_months_of_production_and_quality(full_db):
    with full_db.connect() as conn:
        for scenario in SCENARIOS:
            for model in (ProductionEntry, QualityEntry):
                dates = (
                    conn.execute(select(model.shift_date).where(model.client_id == scenario.client_id)).scalars().all()
                )
                months = {(d.year, d.month) for d in dates}

                assert len(months) >= 12, f"{scenario.client_id}/{model.__name__}: {len(months)} months"


def test_demo_hourly_maintenance_downtime_dominates_inside_its_window(full_db):
    """Spec section 8 row 7 says 'unplanned-maintenance downtime' -- read
    literally as downtime_reason == 'MAINTENANCE' this assertion fails, and
    should: MAINTENANCE is one of the two DOWNTIME_TAXONOMY
    PLANNED_DOWNTIME_REASONS, and calculate_mtbf (backend/calculations/
    availability.py:87) excludes planned reasons because it counts FAILURES.
    downtime_taxonomy() in backend/seed/narrative.py therefore writes machine
    root-cause stops as EQUIPMENT_FAILURE -- the unplanned sibling reason --
    while the equipment-reliability-decline window is open, precisely so
    MTBF (the metric this client's whole story is named for) can move.
    test_equipment_decline_lands_as_UNPLANNED_downtime in test_narrative.py
    guards that same design at the event-stream layer; asserting the literal
    'MAINTENANCE' string here would assert the regression that fix removed.
    'Unplanned-maintenance' is EQUIPMENT_FAILURE."""
    from collections import Counter

    from backend.orm import DowntimeEntry

    scenario = next(s for s in SCENARIOS if s.client_id == "DEMO-HOURLY")
    with full_db.connect() as conn:
        rows = conn.execute(
            select(
                DowntimeEntry.shift_date, DowntimeEntry.downtime_reason, DowntimeEntry.downtime_duration_minutes
            ).where(DowntimeEntry.client_id == "DEMO-HOURLY")
        ).all()

    inside = Counter()
    for shift_date, reason, minutes in rows:
        if window_active(scenario, shift_date.date(), AS_OF, "equipment_reliability_decline"):
            inside[reason] += minutes

    others = sum(v for k, v in inside.items() if k != "EQUIPMENT_FAILURE")

    assert inside["EQUIPMENT_FAILURE"] >= 2 * others


def test_demo_hybrid_absenteeism_peaks_inside_its_window(full_db):
    scenario = next(s for s in SCENARIOS if s.client_id == "DEMO-HYBRID")
    with full_db.connect() as conn:
        rows = conn.execute(
            select(AttendanceEntry.shift_date, AttendanceEntry.is_absent).where(
                AttendanceEntry.client_id == "DEMO-HYBRID"
            )
        ).all()

    inside = [a for d, a in rows if window_active(scenario, d.date(), AS_OF, "labor_disruption")]
    outside = [a for d, a in rows if not window_active(scenario, d.date(), AS_OF, "labor_disruption")]

    assert inside and outside
    assert sum(bool(a) for a in inside) / len(inside) > sum(bool(a) for a in outside) / len(outside)


def test_otd_dips_below_eighty_percent_for_at_least_one_client_and_never_for_sample_ref(full_db):
    """Spec section 8 row 3. SAMPLE_REF is the healthy control -- if it dips,
    the dashboards are uniformly red and the thresholds read as broken.

    Drives the PRODUCTION calculator (backend/calculations/otd.py:
    calculate_true_otd), not a reimplementation of the metric: it needs only
    a plain Session, no request context, so calling it proves the seeded data
    agrees with the application's own OTD calculation rather than with this
    test author's idea of one. `standard_otd` (not `true_otd`) is used
    because it counts every delivered order regardless of status, matching
    spec section 8's "at least one month per client below 80% OTD" framing
    rather than the COMPLETED-only subset TRUE-OTD scopes to.
    """
    # Wide enough to catch every seeded delivery: FULL spans profile.days=365
    # plus setup overhead, so 400 days back from AS_OF is a safe margin
    # without depending on the exact activity_start the setup band computes.
    start = AS_OF - timedelta(days=400)

    rates = {}
    with Session(full_db) as db:
        for scenario in SCENARIOS:
            result = calculate_true_otd(db, scenario.client_id, start, AS_OF)
            standard = result["standard_otd"]
            assert standard["total"] > 0, f"{scenario.client_id}: no delivered orders -- OTD is undemonstrable"
            rates[scenario.client_id] = standard["percentage"]

    assert min(rates.values()) < Decimal("80")
    assert rates["SAMPLE_REF"] >= Decimal("80")


def test_the_priority_adherence_denominator_is_non_empty_and_incomplete(full_db):
    """Spec section 3 decision 6: orders with no priority are excluded from the
    denominator and their share is published as a coverage figure. A dataset
    where every order has a priority cannot demonstrate the exclusion works."""
    with full_db.connect() as conn:
        total = conn.execute(select(func.count()).select_from(WorkOrder)).scalar_one()
        with_priority = conn.execute(
            select(func.count()).select_from(WorkOrder).where(WorkOrder.priority.isnot(None))
        ).scalar_one()

    assert with_priority > 0
    assert with_priority < total


def test_defect_rows_exist_for_every_client(full_db):
    with full_db.connect() as conn:
        clients = conn.execute(select(func.distinct(DefectDetail.client_id_fk))).scalars().all()

    assert set(clients) == {s.client_id for s in SCENARIOS}
