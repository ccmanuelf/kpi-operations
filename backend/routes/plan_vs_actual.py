"""
Plan vs Actual API Routes
Compare capacity planning orders against actual production data.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import date

from backend.utils.logging_utils import get_module_logger
from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.orm.user import User
from backend.services.plan_vs_actual_service import (
    get_plan_vs_actual,
    get_plan_vs_actual_summary,
)

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/plan-vs-actual", tags=["Plan vs Actual"])


@router.get("", response_model=None)
def plan_vs_actual(
    client_id: Optional[str] = Query(None, description="Filter by client"),
    start_date: Optional[date] = Query(None, description="Filter by required_date start"),
    end_date: Optional[date] = Query(None, description="Filter by required_date end"),
    line_id: Optional[int] = Query(None, description="Filter production by line_id (integer)"),
    status: Optional[str] = Query(None, description="Filter by capacity order status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Get plan vs actual comparison for capacity orders."""
    logger.info(
        "Plan vs actual requested by user=%s, client=%s",
        current_user.username,
        client_id,
    )
    return get_plan_vs_actual(db, current_user, client_id, start_date, end_date, line_id, status)


@router.get("/summary", response_model=None)
def plan_vs_actual_summary(
    client_id: Optional[str] = Query(None, description="Filter by client"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get aggregate summary of plan vs actual across all active orders."""
    logger.info("Plan vs actual summary requested by user=%s", current_user.username)
    return get_plan_vs_actual_summary(db, current_user, client_id)
