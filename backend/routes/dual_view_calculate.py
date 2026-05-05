"""
Dual-view on-demand calculation endpoints — Phase 4c.

Three POST endpoints, one per dual-view service. Each accepts raw inputs in
the request body, runs both standard and site_adjusted modes, persists a
METRIC_CALCULATION_RESULT row, and returns its `result_id`. The frontend
inspector then loads that row via `GET /api/metrics/results/{id}`.

Tenant isolation: `verify_client_access` is enforced. Any authenticated
user may trigger a calculation for a client they have access to — the
calculation itself is read-only over the assumption registry; the only
write is the persisted result row, which records `calculated_by` for audit.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.middleware.client_auth import verify_client_access
from backend.orm.user import User
from backend.services.dual_view.aggregators import (
    aggregate_fpy_inputs,
    aggregate_oee_inputs,
    aggregate_otd_inputs,
)
from backend.services.dual_view.fpy_service import FPYCalculationService, FPYRawInputs
from backend.services.dual_view.oee_service import OEECalculationService, OEERawInputs
from backend.services.dual_view.otd_service import (
    OTDCalculationService,
    OTDRawInputs,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/metrics/calculate", tags=["Dual-View Calculations"])


class CalculateRequestBase(BaseModel):
    client_id: str
    period_start: datetime
    period_end: datetime


class OEECalculateRequest(CalculateRequestBase):
    raw_inputs: OEERawInputs


class OTDCalculateRequest(CalculateRequestBase):
    raw_inputs: OTDRawInputs


class FPYCalculateRequest(CalculateRequestBase):
    raw_inputs: FPYRawInputs


class CalculateResponse(BaseModel):
    result_id: int
    metric_name: str
    standard_value: str
    site_adjusted_value: str
    delta: float | None
    delta_pct: float | None
    assumptions_applied_count: int


def _validate_period(period_start: datetime, period_end: datetime) -> None:
    if period_start > period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_start must be on or before period_end",
        )


@router.post("/oee", response_model=CalculateResponse, status_code=status.HTTP_201_CREATED)
def calculate_oee_endpoint(
    body: OEECalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalculateResponse:
    verify_client_access(current_user, body.client_id)
    _validate_period(body.period_start, body.period_end)

    result = OEECalculationService(db, current_user).calculate(
        client_id=body.client_id,
        period_start=body.period_start,
        period_end=body.period_end,
        raw_inputs=body.raw_inputs,
        persist=True,
    )
    assert result.result_id is not None  # persist=True guarantees this
    return CalculateResponse(
        result_id=result.result_id,
        metric_name=result.metric_name,
        standard_value=str(result.standard_value),
        site_adjusted_value=str(result.site_adjusted_value),
        delta=result.delta,
        delta_pct=result.delta_pct,
        assumptions_applied_count=len(result.assumptions_applied),
    )


@router.post("/otd", response_model=CalculateResponse, status_code=status.HTTP_201_CREATED)
def calculate_otd_endpoint(
    body: OTDCalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalculateResponse:
    verify_client_access(current_user, body.client_id)
    _validate_period(body.period_start, body.period_end)

    result = OTDCalculationService(db, current_user).calculate(
        client_id=body.client_id,
        period_start=body.period_start,
        period_end=body.period_end,
        raw_inputs=body.raw_inputs,
        persist=True,
    )
    assert result.result_id is not None
    return CalculateResponse(
        result_id=result.result_id,
        metric_name=result.metric_name,
        standard_value=str(result.standard_value),
        site_adjusted_value=str(result.site_adjusted_value),
        delta=result.delta,
        delta_pct=result.delta_pct,
        assumptions_applied_count=len(result.assumptions_applied),
    )


@router.post("/fpy", response_model=CalculateResponse, status_code=status.HTTP_201_CREATED)
def calculate_fpy_endpoint(
    body: FPYCalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalculateResponse:
    verify_client_access(current_user, body.client_id)
    _validate_period(body.period_start, body.period_end)

    result = FPYCalculationService(db, current_user).calculate(
        client_id=body.client_id,
        period_start=body.period_start,
        period_end=body.period_end,
        raw_inputs=body.raw_inputs,
        persist=True,
    )
    assert result.result_id is not None
    return CalculateResponse(
        result_id=result.result_id,
        metric_name=result.metric_name,
        standard_value=str(result.standard_value),
        site_adjusted_value=str(result.site_adjusted_value),
        delta=result.delta,
        delta_pct=result.delta_pct,
        assumptions_applied_count=len(result.assumptions_applied),
    )


class FromPeriodRequest(BaseModel):
    """
    Body for /api/metrics/calculate-from-period/{metric}.

    Optional partition filters pass through to the aggregator's WHERE clauses.
    Filters not applicable to a metric's source tables (per
    aggregators.py § filter applicability matrix) are silently ignored.
    """

    client_id: str
    period_start: datetime
    period_end: datetime
    line_id: Optional[int] = None
    shift_id: Optional[int] = None
    product_id: Optional[int] = None
    work_order_id: Optional[str] = None

    def filter_kwargs(self) -> dict:
        """Pass-through filter kwargs (only the applicable ones; aggregators ignore the rest)."""
        return {
            "line_id": self.line_id,
            "shift_id": self.shift_id,
            "product_id": self.product_id,
            "work_order_id": self.work_order_id,
        }


@router.post(
    "/from-period/oee",
    response_model=CalculateResponse,
    status_code=status.HTTP_201_CREATED,
)
def calculate_oee_from_period(
    body: FromPeriodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalculateResponse:
    """Aggregate OEE raw inputs from production data + run dual-view calculation."""

    verify_client_access(current_user, body.client_id)
    _validate_period(body.period_start, body.period_end)

    raw_inputs = aggregate_oee_inputs(db, body.client_id, body.period_start, body.period_end, **body.filter_kwargs())
    result = OEECalculationService(db, current_user).calculate(
        client_id=body.client_id,
        period_start=body.period_start,
        period_end=body.period_end,
        raw_inputs=raw_inputs,
        persist=True,
    )
    assert result.result_id is not None
    return CalculateResponse(
        result_id=result.result_id,
        metric_name=result.metric_name,
        standard_value=str(result.standard_value),
        site_adjusted_value=str(result.site_adjusted_value),
        delta=result.delta,
        delta_pct=result.delta_pct,
        assumptions_applied_count=len(result.assumptions_applied),
    )


@router.post(
    "/from-period/otd",
    response_model=CalculateResponse,
    status_code=status.HTTP_201_CREATED,
)
def calculate_otd_from_period(
    body: FromPeriodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalculateResponse:
    """Aggregate OTD raw inputs from work-order data + run dual-view calculation."""

    verify_client_access(current_user, body.client_id)
    _validate_period(body.period_start, body.period_end)

    raw_inputs = aggregate_otd_inputs(db, body.client_id, body.period_start, body.period_end, **body.filter_kwargs())
    result = OTDCalculationService(db, current_user).calculate(
        client_id=body.client_id,
        period_start=body.period_start,
        period_end=body.period_end,
        raw_inputs=raw_inputs,
        persist=True,
    )
    assert result.result_id is not None
    return CalculateResponse(
        result_id=result.result_id,
        metric_name=result.metric_name,
        standard_value=str(result.standard_value),
        site_adjusted_value=str(result.site_adjusted_value),
        delta=result.delta,
        delta_pct=result.delta_pct,
        assumptions_applied_count=len(result.assumptions_applied),
    )


@router.post(
    "/from-period/fpy",
    response_model=CalculateResponse,
    status_code=status.HTTP_201_CREATED,
)
def calculate_fpy_from_period(
    body: FromPeriodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalculateResponse:
    """Aggregate FPY raw inputs from quality data + run dual-view calculation."""

    verify_client_access(current_user, body.client_id)
    _validate_period(body.period_start, body.period_end)

    raw_inputs = aggregate_fpy_inputs(db, body.client_id, body.period_start, body.period_end, **body.filter_kwargs())
    result = FPYCalculationService(db, current_user).calculate(
        client_id=body.client_id,
        period_start=body.period_start,
        period_end=body.period_end,
        raw_inputs=raw_inputs,
        persist=True,
    )
    assert result.result_id is not None
    return CalculateResponse(
        result_id=result.result_id,
        metric_name=result.metric_name,
        standard_value=str(result.standard_value),
        site_adjusted_value=str(result.site_adjusted_value),
        delta=result.delta,
        delta_pct=result.delta_pct,
        assumptions_applied_count=len(result.assumptions_applied),
    )


@router.post(
    "/run-nightly",
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_nightly_run(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Admin-only manual trigger for the F.4 nightly dual-view calculation job.

    Useful for testing or "compute now" buttons in admin tooling. Runs
    synchronously — for large deployments, queue this instead.
    """

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to trigger nightly dual-view run",
        )
    from backend.tasks.dual_view_calculation import run_nightly_dual_view_calculations

    summary = run_nightly_dual_view_calculations()
    return {"status": "completed", "summary": summary}


__all__: List[str] = ["router"]
