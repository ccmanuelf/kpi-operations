"""
Tenant Guard Utilities
Defensive checks for multi-tenant data isolation.

CRITICAL: These utilities provide the last line of defense for tenant isolation.
Always use these checks when accessing resources that may belong to different tenants.
"""

from typing import Optional, Any, TypeVar
from fastapi import HTTPException

from backend.exceptions.domain_exceptions import MultiTenantViolationError


T = TypeVar("T")


def verify_tenant_access(current_client_id: str, resource_client_id: str, resource_type: str = "resource") -> None:
    """
    Verify that the current user has access to a resource's tenant.

    This is a critical security check that should be called before any
    operation that accesses or modifies a resource belonging to a specific
    client/tenant.

    Args:
        current_client_id: The client_id of the current user/request context
        resource_client_id: The client_id of the resource being accessed
        resource_type: Description of the resource for error messages

    Raises:
        MultiTenantViolationError: If tenant access is denied

    Example:
        >>> verify_tenant_access("CLIENT-A", "CLIENT-A", "work_order")  # OK
        >>> verify_tenant_access("CLIENT-A", "CLIENT-B", "work_order")  # Raises!
    """
    if current_client_id != resource_client_id:
        raise MultiTenantViolationError(
            message=f"Access denied: {resource_type} belongs to different tenant",
            details={
                "requested_tenant": resource_client_id,
                "current_tenant": current_client_id,
                "resource_type": resource_type,
            },
        )


def build_client_filter_clause(model: Any, client_id: str) -> Any:
    """
    Build a SQLAlchemy filter clause for client isolation.

    Use this helper to consistently apply client_id filtering across
    all database queries to ensure tenant isolation.

    Args:
        model: SQLAlchemy model class with client_id column
        client_id: Client ID to filter by

    Returns:
        SQLAlchemy filter clause (model.client_id == client_id)

    Example:
        >>> query = session.query(WorkOrder).filter(
        ...     build_client_filter_clause(WorkOrder, "CLIENT-A")
        ... )
    """
    # Check for different possible client_id column names
    if hasattr(model, "client_id"):
        return model.client_id == client_id
    elif hasattr(model, "client_id_fk"):
        return model.client_id_fk == client_id
    else:
        raise AttributeError(f"Model {model.__name__} does not have client_id or client_id_fk column")


def ensure_client_id(client_id: Optional[str], context: str = "request") -> str:
    """
    Ensure client_id is provided, raise error if missing.

    This is a defensive check to prevent queries or operations that
    would operate without proper tenant context.

    Args:
        client_id: The client_id to validate (may be None or empty)
        context: Context for error message (e.g., "work_order_query")

    Returns:
        The validated client_id (guaranteed non-empty string)

    Raises:
        HTTPException: If client_id is None or empty string

    Example:
        >>> ensure_client_id("CLIENT-A", "work_order_query")
        'CLIENT-A'
        >>> ensure_client_id(None, "work_order_query")
        HTTPException(status_code=400, detail="client_id is required...")
    """
    if not client_id:
        raise HTTPException(status_code=400, detail=f"client_id is required for {context}")
    return client_id


def get_client_id_from_user(user: Any, allow_admin_override: bool = False) -> Optional[str]:
    """
    Extract client_id from user object with role-based logic.

    For regular users (OPERATOR, MANAGER), returns their assigned client_id.
    For ADMIN users, returns None if allow_admin_override is True (meaning
    they can access all tenants).

    Args:
        user: User object with role and client_id_assigned/client_id_fk attributes
        allow_admin_override: If True, ADMIN users get None (all-tenant access)

    Returns:
        client_id string, or None if admin with override

    Example:
        >>> get_client_id_from_user(operator_user)
        'CLIENT-A'
        >>> get_client_id_from_user(admin_user, allow_admin_override=True)
        None  # Admin can see all
    """
    if user is None:
        return None

    user_role = getattr(user, "role", None)

    # ADMIN/POWERUSER users may have all-tenant access
    if allow_admin_override and user_role in ("ADMIN", "admin", "POWERUSER", "poweruser"):
        return None  # No filter = all tenants

    # Regular users are restricted to their tenant
    # Check multiple possible attribute names for flexibility
    client_id = (
        getattr(user, "client_id_assigned", None)
        or getattr(user, "client_id_fk", None)
        or getattr(user, "client_id", None)
    )

    # client_id_assigned may contain comma-separated values, take first
    if client_id and "," in str(client_id):
        client_id = str(client_id).split(",")[0].strip()

    return client_id


def validate_resource_ownership(resource: T, current_client_id: str, resource_type: str = "resource") -> T:
    """
    Validate that a resource belongs to the current tenant and return it.

    This is useful for chaining - it validates and returns the resource
    if valid, or raises an exception if not.

    Args:
        resource: The resource object to validate
        current_client_id: The client_id of the current user
        resource_type: Description for error messages

    Returns:
        The same resource if validation passes

    Raises:
        MultiTenantViolationError: If resource belongs to different tenant

    Example:
        >>> work_order = session.query(WorkOrder).first()
        >>> validated_order = validate_resource_ownership(
        ...     work_order, "CLIENT-A", "work_order"
        ... )
    """
    if resource is None:
        return None

    # Check for different possible client_id attribute names
    resource_client_id = getattr(resource, "client_id", None) or getattr(resource, "client_id_fk", None)

    if resource_client_id and resource_client_id != current_client_id:
        raise MultiTenantViolationError(
            message=f"Access denied: {resource_type} belongs to different tenant",
            details={
                "resource_tenant": resource_client_id,
                "current_tenant": current_client_id,
                "resource_type": resource_type,
            },
        )

    return resource


def filter_resources_by_tenant(resources: list, client_id: str) -> list:
    """
    Filter a list of resources to only include those belonging to a tenant.

    This is a safety net for cases where database-level filtering might
    have been bypassed or incomplete.

    Args:
        resources: List of resource objects
        client_id: Client ID to filter by

    Returns:
        Filtered list containing only resources matching the client_id

    Example:
        >>> all_orders = session.query(WorkOrder).all()  # Potentially unfiltered
        >>> client_orders = filter_resources_by_tenant(all_orders, "CLIENT-A")
    """
    if not resources:
        return []

    filtered = []
    for resource in resources:
        resource_client_id = getattr(resource, "client_id", None) or getattr(resource, "client_id_fk", None)
        if resource_client_id == client_id:
            filtered.append(resource)

    return filtered
