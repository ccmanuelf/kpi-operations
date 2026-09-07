"""
CRUD operations for shift coverage tracking
PHASE 3
SECURITY: Multi-tenant client filtering enabled
"""

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
    """The derived percentage, clamped to what the column can actually hold."""
    if required <= 0:
        return Decimal("0")
    pct = (Decimal(str(actual)) / Decimal(str(required))) * 100
    return min(pct, MAX_COVERAGE_PERCENTAGE)


def _assert_shift_belongs_to_client(db: Session, shift_id: int, client_id: str) -> None:
    """Reject a coverage row pointing at another tenant's shift.

    The FK only requires that the shift EXISTS, so a row for client A
    referencing client B's shift satisfies every database on every dialect and
    is silently cross-tenant. Nothing else checks this.
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


def _assert_not_duplicate(db: Session, client_id: str, coverage_date: date, shift_id: int) -> None:
    """One coverage record per client, date and shift.

    Deliberately an application check rather than a UNIQUE constraint: the
    table is soft-deleted, and a plain constraint would let a deleted row hold
    the slot forever. A partial index would express it, but MariaDB does not
    support them, so the constraint could not be made portable. The ORM read
    below is auto-filtered to active rows, which is exactly the scope wanted.
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
    if clash is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Coverage for shift {shift_id} on {coverage_date} already exists "
                f"for this client (record {clash[0]}). Edit it instead."
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
    db.commit()
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
