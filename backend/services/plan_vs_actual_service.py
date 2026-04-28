"""
Plan vs Actual Service
Compares capacity planning orders against actual production data.
Calculates variance, risk assessment, and per-line breakdowns.
"""

from typing import List, Optional, Dict, Any
from datetime import date, timedelta
from sqlalchemy.orm import Session

from backend.utils.logging_utils import get_module_logger
from backend.orm.capacity.orders import CapacityOrder, OrderStatus
from backend.orm.work_order import WorkOrder
from backend.orm.production_entry import ProductionEntry
from backend.middleware.client_auth import build_client_filter_clause
from backend.orm.user import User

logger = get_module_logger(__name__)


def get_plan_vs_actual(
    db: Session,
    current_user: User,
    client_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    line_id: Optional[int] = None,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get plan vs actual comparison for capacity orders.

    For each capacity order:
    1. Get planned_quantity from the capacity order (order_quantity)
    2. Sum actual_quantity from linked work orders
    3. Sum units_produced from production entries linked to those work orders
    4. Calculate variance and risk

    Args:
        db: Database session
        current_user: Authenticated user for multi-tenant filtering
        client_id: Optional explicit client_id filter
        start_date: Filter capacity orders with required_date >= start_date
        end_date: Filter capacity orders with required_date <= end_date
        line_id: Filter production entries by production line
        status_filter: Filter by specific capacity order status

    Returns:
        List of plan vs actual comparison dicts, one per capacity order
    """
    query = db.query(CapacityOrder)

    # Multi-tenant filtering
    client_filter = build_client_filter_clause(current_user, CapacityOrder.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)
    if client_id:
        query = query.filter(CapacityOrder.client_id == client_id)

    # Status filter - default to active orders only
    if status_filter:
        query = query.filter(CapacityOrder.status == status_filter)
    else:
        query = query.filter(CapacityOrder.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED]))

    # Date range filter on required_date
    if start_date:
        query = query.filter(CapacityOrder.required_date >= start_date)
    if end_date:
        query = query.filter(CapacityOrder.required_date <= end_date)

    capacity_orders = query.order_by(CapacityOrder.required_date).all()

    logger.info(
        "Plan vs actual query returned %d capacity orders for user=%s",
        len(capacity_orders),
        current_user.username,
    )

    results = []
    for cap_order in capacity_orders:
        result = _build_plan_vs_actual_entry(db, cap_order, line_id)
        results.append(result)

    return results


def _build_plan_vs_actual_entry(
    db: Session,
    cap_order: CapacityOrder,
    line_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a single plan vs actual entry for one capacity order."""

    # Get linked work orders
    wo_query = db.query(WorkOrder).filter(
        WorkOrder.capacity_order_id == cap_order.id,
        WorkOrder.client_id == cap_order.client_id,
    )
    linked_work_orders = wo_query.all()

    # Sum actual completed from work orders
    wo_actual_total = sum(wo.actual_quantity or 0 for wo in linked_work_orders)

    # Get production entries from linked work orders
    wo_ids = [wo.work_order_id for wo in linked_work_orders]

    production_total = 0
    line_breakdown: Dict[str, Dict[str, Any]] = {}

    if wo_ids:
        pe_query = db.query(ProductionEntry).filter(
            ProductionEntry.work_order_id.in_(wo_ids),
            ProductionEntry.client_id == cap_order.client_id,
        )
        if line_id is not None:
            pe_query = pe_query.filter(ProductionEntry.line_id == line_id)

        production_entries = pe_query.all()
        production_total = sum(pe.units_produced or 0 for pe in production_entries)

        # Per-line breakdown
        for pe in production_entries:
            lid = str(pe.line_id) if pe.line_id is not None else "UNASSIGNED"
            if lid not in line_breakdown:
                line_breakdown[lid] = {
                    "line_id": lid,
                    "units_produced": 0,
                    "entry_count": 0,
                }
            line_breakdown[lid]["units_produced"] += pe.units_produced or 0
            line_breakdown[lid]["entry_count"] += 1

    # Use the higher of wo_actual_total and production_total as the actual
    actual_completed = max(wo_actual_total, production_total)

    # Calculate variance
    planned_quantity = cap_order.order_quantity or 0
    variance_quantity = actual_completed - planned_quantity
    variance_percentage = round((variance_quantity / planned_quantity) * 100, 2) if planned_quantity > 0 else 0.0

    # Calculate on-time risk
    on_time_risk = _calculate_risk(cap_order, actual_completed, planned_quantity)

    # Projected completion (simple linear projection)
    projected_completion = _project_completion(cap_order, actual_completed, planned_quantity)

    return {
        "capacity_order_id": cap_order.id,
        "order_number": cap_order.order_number,
        "customer_name": cap_order.customer_name,
        "style_model": cap_order.style_model,
        # status/priority are Mapped[Optional[Enum]] in the ORM. Use
        # an explicit None-or-value chain so mypy doesn't trip on
        # `.value` access via hasattr-narrow (which doesn't actually
        # exclude None).
        "status": (cap_order.status.value if cap_order.status is not None else None),
        "priority": (cap_order.priority.value if cap_order.priority is not None else None),
        "planned_quantity": planned_quantity,
        "actual_completed": actual_completed,
        "variance_quantity": variance_quantity,
        "variance_percentage": variance_percentage,
        "completion_percentage": (
            round((actual_completed / planned_quantity * 100), 2) if planned_quantity > 0 else 0.0
        ),
        "required_date": (cap_order.required_date.isoformat() if cap_order.required_date else None),
        "planned_start_date": (cap_order.planned_start_date.isoformat() if cap_order.planned_start_date else None),
        "planned_end_date": (cap_order.planned_end_date.isoformat() if cap_order.planned_end_date else None),
        "projected_completion": projected_completion,
        "on_time_risk": on_time_risk,
        "linked_work_orders": len(linked_work_orders),
        "line_breakdown": list(line_breakdown.values()),
    }


def _calculate_risk(cap_order: CapacityOrder, actual_completed: int, planned_quantity: int) -> str:
    """
    Calculate on-time delivery risk level.

    Returns one of: COMPLETED, OVERDUE, LOW, MEDIUM, HIGH, UNKNOWN
    """
    if not cap_order.required_date or planned_quantity == 0:
        return "UNKNOWN"

    remaining_quantity = max(0, planned_quantity - actual_completed)

    if remaining_quantity == 0:
        return "COMPLETED"

    today = date.today()
    days_remaining = (cap_order.required_date - today).days

    if days_remaining <= 0:
        return "OVERDUE"

    # Calculate completion rate
    completion_pct = actual_completed / planned_quantity if planned_quantity > 0 else 0

    # If order has a planned_start_date, use time-based risk comparison
    if cap_order.planned_start_date:
        total_days = (cap_order.required_date - cap_order.planned_start_date).days
        elapsed_days = (today - cap_order.planned_start_date).days
        if total_days > 0 and elapsed_days >= 0:
            expected_pct = elapsed_days / total_days
            if completion_pct >= expected_pct * 0.9:
                return "LOW"
            elif completion_pct >= expected_pct * 0.7:
                return "MEDIUM"
            else:
                return "HIGH"

    # Fallback: simple ratio-based risk
    if completion_pct >= 0.8:
        return "LOW"
    elif completion_pct >= 0.5:
        return "MEDIUM"
    else:
        return "HIGH"


def _project_completion(cap_order: CapacityOrder, actual_completed: int, planned_quantity: int) -> Optional[str]:
    """
    Project completion date based on current production rate.
    Uses simple linear projection from planned_start_date to today.

    Returns ISO-format date string or None if projection is not possible.
    """
    if not cap_order.planned_start_date or actual_completed == 0 or planned_quantity == 0:
        return None

    today = date.today()
    elapsed_days = max(1, (today - cap_order.planned_start_date).days)
    daily_rate = actual_completed / elapsed_days

    if daily_rate <= 0:
        return None

    remaining = max(0, planned_quantity - actual_completed)
    days_needed = remaining / daily_rate
    projected = today + timedelta(days=int(days_needed))
    return projected.isoformat()


def get_plan_vs_actual_summary(
    db: Session,
    current_user: User,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get aggregate summary of plan vs actual across all active orders.

    Args:
        db: Database session
        current_user: Authenticated user for multi-tenant filtering
        client_id: Optional explicit client_id filter

    Returns:
        Summary dict with totals, risk distribution, and individual order details
    """
    details = get_plan_vs_actual(db, current_user, client_id=client_id)

    total_planned = sum(d["planned_quantity"] for d in details)
    total_actual = sum(d["actual_completed"] for d in details)

    risk_counts = {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "OVERDUE": 0,
        "COMPLETED": 0,
        "UNKNOWN": 0,
    }
    for d in details:
        risk = d["on_time_risk"]
        if risk in risk_counts:
            risk_counts[risk] += 1

    return {
        "total_orders": len(details),
        "total_planned_quantity": total_planned,
        "total_actual_completed": total_actual,
        "overall_variance": total_actual - total_planned,
        "overall_completion_pct": (round((total_actual / total_planned * 100), 2) if total_planned > 0 else 0.0),
        "risk_distribution": risk_counts,
        "orders": details,
    }
