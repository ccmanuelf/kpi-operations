"""
Defect Type Catalog Service
Thin service layer wrapping Defect Type Catalog CRUD operations.
Routes should import from this module instead of backend.crud.defect_type_catalog directly.
"""

from typing import Any, List, Optional
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.defect_type_catalog import (
    create_defect_type,
    get_defect_type,
    get_defect_types_by_client,
    get_global_defect_types,
    update_defect_type,
    delete_defect_type,
    bulk_create_defect_types,
    validate_defect_type_for_client,
    get_defect_type_by_name,
    GLOBAL_CLIENT_ID,
    is_global_client,
)


def create_defect_type_record(db: Session, defect_type_data: Any, current_user: User) -> Any:
    """Create a new defect type catalog entry."""
    return create_defect_type(db, defect_type_data, current_user)


def get_defect_type_by_id(db: Session, defect_type_id: str, current_user: User) -> Any:
    """Get a defect type by ID."""
    return get_defect_type(db, defect_type_id, current_user)


def list_defect_types_by_client(
    db: Session,
    client_id: str,
    current_user: User,
    include_inactive: bool = False,
    include_global: bool = True,
) -> Any:
    """List defect types for a client."""
    return get_defect_types_by_client(
        db,
        client_id,
        current_user,
        include_inactive=include_inactive,
        include_global=include_global,
    )


def list_global_defect_types(db: Session, include_inactive: bool = False) -> Any:
    """List global defect types."""
    return get_global_defect_types(db, include_inactive)


def update_defect_type_record(db: Session, defect_type_id: str, data: Any, current_user: User) -> Any:
    """Update a defect type catalog entry."""
    return update_defect_type(db, defect_type_id, data, current_user)


def delete_defect_type_record(db: Session, defect_type_id: str, current_user: User) -> bool:
    """Delete a defect type catalog entry."""
    return delete_defect_type(db, defect_type_id, current_user)


def bulk_create_defect_type_records(
    db: Session,
    client_id: str,
    defect_types: list,
    current_user: User,
    replace_existing: bool = False,
) -> Any:
    """Bulk create defect type catalog entries."""
    return bulk_create_defect_types(
        db,
        client_id,
        defect_types,
        current_user,
        replace_existing=replace_existing,
    )


def validate_defect_type(db: Session, client_id: str, defect_type_name: str) -> bool:
    """Validate a defect type exists for a client."""
    return validate_defect_type_for_client(db, client_id, defect_type_name)


def get_defect_type_by_name_and_client(db: Session, client_id: str, defect_type_name: str) -> Any:
    """Get a defect type by name within a client."""
    return get_defect_type_by_name(db, client_id, defect_type_name)
