"""Fetch hooks for datasets whose semantics live in existing calculations, or
whose per-row logic simply isn't SQL-expressible.

Each hook yields (day, group_key, components) triples -- the same shape the
generic SQL path (`_sql_day_rows` in engine.py) produces. fetch_labor and
fetch_delivery REUSE the existing calculation functions verbatim so the
cross-source goldens (test_hooks_golden.py) hold by construction, never by
re-deriving the math. fetch_holds has no such external calculation to golden
against -- it moved off the SQL path (validation finding F3) because
`SUM(total_hold_duration_hours)` silently coalesces every still-open hold to
0 (the column defaults to 0, not NULL, until a hold resumes), which a plain
SQL sum can't distinguish from a hold that resolved in a minute; the
per-row hold_status branch that fixes this (open vs. terminal, not a
nullness check -- see fetch_holds' own docstring, review round CRITICAL 1)
is only expressible in Python."""

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Iterator, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.calculations.labor_hours import (
    available_for_efficiency_hours,
    billed_hours,
    effective_labor_class,
)
from backend.calculations.otd import infer_planned_delivery_date
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.delay_taxonomy import DelayClassificationEnum
from backend.orm.employee import Employee
from backend.orm.hold_entry import HoldEntry, HoldStatus
from backend.orm.production_entry import ProductionEntry
from backend.orm.work_order import WorkOrder

# Mirrors backend/scripts/_seed_operations.py's open_statuses set: a hold is
# still "open" (not yet resumed/cancelled/released) in these three statuses.
# Used to decide age-to-date vs. recorded-duration in fetch_holds below.
_OPEN_HOLD_STATUSES = frozenset(
    {HoldStatus.PENDING_HOLD_APPROVAL, HoldStatus.ON_HOLD, HoldStatus.PENDING_RESUME_APPROVAL}
)


