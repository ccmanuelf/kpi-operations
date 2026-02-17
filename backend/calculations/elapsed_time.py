"""
Elapsed Time Calculations for Work Order Lifecycle
Implements Phase 10.3: Workflow Foundation - Elapsed Time Calculations

Provides calculations for:
- Total lifecycle time (received → closure)
- Lead time (received → dispatch)
- Processing time (dispatch → completion)
- Shipping time (completion → shipped)
- Closure time (shipped → closed)
- Custom date range calculations
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from backend.schemas.work_order import WorkOrder
from backend.schemas.workflow import WorkflowTransitionLog


def _ensure_tz_compatible(dt1: datetime, dt2: datetime) -> tuple:
    """Normalize naive datetimes (from SQLite) to UTC for safe comparison."""
    if dt1.tzinfo is None and dt2.tzinfo is not None:
        dt1 = dt1.replace(tzinfo=timezone.utc)
    elif dt1.tzinfo is not None and dt2.tzinfo is None:
        dt2 = dt2.replace(tzinfo=timezone.utc)
    return dt1, dt2


def calculate_elapsed_hours(from_datetime: Optional[datetime], to_datetime: Optional[datetime]) -> Optional[int]:
    """
    Calculate elapsed hours between two datetimes.

    Args:
        from_datetime: Start datetime
        to_datetime: End datetime (defaults to now if None and from_datetime exists)

    Returns:
        Elapsed hours as integer, or None if from_datetime is missing
    """
    if from_datetime is None:
        return None

    if to_datetime is None:
        to_datetime = datetime.now(tz=timezone.utc)

    from_datetime, to_datetime = _ensure_tz_compatible(from_datetime, to_datetime)
    delta = to_datetime - from_datetime
    return int(delta.total_seconds() / 3600)


def calculate_elapsed_days(from_datetime: Optional[datetime], to_datetime: Optional[datetime]) -> Optional[float]:
    """
    Calculate elapsed days between two datetimes.

    Args:
        from_datetime: Start datetime
        to_datetime: End datetime (defaults to now if None and from_datetime exists)

    Returns:
        Elapsed days as float with 2 decimal precision, or None if from_datetime is missing
    """
    if from_datetime is None:
        return None

    if to_datetime is None:
        to_datetime = datetime.now(tz=timezone.utc)

    from_datetime, to_datetime = _ensure_tz_compatible(from_datetime, to_datetime)
    delta = to_datetime - from_datetime
    return round(delta.total_seconds() / 86400, 2)  # 86400 seconds in a day


def calculate_business_hours(
    from_datetime: Optional[datetime],
    to_datetime: Optional[datetime],
    hours_per_day: int = 8,
    working_days: List[int] = None,
) -> Optional[int]:
    """
    Calculate elapsed business hours between two datetimes.

    Args:
        from_datetime: Start datetime
        to_datetime: End datetime
        hours_per_day: Working hours per day (default 8)
        working_days: List of weekday numbers (0=Monday, default Mon-Fri)

    Returns:
        Elapsed business hours, or None if from_datetime is missing
    """
    if from_datetime is None:
        return None

    if to_datetime is None:
        to_datetime = datetime.now(tz=timezone.utc)

    from_datetime, to_datetime = _ensure_tz_compatible(from_datetime, to_datetime)

    if working_days is None:
        working_days = [0, 1, 2, 3, 4]  # Monday to Friday

    # Count working days
    business_days = 0
    current = from_datetime.date()
    end_date = to_datetime.date()

    while current <= end_date:
        if current.weekday() in working_days:
            business_days += 1
        current += timedelta(days=1)

    return business_days * hours_per_day


class WorkOrderElapsedTime:
    """
    Calculate elapsed times for a work order lifecycle.
    Provides multiple time metrics for analysis and reporting.
    """

    def __init__(self, work_order: WorkOrder):
        """
        Initialize with a work order.

        Args:
            work_order: Work order instance
        """
        self.work_order = work_order
        self._now = datetime.now(tz=timezone.utc)

    @property
    def total_lifecycle_hours(self) -> Optional[int]:
        """
        Total hours from received to closure (or now if not closed).

        Returns:
            Hours from received_date to closure_date or now
        """
        end_time = self.work_order.closure_date or self._now
        return calculate_elapsed_hours(self.work_order.received_date, end_time)

    @property
    def total_lifecycle_days(self) -> Optional[float]:
        """
        Total days from received to closure (or now if not closed).

        Returns:
            Days from received_date to closure_date or now
        """
        end_time = self.work_order.closure_date or self._now
        return calculate_elapsed_days(self.work_order.received_date, end_time)

    @property
    def lead_time_hours(self) -> Optional[int]:
        """
        Hours from received to dispatch (queue time).

        Returns:
            Hours from received_date to dispatch_date
        """
        return calculate_elapsed_hours(self.work_order.received_date, self.work_order.dispatch_date)

    @property
    def lead_time_days(self) -> Optional[float]:
        """
        Days from received to dispatch (queue time).

        Returns:
            Days from received_date to dispatch_date
        """
        return calculate_elapsed_days(self.work_order.received_date, self.work_order.dispatch_date)

    @property
    def processing_time_hours(self) -> Optional[int]:
        """
        Hours from dispatch to completion (actual work time).

        Returns:
            Hours from dispatch_date to closure_date or completion
        """
        end_time = self.work_order.closure_date or self._now
        return calculate_elapsed_hours(self.work_order.dispatch_date, end_time)

    @property
    def processing_time_days(self) -> Optional[float]:
        """
        Days from dispatch to completion.

        Returns:
            Days from dispatch_date to closure_date or completion
        """
        end_time = self.work_order.closure_date or self._now
        return calculate_elapsed_days(self.work_order.dispatch_date, end_time)

    @property
    def shipping_time_hours(self) -> Optional[int]:
        """
        Hours from completion to shipped.

        Returns:
            Hours from closure_date (if COMPLETED) to shipped_date
        """
        # Use actual_delivery_date if shipped_date not available
        shipped = self.work_order.shipped_date or self.work_order.actual_delivery_date
        # Use closure_date or updated_at as completion reference
        completed = self.work_order.closure_date or self.work_order.updated_at
        return calculate_elapsed_hours(completed, shipped)

    @property
    def time_to_expected(self) -> Optional[int]:
        """
        Hours remaining until expected date (negative if past due).

        Returns:
            Hours until expected_date (negative if overdue)
        """
        if self.work_order.expected_date is None:
            return None

        expected, now = _ensure_tz_compatible(self.work_order.expected_date, self._now)
        delta = expected - now
        return int(delta.total_seconds() / 3600)

    @property
    def is_overdue(self) -> bool:
        """
        Check if work order is past expected date.

        Returns:
            True if past expected_date and not closed
        """
        if self.work_order.closure_date is not None:
            return False  # Closed orders aren't overdue

        if self.work_order.expected_date is None:
            return False

        now, expected = _ensure_tz_compatible(self._now, self.work_order.expected_date)
        return now > expected

    @property
    def days_early_or_late(self) -> Optional[int]:
        """
        Days early (positive) or late (negative) vs expected date.

        Returns:
            Days difference (positive = early, negative = late)
        """
        if self.work_order.expected_date is None:
            return None

        actual_end = self.work_order.closure_date or self._now
        expected, end = _ensure_tz_compatible(self.work_order.expected_date, actual_end)
        delta = expected - end
        return delta.days

    def get_all_metrics(self) -> Dict:
        """
        Get all elapsed time metrics for the work order.

        Returns:
            Dictionary with all time metrics
        """
        return {
            "work_order_id": self.work_order.work_order_id,
            "status": self.work_order.status,
            "lifecycle": {
                "total_hours": self.total_lifecycle_hours,
                "total_days": self.total_lifecycle_days,
                "is_overdue": self.is_overdue,
                "days_early_or_late": self.days_early_or_late,
            },
            "stages": {
                "lead_time_hours": self.lead_time_hours,
                "lead_time_days": self.lead_time_days,
                "processing_time_hours": self.processing_time_hours,
                "processing_time_days": self.processing_time_days,
                "shipping_time_hours": self.shipping_time_hours,
            },
            "forecast": {
                "time_to_expected_hours": self.time_to_expected,
                "expected_date": self.work_order.expected_date.isoformat() if self.work_order.expected_date else None,
            },
            "dates": {
                "received_date": self.work_order.received_date.isoformat() if self.work_order.received_date else None,
                "dispatch_date": self.work_order.dispatch_date.isoformat() if self.work_order.dispatch_date else None,
                "shipped_date": self.work_order.shipped_date.isoformat() if self.work_order.shipped_date else None,
                "closure_date": self.work_order.closure_date.isoformat() if self.work_order.closure_date else None,
            },
        }


def calculate_work_order_elapsed_times(work_order: WorkOrder) -> Dict:
    """
    Convenience function to get all elapsed times for a work order.

    Args:
        work_order: Work order instance

    Returns:
        Dictionary with all elapsed time metrics
    """
    calc = WorkOrderElapsedTime(work_order)
    return calc.get_all_metrics()


def calculate_client_average_times(
    db: Session,
    client_id: str,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict:
    """
    Calculate average elapsed times for a client's work orders.

    Args:
        db: Database session
        client_id: Client ID
        status: Filter by status (optional)
        start_date: Filter by start date (optional)
        end_date: Filter by end date (optional)

    Returns:
        Dictionary with average time metrics
    """
    query = db.query(WorkOrder).filter(WorkOrder.client_id == client_id)

    if status:
        query = query.filter(WorkOrder.status == status)

    if start_date:
        query = query.filter(WorkOrder.received_date >= start_date)

    if end_date:
        query = query.filter(WorkOrder.received_date <= end_date)

    work_orders = query.all()

    if not work_orders:
        return {"client_id": client_id, "count": 0, "averages": None}

    # Calculate totals
    total_lifecycle = []
    total_lead_time = []
    total_processing = []
    overdue_count = 0

    for wo in work_orders:
        calc = WorkOrderElapsedTime(wo)

        if calc.total_lifecycle_hours is not None:
            total_lifecycle.append(calc.total_lifecycle_hours)

        if calc.lead_time_hours is not None:
            total_lead_time.append(calc.lead_time_hours)

        if calc.processing_time_hours is not None:
            total_processing.append(calc.processing_time_hours)

        if calc.is_overdue:
            overdue_count += 1

    def safe_avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else None

    return {
        "client_id": client_id,
        "count": len(work_orders),
        "overdue_count": overdue_count,
        "overdue_percentage": round(overdue_count / len(work_orders) * 100, 2) if work_orders else 0,
        "averages": {
            "lifecycle_hours": safe_avg(total_lifecycle),
            "lifecycle_days": round(safe_avg(total_lifecycle) / 24, 2) if safe_avg(total_lifecycle) else None,
            "lead_time_hours": safe_avg(total_lead_time),
            "lead_time_days": round(safe_avg(total_lead_time) / 24, 2) if safe_avg(total_lead_time) else None,
            "processing_time_hours": safe_avg(total_processing),
            "processing_time_days": round(safe_avg(total_processing) / 24, 2) if safe_avg(total_processing) else None,
        },
    }


def get_transition_elapsed_times(db: Session, work_order_id: str, client_id: str) -> List[Dict]:
    """
    Get elapsed times between each transition for a work order.

    Args:
        db: Database session
        work_order_id: Work order ID
        client_id: Client ID

    Returns:
        List of dictionaries with transition details and elapsed times
    """
    transitions = (
        db.query(WorkflowTransitionLog)
        .filter(
            and_(WorkflowTransitionLog.work_order_id == work_order_id, WorkflowTransitionLog.client_id == client_id)
        )
        .order_by(WorkflowTransitionLog.transitioned_at.asc())
        .all()
    )

    result = []
    prev_time = None

    for trans in transitions:
        elapsed_from_prev = None
        if prev_time:
            elapsed_from_prev = calculate_elapsed_hours(prev_time, trans.transitioned_at)

        result.append(
            {
                "transition_id": trans.transition_id,
                "from_status": trans.from_status,
                "to_status": trans.to_status,
                "transitioned_at": trans.transitioned_at.isoformat() if trans.transitioned_at else None,
                "elapsed_from_previous_hours": elapsed_from_prev,
                "elapsed_from_received_hours": trans.elapsed_from_received_hours,
                "trigger_source": trans.trigger_source,
                "notes": trans.notes,
            }
        )

        prev_time = trans.transitioned_at

    return result


def calculate_stage_duration_summary(
    db: Session, client_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
) -> Dict:
    """
    Calculate average duration for each workflow stage.

    Args:
        db: Database session
        client_id: Client ID
        start_date: Filter by start date
        end_date: Filter by end date

    Returns:
        Dictionary with stage durations
    """
    query = db.query(
        WorkflowTransitionLog.from_status,
        WorkflowTransitionLog.to_status,
        func.avg(WorkflowTransitionLog.elapsed_from_previous_hours).label("avg_hours"),
        func.min(WorkflowTransitionLog.elapsed_from_previous_hours).label("min_hours"),
        func.max(WorkflowTransitionLog.elapsed_from_previous_hours).label("max_hours"),
        func.count(WorkflowTransitionLog.transition_id).label("count"),
    ).filter(
        WorkflowTransitionLog.client_id == client_id, WorkflowTransitionLog.elapsed_from_previous_hours.isnot(None)
    )

    if start_date:
        query = query.filter(WorkflowTransitionLog.transitioned_at >= start_date)

    if end_date:
        query = query.filter(WorkflowTransitionLog.transitioned_at <= end_date)

    results = query.group_by(WorkflowTransitionLog.from_status, WorkflowTransitionLog.to_status).all()

    stages = []
    for r in results:
        stages.append(
            {
                "from_status": r.from_status,
                "to_status": r.to_status,
                "avg_hours": round(r.avg_hours, 2) if r.avg_hours else None,
                "avg_days": round(r.avg_hours / 24, 2) if r.avg_hours else None,
                "min_hours": r.min_hours,
                "max_hours": r.max_hours,
                "transition_count": r.count,
            }
        )

    return {
        "client_id": client_id,
        "stage_durations": stages,
        "filter": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    }
