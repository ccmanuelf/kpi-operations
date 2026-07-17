# KPI Decimal→JSON-number Serialization Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make 5 KPI numeric fields return JSON numbers on MariaDB (currently `Decimal`→`"0.00"` strings) by `float()`-casting the SQL-aggregate divisions, matching the sibling endpoints.

**Architecture:** One-line `float()` cast at each of 5 sites across 3 route files, plus a contract-guard test asserting each field is a Python `float`. No signature/shape/frontend change.

**Tech Stack:** FastAPI + SQLAlchemy (SQLite tests + MariaDB prod), pytest.

## Global Constraints

- Cast **both operands** of the division `float(...)`; preserve the existing zero-guard verbatim; the `else 0` branch stays `0` (int, a valid JSON number). No other change per site.
- **The defect is MariaDB-only** (SQLite returns the aggregate as int/float already). The SQLite unit tests therefore PASS before and after — they are **contract/regression guards** (the field must be a JSON number), not a red→green reproduction. The real proof is a live curl against the VM MariaDB post-deploy (out of this plan; done at deploy).
- No OpenAPI change; `mariadb-portability` CI job + full backend suite stay green.

---

### Task 1: float()-cast the 5 Decimal-division KPI fields + contract-guard tests

**Files:**
- Modify: `backend/routes/kpi/trends.py` (3 sites: 222, 394, 434), `backend/routes/kpi/otd.py` (175), `backend/routes/quality/pareto.py` (179)
- Test: `backend/tests/test_kpi/test_decimal_json_serialization.py` (create)

**Interfaces:** none produced; endpoints keep their exact response shapes.

- [ ] **Step 1: Write the contract-guard tests**

```python
# backend/tests/test_kpi/test_decimal_json_serialization.py
"""Guard: KPI numeric fields that divide a SQL-aggregate must serialize as JSON
numbers (Python float), not Decimal->str. The original defect is MariaDB-only
(SQLite returns int/float already), so these pass on SQLite before and after the
fix — they are a regression contract, not a red->green reproduction. Live MariaDB
verification is the real proof (see the deploy step)."""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.factories import TestDataFactory
from backend.main import app
from backend.orm.quality_entry import QualityEntry
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.work_order import WorkOrder, WorkOrderStatus


@pytest.fixture
def db_session(transactional_db):
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(db_session):
    admin = TestDataFactory.create_user(db_session, username="serial_admin", role="admin")
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def _num(v):
    # a JSON number decodes to int/float in Python; a Decimal->str bug decodes to str
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def test_quality_trend_value_is_number(client, db_session):
    db_session.add(QualityEntry(quality_entry_id="QE1", client_id="C1", work_order_id="WO1",
                                shift_date=datetime(2026, 6, 10, 8), units_inspected=100, units_passed=90,
                                units_defective=10, total_defects_count=10))
    db_session.commit()
    body = client.get("/api/kpi/quality/trend",
                      params={"start_date": "2026-06-10", "end_date": "2026-06-10"}).json()
    assert body and _num(body[0]["value"])


def test_otd_trend_value_is_number(client, db_session):
    db_session.add(WorkOrder(work_order_id="WO1", client_id="C1", style_model="M1", planned_quantity=10,
                             status=WorkOrderStatus.SHIPPED, required_date=datetime(2026, 6, 10, 8),
                             actual_delivery_date=datetime(2026, 6, 12, 8)))
    db_session.commit()
    body = client.get("/api/kpi/on-time-delivery/trend",
                      params={"start_date": "2026-06-10", "end_date": "2026-06-10"}).json()
    assert body and _num(body[0]["value"])


def test_absenteeism_trend_value_is_number(client, db_session):
    db_session.add(AttendanceEntry(attendance_entry_id="AE1", client_id="C1", employee_id=1,
                                   shift_date=datetime(2026, 6, 10, 8), scheduled_hours=8,
                                   is_absent=1, absence_hours=8))
    db_session.commit()
    body = client.get("/api/kpi/absenteeism/trend",
                      params={"start_date": "2026-06-10", "end_date": "2026-06-10"}).json()
    assert body and _num(body[0]["value"])


def test_otd_by_client_percentage_is_number(client, db_session):
    db_session.add(WorkOrder(work_order_id="WO1", client_id="C1", style_model="M1", planned_quantity=10,
                             status=WorkOrderStatus.SHIPPED, required_date=datetime(2026, 6, 10, 8),
                             actual_delivery_date=datetime(2026, 6, 12, 8)))
    db_session.commit()
    body = client.get("/api/kpi/otd/by-client",
                      params={"start_date": "2026-06-01", "end_date": "2026-06-30"}).json()
    assert body and _num(body[0]["otd_percentage"])


def test_quality_by_product_fpy_is_number(client, db_session):
    db_session.add(WorkOrder(work_order_id="WO1", client_id="C1", style_model="M1", planned_quantity=10,
                             status=WorkOrderStatus.SHIPPED))
    db_session.add(QualityEntry(quality_entry_id="QE1", client_id="C1", work_order_id="WO1",
                                shift_date=datetime(2026, 6, 10, 8), units_inspected=100, units_passed=90,
                                units_defective=10, total_defects_count=10))
    db_session.commit()
    body = client.get("/api/quality/kpi/by-product",
                      params={"start_date": "2026-06-10", "end_date": "2026-06-10"}).json()
    assert body and _num(body[0]["fpy"])
```

