# Labor-Hours Capture (Cycle 3 PR-A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Cycle 3 capture layer — OT 3-way split, labor-class default+override, and the 8-category hour-allocation ledger — end-to-end (model → migration → API invariants → UI → seeders) per spec `docs/superpowers/specs/2026-08-05-labor-hours-accounting-design.md` §3–§5, §7.

**Architecture:** A labor taxonomy module (`backend/orm/labor_taxonomy.py`, third sibling of the downtime/delay modules) + a pure derivations module (`backend/calculations/labor_hours.py`) feed the ORM validators, the attendance API invariants, response enrichment, UI, and seeders. `ATTENDANCE_HOUR_ALLOCATION` is a replace-on-write child of `ATTENDANCE_ENTRY`. PR-B (metrics) builds on the derivations module later — its function signatures are contractual.

**Tech Stack:** FastAPI/Pydantic v2, SQLAlchemy 2.x, Alembic (DDL revision `0004`), Vue 3 + Vuetify + AG Grid, vitest, Playwright, pytest.

## Global Constraints

- Branch: `feat/labor-hours-capture` (exists; spec committed at HEAD). This plan is PR-A ONLY — no metrics endpoint, no efficiency variant, no Excel rows, no living-doc re-grade (all PR-B).
- Split invariant (spec §3.1): all three of normal/double/triple NULL = unsplit; if ANY supplied, absent ones default to 0 and the sum must equal `actual_hours` exactly → **422**; split with no `actual_hours` → **422**.
- Allocation invariants (spec §3.4/§4): `Σ allocations ≤ actual_hours` → **422**; duplicate categories in one payload → **422**; `hours > 0`; supplied list replaces wholesale; empty list clears; omitted = no change.
- Derived (computed, never stored): `billed_hours = Σ over BILLABLE_CATEGORIES`; `available_for_efficiency_hours = actual_hours − Σ over (allocated ∖ PRODUCTIVE_CATEGORIES)`; `effective_labor_class = labor_class_override ?? employee.labor_class` (may be None).
- Absence boundary: `paid_leave`/`medical` = intra-day paid hours; day-level `is_absent`/`AbsenceType` untouched, no reconciliation.
- Authorization unchanged — fields ride host-surface guards (attendance = its current contributor-tier guards; employee admin = `get_current_active_supervisor` as today).
- No new UI text without i18n en+es (static keys, `labor.*` block); referenced-keys gate green; NO low-contrast placeholders — absent values render EMPTY cells (standing a11y rule).
- Seeder coverage counters must be independent of selection-pattern moduli (gcd lesson); exact-set assertions for all 8 categories across the sample dataset.
- pytest FOREGROUND from `backend/` with the Bash timeout PARAMETER set to 600000; frontend commands FOREGROUND from `frontend/` likewise; no permissive assertions; derivation comments on expected values; mypy gate blocking.
- Commits end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Labor taxonomy + ORM columns/validators + allocation model

**Files:**
- Create: `backend/orm/labor_taxonomy.py`
- Create: `backend/orm/attendance_hour_allocation.py`
- Modify: `backend/orm/attendance_entry.py` (4 columns + validator + relationship), `backend/orm/employee.py` (1 column + validator), `backend/orm/__init__.py` (export the new model — match how other models are exported)
- Test: `backend/tests/test_orm/test_labor_taxonomy.py` (create)

**Interfaces:**
- Produces (contractual): `LaborClassEnum` (`DIRECT="direct"`, `INDIRECT="indirect"`); `HourCategoryEnum` (8 members, values: `billed_production`, `unbilled_production`, `training`, `meeting`, `idle_wait`, `other_nonproductive`, `paid_leave`, `medical`); `BILLABLE_CATEGORIES: frozenset[str]` = {billed_production}; `PRODUCTIVE_CATEGORIES: frozenset[str]` = {billed_production, unbilled_production}; `SELECTABLE_HOUR_CATEGORIES: list[str]` (8, declaration order).
- `AttendanceEntry` gains `normal_hours`/`double_hours`/`triple_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))`, `labor_class_override: Mapped[Optional[str]] = mapped_column(String(10))`, and `hour_allocations: Mapped[list["AttendanceHourAllocation"]] = relationship(cascade="all, delete-orphan")`.
- `Employee` gains `labor_class: Mapped[Optional[str]] = mapped_column(String(10))`.
- New model `AttendanceHourAllocation` (`__tablename__ = "ATTENDANCE_HOUR_ALLOCATION"`): `allocation_id` Integer PK autoincrement, `attendance_entry_id` String(50) FK→`ATTENDANCE_ENTRY.attendance_entry_id` (ondelete CASCADE, index=True), `category` String(30) with `@validates` (no None — required), `hours` Numeric(5,2); `UniqueConstraint("attendance_entry_id", "category")`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_orm/test_labor_taxonomy.py
from decimal import Decimal
from datetime import datetime

