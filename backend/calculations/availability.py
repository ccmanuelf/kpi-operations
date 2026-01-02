"""
Availability KPI Calculation
PHASE 2: Machine/Line availability tracking

Availability = (Total Scheduled Time - Downtime) / Total Scheduled Time * 100
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date
from decimal import Decimal
from typing import Optional

from backend.schemas.downtime import DowntimeEvent
from backend.schemas.shift import Shift


def calculate_availability(
    db: Session,
    product_id: int,
    shift_id: int,
    production_date: date
) -> tuple[Decimal, Decimal, Decimal, int]:
    """
    Calculate availability for a specific product/shift/date

    Returns: (availability_percentage, scheduled_hours, downtime_hours, event_count)
    """

    # Get shift scheduled hours
    shift = db.query(Shift).filter(Shift.shift_id == shift_id).first()
    if not shift or not shift.duration_hours:
        # Default to 8 hours if shift not found
        scheduled_hours = Decimal("8.0")
    else:
        scheduled_hours = Decimal(str(shift.duration_hours))

    # Sum all downtime for this product/shift/date
    total_downtime = db.query(
        func.coalesce(func.sum(DowntimeEvent.duration_hours), 0)
    ).filter(
        and_(
            DowntimeEvent.product_id == product_id,
            DowntimeEvent.shift_id == shift_id,
            DowntimeEvent.production_date == production_date
        )
    ).scalar()

    downtime_hours = Decimal(str(total_downtime))

    # Count downtime events
    event_count = db.query(func.count(DowntimeEvent.downtime_id)).filter(
        and_(
            DowntimeEvent.product_id == product_id,
            DowntimeEvent.shift_id == shift_id,
            DowntimeEvent.production_date == production_date
        )
    ).scalar()

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
    db: Session,
    machine_id: str,
    start_date: date,
    end_date: date
) -> Optional[Decimal]:
    """
    Calculate Mean Time Between Failures (MTBF)

    MTBF = Total Operating Time / Number of Failures
    """

    # Get all downtime events for machine
    failures = db.query(DowntimeEvent).filter(
        and_(
            DowntimeEvent.machine_id == machine_id,
            DowntimeEvent.production_date >= start_date,
            DowntimeEvent.production_date <= end_date,
            DowntimeEvent.downtime_category.in_(['Breakdown', 'Failure'])
        )
    ).all()

    if not failures:
        return None

    # Calculate total operating time (scheduled - downtime)
    total_downtime = sum(Decimal(str(f.duration_hours)) for f in failures)

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
    db: Session,
    machine_id: str,
    start_date: date,
    end_date: date
) -> Optional[Decimal]:
    """
    Calculate Mean Time To Repair (MTTR)

    MTTR = Total Repair Time / Number of Repairs
    """

    repairs = db.query(DowntimeEvent).filter(
        and_(
            DowntimeEvent.machine_id == machine_id,
            DowntimeEvent.production_date >= start_date,
            DowntimeEvent.production_date <= end_date,
            DowntimeEvent.downtime_category.in_(['Breakdown', 'Failure', 'Maintenance'])
        )
    ).all()

    if not repairs:
        return None

    total_repair_time = sum(Decimal(str(r.duration_hours)) for r in repairs)

    if len(repairs) > 0:
        mttr = total_repair_time / Decimal(str(len(repairs)))
        return mttr

    return None
