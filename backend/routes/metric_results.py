"""
Inspector API for Phase 4 dual-view UI.

Two endpoints:
  - `GET /api/metrics/results` — filtered list (for tables/charts)
  - `GET /api/metrics/results/{id}` — full lineage for the inspector panel
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.middleware.client_auth import verify_client_access
from backend.orm.calculation_assumption import CalculationAssumption
from backend.orm.metric_calculation_result import MetricCalculationResult
from backend.orm.user import User
from backend.schemas.metric_calculation_result import (
    AssumptionInLineage,
    MetricLineage,
    MetricResultBrief,
)
from backend.services.calculations.assumption_catalog import V1_CATALOG
from backend.services.dual_view.metric_metadata import get_metadata
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/metrics/results", tags=["Metric Calculation Results"])


# ------------------------------------------------------------------ helpers


def _parse_value(raw: str) -> Any:
    """Decode a stored value_json. Falls back to the raw string if not JSON."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def _to_brief(row: MetricCalculationResult) -> MetricResultBrief:
    snapshot = json.loads(row.assumptions_snapshot or "{}")
    return MetricResultBrief(
        result_id=row.result_id,
        client_id=row.client_id,
        metric_name=row.metric_name,
        period_start=row.period_start,
        period_end=row.period_end,
        standard_value=_parse_value(row.standard_value_json),
        site_adjusted_value=_parse_value(row.site_adjusted_value_json),
        delta=row.delta,
        delta_pct=row.delta_pct,
        has_assumptions=bool(snapshot),
        calculated_at=row.calculated_at,
    )


def _expand_assumptions(
    db: Session, snapshot: dict[str, dict[str, Any]]
) -> list[AssumptionInLineage]:
    """Expand a per-name snapshot into full lineage entries.

    Looks up each `assumption_id` so the rationale/approved_by/approved_at
    reflects the assumption record as it was at calculation time. We pull
    description text from V1_CATALOG (engineering-curated, not user data).
    """

    if not snapshot:
        return []

    ids = [entry.get("assumption_id") for entry in snapshot.values() if entry.get("assumption_id") is not None]
    records: dict[int, CalculationAssumption] = {}
    if ids:
        for rec in db.query(CalculationAssumption).filter(CalculationAssumption.assumption_id.in_(ids)).all():
            records[rec.assumption_id] = rec

    out: list[AssumptionInLineage] = []
    for name, entry in snapshot.items():
        assumption_id = entry.get("assumption_id")
        rec = records.get(assumption_id) if assumption_id else None
        catalog_entry = V1_CATALOG.get(name, {})
        out.append(
            AssumptionInLineage(
                name=name,
                value=entry.get("value"),
                description=catalog_entry.get("description"),
                rationale=rec.rationale if rec else None,
                approved_by=entry.get("approved_by"),
                approved_at=_parse_iso(entry.get("approved_at")),
                assumption_id=assumption_id,
            )
        )
    return out


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


# -------------------------------------------------------------------- routes


@router.get("", response_model=List[MetricResultBrief])
def list_results(
    client_id: Optional[str] = None,
    metric_name: Optional[str] = None,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[MetricResultBrief]:
    """List dual-view calculation results with optional filters."""

    query = db.query(MetricCalculationResult)

    # Tenant-isolation: non-cross-tenant roles see only their assigned client.
    if current_user.role not in {"admin", "poweruser"}:
        if not current_user.client_id_assigned:
            return []
        query = query.filter(MetricCalculationResult.client_id == current_user.client_id_assigned)
    elif client_id is not None:
        query = query.filter(MetricCalculationResult.client_id == client_id)

    if metric_name is not None:
        query = query.filter(MetricCalculationResult.metric_name == metric_name)
    if period_start is not None:
        query = query.filter(MetricCalculationResult.period_end >= period_start)
    if period_end is not None:
        query = query.filter(MetricCalculationResult.period_start <= period_end)

    rows = query.order_by(MetricCalculationResult.calculated_at.desc()).limit(limit).all()
    return [_to_brief(r) for r in rows]


@router.get("/{result_id}", response_model=MetricLineage)
def get_lineage(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MetricLineage:
    """Full lineage view — what the inspector panel renders for one calculation."""

    row = (
        db.query(MetricCalculationResult)
        .filter(MetricCalculationResult.result_id == result_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Result {result_id} not found")

    verify_client_access(current_user, row.client_id)

    metadata = get_metadata(row.metric_name)
    if metadata is None:
        # Should not happen for any metric we've shipped; defensive default.
        metadata = {
            "name": row.metric_name,
            "formula": "(formula not registered)",
            "description": "",
            "inputs_help": {},
        }

    snapshot = json.loads(row.assumptions_snapshot or "{}")
    inputs = json.loads(row.inputs_snapshot_json or "{}")

    return MetricLineage(
        result_id=row.result_id,
        client_id=row.client_id,
        metric_name=row.metric_name,
        metric_display_name=metadata["name"],
        formula=metadata["formula"],
        description=metadata["description"],
        period_start=row.period_start,
        period_end=row.period_end,
        standard_value=_parse_value(row.standard_value_json),
        site_adjusted_value=_parse_value(row.site_adjusted_value_json),
        delta=row.delta,
        delta_pct=row.delta_pct,
        inputs=inputs,
        inputs_help=metadata["inputs_help"],
        assumptions_applied=_expand_assumptions(db, snapshot),
        calculated_at=row.calculated_at,
        calculated_by=row.calculated_by,
    )
