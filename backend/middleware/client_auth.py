"""
Client Authorization Middleware
Multi-tenant access control and client isolation

Phase 2.2: Updated to support both:
- Junction table (USER_CLIENT_ASSIGNMENT) - new normalized approach
- Comma-separated client_id_assigned field - legacy fallback
"""

import logging
from typing import Any, Optional, List
from fastapi import HTTPException, status
from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session
from backend.orm.user import User, UserRole

logger = logging.getLogger(__name__)


#: Sentinel distinguishing "column absent" from "column is NULL". `or \"\"`
#: collapsed the two, turning an uninspectable row into an access grant.
_UNSET = object()


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
        from backend.orm.user_client_assignment import UserClientAssignment

        assignments = (
            db.query(UserClientAssignment.client_id)
            .filter(UserClientAssignment.user_id == user_id, UserClientAssignment.is_active.is_(True))
            .all()
        )

        if assignments:
            return [a.client_id for a in assignments]
        return None
    except Exception as e:
        # Table doesn't exist yet or other error - fall back to legacy
        logger.warning("Junction table lookup failed for user %s, falling back to legacy: %s", user_id, e)
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


def get_user_client_filter(user: User, db: Optional[Session] = None) -> Optional[List[str]]:
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


def verify_client_access(user: User, resource_client_id: str, db: Optional[Session] = None) -> bool:
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
                "JWT client_id freshness mismatch for user %s — JWT has [%s] but DB has [%s]. Token may be stale.",
                user.username,
                jwt_client_ids.strip(),
                db_client_ids.strip(),
            )

    # Get user's authorized client list (always from DB record, not JWT).
    # ADMIN/POWERUSER returned True above, so by here the function is
    # guaranteed to return a non-None list (or raise ClientAccessError).
    user_clients = get_user_client_filter(user, db)
    assert user_clients is not None

    # Check if resource's client is in user's authorized list
    if resource_client_id not in user_clients:
        raise ClientAccessError(
            detail=f"Access denied: User {user.username} cannot access client '{resource_client_id}'"
        )

    return True


def verify_employee_access(user: User, employee: Any, db: Optional[Session] = None) -> bool:
    """
    Verify user has access to a specific EMPLOYEE row.

    EMPLOYEE has no ``client_id`` column: ownership lives in the
    comma-separated ``EMPLOYEE.client_id_assigned``, which is the shape the
    seeder writes (``seed/writers_master.py``) and the shape
    ``crud/employee/client_assignment.get_employees_by_client`` filters on.
    Access is granted when at least ONE of the employee's assigned clients is
    in the caller's authorized set — an employee may legitimately be shared by
    several clients.

    **NULL, and only NULL, means "shared floating-pool resource"** —
    ``EmployeeCreate.client_id_assigned`` documents it as "Comma-separated
    client IDs, NULL for floating pool". A blank or whitespace-only string is a
    MALFORMED assignment, not a shared one, and is denied. Treating it as
    shared was a privilege-escalation path: ``EmployeeUpdate`` has no
    ``min_length`` and ``PUT /api/employees/{id}`` is supervisor-tier, so a
    supervisor could set ``client_id_assigned=""`` on an employee they own and
    publish it to every tenant — while ``get_employees`` (which admits only
    ``IS NULL``) went on hiding it, making the by-id route MORE permissive than
    the listing. The two now agree; pinned by
    ``test_cross_tenant_authz.py::test_blank_client_assignment_is_not_shared``.

    Fails CLOSED. If the employee row is missing, or does not expose
    ``client_id_assigned`` at all (a partial projection, a ``Row``, ``None``),
    this raises rather than granting: an authorization helper that cannot
    inspect the field it authorizes on has no basis to allow anything.

    Args:
        user: Authenticated user object (loaded from DB by get_current_user)
        employee: EMPLOYEE ORM row whose access is being checked
        db: Optional database session for junction table lookup

    Returns:
        True if user has access

    Raises:
        ClientAccessError: if the row cannot be inspected, if its assignment is
            malformed, or if none of its clients is in the caller's set
    """
    # Fail closed BEFORE the role bypass: an uninspectable row is a caller bug,
    # and a loud 403 is the safe way to surface it.
    if employee is None:
        raise ClientAccessError(detail="Access denied: no employee record to authorize")
    assigned = getattr(employee, "client_id_assigned", _UNSET)
    if assigned is _UNSET:
        raise ClientAccessError(detail="Access denied: employee record does not expose client_id_assigned")

    if user.role in [UserRole.ADMIN, UserRole.POWERUSER]:
        return True

    if assigned is None:
        # The documented shared floating-pool marker.
        return True

    owners = [c.strip() for c in str(assigned).split(",") if c.strip()]
    if not owners:
        raise ClientAccessError(
            detail=f"Access denied: User {user.username} cannot access an employee " f"whose client assignment is blank"
        )

    user_clients = get_user_client_filter(user, db)
    assert user_clients is not None  # ADMIN/POWERUSER returned True above

    if not any(owner in user_clients for owner in owners):
        raise ClientAccessError(detail=f"Access denied: User {user.username} cannot access client '{owners[0]}'")

    return True


