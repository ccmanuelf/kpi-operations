# Seed-Credibility Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the demo seeder produce credible non-zero WIP-Aging and OTD data — including at least one guaranteed out-of-control OTD point whose SP2 cause tooltip is demoable.

**Architecture:** Three surgical edits to `backend/scripts/_seed_operations.py`: (1) `seed_holds` backdates `hold_date` and sets `resume_date`; (2) `seed_work_orders` sets `required_date` on the 10 status WOs; (3) `seed_work_orders` adds a ~15-WO delivered-history batch shaped to dip below the OTD critical threshold, and `seed_daily_data` excludes that batch so production data is unchanged. INSERT-only, deterministic (`rng_for`), prod-safe.

**Tech Stack:** Python, SQLAlchemy ORM, pytest. SQLite (tests) + MariaDB (prod) portable.

## Global Constraints

- **INSERT-only, prod-safe:** no schema/DDL, no `drop_all`/`create_all`, allowlist unchanged. The static-safety scan (`test_prod_safety_static_scan`) must stay green.
- **Deterministic:** every generated date/quantity comes from the sha256-seeded `rng_for(*key_parts)` helper (`backend/scripts/_seed_common.py:25`) — never `date.today()`/`random`. Re-seeding produces identical rows (`test_full_seed_is_idempotent` must stay green).
- **OTD read semantics** (`backend/routes/kpi/trends.py:388`): OTD per `func.date(required_date)` day = `sum(actual_delivery_date <= required_date) / count(WO) × 100`; undelivered WO counts as a miss. **Critical threshold 80%, higher-is-better** (`_seed_reference.py:42`) → a day < 80% flags OOC.
- **WIP-Aging read semantics** (`backend/routes/holds.py:472`): per day, `avg(date_diff_days(day, hold_date))` over holds with `hold_date <= day AND (resume_date IS NULL OR resume_date > day)`. Active = `resume_date` NULL.
- **Determinism must not disturb existing data:** do NOT add `rng` draws inside the base `seed_work_orders` status loop (that would shift every downstream value); `required_date` is a no-draw assignment. The history batch uses its OWN `rng_for(cid, "otd_history")` stream.
- **MariaDB FK order:** new WOs are created in `seed_work_orders` (runs before `seed_holds`); holds reference only pre-existing WOs. `required_date`/`actual_delivery_date` are plain columns.
- Backend coverage gate ≥75% stays green.
- Anchor in code is a `datetime`: `now = datetime.combine(anchor, datetime.min.time(), tzinfo=timezone.utc)`.

---

### Task 1: Backdate holds for realistic WIP aging

