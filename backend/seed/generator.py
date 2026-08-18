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
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple, Type

from backend.seed.events import (
    PLATFORM_CLIENT_ID,
    AttendanceRecorded,
    ClientAccessGranted,
    ClientConfigured,
    ClientCreated,
    DefectsFound,
    DefectTypeDefined,
    DowntimeLogged,
    EmployeeHired,
    Event,
    HoldOpened,
    HoldReasonDefined,
    HoldStatusChanged,
    HoldStatusDefined,
    LineCommissioned,
    ProductDefined,
    ProductionRecorded,
    QualityInspected,
    ShiftDefined,
    ThresholdSet,
    UserCreated,
    WorkOrderReceived,
    WorkOrderStatusChanged,
)
from backend.seed.profiles import Profile
from backend.seed.scenarios import (
    DEFECT_CATALOG,
    DEFECT_CODES,
    DEMO_PASSWORD,
    HOLD_REASONS,
    HOLD_STATUSES,
    LINE_TYPE,
    REASON_BY_ROOT_CAUSE,
    SUPERVISOR_USER_ID,
    THRESHOLDS,
    UNIT_OF_MEASURE,
    USERS,
    WORK_ORDER_ORIGINS,
    ClientScenario,
    NarrativeWindow,
    ProductSpec,
)

# Mainline work-order lifecycle. Every order walks a prefix of this.
WORK_ORDER_FLOW = ("RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED")

HOLD_FLOW = ("PENDING_HOLD_APPROVAL", "ON_HOLD", "PENDING_RESUME_APPROVAL", "RESUMED")

#: WORK_ORDER.priority is a free String(20); these are the four values the
#: request schema's own pattern accepts (backend/schemas/work_order.py:70).
PRIORITIES = ("LOW", "NORMAL", "HIGH", "URGENT")

#: CLIENT_CONFIG.otd_mode. STANDARD is the application's own default
#: (backend/schemas/client_config.py), so a seeded config says exactly what the
#: app would have written for itself rather than a mode nothing else picks.
OTD_MODE = "STANDARD"

#: Declared shift length, used only to derive SHIFT.end_hour from start_hour.
SHIFT_LENGTH_HOURS = 8

# Narrative multipliers. "Roughly" per the brief -- these scale the drawn
# baseline rather than replace it, so days inside a window still differ from
# each other instead of collapsing to a constant.
DEFECT_CRISIS_SCALE = 3.0
DOWNTIME_DECLINE_SCALE = 3.0
ATTENDANCE_DISRUPTION_SCALE = 2.0 / 3.0  # "reduce by roughly a third"
HOLD_RATE_BASELINE = 0.15
HOLD_RATE_QUALITY_CRISIS = 0.5

#: Absence threshold at scale 1.0: a draw above this marks the employee absent,
#: so the baseline no-show rate is 5%. The narrative lowers the threshold via
#: scale["attendance"], which is why a LOWER scale means MORE absence.
ATTENDANCE_PRESENT_THRESHOLD = 0.95

# Reason pools for a hold. The crisis pool is the baseline with QUALITY
# weighted up, not replaced -- a crisis makes quality holds dominant, it does
# not make every other cause vanish.
BASELINE_REASONS = ("QUALITY", "MATERIAL", "ENGINEERING")
QUALITY_CRISIS_REASONS = ("QUALITY", "QUALITY", "QUALITY", "MATERIAL", "ENGINEERING")

# Root-cause pools for downtime, weighted the same way and for the same reason.
EQUIPMENT_DECLINE_CAUSES = ("machine", "machine", "machine", "machine", "materials", "other")
SCHEDULING_PRESSURE_CAUSES = ("scheduling", "scheduling", "machine", "materials", "other")
BASELINE_CAUSES = ("attendance", "machine", "materials", "other", "scheduling")


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

    _generate_platform(emit, start)

    for scenario in scenarios:
        # KPI_THRESHOLD has no client column -- the targets are global -- so
        # they ride under the FIRST scenario's client rather than being emitted
        # once per client and writing four copies of each.
        _generate_client(emit, rng, scenario, profile, start, as_of, is_first=scenario is scenarios[0])

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
                # repr() escapes special characters to prevent separator-injection
                # collisions where | or = in a field value could imitate a boundary.
                value = repr(getattr(e, f.name))
                h.update(f"|{f.name}={value}".encode())
        h.update(b"\n")  # Record terminator to separate events
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


