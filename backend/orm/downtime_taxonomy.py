"""
Canonical downtime taxonomy (Cycle 1 of the reporting data-capture roadmap).

Two-level structure: root_cause_category (management attribution) over
downtime_reason (operational/NPT bucket). Single source of truth consumed by
schemas, ORM validators, the reference endpoint, availability calculations,
and the seeder. The Alembic backfill revision carries FROZEN COPIES of these
dicts — do not refactor it to import this module.

Spec: docs/superpowers/specs/2026-07-31-downtime-cause-taxonomy-design.md
"""

from enum import Enum


class DowntimeReasonEnum(str, Enum):
    """Operational downtime reasons (level 2 / NPT buckets)."""

    EQUIPMENT_FAILURE = "EQUIPMENT_FAILURE"
    MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE"
    SETUP_CHANGEOVER = "SETUP_CHANGEOVER"
    QUALITY_HOLD = "QUALITY_HOLD"
    MAINTENANCE = "MAINTENANCE"
    POWER_OUTAGE = "POWER_OUTAGE"
    OPERATOR_UNAVAILABLE = "OPERATOR_UNAVAILABLE"
    OTHER = "OTHER"


class DowntimeCategoryEnum(str, Enum):
    """Management attribution categories (level 1). 'uncategorized' is
    legacy-only: assigned by migration / accepted for CSV re-import back-compat,
    never offered in UI selects."""

    MACHINE = "machine"
    MATERIALS = "materials"
    SCHEDULING = "scheduling"
    ATTENDANCE = "attendance"
    OTHER = "other"
    UNCATEGORIZED = "uncategorized"


DEFAULT_CATEGORY_BY_REASON: dict[str, str] = {
    DowntimeReasonEnum.EQUIPMENT_FAILURE.value: DowntimeCategoryEnum.MACHINE.value,
    DowntimeReasonEnum.MAINTENANCE.value: DowntimeCategoryEnum.MACHINE.value,
    DowntimeReasonEnum.MATERIAL_SHORTAGE.value: DowntimeCategoryEnum.MATERIALS.value,
    DowntimeReasonEnum.SETUP_CHANGEOVER.value: DowntimeCategoryEnum.SCHEDULING.value,
    DowntimeReasonEnum.OPERATOR_UNAVAILABLE.value: DowntimeCategoryEnum.ATTENDANCE.value,
    DowntimeReasonEnum.QUALITY_HOLD.value: DowntimeCategoryEnum.OTHER.value,
    DowntimeReasonEnum.POWER_OUTAGE.value: DowntimeCategoryEnum.OTHER.value,
    DowntimeReasonEnum.OTHER.value: DowntimeCategoryEnum.OTHER.value,
}

PLANNED_DOWNTIME_REASONS: frozenset[str] = frozenset(
    {DowntimeReasonEnum.MAINTENANCE.value, DowntimeReasonEnum.SETUP_CHANGEOVER.value}
)

SELECTABLE_CATEGORIES: list[str] = [
    c.value for c in DowntimeCategoryEnum if c is not DowntimeCategoryEnum.UNCATEGORIZED
]
