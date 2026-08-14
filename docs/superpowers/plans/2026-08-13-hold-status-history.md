# Hold-Status Transition History Implementation Plan (Cycle 4 PR-C1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `active_as_of` a real status-transition history so `/api/kpi/wip-aging/trend` stops judging past dates by holds' current status.

**Architecture:** A new `HOLD_STATUS_TRANSITION` table mirroring the existing `WORKFLOW_TRANSITION_LOG`, written at every `hold_status` write site, read back by a correlated scalar subquery inside `active_as_of`. Holds with no recorded transition fall back to their current status, so behaviour before the table exists is unchanged rather than wrong in a new way.

**Tech Stack:** SQLAlchemy 2.x declarative ORM, Alembic, FastAPI, pytest. Runs on SQLite (dev/CI) and MariaDB 11.4 (production).

**Spec:** `docs/superpowers/specs/2026-08-13-hold-status-history-design.md`

## Global Constraints

- Alembic is the **only** schema-evolution mechanism. Never edit a shipped revision; add a new one. `create_all` is forbidden outside Alembic and guarded by `test_no_create_all_outside_alembic`.
- New revision id is `0006_hold_status_history`, `down_revision = "0005_audit_trail"` (current head).
- **Every new ORM table must be added to `backend/audit/registry.py`.** `tests/test_audit/test_registry_guards.py` asserts every table in `Base.metadata` appears in exactly one of `AUDITED_TABLES` / `EXCLUDED_TABLES`. Omitting it fails the build.
- Portable SQL only: no `julianday()`, no `CAST(... AS DATE)`, no dialect-specific date arithmetic, no JSON extraction. Guarded by `test_no_sql_cast_date` and `test_date_diff_days_executes_on_mariadb`.
- **MariaDB `DATETIME` stores whole seconds.** Two transitions can share a timestamp; every "latest transition" query must tie-break on `transition_id DESC`.
- Permissive assertions are forbidden. No `assert response.status_code in [...]` — each test asserts exactly one expected value.
- **No backfill.** Do not synthesise history for existing holds.
- `NON_WIP_HOLD_STATUSES` membership is settled by owner ruling and must not change: `CANCELLED`, `RELEASED`, `SCRAPPED`, `PENDING_HOLD_APPROVAL` are excluded; `PENDING_RESUME_APPROVAL` counts.
- Backend tests run as `pytest tests/` from `backend/`. Coverage gate ≥ 75%.
- A test counts as evidence only after you have watched it fail for the reason it exists. Every "verify it fails" step requires pasting the actual failure output into the task report.

---

### Task 1: `HOLD_STATUS_TRANSITION` model, migration, and registry entry

**Files:**
- Create: `backend/orm/hold_status_transition.py`
- Modify: `backend/orm/__init__.py` (import + `__all__`, following the `WorkflowTransitionLog` entries)
- Create: `backend/alembic/versions/0006_hold_status_history.py`
- Modify: `backend/audit/registry.py` (add to `EXCLUDED_TABLES`)
- Test: `backend/tests/test_calculations/test_hold_status_history.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `HoldStatusTransition` with columns `transition_id: int`, `hold_entry_id: str`, `client_id: str`, `from_status: Optional[str]`, `to_status: str`, `transitioned_by: Optional[str]`, `transitioned_at: datetime`, `notes: Optional[str]`.

- [ ] **Step 1: Write the model**

`backend/orm/hold_status_transition.py`. Mirrors `backend/orm/workflow.py`, including its corrected `transitioned_by` type (String(50) FK to `USER.user_id`, not Integer).

```python
"""HOLD_STATUS_TRANSITION table ORM schema (SQLAlchemy).

Append-only history of HOLD_ENTRY.hold_status changes. Mirrors
WORKFLOW_TRANSITION_LOG (backend/orm/workflow.py), which answers the same
question for work orders.

Exists so `backend/calculations/wip_aging.py:active_as_of` can ask "what was
this hold's status on date D" instead of judging past dates by current state.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class HoldStatusTransition(Base):
    __tablename__ = "HOLD_STATUS_TRANSITION"
    __table_args__ = (
        Index("ix_hold_transition_hold", "hold_entry_id"),
        Index("ix_hold_transition_client_date", "client_id", "transitioned_at"),
        Index("ix_hold_transition_status", "to_status", "transitioned_at"),
        {"extend_existing": True},
    )

    transition_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    hold_entry_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("HOLD_ENTRY.hold_entry_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # NULL only on the row recording hold creation.
    from_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)

    transitioned_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=True)
    # No server_default: callers always pass an explicit instant, so seeded
    # history can be back-dated and every row's time is caller-controlled.
    transitioned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    notes: Mapped[Optional[str]] = mapped_column(Text)
```

Confirm `HOLD_ENTRY.hold_entry_id` is `String(50)` before committing to that FK type; if it differs, match it exactly (`test_foreign_key_column_types_match_referenced_columns` will fail otherwise).

- [ ] **Step 2: Register the model**

In `backend/orm/__init__.py`, add `from backend.orm.hold_status_transition import HoldStatusTransition` and `"HoldStatusTransition"` to `__all__`, placed beside the existing `WorkflowTransitionLog` entries.

- [ ] **Step 3: Add the registry entry**

In `backend/audit/registry.py`, add to `EXCLUDED_TABLES` in the "Self-auditing tables" block, next to `WORKFLOW_TRANSITION_LOG`:

```python
    "HOLD_STATUS_TRANSITION": (
        "own append-only audit trail for HOLD_ENTRY.hold_status changes "
        "(mirrors WORKFLOW_TRANSITION_LOG); auditing it would double-log"
    ),
```

- [ ] **Step 4: Run the registry guard to confirm it passes**

Run: `pytest tests/test_audit/test_registry_guards.py -v`
Expected: PASS. If you skipped Step 3, this fails with the new table named as unclassified — worth seeing once to confirm the guard works.

- [ ] **Step 5: Write the migration**

`backend/alembic/versions/0006_hold_status_history.py`, following `0005_audit_trail.py`:

```python
"""Hold-status transition history (Cycle 4 PR-C1).

