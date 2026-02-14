"""
Availability KPI Calculation
PHASE 2: Machine/Line availability tracking

Availability = (Total Scheduled Time - Downtime) / Total Scheduled Time * 100
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Date
from datetime import date
from decimal import Decimal
from typing import Optional

from backend.schemas.downtime_entry import DowntimeEntry
from backend.schemas.shift import Shift


def calculate_availability(
    db: Session, work_order_id: str, target_date: date, client_id: Optional[str] = None
) -> tuple[Decimal, Decimal, Decimal, int]:
    """
    Calculate availability for a specific work order/date

    Args:
        db: Database session
        work_order_id: Work order to calculate availability for
        target_date: Date to calculate availability for
        client_id: Optional client filter

    Returns: (availability_percentage, scheduled_hours, downtime_hours, event_count)
    """

    # Default scheduled hours (8 hours per shift)
    scheduled_hours = Decimal("8.0")

    # Build query for downtime entries
    query = db.query(func.coalesce(func.sum(DowntimeEntry.downtime_duration_minutes), 0)).filter(
        and_(DowntimeEntry.work_order_id == work_order_id, cast(DowntimeEntry.shift_date, Date) == target_date)
    )

    if client_id:
        query = query.filter(DowntimeEntry.client_id == client_id)

    total_downtime_minutes = query.scalar()

    # Convert minutes to hours
    downtime_hours = Decimal(str(total_downtime_minutes)) / Decimal("60")

    # Count downtime events
    count_query = db.query(func.count(DowntimeEntry.downtime_entry_id)).filter(
        and_(DowntimeEntry.work_order_id == work_order_id, cast(DowntimeEntry.shift_date, Date) == target_date)
    )

    if client_id:
        count_query = count_query.filter(DowntimeEntry.client_id == client_id)

    event_count = count_query.scalar()

    # Calculate availability
    if scheduled_hours > 0:
        available_hours = scheduled_hours - downtime_hours
        availability_pct = (available_hours / scheduled_hours) * 100

        # Ensure non-negative
        availability_pct = max(Decimal("0"), availability_pct)
    else:
        availability_pct = Decimal("0")

    return (availability_pct, scheduled_hours, downtime_hours, event_count or 0)


def calculate_mtbf(
    db: Session, machine_id: str, start_date: date, end_date: date, client_id: Optional[str] = None
) -> Optional[Decimal]:
    """
    Calculate Mean Time Between Failures (MTBF)

    MTBF = Total Operating Time / Number of Failures
    """

    # Get all downtime events for machine (using DowntimeEntry with correct fields)
    query = db.query(DowntimeEntry).filter(
        and_(
            DowntimeEntry.machine_id == machine_id,
            cast(DowntimeEntry.shift_date, Date) >= start_date,
            cast(DowntimeEntry.shift_date, Date) <= end_date,
            DowntimeEntry.root_cause_category.in_(["Breakdown", "Failure", "Equipment Failure"]),
        )
    )

    if client_id:
        query = query.filter(DowntimeEntry.client_id == client_id)

    failures = query.all()

    if not failures:
        return None

    # Calculate total downtime in hours (DowntimeEntry stores minutes)
    total_downtime = sum(Decimal(str(f.downtime_duration_minutes or 0)) / Decimal("60") for f in failures)

    # Assume 24/7 operation (can be adjusted)
    days = (end_date - start_date).days + 1
    total_scheduled = Decimal(str(days * 24))

    operating_time = total_scheduled - total_downtime

    # MTBF calculation
    if len(failures) > 0:
        mtbf = operating_time / Decimal(str(len(failures)))
        return mtbf

    return None


def calculate_mttr(
    db: Session, machine_id: str, start_date: date, end_date: date, client_id: Optional[str] = None
) -> Optional[Decimal]:
    """
    Calculate Mean Time To Repair (MTTR)

    MTTR = Total Repair Time / Number of Repairs
    """

    query = db.query(DowntimeEntry).filter(
        and_(
            DowntimeEntry.machine_id == machine_id,
            cast(DowntimeEntry.shift_date, Date) >= start_date,
            cast(DowntimeEntry.shift_date, Date) <= end_date,
            DowntimeEntry.root_cause_category.in_(["Breakdown", "Failure", "Maintenance", "Equipment Failure"]),
        )
    )

    if client_id:
        query = query.filter(DowntimeEntry.client_id == client_id)

    repairs = query.all()

    if not repairs:
        return None

    # DowntimeEntry stores minutes, convert to hours
    total_repair_time = sum(Decimal(str(r.downtime_duration_minutes or 0)) / Decimal("60") for r in repairs)

    if len(repairs) > 0:
        mttr = total_repair_time / Decimal(str(len(repairs)))
        return mttr

    return None
