"""
Calculation assumption registry — Phase 2 dual-view architecture.

REST API for proposing, approving, retiring, and querying site-level
calculation assumptions.

Role gates (option B ratified):
  - admin     → approve, retire (status transitions)
  - poweruser → propose, edit own proposal
  - others    → read only
"""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.orm.calculation_assumption import AssumptionStatus
from backend.orm.user import User
from backend.schemas.calculation_assumption import (
    AssumptionApproveRequest,
    AssumptionChangeResponse,
    AssumptionProposalCreate,
    AssumptionProposalUpdate,
    AssumptionResponse,
    AssumptionRetireRequest,
    AssumptionStatusEnum,
    CatalogEntry,
    EffectiveAssumptionSet,
    MetricAssumptionDependencyResponse,
    VarianceRow,
)
from backend.services.assumption_service import AssumptionService
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/assumptions", tags=["Calculation Assumptions"])


# --------------------------------------------------------------------- helpers


def _to_response(record) -> AssumptionResponse:
    import json

    return AssumptionResponse(
        assumption_id=record.assumption_id,
        client_id=record.client_id,
        assumption_name=record.assumption_name,
        value=json.loads(record.value_json),
        rationale=record.rationale,
        effective_date=record.effective_date,
        expiration_date=record.expiration_date,
        status=AssumptionStatusEnum(record.status.value),
        proposed_by=record.proposed_by,
        proposed_at=record.proposed_at,
        approved_by=record.approved_by,
        approved_at=record.approved_at,
        retired_by=record.retired_by,
        retired_at=record.retired_at,
        is_active=bool(record.is_active),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_change_response(change) -> AssumptionChangeResponse:
    import json

    return AssumptionChangeResponse(
        change_id=change.change_id,
        assumption_id=change.assumption_id,
        changed_by=change.changed_by,
        changed_at=change.changed_at,
        previous_value=json.loads(change.previous_value_json) if change.previous_value_json else None,
        new_value=json.loads(change.new_value_json) if change.new_value_json else None,
        previous_status=change.previous_status,
        new_status=change.new_status,
        change_reason=change.change_reason,
        trigger_source=change.trigger_source,
    )


# ------------------------------------------------------------------------ reads


@router.get("/catalog", response_model=List[CatalogEntry])
def get_catalog(current_user: User = Depends(get_current_user)) -> List[CatalogEntry]:
    """Static v1 catalog of valid assumption names + their permitted values."""

    catalog = AssumptionService.get_catalog()
    return [
        CatalogEntry(
            name=name,
            description=entry["description"],
            allowed_values=entry.get("allowed_values"),
        )
        for name, entry in catalog.items()
    ]


@router.get("/dependencies", response_model=List[MetricAssumptionDependencyResponse])
def list_dependencies(
    metric_name: Optional[str] = None,
    assumption_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[MetricAssumptionDependencyResponse]:
    """Map of which metrics consume which assumptions (engineering-curated)."""

    rows = AssumptionService(db, current_user).list_dependencies(
        metric_name=metric_name, assumption_name=assumption_name
    )
    return [MetricAssumptionDependencyResponse.model_validate(r) for r in rows]


@router.get("/variance", response_model=List[VarianceRow])
def get_variance_report(
    stale_after_days: int = Query(365, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[VarianceRow]:
    """Phase 5 — adjustment variance report.

    Returns one row per ACTIVE assumption (across all sites for admin/poweruser;
    tenant-scoped otherwise). Each row carries the catalog default + a deviation
    magnitude suitable for sortable-table UIs, plus an `is_stale` flag for
    assumptions not reviewed in `stale_after_days` (default 365).
    """

    rows = AssumptionService(db, current_user).get_variance_report(stale_after_days=stale_after_days)
    return [VarianceRow(**row) for row in rows]


@router.get("/effective", response_model=EffectiveAssumptionSet)
def get_effective_set(
    client_id: str = Query(..., description="Client to fetch the effective assumption set for"),
    as_of: Optional[datetime] = Query(None, description="ISO-8601 timestamp; defaults to now (UTC)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EffectiveAssumptionSet:
    """Return the active assumption value per name for a client at a point in time."""

    import json
    from datetime import timezone

    effective = AssumptionService(db, current_user).get_effective_set(client_id=client_id, as_of=as_of)
    as_of_value = as_of or datetime.now(tz=timezone.utc)

    assumptions: dict[str, Any] = {}
    metadata: dict[str, AssumptionResponse] = {}
    for name, record in effective.items():
        assumptions[name] = json.loads(record.value_json)
        metadata[name] = _to_response(record)

    return EffectiveAssumptionSet(
        client_id=client_id,
        as_of=as_of_value,
        assumptions=assumptions,
        metadata=metadata,
    )


@router.get("", response_model=List[AssumptionResponse])
def list_assumptions(
    client_id: Optional[str] = None,
    assumption_name: Optional[str] = None,
    status_filter: Optional[AssumptionStatusEnum] = Query(None, alias="status"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AssumptionResponse]:
    """List assumption records, with tenant-isolation enforced for non-admin/poweruser users."""

    status_enum = AssumptionStatus(status_filter.value) if status_filter else None
    rows = AssumptionService(db, current_user).list_assumptions(
        client_id=client_id,
        assumption_name=assumption_name,
        status_filter=status_enum,
        include_inactive=include_inactive,
    )
    return [_to_response(r) for r in rows]


@router.get("/{assumption_id}", response_model=AssumptionResponse)
def get_assumption(
    assumption_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssumptionResponse:
    record = AssumptionService(db, current_user).get_assumption(assumption_id)
    return _to_response(record)


@router.get("/{assumption_id}/history", response_model=List[AssumptionChangeResponse])
def get_history(
    assumption_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AssumptionChangeResponse]:
    """Append-only change log for one assumption record (newest first)."""

    rows = AssumptionService(db, current_user).get_history(assumption_id)
    return [_to_change_response(r) for r in rows]


# ----------------------------------------------------------------------- writes


@router.post("", response_model=AssumptionResponse, status_code=status.HTTP_201_CREATED)
def propose_assumption(
    body: AssumptionProposalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssumptionResponse:
    """Submit a new assumption proposal. Requires `poweruser` or `admin` role."""

    record = AssumptionService(db, current_user).propose(
        client_id=body.client_id,
        assumption_name=body.assumption_name,
        value=body.value,
        rationale=body.rationale,
        effective_date=body.effective_date,
        expiration_date=body.expiration_date,
    )
    return _to_response(record)


@router.patch("/{assumption_id}", response_model=AssumptionResponse)
def update_proposal(
    assumption_id: int,
    body: AssumptionProposalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssumptionResponse:
    """Edit a PROPOSED record. Allowed for the original proposer or any admin."""

    fields_set = body.model_fields_set
    record = AssumptionService(db, current_user).update_proposal(
        assumption_id=assumption_id,
        value=body.value if "value" in fields_set else None,
        rationale=body.rationale if "rationale" in fields_set else None,
        effective_date=body.effective_date if "effective_date" in fields_set else None,
        expiration_date=body.expiration_date if "expiration_date" in fields_set else None,
        change_reason=body.change_reason,
        effective_date_provided="effective_date" in fields_set,
        expiration_date_provided="expiration_date" in fields_set,
    )
    return _to_response(record)


@router.post("/{assumption_id}/approve", response_model=AssumptionResponse)
def approve_assumption(
    assumption_id: int,
    body: AssumptionApproveRequest = AssumptionApproveRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssumptionResponse:
    """Transition PROPOSED → ACTIVE. Admin only. Auto-retires overlapping ACTIVE records."""

    record = AssumptionService(db, current_user).approve(assumption_id=assumption_id, change_reason=body.change_reason)
    return _to_response(record)


@router.post("/{assumption_id}/retire", response_model=AssumptionResponse)
def retire_assumption(
    assumption_id: int,
    body: AssumptionRetireRequest = AssumptionRetireRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssumptionResponse:
    """Transition ACTIVE → RETIRED. Admin only."""

    record = AssumptionService(db, current_user).retire(assumption_id=assumption_id, change_reason=body.change_reason)
    return _to_response(record)
