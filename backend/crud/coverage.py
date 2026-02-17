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

from backend.schemas.coverage import ShiftCoverage
from backend.models.coverage import ShiftCoverageCreate, ShiftCoverageUpdate, ShiftCoverageResponse
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User
from backend.utils.soft_delete import soft_delete


def create_shift_coverage(db: Session, coverage: ShiftCoverageCreate, current_user: User) -> ShiftCoverageResponse:
    """
    Create new shift coverage record
    SECURITY: Verifies user has access to the specified client
    """
    # SECURITY: Verify user has access to this client
    if hasattr(coverage, "client_id") and coverage.client_id:
        verify_client_access(current_user, coverage.client_id)

    # Calculate coverage percentage
    if coverage.required_employees > 0:
        coverage_pct = (Decimal(str(coverage.actual_employees)) / Decimal(str(coverage.required_employees))) * 100
    else:
        coverage_pct = Decimal("0")

    db_coverage = ShiftCoverage(**coverage.model_dump(), coverage_percentage=coverage_pct, entered_by=current_user.user_id)

    db.add(db_coverage)
    db.commit()
    db.refresh(db_coverage)

    return ShiftCoverageResponse.from_orm(db_coverage)


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

    if required > 0:
        update_data["coverage_percentage"] = (Decimal(str(actual)) / Decimal(str(required))) * 100
    else:
        update_data["coverage_percentage"] = Decimal("0")

    for field, value in update_data.items():
        if hasattr(db_coverage, field):
            setattr(db_coverage, field, value)

    db.commit()
    db.refresh(db_coverage)

    return ShiftCoverageResponse.from_orm(db_coverage)


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
    return soft_delete(db, db_coverage)