Revision ID: 0006_hold_status_history
Revises: 0005_audit_trail
Create Date: 2026-08-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_hold_status_history"
down_revision: Union[str, None] = "0005_audit_trail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "HOLD_STATUS_TRANSITION",
        sa.Column("transition_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hold_entry_id", sa.String(length=50), nullable=False),
        sa.Column("client_id", sa.String(length=50), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("transitioned_by", sa.String(length=50), nullable=True),
        sa.Column("transitioned_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["hold_entry_id"], ["HOLD_ENTRY.hold_entry_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["CLIENT.client_id"]),
        sa.ForeignKeyConstraint(["transitioned_by"], ["USER.user_id"]),
        sa.PrimaryKeyConstraint("transition_id"),
    )
    op.create_index("ix_hold_transition_hold", "HOLD_STATUS_TRANSITION", ["hold_entry_id"])
    op.create_index("ix_hold_transition_client_date", "HOLD_STATUS_TRANSITION", ["client_id", "transitioned_at"])
    op.create_index("ix_hold_transition_status", "HOLD_STATUS_TRANSITION", ["to_status", "transitioned_at"])
    op.create_index(
        op.f("ix_HOLD_STATUS_TRANSITION_hold_entry_id"), "HOLD_STATUS_TRANSITION", ["hold_entry_id"]
    )
    op.create_index(op.f("ix_HOLD_STATUS_TRANSITION_client_id"), "HOLD_STATUS_TRANSITION", ["client_id"])
    op.create_index(
        op.f("ix_HOLD_STATUS_TRANSITION_transitioned_at"), "HOLD_STATUS_TRANSITION", ["transitioned_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_HOLD_STATUS_TRANSITION_transitioned_at"), table_name="HOLD_STATUS_TRANSITION")
    op.drop_index(op.f("ix_HOLD_STATUS_TRANSITION_client_id"), table_name="HOLD_STATUS_TRANSITION")
    op.drop_index(op.f("ix_HOLD_STATUS_TRANSITION_hold_entry_id"), table_name="HOLD_STATUS_TRANSITION")
    op.drop_index("ix_hold_transition_status", table_name="HOLD_STATUS_TRANSITION")
    op.drop_index("ix_hold_transition_client_date", table_name="HOLD_STATUS_TRANSITION")
    op.drop_index("ix_hold_transition_hold", table_name="HOLD_STATUS_TRANSITION")
    op.drop_table("HOLD_STATUS_TRANSITION")
```

The index set must match what the ORM declares exactly — three named composite/simple indexes from `__table_args__` plus the three `index=True` column indexes. If schema parity fails in Step 6, reconcile by making the migration match the model, never the reverse.

- [ ] **Step 6: Run the schema-parity gates on both dialects**

Run: `pytest tests/test_mariadb_portability.py -v --no-cov`
Expected: PASS, specifically `test_baseline_builds_schema_equal_to_metadata_sqlite`, `test_baseline_builds_schema_equal_to_metadata_mariadb`, `test_full_schema_creates_on_mariadb`, and `test_foreign_key_column_types_match_referenced_columns`.

If MariaDB is unavailable locally, say so explicitly in the task report rather than reporting a pass you did not observe — CI's `mariadb-portability` job runs it regardless.

- [ ] **Step 7: Commit**

```bash
git add backend/orm/hold_status_transition.py backend/orm/__init__.py \
        backend/alembic/versions/0006_hold_status_history.py backend/audit/registry.py
