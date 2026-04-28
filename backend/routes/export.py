"""
Data Export Routes - Per-Entity CSV Export Endpoints

Provides CSV download endpoints for all major entities in the system.
Each endpoint streams CSV data with proper Content-Disposition headers
for browser download. Column names match the CSV upload format for
round-trip compatibility.
"""

from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.orm.user import User
from backend.middleware.client_auth import build_client_filter_clause
from backend.services.csv_export_service import stream_csv_export
from backend.utils.logging_utils import get_module_logger

# ORM models (in schemas/ per project convention)
from backend.orm.production_entry import ProductionEntry
from backend.orm.work_order import WorkOrder
from backend.orm.quality_entry import QualityEntry
from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.employee import Employee
from backend.orm.product import Product
from backend.orm.shift import Shift
from backend.orm.hold_entry import HoldEntry

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/export", tags=["Data Export"])


def _build_csv_response(
    db: Session,
    current_user: User,
    model_class,
    columns,
    entity_name: str,
    client_id: Optional[str],
    date_field=None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    line_id: Optional[int] = None,
) -> StreamingResponse:
    """
    Build a StreamingResponse for CSV export of any entity.

    Args:
        db: Database session.
        current_user: Authenticated user.
        model_class: ORM model class.
        columns: List of (attribute_name, csv_header) tuples.
        entity_name: Name for the downloaded file.
        client_id: Optional client_id filter override.
        date_field: Optional SQLAlchemy column for date range filtering.
        start_date: Optional start date for range filter.
        end_date: Optional end date for range filter.
        line_id: Optional line_id filter.

    Returns:
        StreamingResponse with CSV content.
    """
    # Build client isolation filter
    if client_id:
        # If explicit client_id is provided, filter to just that client
        client_filter = model_class.client_id == client_id
    else:
        client_filter = build_client_filter_clause(current_user, model_class.client_id)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    filename = f"{entity_name}_{timestamp}.csv"

    logger.info(
        "CSV export requested: entity=%s, client_id=%s, start_date=%s, end_date=%s, line_id=%s, user=%s",
        entity_name,
        client_id,
        start_date,
        end_date,
        line_id,
        current_user.username,
    )

    generator = stream_csv_export(
        db=db,
        model_class=model_class,
        client_filter=client_filter,
        columns=columns,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date,
        line_id=line_id,
    )

    return StreamingResponse(
        generator,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =============================================================================
# Production Entries Export
# =============================================================================

PRODUCTION_ENTRY_COLUMNS = [
    ("production_entry_id", "production_entry_id"),
    ("client_id", "client_id"),
    ("line_id", "line_id"),
    ("product_id", "product_id"),
    ("shift_id", "shift_id"),
    ("work_order_id", "work_order_id"),
    ("job_id", "job_id"),
    ("production_date", "production_date"),
    ("shift_date", "shift_date"),
    ("units_produced", "units_produced"),
    ("run_time_hours", "run_time_hours"),
    ("employees_assigned", "employees_assigned"),
    ("employees_present", "employees_present"),
    ("defect_count", "defect_count"),
    ("scrap_count", "scrap_count"),
    ("rework_count", "rework_count"),
    ("setup_time_hours", "setup_time_hours"),
    ("downtime_hours", "downtime_hours"),
    ("maintenance_hours", "maintenance_hours"),
    ("ideal_cycle_time", "ideal_cycle_time"),
    ("actual_cycle_time", "actual_cycle_time"),
    ("efficiency_percentage", "efficiency_percentage"),
    ("performance_percentage", "performance_percentage"),
    ("quality_rate", "quality_rate"),
    ("notes", "notes"),
    ("entry_method", "entry_method"),
]


@router.get("/production-entries")
async def export_production_entries(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    line_id: Optional[int] = Query(None, description="Filter by production line ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export production entries as CSV."""
    return _build_csv_response(
        db=db,
        current_user=current_user,
        model_class=ProductionEntry,
        columns=PRODUCTION_ENTRY_COLUMNS,
        entity_name="production_entries",
        client_id=client_id,
        date_field=ProductionEntry.shift_date,
        start_date=start_date,
        end_date=end_date,
        line_id=line_id,
    )


# =============================================================================
# Work Orders Export
# =============================================================================

WORK_ORDER_COLUMNS = [
    ("work_order_id", "work_order_id"),
    ("client_id", "client_id"),
    ("style_model", "style_model"),
    ("planned_quantity", "planned_quantity"),
    ("actual_quantity", "actual_quantity"),
    ("status", "status"),
    ("priority", "priority"),
    ("planned_start_date", "planned_start_date"),
    ("actual_start_date", "actual_start_date"),
    ("planned_ship_date", "planned_ship_date"),
    ("required_date", "required_date"),
    ("actual_delivery_date", "actual_delivery_date"),
    ("received_date", "received_date"),
    ("ideal_cycle_time", "ideal_cycle_time"),
    ("calculated_cycle_time", "calculated_cycle_time"),
    ("customer_po_number", "customer_po_number"),
    ("notes", "notes"),
    ("internal_notes", "internal_notes"),
]


@router.get("/work-orders")
async def export_work_orders(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export work orders as CSV."""
    return _build_csv_response(
        db=db,
        current_user=current_user,
        model_class=WorkOrder,
        columns=WORK_ORDER_COLUMNS,
        entity_name="work_orders",
        client_id=client_id,
        date_field=WorkOrder.planned_start_date,
        start_date=start_date,
        end_date=end_date,
    )


# =============================================================================
# Quality Inspections Export
# =============================================================================

QUALITY_ENTRY_COLUMNS = [
    ("quality_entry_id", "quality_entry_id"),
    ("client_id", "client_id"),
    ("work_order_id", "work_order_id"),
    ("job_id", "job_id"),
    ("shift_date", "shift_date"),
    ("inspection_date", "inspection_date"),
    ("units_inspected", "units_inspected"),
    ("units_passed", "units_passed"),
    ("units_defective", "units_defective"),
    ("total_defects_count", "total_defects_count"),
    ("inspection_stage", "inspection_stage"),
    ("process_step", "process_step"),
    ("operation_checked", "operation_checked"),
    ("is_first_pass", "is_first_pass"),
    ("units_scrapped", "units_scrapped"),
    ("units_reworked", "units_reworked"),
    ("units_requiring_repair", "units_requiring_repair"),
    ("inspection_method", "inspection_method"),
    ("notes", "notes"),
]


@router.get("/quality-inspections")
async def export_quality_inspections(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export quality inspection entries as CSV."""
    return _build_csv_response(
        db=db,
        current_user=current_user,
        model_class=QualityEntry,
        columns=QUALITY_ENTRY_COLUMNS,
        entity_name="quality_inspections",
        client_id=client_id,
        date_field=QualityEntry.shift_date,
        start_date=start_date,
        end_date=end_date,
    )


# =============================================================================
# Downtime Events Export
# =============================================================================

DOWNTIME_ENTRY_COLUMNS = [
    ("downtime_entry_id", "downtime_entry_id"),
    ("client_id", "client_id"),
    ("line_id", "line_id"),
    ("work_order_id", "work_order_id"),
    ("shift_date", "shift_date"),
    ("downtime_reason", "downtime_reason"),
    ("downtime_duration_minutes", "downtime_duration_minutes"),
    ("machine_id", "machine_id"),
    ("equipment_code", "equipment_code"),
    ("root_cause_category", "root_cause_category"),
    ("corrective_action", "corrective_action"),
    ("notes", "notes"),
]


@router.get("/downtime-events")
async def export_downtime_events(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    line_id: Optional[int] = Query(None, description="Filter by production line ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export downtime events as CSV."""
    return _build_csv_response(
        db=db,
        current_user=current_user,
        model_class=DowntimeEntry,
        columns=DOWNTIME_ENTRY_COLUMNS,
        entity_name="downtime_events",
        client_id=client_id,
        date_field=DowntimeEntry.shift_date,
        start_date=start_date,
        end_date=end_date,
        line_id=line_id,
    )


# =============================================================================
# Attendance Export
# =============================================================================

ATTENDANCE_ENTRY_COLUMNS = [
    ("attendance_entry_id", "attendance_entry_id"),
    ("client_id", "client_id"),
    ("line_id", "line_id"),
    ("employee_id", "employee_id"),
    ("shift_date", "shift_date"),
    ("shift_id", "shift_id"),
    ("scheduled_hours", "scheduled_hours"),
    ("actual_hours", "actual_hours"),
    ("absence_hours", "absence_hours"),
    ("is_absent", "is_absent"),
    ("absence_type", "absence_type"),
    ("covered_by_employee_id", "covered_by_employee_id"),
    ("coverage_confirmed", "coverage_confirmed"),
    ("is_late", "is_late"),
    ("is_early_departure", "is_early_departure"),
    ("absence_reason", "absence_reason"),
    ("notes", "notes"),
]


@router.get("/attendance")
async def export_attendance(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    line_id: Optional[int] = Query(None, description="Filter by production line ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export attendance entries as CSV."""
    return _build_csv_response(
        db=db,
        current_user=current_user,
        model_class=AttendanceEntry,
        columns=ATTENDANCE_ENTRY_COLUMNS,
        entity_name="attendance",
        client_id=client_id,
        date_field=AttendanceEntry.shift_date,
        start_date=start_date,
        end_date=end_date,
        line_id=line_id,
    )


# =============================================================================
# Employees Export
# =============================================================================

EMPLOYEE_COLUMNS = [
    ("employee_id", "employee_id"),
    ("employee_code", "employee_code"),
    ("employee_name", "employee_name"),
    ("client_id_assigned", "client_id_assigned"),
    ("is_floating_pool", "is_floating_pool"),
    ("is_active", "is_active"),
    ("department", "department"),
    ("position", "position"),
    ("contact_phone", "contact_phone"),
    ("contact_email", "contact_email"),
    ("hire_date", "hire_date"),
]


@router.get("/employees")
async def export_employees(
    client_id: Optional[str] = Query(None, description="Filter by client ID (matches client_id_assigned)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export employees as CSV.

    Note: Employee uses client_id_assigned (comma-separated), not client_id.
    When client_id is provided, filters for employees assigned to that client
    using LIKE matching on client_id_assigned.
    """
    # Employees use client_id_assigned (comma-separated), not client_id.
    # Build a custom filter for this entity. Annotated as Optional[Any]
    # because the branches mix BinaryExpression (LIKE), or_(...) ColumnElement,
    # and None — let mypy treat it as a SQLAlchemy clause without trying
    # to unify the variants.
    client_filter: Any = None
    if client_id:
        client_filter = Employee.client_id_assigned.like(f"%{client_id}%")
    else:
        # For non-admin users, we still need to filter based on their assigned clients
        from backend.middleware.client_auth import get_user_client_filter

        user_clients = get_user_client_filter(current_user)
        if user_clients is not None:
            # Build OR filter for each client in the user's list
            from sqlalchemy import or_

            client_filter = or_(*[Employee.client_id_assigned.like(f"%{c}%") for c in user_clients])

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    filename = f"employees_{timestamp}.csv"

    logger.info(
        "CSV export requested: entity=employees, client_id=%s, user=%s",
        client_id,
        current_user.username,
    )

    generator = stream_csv_export(
        db=db,
        model_class=Employee,
        client_filter=client_filter,
        columns=EMPLOYEE_COLUMNS,
    )

    return StreamingResponse(
        generator,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =============================================================================
# Products Export
# =============================================================================

PRODUCT_COLUMNS = [
    ("product_id", "product_id"),
    ("client_id", "client_id"),
    ("product_code", "product_code"),
    ("product_name", "product_name"),
    ("description", "description"),
    ("ideal_cycle_time", "ideal_cycle_time"),
    ("unit_of_measure", "unit_of_measure"),
    ("is_active", "is_active"),
]


@router.get("/products")
async def export_products(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export products as CSV."""
    return _build_csv_response(
        db=db,
        current_user=current_user,
        model_class=Product,
        columns=PRODUCT_COLUMNS,
        entity_name="products",
        client_id=client_id,
    )


# =============================================================================
# Shifts Export
# =============================================================================

SHIFT_COLUMNS = [
    ("shift_id", "shift_id"),
    ("client_id", "client_id"),
    ("line_id", "line_id"),
    ("shift_name", "shift_name"),
    ("start_time", "start_time"),
    ("end_time", "end_time"),
    ("is_active", "is_active"),
]


@router.get("/shifts")
async def export_shifts(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export shifts as CSV."""
    return _build_csv_response(
        db=db,
        current_user=current_user,
        model_class=Shift,
        columns=SHIFT_COLUMNS,
        entity_name="shifts",
        client_id=client_id,
    )


# =============================================================================
# Hold Entries Export
# =============================================================================

HOLD_ENTRY_COLUMNS = [
    ("hold_entry_id", "hold_entry_id"),
    ("client_id", "client_id"),
    ("work_order_id", "work_order_id"),
    ("job_id", "job_id"),
    ("hold_status", "hold_status"),
    ("hold_date", "hold_date"),
    ("resume_date", "resume_date"),
    ("total_hold_duration_hours", "total_hold_duration_hours"),
    ("hold_reason_category", "hold_reason_category"),
    ("hold_reason", "hold_reason"),
    ("hold_reason_description", "hold_reason_description"),
    ("quality_issue_type", "quality_issue_type"),
    ("expected_resolution_date", "expected_resolution_date"),
    ("notes", "notes"),
]


@router.get("/holds")
async def export_holds(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export hold entries as CSV."""
    return _build_csv_response(
        db=db,
        current_user=current_user,
        model_class=HoldEntry,
        columns=HOLD_ENTRY_COLUMNS,
        entity_name="holds",
        client_id=client_id,
        date_field=HoldEntry.hold_date,
        start_date=start_date,
        end_date=end_date,
    )
