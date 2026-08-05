"""
Work-order / hold / daily-Operations-data builders for the demo-client seeder.

No behavior change from the pre-split version — this is a pure move.
"""

from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from backend.orm.delay_taxonomy import DelayClassificationEnum, JustifiedDelayReasonEnum
from backend.orm.downtime_taxonomy import DEFAULT_CATEGORY_BY_REASON, DowntimeCategoryEnum, DowntimeReasonEnum
from backend.orm.labor_taxonomy import HourCategoryEnum, LaborClassEnum
from backend.scripts._seed_common import ClientSpec, rng_for
from backend.scripts._seed_master import seed_employees, seed_lines, seed_products, seed_shifts

if TYPE_CHECKING:
    from backend.orm import WorkOrderStatus


def _production_target_fraction(status: "WorkOrderStatus") -> float:
    """Status-derived fraction of planned_quantity a WO should have produced
    (the plan-vs-actual true-up target). Terminal/shipped statuses are "done";
    in-flight statuses are partially complete; not-yet-started/cancelled WOs
    are zero. Shared by seed_work_orders (CapacityOrder alignment) and
    seed_daily_data (production distribution) so both land on the same number."""
    from backend.orm import WorkOrderStatus as S

    return {
        S.SHIPPED: 1.0,
        S.CLOSED: 1.0,
        S.COMPLETED: 1.0,
        S.IN_PROGRESS: 0.5,
        S.ON_HOLD: 0.3,
    }.get(status, 0.0)


# The delivered-history batch's late subset always contains exactly this many
# justified rows per client (late_ct in {0, 3} out of HISTORY_N=15's 5 late
# rows — see the `late_ct % 3` pattern below). Callers that seed multiple
# clients in one run (seed_client / main()) use this to space each client's
# `justified_reason_offset` so the union of justified reasons across clients
# covers all 6 JustifiedDelayReasonEnum members without overlap or gaps —
# e.g. offsets 0, 2, 4 for 3 clients cover reason indices 0-5 exactly once.
JUSTIFIED_REASONS_PER_CLIENT = 2


