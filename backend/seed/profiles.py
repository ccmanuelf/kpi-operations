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
    # Defaulted, not required: test_generator.py (owned by a separate task)
    # builds ad-hoc Profile instances that predate this field, and this
    # module must stay purely additive to them.
    defect_rows_per_inspection: int = 2


# 365 days x 4 clients x 2 lines x 2 shifts is the density the pivot layer
# needs for twelve genuine monthly buckets (spec sections 2 and 13).
FULL = Profile(
    name="full",
    days=365,
    lines_per_client=2,
    shifts_per_client=2,
    employees_per_client=8,
    work_orders_per_client=100,
    defect_rows_per_inspection=2,
)

SMOKE = Profile(
    name="smoke",
    days=14,
    lines_per_client=2,
    shifts_per_client=2,
    employees_per_client=4,
    work_orders_per_client=6,
    defect_rows_per_inspection=1,
)

PROFILES = {p.name: p for p in (FULL, SMOKE)}