import pytest

from backend.orm.labor_taxonomy import (
    BILLABLE_CATEGORIES,
    PRODUCTIVE_CATEGORIES,
    SELECTABLE_HOUR_CATEGORIES,
    HourCategoryEnum,
    LaborClassEnum,
)
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.attendance_hour_allocation import AttendanceHourAllocation
from backend.orm.employee import Employee


def test_labor_class_enum():
    assert {c.value for c in LaborClassEnum} == {"direct", "indirect"}


def test_hour_category_enum_exact_eight():
    assert [c.value for c in HourCategoryEnum] == [
        "billed_production",
        "unbilled_production",
        "training",
        "meeting",
        "idle_wait",
        "other_nonproductive",
        "paid_leave",
        "medical",
    ]
    assert SELECTABLE_HOUR_CATEGORIES == [c.value for c in HourCategoryEnum]


def test_metadata_sets():
    assert BILLABLE_CATEGORIES == frozenset({"billed_production"})
    assert PRODUCTIVE_CATEGORIES == frozenset({"billed_production", "unbilled_production"})
    assert BILLABLE_CATEGORIES <= PRODUCTIVE_CATEGORIES
    assert PRODUCTIVE_CATEGORIES <= {c.value for c in HourCategoryEnum}


def _entry(**kwargs):
    return AttendanceEntry(
        attendance_entry_id=kwargs.pop("attendance_entry_id", "ATT-LAB-T1"),
        client_id="C1",
        employee_id=1,
        shift_date=datetime(2026, 8, 1, 6, 0),
        scheduled_hours=Decimal("8.00"),
        **kwargs,
    )
    # Align with AttendanceEntry's actual NOT-NULL constructor fields — read the
    # model first and extend if instantiation needs more; keep labor kwargs as tested.


def test_attendance_validators_reject_invalid_override_allow_none():
    with pytest.raises(ValueError, match="labor_class_override"):
        _entry(labor_class_override="contractor")
    assert _entry(attendance_entry_id="ATT-LAB-T2", labor_class_override=None).labor_class_override is None
    assert _entry(attendance_entry_id="ATT-LAB-T3", labor_class_override="indirect").labor_class_override == "indirect"


def test_employee_validator_rejects_invalid_class():
    with pytest.raises(ValueError, match="labor_class"):
        Employee(employee_id=999999, client_id_assigned="C1", labor_class="temp")
    # Align Employee constructor with its NOT-NULL fields (read model); the
    # labor_class kwarg is the assertion target.


def test_allocation_category_validator():
    with pytest.raises(ValueError, match="category"):
        AttendanceHourAllocation(attendance_entry_id="ATT-LAB-T1", category="lunch", hours=Decimal("1.00"))
    ok = AttendanceHourAllocation(attendance_entry_id="ATT-LAB-T1", category="training", hours=Decimal("1.50"))
    assert ok.category == "training"
