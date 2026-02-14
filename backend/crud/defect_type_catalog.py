"""
CRUD operations for Client-specific Defect Type Catalog
Supports both client-specific and global defect types
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List
from datetime import datetime
import uuid

from backend.schemas.defect_type_catalog import DefectTypeCatalog
from backend.models.defect_type_catalog import (
    DefectTypeCatalogCreate,
    DefectTypeCatalogUpdate,
    DefectTypeCatalogResponse,
    DefectTypeCatalogCSVRow,
)
from backend.middleware.client_auth import verify_client_access
from backend.schemas.user import User

# Reserved client_id for global defect types available to all clients
GLOBAL_CLIENT_ID = "GLOBAL"


def is_global_client(client_id: str) -> bool:
    """Check if the client_id is the global/shared client"""
    return client_id.upper() == GLOBAL_CLIENT_ID


def generate_defect_type_id(client_id: str, defect_code: str) -> str:
    """Generate unique defect type ID"""
    return f"DT-{client_id}-{defect_code}-{uuid.uuid4().hex[:6].upper()}"


def create_defect_type(db: Session, defect_type: DefectTypeCatalogCreate, current_user: User) -> DefectTypeCatalog:
    """Create a new defect type for a client or globally"""
    # Global defect types require admin role
    if is_global_client(defect_type.client_id):
        if current_user.role not in ["admin", "supervisor"]:
            raise ValueError("Only admins can create global defect types")
    else:
        # Verify user has access to this client
        verify_client_access(current_user, defect_type.client_id)

    # Check if defect code already exists for this client
    existing = (
        db.query(DefectTypeCatalog)
        .filter(
            and_(
                DefectTypeCatalog.client_id == defect_type.client_id,
                DefectTypeCatalog.defect_code == defect_type.defect_code,
            )
        )
        .first()
    )

    if existing:
        raise ValueError(f"Defect code '{defect_type.defect_code}' already exists for this client")

    db_defect_type = DefectTypeCatalog(
        defect_type_id=generate_defect_type_id(defect_type.client_id, defect_type.defect_code),
        client_id=defect_type.client_id,
        defect_code=defect_type.defect_code,
        defect_name=defect_type.defect_name,
        description=defect_type.description,
        category=defect_type.category,
        severity_default=defect_type.severity_default,
        industry_standard_code=defect_type.industry_standard_code,
        sort_order=defect_type.sort_order,
        is_active=True,
    )

    db.add(db_defect_type)
    db.commit()
    db.refresh(db_defect_type)
    return db_defect_type


def get_defect_type(db: Session, defect_type_id: str, current_user: User) -> Optional[DefectTypeCatalog]:
    """Get a defect type by ID"""
    defect_type = db.query(DefectTypeCatalog).filter(DefectTypeCatalog.defect_type_id == defect_type_id).first()

    if defect_type and not is_global_client(defect_type.client_id):
        verify_client_access(current_user, defect_type.client_id)

    return defect_type


def get_defect_types_by_client(
    db: Session, client_id: str, current_user: User, include_inactive: bool = False, include_global: bool = True
) -> List[DefectTypeCatalog]:
    """
    Get all defect types for a specific client

    Args:
        client_id: The client ID to fetch defect types for
        include_inactive: Include inactive defect types
        include_global: Include global defect types (default True)

    Returns:
        List of defect types (client-specific + global if requested)
    """
    # Skip client access check for GLOBAL
    if not is_global_client(client_id):
        verify_client_access(current_user, client_id)

    # Build filter: client-specific OR global (if requested)
    if is_global_client(client_id):
        # If requesting GLOBAL specifically, only return global types
        client_filter = DefectTypeCatalog.client_id == GLOBAL_CLIENT_ID
    elif include_global:
        # Return both client-specific and global types
        client_filter = or_(DefectTypeCatalog.client_id == client_id, DefectTypeCatalog.client_id == GLOBAL_CLIENT_ID)
    else:
        # Only client-specific types
        client_filter = DefectTypeCatalog.client_id == client_id

    query = db.query(DefectTypeCatalog).filter(client_filter)

    if not include_inactive:
        query = query.filter(DefectTypeCatalog.is_active == True)

    return query.order_by(DefectTypeCatalog.sort_order, DefectTypeCatalog.defect_name).all()


def get_global_defect_types(db: Session, include_inactive: bool = False) -> List[DefectTypeCatalog]:
    """Get all global defect types (available to all clients)"""
    query = db.query(DefectTypeCatalog).filter(DefectTypeCatalog.client_id == GLOBAL_CLIENT_ID)

    if not include_inactive:
        query = query.filter(DefectTypeCatalog.is_active == True)

    return query.order_by(DefectTypeCatalog.sort_order, DefectTypeCatalog.defect_name).all()


def update_defect_type(
    db: Session, defect_type_id: str, defect_type_update: DefectTypeCatalogUpdate, current_user: User
) -> Optional[DefectTypeCatalog]:
    """Update a defect type"""
    db_defect_type = db.query(DefectTypeCatalog).filter(DefectTypeCatalog.defect_type_id == defect_type_id).first()

    if not db_defect_type:
        return None

    # Global defect types require admin role
    if is_global_client(db_defect_type.client_id):
        if current_user.role not in ["admin", "supervisor"]:
            raise ValueError("Only admins can update global defect types")
    else:
        verify_client_access(current_user, db_defect_type.client_id)

    update_data = defect_type_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_defect_type, field, value)

    db_defect_type.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_defect_type)
    return db_defect_type


def delete_defect_type(db: Session, defect_type_id: str, current_user: User) -> bool:
    """Soft delete a defect type (sets is_active = False)"""
    db_defect_type = db.query(DefectTypeCatalog).filter(DefectTypeCatalog.defect_type_id == defect_type_id).first()

    if not db_defect_type:
        return False

    # Global defect types require admin role
    if is_global_client(db_defect_type.client_id):
        if current_user.role not in ["admin", "supervisor"]:
            raise ValueError("Only admins can delete global defect types")
    else:
        verify_client_access(current_user, db_defect_type.client_id)

    db_defect_type.is_active = False
    db_defect_type.updated_at = datetime.utcnow()
    db.commit()
    return True


def bulk_create_defect_types(
    db: Session,
    client_id: str,
    defect_types: List[DefectTypeCatalogCSVRow],
    current_user: User,
    replace_existing: bool = False,
) -> dict:
    """
    Bulk create defect types from CSV data
    Returns summary of created, skipped, and errors
    """
    # Global defect types require admin role
    if is_global_client(client_id):
        if current_user.role not in ["admin", "supervisor"]:
            raise ValueError("Only admins can bulk create global defect types")
    else:
        verify_client_access(current_user, client_id)

    if replace_existing:
        # Deactivate all existing defect types for this client
        db.query(DefectTypeCatalog).filter(DefectTypeCatalog.client_id == client_id).update(
            {"is_active": False, "updated_at": datetime.utcnow()}
        )
        db.commit()

    created = 0
    skipped = 0
    errors = []

    for idx, dt in enumerate(defect_types):
        try:
            # Check if already exists
            existing = (
                db.query(DefectTypeCatalog)
                .filter(and_(DefectTypeCatalog.client_id == client_id, DefectTypeCatalog.defect_code == dt.defect_code))
                .first()
            )

            if existing:
                if replace_existing:
                    # Reactivate and update
                    existing.defect_name = dt.defect_name
                    existing.description = dt.description
                    existing.category = dt.category
                    existing.severity_default = dt.severity_default
                    existing.industry_standard_code = dt.industry_standard_code
                    existing.sort_order = dt.sort_order
                    existing.is_active = True
                    existing.updated_at = datetime.utcnow()
                    created += 1
                else:
                    skipped += 1
                continue

            db_defect_type = DefectTypeCatalog(
                defect_type_id=generate_defect_type_id(client_id, dt.defect_code),
                client_id=client_id,
                defect_code=dt.defect_code,
                defect_name=dt.defect_name,
                description=dt.description,
                category=dt.category,
                severity_default=dt.severity_default,
                industry_standard_code=dt.industry_standard_code,
                sort_order=dt.sort_order,
                is_active=True,
            )
            db.add(db_defect_type)
            created += 1

        except Exception as e:
            errors.append({"row": idx + 1, "defect_code": dt.defect_code, "error": str(e)})

    db.commit()

    return {"created": created, "skipped": skipped, "errors": errors, "total_processed": len(defect_types)}


def validate_defect_type_for_client(db: Session, client_id: str, defect_type_name: str) -> bool:
    """
    Validate that a defect type name is valid for a client
    Used when creating defect details
    """
    exists = (
        db.query(DefectTypeCatalog)
        .filter(
            and_(
                DefectTypeCatalog.client_id == client_id,
                DefectTypeCatalog.defect_name == defect_type_name,
                DefectTypeCatalog.is_active == True,
            )
        )
        .first()
    )
    return exists is not None


def get_defect_type_by_name(db: Session, client_id: str, defect_type_name: str) -> Optional[DefectTypeCatalog]:
    """Get defect type by name for a client"""
    return (
        db.query(DefectTypeCatalog)
        .filter(
            and_(
                DefectTypeCatalog.client_id == client_id,
                DefectTypeCatalog.defect_name == defect_type_name,
                DefectTypeCatalog.is_active == True,
            )
        )
        .first()
    )
