"""
On-Time Delivery (OTD) KPI Calculation
PHASE 3: Delivery performance tracking
Enhanced with P3-001: TRUE-OTD vs Standard OTD
Enhanced with Date Inference Chain for audit compliance

OTD% = (Orders Delivered On Time / Total Orders) * 100
TRUE-OTD% = (COMPLETE Orders Delivered On Time / Total COMPLETE Orders) * 100

Date Inference Chain (per specification):
planned_ship_date → required_date → (planned_start + cycle_time × qty)
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Tuple, NamedTuple
from dataclasses import dataclass

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.work_order import WorkOrder, WorkOrderStatus


# =============================================================================
# OTD Date Inference Chain (Audit Requirement)
# =============================================================================


@dataclass
class InferredDate:
    """Result of date inference with metadata for ESTIMATED flag"""

    date: Optional[datetime]
    is_inferred: bool
    inference_source: str  # "planned_ship_date", "required_date", "calculated", "none"
    confidence_score: float  # 1.0 for actual, 0.8 for required_date, 0.5 for calculated


def infer_planned_delivery_date(work_order: WorkOrder) -> InferredDate:
    """
    Infer the planned delivery date using the specification fallback chain:
    planned_ship_date → required_date → (planned_start + cycle_time × qty)

    This implements the OTD Date Inference Chain per audit requirement.

    Args:
        work_order: WorkOrder object with date and cycle time fields

    Returns:
        InferredDate with the resolved date and inference metadata
    """
    # Level 1: Use planned_ship_date (highest confidence - explicit value)
    if work_order.planned_ship_date is not None:
        return InferredDate(
            date=work_order.planned_ship_date,
            is_inferred=False,
            inference_source="planned_ship_date",
            confidence_score=1.0,
        )

    # Level 2: Fall back to required_date (medium confidence)
    if work_order.required_date is not None:
        return InferredDate(
            date=work_order.required_date, is_inferred=True, inference_source="required_date", confidence_score=0.8
        )

    # Level 3: Calculate from planned_start + (cycle_time × quantity)
    if work_order.planned_start_date is not None:
        # Try to use ideal_cycle_time, fall back to calculated_cycle_time
        cycle_time = work_order.ideal_cycle_time or work_order.calculated_cycle_time
        quantity = work_order.planned_quantity or 1

        if cycle_time is not None and cycle_time > 0:
            # cycle_time is in hours, convert to days for date calculation
            total_hours = float(cycle_time) * quantity
            total_days = max(1, int(total_hours / 8))  # Assume 8-hour workday

            calculated_date = work_order.planned_start_date + timedelta(days=total_days)
            return InferredDate(
                date=calculated_date, is_inferred=True, inference_source="calculated", confidence_score=0.5
            )
        else:
            # No cycle time - use planned_start + default lead time (7 days)
            calculated_date = work_order.planned_start_date + timedelta(days=7)
            return InferredDate(
                date=calculated_date, is_inferred=True, inference_source="calculated", confidence_score=0.3
            )

    # No date can be inferred
    return InferredDate(date=None, is_inferred=False, inference_source="none", confidence_score=0.0)


def calculate_otd(
    db: Session, start_date: date, end_date: date, product_id: Optional[int] = None
) -> tuple[Decimal, int, int]:
    """
    Calculate On-Time Delivery percentage

    Note: This is a simplified calculation based on production entries.
    In a full system, this would use order/shipment data.

    For MVP, we consider production completed on time if:
    - Production date <= planned completion date (stored in work_order metadata)

    Returns: (otd_percentage, on_time_count, total_count)
    """

    query = db.query(ProductionEntry).filter(
        and_(ProductionEntry.production_date >= start_date, ProductionEntry.production_date <= end_date)
    )

    if product_id:
        query = query.filter(ProductionEntry.product_id == product_id)

    entries = query.all()

    if not entries:
        return (Decimal("0"), 0, 0)

    # For MVP: Assume orders with confirmation are on-time
    # In production, this would check against delivery dates
    on_time_count = sum(1 for e in entries if e.confirmed_by is not None)
    total_count = len(entries)

    if total_count > 0:
        otd_percentage = (Decimal(str(on_time_count)) / Decimal(str(total_count))) * 100
    else:
        otd_percentage = Decimal("0")

    return (otd_percentage, on_time_count, total_count)


def calculate_lead_time(db: Session, work_order_id: str) -> Optional[int]:
    """
    Calculate actual lead time for a work order

    Lead Time = Completion Date - Start Date (in days)

    In MVP, we calculate from first to last production entry
    """

    entries = (
        db.query(ProductionEntry)
        .filter(ProductionEntry.work_order_id == work_order_id)
        .order_by(ProductionEntry.production_date)
        .all()
    )

    if not entries or len(entries) < 1:
        return None

    start_date = entries[0].production_date
    end_date = entries[-1].production_date

    lead_time_days = (end_date - start_date).days + 1  # Include both days

    return lead_time_days


def calculate_cycle_time(db: Session, work_order_id: str) -> Optional[Decimal]:
    """
    Calculate total cycle time (production hours) for work order
    """

    total_hours = (
        db.query(func.sum(ProductionEntry.run_time_hours))
        .filter(ProductionEntry.work_order_id == work_order_id)
        .scalar()
    )

    if total_hours:
        return Decimal(str(total_hours))

    return None


def calculate_delivery_variance(
    db: Session, start_date: date, end_date: date, product_id: Optional[int] = None
) -> dict:
    """
    Calculate variance between planned and actual delivery

    Returns metrics on early/late deliveries
    """

    # This would be implemented with actual order/delivery data
    # For MVP, returning placeholder structure

    return {
        "total_orders": 0,
        "early_deliveries": 0,
        "on_time_deliveries": 0,
        "late_deliveries": 0,
        "average_variance_days": Decimal("0"),
        "worst_variance_days": 0,
        "best_variance_days": 0,
    }


def identify_late_orders(db: Session, as_of_date: date = None) -> list[dict]:
    """
    Identify work orders that are potentially late

    In MVP: Orders without confirmation that are older than 7 days
    """

    if not as_of_date:
        as_of_date = date.today()

    from datetime import timedelta

    threshold_date = as_of_date - timedelta(days=7)

    late_entries = (
        db.query(ProductionEntry)
        .filter(
            and_(
                ProductionEntry.production_date <= threshold_date,
                ProductionEntry.confirmed_by.is_(None),
                ProductionEntry.work_order_id.isnot(None),
            )
        )
        .all()
    )

    # Group by work order
    work_orders = {}
    for entry in late_entries:
        wo = entry.work_order_id
        if wo not in work_orders:
            # Handle both date and datetime types for production_date
            prod_date = entry.production_date
            if hasattr(prod_date, "date"):
                prod_date = prod_date.date()
            work_orders[wo] = {
                "work_order": wo,
                "product_id": entry.product_id,
                "start_date": entry.production_date,
                "days_pending": (as_of_date - prod_date).days,
                "total_units": 0,
            }
        work_orders[wo]["total_units"] += entry.units_produced

    # Convert to list and sort by days pending
    results = list(work_orders.values())
    results.sort(key=lambda x: x["days_pending"], reverse=True)

    return results


# =============================================================================
# P3-001: TRUE-OTD vs Standard OTD Calculation
# =============================================================================


def calculate_true_otd(db: Session, client_id: str, start_date: date, end_date: date) -> Dict:
    """
    Calculate TRUE-OTD: Only counts COMPLETE orders (status='COMPLETED')
    P3-001: TRUE-OTD Implementation
    Enhanced: Uses date inference chain when planned_ship_date is missing

    TRUE-OTD: An order is on-time ONLY if:
    1. Status is COMPLETED
    2. actual_delivery_date <= inferred_planned_date

    Standard OTD: Uses all orders with actual_delivery_date

    Date Inference Chain:
    planned_ship_date → required_date → (planned_start + cycle_time × qty)

    Args:
        db: Database session
        client_id: Client ID to filter
        start_date: Start of date range
        end_date: End of date range

    Returns:
        Dict with both TRUE-OTD and Standard OTD metrics plus inference metadata
    """
    # Convert dates to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # TRUE-OTD: Only COMPLETED orders with actual delivery date
    # ENHANCED: Removed planned_ship_date requirement - use inference chain
    complete_orders = (
        db.query(WorkOrder)
        .filter(
            and_(
                WorkOrder.client_id == client_id,
                WorkOrder.status == WorkOrderStatus.COMPLETED,
                WorkOrder.actual_delivery_date.isnot(None),
                WorkOrder.actual_delivery_date >= start_datetime,
                WorkOrder.actual_delivery_date <= end_datetime,
            )
        )
        .all()
    )

    # Calculate TRUE-OTD metrics with inference chain
    true_otd_on_time = 0
    true_otd_late = 0
    true_otd_early = 0
    true_otd_inferred_count = 0
    true_otd_skipped = 0  # Orders without any inferable date

    for wo in complete_orders:
        # Use inference chain to get planned date
        inferred = infer_planned_delivery_date(wo)

        if inferred.date is None:
            # No date could be inferred - skip this order
            true_otd_skipped += 1
            continue

        if inferred.is_inferred:
            true_otd_inferred_count += 1

        if wo.actual_delivery_date <= inferred.date:
            true_otd_on_time += 1
            # Check if early (more than 1 day before planned)
            days_diff = (inferred.date - wo.actual_delivery_date).days
            if days_diff > 1:
                true_otd_early += 1
        else:
            true_otd_late += 1

    true_otd_total = len(complete_orders) - true_otd_skipped
    true_otd_pct = Decimal("0")
    if true_otd_total > 0:
        true_otd_pct = (Decimal(str(true_otd_on_time)) / Decimal(str(true_otd_total))) * 100

    # Standard OTD: All orders with delivery dates (any status)
    # ENHANCED: Removed planned_ship_date requirement - use inference chain
    standard_orders = (
        db.query(WorkOrder)
        .filter(
            and_(
                WorkOrder.client_id == client_id,
                WorkOrder.actual_delivery_date.isnot(None),
                WorkOrder.actual_delivery_date >= start_datetime,
                WorkOrder.actual_delivery_date <= end_datetime,
            )
        )
        .all()
    )

    standard_on_time = 0
    standard_inferred_count = 0
    standard_skipped = 0

    for wo in standard_orders:
        inferred = infer_planned_delivery_date(wo)

        if inferred.date is None:
            standard_skipped += 1
            continue

        if inferred.is_inferred:
            standard_inferred_count += 1

        if wo.actual_delivery_date <= inferred.date:
            standard_on_time += 1

    standard_total = len(standard_orders) - standard_skipped
    standard_pct = Decimal("0")
    if standard_total > 0:
        standard_pct = (Decimal(str(standard_on_time)) / Decimal(str(standard_total))) * 100

    # Calculate inference rate
    total_processed = true_otd_total + standard_total
    total_inferred = true_otd_inferred_count + standard_inferred_count
    inference_rate = (total_inferred / total_processed * 100) if total_processed > 0 else 0

    return {
        "true_otd": {
            "on_time": true_otd_on_time,
            "late": true_otd_late,
            "early": true_otd_early,
            "total": true_otd_total,
            "percentage": true_otd_pct.quantize(Decimal("0.01")),
            "description": "COMPLETE orders only",
            "inferred_dates_count": true_otd_inferred_count,
            "skipped_no_date": true_otd_skipped,
        },
        "standard_otd": {
            "on_time": standard_on_time,
            "total": standard_total,
            "percentage": standard_pct.quantize(Decimal("0.01")),
            "description": "All orders with delivery dates",
            "inferred_dates_count": standard_inferred_count,
            "skipped_no_date": standard_skipped,
        },
        "variance": {
            "percentage_diff": (true_otd_pct - standard_pct).quantize(Decimal("0.01")),
            "count_diff": true_otd_total - standard_total,
        },
        "inference": {
            "is_estimated": total_inferred > 0,
            "inferred_dates_total": total_inferred,
            "inference_rate_percentage": round(inference_rate, 2),
            "confidence_note": (
                "Dates inferred via: planned_ship_date → required_date → calculated" if total_inferred > 0 else None
            ),
        },
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "client_id": client_id,
    }


def calculate_otd_by_work_order(db: Session, work_order_id: str) -> Optional[Dict]:
    """
    Calculate OTD status for a single work order
    P3-001: Work order level OTD
    Enhanced: Uses date inference chain when planned_ship_date is missing

    Date Inference Chain:
    planned_ship_date → required_date → (planned_start + cycle_time × qty)

    Args:
        db: Database session
        work_order_id: Work order ID

    Returns:
        Dict with OTD metrics or None if not found
    """
    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

    if not work_order:
        return None

    # Use inference chain to get planned date
    inferred = infer_planned_delivery_date(work_order)

    result = {
        "work_order_id": work_order_id,
        "status": work_order.status.value if work_order.status else None,
        "planned_ship_date": work_order.planned_ship_date.isoformat() if work_order.planned_ship_date else None,
        "required_date": work_order.required_date.isoformat() if work_order.required_date else None,
        "actual_delivery_date": (
            work_order.actual_delivery_date.isoformat() if work_order.actual_delivery_date else None
        ),
        "is_on_time": None,
        "days_variance": None,
        "qualifies_for_true_otd": False,
        # Inference metadata per audit requirement
        "inference": {
            "effective_planned_date": inferred.date.isoformat() if inferred.date else None,
            "is_estimated": inferred.is_inferred,
            "inference_source": inferred.inference_source,
            "confidence_score": inferred.confidence_score,
        },
    }

    # Check if this work order qualifies for TRUE-OTD
    if work_order.status == WorkOrderStatus.COMPLETED:
        result["qualifies_for_true_otd"] = True

    # Calculate OTD using inferred date
    if inferred.date is not None and work_order.actual_delivery_date:
        result["is_on_time"] = work_order.actual_delivery_date <= inferred.date
        result["days_variance"] = (work_order.actual_delivery_date - inferred.date).days

    return result


def calculate_otd_trend(
    db: Session, client_id: str, start_date: date, end_date: date, interval: str = "weekly"
) -> Dict:
    """
    Calculate OTD trend over time with both TRUE-OTD and Standard OTD
    P3-001: Trend analysis with toggle support

    Args:
        db: Database session
        client_id: Client ID
        start_date: Start date
        end_date: End date
        interval: "daily", "weekly", or "monthly"

    Returns:
        Dict with trend data
    """
    from datetime import timedelta
    from collections import defaultdict

    # Determine interval
    if interval == "daily":
        delta = timedelta(days=1)
    elif interval == "weekly":
        delta = timedelta(weeks=1)
    else:  # monthly
        delta = timedelta(days=30)

    # Generate date ranges
    current = start_date
    periods = []
    while current <= end_date:
        period_end = min(current + delta - timedelta(days=1), end_date)
        periods.append((current, period_end))
        current = current + delta

    # Calculate metrics for each period
    trend_data = []
    for period_start, period_end in periods:
        metrics = calculate_true_otd(db, client_id, period_start, period_end)
        trend_data.append(
            {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "true_otd_percentage": metrics["true_otd"]["percentage"],
                "true_otd_count": metrics["true_otd"]["total"],
                "standard_otd_percentage": metrics["standard_otd"]["percentage"],
                "standard_otd_count": metrics["standard_otd"]["total"],
            }
        )

    # Calculate overall averages
    if trend_data:
        avg_true_otd = sum(Decimal(str(d["true_otd_percentage"])) for d in trend_data) / len(trend_data)
        avg_standard_otd = sum(Decimal(str(d["standard_otd_percentage"])) for d in trend_data) / len(trend_data)
    else:
        avg_true_otd = Decimal("0")
        avg_standard_otd = Decimal("0")

    return {
        "trend": trend_data,
        "summary": {
            "average_true_otd": avg_true_otd.quantize(Decimal("0.01")),
            "average_standard_otd": avg_standard_otd.quantize(Decimal("0.01")),
            "periods_analyzed": len(trend_data),
            "interval": interval,
        },
        "client_id": client_id,
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
    }


def calculate_otd_by_product(db: Session, client_id: str, start_date: date, end_date: date) -> Dict:
    """
    Calculate OTD metrics grouped by product/style
    P3-001: Product-level OTD analysis
    Enhanced: Uses date inference chain when planned_ship_date is missing

    Date Inference Chain:
    planned_ship_date → required_date → (planned_start + cycle_time × qty)

    Args:
        db: Database session
        client_id: Client ID
        start_date: Start date
        end_date: End date

    Returns:
        Dict with OTD by product
    """
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Get all orders in range
    # ENHANCED: Removed planned_ship_date requirement - use inference chain
    orders = (
        db.query(WorkOrder)
        .filter(
            and_(
                WorkOrder.client_id == client_id,
                WorkOrder.actual_delivery_date.isnot(None),
                WorkOrder.actual_delivery_date >= start_datetime,
                WorkOrder.actual_delivery_date <= end_datetime,
            )
        )
        .all()
    )

    # Group by style_model with inference tracking
    product_metrics = {}
    total_inferred = 0
    total_skipped = 0

    for wo in orders:
        # Use inference chain to get planned date
        inferred = infer_planned_delivery_date(wo)

        if inferred.date is None:
            total_skipped += 1
            continue

        if inferred.is_inferred:
            total_inferred += 1

        style = wo.style_model
        if style not in product_metrics:
            product_metrics[style] = {
                "style_model": style,
                "true_otd_on_time": 0,
                "true_otd_total": 0,
                "standard_on_time": 0,
                "standard_total": 0,
                "inferred_count": 0,
            }

        if inferred.is_inferred:
            product_metrics[style]["inferred_count"] += 1

        # Standard OTD using inferred date
        product_metrics[style]["standard_total"] += 1
        if wo.actual_delivery_date <= inferred.date:
            product_metrics[style]["standard_on_time"] += 1

        # TRUE-OTD (only COMPLETED)
        if wo.status == WorkOrderStatus.COMPLETED:
            product_metrics[style]["true_otd_total"] += 1
            if wo.actual_delivery_date <= inferred.date:
                product_metrics[style]["true_otd_on_time"] += 1

    # Calculate percentages
    results = []
    for style, metrics in product_metrics.items():
        true_pct = Decimal("0")
        if metrics["true_otd_total"] > 0:
            true_pct = (Decimal(str(metrics["true_otd_on_time"])) / Decimal(str(metrics["true_otd_total"]))) * 100

        standard_pct = Decimal("0")
        if metrics["standard_total"] > 0:
            standard_pct = (Decimal(str(metrics["standard_on_time"])) / Decimal(str(metrics["standard_total"]))) * 100

        results.append(
            {
                "style_model": style,
                "true_otd": {
                    "on_time": metrics["true_otd_on_time"],
                    "total": metrics["true_otd_total"],
                    "percentage": true_pct.quantize(Decimal("0.01")),
                },
                "standard_otd": {
                    "on_time": metrics["standard_on_time"],
                    "total": metrics["standard_total"],
                    "percentage": standard_pct.quantize(Decimal("0.01")),
                },
                "inferred_dates_count": metrics["inferred_count"],
            }
        )

    # Sort by TRUE-OTD percentage (lowest first to highlight issues)
    results.sort(key=lambda x: x["true_otd"]["percentage"])

    # Calculate inference rate
    total_processed = len(orders) - total_skipped
    inference_rate = (total_inferred / total_processed * 100) if total_processed > 0 else 0

    return {
        "by_product": results,
        "total_products": len(results),
        "inference": {
            "is_estimated": total_inferred > 0,
            "inferred_dates_total": total_inferred,
            "skipped_no_date": total_skipped,
            "inference_rate_percentage": round(inference_rate, 2),
        },
        "client_id": client_id,
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
    }
