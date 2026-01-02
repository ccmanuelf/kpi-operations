"""
Client Authorization Middleware
Multi-tenant access control and client isolation
"""
from typing import Optional, List
from fastapi import HTTPException, status
from backend.schemas.user import User, UserRole


class ClientAccessError(HTTPException):
    """Custom exception for client access violations"""
    def __init__(self, detail: str = "Access denied to this client's data"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


def get_user_client_filter(user: User) -> Optional[List[str]]:
    """
    Get list of client IDs the user can access

    Args:
        user: Authenticated user object

    Returns:
        None for ADMIN/POWERUSER (access all clients)
        List[str] of client IDs for LEADER/OPERATOR

    Raises:
        ClientAccessError: If user has no client assignment
    """
    # ADMIN and POWERUSER have access to all clients
    if user.role in [UserRole.ADMIN, UserRole.POWERUSER]:
        return None  # None = no filtering, access all

    # LEADER and OPERATOR must have client_id_assigned
    if not user.client_id_assigned:
        raise ClientAccessError(
            detail=f"User {user.username} has no client assignment. Contact administrator."
        )

    # Parse comma-separated client IDs
    # Example: "BOOT-LINE-A,CLIENT-B,CLIENT-C" -> ["BOOT-LINE-A", "CLIENT-B", "CLIENT-C"]
    user_clients = [c.strip() for c in user.client_id_assigned.split(',') if c.strip()]

    if not user_clients:
        raise ClientAccessError(
            detail=f"User {user.username} has invalid client assignment. Contact administrator."
        )

    return user_clients


def verify_client_access(user: User, resource_client_id: str) -> bool:
    """
    Verify user has access to a specific client's resource

    Args:
        user: Authenticated user object
        resource_client_id: Client ID of the resource being accessed

    Returns:
        True if user has access

    Raises:
        ClientAccessError: If user does not have access to this client

    Usage:
        # In API endpoint:
        verify_client_access(current_user, work_order.client_id)

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

    # Get user's authorized client list
    user_clients = get_user_client_filter(user)

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
