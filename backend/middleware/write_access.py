"""
Write Access Control Middleware

Role-based dependency functions that restrict write (POST/PUT/PATCH/DELETE)
access to specific functional areas. All read (GET) access remains unrestricted
for authenticated users.

Usage:
    Apply as a FastAPI dependency on write-method route definitions:

        @router.post("/items", dependencies=[Depends(require_capacity_write)])
        def create_item(...): ...

Rules:
    - require_capacity_write: blocks POWERUSER (supervisor) from modifying
      Capacity Planning data. ADMIN, OPERATOR, LEADER allowed.
    - require_operations_write: placeholder for future PLANNER role restriction.
      Currently allows all existing roles.
"""

from fastapi import Depends, HTTPException, status

from backend.auth.jwt import get_current_user
from backend.schemas.user import User, UserRole
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


def require_operations_write(current_user: User = Depends(get_current_user)) -> User:
    """Deny write access to KPI operations data for a future PLANNER role.

    Currently all existing roles (ADMIN, POWERUSER, LEADER, OPERATOR) are
    permitted to write operations data. When a PLANNER role is added to
    UserRole, this function should be updated to block it.

    Args:
        current_user: The authenticated user from JWT.

    Returns:
        The current user if write access is granted.
    """
    # Placeholder: all current roles can write operations data.
    # When PLANNER role is added, uncomment:
    # if current_user.role == UserRole.PLANNER.value:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Planners do not have write access to KPI Operations data",
    #     )
    return current_user


def require_capacity_write(current_user: User = Depends(get_current_user)) -> User:
    """Deny write access to Capacity Planning data for POWERUSER (supervisor).

    Supervisors (POWERUSER) can view all Capacity Planning data but cannot
    create, update, or delete records. ADMIN, LEADER, and OPERATOR roles
    retain full write access.

    Args:
        current_user: The authenticated user from JWT.

    Returns:
        The current user if write access is granted.

    Raises:
        HTTPException: 403 if the user is a POWERUSER (supervisor).
    """
    if current_user.role in (UserRole.POWERUSER.value, UserRole.POWERUSER):
        logger.warning(
            "Capacity Planning write access denied for supervisor",
            extra={"user_id": current_user.user_id, "role": current_user.role},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisors do not have write access to Capacity Planning data",
        )
    return current_user
