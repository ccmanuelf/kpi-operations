# Downtime Cause Taxonomy (Cycle 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the controlled two-level downtime taxonomy — `root_cause_category` (5 management categories + legacy `uncategorized`) over the formalized `downtime_reason` enum — with auto-default mapping, data backfill, and consolidation of all four existing vocabularies, per spec `docs/superpowers/specs/2026-07-31-downtime-cause-taxonomy-design.md`.

**Architecture:** A single canonical taxonomy module (`backend/orm/downtime_taxonomy.py`, mirroring the `UserRole`-in-`orm/user.py` precedent) defines both enums, the default mapping, and the planned-reasons set. Everything else consumes it: Pydantic schemas (validation + auto-default), ORM validators (closes the seeder bypass), the Alembic backfill (frozen copies), availability calculations, the reference endpoint, and the seeder. The frontend mirrors the vocabulary in one constants module consumed by the grid and shift forms.

**Tech Stack:** FastAPI/Pydantic v2, SQLAlchemy 2.x mapped_column + `@validates`, Alembic (data-only revision), openpyxl, Vue 3 `<script setup>` + Pinia + AG Grid Community, vitest, Playwright, pytest.

## Global Constraints

- Branch: `feat/downtime-cause-taxonomy` (exists; spec committed at HEAD). Single PR.
- Physical DB column unchanged: `root_cause_category` stays `String(100)`, nullable — **no DDL**, data-only migration.
- `uncategorized` is legacy-only: accepted on input for back-compat, assigned by migration, **never offered in any UI select**.
- Auto-default: absent/NULL category → mapped from reason; an explicitly supplied valid category is never overwritten.
- Planned downtime = `downtime_reason IN (MAINTENANCE, SETUP_CHANGEOVER)`; unplanned = all other reasons.
- No permissive assertions (`status_code in [...]` forbidden — one expected code per test).
- All new UI strings via i18n, en + es, static keys only (template-literal keys evade the referenced-keys gate).
- `openapi_surface.json` must be regenerated in the task that changes route surface (Task 5) — the golden-master test in `backend/tests/test_bootstrap/` fails otherwise and its output explains the regen command; follow it.
- Backend tests: `pytest tests/` from `backend/`; coverage gate ≥75 %. Frontend: `npm run test`, `npm run lint` from `frontend/`.
- Migrations are frozen: the new revision copies mapping dicts rather than importing app modules.
- Commits end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Canonical taxonomy module + ORM validators

**Files:**
- Create: `backend/orm/downtime_taxonomy.py`
- Modify: `backend/schemas/downtime.py:13-23` (move `DowntimeReasonEnum` out, re-import for back-compat)
- Modify: `backend/orm/downtime_entry.py` (add `@validates`)
- Test: `backend/tests/test_orm/test_downtime_taxonomy.py` (create; if `backend/tests/test_orm/` does not exist, create it with an empty `__init__.py` matching sibling test dirs)

**Interfaces:**
- Produces (all later tasks import these): `DowntimeReasonEnum` (9 members: existing 7 + `OPERATOR_UNAVAILABLE = "OPERATOR_UNAVAILABLE"`), `DowntimeCategoryEnum` (`MACHINE="machine"`, `MATERIALS="materials"`, `SCHEDULING="scheduling"`, `ATTENDANCE="attendance"`, `OTHER="other"`, `UNCATEGORIZED="uncategorized"`), `DEFAULT_CATEGORY_BY_REASON: dict[str, str]`, `PLANNED_DOWNTIME_REASONS: frozenset[str]`, `SELECTABLE_CATEGORIES: list[str]` (the 5 real values, no `uncategorized`).
- Existing imports of `from backend.schemas.downtime import DowntimeReasonEnum` keep working.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_orm/test_downtime_taxonomy.py
import pytest
from backend.orm.downtime_taxonomy import (
    DEFAULT_CATEGORY_BY_REASON,
    PLANNED_DOWNTIME_REASONS,
    SELECTABLE_CATEGORIES,
    DowntimeCategoryEnum,
    DowntimeReasonEnum,
)
from backend.orm.downtime_entry import DowntimeEntry


def test_reason_enum_has_eight_members_including_operator_unavailable():
    assert {r.value for r in DowntimeReasonEnum} == {
        "EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "SETUP_CHANGEOVER",
        "QUALITY_HOLD", "MAINTENANCE", "POWER_OUTAGE", "OTHER",
        "OPERATOR_UNAVAILABLE",
    }
    assert len(list(DowntimeReasonEnum)) == 8


def test_category_enum_values():
    assert {c.value for c in DowntimeCategoryEnum} == {
        "machine", "materials", "scheduling", "attendance", "other", "uncategorized",
    }


def test_selectable_categories_exclude_uncategorized():
    assert "uncategorized" not in SELECTABLE_CATEGORIES
    assert len(SELECTABLE_CATEGORIES) == 5


def test_default_mapping_covers_every_reason_and_targets_valid_categories():
    assert set(DEFAULT_CATEGORY_BY_REASON) == {r.value for r in DowntimeReasonEnum}
    valid = {c.value for c in DowntimeCategoryEnum}
    assert set(DEFAULT_CATEGORY_BY_REASON.values()) <= valid
    assert "uncategorized" not in DEFAULT_CATEGORY_BY_REASON.values()


def test_default_mapping_exact_values():
    assert DEFAULT_CATEGORY_BY_REASON == {
        "EQUIPMENT_FAILURE": "machine",
        "MAINTENANCE": "machine",
        "MATERIAL_SHORTAGE": "materials",
        "SETUP_CHANGEOVER": "scheduling",
        "OPERATOR_UNAVAILABLE": "attendance",
        "QUALITY_HOLD": "other",
        "POWER_OUTAGE": "other",
        "OTHER": "other",
    }


def test_planned_reasons():
    assert PLANNED_DOWNTIME_REASONS == frozenset({"MAINTENANCE", "SETUP_CHANGEOVER"})


def test_orm_rejects_invalid_reason():
    with pytest.raises(ValueError, match="downtime_reason"):
        DowntimeEntry(
            downtime_entry_id="DT-T-0001", client_id="C1",
            shift_date=__import__("datetime").datetime(2026, 7, 1, 6, 0),
            downtime_reason="CHANGEOVER",  # the old seeder rogue value
            downtime_duration_minutes=30,
        )


def test_orm_rejects_invalid_category_but_allows_none():
    from datetime import datetime
    with pytest.raises(ValueError, match="root_cause_category"):
        DowntimeEntry(
            downtime_entry_id="DT-T-0002", client_id="C1",
            shift_date=datetime(2026, 7, 1, 6, 0),
            downtime_reason="OTHER", downtime_duration_minutes=30,
            root_cause_category="Breakdown",  # phantom legacy value
        )
    ok = DowntimeEntry(
        downtime_entry_id="DT-T-0003", client_id="C1",
        shift_date=datetime(2026, 7, 1, 6, 0),
        downtime_reason="OTHER", downtime_duration_minutes=30,
        root_cause_category=None,
    )
    assert ok.root_cause_category is None


