from datetime import date, datetime, time, timedelta

from backend.seed.events import (
    ClientCreated,
    EmployeeHired,
    HoldOpened,
    HoldStatusChanged,
    LineCommissioned,
    ProductDefined,
    ShiftDefined,
    ShiftWorked,
    WorkOrderReceived,
    WorkOrderStatusChanged,
)
from backend.seed.generator import generate, stream_digest
from backend.seed.profiles import FULL, SMOKE, Profile
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 14)

# shifts_per_client=4 is the minimum that exposes the old (6 + si * 8) % 24
# aliasing (shift index 0 landed on the same hour as shift index 3): under
# the pre-fix formula, 40 of 40 client-days in a SMOKE-sized run had
# colliding ShiftWorked instants, but SMOKE/FULL's own shifts_per_client=2
# never reaches that collision, so neither profile can catch a regression on
# its own.
WIDE_SHIFTS = Profile(
    name="wide-shifts-test",
    days=SMOKE.days,
    lines_per_client=SMOKE.lines_per_client,
    shifts_per_client=4,
    employees_per_client=SMOKE.employees_per_client,
    work_orders_per_client=SMOKE.work_orders_per_client,
)


MANY_ENTITIES = Profile(
    name="many-entities-test",
    days=30,
    lines_per_client=20,
    shifts_per_client=12,
    employees_per_client=60,
    work_orders_per_client=6,
)


def _gen(seed=1234):
    return generate(SCENARIOS, SMOKE, seed=seed, as_of=AS_OF)


def _activity_start(profile, start):
    """Independent restatement of the generator's setup band: ClientCreated at
    06:00, then one minute per remaining setup event (1 user + lines + shifts
    + 3 products + employees), and activity begins the day after the last of
    them. Recomputed here rather than read off the stream so a regression that
    moved the band would fail the test instead of being absorbed by it."""
    setup_minutes = 1 + profile.lines_per_client + profile.shifts_per_client + 3 + profile.employees_per_client
    setup_end = datetime.combine(start, time(6, 0)) + timedelta(minutes=setup_minutes)
    return setup_end.date() + timedelta(days=1)


def test_same_inputs_produce_an_identical_stream():
    assert stream_digest(_gen()) == stream_digest(_gen())


def test_a_different_seed_produces_a_different_stream():
    """Guards against a generator that ignores its seed and returns a
    constant, which would make the determinism test above vacuous."""
    assert stream_digest(_gen(seed=1234)) != stream_digest(_gen(seed=5678))


def test_stream_is_ordered_by_at_then_seq():
    events = _gen()
    assert events == sorted(events, key=lambda e: e.order_key)


def test_seq_is_contiguous_from_one_across_the_whole_stream():
    """Sortedness and uniqueness alone cannot fail here -- generate() assigns
    seq as final stream position -- which is why this test used to say so in
    its own docstring and assert nothing else. CONTIGUITY can fail, and S1b
    depends on it: it walks the stream expecting seq to be a dense 1..n index
    into insertion order, and a gap would mean events were dropped after
    renumbering (the as_of clamp runs BEFORE renumbering precisely so this
    holds)."""
    seqs = [e.seq for e in _gen()]
    assert seqs, "fixture produced no events; the comparison below would be vacuous"
    assert seqs == list(range(1, len(seqs) + 1))


def test_shift_worked_timestamps_are_distinct_within_a_client_day():
    """order_key uniqueness is guaranteed by construction (seq is reassigned
    1..n), so it cannot catch a real ambiguity defect: collapsing every
    ShiftWorked event to one instant per day still passes it. There is one
    ShiftWorked event per (line, shift) pair per day, deliberately
    staggered by hour/minute -- assert they stay distinct within each
    (client_id, date) group, which is the property a collapse would break.

    SMOKE alone can't catch the aliasing this guards against: its
    shifts_per_client=2 never reaches the modulus where `si * step` wraps
    around and re-collides with a lower si. WIDE_SHIFTS (shifts_per_client=4)
    is the smallest profile that does, so check both."""
    for profile in (SMOKE, WIDE_SHIFTS):
        groups: dict = {}
        for e in generate(SCENARIOS, profile, seed=1234, as_of=AS_OF):
            if isinstance(e, ShiftWorked):
                groups.setdefault((e.client_id, e.at.date()), []).append(e.at)
        assert groups, "fixture produced no ShiftWorked events; the assertion below would be vacuous"
        for key, times in groups.items():
            assert len(set(times)) == len(times), f"{profile.name}/{key} has colliding ShiftWorked instants"


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


# Which attribute on an event names an entity of each creating type. An event
# carrying one of these must come after the event that created that entity.
_REFERENCED_ENTITIES = (
    (LineCommissioned, "line_id"),
    (ShiftDefined, "shift_id"),
    (ProductDefined, "product_id"),
)


