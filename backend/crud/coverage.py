"""
CRUD operations for shift coverage tracking
PHASE 3
SECURITY: Multi-tenant client filtering enabled
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from decimal import Decimal
from fastapi import HTTPException

from backend.orm.coverage import ShiftCoverage
from backend.schemas.coverage import ShiftCoverageCreate, ShiftCoverageUpdate, ShiftCoverageResponse
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.orm.user import User
from backend.db.soft_delete_service import soft_delete_record

logger = logging.getLogger(__name__)

#: `ShiftCoverage.coverage_percentage` is Numeric(5, 2), so the largest value
#: the column can hold is 999.99. The ratio is NOT bounded by anything else:
#: required_employees only has to be > 0, so one required and fifty present
#: computes 5000.00.
#:
#: SQLite stores that silently. MariaDB — the production dialect — rejects it
#: in strict mode, so the whole test suite passes and the write 500s on the
#: VM. Clamping loses nothing recoverable: required_employees and
#: actual_employees are both stored faithfully and the percentage is derived
#: from them, so a reader can always recompute the true ratio.
MAX_COVERAGE_PERCENTAGE = Decimal("999.99")


def _coverage_percentage(required: int, actual: int) -> Decimal:
    """The derived percentage, clamped to what the column can actually hold.

    The clamp is a STORAGE limit, not a domain rule -- 999.99 is the width of
    Numeric(5, 2), not a statement about plausible staffing -- so rejecting on
    it would leak a column definition into validation. It is logged instead of
    passing silently: a ratio this extreme is almost always a typo in
    required_employees, and the operator should be findable afterwards. The
    two source columns are stored faithfully either way, so the true ratio is
    always recoverable from the row itself.
    """
    if required <= 0:
        return Decimal("0")
    pct = (Decimal(str(actual)) / Decimal(str(required))) * 100
    if pct > MAX_COVERAGE_PERCENTAGE:
        logger.warning(
            "Coverage ratio %s%% (required=%s, actual=%s) exceeds the column ceiling; "
            "storing %s. The source counts are kept intact.",
            pct,
            required,
            actual,
            MAX_COVERAGE_PERCENTAGE,
        )
        return MAX_COVERAGE_PERCENTAGE
    return pct


def _assert_shift_belongs_to_client(db: Session, shift_id: int, client_id: str) -> None:
    """Reject a coverage row pointing at another tenant's shift.

    The FK only requires that the shift EXISTS, so a row for client A
    referencing client B's shift satisfies every database on every dialect and
    is silently cross-tenant. Nothing else checks this.

    A DEACTIVATED shift still passes. SHIFT is in AD_HOC_FILTERED_TABLES
    rather than the auto-filtered set precisely so its historical rows stay
    readable -- "hiding one orphans its entries" -- and refusing coverage
    against one here would contradict that and block backfilling a shift that
    has since been retired. Checked deliberately, not overlooked.
    """
    from backend.orm.shift import Shift

    owner = db.query(Shift.client_id).filter(Shift.shift_id == shift_id).scalar()
    if owner is None:
        raise HTTPException(status_code=400, detail=f"Shift {shift_id} not found")
    if owner != client_id:
        raise HTTPException(
            status_code=400,
            detail=f"Shift {shift_id} belongs to a different client",
        )


def _find_duplicate(db: Session, client_id: str, coverage_date: date, shift_id: int) -> Optional[int]:
    """The id of the ACTIVE row already holding this slot, or None.

    Auto-filtered to active rows, which matches what the constraint binds.
    """
    clash = (
        db.query(ShiftCoverage.coverage_id)
        .filter(
            ShiftCoverage.client_id == client_id,
            ShiftCoverage.coverage_date == coverage_date,
            ShiftCoverage.shift_id == shift_id,
        )
        .first()
    )
    return None if clash is None else clash[0]


def _assert_not_duplicate(db: Session, client_id: str, coverage_date: date, shift_id: int) -> None:
    """One coverage record per client, date and shift.

    NOT the thing that enforces this. `uq_shift_coverage_active` is -- see
    backend/orm/coverage.py -- because this is SELECT-then-INSERT with no lock
    and two creates racing inside the same millisecond both pass it.

    This exists for the error MESSAGE. The constraint can only report which
    columns collided; the caller wants to know which record already holds the
    slot so they can go and edit it, and that needs the row. When this check
    passes and the constraint still fires, `create_shift_coverage` catches the
    IntegrityError and returns the same 409 with a less specific message.

    The read is auto-filtered to ACTIVE rows, matching the constraint, which
    only binds live rows: deleting a record and entering it again works on
    both paths. A soft-deleted row is deleted as far as its author is
    concerned; treating it as a tombstone would make a
    mistakenly-entered-then-removed row impossible to re-enter.
    """
    clash = _find_duplicate(db, client_id, coverage_date, shift_id)
    if clash is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Coverage for shift {shift_id} on {coverage_date} already exists "
                f"for this client (record {clash}). Edit it instead."
            ),
        )


def create_shift_coverage(db: Session, coverage: ShiftCoverageCreate, current_user: User) -> ShiftCoverageResponse:
    """
    Create new shift coverage record
    SECURITY: Verifies user has access to the specified client
    """
    # SECURITY: Verify user has access to this client
    if hasattr(coverage, "client_id") and coverage.client_id:
        verify_client_access(current_user, coverage.client_id)

    _assert_shift_belongs_to_client(db, coverage.shift_id, coverage.client_id)
    _assert_not_duplicate(db, coverage.client_id, coverage.coverage_date, coverage.shift_id)

    coverage_pct = _coverage_percentage(coverage.required_employees, coverage.actual_employees)

    db_coverage = ShiftCoverage(
        **coverage.model_dump(), coverage_percentage=coverage_pct, entered_by=current_user.user_id
    )

    db.add(db_coverage)
    try:
        db.commit()
    except IntegrityError:
        # The pre-check above catches the case that actually happens -- someone
        # re-adding a row that is already there -- but it is SELECT-then-INSERT,
        # so two creates racing inside the same millisecond both pass it. The
        # uq_shift_coverage_active constraint is what makes the invariant hold;
        # this turns losing that race into the same 409 the pre-check gives,
        # rather than a 500.
        db.rollback()
        # ONLY that constraint. A blanket `except IntegrityError` would report a
        # foreign-key or not-null violation as "already exists" -- sending
        # whoever hit it looking for a duplicate that does not exist.
        #
        # Decided by RE-READING rather than by matching the driver's message:
        # SQLite names the columns ("UNIQUE constraint failed: shift_coverage.
        # client_id, ...") while MariaDB names the constraint ("Duplicate entry
        # ... for key 'uq_shift_coverage_active'"), so any string match is one
        # dialect's format and 500s on the other. Asking whether a row now
        # holds the slot is exact on both, and costs one SELECT on a path that
        # only runs when a write has already failed.
        if _find_duplicate(db, coverage.client_id, coverage.coverage_date, coverage.shift_id) is None:
            raise
        raise HTTPException(
            status_code=409,
            detail=(
                f"Coverage for shift {coverage.shift_id} on {coverage.coverage_date} "
                f"already exists for this client. Edit it instead."
            ),
        ) from None
    db.refresh(db_coverage)

    return ShiftCoverageResponse.model_validate(db_coverage)


def get_shift_coverage(db: Session, coverage_id: int, current_user: User) -> Optional[ShiftCoverage]:
    """
    Get shift coverage by ID
    SECURITY: Verifies user has access to the record's client
    """
    db_coverage = db.query(ShiftCoverage).filter(ShiftCoverage.coverage_id == coverage_id).first()

    if not db_coverage:
        raise HTTPException(status_code=404, detail="Shift coverage record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_coverage, "client_id") and db_coverage.client_id:
        verify_client_access(current_user, db_coverage.client_id)

    return db_coverage


def get_shift_coverages(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    shift_id: Optional[int] = None,
    client_id: Optional[str] = None,
) -> List[ShiftCoverage]:
    """
    Get shift coverage records with filters
    SECURITY: Automatically filters by user's authorized clients
    """
    query = db.query(ShiftCoverage)

    # SECURITY: Apply client filtering based on user's role
    client_filter = build_client_filter_clause(current_user, ShiftCoverage.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply additional filters
    if client_id:
        query = query.filter(ShiftCoverage.client_id == client_id)

    if start_date:
        query = query.filter(ShiftCoverage.coverage_date >= start_date)

    if end_date:
        query = query.filter(ShiftCoverage.coverage_date <= end_date)

    if shift_id:
        query = query.filter(ShiftCoverage.shift_id == shift_id)

    return query.order_by(ShiftCoverage.coverage_date.desc()).offset(skip).limit(limit).all()


def update_shift_coverage(
    db: Session, coverage_id: int, coverage_update: ShiftCoverageUpdate, current_user: User
) -> Optional[ShiftCoverageResponse]:
    """
    Update shift coverage record
    SECURITY: Verifies user has access to the record's client
    """
    db_coverage = db.query(ShiftCoverage).filter(ShiftCoverage.coverage_id == coverage_id).first()

    if not db_coverage:
        raise HTTPException(status_code=404, detail="Shift coverage record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_coverage, "client_id") and db_coverage.client_id:
        verify_client_access(current_user, db_coverage.client_id)

    update_data = coverage_update.model_dump(exclude_unset=True)

    # Recalculate coverage percentage if values changed
    required = update_data.get("required_employees", db_coverage.required_employees)
    actual = update_data.get("actual_employees", db_coverage.actual_employees)

    update_data["coverage_percentage"] = _coverage_percentage(required, actual)

    for field, value in update_data.items():
        if hasattr(db_coverage, field):
            setattr(db_coverage, field, value)

    db.commit()
    db.refresh(db_coverage)

    return ShiftCoverageResponse.model_validate(db_coverage)


def delete_shift_coverage(db: Session, coverage_id: int, current_user: User) -> bool:
    """
    Soft delete shift coverage record (sets is_active = False)
    SECURITY: Verifies user has access to the record's client
    """
    db_coverage = db.query(ShiftCoverage).filter(ShiftCoverage.coverage_id == coverage_id).first()

    if not db_coverage:
        raise HTTPException(status_code=404, detail="Shift coverage record not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_coverage, "client_id") and db_coverage.client_id:
        verify_client_access(current_user, db_coverage.client_id)

    # Soft delete - preserves data integrity
    return soft_delete_record(db, db_coverage, current_user)