git commit -m "feat(holds): HOLD_STATUS_TRANSITION table + migration 0006"
```

---

### Task 2: Transition recorder

**Files:**
- Create: `backend/crud/hold/transition_log.py`
- Modify: `backend/crud/hold/__init__.py` (export)
- Test: `backend/tests/test_crud/test_hold_transition_log.py`

**Interfaces:**
- Consumes: `HoldStatusTransition` from Task 1.
- Produces: `record_hold_transition(db, hold, to_status, current_user, from_status=..., notes=None, transitioned_at=None) -> HoldStatusTransition`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_crud/test_hold_transition_log.py`:

```python
from datetime import datetime, timedelta

from backend.crud.hold.transition_log import record_hold_transition
from backend.orm.hold_status_transition import HoldStatusTransition


def test_records_transition_with_explicit_instant(db_session, sample_hold, sample_user):
    when = datetime(2026, 3, 1, 8, 30, 0)

    row = record_hold_transition(
        db_session,
        sample_hold,
        to_status="ON_HOLD",
        current_user=sample_user,
        from_status="PENDING_HOLD_APPROVAL",
        transitioned_at=when,
    )
    db_session.flush()

    assert row.transitioned_at == when
    assert row.from_status == "PENDING_HOLD_APPROVAL"
    assert row.to_status == "ON_HOLD"
    assert row.hold_entry_id == sample_hold.hold_entry_id
    assert row.client_id == sample_hold.client_id
    assert row.transitioned_by == sample_user.user_id


def test_from_status_defaults_to_holds_current_status(db_session, sample_hold, sample_user):
    sample_hold.hold_status = "ON_HOLD"

    row = record_hold_transition(
        db_session, sample_hold, to_status="RESUMED", current_user=sample_user
    )
    db_session.flush()

    assert row.from_status == "ON_HOLD"


def test_defaults_transitioned_at_to_now_when_not_given(db_session, sample_hold, sample_user):
    before = datetime.utcnow() - timedelta(seconds=5)

    row = record_hold_transition(
        db_session, sample_hold, to_status="RESUMED", current_user=sample_user
    )
    db_session.flush()

    assert row.transitioned_at >= before


def test_rows_are_queryable_in_recorded_order(db_session, sample_hold, sample_user):
    day1 = datetime(2026, 3, 1, 8, 0, 0)
    day5 = datetime(2026, 3, 5, 8, 0, 0)
    record_hold_transition(
        db_session, sample_hold, to_status="ON_HOLD", current_user=sample_user, transitioned_at=day5
    )
    record_hold_transition(
        db_session,
        sample_hold,
        to_status="PENDING_HOLD_APPROVAL",
        current_user=sample_user,
        from_status=None,
        transitioned_at=day1,
    )
    db_session.flush()

    rows = (
        db_session.query(HoldStatusTransition)
        .filter(HoldStatusTransition.hold_entry_id == sample_hold.hold_entry_id)
        .order_by(HoldStatusTransition.transitioned_at)
        .all()
    )

    assert [r.to_status for r in rows] == ["PENDING_HOLD_APPROVAL", "ON_HOLD"]
```

Reuse the existing hold/user fixtures from `backend/tests/test_crud/test_hold_crud_comprehensive.py`; if their names differ from `sample_hold` / `sample_user`, use the real ones rather than adding duplicates.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_crud/test_hold_transition_log.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.crud.hold.transition_log'`.

- [ ] **Step 3: Write the recorder**

```python
"""Append-only recorder for HOLD_ENTRY.hold_status changes.

Mirrors backend/crud/workflow/transition_log.py. Every hold_status write in
the codebase pairs with a call here, in the same transaction, so the history
cannot disagree with the hold row it describes.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.orm.hold_entry import HoldEntry
from backend.orm.hold_status_transition import HoldStatusTransition
from backend.orm.user import User

_UNSET = object()


def record_hold_transition(
    db: Session,
    hold: HoldEntry,
    to_status: str,
    current_user: Optional[User] = None,
    from_status: object = _UNSET,
    notes: Optional[str] = None,
    transitioned_at: Optional[datetime] = None,
) -> HoldStatusTransition:
    """Record one hold_status change.

    Call BEFORE assigning the new status, so the default `from_status` reads
    the value being replaced. Pass `from_status=None` explicitly for the row
    that records hold creation.

    `transitioned_at` defaults to now; callers that write historical rows
    (the demo seeder) always pass an explicit instant.
    """
    resolved_from = hold.hold_status if from_status is _UNSET else from_status

    row = HoldStatusTransition(
        hold_entry_id=hold.hold_entry_id,
        client_id=hold.client_id,
        from_status=resolved_from,
        to_status=to_status,
        transitioned_by=getattr(current_user, "user_id", None),
        transitioned_at=transitioned_at or datetime.utcnow(),
        notes=notes,
    )
    db.add(row)
    return row
```

