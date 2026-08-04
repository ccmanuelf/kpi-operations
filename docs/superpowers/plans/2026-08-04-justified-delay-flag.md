# Justified-Delay Flag (Cycle 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 3-state justified-delay classification on late work orders — capture (columns, invariants, dialog) plus the OTD gross/net-of-justified dual metric — per spec `docs/superpowers/specs/2026-08-04-justified-delay-flag-design.md`.

**Architecture:** A delay taxonomy module (`backend/orm/delay_taxonomy.py`, exact sibling of `downtime_taxonomy.py`) feeds ORM validators, schemas, metrics, seeders, and a frontend mirror. One shared lateness helper (`is_late` in `calculations/otd.py`, reusing `infer_planned_delivery_date`) gates the API invariants and the metrics. The classification fields ride the existing WorkOrder update path with three new invariants enforced in `crud/work_order.py` where the loaded row is available.

**Tech Stack:** FastAPI/Pydantic v2, SQLAlchemy 2.x `@validates`, Alembic (first DDL revision since baseline), Vue 3 + Vuetify (WorkOrderManagement dialog), vitest, Playwright, pytest.

## Global Constraints

- Branch: `feat/justified-delay-flag` (exists; spec committed at HEAD). Single PR.
- 3-state semantics: `delay_classification` NULL = unclassified (default); `justified` / `unjustified`. Unclassified is NEVER an enum member and never offered in UI selects.
- Invariants (spec §5, exact codes): classification on a non-late order → **422**; `justified` without valid reason → **422**; classification-field write by non-supervisory role → **403**; clearing classification clears reason + note server-side.
- Lateness (spec §4): ONE definition — `is_late(work_order, as_of)`; late iff delivered after inferred planned date OR undelivered with inferred planned date < as_of; `inference_source == "none"` → not late. No second definition may exist.
- Net-of-justified formula (spec §6): `(on_time + justified_late) / total × 100` — denominator unchanged.
- Migration `0003_justified_delay_columns`, `down_revision = "0002_downtime_taxonomy"`, nullable `add_column` × 3, downgrade drops. Baseline-equality + no-create-all guards must stay green.
- No permissive assertions; derivation comments on expected metric values.
- i18n en + es, static keys only; referenced-keys gate green.
- pytest FOREGROUND from `backend/` with explicit 600000ms Bash timeout (background runs die silently); frontend commands from `frontend/`.
- `openapi_surface.json` snapshots (method, path)+tags ONLY — schema-field changes don't touch it; run `pytest tests/test_bootstrap/ -q` to confirm, regenerate only if it actually fails.
- Commits end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Delay taxonomy module + WorkOrder columns + ORM validators

**Files:**
- Create: `backend/orm/delay_taxonomy.py`
- Modify: `backend/orm/work_order.py` (3 columns + 2 validators)
- Test: `backend/tests/test_orm/test_delay_taxonomy.py` (create; `tests/test_orm/` exists from Cycle 1)

**Interfaces:**
- Produces (later tasks import): `DelayClassificationEnum` (`JUSTIFIED="justified"`, `UNJUSTIFIED="unjustified"`), `JustifiedDelayReasonEnum` (`CUSTOMER_REQUEST="customer_request"`, `CUSTOMER_CHANGE_ORDER="customer_change_order"`, `MATERIAL_SUPPLIER_DELAY="material_supplier_delay"`, `FORCE_MAJEURE="force_majeure"`, `UPSTREAM_HOLD="upstream_hold"`, `OTHER="other"`), `SELECTABLE_DELAY_REASONS: list[str]` (all 6, declaration order).
- `WorkOrder` gains `delay_classification: Mapped[Optional[str]] = mapped_column(String(20))`, `justified_delay_reason: Mapped[Optional[str]] = mapped_column(String(40))`, `delay_classification_note: Mapped[Optional[str]] = mapped_column(Text)`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_orm/test_delay_taxonomy.py
from datetime import datetime

import pytest

from backend.orm.delay_taxonomy import (
    SELECTABLE_DELAY_REASONS,
    DelayClassificationEnum,
    JustifiedDelayReasonEnum,
)
from backend.orm.work_order import WorkOrder


def test_classification_enum_has_exactly_two_members():
    assert {c.value for c in DelayClassificationEnum} == {"justified", "unjustified"}


def test_reason_enum_exact_members():
    assert {r.value for r in JustifiedDelayReasonEnum} == {
        "customer_request",
        "customer_change_order",
        "material_supplier_delay",
        "force_majeure",
        "upstream_hold",
        "other",
    }
    assert SELECTABLE_DELAY_REASONS == [r.value for r in JustifiedDelayReasonEnum]


