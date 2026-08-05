"""
Labor-hours taxonomy (Cycle 3 of the reporting data-capture roadmap).

OT tiers are CAPTURED (normal/double/triple columns on ATTENDANCE_ENTRY),
never derived from LFT rules. labor_class: employee-level default with a
per-entry override (effective = override ?? default; NULL = unclassified).
Hour allocations: 8-category intra-day ledger with static billable/productive
metadata; paid_leave/medical are intra-day paid hours — the day-level
is_absent/AbsenceType mechanism stays authoritative for whole-day absence.

Third sibling of downtime_taxonomy.py / delay_taxonomy.py — same conventions.
Spec: docs/superpowers/specs/2026-08-05-labor-hours-accounting-design.md
"""

from enum import Enum


class LaborClassEnum(str, Enum):
    """Direct/indirect labor classification (NULL = unclassified)."""

    DIRECT = "direct"
    INDIRECT = "indirect"


class HourCategoryEnum(str, Enum):
    """Intra-day hour-allocation categories (complete ledger vocabulary)."""

    BILLED_PRODUCTION = "billed_production"
    UNBILLED_PRODUCTION = "unbilled_production"
    TRAINING = "training"
    MEETING = "meeting"
    IDLE_WAIT = "idle_wait"
    OTHER_NONPRODUCTIVE = "other_nonproductive"
    PAID_LEAVE = "paid_leave"
    MEDICAL = "medical"


BILLABLE_CATEGORIES: frozenset[str] = frozenset({HourCategoryEnum.BILLED_PRODUCTION.value})

PRODUCTIVE_CATEGORIES: frozenset[str] = frozenset(
    {HourCategoryEnum.BILLED_PRODUCTION.value, HourCategoryEnum.UNBILLED_PRODUCTION.value}
)

SELECTABLE_HOUR_CATEGORIES: list[str] = [c.value for c in HourCategoryEnum]
