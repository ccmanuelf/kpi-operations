"""
Client Authorization Middleware
Multi-tenant access control and client isolation

Phase 2.2: Updated to support both:
- Junction table (USER_CLIENT_ASSIGNMENT) - new normalized approach
- Comma-separated client_id_assigned field - legacy fallback
"""

import logging
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.schemas.user import User, UserRole

logger = logging.getLogger(__name__)


class ClientAccessError(HTTPException):
    """Custom exception for client access violations"""

    def __init__(self, detail: str = "Access denied to this client's data"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _get_clients_from_junction_table(db: Session, user_id: str) -> Optional[List[str]]:
    """
    Get client assignments from junction table (Phase 2 normalized approach).

    Args:
        db: Database session
        user_id: User ID

    Returns:
        List of client IDs or None if no assignments found
    """
    try:
        from backend.schemas.user_client_assignment import UserClientAssignment

        assignments = (
            db.query(UserClientAssignment.client_id)
            .filter(UserClientAssignment.user_id == user_id, UserClientAssignment.is_active == True)
            .all()
        )

        if assignments:
            return [a.client_id for a in assignments]
        return None
    except Exception:
        # Table doesn't exist yet or other error - fall back to legacy
        return None


def _get_clients_from_legacy_field(user: User) -> Optional[List[str]]:
    """
    Get client assignments from legacy comma-separated field.

    Args:
        user: User object

    Returns:
        List of client IDs or None if no assignments
    """
    if not user.client_id_assigned:
        return None

    # Parse comma-separated client IDs
    user_clients = [c.strip() for c in user.client_id_assigned.split(",") if c.strip()]

    return user_clients if user_clients else None


def get_user_client_filter(user: User, db: Session = None) -> Optional[List[str]]:
    """
    Get list of client IDs the user can access

    Phase 2.2: Supports both junction table and legacy comma-separated field.
    Tries junction table first, falls back to legacy field.

    JWT Freshness Note:
        This function reads client assignments from the DB user record
        (user.client_id_assigned) or the junction table — never from JWT
        claims. The user object passed here is loaded fresh from the DB
        by get_current_user on every request, so the client list is always
        current regardless of what the JWT token contains.

    Args:
        user: Authenticated user object (loaded from DB by get_current_user)
        db: Optional database session for junction table lookup

    Returns:
        None for ADMIN/POWERUSER (access all clients)
        List[str] of client IDs for LEADER/OPERATOR

    Raises:
        ClientAccessError: If user has no client assignment
    """
    # ADMIN and POWERUSER have access to all clients
    if user.role in [UserRole.ADMIN, UserRole.POWERUSER]:
        return None  # None = no filtering, access all

    # Try junction table first (if db session available)
    user_clients = None
    if db is not None:
        user_clients = _get_clients_from_junction_table(db, user.user_id)

    # Fall back to legacy comma-separated field
    if user_clients is None:
        user_clients = _get_clients_from_legacy_field(user)

    # LEADER and OPERATOR must have client assignment
    if not user_clients:
        raise ClientAccessError(detail=f"User {user.username} has no client assignment. Contact administrator.")

    return user_clients


def verify_client_access(user: User, resource_client_id: str, db: Session = None) -> bool:
    """
    Verify user has access to a specific client's resource

    Phase 2.2: Added db parameter for junction table support.

    JWT Freshness Note:
        The client_id in the JWT is set at login time. If a user's client
        association changes (e.g., admin reassignment), the stale JWT will
        still carry the old client_id until it expires.

        Mitigation: Short token expiry (30 min) + this function always checks
        against the DB user record (loaded by get_current_user), not the JWT
        claim. The get_current_user dependency (backend/auth/jwt.py) performs
        a full DB lookup on every request, so user.client_id_assigned is
        always the current DB value.

        Additionally, if the JWT-embedded client_ids drift from the DB value,
        a warning is logged for audit visibility. Hard enforcement of token
        revocation is deferred to the MariaDB production phase where a
        Redis-backed token blacklist will be available.

    Args:
        user: Authenticated user object (loaded from DB by get_current_user)
        resource_client_id: Client ID of the resource being accessed
        db: Optional database session for junction table lookup

    Returns:
        True if user has access

    Raises:
        ClientAccessError: If user does not have access to this client

    Usage:
        # In API endpoint:
        verify_client_access(current_user, work_order.client_id, db)

    Examples:
        >>> admin = User(role=UserRole.ADMIN)
        >>> verify_client_access(admin, "ANY-CLIENT")  # True - admin access all

        >>> operator = User(role=UserRole.OPERATOR, client_id_assigned="BOOT-LINE-A")
        >>> verify_client_access(operator, "BOOT-LINE-A")  # True - has access
        >>> verify_client_access(operator, "CLIENT-B")  # ClientAccessError - denied

        >>> leader = User(role=UserRole.LEADER, client_id_assigned="BOOT-LINE-A,CLIENT-B")
        >>> verify_client_access(leader, "CLIENT-B")  # True - multi-client access
    """
    # ADMIN and POWERUSER can access all clients
    if user.role in [UserRole.ADMIN, UserRole.POWERUSER]:
        return True

    # JWT freshness check: warn if JWT-embedded client_ids differ from DB record.
    # The _jwt_client_ids attribute is attached by get_current_user (auth/jwt.py).
    # This is a logging-only check — access decisions always use the DB record.
    jwt_client_ids = getattr(user, "_jwt_client_ids", None)
    db_client_ids = user.client_id_assigned
    if jwt_client_ids is not None and db_client_ids is not None:
        if jwt_client_ids.strip() != db_client_ids.strip():
            logger.warning(
                "JWT client_id freshness mismatch for user '%s': "
                "jwt_client_ids='%s', db_client_ids='%s'. "
                "User's client assignment may have changed since login.",
                user.username,
                jwt_client_ids,
                db_client_ids,
            )

    # Get user's authorized client list (always from DB record, not JWT)
    user_clients = get_user_client_filter(user, db)

    # Check if resource's client is in user's authorized list
    if resource_client_id not in user_clients:
        raise ClientAccessError(
            detail=f"Access denied: User {user.username} cannot access client '{resource_client_id}'"
        )

    return True


def build_client_filter_clause(user: User, client_id_column):
    """
    Build SQLAlchemy filter clause for client isolation

    Args:
        user: Authenticated user object
        client_id_column: SQLAlchemy column for client_id filtering

    Returns:
        SQLAlchemy filter clause or None (no filtering for ADMIN/POWERUSER)

    Usage:
        # In CRUD list operation:
        from sqlalchemy import and_

        query = db.query(WorkOrder)

        # Apply client filtering
        client_filter = build_client_filter_clause(current_user, WorkOrder.client_id)
        if client_filter is not None:
            query = query.filter(client_filter)

        results = query.all()

    Examples:
        >>> admin = User(role=UserRole.ADMIN)
        >>> build_client_filter_clause(admin, WorkOrder.client_id)  # None - no filter

        >>> operator = User(role=UserRole.OPERATOR, client_id_assigned="BOOT-LINE-A")
        >>> build_client_filter_clause(operator, WorkOrder.client_id)
        # WorkOrder.client_id.in_(["BOOT-LINE-A"])

        >>> leader = User(role=UserRole.LEADER, client_id_assigned="BOOT-LINE-A,CLIENT-B")
        >>> build_client_filter_clause(leader, WorkOrder.client_id)
        # WorkOrder.client_id.in_(["BOOT-LINE-A", "CLIENT-B"])
    """
    user_clients = get_user_client_filter(user)

    # None = ADMIN/POWERUSER, no filtering needed
    if user_clients is None:
        return None

    # Return IN clause for user's authorized clients
    return client_id_column.in_(user_clients)


# Convenience decorator for FastAPI endpoints
def require_client_access(resource_client_id: str):
    """
    Decorator to enforce client access verification in API endpoints

    Args:
        resource_client_id: Client ID to check access for

    Usage:
        @app.get("/api/v1/work-orders/{work_order_id}")
        @require_client_access(work_order.client_id)
        async def get_work_order(work_order_id: str, current_user: User = Depends(get_current_user)):
            # Access already verified by decorator
            return work_order
    """

    def decorator(func):
        async def wrapper(*args, current_user: User, **kwargs):
            verify_client_access(current_user, resource_client_id)
            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator
