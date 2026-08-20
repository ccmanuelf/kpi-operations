from collections import Counter
from datetime import date, timedelta

import pytest

from backend.seed.events import (
    AttendanceRecorded,
    DowntimeLogged,
    HoldOpened,
    ProductionRecorded,
    QualityInspected,
    WorkOrderStatusChanged,
)
from backend.seed.generator import generate
from backend.seed.narrative import window_active
from backend.seed.profiles import FULL
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 14)

# A single FULL stream yields only ~17 holds per client, of which 2-6 land in
# the two-month crisis window -- far too few for a rate comparison to mean
# anything (seed 7 alone shows a ratio of 1.17 where the true parameter ratio
# is 3.33). Pooling twelve independent streams raises that to ~53 in-window
# holds and puts the measured ratio within 6% of the parameter. Generation is
# ~0.03s per stream, so the whole pool costs well under a second.
POOL_SEEDS = tuple(range(1, 13))


@pytest.fixture(scope="module")
def events():
    """Module-scoped: the FULL profile is ~50k events and every test here
    needs the same stream. Regenerating per test would dominate the suite."""
    return generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)


@pytest.fixture(scope="module")
def stream_pool():
    return [generate(SCENARIOS, FULL, seed=s, as_of=AS_OF) for s in POOL_SEEDS]


def _window(lo_months, hi_months):
    """Calendar bounds for a month-offset window. Offsets are negative, so the
    EARLIER bound comes from the LARGER absolute value -- getting this backwards
    yields an empty range that silently matches nothing and makes every
    assertion below vacuous."""
    earlier = AS_OF - timedelta(days=abs(lo_months) * 30)
    later = AS_OF - timedelta(days=abs(hi_months) * 30)
    assert earlier < later
    return earlier, later


def _shift_events(events, cls, client_id, lo, hi):
    """One shift now writes five kinds of event, so the caller names which one
    it is measuring. Filtered on `at` rather than `shift_date`: they are the
    same calendar day by construction (both are built from the day the shift
    loop is on), and `at` is the only field every event carries."""
    earlier, later = _window(lo, hi)
    rows = [e for e in events if isinstance(e, cls) and e.client_id == client_id and earlier <= e.at.date() <= later]
    assert rows, f"no {cls.__name__} rows for {client_id} in [{earlier}, {later}] — assertion would be vacuous"
    return rows


def _defect_rate(events, client_id, lo, hi):
    rows = _shift_events(events, QualityInspected, client_id, lo, hi)
    inspected = sum(r.units_inspected for r in rows)
    defective = sum(r.units_defective for r in rows)
    return defective / inspected if inspected else 0.0


def test_supplier_quality_crisis_lifts_demo_piece_defect_rate(events):
    """The scripted episode must be visible in the data, or the Q3 view has
    nothing to show and the DHU derivation cannot be demoed."""
    crisis = _defect_rate(events, "DEMO-PIECE", -8, -6)
    baseline = _defect_rate(events, "DEMO-PIECE", -3, -1)

    assert crisis > baseline * 1.5


def test_equipment_decline_lifts_demo_hourly_downtime(events):
    crisis_rows = _shift_events(events, DowntimeLogged, "DEMO-HOURLY", -5, -3)
    baseline_rows = _shift_events(events, DowntimeLogged, "DEMO-HOURLY", -2, -1)

    # Windows differ in length, so compare per-shift averages, not totals.
    crisis_avg = sum(r.downtime_minutes for r in crisis_rows) / len(crisis_rows)
    baseline_avg = sum(r.downtime_minutes for r in baseline_rows) / len(baseline_rows)
    assert crisis_avg > baseline_avg * 1.5


def _hourly_downtime_split(events):
    """DEMO-HOURLY's downtime rows, partitioned by whether the
    equipment-reliability-decline window covers the shift."""
    hourly = next(s for s in SCENARIOS if s.client_id == "DEMO-HOURLY")
    rows = [e for e in events if isinstance(e, DowntimeLogged) and e.client_id == "DEMO-HOURLY"]
    inside = [e for e in rows if window_active(hourly, e.shift_date.date(), AS_OF, "equipment_reliability_decline")]
    outside = [
        e for e in rows if not window_active(hourly, e.shift_date.date(), AS_OF, "equipment_reliability_decline")
    ]
    assert inside and outside, "one side of the window is empty; the comparisons below would be vacuous"
    return inside, outside