`datetime.utcnow()` matches the naive-UTC convention `HoldEntry.hold_date` and `AuditEntry.occurred_at` already use; do not introduce a tz-aware default here, since comparisons against `snapshot_cutoff` are naive.

- [ ] **Step 4: Export it**

Add `record_hold_transition` to `backend/crud/hold/__init__.py` alongside the existing hold CRUD exports.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_crud/test_hold_transition_log.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/crud/hold/transition_log.py backend/crud/hold/__init__.py \
        backend/tests/test_crud/test_hold_transition_log.py
git commit -m "feat(holds): record_hold_transition recorder"
```

---

### Task 3: Instrument every `hold_status` write site

**Files:**
- Modify: `backend/crud/hold/core.py:57,60` (creation, two branches)
- Modify: `backend/crud/hold/duration.py:55` (resume), `:168` (release)
- Modify: `backend/routes/holds.py:196` (approve hold), `:231` (request resume), `:271` (approve resume)
- Test: `backend/tests/test_crud/test_hold_transition_log.py` (append)

**Interfaces:**
- Consumes: `record_hold_transition` from Task 2.
- Produces: every hold carries a transition chain beginning with a `from_status=None` row.

There are exactly seven sites. Two are creation branches in `core.py`; five are status changes. Re-run the search before starting in case the tree moved:

```bash
rg -n "hold_status\s*=" --type py backend/ | grep -v "/tests/" | grep -v "==" | grep -v "^backend/orm/"
```

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_crud/test_hold_transition_log.py`:

```python
def test_hold_creation_records_opening_row(db_session, sample_client, sample_user):
    """Every hold begins with a from_status=None row, so its history is complete."""
    hold = create_wip_hold(db_session, _hold_create_payload(sample_client), sample_user)
    db_session.flush()

    rows = (
        db_session.query(HoldStatusTransition)
        .filter(HoldStatusTransition.hold_entry_id == hold.hold_entry_id)
        .all()
    )

    assert len(rows) == 1
    assert rows[0].from_status is None
    assert rows[0].to_status == hold.hold_status


def test_resume_records_transition_to_resumed(db_session, sample_hold, sample_user):
    sample_hold.hold_status = "ON_HOLD"
    db_session.flush()

    resume_wip_hold(db_session, sample_hold.hold_entry_id, sample_user)
    db_session.flush()

    rows = (
        db_session.query(HoldStatusTransition)
        .filter(HoldStatusTransition.hold_entry_id == sample_hold.hold_entry_id)
        .order_by(HoldStatusTransition.transition_id)
        .all()
    )

    assert rows[-1].from_status == "ON_HOLD"
    assert rows[-1].to_status == "RESUMED"


def test_every_hold_status_write_site_is_instrumented():
    """Static guard: a hold_status assignment with no recorder call nearby is a
    hole in the history, and holes are invisible until a trend query is wrong.

    Scans for `hold_status =` assignments in production modules and requires
    `record_hold_transition` to appear in the same file.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2]
    assignment = re.compile(r"^\s*[\w.]*hold_status\s*=\s*(?!=)")
    offenders = []

    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("tests/", "orm/", "schemas/", "scripts/", "db/", "alembic/")):
            continue
        text = path.read_text()
        if any(assignment.match(line) for line in text.splitlines()):
            if "record_hold_transition" not in text:
                offenders.append(rel)

    assert offenders == []
```

The guard's exclusions are deliberate: `orm/` and `schemas/` declare defaults rather than perform transitions, `scripts/` and `db/` are seeders and fixtures that write history explicitly, `alembic/` is schema.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_crud/test_hold_transition_log.py -v -k "creation_records or resume_records or write_site"`
Expected: FAIL. The static guard must name `crud/hold/core.py`, `crud/hold/duration.py`, and `routes/holds.py` in `offenders`. Paste that list into the task report — a guard that passes before the fix is testing nothing.

- [ ] **Step 3: Instrument `crud/hold/core.py`**

Both branches set the initial status. After the hold row exists and has its PK (after the `db.add(...)` / `db.flush()` that assigns `hold_entry_id`), record the opening row:

```python
    record_hold_transition(
        db,
        db_hold,
        to_status=db_hold.hold_status,
        current_user=current_user,
        from_status=None,
        notes="Hold created",
    )
```

The recorder needs `hold_entry_id` and `client_id` populated, so it must run after the flush that assigns them, not before.

- [ ] **Step 4: Instrument the five transition sites**

At each, call the recorder **before** the assignment so the default `from_status` captures the outgoing value:

```python
    record_hold_transition(db, db_hold, to_status=HoldStatus.RESUMED, current_user=current_user)
    db_hold.hold_status = HoldStatus.RESUMED
```

