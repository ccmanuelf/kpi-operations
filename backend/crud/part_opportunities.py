"""
CRUD operations for PART_OPPORTUNITIES (DPMO calculation metadata)
Create, Read, Update, Delete with multi-tenant client filtering
SECURITY: All operations enforce client-based access control
"""

import logging
from typing import Any, List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

from backend.orm.part_opportunities import PartOpportunities
from backend.orm.user import User
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.utils.soft_delete import soft_delete


def create_part_opportunity(db: Session, part_data: dict, current_user: User) -> PartOpportunities:
    """
    Create new part opportunity record
    SECURITY: Verifies user has access to the specified client

    Args:
        db: Database session
        part_data: Part opportunity data dictionary
        current_user: Authenticated user

    Returns:
        Created part opportunity

    Raises:
        ClientAccessError: If user doesn't have access to part_data['client_id_fk']
    """
    # Verify client access. .get returns Optional[Any] but
    # verify_client_access requires a real client_id string — surface a
    # KeyError early when the caller forgot to set it rather than handing
    # None into the access check.
    client_id_fk = part_data.get("client_id_fk")
    if not isinstance(client_id_fk, str) or not client_id_fk:
        raise ValueError("part_data['client_id_fk'] is required")
    verify_client_access(current_user, client_id_fk)

    db_part = PartOpportunities(**part_data)
    db.add(db_part)
    db.commit()
    db.refresh(db_part)
    return db_part


def get_part_opportunity(db: Session, part_number: str, current_user: User) -> Optional[PartOpportunities]:
    """
    Get part opportunity by part number with client filtering
    SECURITY: Returns None if user doesn't have access to part's client

    Args:
        db: Database session
        part_number: Part number (primary key)
        current_user: Authenticated user

    Returns:
        Part opportunity if found and user has access, None otherwise
    """
    query = db.query(PartOpportunities).filter(PartOpportunities.part_number == part_number)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, PartOpportunities.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.first()


def get_part_opportunities(db: Session, current_user: User, skip: int = 0, limit: int = 100) -> List[PartOpportunities]:
    """
    List part opportunities with client filtering
    SECURITY: Returns only part opportunities for user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of part opportunities user has access to
    """
    query = db.query(PartOpportunities)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, PartOpportunities.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.offset(skip).limit(limit).all()


def get_part_opportunities_by_category(db: Session, category: str, current_user: User) -> List[PartOpportunities]:
    """
    Get all part opportunities for a specific category with client filtering
    SECURITY: Returns only part opportunities for user's authorized clients

    Args:
        db: Database session
        category: Part category to filter by
        current_user: Authenticated user

    Returns:
        List of part opportunities in the category
    """
    query = db.query(PartOpportunities).filter(PartOpportunities.part_category == category)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, PartOpportunities.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.all()


def update_part_opportunity(
    db: Session, part_number: str, part_update: dict, current_user: User
) -> Optional[PartOpportunities]:
    """
    Update part opportunity with client access verification
    SECURITY: Verifies user has access to the part's client

    Args:
        db: Database session
        part_number: Part number to update
        part_update: Fields to update
        current_user: Authenticated user

    Returns:
        Updated part opportunity if found and user has access, None otherwise
    """
    part = get_part_opportunity(db, part_number, current_user)
    if not part:
        return None

    # Update fields
    for key, value in part_update.items():
        if hasattr(part, key) and key != "part_number":  # Prevent PK changes
            setattr(part, key, value)

    db.commit()
    db.refresh(part)
    return part


def delete_part_opportunity(db: Session, part_number: str, current_user: User) -> bool:
    """
    Soft delete part opportunity (sets is_active = False)
    SECURITY: Only deletes if user has access to the part's client

    Args:
        db: Database session
        part_number: Part number to delete
        current_user: Authenticated user

    Returns:
        True if soft deleted, False if not found or no access
    """
    part = get_part_opportunity(db, part_number, current_user)
    if not part:
        return False

    # Soft delete - preserves data integrity
    return soft_delete(db, part)


def bulk_import_opportunities(db: Session, opportunities_list: List[dict], current_user: User) -> Dict[str, Any]:
    """
    Bulk import part opportunities (for CSV imports)
    SECURITY: Validates client_id_fk for all records before import

    Args:
        db: Database session
        opportunities_list: List of part opportunity dictionaries
        current_user: Authenticated user

    Returns:
        Dictionary with success_count and failure_count

    Raises:
        ClientAccessError: If any record has unauthorized client_id_fk
    """
    success_count = 0
    failure_count = 0
    errors = []

    for idx, part_data in enumerate(opportunities_list):
        try:
            # Verify client access for each record. Both client_id_fk
            # and part_number must be present strings — bail with a
            # clear error otherwise rather than passing None deeper.
            row_client_id = part_data.get("client_id_fk")
            row_part_number = part_data.get("part_number")
            if not isinstance(row_client_id, str) or not row_client_id:
                raise ValueError("client_id_fk is required")
            if not isinstance(row_part_number, str) or not row_part_number:
                raise ValueError("part_number is required")

            verify_client_access(current_user, row_client_id)

            # Check if part already exists (update vs create)
            existing = get_part_opportunity(db, row_part_number, current_user)
            if existing:
                # Update existing
                for key, value in part_data.items():
                    if hasattr(existing, key) and key != "part_number":
                        setattr(existing, key, value)
            else:
                # Create new
                db_part = PartOpportunities(**part_data)
                db.add(db_part)

            success_count += 1
        except SQLAlchemyError:
            logger.exception("Database error importing part opportunity at row %d", idx + 1)
            failure_count += 1
            errors.append(f"Row {idx + 1}: Database error importing part opportunity")
        except (ValueError, TypeError, KeyError):
            logger.exception("Validation error importing part opportunity at row %d", idx + 1)
            failure_count += 1
            errors.append(f"Row {idx + 1}: Validation error importing part opportunity")

    # Commit all successful imports
    if success_count > 0:
        db.commit()

    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "errors": errors[:10],  # Return first 10 errors to avoid large responses
    }
