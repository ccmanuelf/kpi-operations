"""Scenario + seed -> ordered event stream. Pure: no database, no clock, no
module-level randomness.

Determinism is the contract. The same (scenarios, profile, seed, as_of)
produces a byte-identical stream, which is what lets the seeded dataset be
asserted against rather than merely eyeballed.
"""

import hashlib
import random
from dataclasses import fields, replace
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Iterable, List, Sequence, Type

from backend.seed.events import (
    ClientCreated,
    EmployeeHired,
    Event,
    HoldOpened,
    HoldStatusChanged,
    LineCommissioned,
    ProductDefined,
    ShiftDefined,
    ShiftWorked,
    UserCreated,
    WorkOrderReceived,
    WorkOrderStatusChanged,
)
from backend.seed.profiles import Profile
from backend.seed.scenarios import ClientScenario, NarrativeWindow

# Mainline work-order lifecycle. Every order walks a prefix of this.
WORK_ORDER_FLOW = ("RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED")

HOLD_FLOW = ("PENDING_HOLD_APPROVAL", "ON_HOLD", "PENDING_RESUME_APPROVAL", "RESUMED")

# Narrative multipliers. "Roughly" per the brief -- these scale the drawn
# baseline rather than replace it, so days inside a window still differ from
# each other instead of collapsing to a constant.
DEFECT_CRISIS_SCALE = 3.0
DOWNTIME_DECLINE_SCALE = 3.0
ATTENDANCE_DISRUPTION_SCALE = 2.0 / 3.0  # "reduce by roughly a third"
HOLD_RATE_BASELINE = 0.15
HOLD_RATE_QUALITY_CRISIS = 0.5


def generate(
    scenarios: Sequence[ClientScenario],
    profile: Profile,
    seed: int,
    as_of: date,
) -> List[Event]:
    rng = random.Random(seed)
    start = as_of - timedelta(days=profile.days)
    events: List[Event] = []
    seq = 0

    def emit(cls: Type[Event], at: datetime, client_id: str, **kw: Any) -> None:
        nonlocal seq
        seq += 1
        events.append(cls(at=at, seq=seq, client_id=client_id, **kw))

    for scenario in scenarios:
        _generate_client(emit, rng, scenario, profile, start, as_of)

    events.sort(key=lambda e: e.order_key)
    # Clamp to the seeded window: a dataset generated "as of" a date must not
    # contain events after it, or a materialized "current status" taken from
    # the newest transition would report a closure or resume that has not
    # happened yet. Truncation is the realistic outcome anyway -- an order
    # received recently is genuinely mid-flow at as_of, which is exactly how
    # orders end up spread across every status. Clamp AFTER the sort and
    # BEFORE seq renumbering, so seq stays contiguous from 1.
    events = [e for e in events if e.at.date() <= as_of]
    # Re-number so seq reflects final stream position: the materializer relies
    # on insertion order, and active_as_of tie-breaks on it within a second.
    return [replace(e, seq=i + 1) for i, e in enumerate(events)]


def stream_digest(events: Iterable[Event]) -> str:
    """Stable hash of a stream, for asserting determinism without comparing
    thousands of objects.

    Uses dataclasses.fields() rather than vars(e): the latter raises
    TypeError the moment any Event gains slots=True.
    """
    h = hashlib.sha256()
    for e in events:
        h.update(f"{type(e).__name__}|{e.at.isoformat()}|{e.seq}|{e.client_id}".encode())
        for f in sorted(fields(e), key=lambda f: f.name):
            if f.name not in ("at", "seq", "client_id"):
                h.update(f"|{f.name}={getattr(e, f.name)}".encode())
    return h.hexdigest()


def _window_bounds(window: NarrativeWindow, as_of: date) -> tuple:
    """A window's calendar bounds, resolved from as_of and its month offsets.
    Offsets are negative -- the EARLIER bound comes from the larger magnitude
    (start_month=-8 is further back than end_month=-6)."""
    earlier = as_of - timedelta(days=abs(window.start_month) * 30)
    later = as_of - timedelta(days=abs(window.end_month) * 30)
    return earlier, later


def _window_active(scenario: ClientScenario, day: date, as_of: date, kind: str) -> bool:
    """Whether one of the scenario's windows of the given kind covers `day`."""
    for window in scenario.narrative:
        if window.kind != kind:
            continue
        earlier, later = _window_bounds(window, as_of)
        if earlier <= day <= later:
            return True
    return False


def _narrative_scale(scenario: ClientScenario, day: date, as_of: date) -> dict:
    """Multipliers applied to the drawn baseline for a client-day. Multiplying
    rather than overriding keeps the day-to-day RNG variation alive inside a
    scripted episode -- setting a constant would make every day identical and
    read as synthetic."""
    scale = {"defects": 1.0, "downtime": 1.0, "attendance": 1.0}
    if _window_active(scenario, day, as_of, "supplier_quality_crisis"):
        scale["defects"] *= DEFECT_CRISIS_SCALE
    if _window_active(scenario, day, as_of, "equipment_reliability_decline"):
        scale["downtime"] *= DOWNTIME_DECLINE_SCALE
    if _window_active(scenario, day, as_of, "labor_disruption"):
        scale["attendance"] *= ATTENDANCE_DISRUPTION_SCALE
    return scale


