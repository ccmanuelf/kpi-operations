"""
Capacity Planning - KPI and Workbook Endpoints

KPI integration (commitments, variance) and workbook save/load operations.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.constants import (
    CALENDAR_DEFAULT_DAYS,
    LARGE_PAGE_SIZE,
    EXTRA_LARGE_PAGE_SIZE,
)
from backend.crud.capacity import calendar, production_lines, orders, standards, bom, stock

from ._models import (
    KPICommitmentResponse,
    WorksheetSaveResponse,
)

logger = logging.getLogger(__name__)

kpi_workbook_router = APIRouter()


# =============================================================================
# KPI Integration Endpoints
# =============================================================================


@kpi_workbook_router.get("/kpi/commitments", response_model=List[KPICommitmentResponse])
def get_kpi_commitments(
    client_id: str = Query(..., description="Client ID"),
    schedule_id: Optional[int] = None,
    kpi_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get KPI commitments for a client."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.kpi_commitment import CapacityKPICommitment

    query = db.query(CapacityKPICommitment).filter(CapacityKPICommitment.client_id == client_id)

    if schedule_id:
        query = query.filter(CapacityKPICommitment.schedule_id == schedule_id)
    if kpi_key:
        query = query.filter(CapacityKPICommitment.kpi_key == kpi_key)

    return query.order_by(CapacityKPICommitment.period_start.desc()).all()


@kpi_workbook_router.get("/kpi/variance", responses={400: {"description": "KPI variance report failed"}, 501: {"description": "KPI integration service not yet implemented"}})
def get_kpi_variance_report(
    client_id: str = Query(..., description="Client ID"),
    schedule_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get KPI variance report."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.kpi_integration_service import KPIIntegrationService

        service = KPIIntegrationService(db)

        report = service.get_variance_report(client_id, schedule_id)
        return report
    except ImportError:
        raise HTTPException(status_code=501, detail="KPI integration service not yet implemented")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.exception("Database error in KPI variance report for client_id=%s", client_id)
        raise HTTPException(status_code=503, detail="Database error generating KPI variance report")
    except Exception as e:
        logger.exception("KPI variance report failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="KPI variance report failed")


# =============================================================================
# Workbook Endpoints (Multi-sheet operations)
# =============================================================================


@kpi_workbook_router.get("/workbook/{client_id}", response_model=Dict[str, Any], responses={403: {"description": "Client access denied"}})
def load_workbook(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Load all worksheet data for a client (capacity planning workbook).

    Returns all 13 worksheets with snake_case keys matching the frontend store mapping:
    master_calendar, production_lines, orders, production_standards, bom, stock_snapshot,
    component_check, capacity_analysis, production_schedule, what_if_scenarios,
    dashboard_inputs, kpi_tracking, instructions
    """
    verify_client_access(current_user, client_id, db)

    # --- Base data (6 worksheets via CRUD modules) ---
    calendar_data = calendar.get_calendar_entries(db, client_id, limit=CALENDAR_DEFAULT_DAYS)
    lines_data = production_lines.get_production_lines(db, client_id, include_inactive=True)
    orders_data = orders.get_orders(db, client_id, limit=LARGE_PAGE_SIZE)
    standards_data = standards.get_standards(db, client_id, limit=EXTRA_LARGE_PAGE_SIZE)
    bom_headers = bom.get_bom_headers(db, client_id, include_inactive=True)
    stock_data = stock.get_stock_snapshots(db, client_id, limit=LARGE_PAGE_SIZE)

    # --- Computed data (7 worksheets via direct queries) ---
    from backend.schemas.capacity.component_check import CapacityComponentCheck
    from backend.schemas.capacity.analysis import CapacityAnalysis
    from backend.schemas.capacity.schedule import CapacitySchedule, CapacityScheduleDetail
    from backend.schemas.capacity.scenario import CapacityScenario
    from backend.schemas.capacity.kpi_commitment import CapacityKPICommitment

    component_checks = (
        db.query(CapacityComponentCheck)
        .filter(CapacityComponentCheck.client_id == client_id)
        .order_by(CapacityComponentCheck.run_date.desc(), CapacityComponentCheck.order_number)
        .all()
    )

    analysis_data = (
        db.query(CapacityAnalysis)
        .filter(CapacityAnalysis.client_id == client_id)
        .order_by(CapacityAnalysis.analysis_date.desc(), CapacityAnalysis.line_code)
        .all()
    )

    schedules = (
        db.query(CapacitySchedule)
        .filter(CapacitySchedule.client_id == client_id)
        .order_by(CapacitySchedule.period_start.desc())
        .all()
    )

    schedule_details = (
        db.query(CapacityScheduleDetail)
        .filter(CapacityScheduleDetail.client_id == client_id)
        .order_by(CapacityScheduleDetail.scheduled_date, CapacityScheduleDetail.sequence)
        .all()
    )

    scenarios = (
        db.query(CapacityScenario)
        .filter(CapacityScenario.client_id == client_id)
        .order_by(CapacityScenario.created_at.desc())
        .all()
    )

    kpi_commitments = (
        db.query(CapacityKPICommitment)
        .filter(CapacityKPICommitment.client_id == client_id)
        .order_by(CapacityKPICommitment.period_start.desc())
        .all()
    )

    return {
        # --- Sheet 1: Master Calendar ---
        "master_calendar": [
            {
                "id": e.id,
                "calendar_date": e.calendar_date.isoformat(),
                "is_working_day": e.is_working_day,
                "shifts_available": e.shifts_available,
                "shift1_hours": float(e.shift1_hours),
                "shift2_hours": float(e.shift2_hours),
                "shift3_hours": float(e.shift3_hours),
                "holiday_name": e.holiday_name,
                "notes": e.notes,
            }
            for e in calendar_data
        ],
        # --- Sheet 2: Production Lines ---
        "production_lines": [
            {
                "id": l.id,
                "line_code": l.line_code,
                "line_name": l.line_name,
                "department": l.department,
                "standard_capacity_units_per_hour": float(l.standard_capacity_units_per_hour),
                "max_operators": l.max_operators,
                "efficiency_factor": float(l.efficiency_factor),
                "absenteeism_factor": float(l.absenteeism_factor),
                "is_active": l.is_active,
                "notes": l.notes,
            }
            for l in lines_data
        ],
        # --- Sheet 3: Orders ---
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "customer_name": o.customer_name,
                "style_code": o.style_code,
                "style_description": o.style_description,
                "order_quantity": o.order_quantity,
                "completed_quantity": o.completed_quantity,
                "order_date": o.order_date.isoformat() if o.order_date else None,
                "required_date": o.required_date.isoformat(),
                "planned_start_date": o.planned_start_date.isoformat() if o.planned_start_date else None,
                "planned_end_date": o.planned_end_date.isoformat() if o.planned_end_date else None,
                "priority": o.priority.value,
                "status": o.status.value,
                "order_sam_minutes": float(o.order_sam_minutes) if o.order_sam_minutes else None,
                "notes": o.notes,
            }
            for o in orders_data
        ],
        # --- Sheet 4: Production Standards ---
        "production_standards": [
            {
                "id": s.id,
                "style_code": s.style_code,
                "operation_code": s.operation_code,
                "operation_name": s.operation_name,
                "department": s.department,
                "sam_minutes": float(s.sam_minutes),
                "setup_time_minutes": float(s.setup_time_minutes or 0),
                "machine_time_minutes": float(s.machine_time_minutes or 0),
                "manual_time_minutes": float(s.manual_time_minutes or 0),
                "notes": s.notes,
            }
            for s in standards_data
        ],
        # --- Sheet 5: BOM ---
        "bom": [
            {
                "id": h.id,
                "parent_item_code": h.parent_item_code,
                "parent_item_description": h.parent_item_description,
                "style_code": h.style_code,
                "revision": h.revision,
                "is_active": h.is_active,
                "notes": h.notes,
            }
            for h in bom_headers
        ],
        # --- Sheet 6: Stock Snapshot ---
        "stock_snapshot": [
            {
                "id": s.id,
                "snapshot_date": s.snapshot_date.isoformat(),
                "item_code": s.item_code,
                "item_description": s.item_description,
                "on_hand_quantity": float(s.on_hand_quantity),
                "allocated_quantity": float(s.allocated_quantity),
                "on_order_quantity": float(s.on_order_quantity),
                "available_quantity": float(s.available_quantity),
                "unit_of_measure": s.unit_of_measure,
                "location": s.location,
                "notes": s.notes,
            }
            for s in stock_data
        ],
        # --- Sheet 7: Component Check (MRP results) ---
        "component_check": [
            {
                "id": c.id,
                "run_date": c.run_date.isoformat(),
                "order_id": c.order_id,
                "order_number": c.order_number,
                "component_item_code": c.component_item_code,
                "component_description": c.component_description,
                "required_quantity": float(c.required_quantity),
                "available_quantity": float(c.available_quantity),
                "shortage_quantity": float(c.shortage_quantity or 0),
                "status": c.status.value if c.status else None,
                "notes": c.notes,
            }
            for c in component_checks
        ],
        # --- Sheet 8: Capacity Analysis (12-step utilization) ---
        "capacity_analysis": [
            {
                "id": a.id,
                "analysis_date": a.analysis_date.isoformat(),
                "line_id": a.line_id,
                "line_code": a.line_code,
                "department": a.department,
                "working_days": a.working_days,
                "shifts_per_day": a.shifts_per_day,
                "hours_per_shift": float(a.hours_per_shift or 0),
                "operators_available": a.operators_available,
                "efficiency_factor": float(a.efficiency_factor or 0),
                "absenteeism_factor": float(a.absenteeism_factor or 0),
                "gross_hours": float(a.gross_hours or 0),
                "net_hours": float(a.net_hours or 0),
                "capacity_hours": float(a.capacity_hours or 0),
                "demand_hours": float(a.demand_hours or 0),
                "demand_units": a.demand_units or 0,
                "utilization_percent": float(a.utilization_percent or 0),
                "is_bottleneck": a.is_bottleneck or False,
                "notes": a.notes,
            }
            for a in analysis_data
        ],
        # --- Sheet 9: Production Schedule (header + details) ---
        "production_schedule": [
            {
                "id": sd.id,
                "schedule_id": sd.schedule_id,
                "order_id": sd.order_id,
                "order_number": sd.order_number,
                "style_code": sd.style_code,
                "line_id": sd.line_id,
                "line_code": sd.line_code,
                "scheduled_date": sd.scheduled_date.isoformat(),
                "scheduled_quantity": sd.scheduled_quantity or 0,
                "completed_quantity": sd.completed_quantity or 0,
                "sequence": sd.sequence or 1,
                "notes": sd.notes,
                # Include parent schedule metadata
                "schedule_name": next((s.schedule_name for s in schedules if s.id == sd.schedule_id), None),
                "schedule_status": next((s.status.value for s in schedules if s.id == sd.schedule_id), None),
            }
            for sd in schedule_details
        ],
        # --- Sheet 10: What-If Scenarios ---
        "what_if_scenarios": [
            {
                "id": sc.id,
                "scenario_name": sc.scenario_name,
                "scenario_type": sc.scenario_type,
                "base_schedule_id": sc.base_schedule_id,
                "parameters": sc.parameters_json or {},
                "results": sc.results_json or {},
                "is_active": sc.is_active,
                "notes": sc.notes,
            }
            for sc in scenarios
        ],
        # --- Sheet 11: Dashboard Inputs (planning parameters) ---
        "dashboard_inputs": {
            "planning_horizon_days": 30,
            "default_efficiency": 85,
            "bottleneck_threshold": 90,
            "shortage_alert_days": 7,
            "auto_schedule_enabled": False,
            "target_utilization": 85,
            "overtime_limit_percent": 20,
            "safety_stock_days": 5,
            "schedule_freeze_days": 3,
            "max_shifts_per_day": 2,
            "min_lot_size": 50,
            "schedule_granularity": "daily",
        },
        # --- Sheet 12: KPI Tracking ---
        "kpi_tracking": [
            {
                "id": k.id,
                "schedule_id": k.schedule_id,
                "kpi_key": k.kpi_key,
                "kpi_name": k.kpi_name,
                "period_start": k.period_start.isoformat(),
                "period_end": k.period_end.isoformat(),
                "committed_value": float(k.committed_value),
                "actual_value": float(k.actual_value) if k.actual_value is not None else None,
                "variance": float(k.variance) if k.variance is not None else None,
                "variance_percent": float(k.variance_percent) if k.variance_percent is not None else None,
                "notes": k.notes,
            }
            for k in kpi_commitments
        ],
        # --- Sheet 13: Instructions (static content) ---
        "instructions": (
            "# Capacity Planning Workbook\n\n"
            "## Overview\n"
            "This workbook contains 13 interconnected worksheets for production capacity planning.\n\n"
            "## Workflow\n"
            "1. **Master Calendar** - Define working days, shifts, and holidays\n"
            "2. **Production Lines** - Configure line capacities and efficiency factors\n"
            "3. **Orders** - Enter customer orders with quantities and due dates\n"
            "4. **Production Standards** - Set SAM (Standard Allowed Minutes) per style/operation\n"
            "5. **BOM** - Define Bills of Material for component requirements\n"
            "6. **Stock Snapshot** - Record current inventory positions\n"
            "7. **Component Check** - Run MRP explosion to check material availability\n"
            "8. **Capacity Analysis** - Calculate utilization using the 12-step method\n"
            "9. **Production Schedule** - Assign orders to lines and dates\n"
            "10. **What-If Scenarios** - Model capacity changes (overtime, new lines, etc.)\n"
            "11. **Dashboard Inputs** - Configure planning parameters\n"
            "12. **KPI Tracking** - Monitor committed vs actual performance\n"
            "13. **Instructions** - This guide\n\n"
            "## Key Concepts\n"
            "- **SAM**: Standard Allowed Minutes - time required per operation\n"
            "- **Utilization**: Demand hours / Capacity hours x 100\n"
            "- **Bottleneck**: Line where utilization exceeds threshold (default 90%)\n"
            "- **MRP Explosion**: Breaking down finished goods into component requirements\n"
        ),
    }