def test_no_event_precedes_the_line_shift_or_product_it_references():
    """Clients were the only entity this suite checked, so a ShiftWorked
    stamped before its own line/shift went unnoticed: the modular hour/minute
    steps wrap the highest line index back to minute 0 and (at 4 shifts) the
    highest shift index back to hour 0, landing activity BELOW the 06:00 setup
    block on the same day. Measured before the fix: 8 violations on SMOKE and
    FULL, 32 on WIDE_SHIFTS.

    Checked over three profiles that stress different arithmetic:
    WIDE_SHIFTS wraps the shift HOUR to 0, and MANY_ENTITIES declares enough
    entities (96) that the setup minute cursor runs past the fixed 07:00
    WorkOrderReceived instant."""
    for profile in (SMOKE, WIDE_SHIFTS, MANY_ENTITIES):
        events = generate(SCENARIOS, profile, seed=1234, as_of=AS_OF)
        created_at: dict = {}
        checked = 0
        for e in events:
            for cls, attr in _REFERENCED_ENTITIES:
                if isinstance(e, cls):
                    created_at[(attr, getattr(e, attr))] = e.order_key
            for _, attr in _REFERENCED_ENTITIES:
                referenced = getattr(e, attr, None)
                if referenced is None or isinstance(e, tuple(c for c, a in _REFERENCED_ENTITIES if a == attr)):
                    continue
                key = (attr, referenced)
                assert key in created_at, f"{profile.name}: {type(e).__name__} references uncreated {key}"
                assert (
                    created_at[key] < e.order_key
                ), f"{profile.name}: {type(e).__name__} at {e.at} precedes creation of {key}"
                checked += 1
        assert checked, f"{profile.name} produced no referencing events; the assertions above would be vacuous"


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
    assert received, "fixture produced no work orders; the equality below would be vacuous"
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
    working-day set (Mon-Fri, mirroring the generator's own day loop) and
    compare the actual dates, not just their count -- a window shifted by
    one day would still match on cardinality alone."""
    days = {e.at.date() for e in _gen() if isinstance(e, ShiftWorked)}
    start = AS_OF - timedelta(days=SMOKE.days)
    # Day 0 (and any further day the setup band spills onto) belongs to setup
    # alone, so activity runs [activity_start, as_of) -- see _activity_start.
    activity_start = _activity_start(SMOKE, start)
    expected_days = {
        activity_start + timedelta(days=offset)
        for offset in range((AS_OF - activity_start).days)
        if (activity_start + timedelta(days=offset)).weekday() < 5
    }
    assert expected_days, "expected-day set is empty; the comparison below would be vacuous"
    assert days == expected_days


def test_no_event_is_dated_after_as_of():
    """FINDING 1: work-order and hold chains walk forward with no clamp, so
    every run emitted future-dated events past as_of. A dataset generated
    "as of" a date must not contain events after it, or a materialized
    "current status" taken from the newest transition would report a
    closure or resume that hasn't happened (spec section 3)."""
    for profile in (SMOKE, FULL):
        events = generate(SCENARIOS, profile, seed=1234, as_of=AS_OF)
        assert max(e.at for e in events).date() <= AS_OF


def test_holds_stay_within_their_work_orders_active_window():
    """FINDING 2: holds were scheduled off the work order's bare receipt
    date, independent of its status chain, so a hold could open on an order
    already CLOSED or resume before the order progressed -- fixed by
    windowing the opening. That fix alone was incomplete: HoldStatusChanged
    advanced with no bound of its own, so the chain could still walk past
    the order's terminal transition after opening inside the window. Every
    HoldOpened AND every HoldStatusChanged for that hold must fall on/after
    its work order's RELEASED transition and on/before its terminal
    transition (or as_of, if the chain hasn't reached CLOSED).

    SMOKE alone doesn't exercise this: its short window means the escape
    (a hold advancing past its order's own terminal transition while
    staying under the global as_of clamp) rarely has room to occur --
    the escape needs a chain that both terminates well before as_of AND
    has enough runway afterward for a status step to land beyond its
    terminal day yet still under as_of. FULL is where the review measured
    it (23 violations), so check both profiles.

    Compared at INSTANT resolution, not date. Transitions are stamped 08:00
    and hold status changes 10:00, so a date-granular comparison silently
    accepts a hold reaching ON_HOLD two hours after its order was CLOSED the
    same day. Seed 1234 happens to be clean of that; seed 7 is not (2
    escapes on FULL), so it is pinned here explicitly."""
    for profile, seed in ((SMOKE, 1234), (FULL, 1234), (FULL, 7)):
        events = generate(SCENARIOS, profile, seed=seed, as_of=AS_OF)
        steps_by_wo = {}
        wo_by_hold = {}
        for e in events:
            if isinstance(e, WorkOrderStatusChanged):
                steps_by_wo.setdefault(e.work_order_id, []).append((e.at, e.to_status))
            elif isinstance(e, HoldOpened):
                wo_by_hold[e.hold_entry_id] = e.work_order_id

        def active_window(work_order_id, steps_by_wo=steps_by_wo):
            steps = sorted(steps_by_wo[work_order_id])
            released_at = next(t for t, status in steps if status == "RELEASED")
            terminal_at, terminal_status = steps[-1]
            window_end_at = terminal_at if terminal_status == "CLOSED" else datetime.combine(AS_OF, time(23, 59, 59))
            return released_at, window_end_at

        opened_checked = 0
        status_checked = 0
        for e in events:
            if isinstance(e, HoldOpened):
                released_at, window_end_at = active_window(e.work_order_id)
                assert (
                    released_at <= e.at <= window_end_at
                ), f"{profile.name}/{seed}: {e.hold_entry_id} opened at {e.at}"
                opened_checked += 1
            elif isinstance(e, HoldStatusChanged):
                released_at, window_end_at = active_window(wo_by_hold[e.hold_entry_id])
                assert (
                    released_at <= e.at <= window_end_at
                ), f"{profile.name}/{seed}: {e.hold_entry_id} -> {e.to_status} at {e.at} exceeds {window_end_at}"
                status_checked += 1
        assert opened_checked, "fixture produced no holds; the assertion above would be vacuous"
        assert status_checked, "fixture produced no hold status changes; the assertion above would be vacuous"


def test_each_client_gets_its_declared_employee_count():
    per_client = {}
    for e in _gen():
        if isinstance(e, EmployeeHired):
            per_client[e.client_id] = per_client.get(e.client_id, 0) + 1
    for scenario in SCENARIOS:
        assert per_client[scenario.client_id] == SMOKE.employees_per_client
