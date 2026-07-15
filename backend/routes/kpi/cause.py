"""Dispatching endpoint for data-driven KPI cause analysis (SP2)."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.orm.user import User
from backend.services import kpi_cause_service as svc

cause_router = APIRouter(prefix="/api/kpi", tags=["KPI Calculations"])

# Real-driver metrics -> their driver function. Fallback metrics are absent here.
_DRIVERS: dict[str, Callable[[Session, Optional[str], date_cls], Any]] = {
    "quality": svc.top_defect_type,
    "ppm": svc.top_defect_type,
    "availability": svc.top_downtime_reason,
    "absenteeism": svc.top_absence_type,
    "otd": svc.late_work_orders,
    "wipAging": svc.oldest_active_hold,
    "oee": svc.oee_dominant_loss,
}
_FALLBACK_METRICS = {"efficiency", "performance", "throughput"}
_ALL_METRICS = set(_DRIVERS) | _FALLBACK_METRICS


@cause_router.get("/{metric}/cause")
def get_kpi_cause(
    metric: str,
    date: date_cls,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if metric not in _ALL_METRICS:
        raise HTTPException(status_code=422, detail=f"Unknown metric: {metric}")

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    empty = {
        "date": date.isoformat(),
        "metric": metric,
        "kind": None,
        "factor": None,
        "value": None,
        "unit": "",
        "share": None,
    }

    driver = _DRIVERS.get(metric)
    if driver is None:  # fallback metric -> keep SP1 hint on the frontend
        return empty

    result = driver(db, effective_client_id, date)
    if result is None:
        return empty
    return {
        "date": date.isoformat(),
        "metric": metric,
        "kind": result.kind,
        "factor": result.factor,
        "value": result.value,
        "unit": result.unit,
        "share": result.share,
    }
