# Diagnostic KPI Charts SP2 — Data-Driven Cause Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a KPI trend point is out-of-control, enrich its tooltip with the dominant contributing factor from that day's operational data (top downtime reason / defect type / absence type / late orders / oldest hold), falling back to SP1's value+hint for metrics with no reliable driver.

**Architecture:** A pure backend cause service (`kpi_cause_service.py`) exposes one driver function per family, returning a uniform `CauseResult`. A single dispatching endpoint `GET /api/kpi/{metric}/cause` maps each metric to its driver (or a null response for the 3 fallback metrics). The frontend `KpiTrendChart`, after SP1's OOC computation identifies the sparse OOC dates, batch-fetches their causes and injects one localized cause line into the existing tooltip.

**Tech Stack:** FastAPI + SQLAlchemy (backend, SQLite + MariaDB portable); Vue 3.5 + vue-chartjs + vue-i18n (frontend); pytest + vitest.

## Global Constraints

- **Cause value must mirror the trend endpoint's per-day math**, not the dual-view service. OEE per-day constants (from `backend/routes/kpi/trends.py` `/oee/trend`): `scheduled = entries × 8`; `downtime_hours = sum(downtime_duration_minutes) / 60`; `performance` null-default `95`; `quality` = `sum(units_passed)/sum(units_inspected)×100`, null-default `97`; `availability = ((scheduled − downtime)/scheduled)×100`, fallback `90` when `scheduled==0`.
- **Portability (SQLite + MariaDB):** date filtering ONLY via `datetime.combine(day, datetime.min/max.time())` bounds on the entity's `shift_date`/`required_date`/`hold_date`. NO `julianday()`/`strftime()`. Hold age = Python-side `(day - hold.hold_date.date()).days`. (See [[holds-julianday-mariadb-bug]].)
- **Column-name traps:** `DefectDetail` tenant column is **`client_id_fk`**; `QualityEntry`/all others use **`client_id`**. `DefectDetail` has no date column — join `QualityEntry` for `shift_date`.
- **10 canonical metric keys** (match the frontend `KPI_CHART_CONFIG` metricKey strings exactly): `efficiency, performance, quality, availability, oee, wipAging, otd, absenteeism, ppm, throughput`. Real-driver (7): `quality, ppm, availability, oee, absenteeism, otd, wipAging`. Fallback → null (3): `efficiency, performance, throughput`.
- **OpenAPI golden master:** adding the route breaks `backend/tests/test_bootstrap/test_openapi_surface.py::test_openapi_route_set_unchanged` until `openapi_surface.json` is regenerated. Keep the new router's `tags=["KPI Calculations"]` so the tag set is unchanged.
- **i18n:** cause tooltip keys are resolved via template literal `t(\`kpi.cause.${kind}\`)`, which EVADES the referenced-keys gate. Every `kpi.cause.*` key MUST be added to BOTH `en.json` and `es.json` and covered by an explicit resolution test.
- Backend coverage gate ≥75% stays green; frontend coverage thresholds stay green.
- Auth/client-scoping copies the trend-endpoint convention verbatim: `Depends(get_current_user)`; `effective_client_id = client_id; if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned: effective_client_id = current_user.client_id_assigned`.

---

### Task 1: Cause service — CauseResult + direct top-N drivers (downtime, defect, absence)

**Files:**
- Create: `backend/services/kpi_cause_service.py`
- Test: `backend/tests/test_services/test_kpi_cause_service.py`

**Interfaces:**
- Produces:
  - `@dataclass CauseResult: kind: str; factor: str; value: float | None; unit: str; share: float | None`
  - `def top_downtime_reason(session: Session, client_id: str | None, day: date) -> CauseResult | None` (kind `"downtime"`, unit `"min"`)
  - `def top_defect_type(session: Session, client_id: str | None, day: date) -> CauseResult | None` (kind `"defect"`, unit `"count"`)
  - `def top_absence_type(session: Session, client_id: str | None, day: date) -> CauseResult | None` (kind `"absence"`, unit `"count"`)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_services/test_kpi_cause_service.py
from datetime import date, datetime

from sqlalchemy import event, create_engine
from sqlalchemy.orm import Session as SASession

from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.defect_detail import DefectDetail
from backend.orm.attendance_entry import AttendanceEntry, AbsenceType
from backend.services.kpi_cause_service import (
    CauseResult,
    top_downtime_reason,
    top_defect_type,
    top_absence_type,
)

DAY = date(2026, 6, 10)


def _dt(h):
    return datetime(2026, 6, 10, h, 0, 0)


def test_top_downtime_reason_picks_max_minutes_and_share(db_session):
    db_session.add_all([
        DowntimeEntry(downtime_entry_id="DT1", client_id="C1", shift_date=_dt(8),
                      downtime_reason="Changeover", downtime_duration_minutes=90),
        DowntimeEntry(downtime_entry_id="DT2", client_id="C1", shift_date=_dt(9),
                      downtime_reason="Breakdown", downtime_duration_minutes=30),
        DowntimeEntry(downtime_entry_id="DT3", client_id="C1", shift_date=_dt(10),
                      downtime_reason="Changeover", downtime_duration_minutes=30),
    ])
    db_session.commit()
    res = top_downtime_reason(db_session, "C1", DAY)
    assert res == CauseResult(kind="downtime", factor="Changeover", value=120.0, unit="min", share=0.8)


def test_top_downtime_reason_empty_day_returns_none(db_session):
    assert top_downtime_reason(db_session, "C1", DAY) is None


def test_top_defect_type_joins_quality_entry_for_date(db_session):
    db_session.add(QualityEntry(quality_entry_id="QE1", client_id="C1", work_order_id="WO1",
                                shift_date=_dt(8), units_inspected=100, units_passed=90,
                                units_defective=10, total_defects_count=10))
    db_session.flush()
    db_session.add_all([
        DefectDetail(defect_detail_id="DD1", quality_entry_id="QE1", client_id_fk="C1",
                     defect_type="Burr", defect_count=7),
        DefectDetail(defect_detail_id="DD2", quality_entry_id="QE1", client_id_fk="C1",
                     defect_type="Scratch", defect_count=3),
    ])
    db_session.commit()
    res = top_defect_type(db_session, "C1", DAY)
    assert res.kind == "defect" and res.factor == "Burr" and res.value == 7.0 and res.share == 0.7


