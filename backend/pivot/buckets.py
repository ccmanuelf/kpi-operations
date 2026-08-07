"""Time-bucket assignment for the pivot engine (Cycle 4).

Pure Python on purpose: the engine's SQL aggregates per *day* (the portable
`func.date(...)` idiom) and this module rolls days up into buckets, so
week/quarter math never touches dialect-specific SQL.
"""

from datetime import date, timedelta

VALID_BUCKETS: tuple[str, ...] = ("week", "month", "quarter", "year")


def bucket_start(d: date, bucket: str) -> date:
    """Return the first day of the bucket containing d. ISO week, Monday start."""
    if bucket == "week":
        return d - timedelta(days=d.weekday())
    if bucket == "month":
        return d.replace(day=1)
    if bucket == "quarter":
        return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)
    if bucket == "year":
        return date(d.year, 1, 1)
    raise ValueError(f"bucket must be one of {VALID_BUCKETS}, got {bucket!r}")
