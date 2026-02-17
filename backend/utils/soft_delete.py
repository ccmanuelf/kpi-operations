"""
Soft Delete Utility Module
==========================
Generic soft delete functionality that can be reused across all CRUD operations.

Soft delete sets is_active = False instead of performing actual database deletion,
preserving data integrity and allowing potential recovery.

Usage:
    from backend.utils.soft_delete import soft_delete, get_active_query

    # In delete function:
    success = soft_delete(db, entity, logger_name="employee")

    # In list function:
    query = get_active_query(db, Model)
"""

from datetime import datetime, timezone
from typing import TypeVar, Optional, Type, Any, Callable
from sqlalchemy.orm import Session, Query
from sqlalchemy import Column, Boolean, DateTime, Integer
import logging

# Generic type for SQLAlchemy models
T = TypeVar("T")

logger = logging.getLogger(__name__)


def soft_delete(
    db: Session, entity: Any, commit: bool = True, is_active_field: str = "is_active", inactive_value: Any = False
) -> bool:
    """
    Perform soft delete on an entity by setting is_active = False.

    This function handles both boolean and integer is_active fields:
    - Boolean: Sets to False
    - Integer: Sets to 0

    Args:
        db: SQLAlchemy database session
        entity: The SQLAlchemy model instance to soft delete
        commit: Whether to commit the transaction (default: True)
        is_active_field: Name of the is_active field (default: "is_active")
        inactive_value: Value to set for inactive state (default: False, auto-detects int/bool)

    Returns:
        True if soft delete was successful, False otherwise

    Example:
        db_employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
        if db_employee:
            success = soft_delete(db, db_employee)
    """
    try:
        if not hasattr(entity, is_active_field):
            logger.warning(
                f"Entity {type(entity).__name__} does not have '{is_active_field}' field. "
                f"Cannot perform soft delete."
            )
            return False

        # Detect field type and set appropriate value
        current_value = getattr(entity, is_active_field)

        # Handle integer is_active fields (common in SQLite)
        if isinstance(current_value, int) or inactive_value == 0:
            setattr(entity, is_active_field, 0)
        else:
            setattr(entity, is_active_field, False)

        if commit:
            db.commit()

        logger.debug(
            f"Soft deleted {type(entity).__name__} " f"(set {is_active_field} = {getattr(entity, is_active_field)})"
        )

        return True

    except Exception as e:
        logger.error(f"Soft delete failed for {type(entity).__name__}: {str(e)}")
        if commit:
            db.rollback()
        return False


def soft_delete_with_timestamp(
    db: Session,
    entity: Any,
    commit: bool = True,
    is_active_field: str = "is_active",
    deleted_at_field: str = "deleted_at",
    deleted_by_field: Optional[str] = "deleted_by",
    deleted_by_value: Optional[int] = None,
) -> bool:
    """
    Perform soft delete with timestamp tracking.

    Sets is_active = False and records deletion timestamp and user.

    Args:
        db: SQLAlchemy database session
        entity: The SQLAlchemy model instance to soft delete
        commit: Whether to commit the transaction (default: True)
        is_active_field: Name of the is_active field (default: "is_active")
        deleted_at_field: Name of the deleted_at timestamp field (default: "deleted_at")
        deleted_by_field: Name of the deleted_by user field (default: "deleted_by")
        deleted_by_value: User ID who performed the deletion (optional)

    Returns:
        True if soft delete was successful, False otherwise
    """
    try:
        # Perform basic soft delete
        if not soft_delete(db, entity, commit=False, is_active_field=is_active_field):
            return False

        # Set timestamp if field exists
        if hasattr(entity, deleted_at_field):
            setattr(entity, deleted_at_field, datetime.now(tz=timezone.utc))

        # Set deleted_by if field exists and value provided
        if deleted_by_value is not None and hasattr(entity, deleted_by_field):
            setattr(entity, deleted_by_field, deleted_by_value)

        if commit:
            db.commit()

        return True

    except Exception as e:
        logger.error(f"Soft delete with timestamp failed: {str(e)}")
        if commit:
            db.rollback()
        return False