def test_top_absence_type_groups_by_coalesced_type(db_session):
    db_session.add_all([
        AttendanceEntry(attendance_entry_id="AE1", client_id="C1", employee_id=1, shift_date=_dt(8),
                        scheduled_hours=8, is_absent=1, absence_type=AbsenceType.MEDICAL_LEAVE),
        AttendanceEntry(attendance_entry_id="AE2", client_id="C1", employee_id=2, shift_date=_dt(8),
                        scheduled_hours=8, is_absent=1, absence_type=AbsenceType.MEDICAL_LEAVE),
        AttendanceEntry(attendance_entry_id="AE3", client_id="C1", employee_id=3, shift_date=_dt(8),
                        scheduled_hours=8, is_absent=1, absence_type=AbsenceType.VACATION),
    ])
    db_session.commit()
    res = top_absence_type(db_session, "C1", DAY)
    assert res.kind == "absence" and res.factor == "MEDICAL_LEAVE" and res.value == 2.0


def test_top_defect_type_under_fk_enforcement(tmp_path):
    """Portability guard: the DefectDetail↔QualityEntry join runs under FK enforcement (MariaDB-like)."""
    from backend.db.migrate import upgrade_to_head
    from backend.db.factories import TestDataFactory

    url = f"sqlite:///{tmp_path / 'fk.db'}"
    upgrade_to_head(url)
    eng = create_engine(url)

    @event.listens_for(eng, "connect")
    def _fk_on(conn, _rec):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    try:
        with SASession(eng) as s:
            client = TestDataFactory.create_client(s, client_id="C1")
            wo = TestDataFactory.create_work_order(s, client_id="C1")
            s.commit()
            qe = QualityEntry(quality_entry_id="QE1", client_id="C1", work_order_id=wo.work_order_id,
                              shift_date=_dt(8), units_inspected=10, units_passed=8,
                              units_defective=2, total_defects_count=2)
            s.add(qe)
            s.flush()
            s.add(DefectDetail(defect_detail_id="DD1", quality_entry_id="QE1", client_id_fk="C1",
                               defect_type="Burr", defect_count=2))
            s.commit()
            res = top_defect_type(s, "C1", DAY)
            assert res.factor == "Burr"
    finally:
        eng.dispose()
```

> **Note for implementer:** if `TestDataFactory.create_client` / `create_work_order` signatures differ, adapt the FK-enforcement test's parent-row creation to the factory's real API (grep `backend/db/factories.py`); the assertion (`res.factor == "Burr"`) is what matters. If parent creation is awkward, insert the `Client`/`WorkOrder` ORM rows directly with their non-null columns (`WorkOrder` needs `work_order_id, client_id, style_model, planned_quantity`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_services/test_kpi_cause_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.kpi_cause_service'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/kpi_cause_service.py
"""Data-driven cause analysis for out-of-control KPI trend points (SP2).

Each driver takes an open Session, an optional client filter, and a single day,
and returns the dominant contributing factor for that day as a CauseResult, or
None when there is no operational data behind the metric that day.

All date filtering uses datetime.combine bounds (portable SQLite + MariaDB); no
SQLite-only date functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.defect_detail import DefectDetail
from backend.orm.attendance_entry import AttendanceEntry


@dataclass
class CauseResult:
    kind: str            # "downtime"|"defect"|"absence"|"lateOrders"|"hold"|"component"
    factor: str
    value: float | None
    unit: str
    share: float | None


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, datetime.min.time()), datetime.combine(day, datetime.max.time())


def top_downtime_reason(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    start, end = _day_bounds(day)
    q = session.query(
        DowntimeEntry.downtime_reason,
        func.sum(DowntimeEntry.downtime_duration_minutes).label("mins"),
    ).filter(DowntimeEntry.shift_date >= start, DowntimeEntry.shift_date <= end)
    if client_id:
        q = q.filter(DowntimeEntry.client_id == client_id)
    rows = (
        q.group_by(DowntimeEntry.downtime_reason)
        .order_by(func.sum(DowntimeEntry.downtime_duration_minutes).desc())
        .all()
    )
    if not rows:
        return None
    total = sum(float(r.mins or 0) for r in rows)
    top = rows[0]
    top_val = float(top.mins or 0)
    return CauseResult(
        kind="downtime", factor=str(top.downtime_reason), value=top_val, unit="min",
        share=(top_val / total if total > 0 else None),
    )


def top_defect_type(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    start, end = _day_bounds(day)
    q = (
        session.query(DefectDetail.defect_type, func.sum(DefectDetail.defect_count).label("cnt"))
        .join(QualityEntry, DefectDetail.quality_entry_id == QualityEntry.quality_entry_id)
        .filter(QualityEntry.shift_date >= start, QualityEntry.shift_date <= end)
    )
    if client_id:
        q = q.filter(DefectDetail.client_id_fk == client_id)
    rows = q.group_by(DefectDetail.defect_type).order_by(func.sum(DefectDetail.defect_count).desc()).all()
    if not rows:
        return None
    total = sum(int(r.cnt or 0) for r in rows)
    top = rows[0]
    top_val = float(int(top.cnt or 0))
    return CauseResult(
        kind="defect", factor=str(top.defect_type), value=top_val, unit="count",
        share=(top_val / total if total > 0 else None),
    )


def top_absence_type(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    start, end = _day_bounds(day)
    label = func.coalesce(AttendanceEntry.absence_type, "Unspecified").label("reason")
    q = session.query(label, func.count().label("cnt")).filter(
        AttendanceEntry.shift_date >= start,
        AttendanceEntry.shift_date <= end,
        AttendanceEntry.is_absent == 1,
    )
    if client_id:
        q = q.filter(AttendanceEntry.client_id == client_id)
    rows = q.group_by(label).order_by(func.count().desc()).all()
    if not rows:
        return None
    total = sum(int(r.cnt) for r in rows)
    top = rows[0]
    top_val = float(int(top.cnt))
    return CauseResult(
        kind="absence", factor=str(top.reason), value=top_val, unit="count",
        share=(top_val / total if total > 0 else None),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_services/test_kpi_cause_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/kpi_cause_service.py backend/tests/test_services/test_kpi_cause_service.py
git commit -m "feat(kpi): SP2 cause service — downtime/defect/absence drivers"
```

---

### Task 2: Cause service — late work orders + oldest active hold drivers