def _wo(**kwargs):
    return WorkOrder(
        work_order_id=kwargs.pop("work_order_id", "WO-DLY-T1"),
        client_id="C1",
        status=kwargs.pop("status", "IN_PROGRESS"),
        **kwargs,
    )
    # NOTE: align constructor kwargs with WorkOrder's actual NOT NULL columns —
    # read the model first and extend (e.g. product/style fields) if instantiation
    # requires more; keep the taxonomy kwargs exactly as tested.


def test_orm_rejects_invalid_classification_but_allows_none_and_valid():
    with pytest.raises(ValueError, match="delay_classification"):
        _wo(delay_classification="excused")
    assert _wo(work_order_id="WO-DLY-T2", delay_classification=None).delay_classification is None
    assert _wo(work_order_id="WO-DLY-T3", delay_classification="justified").delay_classification == "justified"


def test_orm_rejects_invalid_reason_but_allows_none_and_valid():
    with pytest.raises(ValueError, match="justified_delay_reason"):
        _wo(justified_delay_reason="because")
    assert _wo(work_order_id="WO-DLY-T4", justified_delay_reason="force_majeure").justified_delay_reason == "force_majeure"
```

- [ ] **Step 2: Run to verify failure** — `pytest tests/test_orm/test_delay_taxonomy.py -v --no-cov` → ModuleNotFoundError.

- [ ] **Step 3: Create the taxonomy module**

```python
# backend/orm/delay_taxonomy.py
"""
Justified-delay taxonomy (Cycle 2 of the reporting data-capture roadmap).

3-state model: WorkOrder.delay_classification is NULL (unclassified, default),
'justified', or 'unjustified'. Unclassified is the ABSENCE of a value — never
an enum member, never offered in UI selects. justified_delay_reason is stored
only when classification == 'justified'.

Sibling of backend/orm/downtime_taxonomy.py (Cycle 1) — same conventions.
Spec: docs/superpowers/specs/2026-08-04-justified-delay-flag-design.md
"""

from enum import Enum


class DelayClassificationEnum(str, Enum):
    """Late-order delay classification (NULL = unclassified)."""

    JUSTIFIED = "justified"
    UNJUSTIFIED = "unjustified"


class JustifiedDelayReasonEnum(str, Enum):
    """Controlled justification reasons (required iff classification is justified)."""

    CUSTOMER_REQUEST = "customer_request"
    CUSTOMER_CHANGE_ORDER = "customer_change_order"
    MATERIAL_SUPPLIER_DELAY = "material_supplier_delay"
    FORCE_MAJEURE = "force_majeure"
    UPSTREAM_HOLD = "upstream_hold"
    OTHER = "other"


SELECTABLE_DELAY_REASONS: list[str] = [r.value for r in JustifiedDelayReasonEnum]
```

- [ ] **Step 4: Add columns + validators to `backend/orm/work_order.py`**

After the existing date/status columns (near `priority`), add:

```python
    # Justified-delay classification (Cycle 2) — NULL = unclassified
    delay_classification: Mapped[Optional[str]] = mapped_column(String(20))
    justified_delay_reason: Mapped[Optional[str]] = mapped_column(String(40))
    delay_classification_note: Mapped[Optional[str]] = mapped_column(Text)