def fetch_labor(
    db: Session,
    group_by: Optional[str],
    start_date: date,
    end_date: date,
    client_ids: Optional[Sequence[str]],
) -> Iterator[tuple[date, Optional[str], dict[str, float]]]:
    """Per-(day, group) labor components, mirroring summarize_labor_hours
    entry-by-entry (same OT-split transparency, same allocation category
    sets, same effective-class fallback). Also folds in per-day earned hours
    from production entries (entry ict else product default; neither ->
    excluded) so efficiency_available_basis composes as a ratio of sums --
    earned is only attributed when group_by is None or 'client' (production
    rows carry no labor class, so it is never produced for 'labor_class')."""
    q = db.query(AttendanceEntry).filter(
        func.date(AttendanceEntry.shift_date) >= start_date,
        func.date(AttendanceEntry.shift_date) <= end_date,
    )
    if client_ids is not None:
        q = q.filter(AttendanceEntry.client_id.in_(client_ids))
    entries = q.all()

    class_by_employee: dict[int, Optional[str]] = {}
    if group_by == "labor_class":
        employee_ids = {e.employee_id for e in entries}
        if employee_ids:
            class_rows = (
                db.query(Employee.employee_id, Employee.labor_class)
                .filter(Employee.employee_id.in_(employee_ids))
                .all()
            )
            class_by_employee = {row.employee_id: row.labor_class for row in class_rows}

    acc: dict[tuple[date, Optional[str]], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for e in entries:
        day = e.shift_date.date()
        grp: Optional[str]
        if group_by == "labor_class":
            cls = effective_labor_class(e.labor_class_override, class_by_employee.get(e.employee_id))
            grp = cls if cls in ("direct", "indirect") else "unclassified"
        elif group_by == "client":
            grp = e.client_id
        else:
            grp = None
        c = acc[(day, grp)]
        actual = float(e.actual_hours or 0)
        c["scheduled"] += float(e.scheduled_hours or 0)
        c["actual"] += actual
        if e.normal_hours is not None or e.double_hours is not None or e.triple_hours is not None:
            c["normal"] += float(e.normal_hours or 0)
            c["double"] += float(e.double_hours or 0)
            c["triple"] += float(e.triple_hours or 0)
        else:
            c["unsplit_actual"] += actual
        allocs = [(a.category, a.hours) for a in e.hour_allocations]
        c["billed"] += float(billed_hours(allocs))
        c["available_for_efficiency"] += float(
            available_for_efficiency_hours(Decimal(str(e.actual_hours or 0)), allocs)
        )

    if group_by in (None, "client"):
        pq = db.query(ProductionEntry).filter(
            func.date(ProductionEntry.shift_date) >= start_date,
            func.date(ProductionEntry.shift_date) <= end_date,
        )
        if client_ids is not None:
            pq = pq.filter(ProductionEntry.client_id.in_(client_ids))
        production_entries = pq.all()
        if not production_entries:
            # No production rows at all in scope this call -- earned_hours/
            # excluded_entries are still structurally applicable for this
            # group_by (production rows just happen not to exist here), so
            # seed them onto every attendance-populated bucket rather than
            # silently omitting efficiency_available_basis for an
            # attendance-only window.
            for c in acc.values():
                c["earned_hours"] += 0.0
                c["excluded_entries"] += 0.0
        for pe in production_entries:
            ict = pe.ideal_cycle_time
            if ict is None and pe.product is not None:
                ict = pe.product.ideal_cycle_time
            pe_day = pe.shift_date.date()
            pe_grp = pe.client_id if group_by == "client" else None
            pc = acc[(pe_day, pe_grp)]
            # Seed both keys before the branch below: a bucket whose
            # production rows all lack an inferable ideal_cycle_time must
            # still report earned_hours=0.0 (produced) alongside
            # excluded_entries, not omit efficiency_available_basis entirely.
            pc["earned_hours"] += 0.0
            pc["excluded_entries"] += 0.0
            if ict is None:
                pc["excluded_entries"] += 1
            else:
                pc["earned_hours"] += float(Decimal(pe.units_produced) * ict)

    for (acc_day, acc_grp), comps in acc.items():
        yield (acc_day, acc_grp, dict(comps))


def fetch_holds(
    db: Session,
    group_by: Optional[str],
    start_date: date,
    end_date: date,
    client_ids: Optional[Sequence[str]],
) -> Iterator[tuple[date, Optional[str], dict[str, float]]]:
    """Per-(day, group) hold components (validation finding F3; review round
    CRITICAL 1). The SQL-path `hold_days` measure summed
    HoldEntry.total_hold_duration_hours directly, which stays 0 until a hold
    resumes -- so every still-open row silently coalesced to 0,
    indistinguishable from a hold that resolved in a minute.

    Branches on hold_status, NOT on total_hold_duration_hours' nullness:
    HoldEntry.total_hold_duration_hours declares an ORM-level `default=0`
    (backend/orm/hold_entry.py), which SQLAlchemy applies at flush whenever
    the attribute is left None -- so a plain ORM insert (every real code
    path: backend/crud/hold/core.py, the demo seeder) can never actually
    land a NULL through the ORM. A None-check here would be dead code in
    production, always taking the "resolved" branch. Open statuses
    (_OPEN_HOLD_STATUSES, mirroring backend/calculations/wip_aging.py and
    backend/crud/hold/duration.py's ON_HOLD-vs-terminal split, widened to
    the pending-approval statuses too) get age-to-date; terminal/resumed
    holds use their recorded duration, falling back to
    (resume_date - hold_date) when the duration was never recorded (None or
    0 -- matches release_hold's "not recorded" convention in
    backend/crud/hold/duration.py:171), else 0.

    Age-to-date uses min(date.today(), end_date) as the "as of" day, not
    date.today() unconditionally -- a historical window (end_date in the
    past) must produce a STABLE hold_days across re-exports/re-runs, not one
    that silently grows as real-world today() advances after the window
    closed. date.today() (uncapped, for windows still open) matches
    is_late's server-local convention (backend/calculations/otd.py /
    backend/crud/work_order.py) -- not timezone-aware, just the server
    clock. Same window filter and client scoping as the SQL path; group_by
    coalesce-to-"uncategorized" semantics reapplied here in Python since the
    fetch path bypasses the SQL func.coalesce() -- `is None` only (NOT
    `or`), so an empty string doesn't fold into the sentinel, matching SQL
    COALESCE's NULL-only substitution exactly."""
    q = db.query(HoldEntry).filter(
        HoldEntry.hold_date.isnot(None),
        func.date(HoldEntry.hold_date) >= start_date,
        func.date(HoldEntry.hold_date) <= end_date,
    )
    if client_ids is not None:
        q = q.filter(HoldEntry.client_id.in_(client_ids))

    as_of = min(date.today(), end_date)
    acc: dict[tuple[date, Optional[str]], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    # .all() materializes every matching hold row in Python -- fine at the
    # scale this table runs at (mirrors fetch_labor/fetch_delivery, which do
    # the same for attendance/work-order rows).
    for h in q.all():
        if h.hold_date is None:
            continue  # SQL filter already excludes these; narrows for mypy
        day = h.hold_date.date()
        grp: Optional[str]
        if group_by == "client":
            grp = h.client_id  # NOT NULL column -- never None
        elif group_by == "reason_category":
            grp = "uncategorized" if h.hold_reason_category is None else h.hold_reason_category
        elif group_by == "reason":
            grp = "uncategorized" if h.hold_reason is None else h.hold_reason
        else:
            grp = None
        c = acc[(day, grp)]
        c["holds"] += 1
        if h.hold_status in _OPEN_HOLD_STATUSES:
            c["hold_days"] += (as_of - day).days
        elif h.total_hold_duration_hours:
            c["hold_days"] += float(h.total_hold_duration_hours) / 24.0
        elif h.resume_date is not None:
            c["hold_days"] += (h.resume_date.date() - day).days
        else:
            c["hold_days"] += 0.0

    for (acc_day, acc_grp), comps in acc.items():
        yield (acc_day, acc_grp, dict(comps))


def fetch_delivery(
    db: Session,
    group_by: Optional[str],
    start_date: date,
    end_date: date,
    client_ids: Optional[Sequence[str]],
) -> Iterator[tuple[date, Optional[str], dict[str, float]]]:
    """Per-(day, group) delivery components mirroring calculate_true_otd's
    STANDARD-OTD counting rules (backend/calculations/otd.py:380-433, spec §4
    amendment 2026-08-07): delivered-orders basis -- any status counts, not
    just COMPLETED -- with actual_delivery_date in window; planned date via
    the inference chain; orders with no inferable date are skipped (not in
    the denominator, same as calculate_true_otd's skipped_no_date bucket);
    justified-late per delay_classification."""
    q = db.query(WorkOrder).filter(
        WorkOrder.actual_delivery_date.isnot(None),
        WorkOrder.actual_delivery_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.actual_delivery_date <= datetime.combine(end_date, datetime.max.time()),
    )
    if client_ids is not None:
        q = q.filter(WorkOrder.client_id.in_(client_ids))

    acc: dict[tuple[date, Optional[str]], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for wo in q.all():
        inferred = infer_planned_delivery_date(wo)
        if inferred.date is None or wo.actual_delivery_date is None:
            continue  # not inferable -> excluded from denominator (golden rule)
        day = wo.actual_delivery_date.date()
        grp: Optional[str]
        if group_by == "client":
            grp = wo.client_id
        elif group_by == "style":
            grp = wo.style_model
        elif group_by == "delay_reason":
            grp = wo.justified_delay_reason or "none"
        else:
            grp = None
        c = acc[(day, grp)]
        # Seed every structurally-applicable component before the
        # conditional increments below: a bucket whose only delivery is
        # late-and-unjustified must still report on_time=0.0/
        # justified_late=0.0/net_on_time=0.0 (produced) so otd_gross_pct/
        # otd_net_pct compute as 0.0, not get omitted.
        c["delivered"] += 0.0
        c["on_time"] += 0.0
        c["justified_late"] += 0.0
        c["net_on_time"] += 0.0
        c["delivered"] += 1
        on_time = wo.actual_delivery_date <= inferred.date
        justified_late = (not on_time) and (wo.delay_classification == DelayClassificationEnum.JUSTIFIED.value)
        if on_time:
            c["on_time"] += 1
        if justified_late:
            c["justified_late"] += 1
        if on_time or justified_late:
            c["net_on_time"] += 1

    for (acc_day, acc_grp), comps in acc.items():
        yield (acc_day, acc_grp, dict(comps))
