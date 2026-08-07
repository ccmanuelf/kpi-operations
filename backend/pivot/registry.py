"""Declarative dataset registry for the pivot engine (Cycle 4 spec §3–§4).

A dataset is either SQL-path (engine builds one GROUP BY (day, group) query
from Sum/Count exprs) or hook-path (fetch returns the same per-(day, group)
component rows from existing Python calculations). Ratio/Share measures name
their components; the engine computes them from SUMS — ratio-of-sums is
structural (see test_registry_guard.py).
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from sqlalchemy import case, func

from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.hold_entry import HoldEntry
from backend.orm.product import Product
from backend.orm.production_entry import ProductionEntry
from backend.orm.production_line import ProductionLine
from backend.orm.quality_entry import QualityEntry
from backend.orm.work_order import WorkOrder
from backend.pivot.hooks import fetch_delivery, fetch_holds, fetch_labor


@dataclass(frozen=True)
class Sum:
    expr: Any


@dataclass(frozen=True)
class Count:
    pass


@dataclass(frozen=True)
class Component:
    """A summed component produced by a fetch hook (no SQL expr) -- Ratio/Share
    measures on hook datasets reference these instead of Sum/Count."""


@dataclass(frozen=True)
class Ratio:
    numerator: str
    denominator: str
    scale: float = 100.0


@dataclass(frozen=True)
class Share:
    of: str


@dataclass(frozen=True)
class GroupBy:
    expr: Any
    joins: tuple = ()


@dataclass(frozen=True)
class Dataset:
    name: str
    model: Any
    date_column: Any
    client_column: Any
    group_bys: dict[str, GroupBy]
    measures: dict[str, Any]
    joins: tuple = ()
    base_filters: tuple = ()
    fetch: Optional[Callable] = None


# --- production -------------------------------------------------------------
# earned hours mirror backend/calculations/labor_hours.py::earned_hours:
# entry ideal_cycle_time, else product default; neither -> EXCLUDED (counted,
# never guessed). Product join is outer so entries without a product row still
# aggregate (they count as excluded).
_ict = func.coalesce(ProductionEntry.ideal_cycle_time, Product.ideal_cycle_time)

_PRODUCTION = Dataset(
    name="production",
    model=ProductionEntry,
    date_column=ProductionEntry.shift_date,
    client_column=ProductionEntry.client_id,
    joins=((Product, ProductionEntry.product_id == Product.product_id),),
    group_bys={
        "client": GroupBy(ProductionEntry.client_id),
        "line": GroupBy(
            ProductionLine.line_name,
            joins=((ProductionLine, ProductionEntry.line_id == ProductionLine.line_id),),
        ),
        "product": GroupBy(Product.product_name),
    },
    measures={
        "units": Sum(ProductionEntry.units_produced),
        "earned_hours": Sum(case((_ict.isnot(None), ProductionEntry.units_produced * _ict), else_=0)),
        "excluded_entries": Sum(case((_ict.is_(None), 1), else_=0)),
        "run_hours": Sum(ProductionEntry.run_time_hours),
        "downtime_hours": Sum(func.coalesce(ProductionEntry.downtime_hours, 0)),
        "operators": Sum(func.coalesce(ProductionEntry.employees_present, 0)),
        "efficiency_pct": Ratio("earned_hours", "run_hours"),
    },
)

# --- downtime ---------------------------------------------------------------
_DOWNTIME = Dataset(
    name="downtime",
    model=DowntimeEntry,
    date_column=DowntimeEntry.shift_date,
    client_column=DowntimeEntry.client_id,
    group_bys={
        "client": GroupBy(DowntimeEntry.client_id),
        "category": GroupBy(func.coalesce(DowntimeEntry.root_cause_category, "uncategorized")),
        "reason": GroupBy(DowntimeEntry.downtime_reason),
        "line": GroupBy(
            ProductionLine.line_name,
            joins=((ProductionLine, DowntimeEntry.line_id == ProductionLine.line_id),),
        ),
    },
    measures={
        "downtime_hours": Sum(DowntimeEntry.downtime_duration_minutes / 60.0),
        "events": Count(),
        "share_of_window_pct": Share(of="downtime_hours"),
    },
)

# --- quality ----------------------------------------------------------------
_QUALITY = Dataset(
    name="quality",
    model=QualityEntry,
    date_column=QualityEntry.shift_date,
    client_column=QualityEntry.client_id,
    group_bys={
        "client": GroupBy(QualityEntry.client_id),
        "style": GroupBy(
            WorkOrder.style_model,
            joins=((WorkOrder, QualityEntry.work_order_id == WorkOrder.work_order_id),),
        ),
    },
    measures={
        "inspected": Sum(QualityEntry.units_inspected),
        "passed": Sum(QualityEntry.units_passed),
        "defective": Sum(QualityEntry.units_defective),
        "defects": Sum(QualityEntry.total_defects_count),
        "fpy_pct": Ratio("passed", "inspected"),
    },
)

# --- holds (hook path) -------------------------------------------------------
# hold_days/avg_days_per_hold moved off the SQL path (validation finding F3):
# total_hold_duration_hours is NULL until a hold resumes, so a SQL SUM
# coalesces every still-open hold to 0, indistinguishable from a hold that
# resolved in a minute. fetch_holds uses the recorded duration for resolved
# holds and age-to-date for active ones -- see backend/pivot/hooks.py.
_HOLDS = Dataset(
    name="holds",
    model=HoldEntry,
    date_column=HoldEntry.hold_date,
    client_column=HoldEntry.client_id,
    fetch=fetch_holds,
    group_bys={
        "client": GroupBy(None),
        "reason_category": GroupBy(None),
        "reason": GroupBy(None),
    },
    measures={
        "holds": Component(),
        "hold_days": Component(),
        "avg_days_per_hold": Ratio("hold_days", "holds", scale=1.0),
    },
)

# --- labor (hook path) -------------------------------------------------------
# Labor semantics (allocation category sets, effective-class fallback,
# unsplit transparency) live in backend/calculations/labor_hours.py and are
# NOT SQL-expressible without duplicating that logic -- fetch_labor reuses it
# verbatim (see test_hooks_golden.py for the cross-source golden).
_LABOR = Dataset(
    name="labor",
    model=AttendanceEntry,
    date_column=AttendanceEntry.shift_date,
    client_column=AttendanceEntry.client_id,
    fetch=fetch_labor,
    group_bys={
        "client": GroupBy(AttendanceEntry.client_id),
        "labor_class": GroupBy(None),
    },
    measures={
        "scheduled": Component(),
        "actual": Component(),
        "normal": Component(),
        "double": Component(),
        "triple": Component(),
        "unsplit_actual": Component(),
        "billed": Component(),
        "available_for_efficiency": Component(),
        "earned_hours": Component(),
        "excluded_entries": Component(),
        # earned_hours is never produced when group_by == "labor_class"
        # (production rows carry no labor class) -- the engine omits this
        # ratio entirely in that case rather than emitting a spurious 0/None.
        "efficiency_available_basis": Ratio("earned_hours", "available_for_efficiency"),
    },
)

# --- delivery (hook path) ----------------------------------------------------
# Delivery semantics (delivered-orders basis: any status, date-inference
# chain, justified-late) live in backend/calculations/otd.py::calculate_true_otd
# -- fetch_delivery mirrors its `standard_otd` counting rules verbatim (see
# test_hooks_golden.py).
_DELIVERY = Dataset(
    name="delivery",
    model=WorkOrder,
    date_column=WorkOrder.actual_delivery_date,
    client_column=WorkOrder.client_id,
    fetch=fetch_delivery,
    group_bys={
        "client": GroupBy(WorkOrder.client_id),
        "style": GroupBy(WorkOrder.style_model),
        "delay_reason": GroupBy(WorkOrder.justified_delay_reason),
    },
    measures={
        "delivered": Component(),
        "on_time": Component(),
        "justified_late": Component(),
        "net_on_time": Component(),
        "otd_gross_pct": Ratio("on_time", "delivered"),
        "otd_net_pct": Ratio("net_on_time", "delivered"),
    },
)

DATASETS: dict[str, Dataset] = {
    "production": _PRODUCTION,
    "downtime": _DOWNTIME,
    "quality": _QUALITY,
    "holds": _HOLDS,
    "labor": _LABOR,
    "delivery": _DELIVERY,
}