```

(add `Text` / `validates` to imports if missing) and, following the `DowntimeEntry` validator pattern exactly:

```python
    @validates("delay_classification")
    def _validate_delay_classification(self, key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        from backend.orm.delay_taxonomy import DelayClassificationEnum

        valid = {c.value for c in DelayClassificationEnum}
        if value not in valid:
            raise ValueError(f"delay_classification must be one of {sorted(valid)} or NULL, got {value!r}")
        return value

    @validates("justified_delay_reason")
    def _validate_justified_delay_reason(self, key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        from backend.orm.delay_taxonomy import JustifiedDelayReasonEnum

        valid = {r.value for r in JustifiedDelayReasonEnum}
        if value not in valid:
            raise ValueError(f"justified_delay_reason must be one of {sorted(valid)} or NULL, got {value!r}")
        return value
```

- [ ] **Step 5: Run** — new tests PASS; then `pytest tests/ -k "work_order" -q --no-cov` for fallout (none expected — columns are nullable and validators allow None).

- [ ] **Step 6: Commit** — `feat(delay): taxonomy module + WorkOrder classification columns + ORM validators` + trailer.

---

### Task 2: Migration 0003 (DDL)

**Files:**
- Create: `backend/alembic/versions/0003_justified_delay_columns.py`
- Test: `backend/tests/test_migrations/test_justified_delay_columns.py` (create; dir exists)

**Interfaces:**
- Consumes: nothing from app code.
- Produces: revision `0003_justified_delay`, `down_revision="0002_downtime_taxonomy"`; after upgrade `WORK_ORDER` has the 3 nullable columns.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_migrations/test_justified_delay_columns.py
"""First DDL revision since the baseline — verify columns appear on upgrade.

Same throwaway-SQLite alembic harness as test_downtime_taxonomy_backfill.py.
"""
import sqlite3

import pytest
from alembic import command
from alembic.config import Config

NEW_COLUMNS = {"delay_classification", "justified_delay_reason", "delay_classification_note"}


@pytest.fixture()
def upgraded_db(tmp_path):
    db_path = tmp_path / "mig3.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    conn = sqlite3.connect(db_path)
    yield conn, cfg, db_path
    conn.close()


def _wo_columns(conn):
    return {row[1] for row in conn.execute("PRAGMA table_info(WORK_ORDER)").fetchall()}


def test_upgrade_head_adds_the_three_columns(upgraded_db):
    conn, _, _ = upgraded_db
    assert NEW_COLUMNS <= _wo_columns(conn)


def test_head_is_0003(upgraded_db):
    conn, _, _ = upgraded_db
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0003_justified_delay"


def test_downgrade_removes_the_columns(upgraded_db):
    conn, cfg, db_path = upgraded_db
    conn.close()
    command.downgrade(cfg, "0002_downtime_taxonomy")
    conn2 = sqlite3.connect(db_path)
    try:
        assert not (NEW_COLUMNS & _wo_columns(conn2))
    finally:
        conn2.close()
```

- [ ] **Step 2: Run to verify failure** — head is still 0002, columns absent.

- [ ] **Step 3: Write the migration**

```python
# backend/alembic/versions/0003_justified_delay_columns.py
"""Justified-delay classification columns (Cycle 2) — first DDL since baseline.

Three nullable WORK_ORDER columns; no data pass (NULL = unclassified default).

Revision ID: 0003_justified_delay
Revises: 0002_downtime_taxonomy
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_justified_delay"
down_revision: Union[str, None] = "0002_downtime_taxonomy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("WORK_ORDER", sa.Column("delay_classification", sa.String(length=20), nullable=True))
    op.add_column("WORK_ORDER", sa.Column("justified_delay_reason", sa.String(length=40), nullable=True))
    op.add_column("WORK_ORDER", sa.Column("delay_classification_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("WORK_ORDER", "delay_classification_note")
    op.drop_column("WORK_ORDER", "justified_delay_reason")
    op.drop_column("WORK_ORDER", "delay_classification")
```

- [ ] **Step 4: Run** — migration tests PASS; `pytest tests/test_bootstrap/ tests/test_alembic/ -q --no-cov` → baseline-equality (head == Base.metadata now that Task 1 added the mapped columns), no-create-all, and the CLI head assertions (update the two `0002_downtime_taxonomy` head expectations in `tests/test_alembic/test_alembic_setup.py` to `0003_justified_delay` — same expected fallout class as Cycle 1's Task 3).

- [ ] **Step 5: Commit** — `feat(delay): alembic 0003 — WORK_ORDER classification columns (first DDL since baseline)` + trailer.

---

### Task 3: Shared lateness helper

**Files:**
- Modify: `backend/calculations/otd.py` (new function beside `infer_planned_delivery_date`)
- Test: `backend/tests/test_calculations/test_is_late.py` (create)

**Interfaces:**
- Produces: `is_late(work_order: WorkOrder, as_of: date) -> bool` — importable as `from backend.calculations.otd import is_late`. Tasks 4/5/6 consume it.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_calculations/test_is_late.py
from datetime import date, datetime

from backend.calculations.otd import is_late
from backend.orm.work_order import WorkOrder

AS_OF = date(2026, 8, 1)


def _wo(**kwargs):
    return WorkOrder(work_order_id="WO-LATE-T", client_id="C1", status="IN_PROGRESS", **kwargs)
    # Align with WorkOrder's required constructor fields as in Task 1's test.


def test_delivered_after_planned_is_late():
    wo = _wo(planned_ship_date=datetime(2026, 7, 10), actual_delivery_date=datetime(2026, 7, 15))
    assert is_late(wo, AS_OF) is True


def test_delivered_on_or_before_planned_is_not_late():
    wo = _wo(planned_ship_date=datetime(2026, 7, 10), actual_delivery_date=datetime(2026, 7, 10))
    assert is_late(wo, AS_OF) is False


def test_undelivered_past_due_is_late():
    wo = _wo(planned_ship_date=datetime(2026, 7, 10), actual_delivery_date=None)
    assert is_late(wo, AS_OF) is True


def test_undelivered_not_yet_due_is_not_late():
    wo = _wo(planned_ship_date=datetime(2026, 8, 20), actual_delivery_date=None)
    assert is_late(wo, AS_OF) is False


def test_falls_back_to_required_date():
    wo = _wo(planned_ship_date=None, required_date=datetime(2026, 7, 10), actual_delivery_date=datetime(2026, 7, 20))
    assert is_late(wo, AS_OF) is True


def test_no_inferable_date_is_not_late():
    wo = _wo(planned_ship_date=None, required_date=None, actual_delivery_date=datetime(2026, 7, 20))
    # inference_source == "none" (no calculated fallback inputs either) -> not late
    assert is_late(wo, AS_OF) is False
```

- [ ] **Step 2: Run to verify failure** — ImportError.

- [ ] **Step 3: Implement** (in `otd.py`, directly after `infer_planned_delivery_date`)

```python
def is_late(work_order: WorkOrder, as_of: date) -> bool:
    """THE single lateness definition (spec §4) — gates classification
    eligibility (API + UI) and feeds the gross/net OTD metrics. Do not
    introduce a second definition anywhere.

    Late iff: delivered after the inferred planned date, OR undelivered and
    the inferred planned date is before `as_of`. Orders with no inferable
    planned date (inference_source == "none") are never late.
    """
    inferred = infer_planned_delivery_date(work_order)
    if inferred.date is None:
        return False
    if work_order.actual_delivery_date is not None:
        return work_order.actual_delivery_date > inferred.date
    return inferred.date < datetime.combine(as_of, datetime.min.time())
```

(Check `inferred.date`'s type first — `infer_planned_delivery_date` returns datetimes from the ORM columns; if it can return `date` objects on any path, normalize both sides with `datetime.combine(...)`/`.date()` consistently and mirror that in the tests.)

- [ ] **Step 4: Run** — all 6 PASS; `pytest tests/ -k "otd" -q --no-cov` for regressions.

- [ ] **Step 5: Commit** — `feat(delay): shared is_late lateness helper (single definition)` + trailer.

---

### Task 4: Update-path invariants + response is_late

**Files:**
- Modify: `backend/schemas/work_order.py` (`WorkOrderUpdate` + `WorkOrderResponse`)
- Modify: `backend/crud/work_order.py:157-…` (`update_work_order` — invariant block)
- Modify: `backend/routes/work_orders.py` (response `is_late` population — see Step 3 for the chosen mechanism)
- Test: `backend/tests/test_routes/test_work_order_delay_classification.py` (create), `backend/tests/test_auth/test_permission_matrix.py` (extend with the field-level 403 row — locate the module via `rtk proxy grep -rln "permission_matrix" backend/tests`)

**Interfaces:**
- Consumes: Task 1 enums, Task 3 `is_late`.
- Produces: `WorkOrderUpdate.delay_classification: Optional[DelayClassificationEnum]`, `.justified_delay_reason: Optional[JustifiedDelayReasonEnum]`, `.delay_classification_note: Optional[str]`; `WorkOrderResponse` carries the three fields plus `is_late: bool = False`. Invariants per Global Constraints.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_routes/test_work_order_delay_classification.py
"""Spec §5 invariants. Uses the existing work-order route test harness —
read tests/test_routes/ for the established authenticated-client fixtures
(supervisor + operator variants) and the WO factory; mirror them."""
from datetime import datetime, timedelta

# Fixtures: build one LATE work order (planned_ship_date 10 days ago, undelivered)
# and one NOT-LATE order (planned_ship_date 10 days ahead) per test client.


class TestDelayClassificationInvariants:
    def test_classify_late_order_as_justified_with_reason_succeeds(self, supervisor_client_with_wos):
        client, late_wo, _ = supervisor_client_with_wos
        r = client.put(f"/api/work-orders/{late_wo.work_order_id}", json={
            "delay_classification": "justified",
            "justified_delay_reason": "customer_request",
            "delay_classification_note": "Customer asked to hold shipment",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["delay_classification"] == "justified"
        assert body["justified_delay_reason"] == "customer_request"
        assert body["is_late"] is True

    def test_classify_non_late_order_returns_422(self, supervisor_client_with_wos):
        client, _, ontime_wo = supervisor_client_with_wos
        r = client.put(f"/api/work-orders/{ontime_wo.work_order_id}", json={
            "delay_classification": "unjustified",
        })
        assert r.status_code == 422

    def test_justified_without_reason_returns_422(self, supervisor_client_with_wos):
        client, late_wo, _ = supervisor_client_with_wos
        r = client.put(f"/api/work-orders/{late_wo.work_order_id}", json={
            "delay_classification": "justified",
        })
        assert r.status_code == 422

    def test_clearing_classification_clears_reason_and_note(self, supervisor_client_with_wos):
        client, late_wo, _ = supervisor_client_with_wos
        client.put(f"/api/work-orders/{late_wo.work_order_id}", json={
            "delay_classification": "justified",
            "justified_delay_reason": "force_majeure",
            "delay_classification_note": "flood",
        })
        r = client.put(f"/api/work-orders/{late_wo.work_order_id}", json={
            "delay_classification": None,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["delay_classification"] is None
        assert body["justified_delay_reason"] is None
        assert body["delay_classification_note"] is None

    def test_unjustified_clears_reason(self, supervisor_client_with_wos):
        client, late_wo, _ = supervisor_client_with_wos
        client.put(f"/api/work-orders/{late_wo.work_order_id}", json={
            "delay_classification": "justified",
            "justified_delay_reason": "upstream_hold",
        })
        r = client.put(f"/api/work-orders/{late_wo.work_order_id}", json={
            "delay_classification": "unjustified",
        })
        assert r.status_code == 200
        assert r.json()["justified_delay_reason"] is None

    def test_operator_touching_classification_fields_returns_403(self, operator_client_with_wos):
        client, late_wo, _ = operator_client_with_wos
        r = client.put(f"/api/work-orders/{late_wo.work_order_id}", json={
            "delay_classification": "unjustified",
        })
        assert r.status_code == 403

    def test_operator_updating_other_fields_still_succeeds(self, operator_client_with_wos):
        client, late_wo, _ = operator_client_with_wos
        r = client.put(f"/api/work-orders/{late_wo.work_order_id}", json={"priority": "HIGH"})
        assert r.status_code == 200

    def test_response_is_late_false_for_ontime_order(self, supervisor_client_with_wos):
        client, _, ontime_wo = supervisor_client_with_wos
        r = client.get(f"/api/work-orders/{ontime_wo.work_order_id}")
        assert r.status_code == 200
        assert r.json()["is_late"] is False
```

Explicit-null nuance: `"delay_classification": None` with Pydantic `exclude_unset=True` — the key IS set (to None), so it appears in `model_dump(exclude_unset=True)`; verify this holds in the harness and assert it in a small schema-level test if the route tests don't already cover it.

- [ ] **Step 2: Run to verify failure** — fields unknown → ignored/absent → assertions fail.

- [ ] **Step 3: Implement**

- `WorkOrderUpdate` (schemas/work_order.py, near line 110's optional fields): add the three typed fields (`Optional[DelayClassificationEnum]`, `Optional[JustifiedDelayReasonEnum]`, `Optional[str]`, all `= None`; import enums from `backend.orm.delay_taxonomy`).
- `WorkOrderResponse`: add the three fields (plain `Optional[str]`) plus `is_late: bool = False`.
- `crud/work_order.py::update_work_order` — after loading `db_work_order` and the existing access check, insert the invariant block BEFORE the setattr loop:

```python
    CLASSIFICATION_FIELDS = {"delay_classification", "justified_delay_reason", "delay_classification_note"}
    touched = CLASSIFICATION_FIELDS & set(work_order_update)
    if touched:
        from datetime import date as _date

        from backend.calculations.otd import is_late
        from backend.orm.user import SUPERVISORY_ROLES

        if current_user.role not in SUPERVISORY_ROLES:
            raise HTTPException(status_code=403, detail="Delay classification requires a supervisory role")

        new_classification = work_order_update.get("delay_classification", db_work_order.delay_classification)
        if new_classification is not None and not is_late(db_work_order, _date.today()):
            raise HTTPException(status_code=422, detail="Delay classification is only allowed on late work orders")
        if new_classification == "justified":
            reason = work_order_update.get("justified_delay_reason", db_work_order.justified_delay_reason)
            if reason is None:
                raise HTTPException(status_code=422, detail="justified_delay_reason is required when classification is 'justified'")
        else:
            # unjustified or cleared: never store a stale reason; clearing also drops the note
            work_order_update["justified_delay_reason"] = None
            if new_classification is None:
                work_order_update["delay_classification_note"] = None
```

  (Enum values arrive as their `.value` strings after `model_dump`; confirm and coerce if the dump yields Enum instances.)
- Response `is_late`: in `routes/work_orders.py`, populate it wherever `WorkOrderResponse` is built from an ORM row for the single-GET and update endpoints, plus the list endpoint's rows — find the serialization mechanism first (`response_model` conversion from ORM attrs): the clean insertion is a small helper `def _with_is_late(wo) -> WorkOrderResponse: resp = WorkOrderResponse.model_validate(wo, from_attributes=True); resp.is_late = is_late(wo, date.today()); return resp` applied at the return sites. If the routes currently return raw ORM objects and rely on `response_model`, switch the affected return sites to the helper (behavior otherwise unchanged — assert field parity in the tests).

- [ ] **Step 4: Extend the permission matrix** — add the classification-fields row per that module's table conventions (supervisory allowed, operator/viewer 403).

- [ ] **Step 5: Run** — new route tests + `pytest tests/ -k "work_order or permission" -q --no-cov` green; `pytest tests/test_bootstrap/ -q --no-cov` (surface unchanged expected).

- [ ] **Step 6: Commit** — `feat(delay): update-path invariants (late-only, reason-iff-justified, supervisory 403) + is_late on responses` + trailer.

---

### Task 5: Metrics — calculate_true_otd gross + net

**Files:**
- Modify: `backend/calculations/otd.py::calculate_true_otd` (+ its return dict)
- Test: extend `backend/tests/test_calculations/` OTD test module (locate: `rtk proxy grep -rln "calculate_true_otd" backend/tests`)

**Interfaces:**
- Consumes: Task 1 enums, Task 3 `is_late` (for the undelivered-past-due late_counts arm).
- Produces: the return dict gains `"otd_net_of_justified"` (both true and standard variants: `"true_otd_net_pct"`, `"standard_otd_net_pct"` if the dict is per-mode keyed — match its EXISTING key style exactly, read first), `"late_counts": {"total": int, "justified": int, "unjustified": int, "unclassified": int}`, `"justified_by_reason": {reason: count}`.

- [ ] **Step 1: Write the failing test**

```python
def test_true_otd_gross_vs_net_with_derivation(db_session):
    """Seed 5 delivered COMPLETED orders for one client, all with planned dates:
    - 2 on time
    - 1 late + justified (customer_request)
    - 1 late + unjustified
    - 1 late + unclassified
    Plus 1 undelivered past-due order (classifiable, in late_counts, NOT in OTD %).

    Derivations:
      gross true-OTD = 2 on_time / 5 delivered = 40.0
      net  true-OTD  = (2 + 1 justified) / 5   = 60.0
      late_counts = {total: 4, justified: 1, unjustified: 1, unclassified: 2}
        (3 delivered-late + 1 undelivered-past-due; the undelivered one is unclassified)
      justified_by_reason = {"customer_request": 1}
    """
    # seed via the module's existing WO factory helpers, then:
    result = calculate_true_otd(db_session, "OTD-NET-CL", start, end)
    assert result[GROSS_KEY] == Decimal("40.0")      # use the dict's real key names
    assert result[NET_KEY] == Decimal("60.0")
    assert result["late_counts"] == {"total": 4, "justified": 1, "unjustified": 1, "unclassified": 2}
    assert result["justified_by_reason"] == {"customer_request": 1}
```

(Replace GROSS_KEY/NET_KEY with the function's actual key names after reading the return dict; keep the derivation comment. The undelivered-past-due order must have `planned_ship_date` inside the range-independent lateness window but is found via a separate query — see Step 3.)

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** inside `calculate_true_otd` (both the true and standard loops already iterate delivered orders and compute on-time/late):

- Net %: track `justified_late = sum(1 for late wo where wo.delay_classification == "justified")` per mode; `net = (on_time + justified_late) / total × 100` (Decimal, same rounding idiom as the existing pct).
- `late_counts` / `justified_by_reason`: over (a) the delivered-late orders from the loops and (b) undelivered past-due orders in scope — one extra query: `WorkOrder.client_id == client_id`, `actual_delivery_date.is_(None)`, then filter in Python with `is_late(wo, end_date)` (reusing the ONE definition; no date-window predicate on planned dates in SQL — the inference chain is Python-side).
- Bucket by `delay_classification` (None → `unclassified`); reasons only from justified ones.
- Add the new keys to the returned dict without renaming any existing key (consumers depend on them).

- [ ] **Step 4: Run** — new test green; `pytest tests/ -k "otd" -q --no-cov` — existing expectations unchanged (new keys are additive).

- [ ] **Step 5: Commit** — `feat(delay): true/standard OTD net-of-justified + late_counts + by-reason` + trailer.

---

### Task 6: Metrics — dual-view OTD service + KPI endpoint surface

**Files:**
- Modify: `backend/services/dual_view/otd_service.py` (thread classification into its raw order rows; net variant)
- Modify: `backend/routes/kpi/otd.py::calculate_otd_kpi` (surface the Task 5 keys)
- Test: extend the dual-view OTD service test module + the kpi/otd route test module (locate both by grep)

**Interfaces:**
- Consumes: Tasks 1/3/5.
- Produces: dual-view OTD result gains `net_of_justified` alongside its existing value (read `OTDRawData`/`raw.orders` row shape first; add `delay_classification` to the row tuple/dataclass); `GET /api/kpi/otd` response includes the Task 5 keys verbatim.

- [ ] **Step 1: Write the failing tests** — route-level: seed the Task 5 scenario, `GET /api/kpi/otd?...` → assert `late_counts` and net key present with the same derived values (exact asserts + derivation comment). Service-level: with a buffer of 0, orders `delay_pct` > 0 that are justified count into net (mirror the service's existing test idiom).

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** — service: extend the raw-row builder query to select `delay_classification`; net helper mirrors `_otd_for_buffer` but counts `o.delay_pct <= threshold or o.delay_classification == "justified"` as on-time. Route: pass through the new dict keys (it already returns `calculate_true_otd`'s dict or wraps it — keep shape additive).

- [ ] **Step 4: Run** — both modules + `pytest tests/test_bootstrap/ -q --no-cov` (path/method unchanged → surface untouched).

- [ ] **Step 5: Commit** — `feat(delay): dual-view OTD net variant + KPI endpoint surface` + trailer.

---

### Task 7: Excel OTD row + dashboard card (backend + frontend surface)

**Files:**
- Modify: `backend/reports/excel_generator.py` (Executive Summary/KPI table's OTD row → gross + net columns or a second row — match the sheet's existing KPI-row idiom, read `_create_summary_sheet` first)
- Modify: the KPI dashboard OTD card source (locate: `rtk proxy grep -rln "otd" frontend/src/components frontend/src/views --include="*.vue" -i | head`, then the composable/store feeding it) — net shown as secondary line
- Test: extend the excel test module (exact-value assertions incl. net) + the card's existing vitest spec

**Interfaces:**
- Consumes: Task 5/6 keys.
- Produces: UI/report surfaces only; no new exports.

- [ ] **Step 1: Backend failing test** — seed the Task 5 scenario; generate comprehensive Excel; assert the OTD row/cells show gross 40.0 and net 60.0 (exact positions per the sheet's real layout, discovered by reading the generator).
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement Excel change; run green.**
- [ ] **Step 4: Frontend** — card displays net when the API payload carries it (i18n label `delay.netOfJustified` en: "Net of justified", es: "Neto de justificados"); vitest asserts both values render from a mocked payload. Follow the card's existing secondary-line idiom if one exists (compare with other KPI cards first).
- [ ] **Step 5: Run frontend suite + lint + typecheck; commit** — `feat(delay): OTD gross+net on Excel summary and dashboard card` + trailer.

---

### Task 8: WO dialog section + grid badge + frontend constants + i18n

**Files:**
- Create: `frontend/src/constants/delayTaxonomy.ts` (+ `frontend/src/constants/__tests__/delayTaxonomy.spec.ts`)
- Modify: `frontend/src/views/WorkOrderManagement.vue` (edit-dialog section) and/or `frontend/src/components/WorkOrderDetailDrawer.vue` — read both first; the section goes where the edit form fields live; the badge goes in the table row rendering (`useWorkOrderData.ts` headers at :117 area)
- Modify: `frontend/src/composables/useWorkOrderData.ts` (badge state helper + payload fields)
- Modify: `frontend/src/i18n/locales/en.json` / `es.json` (`delay.*` block)
- Test: extend `useWorkOrderData` spec; Playwright guard in the WO e2e spec (locate the existing work-order e2e file; follow its dialog-editing idiom)

**Interfaces:**
- Consumes: Task 4's response fields (`is_late`, the three classification fields) and update API.
- Produces (from `delayTaxonomy.ts`): `DELAY_CLASSIFICATION_CODES = ['justified','unjustified']`, `JUSTIFIED_DELAY_REASON_CODES` (6, backend order), `classificationLabelKey(id)`, `delayReasonLabelKey(id)` → `delay.classifications.<id>` / `delay.reasons.<camelCase>`; badge helper `delayBadge(row): {key: 'unclassified'|'justified'|'unjustified', color: string} | null` (null when `!row.is_late`).

- [ ] **Step 1: Constants + spec** — mirror `downtimeTaxonomy.ts`/its spec exactly (8→2/6 values, both-locale key-resolution test incl. `delay.classifications.unclassified` used by the badge).
- [ ] **Step 2: i18n blocks (both locales)**

```json
"delay": {
  "sectionTitle": "Delay classification",
  "netOfJustified": "Net of justified",
  "classifications": { "unclassified": "Unclassified", "justified": "Justified", "unjustified": "Unjustified" },
  "reasons": {
    "customerRequest": "Customer request",
    "customerChangeOrder": "Customer change order",
    "materialSupplierDelay": "Material/supplier delay",
    "forceMajeure": "Force majeure",
    "upstreamHold": "Upstream hold",
    "other": "Other"
  }
}
```

es: `"sectionTitle": "Clasificación del retraso"`, `"netOfJustified": "Neto de justificados"`, classifications `"Sin clasificar"/"Justificado"/"No justificado"`, reasons `"Solicitud del cliente"/"Cambio de orden del cliente"/"Retraso de material/proveedor"/"Fuerza mayor"/"Retención previa"/"Otro"`. (Task 7's `delay.netOfJustified` key lands here if Task 7 ran first — coordinate: whichever task runs first creates the block, the other extends it.)

- [ ] **Step 3: Dialog section** — render iff `editedItem.is_late`; v-select classification (3 options incl. Unclassified→null), v-select reason (`v-if` justified, required), v-textarea note; all disabled unless the auth store's role is in the supervisory set (mirror how the app currently role-gates UI controls — grep `SUPERVISORY` / role checks in frontend stores first). Submit includes the fields only when the section is visible.
- [ ] **Step 4: Badge** — in the WO table's row rendering add the chip via `delayBadge(row)`; colors: unclassified `warning`, justified `info`, unjustified `error`.
- [ ] **Step 5: Vitest** — badge helper truth table (non-late → null; late+null → unclassified/warning; etc.), dialog visibility logic via extracted pure helper.
- [ ] **Step 6: Playwright guard** — open a seeded late WO, classify justified + reason, save, assert badge text switches (en/es-tolerant regex like Cycle 1's guard).
- [ ] **Step 7: Run suite + lint + typecheck; commit** — `feat(delay): WO dialog classification section + grid badge + delay taxonomy constants` + trailer.

---

### Task 9: Seeders

**Files:**
- Modify: `backend/scripts/_seed_operations.py` (the delivered-history/late-order block around its `required_date`/OTD-dip shaping — read `:95-190` first)
- Modify: `backend/scripts/init_demo_database.py` (its late-WO block near `:1208-1230`)
- Test: extend `backend/tests/test_scripts/test_seed_sample_client.py` + `test_init_demo_database.py`

**Interfaces:**
- Consumes: Task 1 enums.
- Produces: deterministic classification mix on seeded LATE orders only: cycle `justified` (rotating through all 6 reasons across rows), `unjustified`, and unclassified (leave NULL) in a fixed index-based pattern (e.g. `i % 3`); never classify non-late orders (assert with `is_late` in the test, not in the seeder).

- [ ] **Step 1: Failing tests** — extend both seeder test modules: every classified order must be late (`is_late(wo, seed_anchor)`), classification values enum-valid, at least one justified (with reason), one unjustified, one unclassified-late present; justified rows have reasons, others have NULL reason.
- [ ] **Step 2: Run red (fields all NULL today → "at least one justified" fails).**
- [ ] **Step 3: Implement both seeders (enum members, index-deterministic pattern, no RNG for classification); run green + full `pytest tests/ -q`.**
- [ ] **Step 4: Commit** — `feat(delay): seeders classify late orders deterministically (justified/unjustified/unclassified mix)` + trailer.

---

### Task 10: Living-doc re-grade + full verification

**Files:**
- Modify: `docs/reporting/reporting-capabilities-and-gaps.md` (§4 Q3 row, §5 Cycle 2 line)

- [ ] **Step 1: Edits (match current text verbatim by reading first):**
  - §4 Q3 row `| Justified vs unjustified lateness | **missing** | no classification field; PGI's Delivery Performance excludes justified delays |` → `| Justified vs unjustified lateness | **have** | 3-state delay_classification + 6-reason enum on WorkOrder; OTD reports gross + net-of-justified (Cycle 2) |`
  - §5 Cycle 2 line: append ` **[DONE — this PR]**`.
- [ ] **Step 2: Full battery** — backend `pytest tests/ -q` (coverage ≥75%), frontend `npm run test && npm run lint && npm run typecheck`; grep-verify no stray lateness definition: `rtk proxy grep -rn "actual_delivery_date >" backend --include="*.py" | grep -v test | grep -v otd.py` → any hit outside `otd.py` must be pre-existing non-lateness logic (list + disposition in report).
- [ ] **Step 2b: Single-definition guard (spec §4)** — add to `backend/tests/test_calculations/test_is_late.py` a structural test asserting both consumers import THE helper rather than redefining lateness:

```python
def test_single_lateness_definition_guard():
    """Spec §4: is_late in calculations/otd.py is the ONLY lateness definition.
    Both the update-path invariants and the metrics must import it."""
    import pathlib

    backend_root = pathlib.Path(__file__).resolve().parents[2]
    crud_src = (backend_root / "crud" / "work_order.py").read_text(encoding="utf-8")
    assert "from backend.calculations.otd import is_late" in crud_src
    otd_src = (backend_root / "calculations" / "otd.py").read_text(encoding="utf-8")
    assert otd_src.count("def is_late(") == 1
```

(Runs green only after Task 4 lands — mark `xfail(strict=False)` is NOT allowed; instead this test is ADDED in Task 10 where both consumers exist.)
- [ ] **Step 3: Commit** — `docs(reporting): re-grade Q3 justified-lateness to 'have' (Cycle 2 shipped)` + trailer.

---

### Task 11: Cross-review and PR (controller-level)

- [ ] **Step 1:** `git diff --stat main...HEAD` — spec + plan + backend (orm/alembic/calculations/services/routes/schemas/crud/reports/scripts/tests) + frontend (constants/views/composables/i18n/e2e) + living doc. Nothing else.
- [ ] **Step 2:** `/cross-review` for final HEAD (chunked if >1500 lines).
- [ ] **Step 3:** Push; PR `feat(delay): justified-delay flag — 3-state classification + OTD net-of-justified (Cycle 2)`; body lists capture, invariants, metrics, UI, seeders, re-grade; standard footer.
- [ ] **Step 4:** `gh pr checks <n> --watch` (explicit PR number — rtk needs it) → 7/7 green → report URL. Merge is **user-confirmed only**. Post-merge: main watch, Render auto (migration 0003 on startup), VM deploy + re-seed + live-verify spec §10.
