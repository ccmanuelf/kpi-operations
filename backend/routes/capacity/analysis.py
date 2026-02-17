"""
Capacity Planning - Analysis and Schedule Endpoints

Component check (MRP), capacity analysis, and production schedule operations.
"""

import logging
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
from backend.schemas.capacity.component_check import ComponentStatus

from ._models import (
    ComponentCheckRequest,
    ComponentCheckResult,
    AnalysisRequest,
    AnalysisResult,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleCommitRequest,
    MessageResponse,
)

logger = logging.getLogger(__name__)

analysis_router = APIRouter()


# =============================================================================
# Component Check (MRP) Endpoints
# =============================================================================


@analysis_router.post("/component-check/run", response_model=List[ComponentCheckResult], responses={400: {"description": "Must provide order_ids or date range, or component check failed"}, 501: {"description": "MRP service not yet implemented"}})
def run_component_check(
    request: ComponentCheckRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run component availability check (MRP explosion).

    Either provide specific order_ids or a date range to check all confirmed orders.
    """
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.mrp_service import MRPService

        service = MRPService(db)

        if request.order_ids:
            results = service.check_components_for_orders(client_id, request.order_ids)
        elif request.start_date and request.end_date:
            results = service.check_components_for_period(client_id, request.start_date, request.end_date)
        else:
            raise HTTPException(status_code=400, detail="Must provide either order_ids or both start_date and end_date")

        return [
            {
                "order_id": r.order_id,
                "order_number": r.order_number,
                "component_item_code": r.component_item_code,
                "component_description": r.component_description,
                "required_quantity": float(r.required_quantity),
                "available_quantity": float(r.available_quantity),
                "shortage_quantity": float(r.shortage_quantity),
                "status": r.status.value,
                "coverage_percent": r.coverage_percent(),
            }
            for r in results
        ]
    except ImportError:
        raise HTTPException(status_code=501, detail="MRP service not yet implemented")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Database error in component check for client_id=%s", client_id)
        raise HTTPException(status_code=503, detail="Database error during component check")
    except Exception as e:
        db.rollback()
        logger.exception("Component check failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="Component check failed")


@analysis_router.get("/component-check/shortages", response_model=List[ComponentCheckResult])
def get_component_shortages(
    client_id: str = Query(..., description="Client ID"),
    run_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get component shortages from the most recent check run."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.component_check import CapacityComponentCheck, ComponentStatus

    query = db.query(CapacityComponentCheck).filter(
        CapacityComponentCheck.client_id == client_id, CapacityComponentCheck.status != ComponentStatus.OK
    )

    if run_date:
        query = query.filter(CapacityComponentCheck.run_date == run_date)

    results = query.order_by(CapacityComponentCheck.shortage_quantity.desc()).all()

    return [
        {
            "order_id": r.order_id,
            "order_number": r.order_number,
            "component_item_code": r.component_item_code,
            "component_description": r.component_description,
            "required_quantity": float(r.required_quantity),
            "available_quantity": float(r.available_quantity),
            "shortage_quantity": float(r.shortage_quantity),
            "status": r.status.value,
            "coverage_percent": r.coverage_percent(),
        }
        for r in results
    ]


# =============================================================================
# Capacity Analysis Endpoints
# =============================================================================


@analysis_router.post("/analysis/calculate", response_model=List[AnalysisResult], responses={400: {"description": "Capacity analysis failed"}, 501: {"description": "Capacity analysis service not yet implemented"}})
def run_capacity_analysis(
    request: AnalysisRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run capacity analysis for lines within a date range."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.analysis_service import CapacityAnalysisService

        service = CapacityAnalysisService(db)

        results = service.analyze_capacity(
            client_id, request.start_date, request.end_date, request.line_ids, request.department
        )

        return [
            {
                "line_id": r.line_id,
                "line_code": r.line_code,
                "department": r.department,
                "analysis_date": r.analysis_date,
                "working_days": r.working_days,
                "gross_hours": float(r.gross_hours),
                "capacity_hours": float(r.capacity_hours),
                "demand_hours": float(r.demand_hours),
                "utilization_percent": float(r.utilization_percent),
                "is_bottleneck": r.is_bottleneck,
            }
            for r in results
        ]
    except ImportError:
        raise HTTPException(status_code=501, detail="Capacity analysis service not yet implemented")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Database error in capacity analysis for client_id=%s", client_id)
        raise HTTPException(status_code=503, detail="Database error during capacity analysis")
    except Exception as e:
        db.rollback()
        logger.exception("Capacity analysis failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="Capacity analysis failed")


@analysis_router.get("/analysis/bottlenecks", response_model=List[AnalysisResult])
def get_bottleneck_lines(
    client_id: str = Query(..., description="Client ID"),
    analysis_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get lines identified as bottlenecks."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.analysis import CapacityAnalysis

    query = db.query(CapacityAnalysis).filter(
        CapacityAnalysis.client_id == client_id, CapacityAnalysis.is_bottleneck == True
    )

    if analysis_date:
        query = query.filter(CapacityAnalysis.analysis_date == analysis_date)

    results = query.order_by(CapacityAnalysis.utilization_percent.desc()).all()

    return [
        {
            "line_id": r.line_id,
            "line_code": r.line_code,
            "department": r.department,
            "analysis_date": r.analysis_date,
            "working_days": r.working_days,
            "gross_hours": float(r.gross_hours or 0),
            "capacity_hours": float(r.capacity_hours or 0),
            "demand_hours": float(r.demand_hours or 0),
            "utilization_percent": float(r.utilization_percent or 0),
            "is_bottleneck": r.is_bottleneck,
        }
        for r in results
    ]


# =============================================================================
# Schedule Endpoints
# =============================================================================


@analysis_router.get("/schedules", response_model=List[ScheduleResponse])
def list_schedules(
    client_id: str = Query(..., description="Client ID"),
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get schedules for a client."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule

    query = db.query(CapacitySchedule).filter(CapacitySchedule.client_id == client_id)

    if status_filter:
        query = query.filter(CapacitySchedule.status == status_filter)

    return query.order_by(CapacitySchedule.period_start.desc()).offset(skip).limit(limit).all()


@analysis_router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    schedule: ScheduleCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new schedule."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule, ScheduleStatus

    new_schedule = CapacitySchedule(
        client_id=client_id,
        schedule_name=schedule.schedule_name,
        period_start=schedule.period_start,
        period_end=schedule.period_end,
        status=ScheduleStatus.DRAFT,
        notes=schedule.notes,
    )
    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)
    return new_schedule


@analysis_router.get("/schedules/{schedule_id}", response_model=ScheduleResponse, responses={404: {"description": "Schedule not found"}})
def get_schedule(
    schedule_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific schedule."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule

    schedule = (
        db.query(CapacitySchedule)
        .filter(CapacitySchedule.client_id == client_id, CapacitySchedule.id == schedule_id)
        .first()
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@analysis_router.post("/schedules/generate", response_model=ScheduleResponse, responses={400: {"description": "Schedule generation failed"}, 501: {"description": "Scheduling service not yet implemented"}})
def generate_schedule(
    schedule_name: str,
    start_date: date = Query(..., description="Schedule period start"),
    end_date: date = Query(..., description="Schedule period end"),
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-generate a schedule from confirmed orders."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.scheduling_service import SchedulingService

        service = SchedulingService(db)

        schedule = service.generate_schedule(client_id, schedule_name, start_date, end_date)
        return schedule
    except ImportError:
        raise HTTPException(status_code=501, detail="Scheduling service not yet implemented")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Database error in schedule generation for client_id=%s", client_id)
        raise HTTPException(status_code=503, detail="Database error during schedule generation")
    except Exception as e:
        db.rollback()
        logger.exception("Schedule generation failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="Schedule generation failed")


@analysis_router.post("/schedules/{schedule_id}/commit", response_model=ScheduleResponse, responses={404: {"description": "Schedule not found"}, 400: {"description": "Only draft schedules can be committed"}})
def commit_schedule(
    schedule_id: int,
    request: ScheduleCommitRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit a schedule, locking KPI targets."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule, ScheduleStatus
    from datetime import date as date_type

    schedule = (
        db.query(CapacitySchedule)
        .filter(CapacitySchedule.client_id == client_id, CapacitySchedule.id == schedule_id)
        .first()
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if schedule.status != ScheduleStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft schedules can be committed")

    schedule.status = ScheduleStatus.COMMITTED
    schedule.committed_at = date_type.today()
    schedule.committed_by = current_user.user_id
    schedule.kpi_commitments_json = request.kpi_commitments

    db.commit()
    db.refresh(schedule)
    return schedule