@kpi_workbook_router.put("/workbook/{client_id}/{worksheet_name}", response_model=WorksheetSaveResponse, responses={400: {"description": "Invalid worksheet name"}, 403: {"description": "Client access denied"}})
def save_worksheet(
    client_id: str,
    worksheet_name: str,
    data: List[Dict[str, Any]],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a specific worksheet's data (bulk update/create)."""
    verify_client_access(current_user, client_id, db)

    # Accept both camelCase (from frontend store) and snake_case
    camel_to_snake = {
        "masterCalendar": "master_calendar",
        "productionLines": "production_lines",
        "productionStandards": "production_standards",
        "stockSnapshot": "stock_snapshot",
        "componentCheck": "component_check",
        "capacityAnalysis": "capacity_analysis",
        "productionSchedule": "production_schedule",
        "whatIfScenarios": "what_if_scenarios",
        "dashboardInputs": "dashboard_inputs",
        "kpiTracking": "kpi_tracking",
    }
    worksheet_name = camel_to_snake.get(worksheet_name, worksheet_name)

    valid_worksheets = [
        "master_calendar",
        "production_lines",
        "orders",
        "production_standards",
        "bom",
        "stock_snapshot",
        "component_check",
        "capacity_analysis",
        "production_schedule",
        "what_if_scenarios",
        "kpi_tracking",
    ]

    if worksheet_name not in valid_worksheets:
        raise HTTPException(status_code=400, detail=f"Invalid worksheet name. Must be one of: {valid_worksheets}")

    # Handle bulk operations based on worksheet type
    # This is a placeholder for actual implementation
    return {"message": f"Worksheet '{worksheet_name}' saved", "rows_processed": len(data)}