def test_equipment_decline_biases_the_root_cause_toward_machine(events):
    """Spec section 6: DEMO-HOURLY must read as equipment reliability. Scaling
    only downtime MINUTES leaves Q2 an undifferentiated total."""
    inside, outside = _hourly_downtime_split(events)
    inside_share = Counter(e.root_cause_category for e in inside)
    outside_share = Counter(e.root_cause_category for e in outside)

    assert inside_share["machine"] / len(inside) > 2 * (outside_share["machine"] / len(outside))


def test_equipment_decline_lands_as_UNPLANNED_downtime(events):
    """The root_cause_category column alone is not enough, and asserting only
    on it hid this: every machine-category stop was written
    downtime_reason=MAINTENANCE, which is one of the two members of
    PLANNED_DOWNTIME_REASONS. calculate_mtbf (backend/calculations/availability
    .py:87) excludes that set because it counts FAILURES -- so a reliability
    decline made entirely of maintenance produced ZERO failures and MTBF, the
    metric named for the very thing the episode is about, could not move.
    (The raw minutes still landed on the client+date aggregates the
    dashboard, trends, downtime and my_shift endpoints read; what was lost is
    the reliability reading. They do NOT land on calculate_availability or
    calculate_mttr -- those filter DowntimeEntry.work_order_id
    (backend/calculations/availability.py:38) and machine_id
    (availability.py:127) respectively, and the seeder leaves both columns
    NULL, so availability returns (100, 8.0, 0, 0) and MTTR/MTBF return None
    regardless of what this episode writes. Measured, not assumed.)

    Imported from the live taxonomy rather than restated here, so a change to
    what counts as planned reaches this assertion instead of drifting past it.
    Measured on FULL/1234: 69.99 unplanned minutes per shift inside the window
    against 12.48 outside, ratio 5.6, with the in-window unplanned share at
    1.000 versus 0.575."""
    from backend.orm.downtime_taxonomy import PLANNED_DOWNTIME_REASONS

    inside, outside = _hourly_downtime_split(events)

    def unplanned_minutes_per_shift(rows):
        return sum(e.downtime_minutes for e in rows if e.downtime_reason not in PLANNED_DOWNTIME_REASONS) / len(rows)

    assert unplanned_minutes_per_shift(inside) > 2 * unplanned_minutes_per_shift(outside)


def test_every_downtime_reason_agrees_with_its_root_cause_category(events):
    """The two columns are written from one map, so they can never disagree --
    but only if that map stays the canonical one. DEFAULT_CATEGORY_BY_REASON in
    backend/orm/downtime_taxonomy.py is the single source of truth the schemas,
    the ORM validators and the reference endpoint all read; asserting against
    it is what keeps the EQUIPMENT_FAILURE override honest rather than merely
    self-consistent."""
    from backend.orm.downtime_taxonomy import DEFAULT_CATEGORY_BY_REASON

    rows = [e for e in events if isinstance(e, DowntimeLogged)]
    assert rows, "fixture produced no downtime; the assertion below would be vacuous"
    for e in rows:
        assert DEFAULT_CATEGORY_BY_REASON[e.downtime_reason] == e.root_cause_category


def test_labor_disruption_drops_demo_hybrid_attendance(events):
    """Measured off ATTENDANCE_ENTRY's own per-employee rows, which is what the
    widened model made expressible: the retired headcount field could only say
    how many showed up, never who was absent, so an absence rate -- the figure
    the Q2 labor view actually reports -- had to be inferred.

    A RATIO, not a bare `<`. The predecessor asserted only that the in-window
    average was the smaller of two numbers, which two noisy estimates of the
    same quantity satisfy half the time: deleting the narrative multiplier from
    the absence threshold left this test green. The declared multiplier is
    2/3 of a 0.95 present-threshold, i.e. ~37% absence inside the window
    against a ~5% baseline -- measured 0.359 vs 0.054, ratio 6.6."""

    def absence_rate(lo, hi):
        rows = _shift_events(events, AttendanceRecorded, "DEMO-HYBRID", lo, hi)
        return sum(1 if r.is_absent else 0 for r in rows) / len(rows)

    assert absence_rate(-4, -2) > absence_rate(-2, -1) * 2.0


