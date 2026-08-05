"""
KPI Calculation Routes

Core KPI calculation endpoints and the basic dashboard summary.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Optional
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from backend.utils.logging_utils import get_module_logger
from backend.database import get_db
from backend.schemas.production import KPICalculationResponse
from backend.services.production_crud_service import (
    get_entry as get_production_entry,
    get_daily_production_summary as get_daily_summary,
)
from backend.calculations.efficiency import calculate_efficiency
from backend.calculations.labor_hours import summarize_labor_hours
from backend.calculations.performance import calculate_performance, calculate_quality_rate
from backend.auth.jwt import ClientScope, get_current_user, resolve_client_scope
from backend.orm.user import User
from backend.orm.product import Product

logger = get_module_logger(__name__)

calculations_router = APIRouter(prefix="/api/kpi", tags=["KPI Calculations"])


@calculations_router.get("/calculate/{entry_id}", response_model=KPICalculationResponse)
def calculate_kpis(entry_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Any:
    """
    Calculate KPIs for a production entry.

    Returns efficiency, performance, quality rate, and ideal cycle time
    for the specified production entry.

    SECURITY: Requires authentication; client access verified via get_production_entry.
    """
    entry = get_production_entry(db, entry_id, current_user)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Production entry {entry_id} not found")

    product = db.query(Product).filter(Product.product_id == entry.product_id).first()

    efficiency, ideal_time, was_inferred = calculate_efficiency(db, entry, product)
    performance, _, _ = calculate_performance(db, entry, product)
    quality = calculate_quality_rate(entry)

    return KPICalculationResponse(
        entry_id=entry_id,
        efficiency_percentage=efficiency,
        performance_percentage=performance,
        quality_rate=quality,
        ideal_cycle_time_used=ideal_time,
        was_inferred=was_inferred,
        calculation_timestamp=datetime.now(tz=timezone.utc),
    )


@calculations_router.get("/dashboard")
def get_kpi_dashboard(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    """
    Get KPI dashboard data.

    Returns daily summary metrics for the given date range and optional client filter.
    Defaults to the last 30 days if no dates are provided.

    SECURITY: Requires authentication; client access enforced in get_daily_summary.
    `scope` (additive) is used ONLY to resolve `client_ids` for the
    `efficiency_available_basis` enrichment below -- it does not alter the
    pre-existing `get_daily_summary` call or its authorization behavior.
    """
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    daily_summary = get_daily_summary(db, current_user, start_date, end_date, client_id=client_id)

    # --- Task 3 (Cycle 3 PR-B), additive: efficiency_available_basis ---
    # `avg_efficiency` above is the average of ProductionEntry.efficiency_percentage,
    # each of which was computed at write time (backend/calculations/efficiency.py)
    # as earned_hours / (employees_assigned * scheduled_hours) * 100 -- i.e. on a
    # SCHEDULED-hours basis. We don't have per-entry earned_hours here (the daily
    # summary only carries the averaged percentage), so we re-express that SAME
    # average onto an AVAILABLE-hours basis by rescaling with the ratio of Task 1's
    # (`summarize_labor_hours`) own "scheduled" and "available_for_efficiency"
    # totals for the identical window/scope:
    #   efficiency_available_basis = avg_efficiency * (scheduled / available)
    # which is algebraically avg_efficiency's implied numerator (earned_hours),
    # held constant, divided by "available" instead of "scheduled":
    #   (earned / scheduled * 100) * (scheduled / available) == earned / available * 100
    # Conservative: zero AttendanceEntry rows in the window -> None (never
    # fabricate a denominator). Entries with no allocations default `available`
    # to `actual` (Task 1's `available_for_efficiency_hours`), which collapses
    # this to the entries' actual-hours-basis efficiency, per the conservative
    # default documented in Task 1/PR-A.
    labor_summary = summarize_labor_hours(db, scope.client_ids, start_date, end_date)
    scheduled_total = labor_summary["totals"]["scheduled"]
    available_total = labor_summary["totals"]["available_for_efficiency"]
    has_attendance_data = labor_summary["entry_counts"]["total"] > 0

    for row in daily_summary:
        if not has_attendance_data or available_total <= 0:
            row["efficiency_available_basis"] = None
            continue
        avg_efficiency_decimal = Decimal(str(row["avg_efficiency"]))
        available_basis = (avg_efficiency_decimal * scheduled_total / available_total).quantize(Decimal("0.01"))
        row["efficiency_available_basis"] = float(available_basis)

    return daily_summary