def seed_work_orders(
    session: Session, spec: ClientSpec, entered_by: str, anchor: date, justified_reason_offset: int = 0
) -> list:
    """Idempotent per-client work orders spanning every WorkOrderStatus, each
    with a credible WorkflowTransitionLog chain, status-coherent milestone
    dates, and (for mainline RELEASED..CLOSED statuses) a bridge to a seeded
    CapacityOrder — plus a few Jobs.

    `justified_reason_offset` starts this client's justified-reason rotation
    at that index into JustifiedDelayReasonEnum (mod 6) instead of 0, so a
    caller seeding several clients in one run can make each client's 2
    justified rows land on different reasons — see JUSTIFIED_REASONS_PER_CLIENT.
    """
    from datetime import datetime, timedelta, timezone
    from backend.orm import WorkOrder, WorkOrderStatus
    from backend.orm.capacity import CapacityOrder, OrderStatus
    from backend.db.factories import TestDataFactory

    cid = spec.client_id
    existing = session.query(WorkOrder).filter_by(client_id=cid).all()
    if existing:
        return existing

    states = [
        WorkOrderStatus.RECEIVED,
        WorkOrderStatus.RELEASED,
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.COMPLETED,
        WorkOrderStatus.SHIPPED,
        WorkOrderStatus.CLOSED,
        WorkOrderStatus.CANCELLED,
        WorkOrderStatus.ON_HOLD,
        WorkOrderStatus.DEMOTED,
        WorkOrderStatus.REJECTED,
    ]
    # Statuses in the linear RELEASED..CLOSED range get bridged to a
    # CapacityOrder (origin=CAPACITY_PLAN); RECEIVED (not yet released),
    # CANCELLED, and ON_HOLD (branches off the linear chain) stay AD_HOC.
    mainline_bridge_statuses = (
        WorkOrderStatus.RELEASED,
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.COMPLETED,
        WorkOrderStatus.SHIPPED,
        WorkOrderStatus.CLOSED,
    )
    cap_orders = session.query(CapacityOrder).filter_by(client_id=cid).order_by(CapacityOrder.id).all()
    bridge_idx = 0
    rng = rng_for(cid, "work_orders")
    now = datetime.combine(anchor, datetime.min.time(), tzinfo=timezone.utc)
    wos = []
    for i, status in enumerate(states, start=1):
        wo_id = f"WO-{cid}-{i:03d}"  # full client_id — work_order_id PK is GLOBALLY unique
        planned_ship = now - timedelta(days=rng.randint(5, 40))
        # delivered on time for terminal states so OTD computes both hit/miss.
        # Clamp to `now` (the anchor) — the +6 upper bound on the offset can
        # otherwise land in the future when planned_ship is only ~5 days old,
        # producing a "shipped in the future" row that leaks the seeded
        # window's true max date past the anchor (ISSUE-009). Lateness
        # (delivered > required_date == planned_ship) is unaffected: the
        # offset is only ever clamped downward, and it's already positive
        # whenever the clamp triggers.
        delivered = (
            min(planned_ship + timedelta(days=rng.randint(-3, 6)), now)
            if status in (WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED)
            else None
        )
        wo = TestDataFactory.create_work_order(
            session,
            client_id=cid,
            work_order_id=wo_id,
            status=status,
            planned_quantity=rng.randint(500, 3000),
            planned_ship_date=planned_ship,
            priority=rng.choice(["HIGH", "MEDIUM", "LOW"]),
        )
        # create_work_order doesn't read actual_delivery_date via **kwargs; set directly.
        wo.actual_delivery_date = delivered

        # OTD reads required_date (not planned_ship_date). Anchor it to the plan
        # so the 10 status WOs participate in the On-Time-Delivery metric.
        wo.required_date = planned_ship

        # --- Milestones (status-coherent, anchor-relative, deterministic) ---
        wo.received_date = now - timedelta(days=rng.randint(30, 70))
        if status in (WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED):
            wo.dispatch_date = wo.received_date + timedelta(days=rng.randint(2, 10))
            wo.shipped_date = delivered
        if status == WorkOrderStatus.CLOSED:
            # Same future-leak clamp as `delivered` above (ISSUE-009): shipped_date
            # is already <= now, but adding another +[1,5] days can still overshoot.
            wo.closure_date = min((wo.shipped_date or now) + timedelta(days=rng.randint(1, 5)), now)
        if status == WorkOrderStatus.ON_HOLD:
            wo.previous_status = WorkOrderStatus.IN_PROGRESS.value
        if status == WorkOrderStatus.REJECTED:
            wo.rejection_reason = "QC inspection: stitching defect rate exceeded acceptance threshold"
            wo.rejected_by = entered_by
            wo.rejected_date = wo.received_date + timedelta(days=rng.randint(5, 15))

        # --- Bridge to Capacity Planning (mainline WOs only) ---
        # Strict 1:1 map WO→CapacityOrder (no modulo wraparound): each bridged WO
        # takes its own order, so aligning cap.completed_quantity below can never
        # be overwritten by a second WO sharing the same order. If bridged WOs ever
        # outnumber cap orders, the extras simply stay unbridged (safe degradation).
        if status in mainline_bridge_statuses and bridge_idx < len(cap_orders):
            cap = cap_orders[bridge_idx]
            bridge_idx += 1
            wo.origin = "CAPACITY_PLAN"
            wo.capacity_order_id = cap.id
            wo.planned_start_date = now - timedelta(days=rng.randint(20, 60))
            # Re-align the bridged CapacityOrder to this WO's plan/status so the
            # two sides of the bridge stay coherent (single source of truth).
            target_qty = int(wo.planned_quantity * _production_target_fraction(status))
            cap.order_quantity = wo.planned_quantity
            cap.completed_quantity = target_qty
            cap.status = (
                OrderStatus.COMPLETED
                if status in (WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED, WorkOrderStatus.COMPLETED)
                else OrderStatus.IN_PROGRESS if status == WorkOrderStatus.IN_PROGRESS else OrderStatus.CONFIRMED
            )

        # transition chain to the terminal status
        chain = _transition_chain(status)  # e.g. [None->RECEIVED, RECEIVED->RELEASED, ...]
        for frm, to in chain:
            TestDataFactory.create_workflow_transition(
                session,
                work_order_id=wo_id,
                from_status=(frm.value if frm else None),  # type: ignore[arg-type]
                to_status=to.value,
                transitioned_by=entered_by,
                client_id=cid,
            )
        if status in (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED):
            # explicit deterministic job_id (do NOT let the factory mint a _next_id PK)
            TestDataFactory.create_job(session, work_order_id=wo_id, client_id=cid, job_id=f"JOB-{cid}-{i:03d}")
        wos.append(wo)

    # --- Delivered-history batch: credible + OOC-demoable OTD -----------------
    # OTD groups delivered WOs by required_date over the trend window; the 10
    # status WOs alone give too thin a denominator. Add lightweight SHIPPED WOs
    # spread across the last ~90 days, ~67% on-time, with a handful of days that
    # dip below the 80% critical threshold so the diagnostic OOC tooltip demos.
    HISTORY_N = 15
    hrng = rng_for(cid, "otd_history")
    # Deterministic delay-classification mix (Task 9, Cycle 2) over the late
    # subset of this batch only. `late_ct` increments once per late row (n %
    # 3 == 0, below) and drives a fixed i % 3 state pattern: 0=justified,
    # 1=unjustified, 2=unclassified (left NULL). is_late() is deliberately
    # NOT called here to decide eligibility — this block already guarantees
    # lateness by construction (delivered = req + [2,6]d, always after req,
    # whenever `late` is True); the seeder tests assert that guarantee via
    # is_late() instead, per the spec's "assert, don't reimplement" split.
    #
    # Reason rotation uses a SEPARATE `justified_ct` counter, incremented only
    # on justified rows, indexed mod 6 into JustifiedDelayReasonEnum. This
    # must NOT be `late_ct % 6`: late_ct only hits the justified branch when
    # late_ct % 3 == 0, and gcd(3, 6) == 3 means late_ct % 6 would then only
    # ever land on {0, 3} — CUSTOMER_REQUEST/FORCE_MAJEURE — making the other
    # 4 reasons unreachable at any scale (round-1 review finding). `justified_ct`
    # starts at `justified_reason_offset` so a caller seeding multiple clients
    # can advance each client's rotation past the previous one's — see
    # JUSTIFIED_REASONS_PER_CLIENT and seed_sample_client.py's main().
    _delay_reasons = list(JustifiedDelayReasonEnum)
    late_ct = 0
    justified_ct = justified_reason_offset
    for n in range(1, HISTORY_N + 1):
        days_ago = 2 + (n - 1) * 6  # distinct days: 2, 8, 14, ... 86 (within last 90d)
        req = now - timedelta(days=days_ago)
        late = n % 3 == 0  # every 3rd order late -> 5 late / 10 on-time = 67% on-time
        delivered = req + timedelta(days=hrng.randint(2, 6)) if late else req - timedelta(days=hrng.randint(0, 2))
        hwo = TestDataFactory.create_work_order(
            session,
            client_id=cid,
            work_order_id=f"WO-{cid}-H{n:03d}",
            status=WorkOrderStatus.SHIPPED,
            planned_quantity=hrng.randint(500, 2000),
            planned_ship_date=req,
            priority="MEDIUM",
        )
        hwo.required_date = req
        hwo.actual_delivery_date = delivered
        hwo.received_date = req - timedelta(days=hrng.randint(20, 40))
        hwo.dispatch_date = req - timedelta(days=hrng.randint(1, 5))
        hwo.shipped_date = delivered
        # This batch never goes through seed_daily_data's per-WO production
        # true-up (deliberately, to keep OEE/throughput unchanged — see the
        # comment below), so without this a SHIPPED WO would carry the
        # factory default actual_quantity=0 / 0% progress, which is
        # incoherent for a terminal, delivered status. SHIPPED implies fully
        # produced, so true it up to the full planned quantity directly.
        hwo.actual_quantity = hwo.planned_quantity
        if late:
            pattern = late_ct % 3
            if pattern == 0:
                hwo.delay_classification = DelayClassificationEnum.JUSTIFIED.value
                hwo.justified_delay_reason = _delay_reasons[justified_ct % len(_delay_reasons)].value
                justified_ct += 1
            elif pattern == 1:
                hwo.delay_classification = DelayClassificationEnum.UNJUSTIFIED.value
            # pattern == 2: leave both NULL (unclassified)
            late_ct += 1
        wos.append(hwo)

    session.flush()
    return wos


