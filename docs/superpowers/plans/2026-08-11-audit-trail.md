# Audit Trail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a queryable, admin-readable trail of who changed which entity, when, and what each field's value was before and after.

**Architecture:** A SQLAlchemy `before_flush` listener inspects allow-listed models in the session's new/dirty/deleted sets, computes per-field before→after diffs from attribute history, redacts secrets, and stages `AUDIT_ENTRY` rows into the *same* transaction — so a rolled-back change can never leave an entry. The acting user reaches the listener through a `ContextVar` set by the auth dependency, because ORM hooks have no request object. Two structural guard tests keep the table allow-list and the redaction set from drifting.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x (`Mapped`/`mapped_column`), FastAPI, Alembic, pytest. MariaDB in production, SQLite in most tests.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-08-11-audit-trail-design.md`. Every decision there is an owner ruling; do not revisit them in code.
- **Alembic is the only schema mechanism.** No `create_all`. New revision id `0005_audit_trail`, `down_revision = "0004_labor_hours"`.
- **Audited tables (exactly these 14):** `WORK_ORDER`, `HOLD_ENTRY`, `USER`, `CLIENT`, `CLIENT_CONFIG`, `EMPLOYEE`, `EMPLOYEE_CLIENT_ASSIGNMENT`, `EMPLOYEE_LINE_ASSIGNMENT`, `KPI_THRESHOLD`, `HOLD_REASON_CATALOG`, `HOLD_STATUS_CATALOG`, `USER_CLIENT_ASSIGNMENT`, `DEFECT_TYPE_CATALOG`, `ALERT_CONFIG`.
- **Redacted fields:** `{"password_hash"}`.
- **Reads are admin-only** via `from backend.auth.jwt import get_current_admin`.
- **No purge job. No backfill.** The trail starts at deploy.
- **No permissive assertions.** Never `assert x in [200, 404]`; assert one expected status per test.
- **Portable SQL only.** Use `backend.db.sql_functions` / `backend.db.dialects`; never SQLite-only functions such as `julianday()`.
- **`DateTime` range boundaries use next-midnight**, not date-at-midnight.
- **Adding routes requires regenerating** `backend/tests/test_bootstrap/openapi_surface.json`.
- Backend tests run from `backend/` with `pytest tests/`. Coverage gate ≥75%.

---

## File Structure

**Phase A1 — capture core (no API surface)**

| file | responsibility |
|---|---|
| `backend/audit/__init__.py` | package marker; re-exports `audit_suppressed` |
| `backend/audit/context.py` | `ContextVar` for the acting user + `audit_suppressed()` |
| `backend/audit/registry.py` | `AUDITED_TABLES`, `EXCLUDED_TABLES`, `REDACTED_FIELDS` — the single source both guards read |
| `backend/audit/capture.py` | `before_flush` listener; diffing, redaction, row staging |
| `backend/orm/audit_entry.py` | `AuditEntry` model (`AUDIT_ENTRY`) |
| `backend/alembic/versions/0005_audit_trail.py` | creates `AUDIT_ENTRY` |
| `backend/tests/test_audit/test_context.py` | contextvar + suppression |
| `backend/tests/test_audit/test_registry_guards.py` | the two structural guards |
| `backend/tests/test_audit/test_capture.py` | diffs, redaction, transactionality |

**Phase A2 — read API**

| file | responsibility |
|---|---|
| `backend/schemas/audit.py` | response models |
| `backend/routes/audit.py` | the two admin-only endpoints |
| `backend/tests/test_audit/test_audit_routes.py` | behaviour + authorization matrix |

Modified: `backend/auth/jwt.py` (set the contextvar), `backend/bootstrap/app_config.py` (register listener), `backend/bootstrap/routers.py` (A2), `backend/scripts/seed_sample_client.py` and `backend/services/csv_upload_processor.py` (suppression).

---

# PHASE A1 — CAPTURE CORE

### Task 1: Acting-user context and suppression

**Files:**
- Create: `backend/audit/__init__.py`, `backend/audit/context.py`
- Test: `backend/tests/test_audit/test_context.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `current_actor: ContextVar[str | None]`; `set_actor(user_id: str | None) -> Token`; `get_actor() -> str | None`; `audit_suppressed() -> ContextManager[None]`; `is_suppressed() -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_audit/test_context.py
"""Acting-user context and suppression for audit capture.

ORM flush hooks have no request object, so the acting user travels through a
ContextVar set by the auth dependency.
"""

from backend.audit.context import audit_suppressed, get_actor, is_suppressed, set_actor


def test_actor_defaults_to_none():
    assert get_actor() is None


def test_set_actor_round_trips():
    from backend.audit.context import current_actor

    token = set_actor("user-123")
    try:
        assert get_actor() == "user-123"
    finally:
        current_actor.reset(token)
    assert get_actor() is None


def test_not_suppressed_by_default():
    assert is_suppressed() is False


def test_audit_suppressed_suppresses_inside_only():
    assert is_suppressed() is False
    with audit_suppressed():
        assert is_suppressed() is True
    assert is_suppressed() is False


def test_audit_suppressed_restores_on_exception():
    try:
        with audit_suppressed():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert is_suppressed() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_context.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.audit'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/audit/__init__.py
"""Audit trail: entity-level change capture.

See docs/superpowers/specs/2026-08-11-audit-trail-design.md.
"""

from backend.audit.context import audit_suppressed

__all__ = ["audit_suppressed"]
```

```python
# backend/audit/context.py
"""Request-scoped context for audit capture.

SQLAlchemy flush hooks run without a request object, so they cannot read
``request.state.user_id``. The acting user is carried here instead, set by the
auth dependency at the same point ``request.state.user_id`` is assigned so
attribution has one source of truth.
"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

current_actor: ContextVar[Optional[str]] = ContextVar("audit_current_actor", default=None)
_suppressed: ContextVar[bool] = ContextVar("audit_suppressed", default=False)


def set_actor(user_id: Optional[str]) -> Token:
    """Record the acting user. Returns a token the caller may reset with."""
    return current_actor.set(user_id)


def get_actor() -> Optional[str]:
    """The acting user, or None for system-initiated writes."""
    return current_actor.get()


def is_suppressed() -> bool:
    """True when the current context has opted out of audit capture."""
    return _suppressed.get()


@contextmanager
def audit_suppressed() -> Iterator[None]:
    """Opt out of audit capture for deliberate bulk work.

    Used by the demo seeder and CSV importers, which write thousands of rows
    that carry no decision. Deliberately narrow: unsuppressed bulk writes are
    still captured, so this cannot become an ambient default.
    """
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_context.py -v --no-cov`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/audit/__init__.py backend/audit/context.py backend/tests/test_audit/test_context.py
git commit -m "feat(audit): acting-user context and suppression"
```

---

### Task 2: Registry and the table-completeness guard

**Files:**
- Create: `backend/audit/registry.py`
- Test: `backend/tests/test_audit/test_registry_guards.py`

**Interfaces:**
- Consumes: Task 1 (none directly).
- Produces: `AUDITED_TABLES: frozenset[str]`; `EXCLUDED_TABLES: dict[str, str]` (table → reason); `REDACTED_FIELDS: frozenset[str]`; `is_audited(table_name: str) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_audit/test_registry_guards.py
"""Structural guards over the audit registry.

