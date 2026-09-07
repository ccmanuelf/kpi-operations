"""
Shift coverage database schema (SQLAlchemy)
PHASE 3: Shift coverage tracking
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class ShiftCoverage(Base):
    """Shift coverage table"""

    __tablename__ = "shift_coverage"
    __table_args__ = (
        # One ACTIVE coverage record per client, date and shift.
        #
        # `active_marker` is 1 while the row is live and NULL once it is soft
        # deleted, and both SQLite and MariaDB exclude NULLs from uniqueness --
        # verified on MariaDB 11.4, not assumed. That gives "unique among
        # active rows" on both dialects without a partial index, which MariaDB
        # does not support:
        #
        #   second live row for the same key   -> rejected (1062)
        #   delete, then enter it again        -> allowed
        #   many deleted rows sharing a key    -> allowed
        #
        # An application-level check alone could not close this: it is
        # SELECT-then-INSERT, so two creates racing inside the same
        # millisecond both pass it. The database is the only place the
        # invariant can actually hold.
        UniqueConstraint(
            "client_id",
            "coverage_date",
            "shift_id",
            "active_marker",
            name="uq_shift_coverage_active",
        ),
        {"extend_existing": True},
    )

    coverage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    shift_id: Mapped[int] = mapped_column(Integer, ForeignKey("SHIFT.shift_id"), nullable=False)
    coverage_date: Mapped[date] = mapped_column(Date, nullable=False)
    required_employees: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_employees: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # Calculated field
    notes: Mapped[Optional[str]] = mapped_column(Text)
    entered_by: Mapped[str] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=False)
    #: Mirrors `is_active` for the uniqueness constraint above: 1 when live,
    #: NULL when soft deleted. Maintained by the mapper event at the bottom of
    #: this module rather than by any one CRUD function, so no code path that
    #: flips `is_active` can leave a deleted row still holding its slot.
    active_marker: Mapped[Optional[int]] = mapped_column(Integer, default=1)

    # Soft delete (S1): DELETE endpoints set this False instead of removing the row.
    # Filtering is automatic — see backend/db/soft_delete_filter.py, declared in
    # backend/db/soft_delete_registry.py. Do NOT hand-filter on it.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    # Who deleted it and when. Without these a soft-deleted row is
    # indistinguishable from one that was never active — worse than a hard
    # delete, which at least leaves an absence someone might notice.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Deliberately NOT a FK, for the same reason AUDIT_ENTRY.actor_user_id is not:
    # this is a historical record of who acted, and it has to stay readable after
    # that user is renamed or deactivated — which is exactly when it is needed.
    # It also keeps the migration a plain ADD COLUMN: adding a FK constraint to an
    # existing SQLite table needs a batch table rebuild, on 37k rows across 11 tables.
    deleted_by: Mapped[Optional[str]] = mapped_column(String(50))

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )


def _sync_active_marker(mapper: Any, connection: Any, target: "ShiftCoverage") -> None:  # noqa: ARG001
    """Keep `active_marker` in step with `is_active`, on every write path.

    Coverage is soft deleted through the generic `soft_delete_record`, and a
    future bulk update could flip `is_active` without going near this module.
    Deriving the marker at flush time means the uniqueness invariant cannot be
    broken by a caller that simply did not know about it.
    """
    target.active_marker = 1 if target.is_active else None


event.listen(ShiftCoverage, "before_insert", _sync_active_marker)
event.listen(ShiftCoverage, "before_update", _sync_active_marker)
