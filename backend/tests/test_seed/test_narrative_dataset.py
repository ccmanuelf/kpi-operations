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
from backend.calculations.wip_aging import identify_chronic_holds
from backend.orm import (
    AttendanceEntry,
    DefectDetail,
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
    """Spec section 8 row 2: at least three holds aged past sixty days, and
    ALL IN THE CHRONIC LIST. That list is identify_chronic_holds
    (backend/calculations/wip_aging.py:426), so this drives the production
    calculator rather than hand-rolling the predicate -- exactly as the OTD
    assertion below drives calculate_true_otd.

    The two disagree, and the calculator is right. The hand-rolled form this
    replaces (`resume_date IS NULL AND hold_date < AS_OF - 60d`) counts 25
    holds; identify_chronic_holds returns 11. All 14 it drops sit in
    PENDING_HOLD_APPROVAL, one of active_as_of's NON_WIP_HOLD_STATUSES: the
    hold is only REQUESTED, so nothing has stopped and every WIP-aging screen
    the spec row names excludes it. The weaker form let the dataset satisfy
    this row with holds invisible on the screens it exists to populate.

    threshold_days is passed EXPLICITLY. Left out it resolves through
    get_client_wip_thresholds(db, client_id=None) -> (7, 14) and then
    `critical_threshold * 2` = 28 days -- a weaker bar than the sixty this
    row asks for, and one that answers 16 rather than 11. Stating 60 anchors
    the assertion to the spec instead of to a config default.

    identify_chronic_holds reads date.today() internally and takes no as_of
    parameter, while this fixture is anchored at AS_OF = 2026-08-18. The
    resulting drift is one-directional and safe: the holds counted here have
    resume_date IS NULL and no transitions after AS_OF, so as the real date
    advances they only age further and more of the younger ones cross the
    sixty-day line. The count is monotonically non-decreasing, so `>= 3`
    cannot begin failing with the calendar.
    """
    with Session(full_db) as db:
        chronic = identify_chronic_holds(db, threshold_days=60)

    assert len(chronic) >= 3


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
    """Spec section 8 row 8 gives no numeric bar, so the >=5x floor below
    deliberately tightens beyond the spec. It is anchored in a measured
    mutation, not guessed: with the healthy ATTENDANCE_DISRUPTION_SCALE
    (2.0/3.0) the in-window rate measures 35.56% vs 4.74% outside (720 vs
    3440 rows) -- a 7.50x ratio. Weakening that constant to 0.9 (a
    damaged-but-still-directional value that softens DEMO-HYBRID's headline
    labor-disruption story without removing it) drops the in-window rate to
    15.28%, a 3.22x ratio -- and a bare `inside_rate > outside_rate`
    assertion does not notice. 5x sits strictly between 3.22x and 7.50x, so
    it separates a working narrative from a damaged one.
    """
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
    inside_rate = sum(bool(a) for a in inside) / len(inside)
    outside_rate = sum(bool(a) for a in outside) / len(outside)
    assert inside_rate >= 5 * outside_rate


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """First and last calendar day of a month."""
    start = date(year, month, 1)
    end = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
    return start, end


def _otd_months(db, client_id: str) -> tuple[int, int]:
    """(months carrying deliveries, of which months under 80% standard OTD).

    One calculate_true_otd call per month the client actually delivered in,
    so the buckets are the calendar months a dashboard would draw rather than
    a window this test invented.
    """
    delivered = (
        db.execute(
            select(WorkOrder.actual_delivery_date).where(
                WorkOrder.client_id == client_id, WorkOrder.actual_delivery_date.isnot(None)
            )
        )
        .scalars()
        .all()
    )

    evaluated = below = 0
    for year, month in sorted({(d.year, d.month) for d in delivered}):
        start, end = _month_bounds(year, month)
        standard = calculate_true_otd(db, client_id, start, end)["standard_otd"]
        if standard["total"] == 0:
            continue
        evaluated += 1
        if standard["percentage"] < Decimal("80"):
            below += 1
    return evaluated, below


def test_otd_dips_below_eighty_percent_in_some_month_for_every_troubled_client(full_db):
    """Spec section 8 row 3, read as written: at least one MONTH per client
    below 80% OTD, and SAMPLE_REF never below. SAMPLE_REF is the healthy
    control -- if it dips, the dashboards are uniformly red and the
    thresholds read as broken.

    Bucketed by month rather than as one 400-day aggregate. The aggregate
    form shipped first and was weaker than the spec: it asserted only
    `min(rates) < 80`, so a regression that flattened DEMO-HOURLY (whose
    aggregate is 80.65%, already ABOVE the line) and DEMO-HYBRID passed
    unnoticed as long as DEMO-PIECE still dipped. Measured per month on
    FULL/1234: PIECE 5 months below, HOURLY 3, HYBRID 3, SAMPLE_REF 0, out
    of 11 / 11 / 10 / 11 months carrying deliveries.

    Drives the PRODUCTION calculator (backend/calculations/otd.py:
    calculate_true_otd), not a reimplementation of the metric: it needs only
    a plain Session, no request context, so calling it proves the seeded data
    agrees with the application's own OTD calculation rather than with this
    test author's idea of one. `standard_otd` (not `true_otd`) is used
    because it counts every delivered order regardless of status, matching
    spec section 8's "at least one month per client below 80% OTD" framing
    rather than the COMPLETED-only subset TRUE-OTD scopes to.
    """
    months = {}
    with Session(full_db) as db:
        for scenario in SCENARIOS:
            months[scenario.client_id] = _otd_months(db, scenario.client_id)

    for scenario in SCENARIOS:
        evaluated, below = months[scenario.client_id]
        # Non-vacuity: a client with no delivered orders would report zero
        # months below 80% and silently satisfy the SAMPLE_REF arm.
        assert evaluated >= 10, f"{scenario.client_id}: only {evaluated} months of deliveries -- OTD is undemonstrable"

    for client_id in ("DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID"):
        assert months[client_id][1] >= 1, f"{client_id}: no month below 80% OTD"

    assert months["SAMPLE_REF"][1] == 0


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
