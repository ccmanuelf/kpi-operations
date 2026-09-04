"""
Real-data aggregators for dual-view raw inputs (F.1, refined).

Replaces the illustrative sample inputs used in the Phase 4c demo with real
aggregates from ProductionEntry / DowntimeEntry / QualityEntry / WorkOrder.

Each `aggregate_*_inputs(db, client_id, period_start, period_end, **filters)`
returns a fully-populated `*RawInputs` Pydantic model that the matching
dual-view service can consume directly.

## Conventions

  - Inclusive period: `period_start <= shift_date <= period_end`.
  - Tenant filter: every query filters by `client_id`.
  - Optional partition filters (line_id, shift_id, product_id, work_order_id)
    pass through to WHERE clauses; pass `None` to skip a filter.
  - Empty windows return zero-valued inputs (safe for the dual-view service).

## Filter applicability matrix

|                  | line_id | shift_id | product_id | work_order_id |
|------------------|---------|----------|------------|---------------|
| OEE  (Production)| ✅      | ✅       | ✅         | ✅            |
| OEE  (Quality)   | —       | —        | —          | ✅            |
| OTD  (WorkOrder) | —       | —        | —          | ✅            |
| FPY  (Quality)   | —       | —        | —          | ✅            |

Filters not present on a table are silently ignored (no error). The OEE
rework count comes from QualityEntry, which only carries `work_order_id`,
so passing `line_id` to `aggregate_oee_inputs` filters production rows but
not the rework subquery.

## Extending with custom aggregations

For deployments needing more sophisticated aggregation (weighted cycle time,
exotic partitioning), wrap rather than replace. Example for a units-weighted
cycle time:

    def aggregate_oee_inputs_weighted(db, client_id, period_start, period_end, **kw):
        base = aggregate_oee_inputs(db, client_id, period_start, period_end, **kw)
        weighted = (
            db.query(
                (func.sum(ProductionEntry.units_produced * ProductionEntry.ideal_cycle_time)
                 / func.coalesce(func.sum(ProductionEntry.units_produced), 1))
            )
            .filter(...same period + filter clauses...)
            .scalar()
        )
        return base.model_copy(update={"ideal_cycle_time_hours": Decimal(str(weighted))})

Keep the functions pure and SQLAlchemy-backed; the dual-view services
contract is `RawInputs in → CalculationResult out`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query, Session

from backend.orm.production_entry import ProductionEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.work_order import WorkOrder
from backend.services.dual_view.fpy_service import FPYRawInputs
from backend.services.dual_view.oee_service import OEERawInputs
from backend.services.dual_view.otd_service import OrderDelay, OTDRawInputs

_DEFAULT_CYCLE_TIME = Decimal("0.25")  # 15 min/unit, used only when no production rows exist
_NEUTRAL_CYCLE_TIME_FLOOR = Decimal("0.0001")  # 0.36s — guards divide-by-zero when units == 0


def _resolve_ideal_cycle_time(
    avg_cycle: Optional[Decimal],
    units_produced: int,
    run_time_hours: Decimal,
) -> Decimal:
    """
    Pick the ideal_cycle_time used by Performance.

    Order of preference:
      1. Master/product cycle time from ProductionEntry rows (avg_cycle).
      2. Observed rate (run_time / units) — implicit standard from real
         production. This makes Performance == 100% when no published
         standard exists, instead of fabricating a value out of thin air.
      3. _DEFAULT_CYCLE_TIME — only when the period has no production at all
         (units_produced == 0 and run_time_hours == 0). Performance is 0
         in that branch anyway, so the value doesn't materially matter.

    Why not the old hardcoded 0.25h fallback: it routinely produced
    Performance > 100% (and therefore OEE > 100%) on demo data where rows
    don't carry a master cycle time, because real run rates are usually far
    faster than 15 min/unit.
    """

    if avg_cycle is not None and avg_cycle > 0:
        return Decimal(str(avg_cycle))

    if units_produced > 0 and run_time_hours > 0:
        observed = run_time_hours / Decimal(str(units_produced))
        return max(observed, _NEUTRAL_CYCLE_TIME_FLOOR)

    return _DEFAULT_CYCLE_TIME


# --------------------------------------------------------------- helpers


def _apply_production_filters(
    q: Query,
    *,
    line_id: Optional[int],
    shift_id: Optional[int],
    product_id: Optional[int],
    work_order_id: Optional[str],
) -> Query:
    if line_id is not None:
        q = q.filter(ProductionEntry.line_id == line_id)
    if shift_id is not None:
        q = q.filter(ProductionEntry.shift_id == shift_id)
    if product_id is not None:
        q = q.filter(ProductionEntry.product_id == product_id)
    if work_order_id is not None:
        q = q.filter(ProductionEntry.work_order_id == work_order_id)
    return q


def _apply_quality_filters(q: Query, *, work_order_id: Optional[str]) -> Query:
    if work_order_id is not None:
        q = q.filter(QualityEntry.work_order_id == work_order_id)
    return q


def _apply_workorder_filters(q: Query, *, work_order_id: Optional[str]) -> Query:
    if work_order_id is not None:
        q = q.filter(WorkOrder.work_order_id == work_order_id)
    return q


# ------------------------------------------------------------------ OEE


ROLLING_WINDOW_DAYS = 90
"""Window for both alternative cycle times.

