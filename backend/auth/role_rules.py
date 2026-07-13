"""Role ↔ client-assignment invariants — single source of truth.

Mirrors the role model in backend/orm/user.py:
  admin, poweruser              → access ALL clients; client_id_assigned must be empty.
  leader, supervisor, operator, viewer → client-scoped; require an assignment
                                         (leader may list several, comma-separated).
"""

ALL_CLIENT_ROLES = frozenset({"admin", "poweruser"})
SCOPED_ROLES = frozenset({"leader", "supervisor", "operator", "viewer"})
MULTI_CLIENT_ROLES = frozenset({"leader"})


def validate_role_client_assignment(role: str, client_id_assigned: str | None) -> None:
    """Raise ValueError if the role/client pairing violates the tenant model."""
    if role not in ALL_CLIENT_ROLES and role not in SCOPED_ROLES:
        raise ValueError(f"unknown role '{role}'")
    assigned = bool(client_id_assigned and str(client_id_assigned).strip())
    if role in ALL_CLIENT_ROLES and assigned:
        raise ValueError(f"role '{role}' accesses all clients and must not be assigned a client")
    if role in SCOPED_ROLES and not assigned:
        raise ValueError(f"role '{role}' is client-scoped and requires at least one assigned client")
    if role in SCOPED_ROLES and role not in MULTI_CLIENT_ROLES and "," in str(client_id_assigned or ""):
        raise ValueError(f"role '{role}' accepts a single client, not a list")
