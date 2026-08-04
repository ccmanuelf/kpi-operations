"""Downtime taxonomy backfill (Cycle 1) — data-only, no DDL.

Pass A normalizes downtime_reason to the canonical enum; Pass B backfills
root_cause_category to the 5-category management taxonomy (+ 'uncategorized').
Mapping dicts are FROZEN COPIES of backend/orm/downtime_taxonomy.py at the
time of writing — migrations never import app code.

Revision ID: 0002_downtime_taxonomy
Revises: 0001_baseline
Create Date: 2026-07-31
"""

from typing import Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_downtime_taxonomy"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_REASONS = {
    "EQUIPMENT_FAILURE",
    "MATERIAL_SHORTAGE",
    "SETUP_CHANGEOVER",
    "QUALITY_HOLD",
    "MAINTENANCE",
    "POWER_OUTAGE",
    "OPERATOR_UNAVAILABLE",
    "OTHER",
}
REASON_NORMALIZATION = {  # case-insensitive keys, applied before validity check
    "changeover": "SETUP_CHANGEOVER",
    "planned_maintenance": "MAINTENANCE",
}
DEFAULT_CATEGORY_BY_REASON = {
    "EQUIPMENT_FAILURE": "machine",
    "MAINTENANCE": "machine",
    "MATERIAL_SHORTAGE": "materials",
    "SETUP_CHANGEOVER": "scheduling",
    "OPERATOR_UNAVAILABLE": "attendance",
    "QUALITY_HOLD": "other",
    "POWER_OUTAGE": "other",
    "OTHER": "other",
}
CATEGORY_TEXT_MAP = {  # case-insensitive free-text -> category
    "breakdown": "machine",
    "failure": "machine",
    "equipment failure": "machine",
    "mechanical": "machine",
    "electrical": "machine",
    "maintenance": "machine",
    "planned maintenance": "machine",
    "machine": "machine",
    "material": "materials",
    "material shortage": "materials",
    "materials": "materials",
    "supply": "materials",
    "changeover": "scheduling",
    "setup": "scheduling",
    "scheduling": "scheduling",
    "operator": "attendance",
    "labor": "attendance",
    "absenteeism": "attendance",
    "attendance": "attendance",
    "other": "other",
    "uncategorized": "uncategorized",
}


def _append_note(existing: Optional[str], tag: str) -> str:
    return f"{existing} {tag}".strip() if existing else tag


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT downtime_entry_id, downtime_reason, root_cause_category, notes" " FROM DOWNTIME_ENTRY")
    ).fetchall()

    for entry_id, reason, category, notes in rows:
        new_notes = notes

        # Pass A — normalize reason (case-insensitive; spec §4)
        new_reason = reason
        upper_candidate = (reason or "").strip().upper()
        if reason in VALID_REASONS:
            pass
        elif upper_candidate in VALID_REASONS:
            new_reason = upper_candidate
        else:
            normalized = REASON_NORMALIZATION.get((reason or "").strip().lower())
            if normalized:
                new_reason = normalized
            else:
                new_reason = "OTHER"
                new_notes = _append_note(new_notes, f"[legacy reason: {reason}]")

        # Pass B — backfill category
        new_category = category
        if category is None or category.strip() == "":
            new_category = DEFAULT_CATEGORY_BY_REASON[new_reason]
        else:
            mapped = CATEGORY_TEXT_MAP.get(category.strip().lower())
            if mapped:
                new_category = mapped
            else:
                new_category = "uncategorized"
                new_notes = _append_note(new_notes, f"[legacy category: {category}]")

        if (new_reason, new_category, new_notes) != (reason, category, notes):
            conn.execute(
                sa.text(
                    "UPDATE DOWNTIME_ENTRY SET downtime_reason = :r,"
                    " root_cause_category = :c, notes = :n WHERE downtime_entry_id = :i"
                ),
                {"r": new_reason, "c": new_category, "n": new_notes, "i": entry_id},
            )


def downgrade() -> None:
    # Intentional no-op: the original free-text values are not recoverable
    # (preserved only inside notes where they were overwritten).
    pass
