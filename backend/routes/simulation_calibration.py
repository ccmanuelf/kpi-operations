"""
D4 — Historical calibration route.

    GET /api/v2/simulation/calibration?client_id=...&period_start=...&period_end=...

Returns a SimulationConfig-shaped dict pre-filled from real production,
quality, downtime, and shift history for the given window, plus
per-field provenance the UI uses to render confidence chips.

Permissions match the rest of `/api/v2/simulation/*`: planners and
above (leader / supervisor / poweruser / admin). Operators can run
production but they don't author scenarios, so they don't get the
"pre-fill from history" capability either.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.orm.user import User
from backend.schemas.simulation_calibration import CalibrationResponse
from backend.services.simulation_calibration import calibrate_from_history
from backend.utils.date_range import validate_date_range
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(
    prefix="/api/v2/simulation",
    tags=["simulation-v2-calibration"],
)


_WRITE_ROLES = {"admin", "ADMIN", "poweruser", "leader", "supervisor"}


def _check_calibration_permission(user: User) -> None:
    """Calibration is a planner action (it pre-fills a scenario form)
    so it shares the scenario write-permission gate."""
    if (user.role or "") not in _WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Calibration requires leader, supervisor, poweruser, or " "admin role"),
        )


def _allowed_client_ids(user: User) -> Optional[Set[str]]:
    """Return None for unrestricted (admin/poweruser); otherwise the set
    of client_ids parsed from `client_id_assigned` (comma-separated).

    Mirrors the `_resolve_allowed_clients` helper used by the scenarios
    CRUD layer so calibration honours the same tenant fence.
    """
    role = (user.role or "").lower()
    if role in {"admin", "poweruser"}:
        return None
    raw = (user.client_id_assigned or "").strip()
    if not raw:
        # Belt-and-braces: a non-admin user with no client assignment
        # gets an empty allow-set, not a None (which would mean "all").
        return set()
    return {chunk.strip() for chunk in raw.split(",") if chunk.strip()}


@router.get("/calibration", response_model=CalibrationResponse)
def calibrate_endpoint(
    client_id: str = Query(..., description="Client to calibrate (tenant fence)"),
    period_start: Optional[date] = Query(
        None,
        description=(
            "Inclusive start of the calibration window. Defaults to " "30 days before period_end (or 30 days ago)."
        ),
    ),
    period_end: Optional[date] = Query(
        None,
        description="Inclusive end of the calibration window. Defaults to today.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Pre-fill a SimulationConfig from production / quality / downtime
    history.

    The endpoint is read-only — it never writes calibration results to
    the DB. A planner gets the dict back, tweaks it in the UI, and
    saves it as a scenario via `POST /scenarios` if they want to
    persist it.
    """
    _check_calibration_permission(current_user)

    allowed = _allowed_client_ids(current_user)
    if allowed is not None and client_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Client {client_id!r} is not in your allowed client list",
        )

    today = date.today()
    if period_end is None:
        period_end = today
    if period_start is None:
        period_start = period_end - timedelta(days=30)

    validate_date_range(
        period_start,
        period_end,
        start_field="period_start",
        end_field="period_end",
    )

    payload = calibrate_from_history(db, client_id, period_start, period_end)
    logger.info(
        "Calibration: client=%s window=%s..%s ops=%d demands=%d warnings=%d by=%s",
        client_id,
        period_start.isoformat(),
        period_end.isoformat(),
        len(payload["config"].get("operations", [])),
        len(payload["config"].get("demands", [])),
        len(payload.get("warnings", [])),
        current_user.username,
    )
    return payload