# Every client with a narrative, and the window that narrative covers.
_NARRATIVE_WINDOWS = (
    ("DEMO-PIECE", -8, -6),
    ("DEMO-HOURLY", -5, -3),
    ("DEMO-HYBRID", -4, -2),
)

# Floors on how many DISTINCT values each drawn quantity must take inside a
# window, now that the four quantities live on four different events. Set well
# below what the generator actually produces at FULL/1234 -- measured across
# the three narrative windows: units_produced 69-73, units_defective 6-17,
# downtime_minutes 35-36, employees_assigned 3-4 -- so ordinary re-tuning of a
# range does not trip them, but far enough above 1 that any collapse to a
# constant does.
#
# employees_assigned carries the lowest floor because it is the only one whose
# cardinality is structurally capped: it is a headcount bounded by the crew
# size (FULL puts 8 employees on 2 lines, so 4 per line) and floored at 1, so
# 4 values is the most it can ever take and 2 is the highest floor that still
# leaves room for re-tuning. It remains the check that caught the constant
# headcount, which scored 1.
_MIN_DISTINCT_IN_WINDOW = (
    (ProductionRecorded, "units_produced", 20),
    (QualityInspected, "units_defective", 5),
    (DowntimeLogged, "downtime_minutes", 10),
    (ProductionRecorded, "employees_assigned", 2),
)


def test_each_narrative_window_still_varies_day_to_day(events):
    """The three scale tests above compare a window against a baseline, and
    multiplication preserves that ratio whether or not the underlying series
    varies -- replacing all three drawn quantities with constants and keeping
    only the `* scale[...]` multipliers left every one of them green. So the
    ratio is not evidence that a statistical baseline exists.

    Spec section 3.3 chose hybrid shaping precisely because "purely scripted
    data makes every day mechanically regular", so assert the variation
    directly, INSIDE each window, where a scripted episode is most likely to
    have flattened it. This is what would have caught attendance_headcount
    being a constant."""
    for client_id, lo, hi in _NARRATIVE_WINDOWS:
        for cls, field, floor in _MIN_DISTINCT_IN_WINDOW:
            rows = _shift_events(events, cls, client_id, lo, hi)
            distinct = len({getattr(r, field) for r in rows})
            assert distinct >= floor, f"{client_id} {field}: only {distinct} distinct values across {len(rows)} rows"


def test_sample_ref_has_no_episode(events):
    """The control client must stay in specification all year, so a demo can
    show one healthy client beside three troubled ones."""
    early = _defect_rate(events, "SAMPLE_REF", -10, -8)
    late = _defect_rate(events, "SAMPLE_REF", -3, -1)

    assert abs(early - late) < 0.02


def test_demo_piece_accumulates_holds_in_its_window(events):
    """Spec section 6 wants chronic holds visible as a DEMO-PIECE observable on
    the shipped default stream, not merely on average over a seed pool."""
    earlier, later = _window(-8, -6)
    holds = [
        e
        for e in events
        if isinstance(e, HoldOpened) and e.client_id == "DEMO-PIECE" and earlier <= e.at.date() <= later
    ]
    assert len(holds) >= 3


