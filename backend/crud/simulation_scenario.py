"""
CRUD service for SimulationScenario.

All mutating operations enforce tenant isolation: a non-admin user can
only act on scenarios where `client_id` matches one of their assigned
clients (handled via `_resolve_allowed_clients`). Admin / poweruser
have unrestricted access.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.orm.simulation_scenario import SimulationScenario
from backend.orm.user import User


def _resolve_allowed_clients(user: User) -> Optional[Set[str]]:
    """Return the set of client_ids this user can see/modify, or None
    if the user is unrestricted (admin / poweruser).

    `user.client_id_assigned` is comma-separated for multi-client roles
    (leader, supervisor) or a single value (operator). Empty / NULL =
    no client scope (the user is admin-tier).
    """
    role = (user.role or "").lower()
    if role in {"admin", "poweruser"}:
        return None
    raw = user.client_id_assigned or ""
    if not raw:
        return set()  # no clients → no access (defensive)
    return {c.strip() for c in raw.split(",") if c.strip()}


def _scope_filter(query, user: User):
    """Apply the tenant scope filter to a query. NULL client_id (global
    templates) is visible to everyone — they are intentional shared
    baselines."""
    allowed = _resolve_allowed_clients(user)
    if allowed is None:
        return query  # admin / poweruser
    return query.filter(
        or_(
            SimulationScenario.client_id.is_(None),  # global template
            SimulationScenario.client_id.in_(allowed) if allowed else SimulationScenario.client_id.is_(None),
        )
    )


def list_scenarios(
    db: Session,
    user: User,
    *,
    include_inactive: bool = False,
    client_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[SimulationScenario]:
    """List scenarios visible to the user.

    Filters:
      - tenant scope (always)
      - is_active (default True; pass include_inactive=True for soft-deleted)
      - client_id (optional explicit filter — useful when admin wants to
        narrow to one tenant)
    """
    q = db.query(SimulationScenario)
    q = _scope_filter(q, user)
    if not include_inactive:
        q = q.filter(SimulationScenario.is_active.is_(True))
    if client_id is not None:
        q = q.filter(SimulationScenario.client_id == client_id)
    return (
        q.order_by(SimulationScenario.updated_at.desc().nullslast(), SimulationScenario.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_scenario(db: Session, user: User, scenario_id: int) -> Optional[SimulationScenario]:
    """Fetch one scenario the user is allowed to see (or None)."""
    q = db.query(SimulationScenario).filter(SimulationScenario.id == scenario_id)
    q = _scope_filter(q, user)
    return q.first()


def create_scenario(db: Session, user: User, payload: Dict[str, Any]) -> SimulationScenario:
    """Create a scenario. Tenant scope enforced: non-admin users can
    only create scenarios for their assigned clients (or global=NULL
    if they're admin/poweruser).
    """
    target_client = payload.get("client_id")
    allowed = _resolve_allowed_clients(user)
    if allowed is not None:
        # Non-admin user. Cannot create global (NULL) and must target an
        # allowed client.
        if target_client is None:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin/poweruser can create global (client-less) scenarios",
            )
        if target_client not in allowed:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have access to client {target_client}",
            )

    scenario = SimulationScenario(
        client_id=target_client,
        name=payload["name"],
        description=payload.get("description"),
        config_json=payload["config_json"],
        tags=payload.get("tags"),
        is_active=True,
        created_by=user.user_id,
        updated_by=user.user_id,
    )
    db.add(scenario)
    db.flush()  # populate scenario.id
    return scenario


def update_scenario(db: Session, user: User, scenario_id: int, payload: Dict[str, Any]) -> Optional[SimulationScenario]:
    """Partial update. Returns None if not found / not allowed."""
    scenario = get_scenario(db, user, scenario_id)
    if scenario is None:
        return None
    for field in ("name", "description", "config_json", "tags", "is_active"):
        if field in payload and payload[field] is not None:
            setattr(scenario, field, payload[field])
    # Allow explicit setting is_active=False even via "soft delete" path
    if "is_active" in payload and payload["is_active"] is not None:
        scenario.is_active = bool(payload["is_active"])
    scenario.updated_by = user.user_id
    db.flush()
    return scenario


def delete_scenario(db: Session, user: User, scenario_id: int) -> bool:
    """Soft delete (sets is_active=False). Returns True if the scenario
    was found and marked deleted; False if not found or not allowed."""
    scenario = get_scenario(db, user, scenario_id)
    if scenario is None:
        return False
    scenario.is_active = False
    scenario.updated_by = user.user_id
    db.flush()
    return True


def duplicate_scenario(
    db: Session, user: User, scenario_id: int, new_name: Optional[str] = None
) -> Optional[SimulationScenario]:
    """Clone a scenario. The duplicate inherits client_id (so tenant
    scope stays intact) but resets last_run_summary and timestamps."""
    src = get_scenario(db, user, scenario_id)
    if src is None:
        return None
    dup = SimulationScenario(
        client_id=src.client_id,
        name=new_name or f"{src.name} (copy)",
        description=src.description,
        config_json=src.config_json,
        tags=src.tags,
        is_active=True,
        created_by=user.user_id,
        updated_by=user.user_id,
    )
    db.add(dup)
    db.flush()
    return dup


def record_run(
    db: Session,
    user: User,
    scenario_id: int,
    summary: Dict[str, Any],
) -> Optional[SimulationScenario]:
    """Persist a result summary on the scenario. Called by the
    POST /scenarios/{id}/run route after the engine completes.
    """
    scenario = get_scenario(db, user, scenario_id)
    if scenario is None:
        return None
    scenario.last_run_summary = summary
    scenario.last_run_at = datetime.now(tz=timezone.utc)
    scenario.updated_by = user.user_id
    db.flush()
    return scenario