These exist because an allow-list drifts: a new table gets added and nobody
classifies it, so it is silently unaudited. The guard turns that into a
failing build instead of a quiet gap.
"""

import pytest

from backend.audit.registry import AUDITED_TABLES, EXCLUDED_TABLES, REDACTED_FIELDS, is_audited
from backend.database import Base

SENSITIVE_PATTERN = ("password", "token", "secret", "api_key", "hash")


def _all_orm_tables() -> set:
    return set(Base.metadata.tables.keys())


def test_every_orm_table_is_classified():
    """Every table is audited or excluded-with-a-reason. No third state."""
    classified = set(AUDITED_TABLES) | set(EXCLUDED_TABLES)
    unclassified = sorted(_all_orm_tables() - classified)
    assert unclassified == [], (
        "These ORM tables are neither audited nor excluded. Add each to "
        "AUDITED_TABLES, or to EXCLUDED_TABLES with a reason: " + ", ".join(unclassified)
    )


def test_no_table_is_both_audited_and_excluded():
    overlap = sorted(set(AUDITED_TABLES) & set(EXCLUDED_TABLES))
    assert overlap == [], f"Tables in both sets: {overlap}"


def test_registry_references_only_real_tables():
    """A renamed or dropped table must not linger in the registry."""
    real = _all_orm_tables()
    stale = sorted((set(AUDITED_TABLES) | set(EXCLUDED_TABLES)) - real)
    assert stale == [], f"Registry names tables that do not exist: {stale}"


def test_every_exclusion_states_a_reason():
    thin = sorted(t for t, reason in EXCLUDED_TABLES.items() if len(reason.strip()) < 15)
    assert thin == [], f"Exclusions need a real reason, not a placeholder: {thin}"


def test_audited_tables_matches_the_spec():
    """Pinned to the spec's 14 tables so scope changes are deliberate."""
    assert AUDITED_TABLES == frozenset(
        {
            "WORK_ORDER",
            "HOLD_ENTRY",
            "USER",
            "CLIENT",
            "CLIENT_CONFIG",
            "EMPLOYEE",
            "EMPLOYEE_CLIENT_ASSIGNMENT",
            "EMPLOYEE_LINE_ASSIGNMENT",
            "KPI_THRESHOLD",
            "HOLD_REASON_CATALOG",
            "HOLD_STATUS_CATALOG",
            "USER_CLIENT_ASSIGNMENT",
            "DEFECT_TYPE_CATALOG",
            "ALERT_CONFIG",
        }
    )


def test_no_audited_table_exposes_an_unredacted_secret():
    """Redaction completeness: a FUTURE sensitive column must fail CI."""
    leaks = []
    for table_name in AUDITED_TABLES:
        table = Base.metadata.tables.get(table_name)
        if table is None:
            continue
        for column in table.columns:
            lowered = column.name.lower()
            if any(p in lowered for p in SENSITIVE_PATTERN) and column.name not in REDACTED_FIELDS:
                leaks.append(f"{table_name}.{column.name}")
    assert sorted(leaks) == [], (
        "These columns look sensitive but are not in REDACTED_FIELDS, so their "
        "values would be written into AUDIT_ENTRY.changes: " + ", ".join(sorted(leaks))
    )


def test_is_audited_reflects_the_allow_list():
    assert is_audited("HOLD_ENTRY") is True
    assert is_audited("METRIC_CALCULATION_RESULT") is False
    assert is_audited("NOT_A_TABLE") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_registry_guards.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.audit.registry'`

- [ ] **Step 3: Write minimal implementation**

Build `EXCLUDED_TABLES` by listing every remaining table in `Base.metadata`. Run this helper once to enumerate them, then paste the result and replace each reason with a real one:

```bash
cd backend && .venv/bin/python -c "
from backend.database import Base
import backend.orm  # noqa: F401  (registers all models)
audited = {'WORK_ORDER','HOLD_ENTRY','USER','CLIENT','CLIENT_CONFIG','EMPLOYEE','EMPLOYEE_CLIENT_ASSIGNMENT','EMPLOYEE_LINE_ASSIGNMENT','KPI_THRESHOLD','HOLD_REASON_CATALOG','HOLD_STATUS_CATALOG'}
for t in sorted(set(Base.metadata.tables) - audited):
    print(f'    \"{t}\": \"\",')
"
```

```python
# backend/audit/registry.py
"""What the audit trail covers, and what it deliberately does not.

Scope is human decisions only (spec section 2). Machine-written tables are
excluded because auditing them produces a permanent stream of "the scheduler
recalculated things" — METRIC_CALCULATION_RESULT is written daily by
tasks/dual_view_calculation.py and already self-audits via its own
calculated_by field.

Both sets are enforced by guards in tests/test_audit/test_registry_guards.py:
every ORM table must appear in exactly one of them.
"""

from typing import Dict, FrozenSet

#: Tables where a person makes a decision worth attributing.
AUDITED_TABLES: FrozenSet[str] = frozenset(
    {
        "WORK_ORDER",  # status transitions, dates, quantities
        "HOLD_ENTRY",  # placing, releasing, re-reasoning holds
        "USER",  # account creation, role changes, activation
        "CLIENT",  # tenant lifecycle
        "CLIENT_CONFIG",  # per-tenant behaviour switches
        "EMPLOYEE",  # workforce record changes
        "EMPLOYEE_CLIENT_ASSIGNMENT",  # who works for which tenant
        "EMPLOYEE_LINE_ASSIGNMENT",  # line staffing decisions
        "KPI_THRESHOLD",  # the targets performance is judged against
        "HOLD_REASON_CATALOG",  # taxonomy edits reshape historical reporting
        "HOLD_STATUS_CATALOG",  # taxonomy edits reshape historical reporting
        "USER_CLIENT_ASSIGNMENT",  # access-control grant read by middleware/client_auth.py
        "DEFECT_TYPE_CATALOG",  # taxonomy edits reshape historical reporting
        "ALERT_CONFIG",  # per-client thresholds + enabled flag; mirrors KPI_THRESHOLD
    }
)

#: Every other ORM table, with why it is not audited. Filled from the helper
#: command in the plan; each reason must be real, not a placeholder.
EXCLUDED_TABLES: Dict[str, str] = {
    "AUDIT_ENTRY": "the audit trail itself; auditing it would recurse",
    "METRIC_CALCULATION_RESULT": "cron-written daily by dual_view_calculation; self-audits via calculated_by",
    "ATTENDANCE_HOUR_ALLOCATION": "derived splits rewritten whenever attendance changes",
    # ... remaining tables, each with a stated reason
}

#: Column names whose values are never written into AUDIT_ENTRY.changes.
REDACTED_FIELDS: FrozenSet[str] = frozenset({"password_hash"})


def is_audited(table_name: str) -> bool:
    """True when changes to this table should be recorded."""
    return table_name in AUDITED_TABLES
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_registry_guards.py -v --no-cov`
Expected: PASS (7 tests). If `test_every_orm_table_is_classified` fails, its message lists exactly which tables still need a reason — add them.

- [ ] **Step 5: Negative-test both guards (REQUIRED — do not skip)**

A guard that has never failed is not known to work. Prove each one fires:

```bash
cd backend
# (a) completeness guard: temporarily drop a table from EXCLUDED_TABLES
#     -> test_every_orm_table_is_classified MUST fail naming that table
# (b) redaction guard: temporarily remove "password_hash" from REDACTED_FIELDS
#     -> test_no_audited_table_exposes_an_unredacted_secret MUST fail naming USER.password_hash
.venv/bin/python -m pytest tests/test_audit/test_registry_guards.py -v --no-cov
# restore both, confirm green again
```