**Files:**
- Modify: `backend/scripts/_seed_operations.py` (`seed_holds`, lines 178-224)
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- `seed_holds(session, client_id, work_orders, entered_by, anchor)` — signature unchanged. After this task, active (open-status) holds have `hold_date < anchor` (10–70 days), the `ON_HOLD` hold is chronic (60–70 days) with `resume_date` NULL, and resolved-status holds have `resume_date` set strictly between their `hold_date` and `anchor`.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_scripts/test_seed_sample_client.py
def test_holds_are_backdated_with_chronic_active_and_resolved_resume(db_session):
    from backend.orm import HoldEntry

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=10, anchor=FIXED_ANCHOR)

    holds = db_session.query(HoldEntry).filter_by(client_id="DEMO-PIECE").all()
    assert len(holds) == 7
    open_statuses = {"PENDING_HOLD_APPROVAL", "ON_HOLD", "PENDING_RESUME_APPROVAL"}
    resolved_statuses = {"RESUMED", "RELEASED", "CANCELLED", "SCRAPPED"}

    for h in holds:
        age = (FIXED_ANCHOR - h.hold_date.date()).days
        assert 10 <= age <= 70, f"{h.hold_status} age {age} out of band"
        if h.hold_status in open_statuses:
            assert h.resume_date is None
        if h.hold_status in resolved_statuses:
            assert h.resume_date is not None
            assert h.hold_date < h.resume_date
            assert h.resume_date.date() <= FIXED_ANCHOR

    on_hold = next(h for h in holds if h.hold_status == "ON_HOLD")
    chronic_age = (FIXED_ANCHOR - on_hold.hold_date.date()).days
    assert chronic_age >= 60, f"ON_HOLD hold should be chronic, got {chronic_age}d"
    assert on_hold.resume_date is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py::test_holds_are_backdated_with_chronic_active_and_resolved_resume -v`
Expected: FAIL — current code sets `hold_date = anchor` (age 0), so `10 <= age` fails.

- [ ] **Step 3: Write minimal implementation**

Replace the body of the `for i, hold_status in enumerate(chain, start=1):` loop in `seed_holds` (`backend/scripts/_seed_operations.py`, currently lines 205-223) with:

```python
    anchor_dt = datetime.combine(anchor, datetime.min.time(), tzinfo=timezone.utc)
    resolved_statuses = {"RESUMED", "RELEASED", "CANCELLED", "SCRAPPED"}
    for i, hold_status in enumerate(chain, start=1):
        wo = on_hold_wo if hold_status in open_statuses else work_orders[i % len(work_orders)]
        # Backdate deterministically so WIP-Aging shows real aging. The ON_HOLD
        # hold is the chronic one (60-70d) so the active-hold aging is pronounced.
        hrng = rng_for(client_id, "hold_age", i)
        age_days = hrng.randint(60, 70) if hold_status == "ON_HOLD" else hrng.randint(10, 70)
        hold_date = anchor_dt - timedelta(days=age_days)
        # Resolved holds carry a resume_date strictly between hold_date and anchor
        # (correct inactive semantics + the discontinuity that makes an SPC
        # WIP-Aging OOC flag likely). Open-status holds stay active (resume_date NULL).
        resume_date = None
        if hold_status in resolved_statuses:
            resume_offset = rng_for(client_id, "hold_resume", i).randint(1, max(2, age_days - 1))
            resume_date = hold_date + timedelta(days=resume_offset)
        session.add(
            HoldEntry(
                hold_entry_id=f"HOLD-{client_id}-{i:03d}",
                work_order_id=wo.work_order_id,
                client_id=client_id,
                hold_initiated_by=entered_by,
                hold_reason="QUALITY_ISSUE",
                hold_reason_category="QUALITY",
                hold_status=hold_status,
                hold_date=hold_date,
                resume_date=resume_date,
            )
        )
    session.flush()
```

Ensure `timedelta` is imported in `seed_holds` (the function already does `from datetime import datetime, timezone` at line 182 — add `timedelta`): change that import line to `from datetime import datetime, timedelta, timezone`. `rng_for` is already imported at module top (`_seed_operations.py:12`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py::test_holds_are_backdated_with_chronic_active_and_resolved_resume -v`
Expected: PASS

Then confirm no regression in the existing WO/hold + idempotency tests:
Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py -k "holds or work_orders or idempotent or reset_table_order" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/_seed_operations.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): backdate holds for realistic WIP-aging"
```

---

### Task 2: Set required_date on the 10 status work orders

**Files:**
- Modify: `backend/scripts/_seed_operations.py` (`seed_work_orders`, inside the status loop)
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- `seed_work_orders(session, spec, entered_by, anchor) -> list` — signature unchanged. After this task, every WO created in the status loop has a non-null `required_date` (equal to its `planned_ship_date`).

- [ ] **Step 1: Write the failing test**

```python
def test_all_work_orders_have_required_date(db_session):
    from backend.orm import WorkOrder

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=10, anchor=FIXED_ANCHOR)

    wos = db_session.query(WorkOrder).filter_by(client_id="DEMO-PIECE").all()
    assert len(wos) >= 10
    for wo in wos:
        assert wo.required_date is not None, f"{wo.work_order_id} missing required_date"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py::test_all_work_orders_have_required_date -v`
Expected: FAIL — `required_date` is never set → AssertionError.

- [ ] **Step 3: Write minimal implementation**

In `seed_work_orders`, immediately after the line `wo.actual_delivery_date = delivered` (currently line 97), add one no-draw assignment:

```python
        # OTD reads required_date (not planned_ship_date). Anchor it to the plan
        # so the 10 status WOs participate in the On-Time-Delivery metric.
        wo.required_date = planned_ship
