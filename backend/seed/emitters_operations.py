"""Operations emitters: work orders with their chains, and daily shift
activity.

Paired with writers_operations.py the same way emitters_master.py is paired
with writers_master.py.

Both loops anchor on the setup band's activity_start, and work orders are
emitted FIRST because a shift's inspection names an order that must already
exist in the stream.
"""

import random
from datetime import date, datetime, time, timedelta
from typing import Callable, List, Tuple

from backend.seed.emitters_master import SHIFT_LENGTH_HOURS, ClientSetup
from backend.seed.events import (
    AttendanceRecorded,
    DefectsFound,
    DowntimeLogged,
    HoldOpened,
    HoldStatusChanged,
    JobDefined,
    ProductionRecorded,
    QualityInspected,
    WorkOrderReceived,
    WorkOrderStatusChanged,
)
from backend.seed.narrative import (
    BASELINE_REASONS,
    QUALITY_CRISIS_REASONS,
    downtime_taxonomy,
    hold_rate,
    late_rate,
    narrative_scale,
    narrative_window_touches,
    window_active,
)
from backend.seed.profiles import Profile
from backend.seed.scenarios import (
    ATTRIBUTION_USER_ID,
    DEFECT_CODES,
    IDEAL_CYCLE_TIME_HOURS,
    ROUTING,
    SCRAP_UNITS_PER_HUNDRED,
    WORK_ORDER_ORIGINS,
    ClientScenario,
)

# Mainline work-order lifecycle. Every order walks a prefix of this.
WORK_ORDER_FLOW = ("RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED")

HOLD_FLOW = ("PENDING_HOLD_APPROVAL", "ON_HOLD", "PENDING_RESUME_APPROVAL", "RESUMED")

#: WORK_ORDER.priority is a free String(20); these are the four values the
#: request schema's own pattern accepts (backend/schemas/work_order.py:70).
PRIORITIES = ("LOW", "NORMAL", "HIGH", "URGENT")

#: Absence threshold at scale 1.0: a draw above this marks the employee absent,
#: so the baseline no-show rate is 5%. The narrative lowers the threshold via
#: scale["attendance"], which is why a LOWER scale means MORE absence.
ATTENDANCE_PRESENT_THRESHOLD = 0.95


def job_id_for(work_order_id: str, sequence_number: int) -> str:
    """The routing step's primary key.

    Built from the order id rather than from client id + a counter for two
    reasons. JOB.job_id is VARCHAR(50) and MariaDB's strict sql_mode rejects an
    overflow SQLite silently accepts, so the shortest key that is still unique
    wins: the order id is already unique per run and already carries the client
    (`SAMPLE_REF-WO-0100-OP4` is 22 characters at the widest client id and work
    order index a Profile can express). And the shift emitter has to name the
    SAME id the work-order emitter minted, without the two sharing state -- one
    function both call is what keeps them from drifting into two formats.

    Deliberately NOT the `JOB-{client_id}` shape
    tests/test_seed/_reset_row_builders.py plants: those rows exist to prove
    the --reset sweep reaches a table the seeder did not write, and a seeded
    job colliding with one would turn that proof into a PK error.
    """
    return f"{work_order_id}-OP{sequence_number}"


def operations_completed(depth: int, order_index: int) -> int:
    """How many routing steps an order at `depth` of WORK_ORDER_FLOW has
    finished.

    DERIVED, never drawn. Every value here comes from draws the order has
    already made, so the routing costs the RNG stream nothing: a single new
    `rng` call in this loop would move every subsequent draw for every client
    and shift the FULL-profile narrative pins (aged-and-excluded holds == 14,
    SAMPLE_REF months below 80% OTD == 0) that have nothing to do with jobs.

    An order that never reached IN_PROGRESS has finished nothing; one that
    reached COMPLETED has finished everything; one in between is mid-routing,
    and WHICH step it is on rotates with the order index so a client's orders
    are not all frozen on the same operation.
    """
    if depth >= WORK_ORDER_FLOW.index("COMPLETED") + 1:
        return len(ROUTING)
    if depth >= WORK_ORDER_FLOW.index("IN_PROGRESS") + 1:
        return 1 + order_index % (len(ROUTING) - 1)
    return 0


