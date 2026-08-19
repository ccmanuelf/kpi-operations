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

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.calculations.otd import calculate_true_otd
from backend.calculations.wip_aging import (
    NON_WIP_HOLD_STATUSES,
    identify_chronic_holds,
    snapshot_cutoff,
)
from backend.orm import (
    AttendanceEntry,
    DefectDetail,
    HoldEntry,
    HoldStatus,
    HoldStatusTransition,
    ProductionEntry,
    QualityEntry,
    WorkOrder,
)
from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.narrative import narrative_window_touches, window_active
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

    `len(chronic) >= 3` cannot tell those apart. 25 clears it, 11 clears it,
    and so does the 16 that silently dropping `threshold_days=60` produces
    (the parameter then resolves through get_client_wip_thresholds(db, None)
    -> (7, 14) -> critical * 2 = a 28-day bar). Three further assertions
    carry the distinction the docstring claims, each picked to be
    CLOCK-STABLE: identify_chronic_holds reads date.today() internally and
    takes no as_of, while this fixture is anchored at AS_OF = 2026-08-18.

      1. Nothing it returned is in NON_WIP_HOLD_STATUSES. Measured 0 today,
         0 at +1y, 0 at +10y on a frozen-clock sweep.
      2. The dataset genuinely contains 60-day-aged PENDING_HOLD_APPROVAL
         holds -- 14 of them, anchored on AS_OF so the number cannot drift --
         so assertion 1 is exercised rather than vacuously satisfied.
      3. `threshold_days_used`, which identify_chronic_holds copies from its
         own parameter into every row it returns, is exactly 60, and no
         returned hold is younger than 60 days.

    Assertion 3 is deliberately NOT the count comparison it looks like it
    should be. `len(at 60) < len(at the config default)` holds today (11 vs
    16) and stops holding almost immediately: the same frozen-clock sweep
    measures 11/16 at 2026-08-19 but 20/20 at +1y and 20/20 at +10y, because
    once every seeded hold has aged past sixty days both bars select the same
    rows. Reading back the parameter the calculator reports has no such
    saturation point.

    The counts above are recorded and deliberately NOT asserted, for the same
    reason: the sixty-day answer walks 11 -> 20 -> 20 across that sweep, so
    `== 11` would be a time bomb. Everything asserted below is monotone-safe
    -- holds only age, and the two exact numbers (14, 60) are anchored on
    AS_OF and on the argument passed in, neither of which moves with the
    calendar.
    """
    sixty_days_before_as_of = datetime.combine(AS_OF - timedelta(days=60), time.min)
    with Session(full_db) as db:
        chronic = identify_chronic_holds(db, threshold_days=60)
        statuses = db.execute(
            select(HoldEntry.hold_entry_id, HoldEntry.hold_status).where(
                HoldEntry.hold_entry_id.in_([h["hold_id"] for h in chronic])
            )
        ).all()
        latest_transition = db.execute(select(func.max(HoldStatusTransition.transitioned_at))).scalar_one()
        aged_and_excluded = db.execute(
            select(func.count())
            .select_from(HoldEntry)
            .where(
                HoldEntry.hold_status == HoldStatus.PENDING_HOLD_APPROVAL,
                HoldEntry.resume_date.is_(None),
                HoldEntry.hold_date < sixty_days_before_as_of,
            )
        ).scalar_one()

    assert len(chronic) >= 3

    # Reading HOLD_ENTRY.hold_status is reading the EFFECTIVE status here,
    # not merely the current one: every transition this dataset writes
    # predates today's snapshot cutoff, so active_as_of's three-tier
    # resolution settles on tier 1 (the latest transition before the cutoff),
    # and _hold_status_changed mirrors that same to_status into the column.
    # Asserted rather than assumed, so the equivalence cannot rot silently.
    assert latest_transition < snapshot_cutoff(date.today())
    assert [status for _, status in statuses if status in NON_WIP_HOLD_STATUSES] == []
    # Named LITERALLY as well, and that is not redundancy. The line above reads
    # the production tuple, so commenting PENDING_HOLD_APPROVAL out of it
    # removes the status from the calculator AND from this check at the same
    # time: measured, that mutation left all 8 tests in this module green. Only
    # a check that names the status independently of the list under test can
    # see the exclusion being withdrawn.
    assert [status for _, status in statuses if status == HoldStatus.PENDING_HOLD_APPROVAL] == []

    # The INCLUSION half, and the only assertion in this test that is not
    # one-directional. Every other one here says "nothing bad appeared in the
    # output", which ANY narrowing of the result set satisfies -- the whole
    # `A | B == C` shape again, blind to UNDER-inclusion, with `len(chronic)
    # >= 3` against an actual 11 as the sole lower bound and 8x of headroom
    # under it. Measured defeat, an ordinary one-token widening at
    # writers_operations.py:168 -- `if e.to_status == "RESUMED":` ->
    # `if e.to_status in ("RESUMED", "PENDING_RESUME_APPROVAL"):`, i.e.
    # stamping resume_date on holds that have only REQUESTED a resume: the
    # chronic list silently falls 11 -> 7, four aged holds vanish from every
    # WIP-aging screen, and the entire suite stays green.
    #
    # Pinned as a SET, not a count: counts saturate (the 11 walks to 20 on a
    # +1y frozen clock, and both bars converge once every hold has aged past
    # sixty days), while the two statuses are present at AS_OF, +1d, +1y and
    # +10y on that same sweep. It kills two regressions at once -- the
    # resume_date mis-stamp above, and reverting identify_chronic_holds'
    # active arm to the pre-fix `hold_status == ON_HOLD`, which until now was
    # caught only by test_holds_aging_portability.py against hand-built
    # fixtures and never by the seeded dataset that is the only thing able to
    # demonstrate the INCLUSION half of the distinction this docstring claims.
    assert {status for _, status in statuses} == {HoldStatus.ON_HOLD, HoldStatus.PENDING_RESUME_APPROVAL}

    assert aged_and_excluded == 14

    assert {h["threshold_days_used"] for h in chronic} == {60}
    assert [h["hold_id"] for h in chronic if h["aging_days"] < 60] == []


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

    THE FLOORS ARE MEASURED, NOT GUESSED, and both vectors are recorded here
    so the next reader does not have to re-derive them (the same discipline
    the 3.22x/7.50x pair in the absenteeism test above records):

        LATE_RATE_NARRATIVE = 0.9 (healthy, shipping):  PIECE 5, HOURLY 3,
            HYBRID 3 months below 80%; annual standard OTD 75.68 / 80.65 /
            75.00%.
        LATE_RATE_NARRATIVE = 0.4 (damaged):            PIECE 1, HOURLY 2,
            HYBRID 2; annual 94.59 / 90.32 / 91.67% -- four healthy-looking
            clients and no OTD story left on the dashboards.

    So DEMO-PIECE >= 4 is the real discriminator: 3 clear of the damaged
    value (1) and 1 under the healthy one (5). An earlier revision of this
    docstring read "margin 1 above the damaged value", which is simply wrong
    against the vector recorded directly above it -- corrected here rather
    than left to mislead the next reader into thinking the bar is tighter
    than it is. `>= 1` (the bar this replaces) sat blind across roughly
    0.3-0.5 and only went red at 0.15, where every client flattens to 100%.

    STATED LIMITATION, deliberate: DEMO-HOURLY >= 2 and DEMO-HYBRID >= 2
    catch TOTAL flattening only -- at 0.4 both still measure exactly 2, so
    neither notices that degradation. A `>= 3` bar on either would have zero
    margin against the healthy vector and would go red on any unrelated
    reseed jitter, so it is rejected on purpose rather than overlooked.
    DEMO-PIECE carries the discrimination for all three.
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

    for client_id, floor in (("DEMO-PIECE", 4), ("DEMO-HOURLY", 2), ("DEMO-HYBRID", 2)):
        below = months[client_id][1]
        assert below >= floor, f"{client_id}: {below} months below 80% OTD, floor is {floor}"

    assert months["SAMPLE_REF"][1] == 0


def test_some_in_window_order_still_ships_on_time(full_db):
    """The lower bound on the ON-TIME side, which nothing else in this file
    carries.

    Every OTD assertion above is a floor on LATENESS, so all of them are
    satisfied -- more comfortably, in fact -- by LATE_RATE_NARRATIVE = 1.0.
    That constant is documented as 0.9 rather than 1.0 precisely so the RNG
    still decides WHICH eligible orders ship on time ("a hard 100% would read
    as scripted rather than drawn", backend/seed/narrative.py:33), and until
    now that stated distinction rested on nothing: measured on FULL/1234 the
    shipped 0.9 yields 24 of 25 in-window deliveries late, so the entire
    "drawn, not scripted" claim hangs on a single work order that no
    assertion mentioned.

    IN-WINDOW is recomputed here with the production predicate
    (narrative_window_touches over the order's own received -> required
    commitment span, exactly as emitters_operations.py:119 calls it) rather
    than reimplemented, and the restriction is the point: out-of-window
    orders draw against LATE_RATE_BASELINE = 0.0 and are ALWAYS on time, so
    an unrestricted on-time count would stay large at 1.0 and prove nothing.

    AGGREGATE ACROSS THE TROUBLED CLIENTS, NOT PER CLIENT, and that is a
    measured limitation rather than a preference. The per-client vector on
    FULL/1234 is DEMO-PIECE 0 of 9, DEMO-HOURLY 0 of 6, DEMO-HYBRID 1 of 10:
    a per-client floor is unsatisfiable today and would have to be bought by
    lowering LATE_RATE_NARRATIVE, which would weaken the OTD story the tests
    above defend. SAMPLE_REF is excluded because its narrative tuple is
    empty, so it has no in-window orders at all to contribute.

    The denominator is asserted too. Without it a regression that stopped
    emitting in-window deliveries entirely would leave both counts at zero
    and the on-time floor could not tell that apart from the failure it
    exists to catch.
    """
    in_window = on_time = 0
    with full_db.connect() as conn:
        for scenario in SCENARIOS:
            rows = conn.execute(
                select(WorkOrder.received_date, WorkOrder.required_date, WorkOrder.actual_delivery_date).where(
                    WorkOrder.client_id == scenario.client_id, WorkOrder.actual_delivery_date.isnot(None)
                )
            ).all()
            for received, required, delivered in rows:
                if not narrative_window_touches(scenario, received.date(), required.date(), AS_OF):
                    continue
                in_window += 1
                on_time += delivered <= required

    assert in_window >= 20, f"only {in_window} in-window deliveries -- the on-time floor below is vacuous"
    assert on_time >= 1, "every in-window order shipped late: LATE_RATE_NARRATIVE reads as scripted, not drawn"


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