```

- [ ] **Step 2: Run to verify failure** — `pytest tests/test_orm/test_labor_taxonomy.py -v --no-cov` → ModuleNotFoundError.

- [ ] **Step 3: Create the taxonomy module**

```python
# backend/orm/labor_taxonomy.py
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
```

- [ ] **Step 4: Create the allocation model**

```python
# backend/orm/attendance_hour_allocation.py
"""ATTENDANCE_HOUR_ALLOCATION — intra-day hour ledger child of ATTENDANCE_ENTRY.

Replace-on-write: the API accepts an entry's full allocation list and swaps it
wholesale (no per-row PATCH surface). Cycle 3 PR-A.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates

from backend.database import Base


class AttendanceHourAllocation(Base):
    __tablename__ = "ATTENDANCE_HOUR_ALLOCATION"
    __table_args__ = (
        UniqueConstraint("attendance_entry_id", "category", name="uq_attendance_allocation_category"),
        {"extend_existing": True},
    )

    allocation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attendance_entry_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ATTENDANCE_ENTRY.attendance_entry_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    @validates("category")
    def _validate_category(self, key: str, value: str) -> str:
        from backend.orm.labor_taxonomy import HourCategoryEnum

        valid = {c.value for c in HourCategoryEnum}
        if value not in valid:
            raise ValueError(f"category must be one of {sorted(valid)}, got {value!r}")
        return value
```

- [ ] **Step 5: Wire columns + validators + relationship**

`attendance_entry.py` (after the existing hour columns; import `Numeric` if absent, `relationship`, `validates`):

```python
    # Labor-hours capture (Cycle 3 PR-A) — OT split (all NULL = unsplit) + class override
    normal_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    double_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    triple_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    labor_class_override: Mapped[Optional[str]] = mapped_column(String(10))

    hour_allocations: Mapped[list["AttendanceHourAllocation"]] = relationship(
        "AttendanceHourAllocation", cascade="all, delete-orphan", lazy="selectin"
    )

    @validates("labor_class_override")
    def _validate_labor_class_override(self, key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        from backend.orm.labor_taxonomy import LaborClassEnum

        valid = {c.value for c in LaborClassEnum}
        if value not in valid:
            raise ValueError(f"labor_class_override must be one of {sorted(valid)} or NULL, got {value!r}")
        return value
```

(Import `AttendanceHourAllocation` under `TYPE_CHECKING` or via string reference per the file's existing relationship style — check how other relationships in the codebase reference child models.)

`employee.py` (near `department`):

```python
    # direct/indirect labor classification (Cycle 3 PR-A) — NULL = unclassified
    labor_class: Mapped[Optional[str]] = mapped_column(String(10))

    @validates("labor_class")
    def _validate_labor_class(self, key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        from backend.orm.labor_taxonomy import LaborClassEnum

        valid = {c.value for c in LaborClassEnum}
        if value not in valid:
            raise ValueError(f"labor_class must be one of {sorted(valid)} or NULL, got {value!r}")
        return value
```

Export `AttendanceHourAllocation` from `backend/orm/__init__.py` following its existing export list style.

- [ ] **Step 6: Run** — new tests PASS; then `pytest tests/ -k "attendance or employee" -q --no-cov` — fallout expected ONLY as the missing-column class on the un-migrated template (same sequenced pattern as Cycle 2 Task 1: those failures are Task 2's to clear; anything else is yours). Record the exact failing set in your report.

- [ ] **Step 7: Commit** — `feat(labor): taxonomy module + OT split/override/labor_class columns + allocation model` + trailer.

---

### Task 2: Migration 0004 (DDL)

**Files:**
- Create: `backend/alembic/versions/0004_labor_hours_columns.py`
- Test: `backend/tests/test_migrations/test_labor_hours_columns.py` (create)
- Modify: `backend/tests/test_alembic/test_alembic_setup.py` (two CLI head assertions `0003_justified_delay` → `0004_labor_hours` — the established fallout class)

**Interfaces:**
- Produces: revision `0004_labor_hours`, `down_revision="0003_justified_delay"`. Clears Task 1's sequenced missing-column failures.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_migrations/test_labor_hours_columns.py
"""Cycle 3 PR-A DDL — same throwaway-SQLite alembic harness as its siblings."""
import sqlite3

import pytest
from alembic import command
from alembic.config import Config

ATT_COLUMNS = {"normal_hours", "double_hours", "triple_hours", "labor_class_override"}


@pytest.fixture()
def upgraded_db(tmp_path):
    db_path = tmp_path / "mig4.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    conn = sqlite3.connect(db_path)
    yield conn, cfg, db_path
    conn.close()


def _cols(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_upgrade_adds_attendance_columns(upgraded_db):
    conn, _, _ = upgraded_db
    assert ATT_COLUMNS <= _cols(conn, "ATTENDANCE_ENTRY")


def test_upgrade_adds_employee_column(upgraded_db):
    conn, _, _ = upgraded_db
    assert "labor_class" in _cols(conn, "EMPLOYEE")


def test_upgrade_creates_allocation_table_with_unique(upgraded_db):
    conn, _, _ = upgraded_db
    assert _cols(conn, "ATTENDANCE_HOUR_ALLOCATION") == {
        "allocation_id",
        "attendance_entry_id",
        "category",
        "hours",
    }
    indexes = conn.execute("PRAGMA index_list(ATTENDANCE_HOUR_ALLOCATION)").fetchall()
    assert any(row[2] == 1 for row in indexes), "expected a UNIQUE index on (entry, category)"


def test_head_is_0004(upgraded_db):
    conn, _, _ = upgraded_db
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0004_labor_hours"


def test_downgrade_removes_everything(upgraded_db):
    conn, cfg, db_path = upgraded_db
    conn.close()
    command.downgrade(cfg, "0003_justified_delay")
    conn2 = sqlite3.connect(db_path)
    try:
        assert not (ATT_COLUMNS & _cols(conn2, "ATTENDANCE_ENTRY"))
        assert "labor_class" not in _cols(conn2, "EMPLOYEE")
        tables = {r[0] for r in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "ATTENDANCE_HOUR_ALLOCATION" not in tables
    finally:
        conn2.close()
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Write the migration**

```python
# backend/alembic/versions/0004_labor_hours_columns.py
"""Labor-hours capture columns + allocation table (Cycle 3 PR-A).

