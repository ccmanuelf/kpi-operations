"""
D4 — Historical calibration service.

Pre-fills a SimulationConfig from real production / quality / downtime
history so a planner doesn't have to type SAM, grade %, rework %, and
demand by hand. The service outputs a dict the existing
SimulationConfig schema accepts directly, plus per-field provenance
(source table, sample size, period, confidence) so the UI can show
where each number came from.

Aggregation strategy (v1):
  - Operations come from `capacity_production_standards` (per style)
  - Per-product averages from PRODUCTION_ENTRY are applied uniformly
    to every operation of that product (we don't yet have per-op
    actuals; this is acknowledged in the `confidence` tag)
  - Demand from average units_produced per day
  - Breakdowns from DOWNTIME_ENTRY counts per machine
  - Schedule from SHIFT durations + working days in the calendar
    (or simple defaults if either is sparse)

Confidence reporting:
  - high   ≥ 14 production entries in the period (~2 weeks of data)
  - medium 5–13 entries (a week or so)
  - low    1–4 entries (single shift or two)
  - none   0 entries — field falls back to the SimPy default and is
    flagged as a `warning`
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.capacity.standards import CapacityProductionStandard
from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.product import Product
from backend.orm.production_entry import ProductionEntry
from backend.orm.shift import Shift
from backend.simulation_v2.constants import DEFAULT_HORIZON_DAYS, MAX_HORIZON_DAYS


# ---------------------------------------------------------------------------
# Confidence helpers
# ---------------------------------------------------------------------------


def _confidence_for(sample_size: int) -> str:
    """Bucket a sample-size into a label the UI can render as a chip."""
    if sample_size >= 14:
        return "high"
    if sample_size >= 5:
        return "medium"
    if sample_size >= 1:
        return "low"
    return "none"


def _source(*, table: str, sample_size: int, period_start: date, period_end: date) -> Dict[str, Any]:
    """Standard provenance dict attached to each derived field."""
    return {
        "source": table,
        "sample_size": sample_size,
        "period": f"{period_start.isoformat()} to {period_end.isoformat()}",
        "confidence": _confidence_for(sample_size),
    }


# ---------------------------------------------------------------------------
# Per-component calibration
# ---------------------------------------------------------------------------


def _calibrate_schedule(
    db: Session,
    client_id: str,
    period_start: date,
    period_end: date,
) -> Dict[str, Any]:
    """Derive ScheduleConfig from SHIFT durations + working days in the
    period. Fallbacks: 1 shift, 8 hours, 5 days/week — what a brand-new
    plant would assume."""
    shifts = (
        db.query(Shift).filter(Shift.client_id == client_id, Shift.is_active.is_(True)).order_by(Shift.shift_id).all()
    )

    def _hours(s: Shift) -> float:
        if s.start_time is None or s.end_time is None:
            return 8.0
        # SQLite stores TIME as ISO string; SQLAlchemy gives a `time` object
        st = s.start_time
        et = s.end_time
        # Convert times to minutes-since-midnight, accounting for shifts
        # that cross midnight (3rd shift 22:00 → 06:00).
        s_min = st.hour * 60 + st.minute
        e_min = et.hour * 60 + et.minute
        if e_min <= s_min:
            e_min += 24 * 60
        return round((e_min - s_min) / 60.0, 2)

    enabled = max(1, min(3, len(shifts)))
    shift_hours = [_hours(s) for s in shifts[:3]]
    while len(shift_hours) < 3:
        shift_hours.append(0.0)

    # Distinct working days in the production data window — the
    # planner's actual practice, not a calendar lookup.
    work_days_in_window = (
        db.query(func.count(func.distinct(func.date(ProductionEntry.shift_date))))
        .filter(
            ProductionEntry.client_id == client_id,
            ProductionEntry.shift_date >= datetime.combine(period_start, datetime.min.time()),
            ProductionEntry.shift_date <= datetime.combine(period_end, datetime.max.time()),
        )
        .scalar()
        or 0
    )
    period_days = max(1, (period_end - period_start).days + 1)
    weeks = max(1, period_days / 7.0)
    avg_work_days_per_week = max(1, min(7, round(work_days_in_window / weeks)))

    return {
        "shifts_enabled": enabled,
        "shift1_hours": shift_hours[0] or 8.0,
        "shift2_hours": shift_hours[1],
        "shift3_hours": shift_hours[2],
        "work_days": avg_work_days_per_week,
        "ot_enabled": False,
        "weekday_ot_hours": 0,
        "weekend_ot_days": 0,
        "weekend_ot_hours": 0,
        "_source": _source(
            table="SHIFT + PRODUCTION_ENTRY",
            sample_size=int(work_days_in_window),
            period_start=period_start,
            period_end=period_end,
        ),
    }


def _calibrate_per_product_metrics(
    db: Session,
    client_id: str,
    period_start: date,
    period_end: date,
) -> Dict[int, Dict[str, Any]]:
    """One row per product_id with grade/rework/operators/throughput
    averages. Returned as a map for fast lookup by product.
    """
    rows = (
        db.query(
            ProductionEntry.product_id,
            func.count(ProductionEntry.production_entry_id).label("n"),
            func.avg(ProductionEntry.efficiency_percentage).label("avg_eff"),
            func.avg(ProductionEntry.performance_percentage).label("avg_perf"),
            func.avg(ProductionEntry.quality_rate).label("avg_qual"),
            func.avg(ProductionEntry.employees_assigned).label("avg_emps"),
            func.sum(ProductionEntry.units_produced).label("total_units"),
            func.sum(ProductionEntry.defect_count).label("total_defects"),
            func.sum(ProductionEntry.rework_count).label("total_rework"),
            func.sum(ProductionEntry.scrap_count).label("total_scrap"),
        )
        .filter(
            ProductionEntry.client_id == client_id,
            ProductionEntry.shift_date >= datetime.combine(period_start, datetime.min.time()),
            ProductionEntry.shift_date <= datetime.combine(period_end, datetime.max.time()),
        )
        .group_by(ProductionEntry.product_id)
        .all()
    )

    out: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        n = int(r.n or 0)
        total_units = int(r.total_units or 0)
        out[int(r.product_id)] = {
            "n": n,
            "grade_pct": round(float(r.avg_eff or 100), 2),
            "performance_pct": round(float(r.avg_perf or 100), 2),
            "quality_rate": round(float(r.avg_qual or 100), 2),
            "operators": max(1, int(round(float(r.avg_emps or 1)))),
            "total_units": total_units,
            "rework_pct": (round((int(r.total_rework or 0) / total_units) * 100, 2) if total_units > 0 else 0.0),
            "scrap_pct": (round((int(r.total_scrap or 0) / total_units) * 100, 2) if total_units > 0 else 0.0),
        }
    return out


def _calibrate_breakdowns(
    db: Session,
    client_id: str,
    period_start: date,
    period_end: date,
) -> List[Dict[str, Any]]:
    """Derive per-machine_tool breakdown_pct from DOWNTIME_ENTRY events
    in the period.

    Calculation (a deliberately rough first pass):
        breakdown_pct = (events_for_machine / total_events) × scale
    where `scale = clamp(total_minutes / period_minutes, 0..10)` so a
    plant with very rare downtime stays under 1% and one with chronic
    downtime saturates near 10%. Engineering teams will tune this in
    practice; calibration is a starting point, not gospel.
    """
    rows = (
        db.query(
            DowntimeEntry.machine_id,
            func.count(DowntimeEntry.downtime_entry_id).label("n"),
            func.sum(DowntimeEntry.downtime_duration_minutes).label("total_min"),
        )
        .filter(
            DowntimeEntry.client_id == client_id,
            DowntimeEntry.shift_date >= datetime.combine(period_start, datetime.min.time()),
            DowntimeEntry.shift_date <= datetime.combine(period_end, datetime.max.time()),
            DowntimeEntry.machine_id.isnot(None),
        )
        .group_by(DowntimeEntry.machine_id)
        .all()
    )

    out: List[Dict[str, Any]] = []
    period_days = max(1, (period_end - period_start).days + 1)
    period_minutes = period_days * 8 * 60  # nominal: 8h/day, single shift

    for r in rows:
        total_min = int(r.total_min or 0)
        ratio = max(0.0, min(10.0, (total_min / period_minutes) * 100))
        out.append(
            {
                "machine_tool": r.machine_id,
                "breakdown_pct": round(ratio, 2),
                "_event_count": int(r.n or 0),
            }
        )
    return out


def _build_operations(
    db: Session,
    client_id: str,
    products: List[Product],
    per_product: Dict[int, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """For each product the client has standards for, emit one
    SimulationConfig.operations entry per (operation in the standard).

    Per-op fields:
      - sam_min from capacity_production_standards.sam_minutes
      - product/step/operation/machine_tool from the standard
      - operators/grade_pct/rework_pct from the per-product averages
        (uniform across that product's operations — known limitation
        called out in the response payload)
    """
    out: List[Dict[str, Any]] = []
    for prod in products:
        standards = (
            db.query(CapacityProductionStandard)
            .filter(
                CapacityProductionStandard.client_id == client_id,
                CapacityProductionStandard.style_model == prod.product_code,
            )
            .order_by(CapacityProductionStandard.id)
            .all()
        )
        if not standards:
            continue

        m = per_product.get(int(prod.product_id), {})
        product_label = prod.product_name or prod.product_code
        for step_idx, std in enumerate(standards, start=1):
            machine_tool = std.department or std.operation_code or "Generic"
            out.append(
                {
                    "product": product_label,
                    "step": step_idx,
                    "operation": std.operation_name or std.operation_code or f"Op {step_idx}",
                    "machine_tool": machine_tool,
                    "sam_min": float(std.sam_minutes or 1.0),
                    "operators": m.get("operators", 1),
                    "variability": "triangular",
                    "rework_pct": m.get("rework_pct", 0.0),
                    "grade_pct": m.get("grade_pct", 100.0),
                    "fpd_pct": 15.0,  # no historical source for FPD; SimPy default
                    "sequence": std.department or "Assembly",
                    "grouping": std.operation_code or "",
                }
            )
    return out


def _build_demands(
    db: Session,
    client_id: str,
    products: List[Product],
    per_product: Dict[int, Dict[str, Any]],
    period_start: date,
    period_end: date,
    work_days_per_week: int,
) -> List[Dict[str, Any]]:
    """One demand entry per product.

    daily_demand  = avg(units / production day)  — pieces a single
                    working day produces, derived from total units
                    divided by entries (entries ≈ shift-days the
                    plant ran).
    weekly_demand = daily_demand × work_days_per_week — keeps the
                    two fields internally consistent so the engine
                    (which treats them as alternative inputs to the
                    same target) doesn't get conflicting signals.

    Falls back to None when there's no production history; the engine
    accepts None for either field as long as the other is set, and the
    UI shows the warning banner when both are missing.
    """
    out: List[Dict[str, Any]] = []
    for prod in products:
        m = per_product.get(int(prod.product_id), {})
        total_units = int(m.get("total_units", 0))
        n_entries = int(m.get("n", 0))
        # Use distinct production days as the divisor so a 2-week period
        # with 5 days of production gives the right per-day rate.
        days_with_prod = max(1, n_entries) if n_entries > 0 else 1
        avg_per_day = round(total_units / days_with_prod) if days_with_prod else 0
        product_label = prod.product_name or prod.product_code
        daily = max(1, avg_per_day) if total_units else None
        weekly = (daily * max(1, work_days_per_week)) if daily else None
        out.append(
            {
                "product": product_label,
                "bundle_size": 10,
                "daily_demand": daily,
                "weekly_demand": weekly,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


def calibrate_from_history(
    db: Session,
    client_id: str,
    period_start: date,
    period_end: date,
) -> Dict[str, Any]:
    """Top-level entrypoint. Returns a dict with:

        {
          "config": SimulationConfig-shaped dict,
          "sources": {field_path: {source, sample_size, period, confidence}},
          "warnings": [...],
          "period": {"start": ..., "end": ..., "days": ...},
          "client_id": ...,
        }

    Caller (the route) wraps this in a Pydantic schema for the wire.
    """
    if period_end < period_start:
        # Swap silently — same UX policy as Run-6's date-range guard.
        period_start, period_end = period_end, period_start

    # Per-product KPI rollups + the source provenance for each
    per_product = _calibrate_per_product_metrics(db, client_id, period_start, period_end)

    # Pull products that have at least one standard OR appeared in the
    # period's production. Order: standards first (they define the
    # operations list), then any production-only products at the end.
    standard_codes: Set[str] = {
        r.style_model
        for r in db.query(CapacityProductionStandard.style_model)
        .filter(CapacityProductionStandard.client_id == client_id)
        .distinct()
    }
    if standard_codes:
        products_with_data = (
            db.query(Product)
            .filter(
                Product.client_id == client_id,
                Product.product_code.in_(standard_codes),
            )
            .order_by(Product.product_id)
            .all()
        )
    else:
        # No standards yet → no products to calibrate against (the route
        # will surface a warning in the response payload).
        products_with_data = []

    # Compute schedule first — _build_demands needs work_days to keep
    # daily/weekly internally consistent.
    schedule = _calibrate_schedule(db, client_id, period_start, period_end)
    operations = _build_operations(db, client_id, products_with_data, per_product)
    demands = _build_demands(
        db,
        client_id,
        products_with_data,
        per_product,
        period_start,
        period_end,
        work_days_per_week=int(schedule.get("work_days", 5)),
    )
    breakdowns = _calibrate_breakdowns(db, client_id, period_start, period_end)

    # Provenance map — flat field paths with source/sample_size info.
    sources: Dict[str, Any] = {}
    for prod in products_with_data:
        m = per_product.get(int(prod.product_id), {})
        n = int(m.get("n", 0))
        product_label = prod.product_name or prod.product_code
        sources[f"products.{product_label}"] = _source(
            table="PRODUCTION_ENTRY",
            sample_size=n,
            period_start=period_start,
            period_end=period_end,
        )
    sources["schedule"] = schedule.pop(
        "_source",
        _source(
            table="SHIFT",
            sample_size=0,
            period_start=period_start,
            period_end=period_end,
        ),
    )
    if breakdowns:
        sources["breakdowns"] = _source(
            table="DOWNTIME_ENTRY",
            sample_size=sum(b.pop("_event_count", 0) for b in breakdowns),
            period_start=period_start,
            period_end=period_end,
        )

    warnings: List[str] = []
    if not operations:
        warnings.append(
            "No production standards found for this client. "
            "Calibration produced an empty operations list — define "
            "standards in Capacity Planning before re-calibrating."
        )
    if not demands or all(d.get("daily_demand") in (None, 0) for d in demands):
        warnings.append(
            "No production history in the period. Demands fell back to "
            "default (zero / null). Widen the period or load real "
            "production data first."
        )
    fpd_count = sum(1 for op in operations if op.get("fpd_pct") == 15.0)
    if fpd_count:
        warnings.append(
            f"FPD% (Fatigue & Personal Delay) was set to the SimPy "
            f"default (15.0%) on {fpd_count} operation(s). The platform "
            "doesn't yet track FPD as a historical metric; tune by hand "
            "in the Operations tab if this default doesn't fit."
        )

    config: Dict[str, Any] = {
        "operations": operations,
        "schedule": schedule,
        "demands": demands,
        "breakdowns": breakdowns,
        "mode": "demand-driven",
        # Engine caps the horizon (MAX_HORIZON_DAYS, currently 7). The
        # calibration period can span months; the horizon is just how
        # many days the SimPy engine simulates per run, not the data
        # window we calibrated from.
        "horizon_days": min(
            MAX_HORIZON_DAYS,
            max(1, (period_end - period_start).days + 1),
        ),
    }

    return {
        "client_id": client_id,
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "days": (period_end - period_start).days + 1,
        },
        "config": config,
        "sources": sources,
        "warnings": warnings,
    }