Record both observed failure messages in the PR description.

- [ ] **Step 6: Commit**

```bash
git add backend/audit/registry.py backend/tests/test_audit/test_registry_guards.py
git commit -m "feat(audit): registry with table-completeness and redaction guards"
```

---

### Task 3: AUDIT_ENTRY model and Alembic 0005

**Files:**
- Create: `backend/orm/audit_entry.py`, `backend/alembic/versions/0005_audit_trail.py`
- Modify: `backend/orm/__init__.py` (export the model so `Base.metadata` sees it)
- Test: `backend/tests/test_audit/test_audit_model.py`

**Interfaces:**
- Consumes: Task 2 (`AUDITED_TABLES` for the guard).
- Produces: `AuditEntry` with fields `entry_id, occurred_at, actor_user_id, actor_username, table_name, record_pk, operation, changes, client_id, request_method, request_path`; `AuditOperation` enum with `INSERT`, `UPDATE`, `DELETE`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_audit/test_audit_model.py
"""AUDIT_ENTRY shape and migration parity."""

from datetime import datetime, timezone

from backend.database import Base
from backend.orm.audit_entry import AuditEntry, AuditOperation


def test_table_is_registered_with_expected_columns():
    table = Base.metadata.tables["AUDIT_ENTRY"]
    expected = {
        "entry_id",
        "occurred_at",
        "actor_user_id",
        "actor_username",
        "table_name",
        "record_pk",
        "operation",
        "changes",
        "client_id",
        "request_method",
        "request_path",
    }
    assert set(table.columns.keys()) == expected


def test_lookup_indexes_exist():
    """(table_name, record_pk) backs the entity-history query."""
    table = Base.metadata.tables["AUDIT_ENTRY"]
    indexed = {tuple(c.name for c in idx.columns) for idx in table.indexes}
    assert ("table_name", "record_pk") in indexed


def test_row_round_trips(transactional_db):
    entry = AuditEntry(
        occurred_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        actor_user_id="user-1",
        actor_username="alice",
        table_name="HOLD_ENTRY",
        record_pk="HOLD-1",
        operation=AuditOperation.UPDATE,
        changes={"hold_status": {"old": "ON_HOLD", "new": "RELEASED"}},
        client_id="CLIENT-1",
        request_method="PUT",
        request_path="/api/holds/HOLD-1",
    )
    transactional_db.add(entry)
    transactional_db.flush()

    stored = transactional_db.query(AuditEntry).filter_by(record_pk="HOLD-1").one()
    assert stored.operation == AuditOperation.UPDATE
    assert stored.changes["hold_status"]["new"] == "RELEASED"
    assert stored.actor_username == "alice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_audit_model.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.orm.audit_entry'`

- [ ] **Step 3: Write the model**

```python
# backend/orm/audit_entry.py
"""
AUDIT_ENTRY table ORM schema (SQLAlchemy)
Entity-level change trail: who changed what, when, and from what to what.
"""

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AuditOperation(str, enum.Enum):
    """The kind of change recorded."""

    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditEntry(Base):
    """AUDIT_ENTRY table - one row per audited entity change."""

    __tablename__ = "AUDIT_ENTRY"
    __table_args__ = (
        Index("ix_audit_entity", "table_name", "record_pk"),
        {"extend_existing": True},
    )

    entry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Actor. NULL user id means system-initiated (scheduler, migration, CLI).
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    # Snapshot, deliberately not a FK: audit history must stay readable after a
    # user is renamed or deactivated, which is exactly when it is needed.
    actor_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    table_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Stringified single-column PK; every ORM table was verified to have one.
    record_pk: Mapped[str] = mapped_column(String(64), nullable=False)

    operation: Mapped[AuditOperation] = mapped_column(Enum(AuditOperation), nullable=False)

    #: {field: {"old": ..., "new": ...}}, with REDACTED_FIELDS masked.
    changes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Captured now though reads are admin-only: adding it later would need a
    # backfill over rows whose tenant can no longer be reconstructed.
    client_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    request_method: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    request_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

Add to `backend/orm/__init__.py` alongside the existing exports:

```python
from backend.orm.audit_entry import AuditEntry, AuditOperation  # noqa: F401
```

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/0005_audit_trail.py
"""Audit trail table (Project A, PR A1).

Revision ID: 0005_audit_trail
Revises: 0004_labor_hours
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_audit_trail"
down_revision: Union[str, None] = "0004_labor_hours"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "AUDIT_ENTRY",
        sa.Column("entry_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=50), nullable=True),
        sa.Column("actor_username", sa.String(length=100), nullable=True),
        sa.Column("table_name", sa.String(length=64), nullable=False),
        sa.Column("record_pk", sa.String(length=64), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("INSERT", "UPDATE", "DELETE", name="auditoperation"),
            nullable=False,
        ),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("client_id", sa.String(length=50), nullable=True),
        sa.Column("request_method", sa.String(length=8), nullable=True),
        sa.Column("request_path", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index("ix_audit_entity", "AUDIT_ENTRY", ["table_name", "record_pk"])
    op.create_index(op.f("ix_AUDIT_ENTRY_occurred_at"), "AUDIT_ENTRY", ["occurred_at"])
    op.create_index(op.f("ix_AUDIT_ENTRY_actor_user_id"), "AUDIT_ENTRY", ["actor_user_id"])
    op.create_index(op.f("ix_AUDIT_ENTRY_table_name"), "AUDIT_ENTRY", ["table_name"])
    op.create_index(op.f("ix_AUDIT_ENTRY_client_id"), "AUDIT_ENTRY", ["client_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_AUDIT_ENTRY_client_id"), table_name="AUDIT_ENTRY")
    op.drop_index(op.f("ix_AUDIT_ENTRY_table_name"), table_name="AUDIT_ENTRY")
    op.drop_index(op.f("ix_AUDIT_ENTRY_actor_user_id"), table_name="AUDIT_ENTRY")
    op.drop_index(op.f("ix_AUDIT_ENTRY_occurred_at"), table_name="AUDIT_ENTRY")
    op.drop_index("ix_audit_entity", table_name="AUDIT_ENTRY")
    op.drop_table("AUDIT_ENTRY")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_audit_model.py -v --no-cov`
Expected: PASS (3 tests)

The existing baseline-parity test asserts the migrated schema equals `Base.metadata`. Run it:

Run: `cd backend && .venv/bin/python -m pytest tests/ -k "baseline or create_all or alembic" -v --no-cov`
Expected: PASS. A mismatch here means the migration and model disagree — fix the migration, never the guard.

- [ ] **Step 6: Commit**

```bash
git add backend/orm/audit_entry.py backend/orm/__init__.py \
        backend/alembic/versions/0005_audit_trail.py backend/tests/test_audit/test_audit_model.py
git commit -m "feat(audit): AUDIT_ENTRY model and Alembic 0005"
```

---

### Task 4: Capture listener — diffs for insert, update and delete

**Files:**
- Create: `backend/audit/capture.py`
- Test: `backend/tests/test_audit/test_capture.py`

