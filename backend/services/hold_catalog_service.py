"""
Hold Catalog Service
Thin service layer wrapping Hold Catalog CRUD operations.
Routes should import from this module instead of backend.crud.hold_catalog directly.
"""

from sqlalchemy.orm import Session

from backend.crud.hold_catalog import (
    create_hold_status,
    list_hold_statuses,
    update_hold_status,
    deactivate_hold_status,
    create_hold_reason,
    list_hold_reasons,
    update_hold_reason,
    deactivate_hold_reason,
    validate_hold_status_for_client,
    validate_hold_reason_for_client,
    seed_defaults,
)


def create_hold_status_record(db: Session, data):
    """Create a new hold status catalog entry."""
    return create_hold_status(db, data)


def list_hold_status_records(db: Session, client_id: str, include_inactive: bool = False):
    """List hold statuses for a client."""
    return list_hold_statuses(db, client_id, include_inactive)


def update_hold_status_record(db: Session, catalog_id: int, data):
    """Update a hold status catalog entry."""
    return update_hold_status(db, catalog_id, data)


def deactivate_hold_status_record(db: Session, catalog_id: int) -> bool:
    """Deactivate a hold status catalog entry."""
    return deactivate_hold_status(db, catalog_id)


def create_hold_reason_record(db: Session, data):
    """Create a new hold reason catalog entry."""
    return create_hold_reason(db, data)


def list_hold_reason_records(db: Session, client_id: str, include_inactive: bool = False):
    """List hold reasons for a client."""
    return list_hold_reasons(db, client_id, include_inactive)


def update_hold_reason_record(db: Session, catalog_id: int, data):
    """Update a hold reason catalog entry."""
    return update_hold_reason(db, catalog_id, data)


def deactivate_hold_reason_record(db: Session, catalog_id: int) -> bool:
    """Deactivate a hold reason catalog entry."""
    return deactivate_hold_reason(db, catalog_id)


def validate_hold_status(db: Session, client_id: str, status_code: str) -> bool:
    """Validate that a hold status exists for a client."""
    return validate_hold_status_for_client(db, client_id, status_code)


def validate_hold_reason(db: Session, client_id: str, reason_code: str) -> bool:
    """Validate that a hold reason exists for a client."""
    return validate_hold_reason_for_client(db, client_id, reason_code)


def seed_default_catalogs(db: Session, client_id: str) -> dict:
    """Seed default hold statuses and reasons for a client."""
    return seed_defaults(db, client_id)