def _hold_rate(in_quality_crisis: bool) -> float:
    """Baseline hold probability, raised while a supplier-quality-crisis
    window covers the date the HOLD would fall on -- not the date its order
    was received. A hold is caused by conditions at the moment it is placed;
    keying on receipt spread the elevation across the whole year and left the
    crisis window statistically indistinguishable."""
    return HOLD_RATE_QUALITY_CRISIS if in_quality_crisis else HOLD_RATE_BASELINE


def _root_cause_pool(scenario: ClientScenario, day: date, as_of: date) -> Tuple[str, ...]:
    """Which root causes are plausible on this client-day. Biasing the pool
    rather than forcing a value keeps the RNG varying which shifts get which
    cause, so a window reads as a shift in the MIX rather than a block of
    identical rows."""
    if _window_active(scenario, day, as_of, "equipment_reliability_decline"):
        return EQUIPMENT_DECLINE_CAUSES
    if _window_active(scenario, day, as_of, "labor_disruption"):
        return SCHEDULING_PRESSURE_CAUSES
    return BASELINE_CAUSES


def _generate_platform(emit: Callable[..., None], start: date) -> None:
    """Users are global. They are emitted BEFORE the per-client loop and
    stamped a day earlier than the earliest client's setup, so every
    ClientAccessGranted and every `entered_by` reference resolves to a user
    already in the stream.

    The grants themselves cannot share that day. A grant names a user AND a
    client, and no client exists until the setup band opens at 06:00 on
    `start` -- stamping them beside the users would put a
    USER_CLIENT_ASSIGNMENT ahead of its own CLIENT row and the materializer,
    inserting in stream order, would hit the FK. So they are stamped one
    minute INTO that band: after every ClientCreated (all clients share the
    06:00 instant), before anything that could depend on a user's scope.
    """
    platform_at = datetime.combine(start - timedelta(days=1), time(6, 0))
    for i, spec in enumerate(USERS):
        emit(
            UserCreated,
            platform_at + timedelta(minutes=i),
            PLATFORM_CLIENT_ID,
            user_id=spec.user_id,
            username=spec.username,
            role=spec.role,
            email=f"{spec.username}@example.invalid",
            full_name=spec.full_name,
            password=DEMO_PASSWORD,
        )
    grant_at = datetime.combine(start, time(6, 0))
    grant_cursor = 1
    for spec in USERS:
        for cid in spec.client_ids:
            emit(
                ClientAccessGranted,
                grant_at + timedelta(minutes=grant_cursor),
                cid,
                user_id=spec.user_id,
                is_primary=cid == spec.client_ids[0],
            )
            grant_cursor += 1