def restore_soft_deleted(
    db: Session, entity: Any, commit: bool = True, is_active_field: str = "is_active", active_value: Any = True
) -> bool:
    """
    Restore a soft-deleted entity by setting is_active = True.

    Args:
        db: SQLAlchemy database session
        entity: The SQLAlchemy model instance to restore
        commit: Whether to commit the transaction (default: True)
        is_active_field: Name of the is_active field (default: "is_active")
        active_value: Value to set for active state (default: True, auto-detects int/bool)

    Returns:
        True if restore was successful, False otherwise
    """
    try:
        if not hasattr(entity, is_active_field):
            logger.warning(f"Entity {type(entity).__name__} does not have '{is_active_field}' field.")
            return False

        # Detect field type and set appropriate value
        current_value = getattr(entity, is_active_field)

        if isinstance(current_value, int) or active_value == 1:
            setattr(entity, is_active_field, 1)
        else:
            setattr(entity, is_active_field, True)

        # Clear deleted_at if it exists
        if hasattr(entity, "deleted_at"):
            setattr(entity, "deleted_at", None)

        # Clear deleted_by if it exists
        if hasattr(entity, "deleted_by"):
            setattr(entity, "deleted_by", None)

        if commit:
            db.commit()

        logger.debug(f"Restored soft-deleted {type(entity).__name__}")

        return True

    except Exception as e:
        logger.error(f"Restore failed for {type(entity).__name__}: {str(e)}")
        if commit:
            db.rollback()
        return False


def get_active_query(db: Session, model: Type[T], is_active_field: str = "is_active") -> Query:
    """
    Get a query filtered to only active (non-deleted) records.

    Automatically handles both boolean and integer is_active fields.

    Args:
        db: SQLAlchemy database session
        model: The SQLAlchemy model class
        is_active_field: Name of the is_active field (default: "is_active")

    Returns:
        SQLAlchemy Query filtered to active records only

    Example:
        # Instead of: db.query(Employee)
        # Use: get_active_query(db, Employee)
        active_employees = get_active_query(db, Employee).all()
    """
    query = db.query(model)

    if hasattr(model, is_active_field):
        # Try integer comparison first (common in SQLite)
        try:
            query = query.filter(getattr(model, is_active_field) == 1)
        except Exception:
            # Fall back to boolean
            query = query.filter(getattr(model, is_active_field) == True)

    return query


def get_all_including_deleted(db: Session, model: Type[T]) -> Query:
    """
    Get a query including all records (active and soft-deleted).

    Useful for admin views or audit purposes.

    Args:
        db: SQLAlchemy database session
        model: The SQLAlchemy model class

    Returns:
        SQLAlchemy Query without is_active filtering
    """
    return db.query(model)


def filter_active(query: Query, model: Type[T], is_active_field: str = "is_active") -> Query:
    """
    Add active filter to an existing query.

    Useful when you need to add the filter to an existing query chain.

    Args:
        query: Existing SQLAlchemy query
        model: The SQLAlchemy model class
        is_active_field: Name of the is_active field (default: "is_active")

    Returns:
        Query with active filter added

    Example:
        query = db.query(Employee).filter(Employee.department == "Engineering")
        query = filter_active(query, Employee)
    """
    if hasattr(model, is_active_field):
        try:
            query = query.filter(getattr(model, is_active_field) == 1)
        except Exception:
            query = query.filter(getattr(model, is_active_field) == True)

    return query


class SoftDeleteMixin:
    """
    Mixin class that can be added to SQLAlchemy models for soft delete support.

    Adds is_active, deleted_at, and deleted_by columns.

    Usage:
        class Employee(Base, SoftDeleteMixin):
            __tablename__ = "employees"
            employee_id = Column(Integer, primary_key=True)
            # ... other columns

    Note: This is provided for reference. Existing models already have
    is_active fields, so this mixin is mainly useful for new models.
    """

    is_active = Column(Boolean, default=True, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, nullable=True)

    def soft_delete(self, db: Session, deleted_by_user: Optional[int] = None) -> bool:
        """Instance method for soft delete."""
        return soft_delete_with_timestamp(db, self, deleted_by_value=deleted_by_user)

    def restore(self, db: Session) -> bool:
        """Instance method to restore soft-deleted record."""
        return restore_soft_deleted(db, self)

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft-deleted."""
        if hasattr(self, "is_active"):
            # Handle both boolean and integer
            return self.is_active in (False, 0)
        return False


def create_soft_delete_function(
    model: Type[T], id_field: str, is_active_field: str = "is_active", permission_check: Optional[Callable] = None
) -> Callable:
    """
    Factory function to create standardized soft delete functions for CRUD modules.

    This is useful for creating consistent delete functions across modules.

    Args:
        model: The SQLAlchemy model class
        id_field: Name of the primary key field
        is_active_field: Name of the is_active field (default: "is_active")
        permission_check: Optional callback for permission validation

    Returns:
        A delete function configured for the specified model

    Example:
        delete_employee = create_soft_delete_function(
            Employee,
            "employee_id",
            permission_check=lambda user: user.role == "admin"
        )
    """

    def delete_fn(db: Session, entity_id: Any, current_user: Any = None) -> bool:
        # Permission check if provided
        if permission_check and current_user:
            if not permission_check(current_user):
                return False

        # Get entity
        entity = db.query(model).filter(getattr(model, id_field) == entity_id).first()

        if not entity:
            return False

        return soft_delete(db, entity, is_active_field=is_active_field)

    return delete_fn