**Interfaces:**
- Consumes: Task 1 (`get_actor`, `is_suppressed`), Task 2 (`is_audited`, `REDACTED_FIELDS`), Task 3 (`AuditEntry`, `AuditOperation`).
- Produces: `register_audit_listener() -> None`; `unregister_audit_listener() -> None`.
  (**Superseded during implementation:** the original design also declared
  `build_entries(session)`. The adversarial review forced a redesign from
  `before_flush` + `session.info` + `after_flush` to mapper-level `after_insert`
  writing via Core on the flush's own connection, which removed the concept of
  batch-building entries from a session. `build_entries` no longer exists.)

> ⚠️ **The implementation code in this task is SUPERSEDED — kept as the historical
> record of what was attempted, not as instructions.** An adversarial review proved
> the `before_flush` + `session.info` + `after_flush` design below is unsound: state
> parked in `session.info` survives a *failed* flush (SQLAlchemy does not clear user
> `session.info` on rollback) and drains into the next successful flush, writing a
> phantom audit row for a record that was never created, attributed to whichever
> actor is acting then. The shipped design (commit `f7b288d`) instead uses
> mapper-level `after_insert(mapper, connection, target)` writing via Core on the
> flush's own connection, plus `_force_active_history_for_audited_tables()` to stop
> `expire_on_commit=True` recording `old: None`. `build_entries` does not exist in
> the shipped code. **Read `backend/audit/capture.py` for the real implementation.**

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_audit/test_capture.py
"""Audit capture: diffs, redaction, suppression, transactionality."""

from backend.audit.capture import register_audit_listener
from backend.audit.context import audit_suppressed, set_actor, current_actor
from backend.orm.audit_entry import AuditEntry, AuditOperation
from backend.orm.kpi_threshold import KPIThreshold
from backend.tests.fixtures.factories import TestDataFactory


def _entries(db):
    return db.query(AuditEntry).order_by(AuditEntry.entry_id).all()


def test_insert_is_captured_with_no_old_values(transactional_db):
    register_audit_listener()
    token = set_actor("user-1")
    try:
        client = TestDataFactory.create_client(transactional_db, client_id="AUD-C1", client_name="Audit Co")
        transactional_db.flush()
    finally:
        current_actor.reset(token)

    rows = [e for e in _entries(transactional_db) if e.table_name == "CLIENT"]
    assert len(rows) == 1
    assert rows[0].operation == AuditOperation.INSERT
    assert rows[0].record_pk == "AUD-C1"
    assert rows[0].actor_user_id == "user-1"
    assert rows[0].changes["client_name"]["old"] is None
    assert rows[0].changes["client_name"]["new"] == "Audit Co"


def test_update_records_before_and_after(transactional_db):
    register_audit_listener()
    threshold = KPIThreshold(threshold_id="AUD-T1", kpi_key="efficiency", target_value=80.0)
    transactional_db.add(threshold)
    transactional_db.flush()

    threshold.target_value = 90.0
    transactional_db.flush()

    updates = [
        e for e in _entries(transactional_db)
        if e.table_name == "KPI_THRESHOLD" and e.operation == AuditOperation.UPDATE
    ]
    assert len(updates) == 1
    assert updates[0].changes == {"target_value": {"old": 80.0, "new": 90.0}}


def test_no_op_write_produces_no_entry(transactional_db):
    """Setting a field to its existing value is not a change."""
    register_audit_listener()
    threshold = KPIThreshold(threshold_id="AUD-T2", kpi_key="oee", target_value=75.0)
    transactional_db.add(threshold)
    transactional_db.flush()
    before = len(_entries(transactional_db))

    threshold.target_value = 75.0
    transactional_db.flush()

    assert len(_entries(transactional_db)) == before


def test_delete_is_captured(transactional_db):
    register_audit_listener()
    threshold = KPIThreshold(threshold_id="AUD-T3", kpi_key="fpy", target_value=99.0)
    transactional_db.add(threshold)
    transactional_db.flush()

    transactional_db.delete(threshold)
    transactional_db.flush()

    deletes = [e for e in _entries(transactional_db) if e.operation == AuditOperation.DELETE]
    assert len(deletes) == 1
    assert deletes[0].record_pk == "AUD-T3"


def test_unaudited_table_is_ignored(transactional_db):
    """METRIC_CALCULATION_RESULT is excluded; writing one records nothing."""
    register_audit_listener()
    before = len(_entries(transactional_db))
    TestDataFactory.create_client(transactional_db, client_id="AUD-C2", client_name="Kept")
    transactional_db.flush()
    rows = [e for e in _entries(transactional_db) if e.table_name == "METRIC_CALCULATION_RESULT"]
    assert rows == []
    assert len(_entries(transactional_db)) > before  # the CLIENT insert WAS captured


def test_suppressed_writes_are_not_captured(transactional_db):
    register_audit_listener()
    with audit_suppressed():
        TestDataFactory.create_client(transactional_db, client_id="AUD-C3", client_name="Seeded")
        transactional_db.flush()
    assert [e for e in _entries(transactional_db) if e.record_pk == "AUD-C3"] == []


def test_unsuppressed_bulk_write_is_still_captured(transactional_db):
    """The opt-out must stay deliberate: bulk alone does not exempt."""
    register_audit_listener()
    for i in range(3):
        TestDataFactory.create_client(transactional_db, client_id=f"AUD-B{i}", client_name=f"Bulk {i}")
    transactional_db.flush()
    rows = [e for e in _entries(transactional_db) if e.record_pk.startswith("AUD-B")]
    assert len(rows) == 3


def test_password_hash_is_redacted(transactional_db):
    """The field is recorded as changed; neither hash value is persisted."""
    register_audit_listener()
    user = TestDataFactory.create_user(
        transactional_db, user_id="AUD-U1", username="aud_user", role="operator", client_id=None
    )
    transactional_db.flush()

    user.password_hash = "$argon2id$v=19$brand-new-hash"
    transactional_db.flush()

    updates = [
        e for e in _entries(transactional_db)
        if e.table_name == "USER" and e.operation == AuditOperation.UPDATE
    ]
    assert len(updates) == 1
    recorded = updates[0].changes["password_hash"]
    assert recorded == {"old": "[redacted]", "new": "[redacted]"}
    assert "argon2" not in str(updates[0].changes)


def test_actor_is_system_when_unset(transactional_db):
    register_audit_listener()
    TestDataFactory.create_client(transactional_db, client_id="AUD-C4", client_name="No Actor")
    transactional_db.flush()
    row = [e for e in _entries(transactional_db) if e.record_pk == "AUD-C4"][0]
    assert row.actor_user_id is None
    assert row.actor_username == "system"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_capture.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.audit.capture'`

- [ ] **Step 3: Write the implementation**

