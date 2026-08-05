"""
KPI Labor Hours Routes

Exposes Task 1's `summarize_labor_hours` DB aggregation (backend/calculations/
labor_hours.py) as GET /api/kpi/labor-hours.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.jwt import ClientScope, get_current_user, resolve_client_scope
from backend.calculations.labor_hours import summarize_labor_hours
from backend.database import get_db
from backend.orm.user import User
from backend.utils.date_range import validate_date_range
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

labor_hours_router = APIRouter(prefix="/api/kpi", tags=["KPI Calculations"])


@labor_hours_router.get("/labor-hours")
def get_labor_hours_summary(
    start_date: date,
    end_date: date,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    """Summarize labor hours (scheduled/actual/OT-split/billed/available-for-
    efficiency) for AttendanceEntry rows with shift_date in [start_date, end_date].

    `client_id` is resolved by `resolve_client_scope` into `scope`: an
    unauthorized explicit client_id -> 403. With no client_id, scoped users
    default to their assigned client(s) and admin/poweruser default to all
    clients. `scope.client_ids` is passed straight through to
    `summarize_labor_hours` (None = all clients) -- never `scope.as_single()`,
    which would 400 a leader assigned to more than one client (the #144
    regression class).
    """
    validate_date_range(start_date, end_date)

    result = summarize_labor_hours(db, scope.client_ids, start_date, end_date)
    return _coerce_nested(result)


def _coerce_nested(obj: Any) -> Any:
    """Recursively coerce Decimal leaves to float so FastAPI's JSON encoder
    emits numbers, not strings -- nested variant of otd.py's
    `_coerce_decimal_leaves` (regression of the formally-eradicated #145
    Decimal-as-string class), needed here because `summarize_labor_hours`'s
    result nests dicts (by_labor_class, by_category) rather than being flat."""
    if isinstance(obj, dict):
        return {key: _coerce_nested(value) for key, value in obj.items()}
    if isinstance(obj, Decimal):
        return float(obj)
    return obj
