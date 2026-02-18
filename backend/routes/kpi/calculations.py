"""
KPI Calculation Routes

Core KPI calculation endpoints and the basic dashboard summary.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime, timedelta, timezone

from backend.utils.logging_utils import get_module_logger
from backend.database import get_db
from backend.models.production import KPICalculationResponse
from backend.crud.production import get_production_entry, get_daily_summary
from backend.calculations.efficiency import calculate_efficiency
from backend.calculations.performance import calculate_performance, calculate_quality_rate
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.schemas.product import Product

logger = get_module_logger(__name__)

calculations_router = APIRouter(prefix="/api/kpi", tags=["KPI Calculations"])


@calculations_router.get("/calculate/{entry_id}", response_model=KPICalculationResponse)
def calculate_kpis(entry_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
):
    """
    Get KPI dashboard data.

    Returns daily summary metrics for the given date range and optional client filter.
    Defaults to the last 30 days if no dates are provided.

    SECURITY: Requires authentication; client access enforced in get_daily_summary.
    """
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    return get_daily_summary(db, current_user, start_date, end_date, client_id=client_id)
