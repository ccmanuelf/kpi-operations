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

from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.hold_entry import HoldEntry
from backend.orm.product import Product
from backend.orm.production_entry import ProductionEntry
from backend.orm.production_line import ProductionLine
from backend.orm.quality_entry import QualityEntry
from backend.orm.work_order import WorkOrder


@dataclass(frozen=True)
class Sum:
    expr: Any


@dataclass(frozen=True)
class Count:
    pass


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

# --- holds ------------------------------------------------------------------
_HOLDS = Dataset(
    name="holds",
    model=HoldEntry,
    date_column=HoldEntry.hold_date,
    client_column=HoldEntry.client_id,
    base_filters=(HoldEntry.hold_date.isnot(None),),
    group_bys={
        "client": GroupBy(HoldEntry.client_id),
        "reason_category": GroupBy(func.coalesce(HoldEntry.hold_reason_category, "uncategorized")),
        "reason": GroupBy(func.coalesce(HoldEntry.hold_reason, "uncategorized")),
    },
    measures={
        "holds": Count(),
        "hold_days": Sum(func.coalesce(HoldEntry.total_hold_duration_hours, 0) / 24.0),
        "avg_days_per_hold": Ratio("hold_days", "holds", scale=1.0),
    },
)

DATASETS: dict[str, Dataset] = {
    "production": _PRODUCTION,
    "downtime": _DOWNTIME,
    "quality": _QUALITY,
    "holds": _HOLDS,
}
