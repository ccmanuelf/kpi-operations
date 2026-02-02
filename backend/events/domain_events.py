"""
Domain Event Definitions
Phase 3: Domain Events Infrastructure

Defines all domain events for the KPI Operations platform.
Events capture significant state changes for audit and integration.
"""
from pydantic import Field
from typing import Optional, Dict, Any
from datetime import date
from decimal import Decimal

from backend.events.base import DomainEvent


# =============================================================================
# Work Order Events
# =============================================================================

class WorkOrderStatusChanged(DomainEvent):
    """Event raised when a work order status changes."""
    event_type: str = "work_order.status_changed"
    aggregate_type: str = "WorkOrder"

    from_status: Optional[str] = None
    to_status: str
    notes: Optional[str] = None
    trigger_source: str = "manual"


class WorkOrderCreated(DomainEvent):
    """Event raised when a new work order is created."""
    event_type: str = "work_order.created"
    aggregate_type: str = "WorkOrder"

    work_order_number: str
    customer_name: Optional[str] = None
    received_date: Optional[date] = None


class WorkOrderClosed(DomainEvent):
    """Event raised when a work order is closed."""
    event_type: str = "work_order.closed"
    aggregate_type: str = "WorkOrder"

    close_reason: Optional[str] = None
    final_status: str = "CLOSED"


# =============================================================================
# Production Events
# =============================================================================

class ProductionEntryCreated(DomainEvent):
    """Event raised when a production entry is created."""
    event_type: str = "production.entry_created"
    aggregate_type: str = "ProductionEntry"

    product_id: int
    shift_id: int
    production_date: date
    units_produced: int
    efficiency_percentage: Optional[Decimal] = None
    performance_percentage: Optional[Decimal] = None


class ProductionEntryUpdated(DomainEvent):
    """Event raised when a production entry is updated."""
    event_type: str = "production.entry_updated"
    aggregate_type: str = "ProductionEntry"

    changed_fields: Dict[str, Any] = Field(default_factory=dict)
    recalculated_kpis: bool = False


# =============================================================================
# Quality Events
# =============================================================================

class QualityInspectionRecorded(DomainEvent):
    """Event raised when a quality inspection is recorded."""
    event_type: str = "quality.inspection_recorded"
    aggregate_type: str = "QualityInspection"

    work_order_id: Optional[str] = None
    inspection_type: Optional[str] = None
    defect_count: int = 0
    scrap_count: int = 0
    passed: bool = True


class QualityDefectReported(DomainEvent):
    """Event raised when a quality defect is reported."""
    event_type: str = "quality.defect_reported"
    aggregate_type: str = "DefectEntry"

    work_order_id: Optional[str] = None
    defect_type: str
    quantity: int = 1
    severity: Optional[str] = None


# =============================================================================
# Hold Events
# =============================================================================

class HoldCreated(DomainEvent):
    """Event raised when a WIP hold is created."""
    event_type: str = "hold.created"
    aggregate_type: str = "HoldEntry"

    work_order_id: str
    hold_reason_category: Optional[str] = None
    hold_reason: Optional[str] = None
    quantity_on_hold: int = 0
    initial_status: str = "ON_HOLD"


class HoldResumed(DomainEvent):
    """Event raised when a WIP hold is resumed."""
    event_type: str = "hold.resumed"
    aggregate_type: str = "HoldEntry"

    work_order_id: str
    total_hold_duration_hours: Optional[Decimal] = None
    quantity_released: int = 0
    quantity_scrapped: int = 0


class HoldApprovalRequired(DomainEvent):
    """Event raised when a hold requires approval."""
    event_type: str = "hold.approval_required"
    aggregate_type: str = "HoldEntry"

    work_order_id: str
    requested_by: int
    hold_reason: Optional[str] = None


# =============================================================================
# KPI Threshold Events
# =============================================================================

class KPIThresholdViolated(DomainEvent):
    """Event raised when a KPI threshold is violated."""
    event_type: str = "kpi.threshold_violated"
    aggregate_type: str = "KPIMetric"

    metric_name: str
    current_value: Decimal
    threshold_value: Decimal
    threshold_type: str  # 'min', 'max', 'target'
    period: Optional[str] = None  # 'daily', 'weekly', 'monthly'


class KPITargetAchieved(DomainEvent):
    """Event raised when a KPI target is achieved."""
    event_type: str = "kpi.target_achieved"
    aggregate_type: str = "KPIMetric"

    metric_name: str
    current_value: Decimal
    target_value: Decimal
    period: Optional[str] = None


# =============================================================================
# Employee Events
# =============================================================================

class EmployeeAssignedToFloatingPool(DomainEvent):
    """Event raised when an employee is assigned to floating pool."""
    event_type: str = "employee.assigned_to_floating_pool"
    aggregate_type: str = "Employee"

    employee_name: str
    employee_code: str


class EmployeeAssignedToClient(DomainEvent):
    """Event raised when a floating pool employee is assigned to a client."""
    event_type: str = "employee.assigned_to_client"
    aggregate_type: str = "FloatingPoolAssignment"

    employee_id: int
    employee_name: str
    assigned_client_id: str
    available_from: Optional[date] = None
    available_to: Optional[date] = None
