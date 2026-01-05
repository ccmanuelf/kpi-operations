"""
CRUD operations for DEFECT_DETAIL (Defect Tracking)
Create, Read, Update, Delete with multi-tenant client filtering
SECURITY: All operations enforce client-based access control
"""
from typing import List, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from fastapi import HTTPException

from backend.schemas.defect_detail import DefectDetail
from backend.schemas.user import User
from middleware.client_auth import verify_client_access, build_client_filter_clause


def create_defect_detail(
    db: Session,
    defect_data: dict,
    current_user: User
) -> DefectDetail:
    """
    Create new defect detail record
    SECURITY: Verifies user has access to the specified client

    Args:
        db: Database session
        defect_data: Defect detail data dictionary
        current_user: Authenticated user

    Returns:
        Created defect detail

    Raises:
        ClientAccessError: If user doesn't have access to defect_data['client_id_fk']
    """
    # Verify client access
    verify_client_access(current_user, defect_data.get('client_id_fk'))

    db_defect = DefectDetail(**defect_data)
    db.add(db_defect)
    db.commit()
    db.refresh(db_defect)
    return db_defect


def get_defect_detail(
    db: Session,
    defect_detail_id: str,
    current_user: User
) -> Optional[DefectDetail]:
    """
    Get defect detail by ID with client filtering
    SECURITY: Returns None if user doesn't have access to defect's client

    Args:
        db: Database session
        defect_detail_id: Defect detail ID
        current_user: Authenticated user

    Returns:
        Defect detail if found and user has access, None otherwise
    """
    query = db.query(DefectDetail).filter(DefectDetail.defect_detail_id == defect_detail_id)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, DefectDetail.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.first()


def get_defect_details(
    db: Session,
    current_user: User,
    quality_entry_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[DefectDetail]:
    """
    List defect details with client filtering
    SECURITY: Returns only defects for user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user
        quality_entry_id: Optional filter by quality entry
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of defect details user has access to
    """
    query = db.query(DefectDetail)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, DefectDetail.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Optional quality entry filter
    if quality_entry_id:
        query = query.filter(DefectDetail.quality_entry_id == quality_entry_id)

    return query.offset(skip).limit(limit).all()


def get_defect_details_by_quality_entry(
    db: Session,
    quality_entry_id: str,
    current_user: User
) -> List[DefectDetail]:
    """
    Get all defect details for a specific quality entry with client filtering
    SECURITY: Returns only defects for user's authorized clients

    Args:
        db: Database session
        quality_entry_id: Quality entry ID
        current_user: Authenticated user

    Returns:
        List of defect details for the quality entry
    """
    query = db.query(DefectDetail).filter(DefectDetail.quality_entry_id == quality_entry_id)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, DefectDetail.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.all()


def update_defect_detail(
    db: Session,
    defect_detail_id: str,
    defect_update: dict,
    current_user: User
) -> Optional[DefectDetail]:
    """
    Update defect detail with client access verification
    SECURITY: Verifies user has access to the defect's client

    Args:
        db: Database session
        defect_detail_id: Defect detail ID to update
        defect_update: Fields to update
        current_user: Authenticated user

    Returns:
        Updated defect detail if found and user has access, None otherwise
    """
    defect = get_defect_detail(db, defect_detail_id, current_user)
    if not defect:
        return None

    # Update fields
    for key, value in defect_update.items():
        if hasattr(defect, key) and key != 'defect_detail_id':  # Prevent ID changes
            setattr(defect, key, value)

    db.commit()
    db.refresh(defect)
    return defect


def delete_defect_detail(
    db: Session,
    defect_detail_id: str,
    current_user: User
) -> bool:
    """
    Delete defect detail with client access verification
    SECURITY: Only deletes if user has access to the defect's client

    Args:
        db: Database session
        defect_detail_id: Defect detail ID to delete
        current_user: Authenticated user

    Returns:
        True if deleted, False if not found or no access
    """
    defect = get_defect_detail(db, defect_detail_id, current_user)
    if not defect:
        return False

    db.delete(defect)
    db.commit()
    return True


def get_defect_summary_by_type(
    db: Session,
    current_user: User,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[dict]:
    """
    Get defect summary grouped by type with client filtering
    SECURITY: Returns only defects for user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of dicts with defect_type, total_count, and defect_count
    """
    query = db.query(
        DefectDetail.defect_type,
        func.count(DefectDetail.defect_detail_id).label('total_count'),
        func.sum(DefectDetail.defect_count).label('defect_count')
    )

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, DefectDetail.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply date filters if provided
    if start_date:
        query = query.filter(func.date(DefectDetail.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(DefectDetail.created_at) <= end_date)

    # Group by defect type
    results = query.group_by(DefectDetail.defect_type).all()

    return [
        {
            'defect_type': row.defect_type,
            'total_count': row.total_count,
            'defect_count': row.defect_count or 0
        }
        for row in results
    ]
