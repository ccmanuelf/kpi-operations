"""
Production CRUD Service
Thin service layer wrapping Production Entry CRUD operations.
Routes should import from this module instead of backend.crud.production directly.

Note: The ProductionService class in backend.services.production_service provides
a class-based wrapper with DI support. This module provides functional wrappers
for routes that call CRUD functions directly.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.production import (
    create_production_entry,
    get_production_entry,
    get_production_entries,
    update_production_entry,
    delete_production_entry,
    get_production_entry_with_details,
    get_daily_summary,
    batch_create_entries,
)


def create_entry(db: Session, data, current_user: User):
    """Create a new production entry."""
    return create_production_entry(db, data, current_user)


def get_entry(db: Session, entry_id: int, current_user: User):
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
):
    """List production entries with filters."""
    return get_production_entries(db, current_user, skip, limit, start_date, end_date, product_id, shift_id, client_id)


def update_entry(db: Session, entry_id: int, data, current_user: User):
    """Update a production entry."""
    return update_production_entry(db, entry_id, data, current_user)


def delete_entry(db: Session, entry_id: int, current_user: User) -> bool:
    """Delete a production entry."""
    return delete_production_entry(db, entry_id, current_user)


def get_entry_with_details(db: Session, entry_id: int, current_user: User):
    """Get a production entry with full KPI breakdown."""
    return get_production_entry_with_details(db, entry_id, current_user)


def get_daily_production_summary(
    db: Session, current_user: User, start_date: date, end_date: Optional[date] = None, client_id: Optional[str] = None
):
    """Get daily production summary."""
    return get_daily_summary(db, current_user, start_date, end_date, client_id)


def batch_create(db: Session, entries: list, current_user: User):
    """Batch create production entries."""
    return batch_create_entries(db, entries, current_user)
