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
from backend.calculations.labor_hours import earned_hours, summarize_labor_hours
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

    Fix round 1 (2026-08-06, USER RULING): also returns the TRUE
    available-basis efficiency as a ratio of SUMS over this same window/scope
    (replaces an earlier average-of-averages dashboard variant that was
    live-proven wrong -- see docs/superpowers/specs/
    2026-08-05-labor-hours-accounting-design.md Sec 6):
      efficiency_available_basis = earned_hours / available_for_efficiency * 100
    `earned_hours` sums units_produced x ideal_cycle_time per entry (see
    `backend.calculations.labor_hours.earned_hours` for the ideal_cycle_time
    resolution chain and why entries lacking it are EXCLUDED, not guessed --
    `excluded_entries` surfaces that count so the ratio can't silently look
    complete). `efficiency_available_basis` is None when there's no
    attendance data in the window at all, or `available_for_efficiency` is
    <= 0 (never divide by a fabricated/zero denominator).
    """
    validate_date_range(start_date, end_date)

    result = summarize_labor_hours(db, scope.client_ids, start_date, end_date)
    earned_total, excluded_entries = earned_hours(db, scope.client_ids, start_date, end_date)

    available_total = result["totals"]["available_for_efficiency"]
    has_attendance_data = result["entry_counts"]["total"] > 0

    if not has_attendance_data or available_total <= 0:
        efficiency_available_basis = None
    else:
        efficiency_available_basis = float((earned_total / available_total * 100).quantize(Decimal("0.01")))

    response = _coerce_nested(result)
    response["earned_hours"] = float(earned_total)
    response["excluded_entries"] = excluded_entries
    response["efficiency_available_basis"] = efficiency_available_basis
    return response


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