Applied at `crud/hold/duration.py:55` (`RESUMED`), `duration.py:168` (`RESUMED`), `routes/holds.py:196` (`ON_HOLD`), `routes/holds.py:231` (`PENDING_RESUME_APPROVAL`), `routes/holds.py:271` (`RESUMED`). Use whatever the local variable for the acting user is at each site; where a route has `current_user` from its dependency, pass that.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_crud/test_hold_transition_log.py tests/test_crud/test_hold_crud_comprehensive.py tests/test_routes/test_holds_aging_portability.py -v`
Expected: all pass, including the static guard with `offenders == []`.

- [ ] **Step 6: Run the full backend suite**

Run: `pytest tests/`
Expected: no regressions. Existing hold tests that assert row counts may need the extra transition rows accounted for; fix those tests only where the new rows are the genuine cause.

- [ ] **Step 7: Commit**

```bash
git add backend/crud/hold/ backend/routes/holds.py backend/tests/test_crud/test_hold_transition_log.py
git commit -m "feat(holds): record a transition at every hold_status write site"
```

---

### Task 4: Rewrite `active_as_of`'s status arm and expose the boundary

**Files:**
- Modify: `backend/calculations/wip_aging.py:97-136` (`active_as_of`) and its docstring
- Test: `backend/tests/test_calculations/test_hold_status_history.py`

**Interfaces:**
- Consumes: `HoldStatusTransition` (Task 1), transition rows written by Task 3.
- Produces: `active_as_of(as_of: date) -> ColumnElement[bool]` (signature unchanged) and `hold_status_history_started_at(db: Session) -> Optional[datetime]`.

**Do Task 5's golden-master capture (Step 1 of Task 5) BEFORE changing this file** — it must be measured against the old implementation.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_calculations/test_hold_status_history.py`. These are the two cases the current docstring says are wrong, one in each direction:

```python
from datetime import date, datetime

from backend.calculations.wip_aging import active_as_of, hold_status_history_started_at
from backend.orm.hold_entry import HoldEntry


def _active_ids(db, as_of):
    return {h.hold_entry_id for h in db.query(HoldEntry).filter(active_as_of(as_of)).all()}


def test_pending_then_approved_hold_is_absent_before_approval(db_session, hold_with_history):
    """Was only PENDING_HOLD_APPROVAL on day 3; approved on day 5.

    Current-status logic counts it at day 3 because it reads ON_HOLD today.
    """
    assert hold_with_history.pending_then_approved not in _active_ids(db_session, date(2026, 3, 3))
    assert hold_with_history.pending_then_approved in _active_ids(db_session, date(2026, 3, 6))


def test_held_then_cancelled_hold_is_present_before_cancellation(db_session, hold_with_history):
    """Was ON_HOLD on day 3; cancelled on day 8.

    Current-status logic drops it from day 3 because it reads CANCELLED today.
    """
    assert hold_with_history.held_then_cancelled in _active_ids(db_session, date(2026, 3, 3))
    assert hold_with_history.held_then_cancelled not in _active_ids(db_session, date(2026, 3, 9))


def test_hold_without_history_falls_back_to_current_status(db_session, hold_without_history):
    """No backfill: a pre-existing hold has no transitions, so behaviour is
    exactly what it was before this change — present while unresumed."""
    assert hold_without_history.hold_entry_id in _active_ids(db_session, date(2026, 3, 3))
    assert hold_without_history.hold_entry_id in _active_ids(db_session, date(2026, 3, 9))


def test_same_second_transitions_resolve_by_insertion_order(db_session, same_second_hold):
    """MariaDB DATETIME has whole-second resolution, so two transitions can
    share a timestamp. The later-inserted row must win."""
    assert same_second_hold.hold_entry_id not in _active_ids(db_session, date(2026, 3, 5))


def test_history_boundary_reports_first_recorded_transition(db_session, hold_with_history):
    assert hold_status_history_started_at(db_session) == datetime(2026, 3, 1, 8, 0, 0)
```

Fixtures build holds directly plus explicit `HoldStatusTransition` rows:

