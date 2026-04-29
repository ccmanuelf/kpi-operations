"""
Part Opportunity Service
Thin service layer wrapping Part Opportunity CRUD operations.
Routes should import from this module instead of backend.crud.part_opportunities directly.
"""

from typing import Any, List, Dict, Optional
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.part_opportunities import (
    create_part_opportunity,
    get_part_opportunity,
    get_part_opportunities,
    get_part_opportunities_by_category,
    update_part_opportunity,
    delete_part_opportunity,
    bulk_import_opportunities,
)


def create_opportunity(db: Session, part_data: dict, current_user: User) -> Any:
    """Create a new part opportunity."""
    return create_part_opportunity(db, part_data, current_user)


def get_opportunity(db: Session, part_number: str, current_user: User) -> Any:
    """Get a part opportunity by part number."""
    return get_part_opportunity(db, part_number, current_user)


def list_opportunities(db: Session, current_user: User, skip: int = 0, limit: int = 100) -> Any:
    """List part opportunities."""
    return get_part_opportunities(db, current_user, skip, limit)


def list_opportunities_by_category(db: Session, category: str, current_user: User) -> Any:
    """List part opportunities by category."""
    return get_part_opportunities_by_category(db, category, current_user)


def update_opportunity(db: Session, part_number: str, part_data: dict, current_user: User) -> Any:
    """Update a part opportunity."""
    return update_part_opportunity(db, part_number, part_data, current_user)


def delete_opportunity(db: Session, part_number: str, current_user: User) -> bool:
    """Delete a part opportunity."""
    return delete_part_opportunity(db, part_number, current_user)


def bulk_import(db: Session, opportunities_list: List[dict], current_user: User) -> Dict[str, int]:
    """Bulk import part opportunities."""
    return bulk_import_opportunities(db, opportunities_list, current_user)