Revision ID: 0004_labor_hours
Revises: 0003_justified_delay
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_labor_hours"
down_revision: Union[str, None] = "0003_justified_delay"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ATTENDANCE_ENTRY", sa.Column("normal_hours", sa.Numeric(5, 2), nullable=True))
    op.add_column("ATTENDANCE_ENTRY", sa.Column("double_hours", sa.Numeric(5, 2), nullable=True))
    op.add_column("ATTENDANCE_ENTRY", sa.Column("triple_hours", sa.Numeric(5, 2), nullable=True))
    op.add_column("ATTENDANCE_ENTRY", sa.Column("labor_class_override", sa.String(length=10), nullable=True))
    op.add_column("EMPLOYEE", sa.Column("labor_class", sa.String(length=10), nullable=True))
    op.create_table(
        "ATTENDANCE_HOUR_ALLOCATION",
        sa.Column("allocation_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attendance_entry_id", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("hours", sa.Numeric(5, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["attendance_entry_id"], ["ATTENDANCE_ENTRY.attendance_entry_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("allocation_id"),
        sa.UniqueConstraint("attendance_entry_id", "category", name="uq_attendance_allocation_category"),
    )
    op.create_index(
        op.f("ix_ATTENDANCE_HOUR_ALLOCATION_attendance_entry_id"),
        "ATTENDANCE_HOUR_ALLOCATION",
        ["attendance_entry_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ATTENDANCE_HOUR_ALLOCATION_attendance_entry_id"), table_name="ATTENDANCE_HOUR_ALLOCATION"
    )
    op.drop_table("ATTENDANCE_HOUR_ALLOCATION")
    op.drop_column("EMPLOYEE", "labor_class")
    op.drop_column("ATTENDANCE_ENTRY", "labor_class_override")
    op.drop_column("ATTENDANCE_ENTRY", "triple_hours")
    op.drop_column("ATTENDANCE_ENTRY", "double_hours")
    op.drop_column("ATTENDANCE_ENTRY", "normal_hours")
```

CRITICAL parity check: the baseline-equality guard compares `upgrade head` against `Base.metadata` — if the guard flags drift (constraint/index naming, types), reconcile the MIGRATION to the metadata (adjust names/shapes) rather than the model, and record what changed.

- [ ] **Step 4: Run** — migration tests PASS; `pytest tests/ -k "attendance or employee" -q --no-cov` fully green (Task 1's sequenced failures cleared); `pytest tests/test_bootstrap/ tests/test_alembic/ tests/test_mariadb_portability.py -q --no-cov` green (with the two head assertions updated).

- [ ] **Step 5: Commit** — `feat(labor): alembic 0004 — labor-hours columns + ATTENDANCE_HOUR_ALLOCATION table` + trailer.

---

### Task 3: Pure derivations module

**Files:**
- Create: `backend/calculations/labor_hours.py`
- Test: `backend/tests/test_calculations/test_labor_hours.py` (create)

**Interfaces:**
- Produces (contractual — PR-B builds on these):
  - `validate_ot_split(normal, double, triple, actual_hours) -> tuple[Decimal, Decimal, Decimal] | None` — returns the normalized (0-defaulted) split, `None` when all three are None; raises `ValueError` with a human message on sum≠actual or missing actual (callers map to 422).
  - `validate_allocations(items: list[tuple[str, Decimal]], actual_hours) -> None` — raises `ValueError` on duplicate category, hours ≤ 0, or Σ > actual.
  - `billed_hours(allocations: list[tuple[str, Decimal]]) -> Decimal`
  - `available_for_efficiency_hours(actual_hours: Decimal, allocations: list[tuple[str, Decimal]]) -> Decimal`
  - `effective_labor_class(override: str | None, employee_default: str | None) -> str | None`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_calculations/test_labor_hours.py
from decimal import Decimal

import pytest

from backend.calculations.labor_hours import (
    available_for_efficiency_hours,
    billed_hours,
    effective_labor_class,
    validate_allocations,
    validate_ot_split,
)


class TestOTSplit:
    def test_all_none_is_unsplit(self):
        assert validate_ot_split(None, None, None, Decimal("8.00")) is None

    def test_partial_defaults_to_zero_and_must_sum(self):
        # normal=8 supplied alone against actual 8: double/triple default 0 -> 8+0+0 == 8 OK
        assert validate_ot_split(Decimal("8.00"), None, None, Decimal("8.00")) == (
            Decimal("8.00"),
            Decimal("0"),
            Decimal("0"),
        )

    def test_sum_mismatch_raises(self):
        with pytest.raises(ValueError, match="sum"):
            validate_ot_split(Decimal("8.00"), Decimal("1.00"), None, Decimal("8.00"))

    def test_split_without_actual_raises(self):
        with pytest.raises(ValueError, match="actual_hours"):
            validate_ot_split(Decimal("8.00"), None, None, None)

    def test_full_split_ok(self):
        assert validate_ot_split(Decimal("8.00"), Decimal("2.00"), Decimal("1.00"), Decimal("11.00")) == (
            Decimal("8.00"),
            Decimal("2.00"),
            Decimal("1.00"),
        )


class TestAllocations:
    def test_duplicate_category_raises(self):
        with pytest.raises(ValueError, match="duplicate"):
            validate_allocations(
                [("training", Decimal("1.00")), ("training", Decimal("2.00"))], Decimal("8.00")
            )

    def test_sum_over_actual_raises(self):
        with pytest.raises(ValueError, match="exceed"):
            validate_allocations([("billed_production", Decimal("9.00"))], Decimal("8.00"))

    def test_nonpositive_hours_raises(self):
        with pytest.raises(ValueError, match="hours"):
            validate_allocations([("meeting", Decimal("0"))], Decimal("8.00"))

    def test_partial_allocation_ok(self):
        validate_allocations([("billed_production", Decimal("5.00"))], Decimal("8.00"))


class TestDerived:
    def test_billed_hours_sums_billable_only(self):
        allocs = [
            ("billed_production", Decimal("5.00")),
            ("unbilled_production", Decimal("1.00")),
            ("training", Decimal("1.00")),
        ]
        assert billed_hours(allocs) == Decimal("5.00")

    def test_available_subtracts_only_allocated_nonproductive(self):
        # actual 8; allocated: 5 billed_prod (productive), 1 training + 0.5 meeting (non-productive);
        # 1.5 unallocated counts productive-unbilled -> available = 8 - 1.5 = 6.5
        allocs = [
            ("billed_production", Decimal("5.00")),
            ("training", Decimal("1.00")),
            ("meeting", Decimal("0.50")),
        ]
        assert available_for_efficiency_hours(Decimal("8.00"), allocs) == Decimal("6.50")

    def test_available_with_no_allocations_is_actual(self):
        assert available_for_efficiency_hours(Decimal("8.00"), []) == Decimal("8.00")

    def test_effective_labor_class_resolution(self):
        assert effective_labor_class("indirect", "direct") == "indirect"
        assert effective_labor_class(None, "direct") == "direct"
        assert effective_labor_class(None, None) is None
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — straightforward pure functions over the taxonomy sets (`from backend.orm.labor_taxonomy import BILLABLE_CATEGORIES, PRODUCTIVE_CATEGORIES`); raise `ValueError("OT split must sum to actual_hours ...")`, `ValueError("OT split requires actual_hours")`, `ValueError("duplicate allocation category: ...")`, `ValueError("allocations exceed actual_hours ...")`, `ValueError("allocation hours must be > 0")` — messages matching the test regexes.
- [ ] **Step 4: Run green; commit** — `feat(labor): pure derivation + invariant helpers (OT split, allocations, billed/available/effective)` + trailer.

---

### Task 4: Attendance API — schemas, invariants, replace-on-write, derived responses

**Files:**
- Modify: `backend/schemas/attendance.py` (`AttendanceRecordCreate`, the update schema, the response schema — read the file for exact class names first)
- Modify: `backend/crud/attendance.py:27-…` (`create_attendance_record`), `:109-…` (`update_attendance_record`)
- Modify: `backend/routes/attendance.py` (response enrichment only if responses are built in-route — read first; keep changes minimal)
- Test: `backend/tests/test_routes/test_attendance_labor_capture.py` (create; mirror the existing attendance route harness fixtures)

**Interfaces:**
- Consumes: Task 1 enums, Task 3 helpers (exact signatures above).
- Produces: create/update schemas gain `normal_hours`/`double_hours`/`triple_hours: Optional[Decimal]`, `labor_class_override: Optional[LaborClassEnum]`, `allocations: Optional[list[AllocationItem]]` with `class AllocationItem(BaseModel): category: HourCategoryEnum; hours: Decimal = Field(gt=0)`. Response gains the four columns, `allocations: list[AllocationItem]`, `billed_hours: Decimal`, `available_for_efficiency_hours: Optional[Decimal]`, `effective_labor_class: Optional[str]`.

- [ ] **Step 1: Write the failing route tests** (single-status assertions, derivation comments; fixtures: one employee with `labor_class="direct"`):

```python
class TestOTSplitCapture:
    def test_create_with_valid_split(...):  # actual 11 = 8+2+1 -> 200/201, response echoes split
    def test_split_sum_mismatch_422(...):   # 8+1+0 vs actual 8 -> 422
    def test_unsplit_entry_still_works(...) # no split fields -> 200, split fields null

class TestAllocationCapture:
    def test_create_with_allocations_and_derived(...):
        # actual 8; allocs billed 5 + training 1 -> billed_hours 5.0,
        # available = 8 - 1 = 7.0 (derivation comment)
    def test_duplicate_category_422(...)
    def test_over_actual_422(...)
    def test_replace_on_write(...):   # update with new list replaces; empty list clears
    def test_omitted_allocations_no_change(...)

class TestEffectiveLaborClass:
    def test_override_beats_default(...)   # employee direct + override indirect -> "indirect"
    def test_default_when_no_override(...) # -> "direct"
```

(Write these as COMPLETE tests against the real harness — the class/method skeleton above defines required coverage; every test body must be concrete with exact expected values.)

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — schemas per Interfaces; in crud create/update: call `validate_ot_split` / `validate_allocations` mapping `ValueError` → `HTTPException(422, str(e))`; persist the normalized split (store the 0-defaulted triple when split supplied); replace-on-write = assign `entry.hour_allocations = [AttendanceHourAllocation(category=a.category.value, hours=a.hours) for a in allocations]` when the key is present (delete-orphan cascade handles removal). Response enrichment: a small builder applying Task 3's derived functions (join employee for the default class — the entry's employee relationship or a query; read how the routes load entries).
- [ ] **Step 4: Run** — new tests + `pytest tests/ -k "attendance" -q --no-cov` green; `pytest tests/test_bootstrap/ -q --no-cov` (schema-only — surface should be unchanged; verify).
- [ ] **Step 5: Commit** — `feat(labor): attendance API — OT split + allocations invariants, replace-on-write, derived fields` + trailer.

---

### Task 5: Employee admin labor_class

**Files:**
- Modify: `backend/schemas/employee.py:10-…` (`EmployeeCreate`, `EmployeeUpdate`, response), `backend/routes/employees.py` / its crud (read where updates apply fields)
- Test: extend the existing employee routes test module (locate by grep)

- [ ] **Step 1: Failing tests** — create employee with `labor_class="direct"` → 200/201 + echoed; invalid value → 422; update to `"indirect"` → 200; omitted → unchanged; explicit null → cleared. One denial case: the route's existing guard still rejects a non-supervisory caller (assert the exact current code).
- [ ] **Step 2: Run red.** **Step 3: Implement** (`labor_class: Optional[LaborClassEnum]` on create/update; response field; passes through the existing update path). **Step 4: Run green.** **Step 5: Commit** — `feat(labor): employee labor_class on admin surface` + trailer.

---

### Task 6: CSV attendance split columns

**Files:**
- Modify: `backend/endpoints/csv_upload.py:201-…` (`_map_attendance_row` + the attendance endpoint docstring)
- Test: extend the CSV attendance test module (characterization harness conventions)

- [ ] **Step 1: Failing tests** — CSV row with `normal_hours/double_hours/triple_hours` + `labor_class_override` → entry persisted with split (sum-validated: bad sum row → row-level error per the CSV flow's existing error idiom); columns absent → unsplit entry (back-compat).
- [ ] **Step 2: Run red.** **Step 3: Implement** — thread the four optional columns through `_map_attendance_row` into `AttendanceRecordCreate` (validation then flows through Task 4's schema/crud path); docstring documents the new optional columns and states allocations are NOT CSV-supported (spec §4 documented limitation).
- [ ] **Step 4: Run green (incl. golden masters per their harness).** **Step 5: Commit** — `feat(labor): CSV attendance accepts OT split + labor_class_override` + trailer.

---

### Task 7: Frontend — grid columns, allocations dialog, completeness chips, employee select

**Files:**
- Create: `frontend/src/constants/laborTaxonomy.ts` + `frontend/src/constants/__tests__/laborTaxonomy.spec.ts`
- Create: `frontend/src/components/AllocationEditorDialog.vue` (small focused component) + a pure-logic composable `frontend/src/composables/useAllocationEditor.ts` + spec
- Modify: `frontend/src/composables/useAttendanceGridData.ts` (+ its spec), the attendance grid host component (locate via grep `useAttendanceGridData`), the employee admin form (locate via grep — the admin Users/Employees surface), `frontend/src/i18n/locales/en.json`/`es.json` (`labor.*` block)
- Test: vitest specs above; Playwright guard in the attendance e2e area (follow the suite's grid idioms)

**Interfaces:**
- Consumes: Task 4's API shapes.
- Produces: `laborTaxonomy.ts` mirrors backend (LABOR_CLASS_CODES ×2, HOUR_CATEGORY_CODES ×8 in backend order, BILLABLE/PRODUCTIVE sets, `laborClassLabelKey(id)`, `hourCategoryLabelKey(id)` → `labor.classes.<id>` / `labor.categories.<camelCase>`); `useAllocationEditor` pure helpers (row add/remove, client-side sum/duplicate validation mirroring the server rules, Σallocated summary string).

- [ ] **Step 1: Constants + spec** — mirror the Cycle 1/2 constants pattern exactly (backend-order parity, both-locale key resolution incl. every category + class + `labor.unclassified`).
- [ ] **Step 2: i18n blocks (both locales)** — `labor`: `classes {direct: "Direct"/"Directo", indirect: "Indirect"/"Indirecto"}`, `unclassified: "Unclassified"/"Sin clasificar"`, `categories` ×8 (en: "Billed production", "Unbilled production", "Training", "Meeting", "Idle / waiting", "Other non-productive", "Paid leave", "Medical"; es: "Producción facturada", "Producción no facturada", "Capacitación", "Junta", "Espera / inactivo", "Otro no productivo", "Permiso con goce", "Médico"), `allocationsTitle: "Hour allocation"/"Asignación de horas"`, `allocatedSummary: "{allocated} / {actual} h"`, `noSplitCount: "{count} without OT split"/"{count} sin desglose de TE"`, `unallocatedCount: "{count} unallocated"/"{count} sin asignar"`, `otNormal: "Normal"/"Normales"`, `otDouble: "Double"/"Dobles"`, `otTriple: "Triple"/"Triples"`.
- [ ] **Step 3: Grid** — three numeric OT columns (empty when null — NO placeholder text), `labor_class_override` select (values direct/indirect + clear-to-null option, formatted via i18n), an allocations button-cell showing `allocatedSummary` (empty cell when no allocations), and the two completeness chips on the host screen (`v-if > 0`). Dialog: category select (8 options) + hours input rows, add/remove, client-side validation via `useAllocationEditor`, save submits the full list through the entry-update path.
- [ ] **Step 4: Employee admin** — `labor_class` select (Direct/Indirect/Unclassified→null) in the employee form, following how Cycle 2 added the drawer select.
- [ ] **Step 5: Vitest** — constants parity; allocation-editor truth table (duplicate blocked, over-sum blocked, summary string); grid column defs (editors present, empty-cell renderers); completeness counts.
- [ ] **Step 6: Playwright guard** — on the attendance grid: enter an OT split on a row, open the allocation dialog, add billed_production 5 + training 1, save, assert the summary cell shows the allocated total and the API round-trip persisted (reload or response assertion), en/es-tolerant. Run it for real on chromium (gym-platform port dance if needed).
- [ ] **Step 7: Run frontend battery (vitest full, lint, typecheck) + the a11y contrast gate spec (`npx playwright test e2e/a11y-contrast.spec.ts ...`) — MUST stay 0 violations (new UI surfaces!).** Commit — `feat(labor): attendance grid OT split + allocation dialog + completeness chips + employee labor-class select` + trailer.

---

### Task 8: Seeders

**Files:**
- Modify: `backend/scripts/_seed_operations.py:555-…` (attendance block) + employee seeding site (`_seed_master.py` — read it), `backend/scripts/init_demo_database.py` (its attendance/employee blocks)
- Test: extend both seeder test modules

**Interfaces:** deterministic, per spec §7: employees majority-direct (fixed pattern, e.g. `i % 4 == 3` → indirect, else direct — all classified in seeds for demo credibility); attendance entries: fixed cadence OT splits (e.g. every 5th entry double_hours=2 with normal=actual−2; every 20th triple_hours=1; others all-normal split; a fixed minority left UNSPLIT to demo the completeness chip), sparse overrides (every 15th entry override flips the class), allocations on a fixed cadence with a **rotating category counter INDEPENDENT of the cadence modulus** covering all 8 categories across the sample dataset (exact-set asserted), majority `billed_production`, a fixed minority of entries left unallocated (completeness chip demo).

- [ ] **Step 1: Failing seeder tests** — sample: every seeded allocation enum-valid, Σ ≤ actual per entry, exact-set of seeded categories == all 8, both labor classes present on employees, ≥1 override entry, ≥1 unsplit entry, ≥1 unallocated entry, split-sum==actual for all split entries; demo seeder: same invariants with its (documented) achievable category subset — exact-set asserted.
- [ ] **Step 2: Run red.** **Step 3: Implement (enum members only, no string literals; counters per the gcd lesson).** **Step 4: Run seeder tests + FULL `pytest tests/ -q`.** **Step 5: Commit** — `feat(labor): deterministic seeder coverage for OT splits, labor classes, allocations` + trailer.

---

### Task 9: Full verification sweep

**Files:** none new (report-only unless fixes needed).

- [ ] **Step 1:** Backend `pytest tests/ -q` (coverage ≥75%); frontend `npm run test && npm run lint && npm run typecheck`; a11y gate 0 violations; `pytest tests/test_bootstrap/ -q` (no surface change in PR-A).
- [ ] **Step 2:** Grep sweep: no string-literal labor classes/categories outside the taxonomy modules, frozen migrations, and i18n files — `rtk proxy grep -rn "billed_production\|idle_wait\|labor_class" backend frontend/src --include="*.py" --include="*.ts" --include="*.vue" | grep -v taxonomy | grep -v alembic/versions | grep -v test | grep -v i18n` → every hit imports from a taxonomy module or is a documented exemption (list + disposition).
- [ ] **Step 3:** Commit any sweep fixes; otherwise report clean.

---

### Task 10: Cross-review and PR (controller-level)

- [ ] **Step 1:** `git diff --stat main...HEAD` — spec + this plan + backend (orm/alembic/calculations/schemas/crud/routes/endpoints/scripts/tests) + frontend (constants/components/composables/i18n/e2e). NO docs/reporting changes (re-grade is PR-B).
- [ ] **Step 2:** `/cross-review` for final HEAD (chunked if >1500 lines).
- [ ] **Step 3:** Push; PR `feat(labor): labor-hours capture — OT split, labor classes, hour-allocation ledger (Cycle 3 PR-A)`; body lists model/migration/invariants/UI/seeders + "metrics follow in PR-B"; standard footer.
- [ ] **Step 4:** `gh pr checks <n> --watch` (explicit number) → 7/7 → report URL; merge user-confirmed. Post-merge: main verify → Render auto (migration 0004) → VM deploy + re-seed → live-verify spec §9's §10-A items → then write the PR-B plan.