def _transition_chain(status: "WorkOrderStatus") -> list:
    from backend.orm import WorkOrderStatus as S

    linear = [S.RECEIVED, S.RELEASED, S.IN_PROGRESS, S.COMPLETED, S.SHIPPED, S.CLOSED]
    if status in linear:
        upto = linear[: linear.index(status) + 1]
    elif status == S.CANCELLED:
        upto = [S.RECEIVED, S.RELEASED, S.CANCELLED]
    elif status == S.ON_HOLD:
        upto = [S.RECEIVED, S.RELEASED, S.IN_PROGRESS, S.ON_HOLD]
    elif status == S.DEMOTED:
        upto = [S.RECEIVED, S.RELEASED, S.DEMOTED]
    elif status == S.REJECTED:
        upto = [S.RECEIVED, S.RELEASED, S.IN_PROGRESS, S.REJECTED]
    else:
        upto = [status]
    prev: Optional["WorkOrderStatus"] = None
    chain: list = []
    for s in upto:
        chain.append((prev, s))
        prev = s
    return chain


def seed_holds(session: Session, client_id: str, work_orders: list, entered_by: str, anchor: date) -> None:
    # Construct HoldEntry directly: TestDataFactory.create_hold_entry mints
    # hold_entry_id via _next_id("HOLD") (process-local counter → cross-process
    # PK collision). Use a deterministic client-scoped PK instead.
    from datetime import datetime, timedelta, timezone
    from backend.orm import HoldEntry, WorkOrderStatus

    if session.query(HoldEntry).filter_by(client_id=client_id).first() is not None:
        return
    if not work_orders:  # nothing to attach holds to
        return
    chain = [
        "PENDING_HOLD_APPROVAL",
        "ON_HOLD",
        "PENDING_RESUME_APPROVAL",
        "RESUMED",
        "RELEASED",
        "CANCELLED",
        "SCRAPPED",
    ]
    # The currently-open hold statuses must reference the WO that is actually
    # ON_HOLD (credibility: a hold row can't be "open" against a WO that has
    # already moved on). Resolved statuses may reference other WOs as before.
    open_statuses = {"PENDING_HOLD_APPROVAL", "ON_HOLD", "PENDING_RESUME_APPROVAL"}
    # Prefer the WO actually in ON_HOLD status for open holds; fall back to the
    # first WO if (defensively) none is ON_HOLD, so this never StopIteration-crashes.
    on_hold_wo = next((w for w in work_orders if w.status == WorkOrderStatus.ON_HOLD), work_orders[0])
    anchor_dt = datetime.combine(anchor, datetime.min.time(), tzinfo=timezone.utc)
    resolved_statuses = {"RESUMED", "RELEASED", "CANCELLED", "SCRAPPED"}
    for i, hold_status in enumerate(chain, start=1):
        wo = on_hold_wo if hold_status in open_statuses else work_orders[i % len(work_orders)]
        # Backdate deterministically so WIP-Aging shows real aging. The ON_HOLD
        # hold is the chronic one (60-70d) so the active-hold aging is pronounced.
        hrng = rng_for(client_id, "hold_age", i)
        age_days = hrng.randint(60, 70) if hold_status == "ON_HOLD" else hrng.randint(10, 70)
        hold_date = anchor_dt - timedelta(days=age_days)
        # Resolved holds carry a resume_date strictly between hold_date and anchor
        # (correct inactive semantics + the discontinuity that makes an SPC
        # WIP-Aging OOC flag likely). Open-status holds stay active (resume_date NULL).
        resume_date = None
        if hold_status in resolved_statuses:
            resume_offset = rng_for(client_id, "hold_resume", i).randint(1, max(2, age_days - 1))
            resume_date = hold_date + timedelta(days=resume_offset)
        session.add(
            HoldEntry(
                hold_entry_id=f"HOLD-{client_id}-{i:03d}",
                work_order_id=wo.work_order_id,
                client_id=client_id,
                hold_initiated_by=entered_by,
                hold_reason="QUALITY_ISSUE",
                hold_reason_category="QUALITY",
                hold_status=hold_status,
                hold_date=hold_date,
                resume_date=resume_date,
            )
        )
    session.flush()