def _hold_rate(scenario: ClientScenario, opened: date, as_of: date) -> float:
    """Baseline hold probability, raised while a supplier-quality-crisis
    window covers the order's receipt date."""
    if _window_active(scenario, opened, as_of, "supplier_quality_crisis"):
        return HOLD_RATE_QUALITY_CRISIS
    return HOLD_RATE_BASELINE


def _generate_client(
    emit: Callable[..., None],
    rng: random.Random,
    scenario: ClientScenario,
    profile: Profile,
    start: date,
    as_of: date,
) -> None:
    cid = scenario.client_id

    # --- setup, all on the first day, minutes apart so order is unambiguous.
    # A running cursor rather than hardcoded band starts (2 / 10 / 20 / 30):
    # those silently interleaved once a count exceeded its band width (e.g.
    # ShiftDefined's 10 + i colliding with ProductDefined's 20 + i once
    # shifts_per_client > 10). A cursor can't collide regardless of profile
    # size; only the relative order (lines, shifts, products, employees)
    # matters, not the exact minute offsets.
    day0 = datetime.combine(start, time(6, 0))
    emit(ClientCreated, day0, cid, name=scenario.name, pay_model=scenario.pay_model)
    minute_cursor = 1
    emit(
        UserCreated,
        day0 + timedelta(minutes=minute_cursor),
        cid,
        user_id=f"{cid}-USR-001",
        username=f"{cid.lower()}_supervisor",
        role="supervisor",
    )
    minute_cursor += 1

    lines = [f"{cid}-LINE-{i:02d}" for i in range(1, profile.lines_per_client + 1)]
    for i, line_id in enumerate(lines):
        emit(LineCommissioned, day0 + timedelta(minutes=minute_cursor), cid, line_id=line_id, name=f"Line {i + 1}")
        minute_cursor += 1
    # Per-line minute stagger for ShiftWorked below, sized to the actual line
    # count rather than a fixed +1: a fixed step aliases once lines_per_client
    # exceeds the modulus (line 1 and line 61 both landed on :31 under the old
    # `(30 + li) % 60`). Floor division keeps every li * line_minute_step
    # strictly below 60, so distinct lines can never land on the same minute
    # for any lines_per_client a Profile could express.
    line_minute_step = max(1, 60 // len(lines))

    shifts = [f"{cid}-SHIFT-{i:02d}" for i in range(1, profile.shifts_per_client + 1)]
    # Same reasoning as line_minute_step above, for hours: the old fixed
    # `si * 8` step aliased shift 1 with shift 4 (both landed on hour 6) once
    # shifts_per_client reached 4. Sizing the step to the actual shift count
    # keeps every si * shift_hour_step strictly below 24.
    shift_hour_step = max(1, 24 // len(shifts))
    for i, shift_id in enumerate(shifts):
        emit(
            ShiftDefined,
            day0 + timedelta(minutes=minute_cursor),
            cid,
            shift_id=shift_id,
            name=f"Shift {i + 1}",
            # Same formula the ShiftWorked hour below uses (si there == i
            # here, both index the same shifts list): the declared start_hour
            # must not diverge from the hour events are actually stamped at.
            start_hour=(6 + i * shift_hour_step) % 24,
        )
        minute_cursor += 1

    products = [f"{cid}-PROD-{i:02d}" for i in range(1, 4)]
    for i, product_id in enumerate(products):
        emit(
            ProductDefined,
            day0 + timedelta(minutes=minute_cursor),
            cid,
            product_id=product_id,
            style=f"STYLE-{i + 1}",
        )
        minute_cursor += 1

    for i in range(profile.employees_per_client):
        emit(
            EmployeeHired,
            day0 + timedelta(minutes=minute_cursor),
            cid,
            employee_id=f"{cid}-EMP-{i + 1:03d}",
            line_id=lines[i % len(lines)],
        )
        minute_cursor += 1

    # --- daily shift activity, Mon-Fri only
    for offset in range(profile.days):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        scale = _narrative_scale(scenario, day, as_of)
        for li, line_id in enumerate(lines):
            for si, shift_id in enumerate(shifts):
                produced = rng.randint(180, 260)
                defect_rate = rng.uniform(0.01, 0.03) * scale["defects"]
                # shift_hour_step / line_minute_step are sized to this
                # client's actual shift/line counts (see where they're
                # computed above), so distinct si and distinct li can never
                # alias onto the same hour or minute -- collision-free by
                # construction for any (line, shift) pair a Profile could
                # express, not just the <=2-each counts FULL/SMOKE use today.
                shift_hour = (6 + si * shift_hour_step) % 24
                shift_minute = (30 + li * line_minute_step) % 60
                emit(
                    ShiftWorked,
                    datetime.combine(day, time(shift_hour, shift_minute)),
                    cid,
                    line_id=line_id,
                    shift_id=shift_id,
                    units_produced=produced,
                    units_defective=int(produced * defect_rate),
                    downtime_minutes=int(rng.randint(5, 40) * scale["downtime"]),
                    attendance_headcount=max(1, int(profile.employees_per_client / len(lines) * scale["attendance"])),
                )

    # --- work orders spread across the window, each with a real chain
    span = max(1, profile.days - 10)
    for i in range(profile.work_orders_per_client):
        wo = f"{cid}-WO-{i + 1:04d}"
        opened = start + timedelta(days=rng.randrange(span))
        emit(
            WorkOrderReceived,
            datetime.combine(opened, time(7, 0)),
            cid,
            work_order_id=wo,
            product_id=products[i % len(products)],
            planned_quantity=rng.choice([250, 500, 750, 1000]),
        )

        # How far along the flow this order has travelled. Every order emits
        # the opening (from_status=None) row -- the gap that left 60 of 100
        # orders with no chain at all in the old seeder.
        depth = rng.randint(1, len(WORK_ORDER_FLOW))
        prev = None
        when = opened
        transition_days: List[date] = []
        for step in WORK_ORDER_FLOW[:depth]:
            emit(
                WorkOrderStatusChanged,
                datetime.combine(when, time(8, 0)),
                cid,
                work_order_id=wo,
                from_status=prev,
                to_status=step,
            )
            transition_days.append(when)
            prev = step
            # Distinct DAY per transition: same-day steps would collapse the
            # interval this whole project exists to make answerable.
            when = when + timedelta(days=rng.randint(1, 4))

        # A hold can only open once the order has been RELEASED (index 1 of
        # WORK_ORDER_FLOW), and must land before the order's terminal
        # transition -- or before as_of if the chain hasn't reached CLOSED --
        # otherwise a hold could open on an order already CLOSED, or resume
        # before the order progresses. Scheduling it off the bare receipt
        # date, independent of the status chain, was the bug.
        if depth >= 2:
            released_day = transition_days[1]
            terminated = depth == len(WORK_ORDER_FLOW)
            window_end = transition_days[-1] if terminated else as_of
            span_days = (window_end - released_day).days
            # rng.random() is drawn unconditionally *relative to the hold
            # rate* -- once depth >= 2 has gated us into this branch (a
            # structural fact about the order, unrelated to any rate), the
            # draw always happens before _hold_rate is consulted. That's what
            # lets Task 4 vary the rate by narrative window without shifting
            # the draw count between a window with a hold and one without.
            # Do not restructure into `if _hold_rate(...) > 0 and rng.random() < ...`
            # -- that would make the draw count depend on the rate's value.
            draw = rng.random()
            if span_days >= 1 and draw < _hold_rate(scenario, opened, as_of):
                hold_id = f"{cid}-HOLD-{i + 1:04d}"
                hold_day = released_day + timedelta(days=rng.randrange(span_days))
                # Inside a supplier-quality-crisis window, holds should read
                # as caused by that crisis: bias the reason pool toward
                # QUALITY rather than forcing it, so the RNG still varies
                # which holds get QUALITY vs. an unrelated cause. Both
                # branches draw exactly once, so the choice of pool doesn't
                # add or remove a draw relative to the non-crisis path.
                if _window_active(scenario, opened, as_of, "supplier_quality_crisis"):
                    reason_pool = ["QUALITY", "QUALITY", "QUALITY", "MATERIAL", "ENGINEERING"]
                else:
                    reason_pool = ["QUALITY", "MATERIAL", "ENGINEERING"]
                emit(
                    HoldOpened,
                    datetime.combine(hold_day, time(9, 0)),
                    cid,
                    hold_entry_id=hold_id,
                    work_order_id=wo,
                    reason_category=rng.choice(reason_pool),
                )
                prev_h = None
                hwhen = hold_day
                # Bounded by the same window_end the opening used: without this,
                # a status step could land after the order's own terminal
                # transition (order CLOSED, hold still reaching ON_HOLD weeks
                # later). If a step would exceed the bound, stop the chain
                # there rather than piling every remaining step onto the
                # boundary day -- a truncated chain is realistic, a pile-up is
                # not.
                for step in HOLD_FLOW[: rng.randint(1, len(HOLD_FLOW))]:
                    if hwhen > window_end:
                        break
                    emit(
                        HoldStatusChanged,
                        datetime.combine(hwhen, time(10, 0)),
                        cid,
                        hold_entry_id=hold_id,
                        from_status=prev_h,
                        to_status=step,
                    )
                    prev_h = step
                    hwhen = hwhen + timedelta(days=rng.randint(2, 15))