```python
import pytest
from types import SimpleNamespace

from backend.orm.hold_status_transition import HoldStatusTransition


def _t(db, hold_id, client_id, from_status, to_status, when):
    db.add(
        HoldStatusTransition(
            hold_entry_id=hold_id,
            client_id=client_id,
            from_status=from_status,
            to_status=to_status,
            transitioned_at=when,
        )
    )


@pytest.fixture
def hold_with_history(db_session, sample_client):
    a = _make_hold(db_session, sample_client, "H-PENDING-APPROVED", datetime(2026, 3, 1, 8, 0, 0), "ON_HOLD")
    b = _make_hold(db_session, sample_client, "H-HELD-CANCELLED", datetime(2026, 3, 1, 9, 0, 0), "CANCELLED")
    db_session.flush()

    _t(db_session, a.hold_entry_id, a.client_id, None, "PENDING_HOLD_APPROVAL", datetime(2026, 3, 1, 8, 0, 0))
    _t(db_session, a.hold_entry_id, a.client_id, "PENDING_HOLD_APPROVAL", "ON_HOLD", datetime(2026, 3, 5, 10, 0, 0))
    _t(db_session, b.hold_entry_id, b.client_id, None, "ON_HOLD", datetime(2026, 3, 1, 9, 0, 0))
    _t(db_session, b.hold_entry_id, b.client_id, "ON_HOLD", "CANCELLED", datetime(2026, 3, 8, 11, 0, 0))
    db_session.flush()

    return SimpleNamespace(pending_then_approved=a.hold_entry_id, held_then_cancelled=b.hold_entry_id)


@pytest.fixture
def hold_without_history(db_session, sample_client):
    hold = _make_hold(db_session, sample_client, "H-NO-HISTORY", datetime(2026, 3, 1, 8, 0, 0), "ON_HOLD")
    db_session.flush()
    return hold


@pytest.fixture
def same_second_hold(db_session, sample_client):
    hold = _make_hold(db_session, sample_client, "H-SAME-SECOND", datetime(2026, 3, 1, 8, 0, 0), "CANCELLED")
    db_session.flush()
    same = datetime(2026, 3, 4, 12, 0, 0)
    _t(db_session, hold.hold_entry_id, hold.client_id, None, "ON_HOLD", same)
    _t(db_session, hold.hold_entry_id, hold.client_id, "ON_HOLD", "CANCELLED", same)
    db_session.flush()
    return hold
```

The `_make_hold` helper, module-level in this test file. Reuse whichever client fixture the other files in `tests/test_calculations/` use:

```python
def _make_hold(db, client, hold_id, hold_date, current_status):
    """A HoldEntry that is never resumed, carrying the given CURRENT status.

    `current_status` is deliberately set to what the hold looks like TODAY —
    the tests turn on it differing from the status at the as-of date.
    """
    hold = HoldEntry(
        hold_entry_id=hold_id,
        client_id=client.client_id,
        work_order_id=None,
        hold_status=current_status,
        hold_date=hold_date,
        resume_date=None,
        hold_reason="test fixture",
    )
    db.add(hold)
    return hold
```

If `HoldEntry` requires columns beyond these (check `backend/orm/hold_entry.py` for `nullable=False` without a default), add them with obvious values rather than letting the insert fail.

- [ ] **Step 2: Run the tests to verify they fail — and check WHY**

Run: `pytest tests/test_calculations/test_hold_status_history.py -v`
Expected: `test_history_boundary_reports_first_recorded_transition` fails on `ImportError` (the helper does not exist yet), and the first two tests fail on the **assertion**, not the import — that is the proof they exercise the defect. Paste both failure messages into the task report.

If `test_pending_then_approved_hold_is_absent_before_approval` passes before the rewrite, the fixture is wrong: the hold's *current* status must be one that the old predicate treats differently from its status at the as-of date. Fix the fixture, do not proceed.

- [ ] **Step 3: Rewrite the status arm**

Replace the body of `active_as_of` (keeping the date and resume arms exactly as they are):

```python
    cutoff = snapshot_cutoff(as_of)

    # The hold's status AS OF the cutoff: the `to_status` of its latest
    # transition strictly before the cutoff. Ordered by (transitioned_at,
    # transition_id) because MariaDB DATETIME stores whole seconds -- two
    # transitions can share an instant, and the later-inserted row wins.
    status_as_of = (
        select(HoldStatusTransition.to_status)
        .where(
            HoldStatusTransition.hold_entry_id == HoldEntry.hold_entry_id,
            HoldStatusTransition.transitioned_at < cutoff,
        )
        .correlate(HoldEntry)
        .order_by(
            HoldStatusTransition.transitioned_at.desc(),
            HoldStatusTransition.transition_id.desc(),
        )
        .limit(1)
        .scalar_subquery()
    )

    # No backfill: holds predating this table have no transitions, so they
    # fall back to current status -- exactly the pre-PR-C1 behaviour, rather
    # than vanishing from history entirely.
    effective_status = func.coalesce(status_as_of, HoldEntry.hold_status)

    return and_(
        HoldEntry.hold_date < cutoff,
        or_(HoldEntry.resume_date.is_(None), HoldEntry.resume_date >= cutoff),
        effective_status.notin_(NON_WIP_HOLD_STATUSES),
    )
```

Add `from sqlalchemy import func, select` and `from backend.orm.hold_status_transition import HoldStatusTransition` to the module imports.

- [ ] **Step 4: Add the boundary helper**

```python
def hold_status_history_started_at(db: Session) -> Optional[datetime]:
    """Earliest recorded hold-status transition, or None when none exist.

    `active_as_of` is exact from a hold's first recorded transition onward and
    falls back to current status before it (there is no backfill, by owner
    ruling). Callers that present historical series use this to say honestly
    from when the series is exact -- the same role `_trail_started_at` plays
    for the audit read API in backend/routes/audit.py.
    """
    return db.query(func.min(HoldStatusTransition.transitioned_at)).scalar()
```