def test_orm_accepts_uncategorized_and_all_valid_pairs():
    from datetime import datetime
    for i, (reason, category) in enumerate(
        list(DEFAULT_CATEGORY_BY_REASON.items()) + [("OTHER", "uncategorized")]
    ):
        e = DowntimeEntry(
            downtime_entry_id=f"DT-T-1{i:03d}", client_id="C1",
            shift_date=datetime(2026, 7, 1, 6, 0),
            downtime_reason=reason, downtime_duration_minutes=15,
            root_cause_category=category,
        )
        assert e.root_cause_category == category
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `pytest tests/test_orm/test_downtime_taxonomy.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.orm.downtime_taxonomy`

- [ ] **Step 3: Create the taxonomy module**

```python
# backend/orm/downtime_taxonomy.py
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
```

- [ ] **Step 4: Point `backend/schemas/downtime.py` at the canonical enum**

Delete the `class DowntimeReasonEnum(str, Enum):` block at `backend/schemas/downtime.py:13-23` (and the `from enum import Enum` import if now unused) and replace with:

```python
from backend.orm.downtime_taxonomy import DowntimeCategoryEnum, DowntimeReasonEnum  # noqa: F401  (re-exported)
```

Keep every existing usage in the file working (`DowntimeReasonEnum.EQUIPMENT_FAILURE` etc. in `from_legacy_csv` mapping are unchanged names). Run `rtk proxy grep -rn "from backend.schemas.downtime import" backend | grep -i reason` and confirm importers still resolve (they do — the name is re-exported).

- [ ] **Step 5: Add ORM validators**

In `backend/orm/downtime_entry.py`, add to imports:

```python
from sqlalchemy.orm import validates
```

and inside `class DowntimeEntry(Base)` (after the column definitions):

```python
    @validates("downtime_reason")
    def _validate_downtime_reason(self, key: str, value: str) -> str:
        from backend.orm.downtime_taxonomy import DowntimeReasonEnum

        valid = {r.value for r in DowntimeReasonEnum}
        if value not in valid:
            raise ValueError(f"downtime_reason must be one of {sorted(valid)}, got {value!r}")
        return value

    @validates("root_cause_category")
    def _validate_root_cause_category(self, key: str, value):
        if value is None:
            return value
        from backend.orm.downtime_taxonomy import DowntimeCategoryEnum

        valid = {c.value for c in DowntimeCategoryEnum}
        if value not in valid:
            raise ValueError(f"root_cause_category must be one of {sorted(valid)} or NULL, got {value!r}")
        return value
```

- [ ] **Step 6: Run the new tests + existing downtime/schema tests**

Run: `pytest tests/test_orm/test_downtime_taxonomy.py -v` → all PASS.
Run: `pytest tests/ -k "downtime" -q` → note failures. Existing tests that create `DowntimeEntry` rows with now-invalid values (e.g. fixtures using free-form categories) are **expected fallout — fix them in this task** by switching fixtures to valid enum values. Do not weaken the validators.

- [ ] **Step 7: Commit**

```bash
git add backend/orm/downtime_taxonomy.py backend/orm/downtime_entry.py backend/schemas/downtime.py backend/tests/
git commit -m "feat(downtime): canonical two-level taxonomy module + ORM validators

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Pydantic validation + auto-default on the API/CSV paths

**Files:**
- Modify: `backend/schemas/downtime.py` (`DowntimeEventCreate`, `DowntimeEventUpdate`)
- Modify: `backend/endpoints/csv_upload.py:80,111` (downtime column doc/type only if it names free-text)
- Test: `backend/tests/test_schemas/test_downtime_autodefault.py` (create; mirror sibling test-dir conventions)

**Interfaces:**
- Consumes: Task 1's `DowntimeCategoryEnum`, `DEFAULT_CATEGORY_BY_REASON`.
- Produces: `DowntimeEventCreate.root_cause_category: Optional[DowntimeCategoryEnum]` — **guaranteed non-None after validation** (auto-defaulted). `DowntimeEventUpdate.root_cause_category: Optional[DowntimeCategoryEnum]` — None means "no change" (NOT auto-defaulted).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_schemas/test_downtime_autodefault.py
import pytest
from pydantic import ValidationError
from backend.schemas.downtime import DowntimeEventCreate, DowntimeEventUpdate

BASE = {
    "client_id": "C1",
    "shift_date": "2026-07-01",
    "downtime_reason": "MATERIAL_SHORTAGE",
    "downtime_duration_minutes": 30,
}
# NOTE: align BASE with DowntimeEventCreate's actual required fields — read the
# schema first and extend BASE if it requires more (e.g. line_id); keep the
# taxonomy fields exactly as tested here.


def test_create_autodefaults_category_from_reason():
    m = DowntimeEventCreate(**BASE)
    assert m.root_cause_category is not None
    assert m.root_cause_category.value == "materials"


def test_create_explicit_category_is_preserved():
    m = DowntimeEventCreate(**BASE, root_cause_category="scheduling")
    assert m.root_cause_category.value == "scheduling"


def test_create_rejects_unknown_category_with_422_style_error():
    with pytest.raises(ValidationError):
        DowntimeEventCreate(**BASE, root_cause_category="Breakdown")


def test_create_accepts_uncategorized_for_csv_backcompat():
    m = DowntimeEventCreate(**BASE, root_cause_category="uncategorized")
    assert m.root_cause_category.value == "uncategorized"


def test_update_none_means_no_change_not_autodefault():
    u = DowntimeEventUpdate(downtime_reason="MAINTENANCE")
    assert u.root_cause_category is None
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_schemas/test_downtime_autodefault.py -v`
Expected: FAIL — auto-default assertion (`root_cause_category is None`) and/or type coercion.

- [ ] **Step 3: Implement**

In `backend/schemas/downtime.py`:
- Change `DowntimeEventCreate.root_cause_category` to `Optional[DowntimeCategoryEnum] = Field(None, description="Management attribution category; auto-defaulted from downtime_reason when omitted")`.
- Change `DowntimeEventUpdate.root_cause_category` (currently `Optional[str]` at line ~131) to `Optional[DowntimeCategoryEnum]`.
- Add to `DowntimeEventCreate`:

```python
from pydantic import model_validator
from backend.orm.downtime_taxonomy import DEFAULT_CATEGORY_BY_REASON

    @model_validator(mode="after")
    def _autodefault_root_cause_category(self) -> "DowntimeEventCreate":
        if self.root_cause_category is None and self.downtime_reason is not None:
            self.root_cause_category = DowntimeCategoryEnum(
                DEFAULT_CATEGORY_BY_REASON[self.downtime_reason.value]
            )
        return self
```