def _hold_exposure_and_counts(streams, client_id, lo, hi):
    """Hold rate inside vs. outside a window, and the QUALITY share of each.

    Counting raw holds per calendar day is not a rate: a work order is only a
    hold candidate between its RELEASED transition and the end of its active
    window, and only orders whose window overlaps the crisis window can put a
    hold inside it. So normalize by EXPOSURE -- each candidate order
    contributes the fraction of its own candidate days that fall inside the
    window. Reconstructed from the stream alone (every transition is emitted),
    so the test never reaches into the generator's internals.

    Without this normalization the comparison measures how many orders happen
    to be alive during the window, not whether the narrative raised the rate.
    """
    earlier, later = _window(lo, hi)
    exposure_in = exposure_out = 0.0
    holds_in = holds_out = 0
    quality_in = quality_out = 0

    for events in streams:
        steps: dict = {}
        for e in events:
            if isinstance(e, WorkOrderStatusChanged) and e.client_id == client_id:
                steps.setdefault(e.work_order_id, []).append((e.at.date(), e.to_status))
        for chain in steps.values():
            chain.sort()
            released_day = next((d for d, status in chain if status == "RELEASED"), None)
            if released_day is None:
                continue
            terminal_day, terminal_status = chain[-1]
            window_end = terminal_day if terminal_status == "CLOSED" else AS_OF
            span = (window_end - released_day).days
            if span < 1:
                continue
            overlap = sum(1 for k in range(span) if earlier <= released_day + timedelta(days=k) <= later)
            exposure_in += overlap / span
            exposure_out += (span - overlap) / span
        for e in events:
            if not (isinstance(e, HoldOpened) and e.client_id == client_id):
                continue
            if earlier <= e.at.date() <= later:
                holds_in += 1
                quality_in += e.reason_category == "QUALITY"
            else:
                holds_out += 1
                quality_out += e.reason_category == "QUALITY"

    assert exposure_in > 0 and exposure_out > 0, f"{client_id}: no hold exposure; the rates below would be vacuous"
    assert holds_in and holds_out, f"{client_id}: no holds on one side; the shares below would be vacuous"
    return {
        "rate_in": holds_in / exposure_in,
        "rate_out": holds_out / exposure_out,
        "quality_share_in": quality_in / holds_in,
        "quality_share_out": quality_out / holds_out,
    }


def test_supplier_quality_crisis_raises_demo_pieces_own_hold_rate(stream_pool):
    """The narrative hold behaviour has to be CAUSAL, not incidental.

    The previous test counted five in-window holds and called it proof; it
    passed against a flat pre-implementation stub, none of its five holds were
    crisis-derived, and it broke when unrelated quantities were flattened --
    it measured RNG-stream position, not narrative. Worse, the hold rate and
    the QUALITY bias keyed on the order's RECEIPT date while the hold itself
    landed anywhere in an active window up to ~350 days wide, so at FULL/1234
    exactly 1 of DEMO-PIECE's 17 holds fell inside the crisis window and every
    QUALITY-biased hold fell outside it.

    Both are now keyed on the hold's own date, so the elevation is directly
    measurable: DEMO-PIECE's exposure-normalized hold rate inside its crisis
    window must exceed its own rate outside it. Measured over the seed pool:
    0.480 in vs 0.153 out (ratio 3.14), against the generator's declared
    0.5 / 0.15."""
    stats = _hold_exposure_and_counts(stream_pool, "DEMO-PIECE", -8, -6)
    assert stats["rate_in"] > stats["rate_out"] * 2.0, stats


def test_supplier_quality_crisis_shifts_demo_pieces_hold_reasons_to_quality(stream_pool):
    """Second half of the same causal claim: crisis-window holds must read as
    caused by the crisis. Measured over the seed pool: 0.547 QUALITY inside
    the window vs 0.326 outside (ratio 1.68), against the pools' declared
    3/5 and 1/3."""
    stats = _hold_exposure_and_counts(stream_pool, "DEMO-PIECE", -8, -6)
    assert stats["quality_share_in"] > stats["quality_share_out"] * 1.3, stats


def test_the_control_client_shows_no_hold_elevation_in_that_window(stream_pool):
    """Anti-artifact guard: SAMPLE_REF has no narrative at all, so the very
    same estimator over the very same calendar window must come back flat. If
    it did not, the elevation measured above would be an artifact of exposure
    accounting rather than the narrative. Measured: ratio 1.08."""
    stats = _hold_exposure_and_counts(stream_pool, "SAMPLE_REF", -8, -6)
    assert stats["rate_in"] < stats["rate_out"] * 1.5, stats
