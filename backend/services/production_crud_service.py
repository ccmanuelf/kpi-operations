"""
Production CRUD Service
Thin service layer wrapping Production Entry CRUD operations.
Routes should import from this module instead of backend.crud.production directly.

Note: The ProductionService class in backend.services.production_service provides
a class-based wrapper with DI support. This module provides functional wrappers
for routes that call CRUD functions directly.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.crud.production import (
    batch_create_entries,
    create_production_entry,
    delete_production_entry,
    get_daily_summary,
    get_production_entries,
    get_production_entry,
    get_production_entry_with_details,
    update_production_entry,
)
from backend.orm.production_entry import ProductionEntry
from backend.orm.user import User
from backend.schemas.production import ProductionEntryCreate, ProductionEntryUpdate


def create_entry(db: Session, data: ProductionEntryCreate, current_user: User) -> ProductionEntry:
    """Create a new production entry."""
    return create_production_entry(db, data, current_user)


def get_entry(db: Session, entry_id: str, current_user: User) -> Optional[ProductionEntry]:
    """Get a production entry by ID."""
    return get_production_entry(db, entry_id, current_user)


def list_entries(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    client_id: Optional[str] = None,
) -> List[ProductionEntry]:
    """List production entries with filters."""
    return get_production_entries(db, current_user, skip, limit, start_date, end_date, product_id, shift_id, client_id)


def update_entry(
    db: Session, entry_id: str, data: ProductionEntryUpdate, current_user: User
) -> Optional[ProductionEntry]:
    """Update a production entry."""
    return update_production_entry(db, entry_id, data, current_user)


def delete_entry(db: Session, entry_id: str, current_user: User) -> bool:
    """Delete a production entry."""
    return delete_production_entry(db, entry_id, current_user)


def get_entry_with_details(db: Session, entry_id: str, current_user: User):
    """Get a production entry with full KPI breakdown."""
    return get_production_entry_with_details(db, entry_id, current_user)


def get_daily_production_summary(
    db: Session, current_user: User, start_date: date, end_date: Optional[date] = None, client_id: Optional[str] = None
) -> List[dict]:
    """Get daily production summary."""
    return get_daily_summary(db, current_user, start_date, end_date, client_id)


def batch_create(db: Session, entries: List[ProductionEntryCreate], current_user: User) -> List[ProductionEntry]:
    """Batch create production entries."""
    return batch_create_entries(db, entries, current_user)