> **Note for implementer:** these assert the field is a JSON number. Adjust the exact endpoint paths / seed rows only if collection or an empty-body reveals a path or required-column mismatch (confirm paths with `grep -n "@.*get(" backend/routes/kpi/trends.py backend/routes/kpi/otd.py backend/routes/quality/pareto.py`). Do NOT weaken `_num` to accept strings.

- [ ] **Step 2: Run the tests (they pass on SQLite pre-fix — that is expected)**

Run: `cd backend && pytest tests/test_kpi/test_decimal_json_serialization.py -v`
Expected: PASS on SQLite (the field is already int/float here). This confirms the tests are green and stable; they guard against a future regression that would return a string.

- [ ] **Step 3: Apply the float() casts (5 sites)**

`backend/routes/kpi/trends.py:222` (`get_quality_trend`):
```python
# before
            "value": round((r.passed / r.inspected) * 100, 2) if r.inspected and r.inspected > 0 else 0,
# after
            "value": round((float(r.passed) / float(r.inspected)) * 100, 2) if r.inspected and r.inspected > 0 else 0,
```

`backend/routes/kpi/trends.py:394` (`get_otd_trend`):
```python
# before
        {"date": str(r.date), "value": round((r.on_time / r.total * 100) if r.total > 0 else 0, 2)} for r in results
# after
        {"date": str(r.date), "value": round((float(r.on_time) / float(r.total) * 100) if r.total > 0 else 0, 2)}
        for r in results
```

`backend/routes/kpi/trends.py:434` (`get_absenteeism_trend`):
```python
# before
            "value": round((r.absent / r.scheduled * 100) if r.scheduled and r.scheduled > 0 else 0, 2),
# after
            "value": round((float(r.absent) / float(r.scheduled) * 100) if r.scheduled and r.scheduled > 0 else 0, 2),
```

`backend/routes/kpi/otd.py:175` (`get_otd_by_client`):
```python
# before
            "otd_percentage": round((r.on_time / r.total_deliveries * 100) if r.total_deliveries > 0 else 0, 1),
# after
            "otd_percentage": round((float(r.on_time) / float(r.total_deliveries) * 100) if r.total_deliveries > 0 else 0, 1),
```

`backend/routes/quality/pareto.py:179` (`get_quality_by_product`):
```python
# before
            "fpy": round((r.passed / r.inspected) * 100, 1) if r.inspected and r.inspected > 0 else 0,
# after
            "fpy": round((float(r.passed) / float(r.inspected)) * 100, 1) if r.inspected and r.inspected > 0 else 0,
```

(Line numbers are indicative — match on the exact `round((r.<x> / r.<y> ...` expression in each named function.)

- [ ] **Step 4: Run the tests + the existing trend/quality tests**

Run: `cd backend && pytest tests/test_kpi/test_decimal_json_serialization.py -v`
Expected: PASS (5).

Run: `cd backend && pytest tests/ -k "trend or otd or quality or absentee or pareto" -v`
Expected: PASS (existing trend/quality tests unchanged — no shape change).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/kpi/trends.py backend/routes/kpi/otd.py backend/routes/quality/pareto.py backend/tests/test_kpi/test_decimal_json_serialization.py
git commit -m "fix(kpi): return JSON numbers not Decimal-strings for 5 aggregate fields"
```

---

## Post-deploy: live MariaDB verification (the real proof)
After merge + VM deploy, `curl` (authenticated) each of the 5 endpoints and confirm `value`/`otd_percentage`/`fpy` decode as JSON numbers, not `"…"` strings — e.g. `/api/kpi/on-time-delivery/trend` previously returned `{"value":"0.00"}`, must now return `{"value":0.0}`.

## Self-Review
**Spec coverage:** all 5 sites (quality/OTD/absenteeism trends + otd-by-client + quality-by-product) → Task 1 steps; contract-guard tests + honest MariaDB-only caveat → Global Constraints + Task 1 note; live-verify → post-deploy. **Placeholders:** none — every before/after is concrete. **Consistency:** `float(r.<num>) / float(r.<den>)` pattern identical across all 5; `_num` helper rejects strings and bools.

## Global verification
`cd backend && pytest tests/test_kpi/test_decimal_json_serialization.py tests/ -k "trend or otd or quality or pareto or absentee" -q`
