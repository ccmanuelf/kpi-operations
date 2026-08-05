"""Labor-hours derivation functions (OT split validation, allocations, billing)
plus the `summarize_labor_hours` DB aggregation (Cycle 3 PR-B).

The per-entry helpers below are pure (no DB/FastAPI dependencies) and raise
ValueError with human-friendly messages on invariant violation.
`summarize_labor_hours` is the one DB-dependent function in this module: it
queries AttendanceEntry for a date window and reduces each entry through the
pure helpers above, so the derivation math stays in one place.
"""

from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.employee import Employee
from backend.orm.labor_taxonomy import BILLABLE_CATEGORIES, PRODUCTIVE_CATEGORIES


def validate_ot_split(
    normal: Decimal | None, double: Decimal | None, triple: Decimal | None, actual_hours: Decimal | None
) -> tuple[Decimal, Decimal, Decimal] | None:
    """Validate and normalize OT split, defaulting missing tiers to zero.

    Returns the normalized triple (normal, double, triple) when any tier is supplied.
    Returns None when all three tiers are None.

    Raises ValueError when:
    - Any tier is supplied but actual_hours is None
    - Sum of tiers != actual_hours
    """
    # All None -> return None (unsplit)
    if normal is None and double is None and triple is None:
        return None

    # Any tier supplied but no actual_hours -> error
    if actual_hours is None:
        raise ValueError("OT split requires actual_hours")

    # Default missing tiers to zero
    norm = normal if normal is not None else Decimal("0")
    doub = double if double is not None else Decimal("0")
    trip = triple if triple is not None else Decimal("0")

    # Verify sum matches actual_hours
    if norm + doub + trip != actual_hours:
        raise ValueError("OT split must sum to actual_hours")

    return (norm, doub, trip)


def validate_allocations(items: list[tuple[str, Decimal]], actual_hours: Decimal) -> None:
    """Validate allocation list for duplicates, positive hours, and total <= actual.

    Raises ValueError on:
    - Duplicate category
    - Hours <= 0
    - Allocations present but actual_hours is 0/unset ("allocations require
      actual_hours" — distinct from the sum-exceeds case below, which
      assumes a real actual_hours was actually available to exceed)
    - Sum of hours > actual_hours
    """
    categories_seen = set()
    total_hours = Decimal("0")

    for category, hours in items:
        # Check duplicate
        if category in categories_seen:
            raise ValueError(f"duplicate allocation category: {category}")
        categories_seen.add(category)

        # Check positive hours
        if hours <= 0:
            raise ValueError("allocation hours must be > 0")

        total_hours += hours

    # Allocations against a 0/unset actual_hours is a distinct, more specific
    # problem than "exceeds" — callers pass Decimal("0") as the not-provided
    # sentinel (see crud/attendance.py's `data.get("actual_hours") or Decimal("0")`).
    if items and actual_hours <= 0:
        raise ValueError("allocations require actual_hours")

    # Check total doesn't exceed actual
    if total_hours > actual_hours:
        raise ValueError("allocations exceed actual_hours")


def billed_hours(allocations: list[tuple[str, Decimal]]) -> Decimal:
    """Sum hours allocated to billable categories only."""
    return sum(
        (hours for category, hours in allocations if category in BILLABLE_CATEGORIES),
        Decimal("0"),
    )


def available_for_efficiency_hours(actual_hours: Decimal, allocations: list[tuple[str, Decimal]]) -> Decimal:
    """Return hours available for efficiency calculation.

    Subtracts non-productive allocated hours from actual_hours.
    Unallocated time defaults to productive-unbilled (counts as available).
    """
    nonproductive_allocated = sum(
        (hours for category, hours in allocations if category not in PRODUCTIVE_CATEGORIES),
        Decimal("0"),
    )
    return actual_hours - nonproductive_allocated


def effective_labor_class(override: str | None, employee_default: str | None) -> str | None:
    """Resolve labor class: override takes precedence over employee default.

    Returns None if both are None.
    """
    if override is not None:
        return override
    return employee_default


def summarize_labor_hours(db: Session, client_ids: Optional[Sequence[str]], start_date: date, end_date: date) -> dict:
    """Aggregate labor hours for entries with shift_date in [start_date, end_date].

    One query for entries in range (plus lazy="selectin" allocations, batched)
    and one IN-query for the involved employees' default labor_class -- no N+1.
    All returned values are Decimal; callers coerce to float/int at the boundary.

    See the class docstring in test_labor_hours.py::TestSummarizeLaborHours for
    the binding derivation math.
    """
    query = db.query(AttendanceEntry).filter(
        func.date(AttendanceEntry.shift_date) >= start_date,
        func.date(AttendanceEntry.shift_date) <= end_date,
    )
    if client_ids is not None:
        query = query.filter(AttendanceEntry.client_id.in_(client_ids))
    entries = query.all()

    employee_ids = {entry.employee_id for entry in entries}
    class_by_employee_id: dict[int, Optional[str]] = {}
    if employee_ids:
        rows = db.query(Employee.employee_id, Employee.labor_class).filter(Employee.employee_id.in_(employee_ids)).all()
        class_by_employee_id = {row.employee_id: row.labor_class for row in rows}

    totals = {
        "scheduled": Decimal("0"),
        "actual": Decimal("0"),
        "normal": Decimal("0"),
        "double": Decimal("0"),
        "triple": Decimal("0"),
        "billed": Decimal("0"),
        "available_for_efficiency": Decimal("0"),
    }
    by_labor_class = {
        bucket: {"actual": Decimal("0"), "billed": Decimal("0"), "available_for_efficiency": Decimal("0")}
        for bucket in ("direct", "indirect", "unclassified")
    }
    by_category: dict[str, Decimal] = {}
    entry_counts = {"total": 0, "with_split": 0, "with_allocations": 0}

    for entry in entries:
        entry_counts["total"] += 1

        scheduled = entry.scheduled_hours or Decimal("0")
        actual = entry.actual_hours or Decimal("0")
        totals["scheduled"] += scheduled
        totals["actual"] += actual

        if entry.normal_hours is not None or entry.double_hours is not None or entry.triple_hours is not None:
            entry_counts["with_split"] += 1
            totals["normal"] += entry.normal_hours or Decimal("0")
            totals["double"] += entry.double_hours or Decimal("0")
            totals["triple"] += entry.triple_hours or Decimal("0")

        alloc_tuples = [(alloc.category, alloc.hours) for alloc in entry.hour_allocations]
        if alloc_tuples:
            entry_counts["with_allocations"] += 1

        entry_billed = billed_hours(alloc_tuples)
        entry_available = available_for_efficiency_hours(actual, alloc_tuples)
        totals["billed"] += entry_billed
        totals["available_for_efficiency"] += entry_available

        for category, hours in alloc_tuples:
            by_category[category] = by_category.get(category, Decimal("0")) + hours

        eff_class = effective_labor_class(entry.labor_class_override, class_by_employee_id.get(entry.employee_id))
        bucket = by_labor_class[eff_class if eff_class in ("direct", "indirect") else "unclassified"]
        bucket["actual"] += actual
        bucket["billed"] += entry_billed
        bucket["available_for_efficiency"] += entry_available

    return {
        "totals": totals,
        "by_labor_class": by_labor_class,
        "by_category": by_category,
        "entry_counts": entry_counts,
    }