```python
# backend/audit/capture.py
"""SQLAlchemy before_flush capture of entity-level changes.

before_flush rather than after_flush for two reasons that matter: old values
are still present in attribute history before the flush completes, and staged
audit rows join the SAME transaction — so a rolled-back change can never leave
an entry behind, and a committed change can never lack one.
"""

import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from backend.audit.context import get_actor, is_suppressed
from backend.audit.registry import REDACTED_FIELDS, is_audited
from backend.orm.audit_entry import AuditEntry, AuditOperation

_REDACTED = "[redacted]"
_listener_registered = False


def _jsonable(value: Any) -> Any:
    """Coerce a column value into something the JSON column accepts.

    Decimal becomes float, not str. Numeric before/after values must stay JSON
    numbers so consumers can compare them arithmetically — stringified Decimals
    are a bug class this codebase has already shipped to production once, where
    MariaDB returned "0.00" and the frontend had to coerce it back.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return str(value)


def _mask(field: str, value: Any) -> Any:
    return _REDACTED if field in REDACTED_FIELDS else _jsonable(value)


def _record_pk(obj: Any) -> str:
    """Stringified primary key. Every ORM table has a single-column PK."""
    state = inspect(obj)
    identity = state.mapper.primary_key_from_instance(obj)
    return str(identity[0])


def _client_id(obj: Any) -> Optional[str]:
    value = getattr(obj, "client_id", None)
    return str(value) if value is not None else None


def _insert_changes(obj: Any) -> Dict[str, Any]:
    changes: Dict[str, Any] = {}
    for column in inspect(obj).mapper.columns:
        value = getattr(obj, column.key, None)
        if value is None:
            continue
        changes[column.key] = {"old": None, "new": _mask(column.key, value)}
    return changes


def _update_changes(obj: Any) -> Dict[str, Any]:
    """Only genuinely modified columns. A no-op write yields {}."""
    state = inspect(obj)
    changes: Dict[str, Any] = {}
    for column in state.mapper.columns:
        history = state.attrs[column.key].history
        if not history.has_changes():
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        if old == new:
            continue
        changes[column.key] = {"old": _mask(column.key, old), "new": _mask(column.key, new)}
    return changes


def _delete_changes(obj: Any) -> Dict[str, Any]:
    changes: Dict[str, Any] = {}
    for column in inspect(obj).mapper.columns:
        value = getattr(obj, column.key, None)
        changes[column.key] = {"old": _mask(column.key, value), "new": None}
    return changes


def _entry(obj: Any, operation: AuditOperation, changes: Dict[str, Any]) -> AuditEntry:
    actor = get_actor()
    return AuditEntry(
        occurred_at=datetime.now(tz=timezone.utc),
        actor_user_id=actor,
        actor_username=actor if actor else "system",
        table_name=obj.__tablename__,
        record_pk=_record_pk(obj),
        operation=operation,
        changes=changes,
        client_id=_client_id(obj),
    )


def build_entries(session: Session) -> List[AuditEntry]:
    """Audit rows for everything pending in this session. Pure; adds nothing."""
    if is_suppressed():
        return []

    entries: List[AuditEntry] = []

    for obj in session.new:
        if not is_audited(getattr(obj, "__tablename__", "")):
            continue
        entries.append(_entry(obj, AuditOperation.INSERT, _insert_changes(obj)))

    for obj in session.dirty:
        if not is_audited(getattr(obj, "__tablename__", "")):
            continue
        changes = _update_changes(obj)
        if not changes:
            continue  # no-op write
        entries.append(_entry(obj, AuditOperation.UPDATE, changes))

    for obj in session.deleted:
        if not is_audited(getattr(obj, "__tablename__", "")):
            continue
        entries.append(_entry(obj, AuditOperation.DELETE, _delete_changes(obj)))

    return entries


def register_audit_listener() -> None:
    """Attach the before_flush listener. Idempotent."""
    global _listener_registered
    if _listener_registered:
        return

    @event.listens_for(Session, "before_flush")
    def _before_flush(session: Session, flush_context: Any, instances: Any) -> None:
        for entry in build_entries(session):
            session.add(entry)

    _listener_registered = True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_capture.py -v --no-cov`
Expected: PASS (9 tests)

If `test_insert_is_captured_with_no_old_values` reports a `record_pk` of `None`, the PK is assigned by the database on flush. Fix by staging INSERT entries from `session.new` only after their identity exists — move that branch into an `after_flush` companion, or require the PK to be set by the caller. Every audited table uses caller-assigned or autoincrement string/int PKs, so verify which case applies before changing the design.

- [ ] **Step 5: Commit**

```bash
git add backend/audit/capture.py backend/tests/test_audit/test_capture.py
git commit -m "feat(audit): before_flush capture with diffs, redaction and suppression"
```

---

### Task 5: Transactionality — a rolled-back change leaves nothing

**Files:**
- Modify: `backend/tests/test_audit/test_capture.py` (append)

**Interfaces:**
- Consumes: Task 4.
- Produces: nothing new.

This is the property `before_flush` was chosen for, so it is tested explicitly rather than assumed.

- [ ] **Step 1: Write the failing test**

The `transactional_db` fixture wraps each test in its own transaction with `join_transaction_mode="create_savepoint"`, so it cannot express "the outer transaction rolled back". Use a dedicated engine-backed session instead:

```python
# append to backend/tests/test_audit/test_capture.py
from sqlalchemy.orm import Session as SASession

from backend.audit.capture import register_audit_listener
from backend.orm.kpi_threshold import KPIThreshold


def test_rolled_back_change_leaves_zero_audit_rows(_txn_engine):
    """Audit rows share the change's transaction: roll back one, lose both."""
    register_audit_listener()

    connection = _txn_engine.connect()
    trans = connection.begin()
    session = SASession(bind=connection)
    try:
        session.add(KPIThreshold(threshold_id="AUD-RB1", kpi_key="rty", target_value=95.0))
        session.flush()
        # The entry exists inside the open transaction...
        staged = session.query(AuditEntry).filter_by(record_pk="AUD-RB1").count()
        assert staged == 1
    finally:
        session.close()
        trans.rollback()

    # ...and is gone once the transaction is discarded.
    verify_conn = _txn_engine.connect()
    verify_session = SASession(bind=verify_conn)
    try:
        surviving = verify_session.query(AuditEntry).filter_by(record_pk="AUD-RB1").count()
        assert surviving == 0
    finally:
        verify_session.close()
        verify_conn.close()
```

- [ ] **Step 2: Run test to verify it fails or passes for the right reason**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_capture.py::test_rolled_back_change_leaves_zero_audit_rows -v --no-cov`
Expected: PASS. If it fails at the *first* assertion (`staged == 1`), the listener is not firing. If it fails at the second, audit rows are escaping the transaction — that contradicts the design and must be fixed in `capture.py`, not in the test.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_audit/test_capture.py
git commit -m "test(audit): prove audit rows share the change's transaction"
```

---

### Task 6: Wire the listener and the actor into the running app

**Files:**
- Modify: `backend/auth/jwt.py:220` (set the contextvar), `backend/bootstrap/app_config.py` (register the listener)
- Test: `backend/tests/test_audit/test_audit_wiring.py`

**Interfaces:**
- Consumes: Tasks 1 and 4.
- Produces: attribution for real requests.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_audit/test_audit_wiring.py
"""The listener is registered, and the real auth dependency attributes the actor.

These are BEHAVIOURAL on purpose. An earlier draft asserted on module source
text (`"set_actor(" in inspect.getsource(jwt)`); that passes if the call
appears in a comment and breaks on harmless refactors — the green-while-dead
shape this codebase has been bitten by three times.

Note the trap this avoids: a TestClient test cannot use
`app.dependency_overrides[get_current_user]`, because that replaces the very
function under test. The real dependency is therefore called directly with a
real token.
"""

import pytest

from backend.audit import capture
from backend.audit.context import current_actor, get_actor
from backend.auth.jwt import create_access_token, get_current_user
from backend.tests.fixtures.factories import TestDataFactory


