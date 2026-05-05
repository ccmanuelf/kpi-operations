"""
CALCULATION_ASSUMPTION / ASSUMPTION_CHANGE / METRIC_ASSUMPTION_DEPENDENCY tables.

Phase 2 of the dual-view calculation architecture: a first-class data model for
site-level calculation assumptions. Every assumption is named, owned, versioned,
and auditable.

Three tables:
  - CALCULATION_ASSUMPTION  — per-client assumption values with proposal/approval
                              lifecycle and effective-date windows.
  - ASSUMPTION_CHANGE       — append-only audit log for every modification.
  - METRIC_ASSUMPTION_DEPENDENCY  — static map of which metrics consume which
                              assumptions, populated by engineering.

The lifecycle (`proposed → active → retired`) and audit pattern mirror the
existing `WORKFLOW_TRANSITION_LOG` design; the per-tenant + JSON-value shape
mirrors `CLIENT_CONFIG`. Soft delete via `is_active` follows the project-wide
convention.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class AssumptionStatus(str, enum.Enum):
    """Proposal/approval lifecycle state for a single assumption record."""

    PROPOSED = "proposed"  # poweruser submitted; awaiting admin review
    ACTIVE = "active"  # admin approved; in use for calculations
    RETIRED = "retired"  # superseded or no longer relevant


class CalculationAssumption(Base):
    """
    A single named, owned, finance-approved adjustment to a metric calculation.

    Multiple records may exist per (client_id, assumption_name) — they form a
    history chain via effective_date / expiration_date. At most one row per
    (client_id, assumption_name) should be ACTIVE on any given date; this is
    enforced in the service layer (CRUD layer does not validate windows).
    """

    __tablename__ = "CALCULATION_ASSUMPTION"
    __table_args__ = (
        Index("ix_assumption_client_name", "client_id", "assumption_name"),
        Index("ix_assumption_client_status", "client_id", "status"),
        Index("ix_assumption_effective", "client_id", "effective_date"),
        {"extend_existing": True},
    )

    assumption_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Catalog name (e.g. "ideal_cycle_time_source"). Bounded to 15 distinct
    # values in v1 — service layer rejects unknown names.
    assumption_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # JSON-encoded value. Text rather than the dialect-specific JSON type so
    # SQLite (demo) and MariaDB (prod) behave identically.
    value_json: Mapped[str] = mapped_column(Text, nullable=False)

    rationale: Mapped[Optional[str]] = mapped_column(Text)

    # Optional validity window. NULL effective_date = "from inception".
    # NULL expiration_date = "until further notice".
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    status: Mapped[AssumptionStatus] = mapped_column(
        SQLEnum(AssumptionStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AssumptionStatus.PROPOSED,
    )

    # Approval triplet. proposed_by/at always populated; approved_by/at only
    # after status transitions to ACTIVE; retired_by/at only on RETIRED.
    proposed_by: Mapped[str] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=False)
    proposed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    approved_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    retired_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=True)
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Soft-delete (project-wide convention). Hard delete is never allowed —
    # the spec mandates audit retention.
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AssumptionChange(Base):
    """
    Append-only audit log. One row per modification to a CalculationAssumption.

    Mirrors WORKFLOW_TRANSITION_LOG's schema: the record is written by the
    service layer after every successful write to CALCULATION_ASSUMPTION.
    Never updated, never deleted. Project lifespan checks treat this as a
    structural integrity invariant.
    """

    __tablename__ = "ASSUMPTION_CHANGE"
    __table_args__ = (
        Index("ix_assumption_change_assumption", "assumption_id", "changed_at"),
        Index("ix_assumption_change_user", "changed_by", "changed_at"),
        {"extend_existing": True},
    )

    change_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    assumption_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("CALCULATION_ASSUMPTION.assumption_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    changed_by: Mapped[str] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Previous and new value snapshots — both JSON-encoded. Either may be
    # NULL: previous_value_json on initial proposal, new_value_json if the
    # record was retired without a value change (status-only transition).
    previous_value_json: Mapped[Optional[str]] = mapped_column(Text)
    new_value_json: Mapped[Optional[str]] = mapped_column(Text)

    # Status transition recorded as strings (rather than the enum) so the
    # log survives schema changes to the enum without back-filling.
    previous_status: Mapped[Optional[str]] = mapped_column(String(20))
    new_status: Mapped[Optional[str]] = mapped_column(String(20))

    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    trigger_source: Mapped[Optional[str]] = mapped_column(String(50))  # 'manual' | 'api' | 'automatic'


class MetricAssumptionDependency(Base):
    """
    Static reference: which metrics consume which assumptions.

    Populated by engineering at deploy time, not by users. Used by the Phase 4
    inspector UI to show "this OEE value depends on assumptions X and Y".
    """

    __tablename__ = "METRIC_ASSUMPTION_DEPENDENCY"
    __table_args__ = (
        UniqueConstraint("metric_name", "assumption_name", name="uq_metric_assumption"),
        Index("ix_dep_metric", "metric_name"),
        Index("ix_dep_assumption", "assumption_name"),
        {"extend_existing": True},
    )

    dependency_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    assumption_name: Mapped[str] = mapped_column(String(100), nullable=False)
    usage_notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