def emit_work_orders(
    emit: Callable[..., None],
    rng: random.Random,
    scenario: ClientScenario,
    profile: Profile,
    setup: ClientSetup,
    as_of: date,
) -> List[Tuple[date, str]]:
    """Returns (received_day, work_order_id) per order, which emit_shifts uses
    to decide which orders a given day's shifts may name."""
    cid = scenario.client_id
    products = setup.products
    products_by_id = setup.products_by_id
    activity_start = setup.activity_start
    activity_days = setup.activity_days

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
        # Five more draws, taken unconditionally and in a fixed order, for the
        # same reason the hold block below documents at length: how long the
        # customer gave us, where the order came from, how urgent it is, and
        # whether -- if it ships at all -- it ships late.
        lead_days = rng.randint(20, 60)
        origin = WORK_ORDER_ORIGINS[rng.randrange(len(WORK_ORDER_ORIGINS))]
        # ~15% carry no priority: spec section 3 decision 6 excludes those from
        # the priority-adherence denominator and publishes their share as a
        # coverage figure. A dataset where every order has a priority cannot
        # demonstrate that the exclusion works.
        priority_draw = rng.random()
        priority = None if priority_draw < 0.15 else PRIORITIES[int(priority_draw * len(PRIORITIES))]
        # Drawn here, unconditionally, rather than once depth (and therefore
        # whether the order ever reaches SHIPPED) is known: the RNG stream
        # this order consumes must not vary with how far its chain travels or
        # with narrative state. Only the RATE this draw is compared against
        # -- resolved below, once the SHIPPED step is actually reached --
        # depends on the window, the same way hold_rate/reason_pool do for
        # holds. Unused when the order never reaches SHIPPED, same as
        # day_draw/open_draw/reason_draw below are unused when depth < 2.
        lateness_draw = rng.random()
        required_at = datetime.combine(opened + timedelta(days=lead_days), time(17, 0))
        # Overlap of this order's own commitment span (received -> required)
        # against the client's narrative window(s) -- see
        # narrative_window_touches for why a span, not a single day. Draws no
        # RNG, so computing it here (ahead of depth) cannot perturb the stream.
        touches_window = narrative_window_touches(scenario, opened, opened + timedelta(days=lead_days), as_of)
        product_id = products[i % len(products)]
        # Hoisted out of the emit() call below rather than drawn inline: the
        # routing block at the end of this iteration sizes every JOB row off
        # the same quantity, and a second draw for the jobs would both
        # disagree with the order and move the stream. Its position in the
        # draw order is unchanged -- this is the sixth and last draw of the
        # order's own block, exactly where the inline call sat.
        planned_quantity = rng.choice([250, 500, 750, 1000])
        emit(
            WorkOrderReceived,
            datetime.combine(opened, time(7, 0)),
            cid,
            work_order_id=wo,
            product_id=product_id,
            planned_quantity=planned_quantity,
            style_model=products_by_id[product_id].style,
            origin=origin,
            required_date=required_at,
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
            at = datetime.combine(when, time(8, 0))
            # actual_delivery_date is populated on this one step only -- see
            # the field's docstring in events.py. Resolved from lateness_draw,
            # drawn unconditionally above, against required_at: no new RNG
            # consumption happens here, only a read of a value already drawn.
            extra = {}
            if step == "SHIPPED":
                rate = late_rate(touches_window)
                if rate > 0 and lateness_draw < rate:
                    # LATE: how far under the threshold the draw fell spreads
                    # the delay across 1-20 days, so in-window orders do not
                    # all land on the same date.
                    delay = 1 + int((rate - lateness_draw) / rate * 20)
                    delivery = required_at + timedelta(days=delay)
                else:
                    # ON TIME -- including every SAMPLE_REF order, whose rate
                    # is always 0 (LATE_RATE_BASELINE): delivered on or a few
                    # days ahead of the date promised.
                    delivery = required_at - timedelta(days=int(lateness_draw * 5))
                # Never before the order actually shipped, and never after
                # as_of -- a delivery date past as_of would claim something
                # that has not happened yet, the same reasoning generate()'s
                # own clamp applies to the event stream as a whole.
                delivery = max(delivery, at)
                delivery = min(delivery, datetime.combine(as_of, time(20, 0)))
                extra["actual_delivery_date"] = delivery
            emit(
                WorkOrderStatusChanged,
                at,
                cid,
                work_order_id=wo,
                from_status=prev,
                to_status=step,
                **extra,
            )
            transition_days.append(when)
            prev = step
            # Distinct DAY per transition: same-day steps would collapse the
            # interval this whole project exists to make answerable.
            when = when + timedelta(days=rng.randint(1, 4))

        # --- routing: the JOB rows this order is made of.
        #
        # Stamped 07:30, half an hour after the 07:00 receipt and half an hour
        # before the 08:00 first transition, for the same reason every other
        # band is stamped where it is: JOB.work_order_id is a foreign key, so
        # a job must never precede the order it belongs to. (Cross-TABLE order
        # is guaranteed by the metadata topological sort the materializer
        # flushes in; this keeps the STREAM readable, which is what a human
        # debugging it reads.)
        #
        # Emitted here, after the chain, because how far the order travelled is
        # what says how much of the routing is finished -- a job claiming
        # completed units on an order still sitting at RECEIVED is exactly the
        # kind of internal contradiction this rebuild exists to remove.
        job_at = datetime.combine(opened, time(7, 30))
        # Every finished step carries the order's furthest transition day,
        # clamped to as_of. NOT four invented per-step dates: the platform
        # records no per-operation completion anywhere (JOB stores a snapshot,
        # and WORKFLOW_TRANSITION_LOG is per ORDER), so distinct dates would
        # assert a sequencing no other table could corroborate. The as_of clamp
        # is the same one the delivery date takes above -- a completion date
        # past as_of claims something that has not happened yet.
        completion_at = min(
            datetime.combine(transition_days[-1], time(8, 0)),
            datetime.combine(as_of, time(20, 0)),
        )
        done = operations_completed(depth, i)
        product = products_by_id[product_id]
        for seq_no, (op_code, op_name) in enumerate(ROUTING, start=1):
            if seq_no <= done:
                completed = planned_quantity
            elif seq_no == done + 1 and done > 0:
                # The step currently running: half its units through. Only
                # reachable for an order that stopped mid-flow, since `done`
                # is len(ROUTING) once the order reached COMPLETED.
                completed = planned_quantity // 2
            else:
                completed = 0
            scrapped = completed * SCRAP_UNITS_PER_HUNDRED // 100
            # The routing DECOMPOSES the product's labor content, it does not
            # add to it: the four steps' planned_hours sum back to
            # planned_quantity * IDEAL_CYCLE_TIME_HOURS, which is exactly the
            # earned hours the platform's one efficiency formula computes from
            # the same units. A per-step figure invented independently would
            # make a work order's own jobs claim more (or less) labor than the
            # efficiency reading beside them.
            planned_hours = round(planned_quantity * IDEAL_CYCLE_TIME_HOURS / len(ROUTING), 2)
            emit(
                JobDefined,
                job_at,
                cid,
                job_id=job_id_for(wo, seq_no),
                work_order_id=wo,
                operation_code=op_code,
                operation_name=op_name,
                sequence_number=seq_no,
                # Real vocabulary, not invented: the part IS the product this
                # order is for. GET /api/jobs/{job_id}/dpmo looks
                # PART_OPPORTUNITIES up by this value, so a made-up part number
                # would be unmatchable by anything a later task seeds there.
                part_number=product.code,
                part_description=product.name,
                planned_quantity=planned_quantity,
                planned_hours=planned_hours,
                completed_quantity=completed,
                quantity_scrapped=scrapped,
                # Hours claimed at the ideal rate, pro-rated by units finished.
                # Deliberately NOT planned_hours times an invented variance:
                # that would publish a second efficiency number next to the one
                # the platform computes from PRODUCTION_ENTRY, and the two
                # would disagree on every screen that shows both.
                actual_hours=round(planned_hours * completed / planned_quantity, 2),
                is_completed=seq_no <= done,
                completed_date=completion_at if seq_no <= done else None,
            )

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
            # `if hold_rate(...) > 0 and rng.random() < ...` either -- that
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
            in_quality_crisis = window_active(scenario, hold_day, as_of, "supplier_quality_crisis")
            if span_days >= 1 and open_draw < hold_rate(in_quality_crisis):
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

    return received


def emit_shifts(
    emit: Callable[..., None],
    rng: random.Random,
    scenario: ClientScenario,
    profile: Profile,
    setup: ClientSetup,
    received: List[Tuple[date, str]],
    as_of: date,
) -> None:
    cid = scenario.client_id
    lines = setup.lines
    shifts = setup.shifts
    products = setup.products
    employees = setup.employees
    line_minute_step = setup.line_minute_step
    shift_hour_step = setup.shift_hour_step
    activity_start = setup.activity_start
    activity_days = setup.activity_days

    # --- daily shift activity, Mon-Fri only
    for offset in range(max(0, activity_days)):
        day = activity_start + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        scale = narrative_scale(scenario, day, as_of)
        # Orders this day's shifts may name: received on a STRICTLY EARLIER
        # day. A shift is stamped at its own start hour -- 06:30 for shift 0,
        # and as early as 00:30 once the modular hour step wraps -- while a
        # receipt is stamped 07:00, so "received on or before today" would put
        # the shift ahead of the order it names.
        #
        # NOT "open" orders: no status is consulted here, so the list includes
        # orders long since CLOSED or SHIPPED. The name says what the filter
        # actually is -- received earlier -- rather than implying a lifecycle
        # check the generator does not make.
        orders_received_earlier = [wo for received_day, wo in received if received_day < day]
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

                # The order this shift is running. Production and the
                # inspection below must name the SAME one: PRODUCTION_ENTRY
                # and QUALITY_ENTRY are joined back to WORK_ORDER
                # independently (crud/analytics.py, calculations/otd.py,
                # services/plan_vs_actual_service.py, routes/my_shift.py), so
                # two different orders on one shift make those views disagree
                # about what was being run. Derived from the same index
                # arithmetic the inspection used before, so no RNG draw is
                # added and the stream's consumption is unchanged. None only
                # while no order has been received yet -- the column is
                # nullable and inventing an id would be worse.
                shift_order = (
                    orders_received_earlier[(li + si + offset) % len(orders_received_earlier)]
                    if orders_received_earlier
                    else None
                )
                # The routing step that order was on this shift. Five of the
                # six GET /api/jobs/{job_id}/* routes read PRODUCTION_ENTRY and
                # QUALITY_ENTRY by job_id and NEVER by work_order_id, so an
                # entry carrying only the order reaches none of them: seeding
                # JOB without stamping this column would unblock the routes and
                # leave every one of them answering "no entries found".
                #
                # Same (li + si + offset) rotation the order pick uses, so it
                # costs no RNG draw, and production and the inspection below
                # name the SAME step for the same reason they name the same
                # order -- /kpi-summary unions the two, and a shift whose
                # output and inspection sat on different operations would make
                # that one endpoint contradict itself.
                shift_job = (
                    job_id_for(shift_order, 1 + (li + si + offset) % len(ROUTING)) if shift_order is not None else None
                )

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
                    work_order_id=shift_order,
                    job_id=shift_job,
                    shift_date=shift_date,
                    units_produced=produced,
                    run_time_hours=run_time,
                    scrap_count=scrap,
                    employees_assigned=max(1, present),
                    entered_by=ATTRIBUTION_USER_ID,
                )

                # --- downtime, root cause first: the narrative biases the
                # CAUSE and the reason follows from it, so the two can never
                # disagree in the Q2 view. The pool and the reason map come
                # back together from one call, because an equipment-reliability
                # decline has to change both -- see downtime_taxonomy().
                pool, reason_by_root_cause = downtime_taxonomy(scenario, day, as_of)
                root_cause = pool[int(root_cause_draw * len(pool))]
                emit(
                    DowntimeLogged,
                    at,
                    cid,
                    line_id=line_id,
                    shift_id=shift_id,
                    shift_date=shift_date,
                    downtime_reason=reason_by_root_cause[root_cause],
                    root_cause_category=root_cause,
                    downtime_minutes=downtime_minutes,
                )

                # --- quality, against the order this shift is running. If
                # nothing has been received yet there is simply no inspection
                # that day -- do NOT fabricate an order id to keep the shape
                # regular.
                if shift_order is not None:
                    qe_id = f"{cid}-QE-{day.isoformat()}-{li}-{si}"
                    emit(
                        QualityInspected,
                        at,
                        cid,
                        quality_entry_id=qe_id,
                        work_order_id=shift_order,
                        job_id=shift_job,
                        shift_date=shift_date,
                        units_inspected=produced,
                        units_passed=produced - defective,
                        units_defective=defective,
                        total_defects_count=defective,
                    )
                    # Split across defect codes, halving what is left each
                    # time and giving the remainder to the LAST row, so the
                    # rows always sum back to total_defects_count: DHU comes
                    # from QUALITY_ENTRY and the Pareto from DEFECT_DETAIL,
                    # and a demo where the two disagree is worse than one
                    # with no breakdown at all.
                    #
                    # `continue`, never `break`, when a row's share rounds to
                    # zero. `break` left the loop before the row that owes the
                    # remainder: at defective == 1 the non-last row draws
                    # 1 // 2 == 0 and the whole inspection emitted NO detail
                    # rows while still claiming one defect -- 28 of 4104
                    # entries on FULL/1234. Skipping the empty row and letting
                    # the last one carry what is left conserves the total for
                    # every (defective, rows) pair, including 0, where nothing
                    # is emitted and nothing is owed.
                    #
                    # The code index folds in the DAY. Without it every index
                    # was (li + si + k) with all three in {0, 1}, which reaches
                    # 0..3 of a 5-entry tuple and left STITCH structurally
                    # unreachable -- a dead DEFECT_TYPE_CATALOG row, and
                    # pointedly the one code the live dataset this rebuild
                    # replaces had used for all 80 of its rows. `offset` is the
                    # day index, not a draw, so the rotation costs no
                    # randomness and cannot vary with the narrative.
                    remaining = defective
                    for k in range(profile.defect_rows_per_inspection):
                        last = k == profile.defect_rows_per_inspection - 1
                        count = remaining if last else remaining // 2
                        if count <= 0:
                            continue
                        remaining -= count
                        emit(
                            DefectsFound,
                            at,
                            cid,
                            quality_entry_id=qe_id,
                            defect_code=DEFECT_CODES[(li + si + k + offset) % len(DEFECT_CODES)],
                            defect_count=count,
                        )
