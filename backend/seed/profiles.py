"""Dataset size presets. `full` is what the VM and Render seed; `smoke` is a
short window so tests exercise the same code path in seconds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    days: int
    lines_per_client: int
    shifts_per_client: int
    employees_per_client: int
    work_orders_per_client: int


# 365 days x 4 clients x 2 lines x 2 shifts is the density the pivot layer
# needs for twelve genuine monthly buckets (spec sections 2 and 13).
FULL = Profile(
    name="full",
    days=365,
    lines_per_client=2,
    shifts_per_client=2,
    employees_per_client=8,
    work_orders_per_client=100,
)

SMOKE = Profile(
    name="smoke",
    days=14,
    lines_per_client=2,
    shifts_per_client=2,
    employees_per_client=4,
    work_orders_per_client=6,
)

PROFILES = {p.name: p for p in (FULL, SMOKE)}
