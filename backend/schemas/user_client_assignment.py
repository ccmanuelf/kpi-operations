"""
USER_CLIENT_ASSIGNMENT Junction Table ORM Schema
Phase 2.1: Data Layer Normalization

Replaces comma-separated client_id_assigned field with proper junction table.
Provides normalized user-to-client many-to-many relationship.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.database import Base


class UserClientAssignment(Base):
    """
    USER_CLIENT_ASSIGNMENT table - Junction for user to client mapping.

    This replaces the comma-separated client_id_assigned column in USER table.
    Each row represents one user's access to one client.
    """

    __tablename__ = "USER_CLIENT_ASSIGNMENT"
    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_user_client"),
        Index("idx_user_client_user", "user_id"),
        Index("idx_user_client_client", "client_id"),
        Index("idx_user_client_active", "is_active"),
        {"extend_existing": True},
    )

    # Primary key
    assignment_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    user_id = Column(String(50), ForeignKey("USER.user_id", ondelete="CASCADE"), nullable=False)
    client_id = Column(String(50), ForeignKey("CLIENT.client_id", ondelete="RESTRICT"), nullable=False)

    # Assignment metadata
    assigned_at = Column(DateTime, nullable=False, server_default=func.now())
    assigned_by = Column(String(50))  # User who made this assignment

    # Is this the user's primary/default client?
    is_primary = Column(Boolean, nullable=False, default=False)

    # Soft delete / deactivation
    is_active = Column(Boolean, nullable=False, default=True)
    deactivated_at = Column(DateTime)
    deactivated_by = Column(String(50))

    # Audit timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


def get_user_assigned_clients(db, user_id: str, active_only: bool = True):
    """
    Get all clients assigned to a user.

    Args:
        db: Database session
        user_id: User ID
        active_only: Only return active assignments

    Returns:
        List of client_id strings
    """
    query = db.query(UserClientAssignment.client_id).filter(UserClientAssignment.user_id == user_id)

    if active_only:
        query = query.filter(UserClientAssignment.is_active == True)

    return [row.client_id for row in query.all()]


def assign_user_to_client(
    db, user_id: str, client_id: str, assigned_by: str, is_primary: bool = False
) -> UserClientAssignment:
    """
    Assign a user to a client.

    Args:
        db: Database session
        user_id: User ID to assign
        client_id: Client ID to assign to
        assigned_by: User making the assignment
        is_primary: Whether this is the user's primary client

    Returns:
        Created UserClientAssignment

    Raises:
        IntegrityError: If assignment already exists
    """
    assignment = UserClientAssignment(
        user_id=user_id, client_id=client_id, assigned_by=assigned_by, is_primary=is_primary
    )

    db.add(assignment)
    db.flush()

    return assignment


def remove_user_from_client(db, user_id: str, client_id: str, removed_by: str) -> bool:
    """
    Remove (deactivate) a user's client assignment.

    Args:
        db: Database session
        user_id: User ID
        client_id: Client ID
        removed_by: User making the removal

    Returns:
        True if assignment was deactivated, False if not found
    """
    from datetime import datetime

    assignment = (
        db.query(UserClientAssignment)
        .filter(UserClientAssignment.user_id == user_id, UserClientAssignment.client_id == client_id)
        .first()
    )

    if not assignment:
        return False

    assignment.is_active = False
    assignment.deactivated_at = datetime.now(tz=timezone.utc)
    assignment.deactivated_by = removed_by

    return True
