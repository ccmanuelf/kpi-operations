from datetime import date, timedelta

import pytest

from backend.seed.events import HoldOpened, ShiftWorked
from backend.seed.generator import generate
from backend.seed.profiles import FULL
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 14)


@pytest.fixture(scope="module")
def events():
    """Module-scoped: the FULL profile is ~50k events and every test here
    needs the same stream. Regenerating per test would dominate the suite."""
    return generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)


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
    earlier, later = _window(-8, -6)
    holds = [
        e
        for e in events
        if isinstance(e, HoldOpened) and e.client_id == "DEMO-PIECE" and earlier <= e.at.date() <= later
    ]
    assert len(holds) >= 3