def test_listener_is_registered_at_app_startup():
    from backend.bootstrap import app_config  # noqa: F401  (import registers it)

    assert capture._listener_registered is True


def test_real_auth_dependency_sets_the_audit_actor(transactional_db):
    """Calling the REAL get_current_user must populate the audit contextvar."""

    class _FakeRequest:
        """Minimal stand-in exposing the .state the dependency writes to."""

        class _State:
            pass

        def __init__(self):
            self.state = _FakeRequest._State()

    user = TestDataFactory.create_user(
        transactional_db, user_id="wire-u1", username="wire_user", role="admin", client_id=None
    )
    transactional_db.commit()

    token = create_access_token(data={"sub": user.username, "role": user.role})
    request = _FakeRequest()

    # Reset first so a leaked value from another test cannot make this pass.
    reset_token = current_actor.set(None)
    try:
        resolved = get_current_user(request=request, token=token, db=transactional_db)
        assert resolved.user_id == "wire-u1"
        assert get_actor() == "wire-u1", (
            "get_current_user must set the audit contextvar; ORM flush hooks "
            "have no request object and read it instead."
        )
        # Same source of truth as the existing middleware attribution.
        assert request.state.user_id == "wire-u1"
    finally:
        current_actor.reset(reset_token)
```

**Implementer note:** `create_access_token` and `get_current_user`'s exact
signature must be read from `backend/auth/jwt.py` — match the real parameter
names and token payload keys rather than the illustrative ones above. If
`get_current_user` is `async`, await it or drive it with `anyio`/`asyncio.run`
following the pattern already used in `backend/tests/test_security/`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_audit_wiring.py -v --no-cov`
Expected: FAIL on `test_auth_dependency_sets_the_audit_actor` — `set_actor(...)` not present.

- [ ] **Step 3: Wire both**

In `backend/auth/jwt.py`, immediately after the existing line at ~220:

```python
    # Set user_id on request.state so AuditLogMiddleware can attribute actions correctly
    request.state.user_id = user.user_id
    # ...and on the audit contextvar, which ORM flush hooks read (they have no
    # request object). Same point, so attribution has one source of truth.
    set_actor(user.user_id)
```

with the import at the top of `jwt.py`:

```python
from backend.audit.context import set_actor
```

In `backend/bootstrap/app_config.py`, beside the existing middleware registration:

```python
from backend.audit.capture import register_audit_listener

# Attach ORM-level audit capture. Idempotent; safe under test re-imports.
register_audit_listener()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/ -v --no-cov`
Expected: PASS (all audit tests)

- [ ] **Step 5: Commit**

```bash
git add backend/auth/jwt.py backend/bootstrap/app_config.py backend/tests/test_audit/test_audit_wiring.py
git commit -m "feat(audit): register listener and attribute the acting user"
```

---

### Task 7: Suppress capture in the seeder and CSV importers

**Files:**
- Modify: `backend/scripts/seed_sample_client.py`, `backend/scripts/init_demo_database.py`, `backend/services/csv_upload_processor.py`
- Test: `backend/tests/test_audit/test_suppression_sites.py`

**Interfaces:**
- Consumes: Task 1 (`audit_suppressed`).
- Produces: nothing new.

Without this a `--reset` re-seed writes roughly 8,000 audit rows carrying no decision.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_audit/test_suppression_sites.py
"""Bulk writers must produce NO audit rows.

Behavioural on purpose. An earlier draft asserted `"audit_suppressed" in
inspect.getsource(module)`, which passes if the name appears in a comment and
proves nothing about what the seeder actually wrote.

Reuse the existing seeder test setup in
`backend/tests/test_scripts/test_seed_sample_client.py` — read that file for
the fixture and invocation pattern rather than inventing one.
"""

from backend.orm.audit_entry import AuditEntry


def _audit_count(db) -> int:
    return db.query(AuditEntry).count()


def test_sample_seeder_writes_no_audit_rows(transactional_db):
    """A --reset re-seed would otherwise emit ~8000 rows carrying no decision."""
    from backend.audit.capture import register_audit_listener
    from backend.scripts.seed_sample_client import seed_sample_client

    register_audit_listener()
    before = _audit_count(transactional_db)

    # Match the real signature from backend/scripts/seed_sample_client.py.
    seed_sample_client(transactional_db, client_id="SUPPRESS-TEST")
    transactional_db.flush()

    assert _audit_count(transactional_db) == before


def test_csv_upload_writes_no_audit_rows(transactional_db):
    """Bulk CSV import is data movement, not a per-row human decision."""
    from backend.audit.capture import register_audit_listener
    from backend.services import csv_upload_processor  # noqa: F401

    register_audit_listener()
    before = _audit_count(transactional_db)

    # Drive the processor exactly as tests/test_api/test_csv_upload_characterization.py
    # does; read that file for the helper it uses to build the upload payload.
    # ... invoke the processor here ...

    assert _audit_count(transactional_db) == before


def test_writes_outside_suppression_are_still_captured(transactional_db):
    """The opt-out must stay deliberate — it is not an ambient default."""
    from backend.audit.capture import register_audit_listener
    from backend.tests.fixtures.factories import TestDataFactory

    register_audit_listener()
    before = _audit_count(transactional_db)

    TestDataFactory.create_client(transactional_db, client_id="SUPP-CTRL", client_name="Control")
    transactional_db.flush()

    assert _audit_count(transactional_db) == before + 1
```

**Implementer note:** the third test is the control. Without it, all-zero
counts would also be satisfied by capture being broken entirely — the two
suppression tests alone cannot tell "suppression works" apart from "nothing
is ever captured". Read the real signatures for `seed_sample_client` and the
CSV processor before writing the calls; the names above are illustrative.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_suppression_sites.py -v --no-cov`
Expected: FAIL — all three assertions.

- [ ] **Step 3: Wrap each bulk entry point**

In each module, import and wrap the top-level write routine:

```python
from backend.audit import audit_suppressed

# ... inside the seeding / import entry point:
    with audit_suppressed():
        # existing bulk write body, unchanged
        ...
```

Wrap the outermost function that performs the writes, not each `session.add`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/ -v --no-cov`
Expected: PASS

Then confirm the seeder really writes nothing to the trail:

Run: `cd backend && .venv/bin/python -m pytest tests/test_scripts/ -v --no-cov`
Expected: PASS (existing seeder tests unaffected)

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_sample_client.py backend/scripts/init_demo_database.py \
        backend/services/csv_upload_processor.py backend/tests/test_audit/test_suppression_sites.py
git commit -m "feat(audit): suppress capture in seeders and CSV importers"
```

---

### Task 8: A1 gate — full suite, then open the PR

- [ ] **Step 1: Run the whole backend suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected: all pass; coverage ≥75%. Test count should be the prior total plus the new audit tests.

- [ ] **Step 2: Confirm the migration applies cleanly from scratch**

Run: `cd backend && .venv/bin/python -m pytest tests/ -k "baseline or alembic" -v --no-cov`
Expected: PASS — migrated schema equals `Base.metadata`.

- [ ] **Step 3: Cross-model review, then PR**

```bash
# from repo root, on the A1 branch
/cross-review          # required before gh pr create
gh pr create --base main --title "feat(audit): capture core (Project A, PR A1)" --body "..."
```

The PR body must include the two **observed guard failure messages** from Task 2 Step 5. A guard whose failure has not been demonstrated is not evidence.

---

# PHASE A2 — READ API

