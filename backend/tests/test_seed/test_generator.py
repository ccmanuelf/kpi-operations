from datetime import date, timedelta

from backend.seed.events import (
    ClientCreated,
    EmployeeHired,
    HoldOpened,
    HoldStatusChanged,
    ShiftWorked,
    WorkOrderReceived,
    WorkOrderStatusChanged,
)
from backend.seed.generator import generate, stream_digest
from backend.seed.profiles import SMOKE
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 14)


def _gen(seed=1234):
    return generate(SCENARIOS, SMOKE, seed=seed, as_of=AS_OF)


def test_same_inputs_produce_an_identical_stream():
    assert stream_digest(_gen()) == stream_digest(_gen())


def test_a_different_seed_produces_a_different_stream():
    """Guards against a generator that ignores its seed and returns a
    constant, which would make the determinism test above vacuous."""
    assert stream_digest(_gen(seed=1234)) != stream_digest(_gen(seed=5678))


def test_stream_is_ordered_by_at_then_seq():
    events = _gen()
    assert events == sorted(events, key=lambda e: e.order_key)


def test_seq_is_strictly_increasing_across_the_whole_stream():
    """Ties within a second must be resolved by data, not by sort stability."""
    seqs = [e.seq for e in _gen()]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def test_every_timestamp_is_whole_seconds_and_naive():
    for e in _gen():
        assert e.microsecond_free()


def test_no_event_precedes_its_client_creation():
    """Referential integrity in time: the materializer inserts in stream order
    and would hit an FK violation otherwise."""
    created_at = {}
    for e in _gen():
        if isinstance(e, ClientCreated):
            created_at[e.client_id] = e.order_key
        else:
            assert e.client_id in created_at
            assert created_at[e.client_id] < e.order_key


def test_work_order_events_follow_the_work_order_receipt():
    seen = set()
    for e in _gen():
        if isinstance(e, WorkOrderReceived):
            seen.add(e.work_order_id)
        elif isinstance(e, WorkOrderStatusChanged):
            assert e.work_order_id in seen
        elif isinstance(e, HoldOpened):
            assert e.work_order_id in seen


def test_every_work_order_gets_an_opening_status_row():
    """The gap that made the old seeder's transition log unusable: 60 of 100
    orders had no chain at all."""
    received = {e.work_order_id for e in _gen() if isinstance(e, WorkOrderReceived)}
    opened = {e.work_order_id for e in _gen() if isinstance(e, WorkOrderStatusChanged) and e.from_status is None}
    assert received == opened


def test_transition_timestamps_are_distinct_per_work_order():
    """The other half of that defect: all 40 chains shared one instant, so
    status intervals were zero-length and unanswerable."""
    per_order = {}
    for e in _gen():
        if isinstance(e, WorkOrderStatusChanged):
            per_order.setdefault(e.work_order_id, []).append(e.at)
    multi = {k: v for k, v in per_order.items() if len(v) > 1}
    assert multi, "fixture produced no multi-transition orders; the assertion below would be vacuous"
    for wo, times in multi.items():
        assert len(set(times)) == len(times), f"{wo} has duplicate transition instants"


def test_hold_status_changes_follow_their_hold():
    opened = set()
    for e in _gen():
        if isinstance(e, HoldOpened):
            opened.add(e.hold_entry_id)
        elif isinstance(e, HoldStatusChanged):
            assert e.hold_entry_id in opened


def test_shift_events_cover_the_profile_window():
    """The brief's flat "- 4 for weekends" slack is brittle against the
    SMOKE window's actual weekday composition, so compute the exact expected
    working-day count (Mon-Fri, mirroring the generator's own day loop) and
    assert equality rather than a hand-picked slack constant."""
    days = {e.at.date() for e in _gen() if isinstance(e, ShiftWorked)}
    start = AS_OF - timedelta(days=SMOKE.days)
    expected_working_days = sum(1 for offset in range(SMOKE.days) if (start + timedelta(days=offset)).weekday() < 5)
    assert len(days) == expected_working_days


def test_each_client_gets_its_declared_employee_count():
    per_client = {}
    for e in _gen():
        if isinstance(e, EmployeeHired):
            per_client[e.client_id] = per_client.get(e.client_id, 0) + 1
    for scenario in SCENARIOS:
        assert per_client[scenario.client_id] == SMOKE.employees_per_client