#: Hex of a comma. HEX() renders every byte as two uppercase hex digits, so a
#: comma-delimited list becomes a hex string in which token boundaries are
#: exactly this sequence and nothing else can look like one.
_COMMA_HEX = ",".encode().hex().upper()


def client_token_clause(column: Any, client_id: str) -> Any:
    """SQL clause: comma-separated ``column`` contains ``client_id`` as an EXACT token.

    Three ways the obvious spellings are wrong, and all three leak or diverge:

    * ``column.like(f"%{client_id}%")`` matches a client id that is a SUBSTRING
      of another — a caller scoped to ``ACME`` lists ``ACME-WEST``'s employees,
      and a plain ``DEMO`` client would pull in every ``DEMO-*`` tenant.
    * It also treats ``%`` and ``_`` inside a client id as wildcards, and
      ``seed/cli.py``'s ``SAMPLE_REF`` already contains one.
    * Anchored ``LIKE`` fixes both but introduces a third: ``=`` is
      case-SENSITIVE on SQLite while ``LIKE`` is case-INsensitive, so the same
      clause matched ``'acme,OTHER'`` and not ``'acme'`` — case-sensitive for a
      single token, case-insensitive for a list, on one engine, and neither
      agreeing with the case-sensitive Python split in
      ``verify_employee_access``. Collations make it engine-dependent too.

    So the comparison is done on ``HEX()`` output instead. Hex is
    collation-independent and byte-exact on both SQLite and MariaDB, which
    makes the clause agree with the Python split character for character; the
    hex alphabet contains no ``%`` or ``_``, so the token needs no escaping at
    all; and two hex strings differing only in digit case denote the same
    bytes, so ``LIKE``'s case-insensitivity cannot conflate anything.

    Spaces are stripped from the stored value first so ``"A, B"`` and ``"A,B"``
    mean the same thing, matching ``_get_clients_from_legacy_field``'s
    ``.strip()``. A blank ``client_id`` matches nothing.

    Portable across SQLite and MariaDB: ``HEX``/``REPLACE``/``COALESCE``/
    ``LIKE`` only. Pinned by test_cross_tenant_authz.py's
    ``test_client_token_clause_*`` tests.

    Args:
        column: comma-separated client column (e.g. ``Employee.client_id_assigned``)
        client_id: the single client id that must appear as a whole token

    Returns:
        SQLAlchemy boolean clause
    """
    wanted = (client_id or "").strip()
    if not wanted:
        # No token to look for. `normalized == ""` would otherwise match every
        # blank assignment, which is exactly the row class that must never be
        # treated as shared (see verify_employee_access).
        return false()

    hex_column = func.hex(func.replace(func.coalesce(column, ""), " ", ""))
    token = wanted.encode().hex().upper()
    return or_(
        hex_column == token,
        hex_column.like(f"{token}{_COMMA_HEX}%"),
        hex_column.like(f"%{_COMMA_HEX}{token}{_COMMA_HEX}%"),
        hex_column.like(f"%{_COMMA_HEX}{token}"),
    )


def build_client_filter_clause(user: User, client_id_column: Any) -> Any:
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