```

(Do NOT add any `rng` draw here — the base status loop's random sequence must stay unchanged so existing daily-data determinism holds.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py::test_all_work_orders_have_required_date -v`
Expected: PASS

Regression check (existing daily-data determinism must be untouched):
Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py -k "daily or idempotent or work_orders" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/_seed_operations.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): set required_date on status work orders for OTD"
```

---

### Task 3: Delivered-history batch (credible + OOC-demoable OTD) + exclude it from daily data

**Files:**
- Modify: `backend/scripts/_seed_operations.py` (`seed_work_orders` — append batch before `session.flush()`; `seed_daily_data` — exclude the batch)
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- Consumes: `seed_work_orders` already sets `required_date` on the base loop (Task 2).
- Produces: `seed_work_orders` also creates ~15 `SHIPPED` history WOs (`work_order_id = f"WO-{cid}-H{n:03d}"`) with `required_date` spread over the last ~90 days and `actual_delivery_date` set on-time/late (~67% on-time), shaped so ≥1 required-date day has OTD < 80%. `seed_daily_data` generates production data only for the base status WOs (skips the `-H` batch), so production/OEE/quality data is unchanged.

- [ ] **Step 1: Write the failing test**

```python
def test_delivered_history_batch_drives_credible_and_ooc_otd(db_session):
    from collections import defaultdict
    from backend.orm import WorkOrder, ProductionEntry

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=10, anchor=FIXED_ANCHOR)

    hist = (
        db_session.query(WorkOrder)
        .filter(WorkOrder.client_id == "DEMO-PIECE", WorkOrder.work_order_id.like("WO-DEMO-PIECE-H%"))
        .all()
    )
    assert len(hist) == 15, f"expected 15 history WOs, got {len(hist)}"
    for wo in hist:
        assert wo.status.value == "SHIPPED"
        assert wo.required_date is not None and wo.actual_delivery_date is not None

    # Overall on-time rate is credible (~70%), not 0% and not 100%.
    on_time = sum(1 for wo in hist if wo.actual_delivery_date <= wo.required_date)
    rate = on_time / len(hist)
    assert 0.5 <= rate <= 0.85, f"on-time rate {rate} not credible"

    # Replicate the OTD trend's per-required_date-day aggregation over ALL client
    # WOs; at least one day must dip below the 80% critical threshold (guaranteed OOC).
    per_day = defaultdict(lambda: [0, 0])  # date -> [total, on_time]
    for wo in db_session.query(WorkOrder).filter_by(client_id="DEMO-PIECE").all():
        if wo.required_date is None:
            continue
        d = wo.required_date.date()
        per_day[d][0] += 1
        if wo.actual_delivery_date is not None and wo.actual_delivery_date <= wo.required_date:
            per_day[d][1] += 1
    otd_by_day = {d: (ot / tot * 100) for d, (tot, ot) in per_day.items() if tot > 0}
    assert any(v < 80 for v in otd_by_day.values()), f"no OOC OTD day <80%: {otd_by_day}"

    # The history batch must NOT generate production data (keeps OEE/throughput unchanged).
    hist_prod = (
        db_session.query(ProductionEntry)
        .filter(ProductionEntry.client_id == "DEMO-PIECE", ProductionEntry.work_order_id.like("WO-DEMO-PIECE-H%"))
        .count()
    )
    assert hist_prod == 0, f"history WOs should have no production entries, got {hist_prod}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py::test_delivered_history_batch_drives_credible_and_ooc_otd -v`
Expected: FAIL — no `-H` history WOs exist yet (`len(hist) == 0`).

- [ ] **Step 3: Write minimal implementation**

**(3a)** In `seed_work_orders`, immediately BEFORE the final `session.flush()` / `return wos` (currently lines 173-174, after the `for i, status in enumerate(states...)` loop closes), append the delivered-history batch:

```python
    # --- Delivered-history batch: credible + OOC-demoable OTD -----------------
    # OTD groups delivered WOs by required_date over the trend window; the 10
    # status WOs alone give too thin a denominator. Add lightweight SHIPPED WOs
    # spread across the last ~90 days, ~67% on-time, with a handful of days that
    # dip below the 80% critical threshold so the diagnostic OOC tooltip demos.
    HISTORY_N = 15
    hrng = rng_for(cid, "otd_history")
    for n in range(1, HISTORY_N + 1):
        days_ago = 2 + (n - 1) * 6  # distinct days: 2, 8, 14, ... 86 (within last 90d)
        req = now - timedelta(days=days_ago)
        late = n % 3 == 0  # every 3rd order late -> 5 late / 10 on-time = 67% on-time
        delivered = (
            req + timedelta(days=hrng.randint(2, 6)) if late else req - timedelta(days=hrng.randint(0, 2))
        )
        hwo = TestDataFactory.create_work_order(
            session,
            client_id=cid,
            work_order_id=f"WO-{cid}-H{n:03d}",
            status=WorkOrderStatus.SHIPPED,
            planned_quantity=hrng.randint(500, 2000),
            planned_ship_date=req,
            priority="MEDIUM",
        )
        hwo.required_date = req
        hwo.actual_delivery_date = delivered
        hwo.received_date = req - timedelta(days=hrng.randint(20, 40))
        hwo.dispatch_date = req - timedelta(days=hrng.randint(1, 5))
        hwo.shipped_date = delivered
        wos.append(hwo)
```

Because each history WO sits on its own distinct required-date day, a `late` WO makes that day 0% (0/1) — well below the 80% critical threshold — so `n = 3, 6, 9, 12, 15` yield five guaranteed OOC days; the other ten days are 100%.

**(3b)** In `seed_daily_data`, exclude the history batch so it generates no production data. Change the WO query line (currently `work_orders = session.query(WorkOrder).filter_by(client_id=cid).order_by(WorkOrder.work_order_id).all()`) to filter out the `-H` batch:

```python
    work_orders = [
        wo
        for wo in session.query(WorkOrder).filter_by(client_id=cid).order_by(WorkOrder.work_order_id).all()
        if not wo.work_order_id.split("-")[-1].startswith("H")
    ]
```

(The base status WOs are `WO-{cid}-{i:03d}` — last segment is digits; history WOs are `WO-{cid}-H{n:03d}` — last segment starts with `H`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py::test_delivered_history_batch_drives_credible_and_ooc_otd -v`
Expected: PASS

Full seeder-test regression (determinism, idempotency, FK-order, daily-data credibility all unchanged):
Run: `cd backend && pytest tests/test_scripts/test_seed_sample_client.py -v`
Expected: PASS (all existing + 3 new)

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/_seed_operations.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): delivered-history batch for credible OOC-demoable OTD"
```

---

## Self-Review

**1. Spec coverage:**
- Holds backdated 10–70d + chronic active + resume_date on resolved → Task 1. ✅
- `required_date` on all WOs → Task 2 (status WOs) + Task 3 (history WOs). ✅
- Delivered-history batch (~15, ~70% on-time, spread ~90d) → Task 3. ✅
- Guaranteed OTD < 80% day → Task 3 shaping (distinct-day late WOs) + test assertion. ✅
- History batch excluded from daily data (production unchanged) → Task 3 (3b) + test. ✅
- Determinism (rng_for), prod-safe, MariaDB FK order → Global Constraints, honored in each task. ✅
- WIP OOC best-effort via resume-event discontinuity → Task 1 (resume_date on resolved). ✅ (not asserted — spec marks it best-effort).
- Deploy `--reset` re-seed → operational, outside code; noted in spec, handled at deploy.

**2. Placeholder scan:** No TBD/TODO; every code step is complete and concrete; every test asserts specific values.

**3. Type consistency:** `seed_holds`/`seed_work_orders`/`seed_daily_data` signatures unchanged across tasks. History PK format `WO-{cid}-H{n:03d}` identical in the generator (Task 3a), the daily-data filter (Task 3b), and every test `.like("WO-DEMO-PIECE-H%")`. `rng_for` keys are distinct streams (`hold_age`, `hold_resume`, `otd_history`) — no collision with the base loop's `rng_for(cid, "work_orders")`. `FIXED_ANCHOR = date(2026, 6, 15)` used consistently in all new tests.

## Verification command (whole slice)

`cd backend && pytest tests/test_scripts/test_seed_sample_client.py -v` — all existing guards (prod-safety static scan, reset-table-order, determinism, idempotency, daily-data credibility) plus the 3 new tests must pass.