**Files:**
- Modify: `backend/services/kpi_cause_service.py`
- Test: `backend/tests/test_services/test_kpi_cause_service.py` (add cases)

**Interfaces:**
- Consumes: `CauseResult` (Task 1)
- Produces:
  - `def late_work_orders(session: Session, client_id: str | None, day: date) -> CauseResult | None` (kind `"lateOrders"`, unit `"count"`, share `None`)
  - `def oldest_active_hold(session: Session, client_id: str | None, day: date) -> CauseResult | None` (kind `"hold"`, unit `"days"`, share `None`)

- [ ] **Step 1: Write the failing test** (append to the Task 1 test file)

```python
from datetime import timedelta

from backend.orm.work_order import WorkOrder, WorkOrderStatus
from backend.orm.hold_entry import HoldEntry, HoldStatus
from backend.services.kpi_cause_service import late_work_orders, oldest_active_hold


def _wo(wid, required, delivered):
    return WorkOrder(work_order_id=wid, client_id="C1", style_model="M1", planned_quantity=10,
                     status=WorkOrderStatus.ACTIVE, required_date=required, actual_delivery_date=delivered)


def test_late_work_orders_counts_late_and_undelivered_due_that_day(db_session):
    db_session.add_all([
        _wo("W1", _dt(0), _dt(0) + timedelta(days=2)),   # delivered late -> counts
        _wo("W2", _dt(0), None),                          # not delivered, due today -> counts
        _wo("W3", _dt(0), _dt(0) - timedelta(hours=1)),   # delivered early -> excluded
    ])
    db_session.commit()
    res = late_work_orders(db_session, "C1", DAY)
    assert res.kind == "lateOrders" and res.value == 2.0 and res.factor == "2"


def test_late_work_orders_none_when_all_on_time(db_session):
    db_session.add(_wo("W9", _dt(0), _dt(0) - timedelta(hours=1)))
    db_session.commit()
    assert late_work_orders(db_session, "C1", DAY) is None


def test_oldest_active_hold_reports_reason_and_age_days(db_session):
    db_session.add_all([
        HoldEntry(hold_entry_id="H1", client_id="C1", work_order_id="W1",
                  hold_status=HoldStatus.ON_HOLD, hold_date=datetime(2026, 6, 1, 8), resume_date=None),
        HoldEntry(hold_entry_id="H2", client_id="C1", work_order_id="W2",
                  hold_status=HoldStatus.ON_HOLD, hold_date=datetime(2026, 6, 8, 8), resume_date=None),
        # resumed before DAY -> not active on DAY
        HoldEntry(hold_entry_id="H3", client_id="C1", work_order_id="W3",
                  hold_status=HoldStatus.ON_HOLD, hold_date=datetime(2026, 5, 1, 8),
                  resume_date=datetime(2026, 6, 5, 8)),
    ])
    db_session.commit()
    res = oldest_active_hold(db_session, "C1", DAY)
    assert res.kind == "hold" and res.unit == "days" and res.value == 9.0  # 2026-06-10 - 2026-06-01
    assert res.factor  # hold_reason (may be None -> "Unspecified")


def test_oldest_active_hold_none_when_no_active_holds(db_session):
    assert oldest_active_hold(db_session, "C1", DAY) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_services/test_kpi_cause_service.py -k "late_work_orders or oldest_active_hold" -v`
Expected: FAIL — `ImportError: cannot import name 'late_work_orders'`

- [ ] **Step 3: Write minimal implementation** (append to `kpi_cause_service.py`)

```python
from sqlalchemy import or_

from backend.orm.work_order import WorkOrder
from backend.orm.hold_entry import HoldEntry, HoldStatus


def late_work_orders(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    start, end = _day_bounds(day)
    q = session.query(func.count(WorkOrder.work_order_id)).filter(
        WorkOrder.required_date >= start,
        WorkOrder.required_date <= end,
        or_(
            WorkOrder.actual_delivery_date.is_(None),
            WorkOrder.actual_delivery_date > WorkOrder.required_date,
        ),
    )
    if client_id:
        q = q.filter(WorkOrder.client_id == client_id)
    late = int(q.scalar() or 0)
    if late == 0:
        return None
    return CauseResult(kind="lateOrders", factor=str(late), value=float(late), unit="count", share=None)


def oldest_active_hold(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    _, end = _day_bounds(day)
    q = session.query(HoldEntry).filter(
        HoldEntry.hold_status == HoldStatus.ON_HOLD,
        HoldEntry.hold_date.isnot(None),
        HoldEntry.hold_date <= end,
        or_(HoldEntry.resume_date.is_(None), HoldEntry.resume_date > end),
    )
    if client_id:
        q = q.filter(HoldEntry.client_id == client_id)
    hold = q.order_by(HoldEntry.hold_date.asc()).first()
    if hold is None or hold.hold_date is None:
        return None
    age_days = (day - hold.hold_date.date()).days
    return CauseResult(
        kind="hold", factor=str(hold.hold_reason or "Unspecified"),
        value=float(age_days), unit="days", share=None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_services/test_kpi_cause_service.py -v`
Expected: PASS (9 tests total)

- [ ] **Step 5: Commit**

```bash
git add backend/services/kpi_cause_service.py backend/tests/test_services/test_kpi_cause_service.py
git commit -m "feat(kpi): SP2 cause service — late-order and oldest-hold drivers"
```

---

### Task 3: Cause service — OEE loss-decomposition

**Files:**
- Modify: `backend/services/kpi_cause_service.py`
- Test: `backend/tests/test_services/test_kpi_cause_service.py` (add cases)

**Interfaces:**
- Consumes: `CauseResult`, `top_downtime_reason`, `top_defect_type` (Tasks 1–2)
- Produces: `def oee_dominant_loss(session: Session, client_id: str | None, day: date) -> CauseResult | None`
  - Mirrors the `/oee/trend` per-day math to compute availability/performance/quality, finds the dominant loss, and returns that loss's driver: availability-loss → `top_downtime_reason`; quality-loss → `top_defect_type`; performance-loss → `CauseResult(kind="component", factor="performance", value=None, unit="", share=None)`. Returns `None` when there are no production entries that day or no loss (all components ≥ 100).

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal

from backend.orm.production_entry import ProductionEntry
from backend.services.kpi_cause_service import oee_dominant_loss