- In `backend/endpoints/csv_upload.py`, the downtime flow builds `DowntimeEventCreate` (or dict) from CSV rows — verify the `root_cause_category` value at line 80 flows through the schema so validation + auto-default apply. If the CSV path bypasses the Create schema, route it through the schema (construct `DowntimeEventCreate` from the row dict). Update the column docstring at line 111 from "(str, max 100)" to name the enum values.
- Check the downtime create/update service path (`get_downtime_events` sibling functions in the module imported by `backend/routes/downtime.py`): if the service copies schema fields onto the ORM model, no change; if it sets `root_cause_category` only when present in the payload, confirm the auto-defaulted value lands on the row.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_schemas/test_downtime_autodefault.py tests/ -k "downtime or csv" -q`
Expected: new tests PASS; fix any CSV characterization fallout by updating fixture rows to valid vocabulary (the golden masters for csv_upload were built pre-taxonomy — regenerate/adjust per their own harness README/comments, never by loosening assertions).

- [ ] **Step 5: Commit**

```bash
git add backend/schemas/downtime.py backend/endpoints/csv_upload.py backend/tests/
git commit -m "feat(downtime): enum validation + category auto-default on create/CSV paths

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Alembic data-only backfill migration

**Files:**
- Create: `backend/alembic/versions/0002_downtime_taxonomy_backfill.py`
- Test: `backend/tests/test_migrations/test_downtime_taxonomy_backfill.py` (create dir with `__init__.py` if absent)

**Interfaces:**
- Consumes: nothing from app code (frozen copies by design).
- Produces: revision `0002_downtime_taxonomy`, `down_revision="0001_baseline"`. After upgrade, every `DOWNTIME_ENTRY` row has a valid enum reason and a non-NULL valid category.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_migrations/test_downtime_taxonomy_backfill.py
"""Runs alembic upgrade against a temp SQLite DB seeded with legacy rows.

Follows the existing migration-test approach in backend/tests/ (see the
baseline-equality test in test_bootstrap/) for building an alembic Config
against a throwaway database URL.
"""
import sqlite3

import pytest
from alembic import command
from alembic.config import Config


LEGACY_ROWS = [
    # (id, reason, category, notes)
    ("DT-L-1", "CHANGEOVER", None, None),                    # rogue reason -> SETUP_CHANGEOVER, cat from mapping -> scheduling
    ("DT-L-2", "PLANNED_MAINTENANCE", "Maintenance", None),  # rogue reason -> MAINTENANCE; category text -> machine
    ("DT-L-3", "EQUIPMENT_FAILURE", "Breakdown", None),      # phantom category -> machine
    ("DT-L-4", "OTHER", "weird stuff", "keep me"),           # unknown -> uncategorized + notes preserved
    ("DT-L-5", "MATERIAL_SHORTAGE", None, None),             # NULL -> materials (mapping)
    ("DT-L-6", "QUALITY_HOLD", "other", None),               # already valid -> unchanged
    ("DT-L-7", "TOTALLY_UNKNOWN", None, None),               # unknown reason -> OTHER + notes tag, cat -> other
]


@pytest.fixture()
def migrated_db(tmp_path):
    db_path = tmp_path / "mig.db"
    url = f"sqlite:///{db_path}"
    cfg = Config("alembic.ini")  # run pytest from backend/
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0001_baseline")

    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO CLIENT (client_id, client_name) VALUES ('C1', 'Test')")
    # NOTE: adapt the CLIENT insert columns to the baseline's NOT NULL columns —
    # inspect the CREATE TABLE via `PRAGMA table_info(CLIENT)` in the fixture if needed.
    for rid, reason, category, notes in LEGACY_ROWS:
        conn.execute(
            "INSERT INTO DOWNTIME_ENTRY (downtime_entry_id, client_id, shift_date,"
            " downtime_reason, downtime_duration_minutes, root_cause_category, notes)"
            " VALUES (?, 'C1', '2026-07-01 06:00:00', ?, 30, ?, ?)",
            (rid, reason, category, notes),
        )
    conn.commit()
    conn.close()

    command.upgrade(cfg, "0002_downtime_taxonomy")
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


def _row(conn, rid):
    cur = conn.execute(
        "SELECT downtime_reason, root_cause_category, notes FROM DOWNTIME_ENTRY WHERE downtime_entry_id=?",
        (rid,),
    )
    return cur.fetchone()


def test_rogue_reasons_normalized(migrated_db):
    assert _row(migrated_db, "DT-L-1")[0] == "SETUP_CHANGEOVER"
    assert _row(migrated_db, "DT-L-2")[0] == "MAINTENANCE"


def test_unknown_reason_becomes_other_with_notes_tag(migrated_db):
    reason, _, notes = _row(migrated_db, "DT-L-7")
    assert reason == "OTHER"
    assert "[legacy reason: TOTALLY_UNKNOWN]" in (notes or "")


def test_phantom_and_text_categories_mapped(migrated_db):
    assert _row(migrated_db, "DT-L-3")[1] == "machine"
    assert _row(migrated_db, "DT-L-2")[1] == "machine"


def test_null_category_backfilled_from_normalized_reason(migrated_db):
    assert _row(migrated_db, "DT-L-1")[1] == "scheduling"
    assert _row(migrated_db, "DT-L-5")[1] == "materials"


def test_unknown_category_becomes_uncategorized_and_preserves_original_in_notes(migrated_db):
    _, category, notes = _row(migrated_db, "DT-L-4")
    assert category == "uncategorized"
    assert "[legacy category: weird stuff]" in notes
    assert "keep me" in notes


def test_already_valid_category_unchanged(migrated_db):
    assert _row(migrated_db, "DT-L-6")[1] == "other"


