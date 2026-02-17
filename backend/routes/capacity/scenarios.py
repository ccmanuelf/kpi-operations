"""
Capacity Planning - Scenario Endpoints

What-if scenario CRUD, run/evaluate, compare, and delete operations.
"""

from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.constants import DEFAULT_PAGE_SIZE

from ._models import (
    ScenarioCreate,
    ScenarioResponse,
    ScenarioRunRequest,
    ScenarioRunResponse,
    ScenarioCompareRequest,
    MessageResponse,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

scenarios_router = APIRouter()


@scenarios_router.get("/scenarios", response_model=List[ScenarioResponse])
def list_scenarios(
    client_id: str = Query(..., description="Client ID"),
    scenario_type: Optional[str] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get scenarios for a client."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    query = db.query(CapacityScenario).filter(CapacityScenario.client_id == client_id)

    if scenario_type:
        query = query.filter(CapacityScenario.scenario_type == scenario_type)

    return query.order_by(CapacityScenario.created_at.desc()).offset(skip).limit(limit).all()


@scenarios_router.post("/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    scenario: ScenarioCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new scenario."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    new_scenario = CapacityScenario(
        client_id=client_id,
        scenario_name=scenario.scenario_name,
        scenario_type=scenario.scenario_type,
        base_schedule_id=scenario.base_schedule_id,
        parameters_json=scenario.parameters,
        is_active=True,
        notes=scenario.notes,
    )
    db.add(new_scenario)
    db.commit()
    db.refresh(new_scenario)
    return new_scenario


@scenarios_router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse, responses={404: {"description": "Scenario not found"}})
def get_scenario(
    scenario_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific scenario."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    scenario = (
        db.query(CapacityScenario)
        .filter(CapacityScenario.client_id == client_id, CapacityScenario.id == scenario_id)
        .first()
    )

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@scenarios_router.post("/scenarios/{scenario_id}/run", response_model=ScenarioRunResponse, responses={404: {"description": "Scenario not found"}, 400: {"description": "Scenario evaluation failed"}, 501: {"description": "Scenario service not yet implemented"}})
def run_scenario(
    scenario_id: int,
    request: ScenarioRunRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run/evaluate a scenario by applying its parameters and analyzing impact."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    scenario = (
        db.query(CapacityScenario)
        .filter(CapacityScenario.client_id == client_id, CapacityScenario.id == scenario_id)
        .first()
    )

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    try:
        from backend.services.capacity.scenario_service import ScenarioService

        service = ScenarioService(db)

        # Use provided dates or derive from base schedule or default to 30-day window
        period_start = request.period_start
        period_end = request.period_end

        if not period_start or not period_end:
            if scenario.base_schedule_id:
                from backend.schemas.capacity.schedule import CapacitySchedule

                base_schedule = (
                    db.query(CapacitySchedule).filter(CapacitySchedule.id == scenario.base_schedule_id).first()
                )
                if base_schedule:
                    period_start = period_start or base_schedule.period_start
                    period_end = period_end or base_schedule.period_end

            if not period_start:
                from datetime import timedelta

                period_start = date.today()
            if not period_end:
                from datetime import timedelta

                period_end = period_start + timedelta(days=30)

        result = service.apply_scenario_parameters(client_id, scenario_id, period_start, period_end)

        return {
            "scenario_id": result.scenario_id,
            "scenario_name": result.scenario_name,
            "original_metrics": result.original_metrics,
            "modified_metrics": result.modified_metrics,
            "impact_summary": result.impact_summary,
        }
    except ImportError:
        raise HTTPException(status_code=501, detail="Scenario service not yet implemented")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Database error in scenario run for scenario_id=%s", scenario_id)
        raise HTTPException(status_code=503, detail="Database error during scenario evaluation")
    except Exception as e:
        db.rollback()
        logger.exception("Scenario run failed for scenario_id=%s", scenario_id)
        raise HTTPException(status_code=400, detail="Scenario run failed")


@scenarios_router.delete("/scenarios/{scenario_id}", response_model=MessageResponse, responses={404: {"description": "Scenario not found"}})
def delete_scenario(
    scenario_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a scenario."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    scenario = (
        db.query(CapacityScenario)
        .filter(CapacityScenario.client_id == client_id, CapacityScenario.id == scenario_id)
        .first()
    )

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    db.delete(scenario)
    db.commit()
    return {"message": "Scenario deleted"}


@scenarios_router.post("/scenarios/compare", responses={400: {"description": "Scenario comparison failed"}, 501: {"description": "Scenario service not yet implemented"}})
def compare_scenarios(
    request: ScenarioCompareRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare multiple scenarios."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.scenario_service import ScenarioService

        service = ScenarioService(db)

        comparison = service.compare_scenarios(client_id, request.scenario_ids)
        return comparison
    except ImportError:
        raise HTTPException(status_code=501, detail="Scenario service not yet implemented")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.exception("Database error in scenario comparison for client_id=%s", client_id)
        raise HTTPException(status_code=503, detail="Database error during scenario comparison")
    except Exception as e:
        logger.exception("Scenario comparison failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="Scenario comparison failed")