def _pe(pid, perf):
    return ProductionEntry(production_entry_id=pid, client_id="C1", product_id=1, shift_id=1,
                           production_date=_dt(8), shift_date=_dt(8), units_produced=100,
                           run_time_hours=Decimal("8.0"), employees_assigned=5,
                           performance_percentage=Decimal(str(perf)), entered_by="u1")


def test_oee_dominant_loss_availability(db_session):
    # 1 entry -> scheduled 8h; 240 min downtime -> 4h -> availability 50 (loss 50, dominant)
    db_session.add(_pe("PE1", 95))
    db_session.add(QualityEntry(quality_entry_id="QE1", client_id="C1", work_order_id="WO1",
                                shift_date=_dt(8), units_inspected=100, units_passed=100,
                                units_defective=0, total_defects_count=0))
    db_session.add(DowntimeEntry(downtime_entry_id="DT1", client_id="C1", shift_date=_dt(9),
                                 downtime_reason="Breakdown", downtime_duration_minutes=240))
    db_session.commit()
    res = oee_dominant_loss(db_session, "C1", DAY)
    assert res.kind == "downtime" and res.factor == "Breakdown"


def test_oee_dominant_loss_quality(db_session):
    db_session.add(_pe("PE1", 98))  # perf loss 2, no downtime -> avail loss 0
    db_session.add(QualityEntry(quality_entry_id="QE1", client_id="C1", work_order_id="WO1",
                                shift_date=_dt(8), units_inspected=100, units_passed=70,
                                units_defective=30, total_defects_count=30))  # quality 70, loss 30
    db_session.flush()
    db_session.add(DefectDetail(defect_detail_id="DD1", quality_entry_id="QE1", client_id_fk="C1",
                                defect_type="Burr", defect_count=30))
    db_session.commit()
    res = oee_dominant_loss(db_session, "C1", DAY)
    assert res.kind == "defect" and res.factor == "Burr"


def test_oee_dominant_loss_performance_component(db_session):
    db_session.add(_pe("PE1", 60))  # perf loss 40 dominant; no downtime, quality 100
    db_session.add(QualityEntry(quality_entry_id="QE1", client_id="C1", work_order_id="WO1",
                                shift_date=_dt(8), units_inspected=100, units_passed=100,
                                units_defective=0, total_defects_count=0))
    db_session.commit()
    res = oee_dominant_loss(db_session, "C1", DAY)
    assert res == CauseResult(kind="component", factor="performance", value=None, unit="", share=None)


def test_oee_dominant_loss_none_without_production(db_session):
    assert oee_dominant_loss(db_session, "C1", DAY) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_services/test_kpi_cause_service.py -k oee_dominant_loss -v`
Expected: FAIL — `ImportError: cannot import name 'oee_dominant_loss'`

- [ ] **Step 3: Write minimal implementation** (append to `kpi_cause_service.py`)

```python
from backend.orm.production_entry import ProductionEntry


