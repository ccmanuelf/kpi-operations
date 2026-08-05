"""Pure labor-hours derivation functions (OT split validation, allocations, billing).

No DB or FastAPI dependencies. Raises ValueError with human-friendly messages
on invariant violation.
"""

from decimal import Decimal

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
