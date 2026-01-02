"""
CRUD operations for shift coverage tracking
PHASE 3
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from decimal import Decimal
from fastapi import HTTPException

from backend.schemas.coverage import ShiftCoverage
from backend.models.coverage import (
    ShiftCoverageCreate,
    ShiftCoverageUpdate,
    ShiftCoverageResponse
)
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User


def create_shift_coverage(
    db: Session,
    coverage: ShiftCoverageCreate,
    current_user: User
) -> ShiftCoverageResponse:
    """Create new shift coverage record"""
    # Verify user has access to this client
    verify_client_access(current_user, coverage.client_id)

    # Calculate coverage percentage
    if coverage.required_employees > 0:
        coverage_pct = (
            Decimal(str(coverage.actual_employees)) /
            Decimal(str(coverage.required_employees))
        ) * 100
    else:
        coverage_pct = Decimal("0")

    db_coverage = ShiftCoverage(
        **coverage.dict(),
        coverage_percentage=coverage_pct,
        entered_by=current_user.user_id
    )

    db.add(db_coverage)
    db.commit()
    db.refresh(db_coverage)

    return ShiftCoverageResponse.from_orm(db_coverage)


def get_shift_coverage(
    db: Session,
    coverage_id: int,
    current_user: User
) -> Optional[ShiftCoverage]:
    """Get shift coverage by ID"""
    db_coverage = db.query(ShiftCoverage).filter(
        ShiftCoverage.coverage_id == coverage_id
    ).first()

    if not db_coverage:
        raise HTTPException(status_code=404, detail="Shift coverage not found")

    # Verify user has access to this client
    verify_client_access(current_user, db_coverage.client_id)

    return db_coverage


def get_shift_coverages(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    shift_id: Optional[int] = None
) -> List[ShiftCoverage]:
    """Get shift coverage records with filters"""
    query = db.query(ShiftCoverage)

    # Apply client filtering based on user role
    client_filter = build_client_filter_clause(current_user, ShiftCoverage.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    if start_date:
        query = query.filter(ShiftCoverage.coverage_date >= start_date)

    if end_date:
        query = query.filter(ShiftCoverage.coverage_date <= end_date)

    if shift_id:
        query = query.filter(ShiftCoverage.shift_id == shift_id)

    return query.order_by(
        ShiftCoverage.coverage_date.desc()
    ).offset(skip).limit(limit).all()


def update_shift_coverage(
    db: Session,
    coverage_id: int,
    coverage_update: ShiftCoverageUpdate,
    current_user: User
) -> Optional[ShiftCoverageResponse]:
    """Update shift coverage record"""
    db_coverage = get_shift_coverage(db, coverage_id, current_user)

    if not db_coverage:
        return None

    update_data = coverage_update.dict(exclude_unset=True)

    # Verify client_id if being updated
    if 'client_id' in update_data:
        verify_client_access(current_user, update_data['client_id'])

    # Recalculate coverage percentage if values changed
    required = update_data.get('required_employees', db_coverage.required_employees)
    actual = update_data.get('actual_employees', db_coverage.actual_employees)

    if required > 0:
        update_data['coverage_percentage'] = (
            Decimal(str(actual)) / Decimal(str(required))
        ) * 100
    else:
        update_data['coverage_percentage'] = Decimal("0")

    for field, value in update_data.items():
        setattr(db_coverage, field, value)

    db.commit()
    db.refresh(db_coverage)

    return ShiftCoverageResponse.from_orm(db_coverage)


def delete_shift_coverage(
    db: Session,
    coverage_id: int,
    current_user: User
) -> bool:
    """Delete shift coverage record"""
    db_coverage = get_shift_coverage(db, coverage_id, current_user)

    if not db_coverage:
        return False

    db.delete(db_coverage)
    db.commit()

    return True