### Task 9: Response schemas and the list endpoint

**Files:**
- Create: `backend/schemas/audit.py`, `backend/routes/audit.py`
- Modify: `backend/bootstrap/routers.py`
- Test: `backend/tests/test_audit/test_audit_routes.py`

**Interfaces:**
- Consumes: Task 3 (`AuditEntry`, `AuditOperation`).
- Produces: `GET /api/audit`; `AuditEntryResponse`; `AuditListResponse` with fields `entries: list[AuditEntryResponse]`, `total: int`, `trail_started_at: datetime | None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_audit/test_audit_routes.py
"""Audit read API: behaviour and authorization."""

from datetime import datetime, timezone

from backend.orm.audit_entry import AuditEntry, AuditOperation


def _seed_entry(db, record_pk="HOLD-1", table_name="HOLD_ENTRY", actor="user-1"):
    db.add(
        AuditEntry(
            occurred_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
            actor_user_id=actor,
            actor_username="alice",
            table_name=table_name,
            record_pk=record_pk,
            operation=AuditOperation.UPDATE,
            changes={"hold_status": {"old": "ON_HOLD", "new": "RELEASED"}},
            client_id="CLIENT-1",
        )
    )
    db.flush()


def test_list_returns_entries_for_admin(admin_audit_client):
    client, db = admin_audit_client
    _seed_entry(db)

    response = client.get("/api/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["entries"][0]["table_name"] == "HOLD_ENTRY"
    assert body["entries"][0]["changes"]["hold_status"]["new"] == "RELEASED"


def test_list_filters_by_table_name(admin_audit_client):
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1", table_name="HOLD_ENTRY")
    _seed_entry(db, record_pk="WO-1", table_name="WORK_ORDER")

    response = client.get("/api/audit?table_name=WORK_ORDER")

    assert response.status_code == 200
    assert [e["record_pk"] for e in response.json()["entries"]] == ["WO-1"]


def test_list_reports_when_the_trail_started(admin_audit_client):
    """No backfill exists, so an absent old change is correct, not a bug."""
    client, db = admin_audit_client
    _seed_entry(db)

    body = client.get("/api/audit").json()

    assert body["trail_started_at"] is not None


def test_empty_trail_reports_null_start(admin_audit_client):
    client, _db = admin_audit_client

    body = client.get("/api/audit").json()

    assert body["total"] == 0
    assert body["trail_started_at"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_audit_routes.py -v --no-cov`
Expected: FAIL — fixture `admin_audit_client` does not exist yet; add it in Step 3.

- [ ] **Step 3: Write the fixture, schemas and route**

Add the fixture at the top of `test_audit_routes.py`, following the pattern in `tests/test_routes/test_reports_routes_real.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.routes.audit import router as audit_router
from backend.tests.fixtures.factories import TestDataFactory


@pytest.fixture
def admin_audit_client(transactional_db):
    admin = TestDataFactory.create_user(
        transactional_db, user_id="aud-admin", username="aud_admin", role="admin", client_id=None
    )
    transactional_db.commit()

    app = FastAPI()
    app.include_router(audit_router)
    app.dependency_overrides[get_db] = lambda: transactional_db
    app.dependency_overrides[get_current_user] = lambda: admin
    return TestClient(app), transactional_db
```

```python
# backend/schemas/audit.py
"""Audit trail response models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class AuditEntryResponse(BaseModel):
    """One recorded change."""

    model_config = ConfigDict(from_attributes=True)

    entry_id: int
    occurred_at: datetime
    actor_user_id: Optional[str]
    actor_username: Optional[str]
    table_name: str
    record_pk: str
    operation: str
    changes: Optional[Dict[str, Any]]
    client_id: Optional[str]
    request_method: Optional[str]
    request_path: Optional[str]


class AuditListResponse(BaseModel):
    """A page of entries, plus when the trail itself begins.

    ``trail_started_at`` exists because there is no backfill: an absent change
    from before deployment is correct behaviour, and callers need to be able to
    tell that apart from a bug.
    """

    entries: List[AuditEntryResponse]
    total: int
    trail_started_at: Optional[datetime]
```

```python
# backend/routes/audit.py
"""
Audit Trail API Routes
Admin-only reads over the entity-level change trail.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_admin
from backend.database import get_db
from backend.orm.audit_entry import AuditEntry
from backend.orm.user import User
from backend.schemas.audit import AuditEntryResponse, AuditListResponse

router = APIRouter(prefix="/api/audit", tags=["Audit"])


def _end_of_day(value: date) -> datetime:
    """Inclusive end bound for a DateTime column.

    occurred_at is a DateTime, so an inclusive end date must compare against
    the NEXT midnight. Comparing against the date at midnight silently drops
    everything recorded during the final day.
    """
    return datetime.combine(value, time.min, tzinfo=timezone.utc) + timedelta(days=1)


def _trail_started_at(db: Session) -> Optional[datetime]:
    """When the trail begins, or None if empty.

    Shared by both endpoints deliberately: there is no backfill, so "the trail
    starts here" is load-bearing for interpreting an empty result, and it needs
    exactly one definition. Both responses carry it.
    """
    return db.query(func.min(AuditEntry.occurred_at)).scalar()


@router.get("", response_model=AuditListResponse)
def list_audit_entries(
    table_name: Optional[str] = Query(None),
    actor_user_id: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AuditListResponse:
    """Recent changes, newest first. Admin only."""
    query = db.query(AuditEntry)

    if table_name:
        query = query.filter(AuditEntry.table_name == table_name)
    if actor_user_id:
        query = query.filter(AuditEntry.actor_user_id == actor_user_id)
    if client_id:
        query = query.filter(AuditEntry.client_id == client_id)
    if start_date:
        query = query.filter(
            AuditEntry.occurred_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        )
    if end_date:
        query = query.filter(AuditEntry.occurred_at < _end_of_day(end_date))

    total = query.count()
    rows = query.order_by(AuditEntry.occurred_at.desc()).offset(offset).limit(limit).all()
    trail_started_at = _trail_started_at(db)

    return AuditListResponse(
        entries=[AuditEntryResponse.model_validate(r) for r in rows],
        total=total,
        trail_started_at=trail_started_at,
    )
```

Register in `backend/bootstrap/routers.py` beside the existing includes:

```python
    from backend.routes.audit import router as audit_router

    app.include_router(audit_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_audit_routes.py -v --no-cov`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/schemas/audit.py backend/routes/audit.py backend/bootstrap/routers.py \
        backend/tests/test_audit/test_audit_routes.py