def oee_dominant_loss(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    """Decompose the day's OEE (mirroring /oee/trend math) and return the dominant loss's driver."""
    start, end = _day_bounds(day)

    perf_q = session.query(
        func.avg(ProductionEntry.performance_percentage).label("perf"),
        func.count(ProductionEntry.production_entry_id).label("entries"),
    ).filter(ProductionEntry.shift_date >= start, ProductionEntry.shift_date <= end)
    if client_id:
        perf_q = perf_q.filter(ProductionEntry.client_id == client_id)
    pr = perf_q.one()
    entries = int(pr.entries or 0)
    if entries == 0:
        return None
    performance = float(pr.perf) if pr.perf is not None else 95.0

    qual_q = session.query(
        func.sum(QualityEntry.units_passed).label("passed"),
        func.sum(QualityEntry.units_inspected).label("inspected"),
    ).filter(QualityEntry.shift_date >= start, QualityEntry.shift_date <= end)
    if client_id:
        qual_q = qual_q.filter(QualityEntry.client_id == client_id)
    qr = qual_q.one()
    quality = (float(qr.passed) / float(qr.inspected) * 100) if qr.inspected and qr.inspected > 0 else 97.0

    dt_q = session.query(func.sum(DowntimeEntry.downtime_duration_minutes).label("mins")).filter(
        DowntimeEntry.shift_date >= start, DowntimeEntry.shift_date <= end
    )
    if client_id:
        dt_q = dt_q.filter(DowntimeEntry.client_id == client_id)
    downtime_mins = dt_q.scalar()
    downtime = float(downtime_mins) / 60 if downtime_mins else 0.0

    scheduled = entries * 8
    availability = ((scheduled - downtime) / scheduled * 100) if scheduled > 0 else 90.0

    losses = {
        "availability": 100 - min(availability, 100),
        "performance": 100 - min(performance, 100),
        "quality": 100 - min(quality, 100),
    }
    name, loss = max(losses.items(), key=lambda kv: kv[1])
    if loss <= 0:
        return None

    if name == "availability":
        return top_downtime_reason(session, client_id, day) or CauseResult(
            kind="component", factor="availability", value=None, unit="", share=None
        )
    if name == "quality":
        return top_defect_type(session, client_id, day) or CauseResult(
            kind="component", factor="quality", value=None, unit="", share=None
        )
    return CauseResult(kind="component", factor="performance", value=None, unit="", share=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_services/test_kpi_cause_service.py -v`
Expected: PASS (13 tests total)

- [ ] **Step 5: Commit**

```bash
git add backend/services/kpi_cause_service.py backend/tests/test_services/test_kpi_cause_service.py
git commit -m "feat(kpi): SP2 cause service — OEE loss-decomposition"
```

---

### Task 4: Cause endpoint + router registration + OpenAPI snapshot

**Files:**
- Create: `backend/routes/kpi/cause.py`
- Modify: `backend/routes/kpi/__init__.py` (add `router.include_router(cause_router)`)
- Modify: `backend/tests/test_bootstrap/openapi_surface.json` (regenerate)
- Test: `backend/tests/test_kpi/test_cause_endpoint.py`

**Interfaces:**
- Consumes: all cause-service driver functions (Tasks 1–3)
- Produces: `GET /api/kpi/{metric}/cause?date=<YYYY-MM-DD>&client_id=<optional>`
  - 200 body: `{"date": str, "metric": str, "kind": str|None, "factor": str|None, "value": number|None, "unit": str, "share": number|None}`
  - Unknown metric → 422; missing `date` → 422 (FastAPI required-param).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_kpi/test_cause_endpoint.py
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.factories import TestDataFactory
from backend.main import app
from backend.orm.downtime_entry import DowntimeEntry


@pytest.fixture
def db_session(transactional_db):
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(db_session):
    admin = TestDataFactory.create_user(db_session, username="cause_admin", role="admin")
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_availability_cause_returns_top_downtime(client, db_session):
    db_session.add(DowntimeEntry(downtime_entry_id="DT1", client_id="C1",
                                 shift_date=datetime(2026, 6, 10, 8),
                                 downtime_reason="Changeover", downtime_duration_minutes=60))
    db_session.commit()
    r = client.get("/api/kpi/availability/cause", params={"date": "2026-06-10", "client_id": "C1"})
    assert r.status_code == 200
    body = r.json()
    assert body["metric"] == "availability" and body["kind"] == "downtime"
    assert body["factor"] == "Changeover" and body["unit"] == "min"


def test_fallback_metric_returns_null_cause(client):
    r = client.get("/api/kpi/efficiency/cause", params={"date": "2026-06-10"})
    assert r.status_code == 200
    assert r.json() == {"date": "2026-06-10", "metric": "efficiency",
                        "kind": None, "factor": None, "value": None, "unit": "", "share": None}


def test_real_metric_no_data_returns_null_cause(client):
    r = client.get("/api/kpi/availability/cause", params={"date": "2026-06-10", "client_id": "C1"})
    assert r.status_code == 200 and r.json()["factor"] is None


def test_unknown_metric_422(client):
    r = client.get("/api/kpi/bogus/cause", params={"date": "2026-06-10"})
    assert r.status_code == 422


def test_missing_date_422(client):
    r = client.get("/api/kpi/availability/cause")
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_kpi/test_cause_endpoint.py -v`
Expected: FAIL — 404 on the cause path (route not registered)

- [ ] **Step 3: Write minimal implementation**

Create `backend/routes/kpi/cause.py`:

```python
"""Dispatching endpoint for data-driven KPI cause analysis (SP2)."""
from __future__ import annotations

from datetime import date as date_cls
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.orm.user import User
from backend.services import kpi_cause_service as svc

cause_router = APIRouter(prefix="/api/kpi", tags=["KPI Calculations"])

# Real-driver metrics -> their driver function. Fallback metrics are absent here.
_DRIVERS: dict[str, Callable[[Session, Optional[str], date_cls], Any]] = {
    "quality": svc.top_defect_type,
    "ppm": svc.top_defect_type,
    "availability": svc.top_downtime_reason,
    "absenteeism": svc.top_absence_type,
    "otd": svc.late_work_orders,
    "wipAging": svc.oldest_active_hold,
    "oee": svc.oee_dominant_loss,
}
_FALLBACK_METRICS = {"efficiency", "performance", "throughput"}
_ALL_METRICS = set(_DRIVERS) | _FALLBACK_METRICS


@cause_router.get("/{metric}/cause")
def get_kpi_cause(
    metric: str,
    date: date_cls,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if metric not in _ALL_METRICS:
        raise HTTPException(status_code=422, detail=f"Unknown metric: {metric}")

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    empty = {"date": date.isoformat(), "metric": metric,
             "kind": None, "factor": None, "value": None, "unit": "", "share": None}

    driver = _DRIVERS.get(metric)
    if driver is None:  # fallback metric -> keep SP1 hint on the frontend
        return empty

    result = driver(db, effective_client_id, date)
    if result is None:
        return empty
    return {"date": date.isoformat(), "metric": metric, "kind": result.kind,
            "factor": result.factor, "value": result.value, "unit": result.unit, "share": result.share}
```

Modify `backend/routes/kpi/__init__.py` — add the import and include (alongside the existing includes):

```python
from backend.routes.kpi.cause import cause_router  # noqa: E402
...
router.include_router(cause_router)
```

- [ ] **Step 4: Run test to verify it passes; then regenerate the OpenAPI snapshot**

Run: `cd backend && pytest tests/test_kpi/test_cause_endpoint.py -v`
Expected: PASS (5 tests)

Then confirm the snapshot break and regenerate:

Run: `cd backend && pytest tests/test_bootstrap/test_openapi_surface.py -v`
Expected: FAIL on `test_openapi_route_set_unchanged` (new `/api/kpi/{metric}/cause` route)

Regenerate the snapshot:

Run:
```bash
cd backend && python -c "import json; from tests.test_bootstrap.test_openapi_surface import current_surface; json.dump(current_surface(), open('tests/test_bootstrap/openapi_surface.json','w'), indent=2); print('regenerated')"
```

Re-run: `cd backend && pytest tests/test_bootstrap/test_openapi_surface.py -v`
Expected: PASS (both tests; tag set unchanged, route set now includes the cause route)

- [ ] **Step 5: Commit**

```bash
git add backend/routes/kpi/cause.py backend/routes/kpi/__init__.py \
        backend/tests/test_kpi/test_cause_endpoint.py backend/tests/test_bootstrap/openapi_surface.json
git commit -m "feat(kpi): SP2 dispatching /api/kpi/{metric}/cause endpoint"
```

---

### Task 5: Frontend cause API client

**Files:**
- Modify: `frontend/src/services/api/kpi.ts`
- Test: `frontend/src/services/api/__tests__/kpiCause.spec.ts`

**Interfaces:**
- Produces:
  - `interface KpiCause { date: string; kind: string | null; factor: string | null; value: number | null; unit: string; share: number | null }`
  - `fetchKpiCause(metricKey: string, date: string, clientId?: string | null): Promise<KpiCause | null>` — returns `null` when the response has no factor or on error.
  - `fetchKpiCauses(metricKey: string, dates: string[], clientId?: string | null): Promise<Record<string, KpiCause>>` — concurrent per-date fetch, keyed by date; failures drop out silently.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/services/api/__tests__/kpiCause.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

const get = vi.fn()
vi.mock('../client', () => ({ default: { get: (...a: unknown[]) => get(...a) } }))

import { fetchKpiCause, fetchKpiCauses } from '../kpi'

describe('fetchKpiCause / fetchKpiCauses', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls the cause endpoint and returns the payload when a factor exists', async () => {
    get.mockResolvedValue({ data: { date: '2026-06-10', kind: 'downtime', factor: 'Changeover', value: 60, unit: 'min', share: 0.5 } })
    const res = await fetchKpiCause('availability', '2026-06-10', 'C1')
    expect(get).toHaveBeenCalledWith('/kpi/availability/cause', { params: { date: '2026-06-10', client_id: 'C1' } })
    expect(res?.factor).toBe('Changeover')
  })

  it('returns null when the response has no factor', async () => {
    get.mockResolvedValue({ data: { date: '2026-06-10', factor: null } })
    expect(await fetchKpiCause('efficiency', '2026-06-10')).toBeNull()
  })

  it('returns null on error', async () => {
    get.mockRejectedValue(new Error('boom'))
    expect(await fetchKpiCause('availability', '2026-06-10')).toBeNull()
  })

  it('batches multiple dates into a date-keyed map, dropping nulls', async () => {
    get
      .mockResolvedValueOnce({ data: { date: '2026-06-10', factor: 'Burr', kind: 'defect', value: 3, unit: 'count', share: 1 } })
      .mockResolvedValueOnce({ data: { date: '2026-06-11', factor: null } })
    const map = await fetchKpiCauses('quality', ['2026-06-10', '2026-06-11'], 'C1')
    expect(Object.keys(map)).toEqual(['2026-06-10'])
    expect(map['2026-06-10'].factor).toBe('Burr')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/services/api/__tests__/kpiCause.spec.ts`
Expected: FAIL — `fetchKpiCause is not a function`

- [ ] **Step 3: Write minimal implementation** (append to `frontend/src/services/api/kpi.ts`)

```typescript
export interface KpiCause {
  date: string
  kind: string | null
  factor: string | null
  value: number | null
  unit: string
  share: number | null
}

export const fetchKpiCause = (
  metricKey: string,
  date: string,
  clientId?: string | null,
): Promise<KpiCause | null> =>
  api
    .get(`/kpi/${metricKey}/cause`, { params: { date, client_id: clientId ?? undefined } })
    .then((r) => {
      const d = r.data as KpiCause | undefined
      return d && d.factor != null ? d : null
    })
    .catch(() => null)

export const fetchKpiCauses = (
  metricKey: string,
  dates: string[],
  clientId?: string | null,
): Promise<Record<string, KpiCause>> =>
  Promise.all(dates.map((d) => fetchKpiCause(metricKey, d, clientId))).then((results) => {
    const map: Record<string, KpiCause> = {}
    for (const c of results) if (c) map[c.date] = c
    return map
  })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/services/api/__tests__/kpiCause.spec.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api/kpi.ts frontend/src/services/api/__tests__/kpiCause.spec.ts
git commit -m "feat(kpi): SP2 frontend cause API client"
```

---

### Task 6: Config `causeDriven` flag + i18n cause keys

**Files:**
- Modify: `frontend/src/components/kpi/kpiChartConfig.ts` (add `causeDriven` to interface + each item)
- Modify: `frontend/src/i18n/locales/en.json` (add `kpi.cause` object)
- Modify: `frontend/src/i18n/locales/es.json` (add `kpi.cause` object)
- Test: `frontend/src/components/kpi/__tests__/kpiChartConfig.cause.spec.ts`

**Interfaces:**
- Produces: `KpiChartConfigItem.causeDriven: boolean` (true for `quality, availability, oee, wipAging, otd, absenteeism, ppm`; false for `efficiency, performance, throughput`).
- Produces (i18n): `kpi.cause.downtime`, `kpi.cause.defect`, `kpi.cause.absence`, `kpi.cause.lateOrders`, `kpi.cause.hold`, `kpi.cause.component` in both locales.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/kpi/__tests__/kpiChartConfig.cause.spec.ts
import { describe, it, expect } from 'vitest'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'
import { KPI_CHART_CONFIG } from '../kpiChartConfig'

const REAL = new Set(['quality', 'availability', 'oee', 'wipAging', 'otd', 'absenteeism', 'ppm'])
const CAUSE_KINDS = ['downtime', 'defect', 'absence', 'lateOrders', 'hold', 'component']

describe('SP2 cause config + i18n', () => {
  it('flags exactly the seven real-driver metrics as causeDriven', () => {
    for (const cfg of KPI_CHART_CONFIG) {
      expect(cfg.causeDriven).toBe(REAL.has(cfg.metricKey))
    }
  })

  it('defines every kpi.cause.<kind> key in both locales', () => {
    for (const kind of CAUSE_KINDS) {
      expect((en as any).kpi.cause[kind], `en kpi.cause.${kind}`).toBeTruthy()
      expect((es as any).kpi.cause[kind], `es kpi.cause.${kind}`).toBeTruthy()
    }
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kpi/__tests__/kpiChartConfig.cause.spec.ts`
Expected: FAIL — `cfg.causeDriven` is undefined / `kpi.cause` is undefined

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/components/kpi/kpiChartConfig.ts`, add `causeDriven: boolean` to the `KpiChartConfigItem` interface, and set it on each of the 10 entries (true for quality, availability, oee, wipAging, otd, absenteeism, ppm; false for efficiency, performance, throughput). Example (apply the flag to every entry):

```typescript
export interface KpiChartConfigItem {
  metricKey: string
  titleKey: string
  thresholdKey: string
  alertKey: string | null
  unit: string
  causeDriven: boolean
  fetchTrend: (_params: Record<string, unknown>) => Promise<unknown>
}

// each entry gains causeDriven, e.g.:
{ metricKey: 'efficiency',   titleKey: 'kpi.efficiency',   thresholdKey: 'efficiency',   alertKey: 'efficiency',    unit: '%',   causeDriven: false, fetchTrend: getEfficiencyTrend },
{ metricKey: 'quality',      titleKey: 'kpi.quality',      thresholdKey: 'quality_rate', alertKey: 'quality',       unit: '%',   causeDriven: true,  fetchTrend: getQualityTrend },
{ metricKey: 'availability', titleKey: 'kpi.availability', thresholdKey: 'availability', alertKey: null,            unit: '%',   causeDriven: true,  fetchTrend: getAvailabilityTrend },
{ metricKey: 'oee',          titleKey: 'kpi.oee',          thresholdKey: 'oee',          alertKey: null,            unit: '%',   causeDriven: true,  fetchTrend: getOEETrend },
{ metricKey: 'wipAging',     titleKey: 'kpi.wipAging',     thresholdKey: 'wip_aging',    alertKey: 'hold_approval', unit: 'd',   causeDriven: true,  fetchTrend: getWIPAgingTrend },
{ metricKey: 'otd',          titleKey: 'kpi.otd',          thresholdKey: 'otd',          alertKey: 'otd',           unit: '%',   causeDriven: true,  fetchTrend: getOnTimeDeliveryTrend },
{ metricKey: 'absenteeism',  titleKey: 'kpi.absenteeism',  thresholdKey: 'absenteeism',  alertKey: null,            unit: '%',   causeDriven: true,  fetchTrend: getAbsenteeismTrend },
{ metricKey: 'ppm',          titleKey: 'kpi.ppm',          thresholdKey: 'ppm',          alertKey: null,            unit: 'ppm', causeDriven: true,  fetchTrend: getPpmTrend },
{ metricKey: 'performance',  titleKey: 'kpi.performance',  thresholdKey: 'performance',  alertKey: null,            unit: '%',   causeDriven: false, fetchTrend: getPerformanceTrend },
{ metricKey: 'throughput',   titleKey: 'kpi.throughputTime', thresholdKey: 'throughput', alertKey: null,           unit: 'h',   causeDriven: false, fetchTrend: getThroughputTrend },
```

In `frontend/src/i18n/locales/en.json`, inside the `"kpi"` object, right after the `"ooc"` object, add:

```json
    "cause": {
      "downtime": "Top downtime: {factor} ({value} {unit}, {share}%)",
      "defect": "Top defect: {factor} ({value}, {share}%)",
      "absence": "Top absence: {factor} ({value})",
      "lateOrders": "{value} order(s) due today ran late",
      "hold": "Oldest hold: {factor} ({value} days)",
      "component": "Driven by {factor}"
    },
```

In `frontend/src/i18n/locales/es.json`, inside the `"kpi"` object, right after the `"ooc"` object, add:

```json
    "cause": {
      "downtime": "Mayor paro: {factor} ({value} {unit}, {share}%)",
      "defect": "Mayor defecto: {factor} ({value}, {share}%)",
      "absence": "Mayor ausencia: {factor} ({value})",
      "lateOrders": "{value} orden(es) con entrega vencida hoy",
      "hold": "Retención más antigua: {factor} ({value} días)",
      "component": "Causado por {factor}"
    },
```

> **Note:** the `component` value's `{factor}` receives a localized component label (`Performance`/`Availability`/`Quality`), resolved in the component via the existing `kpi.performance`/`kpi.availability`/`kpi.quality` keys (Task 7).

- [ ] **Step 4: Run test to verify it passes; confirm i18n gates still pass**

Run: `cd frontend && npx vitest run src/components/kpi/__tests__/kpiChartConfig.cause.spec.ts`
Expected: PASS (2 tests)

Run: `cd frontend && npx vitest run src/i18n/__tests__/referenced-keys.spec.ts src/i18n/__tests__/locale-parity.spec.ts`
Expected: PASS (locale parity holds — same keys added to both files)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/kpi/kpiChartConfig.ts frontend/src/i18n/locales/en.json \
        frontend/src/i18n/locales/es.json frontend/src/components/kpi/__tests__/kpiChartConfig.cause.spec.ts
git commit -m "feat(kpi): SP2 causeDriven flag + cause i18n keys (en+es)"
```

---

### Task 7: KpiTrendChart cause fetch + tooltip injection + dashboard wiring

**Files:**
- Modify: `frontend/src/components/kpi/KpiTrendChart.vue`
- Modify: `frontend/src/views/KPIDashboard.vue` (pass `:cause-driven="cfg.causeDriven"`)
- Test: `frontend/src/components/kpi/__tests__/KpiTrendChart.spec.ts` (add cases)

**Interfaces:**
- Consumes: `fetchKpiCauses`, `KpiCause` (Task 5); `causeDriven` config flag (Task 6); `kpi.cause.*` keys (Task 6).
- New prop on `KpiTrendChart`: `causeDriven?: boolean` (default `false`).

- [ ] **Step 1: Write the failing test** (add to `KpiTrendChart.spec.ts`)

Add a mock for the cause API at the top of the file (next to the existing `vue-chartjs` mock):

```typescript
import { fetchKpiCauses } from '@/services/api/kpi'
vi.mock('@/services/api/kpi', () => ({
  fetchActiveAlertsForKpi: vi.fn().mockResolvedValue([]),
  fetchKpiCauses: vi.fn().mockResolvedValue({}),
}))
```

Extend the i18n messages object with cause keys so `t` resolves them:

```typescript
// add inside messages.en.kpi:
cause: { downtime: 'Top downtime: {factor} ({value} {unit}, {share}%)', defect: 'Top defect: {factor}',
         absence: 'Top absence: {factor}', lateOrders: '{value} late', hold: 'Oldest hold: {factor}',
         component: 'Driven by {factor}' },
```

New tests:

```typescript
it('fetches causes for OOC dates on a causeDriven metric and injects the cause line', async () => {
  ;(fetchKpiCauses as any).mockResolvedValue({
    '2026-06-11': { date: '2026-06-11', kind: 'downtime', factor: 'Changeover', value: 60, unit: 'min', share: 0.5 },
  })
  const fetchTrend = vi.fn().mockResolvedValue([
    { date: '2026-06-10', value: 90 },
    { date: '2026-06-11', value: 40 }, // OOC (below critical 60)
    { date: '2026-06-12', value: 88 },
  ])
  const w = mount(KpiTrendChart, {
    props: { metricKey: 'availability', title: 'Availability', threshold: { critical: 60, higher_is_better: true },
             clientId: 'C', unit: '%', fetchTrend, alertKey: null, causeDriven: true },
    global: { plugins: [i18n, createVuetify()] },
  })
  await flushPromises()
  expect(fetchKpiCauses).toHaveBeenCalledWith('availability', ['2026-06-11'], 'C')
  // tooltip for the OOC point includes the cause line
  const label = (w.vm as any).tooltipLabel({ datasetIndex: 0, dataIndex: 1, dataset: { label: 'Availability' }, formattedValue: '40' })
  expect(label.some((l: string) => l.includes('Changeover'))).toBe(true)
})

it('does not fetch causes for a fallback (non-causeDriven) metric', async () => {
  const fetchTrend = vi.fn().mockResolvedValue([
    { date: '2026-06-10', value: 90 },
    { date: '2026-06-11', value: 40 },
  ])
  mount(KpiTrendChart, {
    props: { metricKey: 'efficiency', title: 'Efficiency', threshold: { critical: 60, higher_is_better: true },
             clientId: 'C', unit: '%', fetchTrend, alertKey: null, causeDriven: false },
    global: { plugins: [i18n, createVuetify()] },
  })
  await flushPromises()
  expect(fetchKpiCauses).not.toHaveBeenCalled()
})
```

> **Note for implementer:** `tooltipLabel` must be exposed for the test. Add it to the existing `defineExpose` (`defineExpose({ onRangeChange, tooltipLabel })`). The existing tests mock `@/services/api/kpi`; ensure `fetchActiveAlertsForKpi` remains exported by the mock (already included above) so the SP1 tests still pass.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kpi/__tests__/KpiTrendChart.spec.ts`
Expected: FAIL — `fetchKpiCauses` not called / `tooltipLabel` undefined

- [ ] **Step 3: Write minimal implementation** (edit `KpiTrendChart.vue`)

Add the import and prop, a `causes` ref + a monotonic `causeSeq`, a watcher on `points`, and the tooltip injection.

Imports (extend the existing `@/services/api/kpi` import):

```typescript
import { fetchActiveAlertsForKpi, fetchKpiCauses, type KpiCause } from '@/services/api/kpi'
```

Props — add `causeDriven`:

```typescript
interface Props {
  metricKey: string
  title: string
  threshold: OocThreshold | null
  clientId?: string | null
  unit?: string
  fetchTrend: (_params: Record<string, unknown>) => Promise<unknown>
  alertKey?: string | null
  causeDriven?: boolean
}
const props = withDefaults(defineProps<Props>(), { clientId: null, unit: '', alertKey: null, causeDriven: false })
```

State + watcher (place after the existing OOC `watch`):

```typescript
const causes = ref<Record<string, KpiCause>>({})
let causeSeq = 0

// After OOC points are (re)computed, fetch causes for the sparse OOC dates.
// Guarded so a stale response cannot overwrite a newer one; best-effort.
watch(
  points,
  async (pts) => {
    if (!props.causeDriven) return
    const oocDates = pts.filter((p) => p.ooc).map((p) => p.date)
    if (oocDates.length === 0) {
      causes.value = {}
      return
    }
    const seq = ++causeSeq
    try {
      const map = await fetchKpiCauses(props.metricKey, oocDates, props.clientId ?? null)
      if (seq !== causeSeq) return
      causes.value = map
    } catch {
      // best-effort — SP1 tooltip remains
    }
  },
  { immediate: true },
)
```

Tooltip injection — in `tooltipLabel`, after the SP1 reasons loop (after the `for (const reason of point.reasons)` line) and before the alert-message block:

```typescript
  const cause = causes.value[point.date]
  if (cause?.factor) {
    const factorLabel =
      cause.kind === 'component' ? t(`kpi.${cause.factor}`) : cause.factor
    lines.push(
      t(`kpi.cause.${cause.kind}`, {
        factor: factorLabel,
        value: cause.value ?? '',
        unit: cause.unit,
        share: cause.share != null ? Math.round(cause.share * 100) : '',
      }),
    )
  }
```

Expose `tooltipLabel`:

```typescript
defineExpose({ onRangeChange, tooltipLabel })
```

Then in `frontend/src/views/KPIDashboard.vue`, add the prop to the `<KpiTrendChart>` element (after `:alert-key="cfg.alertKey"`, ~line 201):

```html
        :cause-driven="cfg.causeDriven"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/kpi/__tests__/KpiTrendChart.spec.ts`
Expected: PASS (all SP1 tests + 2 new)

Run the broader gates:
Run: `cd frontend && npm run lint && npx vitest run src/components/kpi src/services/api src/i18n`
Expected: PASS (lint clean; component/api/i18n suites green)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/kpi/KpiTrendChart.vue frontend/src/views/KPIDashboard.vue \
        frontend/src/components/kpi/__tests__/KpiTrendChart.spec.ts
git commit -m "feat(kpi): SP2 cause tooltip injection + dashboard wiring"
```

---

## Self-Review

**1. Spec coverage:**
- Honest cause mapping (7 real + 3 fallback) → Tasks 1–4 (drivers + dispatch); `causeDriven` flag → Task 6. ✅
- OEE loss-decomposition mirroring trend math → Task 3 (constants in Global Constraints). ✅
- `kpi_cause_service.py` one-function-per-driver → Tasks 1–3. ✅
- Dispatching endpoint + null for fallback + unknown→422 + OpenAPI regen → Task 4. ✅
- Sparse, guarded batch fetch + tooltip injection after SP1 reasons + SP1 hint preserved → Tasks 5, 7. ✅
- i18n keys in both locales + explicit resolution test (template-literal evasion) → Task 6. ✅
- Portability (datetime.combine bounds, Python-side hold age, no julianday) + FK-enforcement guard → Global Constraints + Task 1 test. ✅
- Best-effort error handling (cause failure leaves SP1 tooltip) → Task 7 watcher `catch`. ✅
- Reuse defect/absence aggregate shapes; net-new downtime + late-WO; not `identify_late_orders` → Tasks 1–2. ✅

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; test code is concrete. The one `> Note` in Task 1 (factory API adaptation) names the exact fallback (direct ORM insert with listed non-null columns), not a vague placeholder.

**3. Type consistency:** `CauseResult(kind, factor, value, unit, share)` identical across Tasks 1–4. Endpoint response keys `{date, metric, kind, factor, value, unit, share}` match `KpiCause` (Task 5) field-for-field. `causeDriven` boolean consistent across Tasks 6–7. Metric key set identical in backend `_DRIVERS`/`_FALLBACK_METRICS` (Task 4) and frontend `REAL` set (Task 6 test) and `KPI_CHART_CONFIG` (Task 6). Cause kinds `downtime|defect|absence|lateOrders|hold|component` consistent across service (Tasks 1–3), i18n keys (Task 6), and tooltip lookup (Task 7).

## Global test / verification commands

- Backend: `cd backend && pytest tests/test_services/test_kpi_cause_service.py tests/test_kpi/test_cause_endpoint.py tests/test_bootstrap/test_openapi_surface.py -v`
- Frontend: `cd frontend && npm run lint && npx vitest run src/components/kpi src/services/api src/i18n`
- Full suites before PR: backend `pytest tests/` (coverage ≥75%), frontend `npm run test`.