def _generate_client(
    emit: Callable[..., None],
    rng: random.Random,
    scenario: ClientScenario,
    profile: Profile,
    start: date,
    as_of: date,
    is_first: bool,
) -> None:
    cid = scenario.client_id

    # --- setup, all on the first day, minutes apart so order is unambiguous.
    # A running cursor rather than hardcoded band starts (2 / 10 / 20 / 30):
    # those silently interleaved once a count exceeded its band width (e.g.
    # ShiftDefined's 10 + i colliding with ProductDefined's 20 + i once
    # shifts_per_client > 10). A cursor can't collide regardless of profile
    # size; only the relative order (catalogs, lines, shifts, products,
    # employees) matters, not the exact minute offsets. `setup()` owns both
    # the stamp and the increment so no emission can forget to advance it.
    day0 = datetime.combine(start, time(6, 0))
    emit(
        ClientCreated,
        day0,
        cid,
        name=scenario.name,
        pay_model=scenario.pay_model,
        client_type=scenario.client_type,
    )
    minute_cursor = 1

    def setup(cls: Type[Event], **kw: Any) -> None:
        nonlocal minute_cursor
        emit(cls, day0 + timedelta(minutes=minute_cursor), cid, **kw)
        minute_cursor += 1

    setup(ClientConfigured, otd_mode=OTD_MODE)

    # Catalogs before the entities that quote them: a hold reason, a hold
    # status and a defect code are all foreign keys in the target schema, so a
    # HoldOpened or a DefectsFound must never be the first mention of one.
    for reason_code, reason_name, reason_default in HOLD_REASONS:
        setup(HoldReasonDefined, reason_code=reason_code, display_name=reason_name, is_default=reason_default)
    for status_code, status_name, status_default in HOLD_STATUSES:
        setup(HoldStatusDefined, status_code=status_code, display_name=status_name, is_default=status_default)
    for defect_code, defect_name, defect_category, defect_severity in DEFECT_CATALOG:
        setup(
            DefectTypeDefined,
            defect_type_id=f"{cid}-DT-{defect_code}",
            defect_code=defect_code,
            defect_name=defect_name,
            category=defect_category,
            severity=defect_severity,
        )

    lines = [f"{cid}-LINE-{i:02d}" for i in range(1, profile.lines_per_client + 1)]
    for i, line_id in enumerate(lines):
        setup(
            LineCommissioned,
            line_id=line_id,
            name=f"Line {i + 1}",
            line_code=f"LINE-{i + 1:02d}",
            line_type=LINE_TYPE,
        )
    # Per-line minute stagger for the shift events below, sized to the actual
    # line count rather than a fixed +1: a fixed step aliases once
    # lines_per_client exceeds the modulus (line 1 and line 61 both landed on
    # :31 under the old `(30 + li) % 60`). Floor division keeps every
    # li * line_minute_step strictly below 60, so distinct lines can never land
    # on the same minute for any lines_per_client a Profile could express.
    line_minute_step = max(1, 60 // len(lines))

    shifts = [f"{cid}-SHIFT-{i:02d}" for i in range(1, profile.shifts_per_client + 1)]
    # Same reasoning as line_minute_step above, for hours: the old fixed
    # `si * 8` step aliased shift 1 with shift 4 (both landed on hour 6) once
    # shifts_per_client reached 4. Sizing the step to the actual shift count
    # keeps every si * shift_hour_step strictly below 24.
    shift_hour_step = max(1, 24 // len(shifts))
    for i, shift_id in enumerate(shifts):
        # Same formula the shift-activity hour below uses (si there == i here,
        # both index the same shifts list): the declared start_hour must not
        # diverge from the hour events are actually stamped at.
        start_hour = (6 + i * shift_hour_step) % 24
        setup(
            ShiftDefined,
            shift_id=shift_id,
            name=f"Shift {i + 1}",
            start_hour=start_hour,
            end_hour=(start_hour + SHIFT_LENGTH_HOURS) % 24,
        )

    products = [f"{cid}-PROD-{i:02d}" for i in range(1, len(scenario.products) + 1)]
    # Retained, not just emitted: WorkOrderReceived.style_model is the ordered
    # product's own style, so the loop below has to be able to look the spec
    # back up from the id it stamps on the order.
    products_by_id: Dict[str, ProductSpec] = dict(zip(products, scenario.products))
    for product_id, product in zip(products, scenario.products):
        setup(
            ProductDefined,
            product_id=product_id,
            style=product.style,
            product_code=product.code,
            product_name=product.name,
            unit_of_measure=UNIT_OF_MEASURE,
        )

    # Retained for the same kind of reason: attendance is one row per employee
    # ON THIS LINE, so the shift loop needs the roster, not just the count.
    employees: List[Tuple[str, str]] = []
    for i in range(profile.employees_per_client):
        employee_id = f"{cid}-EMP-{i + 1:03d}"
        employee_line = lines[i % len(lines)]
        employees.append((employee_id, employee_line))
        setup(
            EmployeeHired,
            employee_id=employee_id,
            line_id=employee_line,
            # EMPLOYEE.employee_code is unique across the whole table, not per
            # client, so the code carries the client prefix.
            employee_code=employee_id,
            employee_name=f"Operator {i + 1}",
            is_floating_pool=False,
        )

    if is_first:
        for kpi_key, target_value in THRESHOLDS:
            setup(
                ThresholdSet,
                threshold_id=f"THR-{kpi_key.upper()}",
                kpi_key=kpi_key,
                target_value=target_value,
            )

    # --- Setup is finished. Everything below references entities created
    # above, so it must be stamped strictly later than ALL of them.
    #
    # Hour/minute arithmetic alone cannot guarantee that: the shift-hour and
    # line-minute steps are modular, so some (line, shift) index always wraps
    # back toward 00:00 -- at 2 lines `(30 + 1*30) % 60` is minute 0, and at 4
    # shifts `(6 + 3*6) % 24` is hour 0, both of which land BEFORE the 06:00
    # setup block on the same calendar day. The setup cursor can also grow past
    # 07:00 (and past midnight) once a profile declares enough entities,
    # colliding with the fixed 07:00 WorkOrderReceived instant.
    #
    # Bands, not arithmetic, are the fix: setup owns whole calendar days, and
    # all activity starts on the day AFTER the last setup instant. No
    # (lines, shifts, employees, products) a Profile can express can then place
    # an activity event before the entity it references, because the day
    # boundary dominates every hour and minute offset.
    setup_end = day0 + timedelta(minutes=minute_cursor - 1)
    activity_start = setup_end.date() + timedelta(days=1)
    activity_days = (as_of - activity_start).days

    # --- work orders spread across the window, each with a real chain.
    # Anchored on activity_start for the same reason the shift loop is: a
    # WorkOrderReceived is stamped 07:00, which the setup cursor reaches once
    # a client declares ~54 entities, and a work order must never precede the
    # ProductDefined it references.
    #
    # Generated BEFORE the daily shift loop, which is the reverse of the
    # original order: a QualityInspected names the work order it inspected, so
    # the shift loop needs the receipts to already exist. Nothing moves in
    # time -- both loops anchor on activity_start, and generate() sorts the
    # whole stream on order_key and renumbers seq afterwards.
    span = max(1, activity_days - 10)
    received: List[Tuple[date, str]] = []
    for i in range(profile.work_orders_per_client):
        wo = f"{cid}-WO-{i + 1:04d}"
        opened = activity_start + timedelta(days=rng.randrange(span))
        # Four more draws, taken unconditionally and in a fixed order, for the
        # same reason the hold block below documents at length: how long the
        # customer gave us, where the order came from, and how urgent it is.
        lead_days = rng.randint(20, 60)
        origin = WORK_ORDER_ORIGINS[rng.randrange(len(WORK_ORDER_ORIGINS))]
        # ~15% carry no priority: spec section 3 decision 6 excludes those from
        # the priority-adherence denominator and publishes their share as a
        # coverage figure. A dataset where every order has a priority cannot
        # demonstrate that the exclusion works.
        priority_draw = rng.random()
        priority = None if priority_draw < 0.15 else PRIORITIES[int(priority_draw * len(PRIORITIES))]
        product_id = products[i % len(products)]
        emit(
            WorkOrderReceived,
            datetime.combine(opened, time(7, 0)),
            cid,
            work_order_id=wo,
            product_id=product_id,
            planned_quantity=rng.choice([250, 500, 750, 1000]),
            style_model=products_by_id[product_id].style,
            origin=origin,
            required_date=datetime.combine(opened + timedelta(days=lead_days), time(17, 0)),
            priority=priority,
        )
        received.append((opened, wo))

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
            # The bound has to be an INSTANT, not a date. Transitions are
            # stamped 08:00 and hold status changes 10:00, so a date-granular
            # `hwhen > window_end` lets a hold reach ON_HOLD two hours after
            # its order was CLOSED on the same day -- 2 such escapes at
            # FULL/seed=7, invisible at seed 1234.
            window_end_at = (
                datetime.combine(window_end, time(8, 0))
                if terminated
                else datetime.combine(window_end, time(23, 59, 59))
            )
            # Three draws, taken unconditionally and in a fixed order before
            # any narrative state is consulted: WHEN a hold would fall, WHETHER
            # it opens, and WHICH reason it carries. Drawing all three up front
            # is what lets the narrative vary the rate and the reason pool
            # without changing how much of the RNG stream this order consumes.
            #
            # `rng.random()` rather than `rng.randrange`/`rng.choice` for the
            # day and reason: randrange(0) raises, and choice() consumes a
            # variable number of bits via _randbelow's rejection sampling, so
            # picking between a 3-entry and a 5-entry pool with choice() would
            # itself perturb the stream. Do not restructure into
            # `if _hold_rate(...) > 0 and rng.random() < ...` either -- that
            # would make the draw count depend on the rate's value.
            day_draw = rng.random()
            open_draw = rng.random()
            reason_draw = rng.random()
            # The hold's OWN date, not the order's receipt date, is what the
            # narrative keys on below. Receipt-keying was the defect: receipts
            # are uniform over the year but a hold lands anywhere in an active
            # window up to ~350 days wide, so at FULL/1234 only 1 of DEMO-PIECE's
            # 17 holds actually fell inside the crisis window it was supposedly
            # caused by, and every QUALITY-biased hold landed outside it.
            hold_day = released_day + timedelta(days=int(day_draw * span_days)) if span_days >= 1 else released_day
            in_quality_crisis = _window_active(scenario, hold_day, as_of, "supplier_quality_crisis")
            if span_days >= 1 and open_draw < _hold_rate(in_quality_crisis):
                hold_id = f"{cid}-HOLD-{i + 1:04d}"
                # Inside a supplier-quality-crisis window, holds should read
                # as caused by that crisis: bias the reason pool toward
                # QUALITY rather than forcing it, so the RNG still varies
                # which holds get QUALITY vs. an unrelated cause.
                reason_pool = QUALITY_CRISIS_REASONS if in_quality_crisis else BASELINE_REASONS
                emit(
                    HoldOpened,
                    datetime.combine(hold_day, time(9, 0)),
                    cid,
                    hold_entry_id=hold_id,
                    work_order_id=wo,
                    reason_category=reason_pool[int(reason_draw * len(reason_pool))],
                )
                prev_h = None
                hwhen_at = datetime.combine(hold_day, time(10, 0))
                # Bounded by the same window_end_at the opening used: without
                # this, a status step could land after the order's own terminal
                # transition (order CLOSED, hold still reaching ON_HOLD weeks
                # later). If a step would exceed the bound, stop the chain
                # there rather than piling every remaining step onto the
                # boundary day -- a truncated chain is realistic, a pile-up is
                # not.
                for step in HOLD_FLOW[: rng.randint(1, len(HOLD_FLOW))]:
                    if hwhen_at > window_end_at:
                        break
                    emit(
                        HoldStatusChanged,
                        hwhen_at,
                        cid,
                        hold_entry_id=hold_id,
                        from_status=prev_h,
                        to_status=step,
                    )
                    prev_h = step
                    hwhen_at = hwhen_at + timedelta(days=rng.randint(2, 15))

    # --- daily shift activity, Mon-Fri only
    for offset in range(max(0, activity_days)):
        day = activity_start + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        scale = _narrative_scale(scenario, day, as_of)
        # Orders an inspection may name today: received on a STRICTLY EARLIER
        # day. A shift is stamped at its own start hour -- 06:30 for shift 0,
        # and as early as 00:30 once the modular hour step wraps -- while a
        # receipt is stamped 07:00, so "received on or before today" would put
        # the inspection ahead of the order it inspects.
        open_orders = [wo for received_day, wo in received if received_day < day]
        for li, line_id in enumerate(lines):
            for si, shift_id in enumerate(shifts):
                # Draws taken unconditionally and in a fixed order, before any
                # narrative state is consulted: a draw whose existence or count
                # depends on a window being active would make the stream's RNG
                # consumption vary with the calendar, and no two profiles would
                # be comparable. Same rule the hold block above documents.
                #
                # Attendance in particular is a DRAWN baseline, not a computed
                # one. It used to be int(employees / lines * scale), which
                # draws no RNG at all and produced Counter({4: 4004, 2: 172})
                # across the whole year -- one value everywhere and zero
                # variance inside DEMO-HYBRID's labor-disruption window, which
                # is that client's headline observable. One draw per employee
                # the CLIENT declares (not per employee on this line), so the
                # count is fixed by the profile and cannot move with a line's
                # roster; the loop below consumes the prefix it needs.
                produced = rng.randint(180, 260)
                defect_rate = rng.uniform(0.01, 0.03) * scale["defects"]
                downtime_minutes = int(rng.randint(5, 40) * scale["downtime"])
                root_cause_draw = rng.random()
                run_time = round(rng.uniform(6.5, 7.8), 2)
                attendance_draws = [rng.random() for _ in range(profile.employees_per_client)]

                # shift_hour_step / line_minute_step are sized to this
                # client's actual shift/line counts (see where they're
                # computed above), so distinct si and distinct li can never
                # alias onto the same hour or minute -- collision-free by
                # construction for any (line, shift) pair a Profile could
                # express, not just the <=2-each counts FULL/SMOKE use today.
                shift_hour = (6 + si * shift_hour_step) % 24
                shift_minute = (30 + li * line_minute_step) % 60
                at = datetime.combine(day, time(shift_hour, shift_minute))
                # shift_date is the SHIFT's own instant, stamped at its start
                # hour -- never midnight. A midnight shift_date sits on a
                # half-open range boundary and same-day queries return zero
                # (the date-boundary bug class fixed in #146).
                shift_date = datetime.combine(day, time(shift_hour, 0))

                defective = int(produced * defect_rate)
                scrap = defective // 3

                # --- attendance, one row per employee on this line
                crew = [employee_id for employee_id, employee_line in employees if employee_line == line_id]
                present = 0
                for ei, employee_id in enumerate(crew):
                    # A lower scale["attendance"] means MORE absence: the
                    # labor-disruption window reduces effective headcount.
                    is_absent = attendance_draws[ei] > scale["attendance"] * ATTENDANCE_PRESENT_THRESHOLD
                    present += 0 if is_absent else 1
                    emit(
                        AttendanceRecorded,
                        at,
                        cid,
                        employee_id=employee_id,
                        line_id=line_id,
                        shift_id=shift_id,
                        shift_date=shift_date,
                        scheduled_hours=float(SHIFT_LENGTH_HOURS),
                        hours_worked=0.0 if is_absent else float(SHIFT_LENGTH_HOURS),
                        is_absent=is_absent,
                    )

                # --- production
                emit(
                    ProductionRecorded,
                    at,
                    cid,
                    production_entry_id=f"{cid}-PE-{day.isoformat()}-{li}-{si}",
                    line_id=line_id,
                    shift_id=shift_id,
                    product_id=products[(li + si) % len(products)],
                    work_order_id=None,
                    shift_date=shift_date,
                    units_produced=produced,
                    run_time_hours=run_time,
                    scrap_count=scrap,
                    employees_assigned=max(1, present),
                    entered_by=SUPERVISOR_USER_ID,
                )

                # --- downtime, root cause first: the narrative biases the
                # CAUSE and the reason follows from it, so the two can never
                # disagree in the Q2 view.
                pool = _root_cause_pool(scenario, day, as_of)
                root_cause = pool[int(root_cause_draw * len(pool))]
                emit(
                    DowntimeLogged,
                    at,
                    cid,
                    line_id=line_id,
                    shift_id=shift_id,
                    shift_date=shift_date,
                    downtime_reason=REASON_BY_ROOT_CAUSE[root_cause],
                    root_cause_category=root_cause,
                    downtime_minutes=downtime_minutes,
                )

                # --- quality, against a real order. If nothing has been
                # received yet there is simply no inspection that day -- do
                # NOT fabricate an order id to keep the shape regular.
                if open_orders:
                    qe_id = f"{cid}-QE-{day.isoformat()}-{li}-{si}"
                    emit(
                        QualityInspected,
                        at,
                        cid,
                        quality_entry_id=qe_id,
                        work_order_id=open_orders[(li + si + offset) % len(open_orders)],
                        shift_date=shift_date,
                        units_inspected=produced,
                        units_passed=produced - defective,
                        units_defective=defective,
                        total_defects_count=defective,
                    )
                    # Split across defect codes, halving what is left each
                    # time and giving the remainder to the last row, so the
                    # rows always sum back to total_defects_count: DHU comes
                    # from QUALITY_ENTRY and the Pareto from DEFECT_DETAIL,
                    # and a demo where the two disagree is worse than one
                    # with no breakdown at all.
                    remaining = defective
                    for k in range(profile.defect_rows_per_inspection):
                        last = k == profile.defect_rows_per_inspection - 1
                        count = remaining if last else remaining // 2
                        if count <= 0:
                            break
                        remaining -= count
                        emit(
                            DefectsFound,
                            at,
                            cid,
                            quality_entry_id=qe_id,
                            defect_code=DEFECT_CODES[(li + si + k) % len(DEFECT_CODES)],
                            defect_count=count,
                        )
