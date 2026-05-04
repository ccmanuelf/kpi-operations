"""
Shared validators for date-range query params.

The platform exposes many endpoints with `start_date` / `end_date`
query parameters. Without a guard, swapping them returns an empty
result silently — a UX trap (Run-6 audit, finding R6-D-001). This
module centralises the validation so every endpoint can apply it
with one call.

Usage in a route:

    from backend.utils.date_range import validate_date_range

    def my_route(start_date: date, end_date: date, ...):
        validate_date_range(start_date, end_date)
        ...

The function raises `HTTPException(400)` with a clear message when
`start_date > end_date`. Equal dates are allowed (a one-day window).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException, status


def validate_date_range(
    start_date: Optional[date],
    end_date: Optional[date],
    *,
    start_field: str = "start_date",
    end_field: str = "end_date",
) -> None:
    """
    Reject `start_date > end_date` with a 400. No-op if either is None
    (callers may use one-sided ranges) or if start <= end.

    Field names are configurable so the error message names whichever
    parameter the route actually exposes (e.g. `received_after` /
    `received_before`).
    """
    if start_date is None or end_date is None:
        return
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid date range: {start_field}={start_date.isoformat()} "
                f"is after {end_field}={end_date.isoformat()}. Swap them or "
                "fix the upstream date picker."
            ),
        )