def test_no_nulls_remain(migrated_db):
    cur = migrated_db.execute(
        "SELECT COUNT(*) FROM DOWNTIME_ENTRY WHERE root_cause_category IS NULL"
    )
    assert cur.fetchone()[0] == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_migrations/test_downtime_taxonomy_backfill.py -v`
Expected: FAIL — revision `0002_downtime_taxonomy` unknown.

- [ ] **Step 3: Write the migration**

```python
# backend/alembic/versions/0002_downtime_taxonomy_backfill.py
"""Downtime taxonomy backfill (Cycle 1) — data-only, no DDL.

Pass A normalizes downtime_reason to the canonical enum; Pass B backfills
root_cause_category to the 5-category management taxonomy (+ 'uncategorized').
Mapping dicts are FROZEN COPIES of backend/orm/downtime_taxonomy.py at the
time of writing — migrations never import app code.

Revision ID: 0002_downtime_taxonomy
Revises: 0001_baseline
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_downtime_taxonomy"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

VALID_REASONS = {
    "EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "SETUP_CHANGEOVER", "QUALITY_HOLD",
    "MAINTENANCE", "POWER_OUTAGE", "OPERATOR_UNAVAILABLE", "OTHER",
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
    "breakdown": "machine", "failure": "machine", "equipment failure": "machine",
    "mechanical": "machine", "electrical": "machine", "maintenance": "machine",
    "planned maintenance": "machine", "machine": "machine",
    "material": "materials", "material shortage": "materials",
    "materials": "materials", "supply": "materials",
    "changeover": "scheduling", "setup": "scheduling", "scheduling": "scheduling",
    "operator": "attendance", "labor": "attendance",
    "absenteeism": "attendance", "attendance": "attendance",
    "other": "other",
    "uncategorized": "uncategorized",
}


def _append_note(existing, tag):
    return f"{existing} {tag}".strip() if existing else tag


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT downtime_entry_id, downtime_reason, root_cause_category, notes"
            " FROM DOWNTIME_ENTRY"
        )
    ).fetchall()

    for entry_id, reason, category, notes in rows:
        new_notes = notes

        # Pass A — normalize reason
        new_reason = reason
        if reason not in VALID_REASONS:
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_migrations/test_downtime_taxonomy_backfill.py -v` → all PASS.
Run: `pytest tests/test_bootstrap/ -q` → baseline-equality and `test_no_create_all_outside_alembic` still PASS (data-only revision must not disturb them).

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0002_downtime_taxonomy_backfill.py backend/tests/test_migrations/
git commit -m "feat(downtime): alembic data-only backfill — normalize reasons, backfill categories

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Availability planned-vs-unplanned fix

**Files:**
- Modify: `backend/calculations/availability.py:86,129`
- Test: existing availability test module (locate via `rtk proxy grep -rln "availability" backend/tests | head`); extend in place.

**Interfaces:**
- Consumes: Task 1's `PLANNED_DOWNTIME_REASONS`.
- Produces: no signature changes — both query helpers keep their names/returns; only the filter predicates change.

- [ ] **Step 1: Read both call sites with context**

Read `backend/calculations/availability.py` lines 60–150 fully. Site `:86` today filters `DowntimeEntry.root_cause_category.in_(["Breakdown", "Failure", "Equipment Failure"])` — its intent is **unplanned** downtime. Site `:129` filters `.in_(["Breakdown", "Failure", "Maintenance", "Equipment Failure"])` — its intent is **total (planned-inclusive)** downtime. Confirm intent from each function's docstring/usage before editing; if the read contradicts this mapping, STOP and report (NEEDS_CONTEXT) rather than guessing.

- [ ] **Step 2: Write the failing tests**

Add to the existing availability test module (adapt fixture helpers to that module's conventions — session fixture, client seeding):

```python
def test_unplanned_downtime_counts_only_unplanned_reasons(db_session):
    # three entries: EQUIPMENT_FAILURE (unplanned), MAINTENANCE (planned),
    # SETUP_CHANGEOVER (planned) — 60 min each
    _seed_downtime(db_session, reason="EQUIPMENT_FAILURE", minutes=60)
    _seed_downtime(db_session, reason="MAINTENANCE", minutes=60)
    _seed_downtime(db_session, reason="SETUP_CHANGEOVER", minutes=60)
    assert _unplanned_minutes(db_session) == 60          # call the :86 helper
    assert _total_incl_planned_minutes(db_session) == 180  # call the :129 helper
```

(Replace `_seed_downtime`, `_unplanned_minutes`, `_total_incl_planned_minutes` with the module's real helper/function names discovered in Step 1 — the assertion values are the requirement.)

- [ ] **Step 3: Run to verify failure**

Run: `pytest <availability test file> -v`
Expected: FAIL — phantom-category filters match nothing, so both return 0 (or planned/unplanned split is wrong).

- [ ] **Step 4: Implement**

At `:86` replace the category filter with:

```python
            ~DowntimeEntry.downtime_reason.in_(sorted(PLANNED_DOWNTIME_REASONS)),
```

At `:129` replace the filter with **no reason restriction** (total downtime includes planned and unplanned) — delete the `.in_(...)` predicate line entirely. Import at top: `from backend.orm.downtime_taxonomy import PLANNED_DOWNTIME_REASONS`. If Step 1's intent reading showed `:129` is planned-ONLY rather than planned-inclusive, use `DowntimeEntry.downtime_reason.in_(sorted(PLANNED_DOWNTIME_REASONS))` instead and adjust the test's expected value to 120 — the Step 1 reading governs, and record which branch was taken in your report.

- [ ] **Step 5: Run availability + calculation suites**

Run: `pytest tests/ -k "availability or calculation" -q`
Expected: new tests PASS; pre-existing expectations that assumed the dead filters (i.e. zero planned/unplanned split) updated to exact re-derived values — show the derivation in the test as a comment.

- [ ] **Step 6: Commit**

```bash
git add backend/calculations/availability.py backend/tests/
git commit -m "fix(availability): repoint planned-vs-unplanned at reason enum (phantom category filters were dead)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Reference endpoint rewrite + openapi surface regen

**Files:**
- Modify: `backend/routes/reference.py:103-119` (`list_downtime_reasons`)
- Modify: `backend/tests/test_bootstrap/openapi_surface.json` (regenerated, not hand-edited)
- Test: extend the existing reference-routes test module (locate via `rtk proxy grep -rln "downtime-reasons" backend/tests`)

**Interfaces:**
- Consumes: Task 1's enums/mapping.
- Produces: `GET /api/reference/downtime-reasons` returns
  `{"categories": [{"id": "machine", "label_key": "taxonomy.categories.machine"}, ...5 items, no uncategorized],
    "reasons": [{"id": "EQUIPMENT_FAILURE", "label_key": "taxonomy.reasons.equipmentFailure", "default_category": "machine"}, ...8 items]}`.
  Reason `label_key` values (camelCase of the enum value): `equipmentFailure`, `materialShortage`, `setupChangeover`, `qualityHold`, `maintenance`, `powerOutage`, `operatorUnavailable`, `other`. Task 6 binds these exact keys in i18n.

- [ ] **Step 1: Write the failing test**

```python
def test_downtime_reasons_serves_canonical_taxonomy(client_authed):
    resp = client_authed.get("/api/reference/downtime-reasons")
    assert resp.status_code == 200
    body = resp.json()
    assert [c["id"] for c in body["categories"]] == [
        "machine", "materials", "scheduling", "attendance", "other"
    ]
    reasons = {r["id"]: r for r in body["reasons"]}
    assert set(reasons) == {
        "EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "SETUP_CHANGEOVER", "QUALITY_HOLD",
        "MAINTENANCE", "POWER_OUTAGE", "OPERATOR_UNAVAILABLE", "OTHER",
    }
    assert reasons["OPERATOR_UNAVAILABLE"]["default_category"] == "attendance"
    assert reasons["EQUIPMENT_FAILURE"]["label_key"] == "taxonomy.reasons.equipmentFailure"
```

(Adapt `client_authed` to the module's existing authenticated-client fixture name.)

- [ ] **Step 2: Run to verify failure** — old hardcoded list returns a JSON array, so `body["categories"]` raises `TypeError`/KeyError.

- [ ] **Step 3: Implement**

Replace the body of `list_downtime_reasons` (keep route path, `response_model` becomes `dict`):

```python
@router.get("/downtime-reasons", response_model=dict)
def list_downtime_reasons(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Any:
    """Canonical downtime taxonomy: categories (level 1) and reasons (level 2) with default mapping."""
    from backend.orm.downtime_taxonomy import (
        DEFAULT_CATEGORY_BY_REASON,
        SELECTABLE_CATEGORIES,
        DowntimeReasonEnum,
    )

    def _camel(value: str) -> str:
        parts = value.lower().split("_")
        return parts[0] + "".join(p.title() for p in parts[1:])

    return {
        "categories": [
            {"id": c, "label_key": f"taxonomy.categories.{c}"} for c in SELECTABLE_CATEGORIES
        ],
        "reasons": [
            {
                "id": r.value,
                "label_key": f"taxonomy.reasons.{_camel(r.value)}",
                "default_category": DEFAULT_CATEGORY_BY_REASON[r.value],
            }
            for r in DowntimeReasonEnum
        ],
    }
```

- [ ] **Step 4: Regenerate the OpenAPI surface**

Run: `pytest tests/test_bootstrap/ -q` → the route-surface golden master fails and its assertion message states the regeneration command; run exactly that command, re-run the test, confirm PASS. Inspect the JSON diff (`rtk proxy git diff backend/tests/test_bootstrap/openapi_surface.json | head -40`) — only the downtime-reasons entry may change.

- [ ] **Step 5: Run the reference test module** — all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/reference.py backend/tests/
git commit -m "feat(downtime): reference endpoint serves canonical taxonomy (single source of truth)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Frontend consumer consolidation (store, MyShift dialog, shift forms) + i18n

**Files:**
- Create: `frontend/src/constants/downtimeTaxonomy.ts`
- Modify: `frontend/src/stores/productionDataStore.ts:39-41` (`DowntimeReason` interface), `:60,85,246` (state/fetch)
- Modify: `frontend/src/components/dialogs/ShiftDashboardDialogs.vue:74` (reason select binding)
- Modify: `frontend/src/composables/useShiftForms.ts:139-147` (delete hardcoded list + its `downtimeReasonToCode()` mapper; consume the constants module)
- Modify: `frontend/src/i18n/locales/en.json`, `es.json` (taxonomy.* keys)
- Audit (change only if it reads the old reference shape): `frontend/src/services/api/kpi.ts:320` — its `reasonsMap` is built from downtime entries, so it is expected to be untouched; confirm and note in the report.
- Test: `frontend/src/constants/__tests__/downtimeTaxonomy.spec.ts` (create), existing specs for the modified store/composable.

**Interfaces:**
- Consumes: Task 5's response shape and exact `label_key` values.
- Produces (Task 7 imports these): from `downtimeTaxonomy.ts` — `DOWNTIME_REASON_CODES: string[]` (8 ids, same order as backend enum), `DOWNTIME_CATEGORY_CODES: string[]` (5 selectable ids), `DEFAULT_CATEGORY_BY_REASON: Record<string, string>`, `reasonLabelKey(id: string): string`, `categoryLabelKey(id: string): string`.

- [ ] **Step 1: Write the failing constants test**

```typescript
// frontend/src/constants/__tests__/downtimeTaxonomy.spec.ts
import { describe, it, expect } from 'vitest'
import {
  DOWNTIME_REASON_CODES,
  DOWNTIME_CATEGORY_CODES,
  DEFAULT_CATEGORY_BY_REASON,
  reasonLabelKey,
  categoryLabelKey,
} from '../downtimeTaxonomy'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

const resolve = (obj: Record<string, unknown>, key: string) =>
  key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], obj)

describe('downtime taxonomy constants (mirror of backend/orm/downtime_taxonomy.py)', () => {
  it('has 8 reasons and 5 selectable categories (no uncategorized)', () => {
    expect(DOWNTIME_REASON_CODES).toHaveLength(8)
    expect(DOWNTIME_REASON_CODES).toContain('OPERATOR_UNAVAILABLE')
    expect(DOWNTIME_CATEGORY_CODES).toEqual([
      'machine', 'materials', 'scheduling', 'attendance', 'other',
    ])
  })

  it('maps every reason to a selectable category', () => {
    for (const r of DOWNTIME_REASON_CODES) {
      expect(DOWNTIME_CATEGORY_CODES).toContain(DEFAULT_CATEGORY_BY_REASON[r])
    }
    expect(DEFAULT_CATEGORY_BY_REASON['OPERATOR_UNAVAILABLE']).toBe('attendance')
    expect(DEFAULT_CATEGORY_BY_REASON['SETUP_CHANGEOVER']).toBe('scheduling')
  })

  it('every label key resolves in BOTH locales (incl. uncategorized render key)', () => {
    const keys = [
      ...DOWNTIME_REASON_CODES.map(reasonLabelKey),
      ...DOWNTIME_CATEGORY_CODES.map(categoryLabelKey),
      categoryLabelKey('uncategorized'),
    ]
    for (const k of keys) {
      expect(resolve(en, k), `en missing ${k}`).toBeTypeOf('string')
      expect(resolve(es, k), `es missing ${k}`).toBeTypeOf('string')
    }
  })
})
```

- [ ] **Step 2: Run to verify failure** — `npm run test -- downtimeTaxonomy` → module not found.

- [ ] **Step 3: Implement the constants module**

```typescript
// frontend/src/constants/downtimeTaxonomy.ts
// Mirror of backend/orm/downtime_taxonomy.py — keep the two in lockstep.
// The reference endpoint (/api/reference/downtime-reasons) serves the same
// data at runtime for store-driven consumers; this module exists for
// grid/editor code paths that must not depend on a fetch having completed.

export const DOWNTIME_REASON_CODES: string[] = [
  'EQUIPMENT_FAILURE',
  'MATERIAL_SHORTAGE',
  'SETUP_CHANGEOVER',
  'QUALITY_HOLD',
  'MAINTENANCE',
  'POWER_OUTAGE',
  'OPERATOR_UNAVAILABLE',
  'OTHER',
]

export const DOWNTIME_CATEGORY_CODES: string[] = [
  'machine',
  'materials',
  'scheduling',
  'attendance',
  'other',
]

export const DEFAULT_CATEGORY_BY_REASON: Record<string, string> = {
  EQUIPMENT_FAILURE: 'machine',
  MAINTENANCE: 'machine',
  MATERIAL_SHORTAGE: 'materials',
  SETUP_CHANGEOVER: 'scheduling',
  OPERATOR_UNAVAILABLE: 'attendance',
  QUALITY_HOLD: 'other',
  POWER_OUTAGE: 'other',
  OTHER: 'other',
}

const camel = (v: string): string => {
  const parts = v.toLowerCase().split('_')
  return parts[0] + parts.slice(1).map((p) => p[0].toUpperCase() + p.slice(1)).join('')
}

export const reasonLabelKey = (id: string): string => `taxonomy.reasons.${camel(id)}`
export const categoryLabelKey = (id: string): string => `taxonomy.categories.${id}`
```

- [ ] **Step 4: Add i18n keys (both locales)**

`en.json` — add a top-level `"taxonomy"` block (placement: alphabetical/sibling-consistent with the file's existing top-level ordering):

```json
"taxonomy": {
  "categories": {
    "machine": "Machine",
    "materials": "Materials",
    "scheduling": "Scheduling",
    "attendance": "Attendance",
    "other": "Other",
    "uncategorized": "Uncategorized"
  },
  "reasons": {
    "equipmentFailure": "Equipment failure",
    "materialShortage": "Material shortage",
    "setupChangeover": "Setup / changeover",
    "qualityHold": "Quality hold",
    "maintenance": "Scheduled maintenance",
    "powerOutage": "Power outage",
    "operatorUnavailable": "Operator unavailable",
    "other": "Other"
  }
}
```

`es.json` — same structure:

```json
"taxonomy": {
  "categories": {
    "machine": "Máquina",
    "materials": "Materiales",
    "scheduling": "Programación",
    "attendance": "Asistencia",
    "other": "Otro",
    "uncategorized": "Sin categorizar"
  },
  "reasons": {
    "equipmentFailure": "Falla de equipo",
    "materialShortage": "Falta de material",
    "setupChangeover": "Preparación / cambio de modelo",
    "qualityHold": "Retención de calidad",
    "maintenance": "Mantenimiento programado",
    "powerOutage": "Corte de energía",
    "operatorUnavailable": "Operador no disponible",
    "other": "Otro"
  }
}
```

- [ ] **Step 5: Consolidate the consumers**

- `productionDataStore.ts`: replace the loose `DowntimeReason` interface (`:39-41`) with
  ```typescript
  export interface DowntimeReason {
    id: string
    label_key: string
    default_category: string
  }
  export interface DowntimeCategory {
    id: string
    label_key: string
  }
  ```
  Add `downtimeCategories: DowntimeCategory[]` to state (init `[]`); at the fetch site (`:246`) assign `this.downtimeReasons = reasonsRes.data.reasons` and `this.downtimeCategories = reasonsRes.data.categories` (the endpoint now returns an object, not an array).
- `ShiftDashboardDialogs.vue:74`: the select over `downtimeReasons` binds `item-value="id"` and displays `$t(item.label_key)` (use the component's existing Vuetify select idiom — `:item-title` with a function or a computed mapping to `{title, value}` pairs).
- `useShiftForms.ts`: delete the `downtimeReasons` hardcoded array (`:139-147`) and the `downtimeReasonToCode()` mapper; export instead options built from the constants module:
  ```typescript
  import { DOWNTIME_REASON_CODES, reasonLabelKey } from '@/constants/downtimeTaxonomy'
  const downtimeReasons = DOWNTIME_REASON_CODES.map((id) => ({
    value: id,
    title: t(reasonLabelKey(id)),
  }))
  ```
  Update every consumer of the old string list / mapper found via `rtk proxy grep -rn "downtimeReasonToCode\|downtimeReasons" frontend/src --include="*.ts" --include="*.vue"` — the form submits enum ids directly now.
- `kpi.ts:320`: confirm `reasonsMap` derives from downtime entries (not the reference endpoint); if so, leave untouched and state that in the report.

- [ ] **Step 6: Run frontend suite + lint**

Run: `cd frontend && npm run test && npm run lint`
Expected: constants spec PASS; update the existing store/dialog/shift-form specs to the new shapes (exact new assertions, no broad mocks); `@intlify/vue-i18n/no-raw-text` and referenced-keys gates clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src backend/tests frontend/src/i18n
git commit -m "feat(downtime): consolidate all frontend downtime vocabularies onto the taxonomy

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Downtime grid — category select, auto-fill, uncategorized indicator

**Files:**
- Modify: `frontend/src/composables/useDowntimeGridData.ts` (reason codes source, `:174-178` mobile field config, `:294-300` category column, new-row defaults `:363-368`, cell-change handler)
- Modify: the downtime entry view that hosts the grid (locate via `rtk proxy grep -rln "useDowntimeGridData" frontend/src/views`) — add the "N uncategorized" chip
- Modify: `frontend/src/i18n/locales/en.json` / `es.json` — `downtime.uncategorizedCount` key
- Test: `frontend/src/composables/__tests__/useDowntimeGridData.spec.ts` (extend); `frontend/e2e/` Playwright guard (extend the existing downtime e2e spec if one exists, else add to the closest entry-screens spec file)

**Interfaces:**
- Consumes: Task 6's `DOWNTIME_REASON_CODES`, `DOWNTIME_CATEGORY_CODES`, `DEFAULT_CATEGORY_BY_REASON`, `reasonLabelKey`, `categoryLabelKey`.
- Produces: grid behavior only (no exported API change beyond the composable's existing return).

- [ ] **Step 1: Write the failing composable tests**

Extend `useDowntimeGridData.spec.ts` following its existing harness (the repo pattern: composables are unit-tested directly, not via `wrapper.vm`):

```typescript
it('offers exactly the 5 selectable categories in the category column editor', () => {
  const col = columnDefs.value.find((c) => c.field === 'root_cause_category')
  expect(col?.cellEditor).toBe('agSelectCellEditor')
  const params = typeof col?.cellEditorParams === 'function' ? col.cellEditorParams() : col?.cellEditorParams
  expect(params.values).toEqual(['machine', 'materials', 'scheduling', 'attendance', 'other'])
})

it('reason list includes OPERATOR_UNAVAILABLE sourced from the shared constants', () => {
  const col = columnDefs.value.find((c) => c.field === 'downtime_reason')
  const params = typeof col?.cellEditorParams === 'function' ? col.cellEditorParams() : col?.cellEditorParams
  expect(params.values).toContain('OPERATOR_UNAVAILABLE')
})

it('auto-fills default category on reason change unless user already overrode it', () => {
  const row = makeRow({ downtime_reason: 'OTHER', root_cause_category: 'other' })
  applyReasonChange(row, 'MATERIAL_SHORTAGE')       // the composable's handler
  expect(row.root_cause_category).toBe('materials')  // followed the mapping
  applyCategoryChange(row, 'scheduling')             // user override
  applyReasonChange(row, 'EQUIPMENT_FAILURE')
  expect(row.root_cause_category).toBe('scheduling') // override sticks
})

it('flags uncategorized cells with the highlight class', () => {
  const col = columnDefs.value.find((c) => c.field === 'root_cause_category')
  expect(col?.cellClass?.({ value: 'uncategorized' })).toContain('ag-cell-warning')
  expect(col?.cellClass?.({ value: 'machine' })).toBe('')
})
```

(`makeRow`/`applyReasonChange`/`applyCategoryChange` — use or add the composable-level pure helpers; the auto-fill logic must live in an exported pure function of the composable so it is testable, per the repo's `<script setup>` testing convention.)

- [ ] **Step 2: Run to verify failure** — `npm run test -- useDowntimeGridData`.

- [ ] **Step 3: Implement**

In `useDowntimeGridData.ts`:
- Replace the local `DOWNTIME_REASON_CODES` definition with an import from `@/constants/downtimeTaxonomy` (delete the local constant; keep the exported name available if other modules import it from here — re-export in that case). The reason `cellClass` map at `:253-260` gains `OPERATOR_UNAVAILABLE: 'ag-cell-warning'`.
- Category column (`:294-300`) becomes:

```typescript
    {
      headerName: t('grids.columns.rootCauseCategory'),
      field: 'root_cause_category',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: DOWNTIME_CATEGORY_CODES },
      valueFormatter: (params: { value?: string }) =>
        params.value ? t(categoryLabelKey(params.value)) : '',
      cellClass: (params: { value?: string }) =>
        params.value === 'uncategorized' ? 'ag-cell-warning ag-cell-bold' : '',
      width: 160,
    },
```

- Mobile field config (`:174-178`): `type: 'text'` → `type: 'select'` with the same 5 options (match how the reason field's mobile config declares its options).
- Auto-fill: export pure helpers and wire them into the grid's existing cell-value-changed pipeline:

```typescript
export interface DowntimeRowTaxonomyState {
  downtime_reason?: string
  root_cause_category?: string | null
  _categoryOverridden?: boolean
}

export function applyReasonChange(row: DowntimeRowTaxonomyState, newReason: string): void {
  row.downtime_reason = newReason
  if (!row._categoryOverridden) {
    row.root_cause_category = DEFAULT_CATEGORY_BY_REASON[newReason] ?? row.root_cause_category
  }
}

export function applyCategoryChange(row: DowntimeRowTaxonomyState, newCategory: string): void {
  row.root_cause_category = newCategory
  row._categoryOverridden = true
}
```

  In the grid's `onCellValueChanged` handler, route `downtime_reason` edits through `applyReasonChange` and `root_cause_category` edits through `applyCategoryChange` (then refresh the category cell so the auto-fill renders). `_categoryOverridden` joins the row-local underscore fields (`_hasChanges` precedent, `:33-34`) and is stripped before save the same way those are.
- New-row defaults (`:363-368`): `root_cause_category: null` stays (backend auto-default covers API creation), but when the user picks a reason on a new row the auto-fill gives immediate feedback.
- Uncategorized count in the hosting view:

```vue
<v-chip v-if="uncategorizedCount > 0" color="warning" size="small" class="ml-2">
  {{ t('downtime.uncategorizedCount', { count: uncategorizedCount }) }}
</v-chip>
```

with `const uncategorizedCount = computed(() => rowData.value.filter((r) => r.root_cause_category === 'uncategorized').length)` exposed from the composable. i18n: `en` `"uncategorizedCount": "{count} uncategorized"`, `es` `"uncategorizedCount": "{count} sin categorizar"` under a `"downtime"` block (create or extend, following the file's existing per-screen block conventions).

- [ ] **Step 4: Playwright guard**

Add to the downtime-relevant e2e spec (login as the standard e2e user; follow the suite's existing entry-screen test idiom):

```typescript
test('downtime grid: reason select auto-fills category, override sticks', async ({ page }) => {
  await gotoDowntimeEntry(page)              // suite's existing navigation helper
  await addNewDowntimeRow(page)              // suite's existing row helper, or dblclick pattern
  await setGridSelect(page, 'downtime_reason', 'MATERIAL_SHORTAGE')
  await expectGridCell(page, 'root_cause_category', /Materials|Materiales/)
  await setGridSelect(page, 'root_cause_category', 'scheduling')
  await setGridSelect(page, 'downtime_reason', 'EQUIPMENT_FAILURE')
  await expectGridCell(page, 'root_cause_category', /Scheduling|Programación/)
})
```

(Use the suite's real helpers for grid select interaction — grep `agSelectCellEditor` usage in `frontend/e2e/`; if no helper exists, drive via `page.getByRole` on the AG Grid cell + keyboard, matching how existing e2e tests edit grid cells.)

- [ ] **Step 5: Run** — `npm run test && npm run lint`; run the new Playwright test only: `npx playwright test <file> -g "auto-fills"` (chromium project is sufficient locally; CI runs the matrix).

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/e2e
git commit -m "feat(downtime): grid category select + auto-fill + uncategorized indicator

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Excel by-category rollup + listing category filter

**Files:**
- Modify: `backend/reports/excel_generator.py:322-…` (`_create_downtime_sheet`) and `:674` (`_fetch_downtime_data` — no change needed to shape; category already present)
- Modify: `backend/routes/downtime.py:62-90` (`list_downtime`) and its service (`get_downtime_events` in the module it's imported from)
- Test: existing excel-generator test module + existing downtime-routes test module (extend both)

**Interfaces:**
- Consumes: Task 1's `DowntimeCategoryEnum`; existing `_fetch_downtime_data` row dicts (`category` key).
- Produces: `GET /api/downtime?category=<enum>` filter; "Downtime Analysis" sheet gains a summary block (rows: one per category present, columns: Category / Events / Total Minutes / % of Total) inserted above the detail table.

- [ ] **Step 1: Write the failing tests**

Routes (extend the downtime routes test module, using its fixtures):

```python
def test_list_downtime_filters_by_category(client_authed, db_session):
    _seed(db_session, reason="EQUIPMENT_FAILURE", category="machine")
    _seed(db_session, reason="MATERIAL_SHORTAGE", category="materials")
    resp = client_authed.get("/api/downtime?category=machine")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["root_cause_category"] == "machine"


def test_list_downtime_rejects_unknown_category(client_authed):
    resp = client_authed.get("/api/downtime?category=Breakdown")
    assert resp.status_code == 422
```

Excel (extend the excel test module; it already builds workbooks against seeded sessions):

```python
def test_downtime_sheet_has_by_category_summary(excel_workbook_with_downtime):
    ws = excel_workbook_with_downtime["Downtime Analysis"]
    values = [[c.value for c in row] for row in ws.iter_rows()]
    flat = [v for row in values for v in row]
    assert "By Category" in flat            # block title
    assert "machine" in flat or "Machine" in flat
    # % column sums to ~100 for non-empty data
```

(Adapt fixture names; assert exact expected minutes/percentages from the fixture's seeded rows — no fuzzy assertions except the float-rounding tolerance idiom already used in that module.)

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

- `list_downtime`: add parameter `category: Optional[DowntimeCategoryEnum] = None` (import from `backend.orm.downtime_taxonomy`), pass `category=category.value if category else None` into `get_downtime_events`; in the service, add `if category: query = query.filter(DowntimeEntry.root_cause_category == category)` alongside the existing `downtime_reason` filter.
- `_create_downtime_sheet`: after the sheet title/header rows and before the detail table, insert the block (aggregate the already-fetched `data` list):

```python
        # By-category summary (Cycle 1 minimal rollup)
        from collections import defaultdict

        totals: dict[str, dict[str, float]] = defaultdict(lambda: {"events": 0, "minutes": 0.0})
        for row in data:
            cat = row["category"] if row["category"] != "—" else "uncategorized"
            totals[cat]["events"] += 1
            totals[cat]["minutes"] += row["duration"] * 60
        grand = sum(v["minutes"] for v in totals.values()) or 1.0

        ws.append([])
        ws.append(["By Category", "Events", "Total Minutes", "% of Total"])
        for cat in sorted(totals):
            ws.append([
                cat,
                totals[cat]["events"],
                round(totals[cat]["minutes"], 1),
                round(100.0 * totals[cat]["minutes"] / grand, 1),
            ])
        ws.append([])
```

  Match the sheet's existing header-styling idiom (read the function first — if headers get fonts/fills applied, style the "By Category" header row identically). Insert position: the block goes where the detail-table header currently starts; the detail table follows after the trailing blank row.
- Regenerate `openapi_surface.json` (the new query param changes the surface): same procedure as Task 5 Step 4.

- [ ] **Step 4: Run** — `pytest tests/ -k "excel or downtime" -q` + `pytest tests/test_bootstrap/ -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/reports/excel_generator.py backend/routes/downtime.py backend/services backend/tests
git commit -m "feat(downtime): Excel by-category rollup + category filter on listing

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Seeder — valid pairs with deterministic overrides

**Files:**
- Modify: `backend/scripts/_seed_operations.py:451-470`
- Test: extend the seeder test module if one exists (locate via `rtk proxy grep -rln "seed_sample_client\|_seed_operations" backend/tests`); otherwise verify via Step 3's run.

**Interfaces:**
- Consumes: Task 1's `DowntimeReasonEnum`, `DEFAULT_CATEGORY_BY_REASON`, `DowntimeCategoryEnum`.
- Produces: every seeded `DowntimeEntry` has a valid `(reason, category)` pair; ~10% deterministic overrides; zero `uncategorized`.

- [ ] **Step 1: Implement**

Replace the `downtime_reason=wrng.choice([...])` block (`:458-466`) with:

```python
                    reason = wrng.choice(
                        [
                            DowntimeReasonEnum.EQUIPMENT_FAILURE.value,
                            DowntimeReasonEnum.MATERIAL_SHORTAGE.value,
                            DowntimeReasonEnum.SETUP_CHANGEOVER.value,
                            DowntimeReasonEnum.MAINTENANCE.value,
                            DowntimeReasonEnum.QUALITY_HOLD.value,
                            DowntimeReasonEnum.OPERATOR_UNAVAILABLE.value,
                        ]
                    )
                    # ~10% explicit overrides demonstrate the operator-correction flow
                    # (downtime rows are created when seq % 5 == 1, so seq % 50 == 1 hits
                    # one in ten of them): the row is attributed to scheduling even though
                    # the reason's default says otherwise (e.g. a rushed changeover broke
                    # the machine). Skip when the default already IS scheduling, so every
                    # flagged row is a true override.
                    if (
                        seq % 50 == 1
                        and DEFAULT_CATEGORY_BY_REASON[reason] != DowntimeCategoryEnum.SCHEDULING.value
                    ):
                        category = DowntimeCategoryEnum.SCHEDULING.value
                    else:
                        category = DEFAULT_CATEGORY_BY_REASON[reason]
```

and pass both into the constructor: `downtime_reason=reason, root_cause_category=category,` (imports at the top of the file: `from backend.orm.downtime_taxonomy import DEFAULT_CATEGORY_BY_REASON, DowntimeCategoryEnum, DowntimeReasonEnum`).

- [ ] **Step 2: Determinism + validity check**

Run (from `backend/`, against a scratch SQLite DB per the seeder's own docs/flags — read `seed_sample_client.py`'s CLI to find the dev invocation):
`python -m backend.scripts.seed_sample_client --days 30 --reset` (dev DB), then verify:

```bash
rtk proxy python -c "
import sqlite3; c = sqlite3.connect('<dev db path from config>')
rows = c.execute('SELECT downtime_reason, root_cause_category, COUNT(*) FROM DOWNTIME_ENTRY GROUP BY 1,2').fetchall()
print(rows)
assert all(cat not in (None, 'uncategorized') for _, cat, _ in rows)
"
```

Expected: only valid enum pairs, no NULL/uncategorized, at least one overridden pair present.

- [ ] **Step 3: Run the full backend suite** — `pytest tests/ -q` → green (ORM validators now accept everything the seeder writes).

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/_seed_operations.py backend/tests
git commit -m "feat(downtime): seeder emits valid taxonomy pairs with deterministic overrides

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Living-doc re-grade + full-suite verification

**Files:**
- Modify: `docs/reporting/reporting-capabilities-and-gaps.md` (§2 note, §3 row, §4 Q2 grades)

**Interfaces:**
- Consumes: everything merged on the branch.
- Produces: docs consistent with shipped state; whole branch green.

- [ ] **Step 1: Re-grade the living doc**

In `docs/reporting/reporting-capabilities-and-gaps.md`:
- §3 row — replace
  `| Downtime cause taxonomy | **Active lane — Cycle 1** (§5) — small, high leverage for Q2 | Sequenced (§5) |`
  with
  `| Downtime cause taxonomy | **Active lane — Cycle 1** (§5) — small, high leverage for Q2 | **DONE — Cycle 1 PR**: two-level (category, reason) taxonomy, auto-default, backfill migration, availability planned/unplanned fixed |`
- §4 Q2 table — replace the two rows:
  `| Cause taxonomy | **partial** | \`root_cause_category\` exists but free-form; no controlled vocabulary matching the five management categories |`
  → `| Cause taxonomy | **have** | controlled 5-category vocabulary over \`root_cause_category\` + 8-reason enum, auto-default mapping (Cycle 1) |`
  `| NPT categorization | **partial** | same field; industry NPT buckets would ride on the same taxonomy |`
  → `| NPT categorization | **have** | reason enum is the NPT level; (category, reason) pair queryable (Cycle 1) |`
  (Match the exact current row text by reading the file first — the wording above reflects the pre-PR state and must be matched verbatim for the edit.)
- §5 Cycle 1 entry: append ` **[DONE — this PR]**` to the Cycle 1 line.

- [ ] **Step 2: Full verification**

From `backend/`: `pytest tests/ -q` → green, coverage ≥75 %.
From `frontend/`: `npm run test && npm run lint && npm run typecheck` → green.
Repo-wide stale-vocabulary sweep:

```bash
rtk proxy grep -rn "Equipment Breakdown\|downtimeReasonToCode\|PLANNED_MAINTENANCE\|'CHANGEOVER'\|\"CHANGEOVER\"" backend frontend/src --include="*.py" --include="*.ts" --include="*.vue" | grep -v alembic/versions | grep -v test
```

Expected: no hits outside the frozen migration and historical docs (the migration's normalization dict legitimately contains the legacy strings).

- [ ] **Step 3: Commit**

```bash
git add docs/reporting/reporting-capabilities-and-gaps.md
git commit -m "docs(reporting): re-grade Q2 taxonomy concepts to 'have' (Cycle 1 shipped)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Cross-review and PR (controller-level)

**Files:** none.

**Interfaces:** branch `feat/downtime-cause-taxonomy` complete and green locally.

- [ ] **Step 1:** `git diff --stat main...HEAD` — files span `backend/` (taxonomy, schemas, orm, alembic, calculations, routes, reports, scripts, tests), `frontend/src` (+e2e), `docs/` (spec + living doc), and `backend/tests/test_bootstrap/openapi_surface.json`. Nothing else.
- [ ] **Step 2:** Run `/cross-review` (main session) for the final HEAD.
- [ ] **Step 3:** Push; `gh pr create` titled `feat(downtime): cause taxonomy — controlled 2-level vocabulary, backfill, availability fix (Cycle 1)` with a summary listing: taxonomy module + ORM validators; auto-default; 2-pass backfill migration; availability planned/unplanned bug fix; reference-endpoint single source; 4-vocabulary consolidation; grid selects + auto-fill + uncategorized indicator; Excel by-category rollup + category filter; seeder; Q2 re-grade. Body ends with the standard generated-with footer.
- [ ] **Step 4:** `gh pr checks --watch` → 7/7 green → report PR URL. Merge is **user-confirmed only**. Post-merge (after user confirms): deploy Render (auto) + VM (pull, build backend+frontend, `init-data-root.sh` re-chown if backend rebuilt, `up -d` — migration runs on startup), VM re-seed `--reset` + `--client SAMPLE_REF` run, then live-verify per spec §10.