`demonstrated_best` means the best the plant has recently PROVEN it can do.
Bounding it to the same trailing window as the rolling average keeps the
benchmark current -- an all-time minimum would anchor OEE to a single good day
that may be years old and no longer representative.
"""

DEMONSTRATED_BEST_MIN_UNITS_FRACTION = Decimal("0.5")
"""A day must produce at least this fraction of the window's MEDIAN daily
output to be eligible as the demonstrated best.

Without a floor the benchmark is set by whichever day happened to run
shortest: Performance is (ideal_cycle * units) / run_time, so a FASTER ideal
cycle lowers Performance, and a part-day that made 12 units in a brisk hour
would define an unreachable standard and depress OEE for the whole period.
Half the median is deliberately generous -- it excludes partial and
interrupted days without discarding a genuinely good short week.
"""


def _per_day_cycle_times(
    db: Session,
    client_id: str,
    window_start: datetime,
    window_end: datetime,
    *,
    line_id: Optional[int],
    shift_id: Optional[int],
    product_id: Optional[int],
    work_order_id: Optional[str],
) -> list[tuple[Decimal, int]]:
    """Per-day (run_hours, units) over the window, days with output only.

    The SUMs are done in SQL and the division in Python, deliberately. Dividing
    inside the query inherits `run_time_hours`' Numeric(10, 2) type, and
    SQLAlchemy's SQLite result processor then quantises the answer to two
    decimals -- a cycle time of 0.044642 comes back as 0.04 -- while MariaDB
    has native decimal support, runs no processor, and returns the full scale.
    The same query would yield different numbers per dialect, and the SQLite
    suite would report green. Summing and dividing in Python is also what the
    weighted cycle time above already does.
    """
    day = func.date(ProductionEntry.shift_date).label("day")
    q = db.query(
        day,
        func.coalesce(func.sum(ProductionEntry.run_time_hours), 0).label("run_hours"),
        func.coalesce(func.sum(ProductionEntry.units_produced), 0).label("units"),
    ).filter(
        and_(
            ProductionEntry.client_id == client_id,
            ProductionEntry.shift_date >= window_start,
            ProductionEntry.shift_date <= window_end,
        )
    )
    q = _apply_production_filters(
        q,
        line_id=line_id,
        shift_id=shift_id,
        product_id=product_id,
        work_order_id=work_order_id,
    )
    # Grouping by the same expression that is selected keeps MariaDB's
    # ONLY_FULL_GROUP_BY satisfied; the filtering by output happens in Python.
    rows = q.group_by(day).all()

    return [
        (Decimal(str(r.run_hours)), int(r.units))
        for r in rows
        if r.units and int(r.units) > 0 and Decimal(str(r.run_hours)) > 0
    ]


def _median(values: list[int]) -> Decimal:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return Decimal(ordered[mid])
    return (Decimal(ordered[mid - 1]) + Decimal(ordered[mid])) / Decimal("2")


def alternative_cycle_times(
    db: Session,
    client_id: str,
    period_end: datetime,
    *,
    line_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    product_id: Optional[int] = None,
    work_order_id: Optional[str] = None,
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """`(rolling_90_day, demonstrated_best)` observed cycle times, or None.

    These back the `ideal_cycle_time_source` assumption. Nothing populated them
    before, so selecting `rolling_90_day_average` or `demonstrated_best`
    recorded an assumption that changed no number on any production path --
    the appearance of a decision without its substance.

    Both are ACHIEVED cycle times (run time over units), not published
    standards: the assumption exists to let a site benchmark against its own
    demonstrated rate instead of an engineering figure.

    Returns None for either when the window holds no qualifying production, so
    the caller can tell "no basis to compute this" from a real zero.
    """
    window_start = period_end - timedelta(days=ROLLING_WINDOW_DAYS)
    per_day = _per_day_cycle_times(
        db,
        client_id,
        window_start,
        period_end,
        line_id=line_id,
        shift_id=shift_id,
        product_id=product_id,
        work_order_id=work_order_id,
    )
    if not per_day:
        return None, None

    total_hours = sum((h for h, _ in per_day), Decimal("0"))
    total_units = sum(u for _, u in per_day)
    rolling = total_hours / Decimal(total_units) if total_units > 0 else None

    floor = _median([u for _, u in per_day]) * DEMONSTRATED_BEST_MIN_UNITS_FRACTION
    eligible = [(h / Decimal(u)) for h, u in per_day if Decimal(u) >= floor]
    best = min(eligible) if eligible else None

    return rolling, best


def aggregate_oee_inputs(
    db: Session,
    client_id: str,
    period_start: datetime,
    period_end: datetime,
    *,
    line_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    product_id: Optional[int] = None,
    work_order_id: Optional[str] = None,
) -> OEERawInputs:
    """Aggregate OEE raw inputs from ProductionEntry + QualityEntry rows."""

    # Units-weighted ideal cycle time: sum(cycle × units) / sum(units).
    # A simple func.avg over rows would overweight low-volume products and
    # produce Performance > 100% on heterogeneous-product aggregates (e.g.
    # 49 t-shirts at 0.15h/unit alongside 14 jackets at 0.50h/unit aggregate
    # correctly only when the cycle time is units-weighted).
    weighted_cycle_numer = func.coalesce(
        func.sum(ProductionEntry.ideal_cycle_time * ProductionEntry.units_produced),
        0,
    )
    weighted_cycle_denom = func.coalesce(func.sum(ProductionEntry.units_produced), 0)
    prod_q = db.query(
        func.coalesce(func.sum(ProductionEntry.units_produced), 0).label("units_produced"),
        func.coalesce(func.sum(ProductionEntry.run_time_hours), 0).label("run_time_hours"),
        func.coalesce(func.sum(ProductionEntry.downtime_hours), 0).label("downtime_hours"),
        func.coalesce(func.sum(ProductionEntry.setup_time_hours), 0).label("setup_time_hours"),
        func.coalesce(func.sum(ProductionEntry.maintenance_hours), 0).label("maintenance_hours"),
        func.coalesce(func.sum(ProductionEntry.defect_count), 0).label("defect_count"),
        func.coalesce(func.sum(ProductionEntry.scrap_count), 0).label("scrap_count"),
        weighted_cycle_numer.label("cycle_numer"),
        weighted_cycle_denom.label("cycle_denom"),
    ).filter(
        and_(
            ProductionEntry.client_id == client_id,
            ProductionEntry.shift_date >= period_start,
            ProductionEntry.shift_date <= period_end,
        )
    )
    prod_q = _apply_production_filters(
        prod_q,
        line_id=line_id,
        shift_id=shift_id,
        product_id=product_id,
        work_order_id=work_order_id,
    )
    p = prod_q.one()

    run_time = Decimal(str(p.run_time_hours or 0))
    downtime = Decimal(str(p.downtime_hours or 0))
    setup = Decimal(str(p.setup_time_hours or 0))
    maintenance = Decimal(str(p.maintenance_hours or 0))
    scheduled = run_time + downtime + setup + maintenance

    # Resolve the weighted average cycle time. cycle_denom is summed units;
    # when zero (no rows or all units == 0) we hand off to the fallback
    # which derives from observed rate (or the static default for empty
    # periods).
    weighted_cycle: Optional[Decimal] = None
    if p.cycle_denom and p.cycle_denom > 0:
        weighted_cycle = Decimal(str(p.cycle_numer)) / Decimal(str(p.cycle_denom))
    cycle_time = _resolve_ideal_cycle_time(
        weighted_cycle,
        int(p.units_produced or 0),
        run_time,
    )

    rework_q: Query = db.query(func.coalesce(func.sum(QualityEntry.units_reworked), 0)).filter(
        and_(
            QualityEntry.client_id == client_id,
            QualityEntry.shift_date >= period_start,
            QualityEntry.shift_date <= period_end,
        )
    )
    rework_q = _apply_quality_filters(rework_q, work_order_id=work_order_id)
    rework = rework_q.scalar() or 0

    # The two alternative cycle times the `ideal_cycle_time_source` assumption
    # selects between. Nothing populated these before, so choosing
    # `rolling_90_day_average` or `demonstrated_best` was recorded, approved
    # and reported as active while changing no number at all.
    rolling_cycle, best_cycle = alternative_cycle_times(
        db,
        client_id,
        period_end,
        line_id=line_id,
        shift_id=shift_id,
        product_id=product_id,
        work_order_id=work_order_id,
    )

    return OEERawInputs(
        scheduled_hours=scheduled,
        downtime_hours=downtime,
        setup_minutes=setup * Decimal("60"),
        scheduled_maintenance_hours=maintenance,
        units_produced=int(p.units_produced or 0),
        run_time_hours=run_time,
        ideal_cycle_time_hours=cycle_time,
        rolling_90_day_cycle_time_hours=rolling_cycle,
        demonstrated_best_cycle_time_hours=best_cycle,
        defect_count=int(p.defect_count or 0),
        scrap_count=int(p.scrap_count or 0),
        units_reworked=int(rework),
    )


# ------------------------------------------------------------------ OTD


def aggregate_otd_inputs(
    db: Session,
    client_id: str,
    period_start: datetime,
    period_end: datetime,
    *,
    work_order_id: Optional[str] = None,
    # Accepted for signature parity with the other aggregators; unused here
    # because WorkOrder rows aren't partitioned by line/shift/product.
    line_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    product_id: Optional[int] = None,
) -> OTDRawInputs:
    """
    Aggregate OTD raw inputs from completed WorkOrder rows.

    A work order is included if its `actual_delivery_date` falls within the
    period and it has both `actual_delivery_date` and `planned_ship_date`.
    `planned_start_date` anchors the lead-time denominator for delay_pct;
    when it isn't tracked (most work orders — it's only populated for the
    subset bridged to a CapacityOrder), fall back to `received_date`, which
    every work order carries. Without this fallback, the aggregate silently
    excluded almost every order — the same on-time/late orders the plain
    OTD KPI (required_date vs. actual_delivery_date, no planned_start_date
    dependency) counts just fine — starving this tile down to a
    perpetual 0% while the OEE/FPY tiles (whose aggregators don't depend on
    this field) stayed populated.

    delay_pct = (actual_delivery - planned_ship) / (planned_ship - planned_start)
    Negative = early. Zero = exactly on time.
    """

    del line_id, shift_id, product_id  # documented as accepted but inapplicable

    q = db.query(WorkOrder).filter(
        and_(
            WorkOrder.client_id == client_id,
            WorkOrder.actual_delivery_date.isnot(None),
            WorkOrder.planned_ship_date.isnot(None),
            or_(WorkOrder.planned_start_date.isnot(None), WorkOrder.received_date.isnot(None)),
            WorkOrder.actual_delivery_date >= period_start,
            WorkOrder.actual_delivery_date <= period_end,
        )
    )
    q = _apply_workorder_filters(q, work_order_id=work_order_id)
    rows = q.all()

    delays: list[OrderDelay] = []
    for wo in rows:
        actual = wo.actual_delivery_date
        planned_ship = wo.planned_ship_date
        planned_start = wo.planned_start_date or wo.received_date
        if actual is None or planned_ship is None or planned_start is None:
            continue

        lead_seconds = (planned_ship - planned_start).total_seconds()
        if lead_seconds <= 0:
            continue
        delay_seconds = (actual - planned_ship).total_seconds()
        delay_pct = Decimal(str(round(delay_seconds / lead_seconds, 4)))
        delays.append(OrderDelay(delay_pct=delay_pct, delay_classification=wo.delay_classification))

    return OTDRawInputs(orders=delays)


# ------------------------------------------------------------------ FPY


def aggregate_fpy_inputs(
    db: Session,
    client_id: str,
    period_start: datetime,
    period_end: datetime,
    *,
    work_order_id: Optional[str] = None,
    # Accepted for signature parity; QualityEntry has no line_id/shift_id/product_id.
    line_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    product_id: Optional[int] = None,
) -> FPYRawInputs:
    """Aggregate FPY raw inputs from QualityEntry rows."""

    del line_id, shift_id, product_id

    q: Query = db.query(
        func.coalesce(func.sum(QualityEntry.units_inspected), 0).label("inspected"),
        func.coalesce(func.sum(QualityEntry.units_passed), 0).label("passed"),
        func.coalesce(func.sum(QualityEntry.units_reworked), 0).label("reworked"),
    ).filter(
        and_(
            QualityEntry.client_id == client_id,
            QualityEntry.shift_date >= period_start,
            QualityEntry.shift_date <= period_end,
        )
    )
    q = _apply_quality_filters(q, work_order_id=work_order_id)
    row = q.one()

    return FPYRawInputs(
        total_inspected=int(row.inspected or 0),
        units_passed_first_time=int(row.passed or 0),
        units_reworked=int(row.reworked or 0),
    )


__all__ = [
    "aggregate_oee_inputs",
    "aggregate_otd_inputs",
    "aggregate_fpy_inputs",
]
