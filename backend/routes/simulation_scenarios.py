"""
Simulation V2 / MiniZinc scenario persistence routes (D3).

Routes:
  GET    /api/v2/simulation/scenarios            list (tenant-scoped)
  GET    /api/v2/simulation/scenarios/{id}       fetch one
  POST   /api/v2/simulation/scenarios            create
  PUT    /api/v2/simulation/scenarios/{id}       update
  DELETE /api/v2/simulation/scenarios/{id}       soft delete
  POST   /api/v2/simulation/scenarios/{id}/run   run + persist summary
  POST   /api/v2/simulation/scenarios/{id}/duplicate

Permissions match the rest of `/api/v2/simulation/*`:
  - Read (GET): any authenticated user, scoped to allowed clients.
  - Mutate (POST/PUT/DELETE/run/duplicate): leader / supervisor /
    poweruser / admin (operators are data collectors, not planners).
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.crud import simulation_scenario as crud
from backend.database import get_db
from backend.orm.user import User
from backend.schemas.simulation_scenario import (
    SimulationScenarioCreate,
    SimulationScenarioResponse,
    SimulationScenarioSummary,
    SimulationScenarioUpdate,
)
from backend.simulation_v2.calculations import calculate_all_blocks
from backend.simulation_v2.engine import run_simulation
from backend.simulation_v2.models import SimulationConfig
from backend.simulation_v2.validation import validate_simulation_config
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(
    prefix="/api/v2/simulation/scenarios",
    tags=["simulation-v2-scenarios"],
)


_WRITE_ROLES = {"admin", "ADMIN", "poweruser", "leader", "supervisor"}


def _check_write_permission(user: User) -> None:
    """Reject operator/viewer roles from creating, editing, deleting,
    running, or duplicating scenarios.

    Run-6 audit pattern: operators are data-entry users; planners (and
    above) are scenario authors. This guard mirrors the work_orders
    write gate.
    """
    if (user.role or "") not in _WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Scenario mutations require leader, supervisor, "
                "poweruser, or admin role"
            ),
        )


# =============================================================================
# Read
# =============================================================================


@router.get("", response_model=List[SimulationScenarioSummary])
def list_scenarios_endpoint(
    include_inactive: bool = Query(False, description="Include soft-deleted scenarios"),
    client_id: Optional[str] = Query(None, description="Filter by exact client_id"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List scenarios visible to the user. Returns the lightweight
    summary shape (config_json omitted) to keep the response fast.
    Use /scenarios/{id} for the full payload."""
    return crud.list_scenarios(
        db,
        current_user,
        include_inactive=include_inactive,
        client_id=client_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{scenario_id}", response_model=SimulationScenarioResponse)
def get_scenario_endpoint(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Fetch one scenario with its full config_json + last_run_summary."""
    scenario = crud.get_scenario(db, current_user, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return scenario


# =============================================================================
# Mutate
# =============================================================================


@router.post("", response_model=SimulationScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario_endpoint(
    payload: SimulationScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Save a new scenario. The body's config_json is stored verbatim;
    no engine validation runs on save (validate when actually running)."""
    _check_write_permission(current_user)
    scenario = crud.create_scenario(db, current_user, payload.model_dump())
    db.commit()
    db.refresh(scenario)
    logger.info(
        "Scenario created: id=%d client=%s name=%r by=%s",
        scenario.id,
        scenario.client_id,
        scenario.name,
        current_user.username,
    )
    return scenario


@router.put("/{scenario_id}", response_model=SimulationScenarioResponse)
def update_scenario_endpoint(
    scenario_id: int,
    payload: SimulationScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _check_write_permission(current_user)
    scenario = crud.update_scenario(
        db, current_user, scenario_id, payload.model_dump(exclude_unset=True)
    )
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario_endpoint(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _check_write_permission(current_user)
    ok = crud.delete_scenario(db, current_user, scenario_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    db.commit()


@router.post("/{scenario_id}/duplicate", response_model=SimulationScenarioResponse, status_code=status.HTTP_201_CREATED)
def duplicate_scenario_endpoint(
    scenario_id: int,
    new_name: Optional[str] = Query(None, max_length=150),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _check_write_permission(current_user)
    dup = crud.duplicate_scenario(db, current_user, scenario_id, new_name)
    if dup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    db.commit()
    db.refresh(dup)
    return dup


# =============================================================================
# Run + persist summary
# =============================================================================


@router.post("/{scenario_id}/run", response_model=SimulationScenarioResponse)
def run_scenario_endpoint(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Run the scenario through the SimPy engine and persist a result
    summary. The summary (NOT the full result blocks) is stored on the
    scenario so the list view can show headline metrics without
    re-running.

    Returns 422 if the persisted config fails validation (the user
    saved an invalid config or the schema evolved underneath it).
    """
    _check_write_permission(current_user)
    scenario = crud.get_scenario(db, current_user, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    # Materialize SimulationConfig from the JSON blob. If the blob is
    # incompatible with the current Pydantic model (e.g. engine
    # upgraded since the scenario was saved), Pydantic raises
    # ValidationError → return 422 with a helpful message.
    try:
        config = SimulationConfig.model_validate(scenario.config_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Scenario config is incompatible with the current engine "
                f"schema: {exc}. The scenario may have been saved with an "
                "older engine version. Re-save from the simulation UI."
            ),
        ) from exc

    validation_report = validate_simulation_config(config)
    if validation_report.has_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Scenario configuration validation failed",
                "errors": [e.model_dump() for e in validation_report.errors],
            },
        )

    metrics, duration = run_simulation(config)
    results = calculate_all_blocks(
        config=config,
        metrics=metrics,
        validation_report=validation_report,
        duration_seconds=duration,
        defaults_applied=[],
    )

    # Persist a flat summary — just the headline metrics a planner
    # would scan in a list view. Avoid storing the full 8 result blocks
    # (too heavy; users can re-run if they need the detail).
    summary = {
        "daily_throughput_pcs": getattr(results.daily_summary, "daily_throughput_pcs", None),
        "daily_demand_pcs": getattr(results.daily_summary, "daily_demand_pcs", None),
        "daily_coverage_pct": getattr(results.daily_summary, "daily_coverage_pct", None),
        "avg_cycle_time_min": getattr(results.daily_summary, "avg_cycle_time_min", None),
        "avg_wip_pcs": getattr(results.daily_summary, "avg_wip_pcs", None),
        "duration_seconds": duration,
    }

    crud.record_run(db, current_user, scenario_id, summary)
    db.commit()
    db.refresh(scenario)
    logger.info(
        "Scenario run: id=%d throughput=%s coverage=%s%% by=%s",
        scenario_id,
        summary["daily_throughput_pcs"],
        summary["daily_coverage_pct"],
        current_user.username,
    )
    return scenario