git commit -m "feat(audit): admin-only audit list endpoint"
```

---

### Task 10: Entity-history endpoint and the authorization matrix

**Files:**
- Modify: `backend/routes/audit.py`, `backend/tests/test_audit/test_audit_routes.py`

**Interfaces:**
- Consumes: Task 9.
- Produces: `GET /api/audit/{table_name}/{record_pk}`.

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_audit/test_audit_routes.py

def test_entity_history_returns_only_that_entity(admin_audit_client):
    client, db = admin_audit_client
    _seed_entry(db, record_pk="HOLD-1")
    _seed_entry(db, record_pk="HOLD-2")

    response = client.get("/api/audit/HOLD_ENTRY/HOLD-1")

    assert response.status_code == 200
    body = response.json()
    assert [e["record_pk"] for e in body["entries"]] == ["HOLD-1"]


def test_entity_history_of_unknown_record_is_empty_not_an_error(admin_audit_client):
    """No backfill: nothing recorded is a legitimate answer."""
    client, _db = admin_audit_client

    response = client.get("/api/audit/HOLD_ENTRY/NEVER-TOUCHED")

    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.parametrize("role", ["poweruser", "leader", "supervisor", "operator", "viewer"])
def test_non_admin_roles_are_forbidden(transactional_db, role):
    """Admin-only, pinned per role. One expected status per assertion."""
    user = TestDataFactory.create_user(
        transactional_db, user_id=f"aud-{role}", username=f"aud_{role}", role=role, client_id=None
    )
    transactional_db.commit()

    app = FastAPI()
    app.include_router(audit_router)
    app.dependency_overrides[get_db] = lambda: transactional_db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)

    assert client.get("/api/audit").status_code == 403
    assert client.get("/api/audit/HOLD_ENTRY/HOLD-1").status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_audit_routes.py -v --no-cov`
Expected: FAIL — 404 on the history route (not yet defined).

- [ ] **Step 3: Add the endpoint**

```python
# append to backend/routes/audit.py

@router.get("/{table_name}/{record_pk}", response_model=AuditListResponse)
def get_entity_history(
    table_name: str,
    record_pk: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AuditListResponse:
    """Full change history for one entity. Admin only.

    An empty result is a legitimate answer: the trail has no backfill, so
    changes made before it was deployed were never recorded. trail_started_at
    lets callers tell "nothing happened" apart from "before we were watching".
    """
    query = db.query(AuditEntry).filter(
        AuditEntry.table_name == table_name,
        AuditEntry.record_pk == record_pk,
    )
    total = query.count()
    rows = query.order_by(AuditEntry.occurred_at.desc()).offset(offset).limit(limit).all()
    trail_started_at = _trail_started_at(db)

    return AuditListResponse(
        entries=[AuditEntryResponse.model_validate(r) for r in rows],
        total=total,
        trail_started_at=trail_started_at,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_audit/test_audit_routes.py -v --no-cov`
Expected: PASS (11 tests: 4 + 2 + 5 parametrized)

- [ ] **Step 5: Commit**

```bash
git add backend/routes/audit.py backend/tests/test_audit/test_audit_routes.py
git commit -m "feat(audit): entity-history endpoint with admin-only authorization matrix"
```

---

### Task 11: OpenAPI surface and MariaDB portability

**Files:**
- Modify: `backend/tests/test_bootstrap/openapi_surface.json`, `backend/tests/test_mariadb_portability.py`

**Interfaces:**
- Consumes: Tasks 9 and 10.
- Produces: nothing new.

- [ ] **Step 1: Regenerate the OpenAPI golden master**

Run: `cd backend && .venv/bin/python -m pytest tests/test_bootstrap/ -v --no-cov`
Expected: FAIL — the surface gained two routes.

Regenerate it the way the repo already does (check `tests/test_bootstrap/` for the documented command), then confirm the diff adds **exactly** these two and nothing else:

- `GET /api/audit`
- `GET /api/audit/{table_name}/{record_pk}`

- [ ] **Step 2: Write the MariaDB portability test**

```python
# append to backend/tests/test_mariadb_portability.py
"""The JSON column and audit queries must work on MariaDB, not just SQLite.

Imports the PRODUCTION route function rather than re-implementing its query:
a hand-copied query shape is how this job previously went green while the
real code was broken.
"""

from datetime import datetime, timezone

from backend.orm.audit_entry import AuditEntry, AuditOperation
from backend.routes.audit import list_audit_entries


def test_audit_json_column_round_trips_on_mariadb(mariadb_session):
    entry = AuditEntry(
        occurred_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        actor_user_id="u1",
        actor_username="alice",
        table_name="HOLD_ENTRY",
        record_pk="HOLD-MDB-1",
        operation=AuditOperation.UPDATE,
        changes={"hold_status": {"old": "ON_HOLD", "new": "RELEASED"}},
    )
    mariadb_session.add(entry)
    mariadb_session.flush()

    stored = mariadb_session.query(AuditEntry).filter_by(record_pk="HOLD-MDB-1").one()
    assert stored.changes["hold_status"]["new"] == "RELEASED"


def test_audit_date_range_boundary_is_inclusive_on_mariadb(mariadb_session):
    """An entry recorded late on the end date must be returned."""
    late = datetime(2026, 8, 11, 23, 59, tzinfo=timezone.utc)
    mariadb_session.add(
        AuditEntry(
            occurred_at=late,
            table_name="HOLD_ENTRY",
            record_pk="HOLD-MDB-2",
            operation=AuditOperation.INSERT,
            changes={},
        )
    )
    mariadb_session.flush()

    result = list_audit_entries(
        table_name="HOLD_ENTRY",
        actor_user_id=None,
        client_id=None,
        start_date=late.date(),
        end_date=late.date(),
        limit=100,
        offset=0,
        db=mariadb_session,
        _admin=None,
    )

    assert [e.record_pk for e in result.entries] == ["HOLD-MDB-2"]
```

Match the existing fixture name in that file (`mariadb_session` here is illustrative — use whatever the module already provides).

- [ ] **Step 3: Run the portability tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_mariadb_portability.py -v --no-cov`
Expected: PASS locally as skips (no MariaDB URL); they must run for real in the `mariadb-portability` CI job. Confirm in that job's log that the count of executed tests **increased** — a skipped test proves nothing.

- [ ] **Step 4: Full suite and commit**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected: all pass, coverage ≥75%.

```bash
git add backend/tests/test_bootstrap/openapi_surface.json backend/tests/test_mariadb_portability.py
git commit -m "test(audit): openapi surface and MariaDB portability coverage"
```

---

### Task 12: A2 gate — PR, deploy, live verification

- [ ] **Step 1: Cross-review and open the PR**

```bash
/cross-review
gh pr create --base main --title "feat(audit): read API (Project A, PR A2)" --body "..."
```

- [ ] **Step 2: After merge, deploy to the VM**

```bash
ssh manuel@192.168.2.234 'set -e
cd /opt/kpi-operations/app
git pull --ff-only origin main
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend'
```

**Always pass `-f docker-compose.prod.yml`.** The bare file is the dev stack and silently recreates the backend against SQLite — this has broken the deployment before.

The container entrypoint runs `alembic upgrade head`, so `0005_audit_trail` applies on start. Confirm:

```bash
ssh manuel@192.168.2.234 'docker exec -w /app/backend kpi-backend alembic current'
```
Expected: `0005_audit_trail (head)`

- [ ] **Step 3: Live-verify against real MariaDB**

1. Log in as an admin and make a real change through the UI — release a hold, or edit a KPI threshold.
2. `GET /api/audit?table_name=HOLD_ENTRY` and confirm the entry exists with the correct actor, before and after values.
3. `GET /api/audit/HOLD_ENTRY/<id>` and confirm the entity history.
4. Confirm a non-admin receives **403**.
5. Confirm no secret material appears anywhere in `changes`.
6. Re-run the demo seeder and confirm it adds **zero** audit rows.

- [ ] **Step 4: Report and hand back**

Summarise what was verified live. Then **stop**: per the spec §9 the next work is **Cycle 4 PR-C**, which is blocked on two owner rulings (transitions-dataset scope versus the historical-snapshot limitation; the `priority_adherence` denominator). Do not start Project B.