def seed_daily_data(session: Session, spec: ClientSpec, days: int, entered_by: str, anchor: date) -> None:
    """Idempotent credible daily Operations data on the first product/shift/
    line. Production is distributed PER WORK ORDER so cumulative units true-up
    to a status-derived target of planned_quantity (see
    _production_target_fraction): the LAST entry per WO is pinned so the sum
    exactly equals the target, and wo.actual_quantity is set to that total.
    Each production entry carries a QualityEntry + DefectDetail and
    (occasionally) a DowntimeEntry tied to the same WO. AttendanceEntry is
    per employee per working day, independent of the WO split. Construct
    every entity DIRECTLY with a deterministic client-scoped PK (see
    seed_holds docstring) — TestDataFactory.create_production_entry et al.
    mint _next_id counter PKs that collide across processes."""
    from datetime import datetime, timedelta
    from decimal import Decimal
    from backend.orm import (
        ProductionEntry,
        QualityEntry,
        DefectDetail,
        DowntimeEntry,
        AttendanceEntry,
        AttendanceHourAllocation,
        AbsenceType,
        WorkOrder,
    )

    cid = spec.client_id
    if session.query(ProductionEntry).filter_by(client_id=cid).first() is not None:
        return
    products = seed_products(session, cid)
    shifts = seed_shifts(session, cid)
    lines, _ = seed_lines(session, cid)
    employees = seed_employees(session, spec)
    work_orders = [
        wo
        for wo in session.query(WorkOrder).filter_by(client_id=cid).order_by(WorkOrder.work_order_id).all()
        if not wo.work_order_id.split("-")[-1].startswith("H")
    ]
    product, shift, line = products[0], shifts[0], lines[0]
    end = anchor
    ideal_ct = float(product.ideal_cycle_time or Decimal("0.12"))

    # Walk backward from the anchor collecting exactly `days` WORKING days
    # (weekends skipped without counting) so `days` maps to working-day
    # entries, not calendar days diluted by weekend skips.
    working_days: list = []
    offset = 0
    while len(working_days) < days:
        day = end - timedelta(days=offset)
        offset += 1
        if day.weekday() >= 5:
            continue
        working_days.append(day)
    working_days.reverse()

    # --- Production/Quality/Defect/Downtime: distributed per-WO to a
    # status-derived target, so cumulative units are plan-vs-actual coherent. ---
    seq = 0
    for wo in work_orders:
        target_total = int((wo.planned_quantity or 0) * _production_target_fraction(wo.status))
        if target_total <= 0:
            wo.actual_quantity = 0
            continue
        wrng = rng_for(cid, "daily", "wo", wo.work_order_id)
        num_entries = max(1, min(len(working_days), 4 if target_total >= 200 else 2))
        step = max(1, (len(working_days) - 1) // max(1, num_entries - 1)) if num_entries > 1 else 1
        base_per_entry = target_total // num_entries
        running = 0
        for k in range(num_entries):
            is_last = k == num_entries - 1
            day_idx = (len(working_days) - 1) if is_last else min(k * step, len(working_days) - 1)
            day = working_days[day_idx]
            day_dt = datetime.combine(day, shift.start_time)

            if is_last:
                units = max(1, target_total - running)
            else:
                noise = wrng.uniform(0.9, 1.1)
                units = max(1, min(int(base_per_entry * noise), target_total - running - (num_entries - k - 1)))
            running += units
            seq += 1

            target_perf = wrng.uniform(0.82, 0.96)
            run_time = round(ideal_ct * units / target_perf, 2)
            downtime_h = round(run_time * wrng.uniform(0.05, 0.08), 2)
            setup_h = round(run_time * 0.02, 2)
            maint_h = round(run_time * 0.01, 2)
            actual_ct = round(run_time / units, 4)
            defects = max(1, int(units * wrng.uniform(0.003, 0.012)))
            scrap = defects // 3
            rework = defects - scrap
            performance = min(100.0, max(0.01, round(target_perf * 100, 2)))
            # Efficiency is measured against the FULL scheduled shift window
            # (run time + downtime + setup + maintenance), while performance
            # is measured against run time alone — so efficiency is
            # realistically lower than performance by an availability-loss
            # factor. Derive that factor from the downtime/setup/maint hours
            # already generated above (not an independent random draw) so
            # the two metrics stay coherent (ISSUE-010: previously identical).
            scheduled_h = run_time + downtime_h + setup_h + maint_h
            availability_frac = (run_time / scheduled_h) if scheduled_h > 0 else 1.0
            efficiency = min(100.0, max(0.01, round(performance * availability_frac, 2)))
            quality_pct = min(100.0, max(0.01, round(100 - (defects + scrap) / units * 100, 2)))
            employees_present = max(0, len(employees) - (1 if wrng.random() < 0.15 else 0))

            session.add(
                ProductionEntry(
                    production_entry_id=f"PE-{cid}-{seq:04d}",
                    client_id=cid,
                    product_id=product.product_id,
                    shift_id=shift.shift_id,
                    line_id=line.line_id,
                    entered_by=entered_by,
                    production_date=day_dt,
                    shift_date=day_dt,
                    units_produced=units,
                    run_time_hours=Decimal(str(run_time)),
                    setup_time_hours=Decimal(str(setup_h)),
                    downtime_hours=Decimal(str(downtime_h)),
                    maintenance_hours=Decimal(str(maint_h)),
                    defect_count=defects,
                    scrap_count=scrap,
                    rework_count=rework,
                    employees_assigned=len(employees),
                    employees_present=employees_present,
                    ideal_cycle_time=Decimal(str(ideal_ct)),
                    actual_cycle_time=Decimal(str(actual_ct)),
                    efficiency_percentage=Decimal(str(efficiency)),
                    performance_percentage=Decimal(str(performance)),
                    quality_rate=Decimal(str(quality_pct)),
                    work_order_id=wo.work_order_id,
                )
            )

            qe_id = f"QE-{cid}-{seq:04d}"
            units_def = defects + scrap
            session.add(
                QualityEntry(
                    quality_entry_id=qe_id,
                    work_order_id=wo.work_order_id,
                    client_id=cid,
                    inspector_id=entered_by,
                    inspection_date=day_dt,
                    shift_date=day_dt,
                    units_inspected=units,
                    units_passed=units - units_def,
                    units_defective=units_def,
                    total_defects_count=units_def,
                    units_scrapped=scrap,
                    units_reworked=defects - scrap,
                )
            )
            # DefectDetail.quality_entry_id is a raw FK (no ORM relationship), so the
            # unit-of-work won't order the QualityEntry insert before the DefectDetail
            # insert; flush the parent now so the child FK resolves on MariaDB (SQLite
            # with FKs off silently tolerates the wrong order — see the FK-enforcement test).
            session.flush()
            session.add(
                DefectDetail(
                    defect_detail_id=f"DD-{cid}-{seq:04d}",
                    quality_entry_id=qe_id,
                    client_id_fk=cid,
                    defect_type="Stitching",
                    defect_count=defects,
                    severity="MINOR",
                )
            )
            if seq % 5 == 1:
                reason = wrng.choice(
                    [
                        DowntimeReasonEnum.EQUIPMENT_FAILURE.value,
                        DowntimeReasonEnum.MATERIAL_SHORTAGE.value,
                        DowntimeReasonEnum.SETUP_CHANGEOVER.value,
                        DowntimeReasonEnum.MAINTENANCE.value,
                        DowntimeReasonEnum.QUALITY_HOLD.value,
                        DowntimeReasonEnum.OPERATOR_UNAVAILABLE.value,
                    ]
                )
                # ~10% explicit overrides demonstrate the operator-correction flow
                # (downtime rows are created when seq % 5 == 1, so seq % 50 == 1 hits
                # one in ten of them): the row is attributed to scheduling even though
                # the reason's default says otherwise (e.g. a rushed changeover broke
                # the machine). Skip when the default already IS scheduling, so every
                # flagged row is a true override.
                if seq % 50 == 1 and DEFAULT_CATEGORY_BY_REASON[reason] != DowntimeCategoryEnum.SCHEDULING.value:
                    category = DowntimeCategoryEnum.SCHEDULING.value
                else:
                    category = DEFAULT_CATEGORY_BY_REASON[reason]
                session.add(
                    DowntimeEntry(
                        downtime_entry_id=f"DT-{cid}-{seq:04d}",
                        client_id=cid,
                        work_order_id=wo.work_order_id,
                        reported_by=entered_by,
                        downtime_reason=reason,
                        root_cause_category=category,
                        shift_date=day_dt,
                        downtime_duration_minutes=int(downtime_h * 60),
                    )
                )
        # Invariant: the last entry is pinned to (target_total - running), so the
        # per-WO produced total must land EXACTLY on target. Assert it so a future
        # change to planned_quantity range / target fractions / num_entries that
        # broke the reservation budget (target_total < num_entries-1) fails loudly.
        assert running == target_total, f"true-up miss for {wo.work_order_id}: {running} != {target_total}"
        wo.actual_quantity = running

    # --- Attendance: one per employee per working day, independent of the
    # per-WO production split. Labor-hours capture (Cycle 3 PR-A, Task 8):
    # deterministic OT-split / labor-class-override / hour-allocation
    # coverage over the PRESENT entries only (an absence already implies
    # unsplit + unallocated by construction — actual_hours=0). `p` counts
    # present entries only, so the fixed cadences below land regardless of
    # which days the (rng-seeded) absence draw happens to hit.
    #
    # `alloc_ct` is a SEPARATE counter, incremented only on rotating-minority
    # allocation rows and indexed mod 8 into HourCategoryEnum — mirroring the
    # justified_ct fix from Task 9/Cycle 2 above: a naive `p % 8` would
    # collide with the `p % 4 == 0` selection modulus (gcd(4, 8) == 4),
    # reaching only 2 of 8 categories at any scale.
    _hour_categories = list(HourCategoryEnum)
    p = 0
    alloc_ct = 0
    for day_seq, day in enumerate(working_days, start=1):
        day_dt = datetime.combine(day, shift.start_time)
        for j, emp in enumerate(employees, start=1):
            arng = rng_for(cid, "att", day.isoformat(), emp.employee_id)
            absent = arng.random() < 0.05
            absence_type = (
                arng.choice([AbsenceType.UNSCHEDULED_ABSENCE, AbsenceType.VACATION, AbsenceType.MEDICAL_LEAVE])
                if absent
                else None
            )
            actual = Decimal("0") if absent else Decimal("8.0")
            normal_hours = double_hours = triple_hours = None
            labor_class_override = None
            allocations: list = []
            if not absent:
                p += 1
                if p % 25 == 0:
                    pass  # fixed minority left UNSPLIT (completeness chip)
                elif p % 20 == 0:
                    normal_hours, double_hours, triple_hours = Decimal("7.0"), Decimal("0"), Decimal("1.0")
                elif p % 5 == 0:
                    normal_hours, double_hours, triple_hours = Decimal("6.0"), Decimal("2.0"), Decimal("0")
                else:
                    normal_hours, double_hours, triple_hours = Decimal("8.0"), Decimal("0"), Decimal("0")

                if p % 15 == 0:
                    # Sparse per-entry class override, flipping the employee's default.
                    labor_class_override = (
                        LaborClassEnum.INDIRECT.value
                        if emp.labor_class == LaborClassEnum.DIRECT.value
                        else LaborClassEnum.DIRECT.value
                    )

                if p % 10 == 0:
                    pass  # fixed minority left unallocated (completeness chip)
                elif p % 4 == 0:
                    category = _hour_categories[alloc_ct % len(_hour_categories)]
                    alloc_ct += 1
                    allocations.append((category.value, actual))
                else:
                    allocations.append((HourCategoryEnum.BILLED_PRODUCTION.value, actual))

            entry = AttendanceEntry(
                attendance_entry_id=f"ATT-{cid}-{day_seq:04d}-{j:02d}",
                employee_id=emp.employee_id,
                client_id=cid,
                shift_id=shift.shift_id,
                shift_date=day_dt,
                scheduled_hours=Decimal("8.0"),
                actual_hours=actual,
                absence_hours=Decimal("8.0") if absent else Decimal("0"),
                absence_type=absence_type,
                is_absent=1 if absent else 0,
                normal_hours=normal_hours,
                double_hours=double_hours,
                triple_hours=triple_hours,
                labor_class_override=labor_class_override,
            )
            for category_value, hours in allocations:
                entry.hour_allocations.append(AttendanceHourAllocation(category=category_value, hours=hours))
            session.add(entry)
    session.flush()