- [ ] **Step 5: Replace the KNOWN LIMITATION docstring**

The block at lines 115-129 documents the defect this task fixes and instructs against papering over it with current-status logic. Replace it with what is now true:

```
    Status is read from HOLD_STATUS_TRANSITION -- the `to_status` of the
    latest transition before the cutoff -- so a past `as_of` is judged by what
    the hold actually was then, not by what it looks like today.

    BOUNDARY (no backfill). Holds with no recorded transition before the
    cutoff fall back to their current `hold_status`, which is the pre-PR-C1
    behaviour: correct for live holds, approximate for history that predates
    the table. `hold_status_history_started_at` reports where exactness
    begins. Backfill was ruled out deliberately (2026-08-12); do not
    reconstruct history retroactively.
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_calculations/test_hold_status_history.py -v`
Expected: 5 passed.

- [ ] **Step 7: Run every consumer of the predicate**

Run: `pytest tests/test_calculations/ tests/test_routes/test_holds_aging_portability.py -v`
Expected: all pass. The four consumers are the aggregate, top-N, trend, and chronic-hold queries.

- [ ] **Step 8: Commit**

```bash
git add backend/calculations/wip_aging.py backend/tests/test_calculations/test_hold_status_history.py
git commit -m "fix(kpi): active_as_of reads real hold-status history, not current state"
```

---

### Task 5: As-of-now invariance and query-plan guard

**Files:**
- Test: `backend/tests/test_calculations/test_hold_status_history.py` (append)

**Interfaces:**
- Consumes: `active_as_of` (Task 4).
- Produces: nothing consumed downstream.

The rewrite touches the predicate four endpoints share. As-of-now numbers must not move: the fix concerns history only.

- [ ] **Step 1: Capture the golden master BEFORE Task 4's rewrite**

This step runs against the **unmodified** `active_as_of`. If Task 4 is already committed, check out the parent commit into a scratch worktree to capture these numbers, then return.

On a seeded database, record for `as_of = today`: the count of active holds, the top-5 hold ids from the top-N query in `active_as_of` order, and the chronic-hold ids. Write them into the test as literals, with a comment naming the commit they were captured at.

- [ ] **Step 2: Write the invariance test**

```python
def test_as_of_today_is_unchanged_by_the_history_rewrite(db_session, seeded_holds):
    """The fix targets historical as-of dates. Today's dashboards must not move.

    Golden values captured against active_as_of at <commit sha>, before the
    status arm was rewritten.
    """
    today = date.today()

    active = _active_ids(db_session, today)

    assert active == GOLDEN_ACTIVE_IDS_TODAY
```

`seeded_holds` builds a fixed set of holds spanning every status in `HoldStatus`, half with transition history and half without, so the assertion covers both the history path and the fallback path.

- [ ] **Step 3: Run it to verify it passes**

Run: `pytest tests/test_calculations/test_hold_status_history.py -v -k invariance`
Expected: PASS. A failure here means the rewrite changed as-of-now behaviour and must be investigated before merge — that is the defect this test exists to catch.

- [ ] **Step 4: Write the trend-endpoint regression test**

The predicate tests in Task 4 prove the SQL is right. This proves the endpoint that motivated the whole change actually reports differently — the spec asks for it by name.

```python
def test_trend_reflects_history_not_current_status(client, admin_token, hold_with_history):
    """GET /api/kpi/wip-aging/trend is the one caller that walks past dates.

    The pending-then-approved hold was NOT aging WIP on 2026-03-03 and WAS on
    2026-03-06. Before this change the trend counted it on both days, because
    it read today's ON_HOLD status for every point on the line.
    """
    response = client.get(
        "/api/kpi/wip-aging/trend",
        params={"start_date": "2026-03-02", "end_date": "2026-03-07"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200

    points = {p["date"]: p for p in response.json()["trend"]}

    assert points["2026-03-03"]["active_holds"] == 1
    assert points["2026-03-06"]["active_holds"] == 2
```

Read the endpoint's actual response shape from `backend/routes/holds.py:510` before writing the assertions — use its real key names, not the ones guessed here, and assert one exact value per point.

- [ ] **Step 5: Run it to verify it fails for the right reason**

Run: `pytest tests/test_calculations/test_hold_status_history.py -v -k trend`
Expected against the pre-Task-4 predicate: FAIL on the `2026-03-03` assertion with `2 == 1`, because current-status logic counts the pending hold. Against the rewritten predicate: PASS.

If you reach this step after Task 4 is already committed, check out its parent in a scratch worktree, run the test there, and paste that failure output. A regression test never observed failing is not evidence.

- [ ] **Step 6: Write the query-plan guard**

The correlated subquery must not turn the indexed top-N scan into a full scan. This repo has been bitten by exactly this class before, so assert the plan, not just the result:

```python
def test_top_n_query_still_uses_an_index(db_session, seeded_holds):
    """active_as_of's docstring promises callers keep index-assisted
    ORDER BY ... LIMIT. A correlated subquery must not cost them that.

    The plan is taken from a query built WITH the predicate — explaining a
    hand-written SQL string instead would pass no matter what active_as_of
    does, which is no test at all.
    """
    query = (
        db_session.query(HoldEntry.hold_entry_id)
        .filter(active_as_of(date(2026, 3, 10)))
        .order_by(HoldEntry.hold_date)
        .limit(5)
    )
    compiled = query.statement.compile(
        db_session.bind, compile_kwargs={"literal_binds": True}
    )
    plan = db_session.execute(text(f"EXPLAIN QUERY PLAN {compiled}")).fetchall()

    assert not any("SCAN HOLD_ENTRY" in str(row) for row in plan)
```

SQLite's `EXPLAIN QUERY PLAN` distinguishes `SCAN` from `SEARCH`. The MariaDB equivalent lands in Task 6.

- [ ] **Step 7: Run it**

Run: `pytest tests/test_calculations/test_hold_status_history.py -v -k index`
Expected: PASS. If it fails, the index on `hold_date` is not being used and the predicate needs rework before merge — report it rather than deleting the test.

- [ ] **Step 8: Commit**

```bash
git add backend/tests/test_calculations/test_hold_status_history.py
git commit -m "test(kpi): trend regression, as-of-now invariance, query-plan guard"
```

---

### Task 6: MariaDB portability

**Files:**
- Modify: `backend/tests/test_mariadb_portability.py` (append)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing consumed downstream.

SQLite cannot catch this repo's recurring bug class. `holds.py`'s `julianday()` defect reached production precisely because the SQLite suite was green.

- [ ] **Step 1: Write the tests**

Follow the existing `mariadb_boundary_holds` fixture pattern at `tests/test_mariadb_portability.py:414`:

```python
def test_active_as_of_history_lookup_executes_on_mariadb(mariadb_hold_history):
    """The correlated scalar subquery with ORDER BY + LIMIT must execute on
    MariaDB, not just SQLite."""
    session, ids = mariadb_hold_history

    active = {h.hold_entry_id for h in session.query(HoldEntry).filter(active_as_of(date(2026, 3, 3))).all()}

    assert active == {ids["held_then_cancelled"]}


def test_same_second_transitions_resolve_on_mariadb(mariadb_hold_history):
    """MariaDB DATETIME truncates to whole seconds, so the tie-break on
    transition_id is load-bearing here in a way it is not on SQLite."""
    session, ids = mariadb_hold_history

    active = {h.hold_entry_id for h in session.query(HoldEntry).filter(active_as_of(date(2026, 3, 5))).all()}

    assert ids["same_second"] not in active


def test_top_n_with_history_predicate_uses_index_on_mariadb(mariadb_hold_history):
    """Explains the query built WITH active_as_of, not a hand-written string —
    a literal SQL string would pass regardless of what the predicate does."""
    session, _ = mariadb_hold_history

    query = (
        session.query(HoldEntry.hold_entry_id)
        .filter(active_as_of(date(2026, 3, 10)))
        .order_by(HoldEntry.hold_date)
        .limit(5)
    )
    compiled = query.statement.compile(session.bind, compile_kwargs={"literal_binds": True})
    plan = session.execute(text(f"EXPLAIN {compiled}")).fetchall()

    assert not any("Using filesort" in str(row) for row in plan)
```

`mariadb_hold_history` mirrors the SQLite fixtures from Task 4 against the `mariadb_schema` engine, writing microsecond-free datetimes since the column stores whole seconds. It must insert the same-second pair with distinct `transition_id`s.

- [ ] **Step 2: Run against MariaDB**

Run: `pytest tests/test_mariadb_portability.py -v --no-cov`
Expected: all pass. If MariaDB is unavailable locally, state that plainly in the report and rely on CI's `mariadb-portability` job — never report an unobserved pass.

- [ ] **Step 3: Run the whole suite**

Run: `pytest tests/`
Expected: green, coverage ≥ 75%.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_mariadb_portability.py
git commit -m "test(kpi): MariaDB portability for hold-status history lookup"
```

---

## Verification before opening the PR

- [ ] `pytest tests/` green from `backend/`, coverage ≥ 75%
- [ ] `pytest tests/test_mariadb_portability.py -v --no-cov` green
- [ ] `pytest tests/test_audit/test_registry_guards.py -v` green (new table classified)
- [ ] `pre-commit run --all-files` clean
- [ ] `alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` runs cleanly on a scratch database — the downgrade path is real, not decorative
- [ ] `/cross-review` run for the final HEAD (the PreToolUse gate blocks `gh pr create` without it; run `git checkout` as its **own** command before marking, never chained with `&&`)
