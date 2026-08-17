from datetime import date, timedelta

import pytest

from backend.seed.events import HoldOpened, ShiftWorked, WorkOrderStatusChanged
from backend.seed.generator import generate
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


def _shift_events(events, client_id, lo, hi):
    earlier, later = _window(lo, hi)
    rows = [
        e for e in events if isinstance(e, ShiftWorked) and e.client_id == client_id and earlier <= e.at.date() <= later
    ]
    assert rows, f"no ShiftWorked rows for {client_id} in [{earlier}, {later}] — assertion would be vacuous"
    return rows


def _defect_rate(events, client_id, lo, hi):
    rows = _shift_events(events, client_id, lo, hi)
    produced = sum(r.units_produced for r in rows)
    defective = sum(r.units_defective for r in rows)
    return defective / produced if produced else 0.0


def test_supplier_quality_crisis_lifts_demo_piece_defect_rate(events):
    """The scripted episode must be visible in the data, or the Q3 view has
    nothing to show and the DHU derivation cannot be demoed."""
    crisis = _defect_rate(events, "DEMO-PIECE", -8, -6)
    baseline = _defect_rate(events, "DEMO-PIECE", -3, -1)

    assert crisis > baseline * 1.5


def test_equipment_decline_lifts_demo_hourly_downtime(events):
    crisis = sum(r.downtime_minutes for r in _shift_events(events, "DEMO-HOURLY", -5, -3))
    baseline = sum(r.downtime_minutes for r in _shift_events(events, "DEMO-HOURLY", -2, -1))

    # Windows differ in length, so compare per-shift averages, not totals.
    crisis_avg = crisis / len(_shift_events(events, "DEMO-HOURLY", -5, -3))
    baseline_avg = baseline / len(_shift_events(events, "DEMO-HOURLY", -2, -1))
    assert crisis_avg > baseline_avg * 1.5


def test_labor_disruption_drops_demo_hybrid_attendance(events):
    def avg_headcount(lo, hi):
        rows = _shift_events(events, "DEMO-HYBRID", lo, hi)
        return sum(r.attendance_headcount for r in rows) / len(rows)

    assert avg_headcount(-4, -2) < avg_headcount(-2, -1)


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
