"""
AssumptionService — Phase 2 dual-view architecture.

Owns the proposal/approval lifecycle for site-level calculation assumptions and
keeps the audit log honest. Routes call into this service and never write to
CALCULATION_ASSUMPTION or ASSUMPTION_CHANGE directly.

Role gates (per spec, option B ratified):
  - admin     → may approve, retire (status transitions)
  - poweruser → may propose, edit own proposals
  - others    → read only

Soft-delete only: hard deletion is forbidden by spec ("history matters for
audit"). Setting `is_active=0` removes a row from default lists but never
removes its change-log trail.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.middleware.client_auth import verify_client_access
from backend.orm.calculation_assumption import (
    AssumptionChange,
    AssumptionStatus,
    CalculationAssumption,
    MetricAssumptionDependency,
)
from backend.orm.user import User
from backend.services.calculations.assumption_catalog import (
    V1_CATALOG,
    deviation_magnitude,
    get_default_value,
    is_known,
    validate_value,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


_PROPOSER_ROLES = {"admin", "poweruser"}
_APPROVER_ROLES = {"admin"}


class AssumptionService:
    """Lifecycle + audit-log enforcement for the assumption registry."""

    def __init__(self, db: Session, current_user: User) -> None:
        self.db = db
        self.user = current_user

    # ------------------------------------------------------------------ reads

    def list_assumptions(
        self,
        client_id: Optional[str] = None,
        assumption_name: Optional[str] = None,
        status_filter: Optional[AssumptionStatus] = None,
        include_inactive: bool = False,
    ) -> list[CalculationAssumption]:
        """List assumptions, with tenant-isolation enforced."""

        effective_client_id = self._resolve_client_filter(client_id)

        query = self.db.query(CalculationAssumption)
        if effective_client_id is not None:
            query = query.filter(CalculationAssumption.client_id == effective_client_id)
        if assumption_name is not None:
            query = query.filter(CalculationAssumption.assumption_name == assumption_name)
        if status_filter is not None:
            query = query.filter(CalculationAssumption.status == status_filter)
        if not include_inactive:
            query = query.filter(CalculationAssumption.is_active == 1)

        return query.order_by(
            CalculationAssumption.client_id,
            CalculationAssumption.assumption_name,
            CalculationAssumption.proposed_at.desc(),
        ).all()

    def get_assumption(self, assumption_id: int) -> CalculationAssumption:
        record = self._fetch_or_404(assumption_id)
        verify_client_access(self.user, record.client_id)
        return record

    def get_effective_set(self, client_id: str, as_of: Optional[datetime] = None) -> dict[str, CalculationAssumption]:
        """
        Return the active assumption record per name for `client_id` at `as_of`.

        An assumption is "active for `as_of`" iff:
          - status == ACTIVE
          - is_active == 1
          - effective_date is NULL OR effective_date <= as_of
          - expiration_date is NULL OR expiration_date >= as_of
        """

        verify_client_access(self.user, client_id)

        as_of_dt = as_of or datetime.now(tz=timezone.utc)

        query = self.db.query(CalculationAssumption).filter(
            CalculationAssumption.client_id == client_id,
            CalculationAssumption.is_active == 1,
            CalculationAssumption.status == AssumptionStatus.ACTIVE,
            or_(
                CalculationAssumption.effective_date.is_(None),
                CalculationAssumption.effective_date <= as_of_dt,
            ),
            or_(
                CalculationAssumption.expiration_date.is_(None),
                CalculationAssumption.expiration_date >= as_of_dt,
            ),
        )

        # If two ACTIVE rows for the same name overlap, prefer the most
        # recently approved one — the service layer should normally prevent
        # overlap on approve, but defend against it here too.
        result: dict[str, CalculationAssumption] = {}
        for record in query.all():
            existing = result.get(record.assumption_name)
            if existing is None or _approved_after(record, existing):
                result[record.assumption_name] = record
        return result

    def get_history(self, assumption_id: int) -> list[AssumptionChange]:
        record = self._fetch_or_404(assumption_id)
        verify_client_access(self.user, record.client_id)
        return (
            self.db.query(AssumptionChange)
            .filter(AssumptionChange.assumption_id == assumption_id)
            .order_by(AssumptionChange.changed_at.desc())
            .all()
        )

    def list_dependencies(
        self,
        metric_name: Optional[str] = None,
        assumption_name: Optional[str] = None,
    ) -> list[MetricAssumptionDependency]:
        query = self.db.query(MetricAssumptionDependency)
        if metric_name is not None:
            query = query.filter(MetricAssumptionDependency.metric_name == metric_name)
        if assumption_name is not None:
            query = query.filter(MetricAssumptionDependency.assumption_name == assumption_name)
        return query.order_by(
            MetricAssumptionDependency.metric_name,
            MetricAssumptionDependency.assumption_name,
        ).all()

    @staticmethod
    def get_catalog() -> dict[str, dict[str, Any]]:
        return {name: dict(entry) for name, entry in V1_CATALOG.items()}

    def get_variance_report(self, stale_after_days: int = 365) -> list[dict[str, Any]]:
        """
        Phase 5 — variance report rows for every currently ACTIVE assumption.

        Tenant-scoped: admin/poweruser see all clients; others see only their
        assigned client. Each row carries the catalog-default for comparison
        and a `deviation_magnitude` suitable for sorting.

        `stale_after_days` defaults to 365 per spec ("haven't been reviewed
        in > 12 months").
        """

        query = self.db.query(CalculationAssumption).filter(
            CalculationAssumption.status == AssumptionStatus.ACTIVE,
            CalculationAssumption.is_active == 1,
        )
        if self.user.role not in {"admin", "poweruser"}:
            if not self.user.client_id_assigned:
                return []
            query = query.filter(CalculationAssumption.client_id == self.user.client_id_assigned)

        records = query.order_by(
            CalculationAssumption.client_id,
            CalculationAssumption.assumption_name,
        ).all()

        now = datetime.now(tz=timezone.utc)
        rows: list[dict[str, Any]] = []
        for rec in records:
            value = json.loads(rec.value_json)
            default = get_default_value(rec.assumption_name)
            magnitude = deviation_magnitude(rec.assumption_name, value)

            approved_at = rec.approved_at
            days_since: Optional[int] = None
            is_stale = False
            if approved_at is not None:
                # Normalize naive datetimes (SQLite-stored) to UTC for diff.
                anchor = approved_at if approved_at.tzinfo else approved_at.replace(tzinfo=timezone.utc)
                days_since = (now - anchor).days
                is_stale = days_since > stale_after_days

            rows.append(
                {
                    "assumption_id": rec.assumption_id,
                    "client_id": rec.client_id,
                    "assumption_name": rec.assumption_name,
                    "description": V1_CATALOG.get(rec.assumption_name, {}).get("description"),
                    "value": value,
                    "default_value": default,
                    "deviates_from_default": magnitude != 0.0,
                    "deviation_magnitude": magnitude,
                    "approved_by": rec.approved_by,
                    "approved_at": approved_at,
                    "days_since_review": days_since,
                    "is_stale": is_stale,
                    "rationale": rec.rationale,
                }
            )
        return rows

    # ----------------------------------------------------------------- writes

    def propose(
        self,
        client_id: str,
        assumption_name: str,
        value: Any,
        rationale: Optional[str] = None,
        effective_date: Optional[datetime] = None,
        expiration_date: Optional[datetime] = None,
    ) -> CalculationAssumption:
        """Create a new PROPOSED assumption record. Requires poweruser or admin."""

        self._require_role(_PROPOSER_ROLES, action="propose")
        verify_client_access(self.user, client_id)
        self._validate_catalog(assumption_name, value)
        self._validate_window(effective_date, expiration_date)

        record = CalculationAssumption(
            client_id=client_id,
            assumption_name=assumption_name,
            value_json=json.dumps(value),
            rationale=rationale,
            effective_date=effective_date,
            expiration_date=expiration_date,
            status=AssumptionStatus.PROPOSED,
            proposed_by=self.user.user_id,
            is_active=1,
        )
        self.db.add(record)
        self.db.flush()  # populate assumption_id

        self._write_change(
            assumption_id=record.assumption_id,
            previous_value=None,
            new_value=value,
            previous_status=None,
            new_status=AssumptionStatus.PROPOSED.value,
            change_reason="proposed",
        )
        self.db.commit()
        self.db.refresh(record)

        logger.info(
            "Assumption proposed: id=%s client=%s name=%s by=%s",
            record.assumption_id,
            client_id,
            assumption_name,
            self.user.user_id,
        )
        return record

    def update_proposal(
        self,
        assumption_id: int,
        value: Optional[Any] = None,
        rationale: Optional[str] = None,
        effective_date: Optional[datetime] = None,
        expiration_date: Optional[datetime] = None,
        change_reason: Optional[str] = None,
        # Sentinels lets callers explicitly pass None to clear a date — they
        # set the *_provided flag while the value itself is None.
        effective_date_provided: bool = False,
        expiration_date_provided: bool = False,
    ) -> CalculationAssumption:
        """Edit a PROPOSED record. Allowed for the original proposer OR any admin."""

        record = self._fetch_or_404(assumption_id)
        verify_client_access(self.user, record.client_id)

        if record.status != AssumptionStatus.PROPOSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot edit assumption with status {record.status.value}",
            )

        if record.proposed_by != self.user.user_id and self.user.role not in _APPROVER_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the original proposer or an admin may edit a proposal",
            )

        previous_value = json.loads(record.value_json)

        if value is not None:
            self._validate_catalog(record.assumption_name, value)
            record.value_json = json.dumps(value)

        if rationale is not None:
            record.rationale = rationale

        if effective_date_provided:
            record.effective_date = effective_date
        if expiration_date_provided:
            record.expiration_date = expiration_date
        self._validate_window(record.effective_date, record.expiration_date)

        self._write_change(
            assumption_id=record.assumption_id,
            previous_value=previous_value,
            new_value=value if value is not None else previous_value,
            previous_status=AssumptionStatus.PROPOSED.value,
            new_status=AssumptionStatus.PROPOSED.value,
            change_reason=change_reason or "proposal_updated",
        )
        self.db.commit()
        self.db.refresh(record)
        return record

    def approve(self, assumption_id: int, change_reason: Optional[str] = None) -> CalculationAssumption:
        """Transition PROPOSED → ACTIVE. Admin only."""

        self._require_role(_APPROVER_ROLES, action="approve")
        record = self._fetch_or_404(assumption_id)
        verify_client_access(self.user, record.client_id)

        if record.status != AssumptionStatus.PROPOSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only PROPOSED assumptions can be approved (current: {record.status.value})",
            )

        # Auto-retire any existing ACTIVE record for the same (client, name)
        # whose window overlaps the incoming one. Without this, get_effective_set
        # would have to disambiguate at read time on every call.
        self._auto_retire_overlaps(record)

        record.status = AssumptionStatus.ACTIVE
        record.approved_by = self.user.user_id
        record.approved_at = datetime.now(tz=timezone.utc)

        self._write_change(
            assumption_id=record.assumption_id,
            previous_value=None,
            new_value=json.loads(record.value_json),
            previous_status=AssumptionStatus.PROPOSED.value,
            new_status=AssumptionStatus.ACTIVE.value,
            change_reason=change_reason or "approved",
        )
        self.db.commit()
        self.db.refresh(record)

        logger.info(
            "Assumption approved: id=%s client=%s name=%s by=%s",
            record.assumption_id,
            record.client_id,
            record.assumption_name,
            self.user.user_id,
        )
        return record

    def retire(self, assumption_id: int, change_reason: Optional[str] = None) -> CalculationAssumption:
        """Transition ACTIVE → RETIRED. Admin only."""

        self._require_role(_APPROVER_ROLES, action="retire")
        record = self._fetch_or_404(assumption_id)
        verify_client_access(self.user, record.client_id)

        if record.status != AssumptionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only ACTIVE assumptions can be retired (current: {record.status.value})",
            )

        record.status = AssumptionStatus.RETIRED
        record.retired_by = self.user.user_id
        record.retired_at = datetime.now(tz=timezone.utc)

        self._write_change(
            assumption_id=record.assumption_id,
            previous_value=None,
            new_value=json.loads(record.value_json),
            previous_status=AssumptionStatus.ACTIVE.value,
            new_status=AssumptionStatus.RETIRED.value,
            change_reason=change_reason or "retired",
        )
        self.db.commit()
        self.db.refresh(record)

        logger.info(
            "Assumption retired: id=%s client=%s name=%s by=%s",
            record.assumption_id,
            record.client_id,
            record.assumption_name,
            self.user.user_id,
        )
        return record

    # --------------------------------------------------------------- helpers

    def _require_role(self, allowed: set[str], action: str) -> None:
        if self.user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {self.user.role!r} not permitted to {action} assumptions",
            )

    def _resolve_client_filter(self, requested: Optional[str]) -> Optional[str]:
        """Decide which client_id to filter by based on user role + request."""

        if self.user.role in {"admin", "poweruser"}:
            # Cross-client visibility OK; honour an explicit filter when supplied.
            return requested
        # Tenant-bound users see only their assigned client.
        return self.user.client_id_assigned

    def _fetch_or_404(self, assumption_id: int) -> CalculationAssumption:
        record = (
            self.db.query(CalculationAssumption).filter(CalculationAssumption.assumption_id == assumption_id).first()
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assumption {assumption_id} not found",
            )
        return record

    @staticmethod
    def _validate_catalog(assumption_name: str, value: Any) -> None:
        if not is_known(assumption_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown assumption_name {assumption_name!r}; not in v1 catalog",
            )
        try:
            validate_value(assumption_name, value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @staticmethod
    def _validate_window(effective_date: Optional[datetime], expiration_date: Optional[datetime]) -> None:
        if effective_date is not None and expiration_date is not None and effective_date > expiration_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="effective_date cannot be after expiration_date",
            )

    def _auto_retire_overlaps(self, incoming: CalculationAssumption) -> None:
        """When approving, retire any ACTIVE record for the same (client, name) whose window overlaps."""

        existing = (
            self.db.query(CalculationAssumption)
            .filter(
                and_(
                    CalculationAssumption.client_id == incoming.client_id,
                    CalculationAssumption.assumption_name == incoming.assumption_name,
                    CalculationAssumption.status == AssumptionStatus.ACTIVE,
                    CalculationAssumption.is_active == 1,
                    CalculationAssumption.assumption_id != incoming.assumption_id,
                )
            )
            .all()
        )

        now = datetime.now(tz=timezone.utc)
        for record in existing:
            if not _windows_overlap(
                (record.effective_date, record.expiration_date),
                (incoming.effective_date, incoming.expiration_date),
            ):
                continue
            record.status = AssumptionStatus.RETIRED
            record.retired_by = self.user.user_id
            record.retired_at = now
            self._write_change(
                assumption_id=record.assumption_id,
                previous_value=None,
                new_value=json.loads(record.value_json),
                previous_status=AssumptionStatus.ACTIVE.value,
                new_status=AssumptionStatus.RETIRED.value,
                change_reason=f"auto-retired by approval of #{incoming.assumption_id}",
            )

    def _write_change(
        self,
        assumption_id: int,
        previous_value: Optional[Any],
        new_value: Optional[Any],
        previous_status: Optional[str],
        new_status: Optional[str],
        change_reason: Optional[str],
        trigger_source: str = "api",
    ) -> None:
        change = AssumptionChange(
            assumption_id=assumption_id,
            changed_by=self.user.user_id,
            previous_value_json=(json.dumps(previous_value) if previous_value is not None else None),
            new_value_json=(json.dumps(new_value) if new_value is not None else None),
            previous_status=previous_status,
            new_status=new_status,
            change_reason=change_reason,
            trigger_source=trigger_source,
        )
        self.db.add(change)


# --------------------------------------------------------------- module utils


def _approved_after(a: CalculationAssumption, b: CalculationAssumption) -> bool:
    """Tie-breaker for two ACTIVE rows on the same (client, name)."""

    a_at = a.approved_at or a.proposed_at
    b_at = b.approved_at or b.proposed_at
    return a_at > b_at


def _windows_overlap(
    win_a: tuple[Optional[datetime], Optional[datetime]],
    win_b: tuple[Optional[datetime], Optional[datetime]],
) -> bool:
    """Two effective-date windows overlap iff start_a <= end_b AND start_b <= end_a, treating NULLs as ±∞."""

    start_a, end_a = win_a
    start_b, end_b = win_b

    if end_a is not None and start_b is not None and end_a < start_b:
        return False
    if end_b is not None and start_a is not None and end_b < start_a:
        return False
    return True
