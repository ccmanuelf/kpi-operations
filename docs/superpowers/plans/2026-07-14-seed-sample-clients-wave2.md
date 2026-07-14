# Seed Sample Clients — Wave 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the demo dataset **visible today and internally coherent** across every Planning/Operations/Simulation screen (fix the fixed-past-anchor visibility bug, add plan↔actual and capacity↔WO coherence, populate empty screens, cover workflow config + global tables), in a split, maintainable module layout.

**Architecture:** Extends the Wave-1 seeder (`backend/scripts/seed_sample_client.py`). Task 1 splits the section helpers into `backend/scripts/_seed_sections.py` (pure move). Task 2 threads a real-date `anchor` through the date-using helpers. Tasks 3–6 add coherence, empty-screen population, variety/workflow-config, and global tables. Task 7 integrates (reset list, docs, whole-suite).

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 ORM, argparse, pytest (template-clone `db_session` fixture). Portable SQLite + MariaDB (ORM inserts only).

**Spec:** `docs/superpowers/specs/2026-07-14-seed-sample-clients-wave2-design.md`. Wave-1 plan: `docs/superpowers/plans/2026-07-14-seed-sample-clients.md`. **Authoritative field-usage reference for all new entities:** `backend/scripts/init_demo_database.py` (search it for the ORM class name) + the ORM file itself.

## Global Constraints

- **Anchor = real date for seeding, fixed for tests.** Section helpers take an `anchor: date` param; `main()` defaults `--anchor` to `date.today()`; tests pass a fixed `date(2026, 6, 15)`. Determinism holds *given an anchor* (proven by a two-run test), replacing the old no-wall-clock source-scan guard.
- **Deterministic values** from `rng_for(...)` (sha256), never `random`-module-global/`hash()`. New per-day/per-entity values use `rng_for(client_id, section, key)`.
- **PK-safe:** every app-generated PK/unique-code embeds the full `client_id` (no `_next_id` counters, no short prefix) — seeding all clients in one/many processes must not collide. New per-client tables added this wave (Equipment, BreakTime, FloatingPool, Alert instances) MUST be added to `RESET_TABLE_ORDER` children-first.
- **Idempotent** (skip-if-exists) + **scoped `--reset`** unchanged. Global tables (Task 6) are seeded once from `main()`, idempotently, OUTSIDE the per-client loop.
- **Prod-safe:** still no user/credential writes; allowlist + `ensure_migrated` unchanged. Global-table seeding must not `create_all`/`drop`/gate on `DEMO_MODE` (static-scan test still applies).
- Backend: `pytest tests/` from `backend/` (coverage ≥75). `python -m mypy backend` clean. Repo formatter is **black (line-length 120)** — never `ruff format`. Files under 500 lines (the split serves this). Conventional commits. One expected status per assertion.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/scripts/_seed_sections.py` | Create (Task 1) | All section builders (`seed_catalogs`…`seed_simulation` + new Wave-2 helpers) + the `_*` constant tables. Pure functions taking `(session, ...)`. |
| `backend/scripts/seed_sample_client.py` | Modify | Keep CLI (`main`), guards (`ALLOWLIST`, `SeedError`, `ensure_migrated`, `rng_for`), `ClientSpec`/`CLIENT_SPECS`, `resolve_entered_by`, `RESET_TABLE_ORDER`/`reset_client_data`, and the `seed_client` orchestrator (imports from `_seed_sections`). |
| `backend/tests/test_scripts/test_seed_sample_client.py` | Modify | Update call sites to pass `anchor`; replace the wall-clock guard; add Wave-2 tests. |

---

### Task 1: Split section helpers into `_seed_sections.py` (pure move)

**Files:**
- Create: `backend/scripts/_seed_sections.py`
- Modify: `backend/scripts/seed_sample_client.py`

**Interfaces:** No signature changes. Every `seed_*` section function + `_transition_chain` + the `_HOLD_STATUSES`/`_HOLD_REASONS`/`_DEFECT_TYPES`/`_KPI_THRESHOLDS`/`_ALERT_CONFIGS` constants move verbatim to `_seed_sections.py`. `seed_sample_client.py` imports them.

- [ ] **Step 1: Create the module and move helpers**

Read `backend/scripts/seed_sample_client.py`. Cut these top-level definitions and paste them **verbatim** into a new `backend/scripts/_seed_sections.py`: the constant tables (`_HOLD_STATUSES`, `_HOLD_REASONS`, `_DEFECT_TYPES`, `_KPI_THRESHOLDS`, `_ALERT_CONFIGS`) and the functions `seed_catalogs`, `seed_config_layer`, `seed_shifts`, `seed_products`, `seed_lines`, `seed_employees`, `seed_capacity_graph`, `seed_work_orders`, `_transition_chain`, `seed_holds`, `seed_daily_data`, `seed_simulation`. They already use function-local imports, so they move cleanly. Add the module docstring and the shared top-level imports they need at module scope: `from datetime import date` is NOT needed yet (added Task 2); they use function-local imports for ORM. Add `from backend.scripts.seed_sample_client import rng_for, ClientSpec` ONLY if a helper references them — `rng_for` is used by several and `ClientSpec` by `seed_employees`/`seed_work_orders`/`seed_daily_data`. **To avoid a circular import** (`seed_sample_client` will import the helpers back), move `rng_for` and `ClientSpec`/`ClientSpec`-free primitives that helpers need into `_seed_sections.py`? No — instead keep `rng_for` in `seed_sample_client.py` and have `_seed_sections.py` import it lazily inside functions, OR (cleaner) move `rng_for` into `_seed_sections.py` and re-export it from `seed_sample_client.py`. **Chosen approach:** move `rng_for` and the `ClientSpec` dataclass into `_seed_sections.py`; in `seed_sample_client.py` do `from backend.scripts._seed_sections import rng_for, ClientSpec` and re-export (so existing `seed.rng_for` / `seed.CLIENT_SPECS` test references still resolve). `CLIENT_SPECS` (the dict) stays in `seed_sample_client.py` (it's config, used by `main`), but since it needs `ClientSpec`, import `ClientSpec` from `_seed_sections`.

- [ ] **Step 2: Wire imports in `seed_sample_client.py`**

At the top of `seed_sample_client.py` (after the existing imports), add:

```python
from backend.scripts._seed_sections import (  # noqa: E402
    rng_for,
    ClientSpec,
    seed_catalogs,
    seed_config_layer,
    seed_shifts,
    seed_products,
    seed_lines,
    seed_employees,
    seed_capacity_graph,
    seed_work_orders,
    seed_holds,
    seed_daily_data,
    seed_simulation,
)
```

Remove the moved definitions from `seed_sample_client.py`. `seed_client` (which stays) now calls the imported helpers unchanged. `_reset_table_order`/`RESET_TABLE_ORDER`/`reset_client_data`, `ensure_migrated`, `resolve_entered_by`, `seed_client_row`, `CLIENT_SPECS`, `main` stay.

- [ ] **Step 3: Run the full seed test file to verify no behavior change**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q`
Expected: all existing tests PASS unchanged (the split is behavior-preserving). Fix any import errors (circular-import → ensure `_seed_sections.py` does NOT import `seed_sample_client` at module scope; helpers that need `resolve_entered_by`/`RESET_TABLE_ORDER` don't — only `seed_client` in the main file orchestrates those).

- [ ] **Step 4: Confirm file sizes + lint/type**

Run: `cd backend && wc -l scripts/seed_sample_client.py scripts/_seed_sections.py && python -m mypy backend && flake8 scripts/seed_sample_client.py scripts/_seed_sections.py`
Expected: both files well under 500 lines; mypy + flake8 clean.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_sample_client.py backend/scripts/_seed_sections.py
git commit -m "refactor(seed): split section helpers into _seed_sections.py (no behavior change)"
```

---

### Task 2: Temporal anchor parameter + determinism guard rework

**Files:**
- Modify: `backend/scripts/_seed_sections.py`, `backend/scripts/seed_sample_client.py`, `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces (Produces):** `seed_client(session, spec, days, anchor)`, `seed_capacity_graph(session, client_id, days, anchor)`, `seed_work_orders(session, spec, entered_by, anchor)`, `seed_holds(session, client_id, work_orders, entered_by, anchor)`, `seed_daily_data(session, spec, days, entered_by, anchor)` — all gain a trailing `anchor: date`. `main()` gains `--anchor` (default `date.today()`).

- [ ] **Step 1: Add `anchor` to the date-using helpers**

In `_seed_sections.py`, add `anchor: date` as the last parameter to `seed_capacity_graph`, `seed_work_orders`, `seed_holds`, `seed_daily_data`. Replace every use of the module constant with `anchor`:
- `seed_capacity_graph`: `today = anchor` (was `today = ANCHOR_DATE`).
- `seed_work_orders`: `now = datetime.combine(anchor, datetime.min.time(), tzinfo=timezone.utc)`.
- `seed_holds`: `hold_date=datetime.combine(anchor, datetime.min.time(), tzinfo=timezone.utc)`.
- `seed_daily_data`: `end = anchor`.

Delete the module-level `ANCHOR_DATE = date(2026, 6, 15)` constant (its only remaining role — the test default — moves to the test file). Add `from datetime import date` at module scope if any signature annotation needs it (annotations can also be quoted `"date"`; prefer the import).

- [ ] **Step 2: Thread `anchor` through `seed_client` + `main`**

In `seed_sample_client.py`:
- `def seed_client(session: Session, spec: ClientSpec, days: int, anchor: date) -> None:` and pass `anchor` to `seed_capacity_graph`, `seed_work_orders`, `seed_holds`, `seed_daily_data`.
- Add `from datetime import date` at module scope.
- In `main()`, add:
```python
parser.add_argument(
    "--anchor", default=None,
    help="YYYY-MM-DD anchor for seeded dates (Operations history ends here, capacity planning starts here); default = today",
)
```
Parse it after args: `anchor = date.fromisoformat(args.anchor) if args.anchor else date.today()` — wrap the `fromisoformat` in a `try/except ValueError` that prints an error and returns 1. Pass `anchor` into `seed_client(session, spec, args.days, anchor)`.

- [ ] **Step 3: Update existing test call sites + replace the wall-clock guard**

In `test_seed_sample_client.py`:
- Add a module constant `FIXED_ANCHOR = date(2026, 6, 15)` (import `from datetime import date`).
- Every existing call to `seed.seed_client(db_session, spec, days=N)` becomes `seed.seed_client(db_session, spec, days=N, anchor=FIXED_ANCHOR)`. (Grep the file for `seed_client(` and update all.)
- DELETE `test_seeder_uses_no_wall_clock` (the source-scan guard) — `main` now intentionally calls `date.today()`.
- Add the determinism test:
```python
def test_seed_values_deterministic_for_fixed_anchor(db_session):
    from backend.orm import ProductionEntry

    _seed_admin(db_session)
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=10, anchor=FIXED_ANCHOR)
    db_session.commit()
    first = {
        r.production_entry_id: (r.units_produced, str(r.run_time_hours), r.defect_count, r.scrap_count)
        for r in db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").all()
    }
    # Reset just this client and re-seed with the SAME anchor → identical values.
    seed.reset_client_data(db_session, "DEMO-PIECE")
    db_session.commit()
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=10, anchor=FIXED_ANCHOR)
    db_session.commit()
    second = {
        r.production_entry_id: (r.units_produced, str(r.run_time_hours), r.defect_count, r.scrap_count)
        for r in db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").all()
    }
    assert first == second and len(first) > 0
```

- [ ] **Step 4: Run the suite + mypy**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q && python -m mypy backend`
Expected: all pass (updated call sites + new determinism test); mypy clean.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/_seed_sections.py backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): --anchor (default today) for visible data; determinism test replaces wall-clock guard"
```

---

### Task 3: Coherence — plan↔actual true-up, WO↔CapacityOrder bridge, stored KPI fields, milestones/previous_status

**Files:**
- Modify: `backend/scripts/_seed_sections.py`, `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:** `seed_work_orders` now returns work orders carrying `capacity_order_id`/`planned_start_date`/milestones/`previous_status`; `seed_daily_data` distributes production per WO to a status-derived target.

**Reference:** mirror `backend/scripts/init_demo_database.py` — search for the production-distribution/true-up loop (the `target_total` / last-entry-pinned logic, ~lines 1310–1400) and the CPO↔WO bridge (`origin="CAPACITY_PLAN"`, `capacity_order_id`, `planned_start_date`, ~lines 1200–1260). Read `backend/orm/work_order.py` for the exact milestone/`previous_status`/`actual_quantity` columns and `backend/orm/production_entry.py` for the stored KPI columns.

- [ ] **Step 1: Write the failing coherence tests**

```python
def test_production_sums_to_workorder_target(db_session):
    from decimal import Decimal
    from backend.orm import ProductionEntry, WorkOrder, WorkOrderStatus

    _seed_admin(db_session)
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=40, anchor=FIXED_ANCHOR)
    db_session.commit()
    cid = "DEMO-PIECE"
    # For each SHIPPED/CLOSED/COMPLETED WO, produced units must equal actual_quantity
    # and land at ~100% of planned_quantity; RECEIVED/RELEASED WOs have zero production.
    for wo in db_session.query(WorkOrder).filter_by(client_id=cid).all():
        produced = sum(
            pe.units_produced
            for pe in db_session.query(ProductionEntry).filter_by(client_id=cid, work_order_id=wo.work_order_id).all()
        )
        if wo.status in (WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED, WorkOrderStatus.COMPLETED):
            assert produced == wo.actual_quantity and produced > 0
        elif wo.status in (WorkOrderStatus.RECEIVED, WorkOrderStatus.RELEASED):
            assert produced == 0


def test_planned_workorders_bridge_capacity_orders(db_session):
    from backend.orm import WorkOrder

    _seed_admin(db_session)
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=20, anchor=FIXED_ANCHOR)
    db_session.commit()
    planned = [
        wo for wo in db_session.query(WorkOrder).filter_by(client_id="DEMO-PIECE").all()
        if wo.origin == "CAPACITY_PLAN"
    ]
    assert planned, "expected some CAPACITY_PLAN work orders"
    for wo in planned:
        assert wo.capacity_order_id is not None
        assert wo.planned_start_date is not None


def test_production_entry_stored_kpis_populated(db_session):
    from backend.orm import ProductionEntry

    _seed_admin(db_session)
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=15, anchor=FIXED_ANCHOR)
    db_session.commit()
    for pe in db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").all():
        assert pe.maintenance_hours is not None
        assert pe.employees_present is not None
        assert pe.efficiency_percentage is not None and 0 < float(pe.efficiency_percentage) <= 100
        assert pe.performance_percentage is not None and 0 < float(pe.performance_percentage) <= 100
        assert pe.quality_rate is not None and 0 < float(pe.quality_rate) <= 100
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -k "coherence or target or bridge or stored_kpi" -q`
(Or run the three test names.) Expected: FAIL — current data has AD_HOC WOs, unrelated production sums, NULL stored KPIs.

- [ ] **Step 3: Bridge WOs to capacity orders + set milestones/previous_status in `seed_work_orders`**

Modify `seed_work_orders` (read `backend/orm/work_order.py` first for exact columns):
- Fetch the seeded `CapacityOrder`s for the client (`session.query(CapacityOrder).filter_by(client_id=cid).all()`). For the planned/mainline statuses (RELEASED..CLOSED), set `origin="CAPACITY_PLAN"`, `capacity_order_id=<a capacity order id>` (rotate), and `planned_start_date` (e.g. `anchor - timedelta(days=rng.randint(20,60))`). Leave CANCELLED/ON_HOLD as needed.
- Set per-status milestone dates coherent with status: `received_date` for all; `planned_ship_date` (already set); `dispatch_date`/`shipped_date` for SHIPPED/CLOSED; `closure_date` for CLOSED. Use `anchor`-relative deterministic offsets.
- Set `previous_status` on the ON_HOLD WO (e.g. `WorkOrderStatus.IN_PROGRESS`).
- Keep `work_order_id=f"WO-{cid}-{i:03d}"` and everything else.

- [ ] **Step 4: Distribute production per WO to a status target in `seed_daily_data`**

Rework `seed_daily_data`'s production loop (mirror `init_demo_database`'s true-up):
- Compute per-WO target as a fraction of `planned_quantity`: SHIPPED/CLOSED/COMPLETED → 1.0; IN_PROGRESS → ~0.5; ON_HOLD → ~0.3; RELEASED/RECEIVED/CANCELLED → 0.0.
- For each WO with target > 0, spread its target units across a deterministic subset of the working days (assign each day to a WO), so cumulative units for that WO equal the target (pin the last day's entry so the sum matches exactly). Set `wo.actual_quantity` to the produced total for that WO.
- Keep the credibility formula (`run_time = ideal_ct*units/target_perf`, defects/scrap ratios) per entry; keep deterministic `rng_for`.
- Set the stored KPI columns on each `ProductionEntry` (read `backend/orm/production_entry.py`): `employees_present` (= assigned, minus occasional absence), `maintenance_hours` (small, e.g. `run_time*0.01`), `ideal_cycle_time`, `actual_cycle_time` (= `run_time*60/units` min or hours per the column unit), `efficiency_percentage`/`performance_percentage` (≈ `target_perf*100`), `quality_rate` (= `(units-defects-scrap)/units*100`). Clamp all ≤ 100.

Keep quality/defect/downtime/attendance generation but tie them to the same per-day WO. Ensure PKs stay `f"PE-{cid}-{seq:04d}"` etc. with a monotonic `seq`.

- [ ] **Step 5: Run the coherence tests + the existing suite**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q && python -m mypy backend`
Expected: the 3 new tests pass; existing count/credibility/idempotency/determinism tests still pass (adjust any that assumed 1-entry-per-day if needed — the per-WO distribution changes daily counts; update those assertions to `>= days` → the new realistic count, keeping them non-tautological).

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/_seed_sections.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): plan-vs-actual true-up + WO<->CapacityOrder bridge + stored ProductionEntry KPIs + milestones"
```

---

### Task 4: Populate empty screens — Alert instances, Equipment, BreakTime, floating pool

**Files:**
- Modify: `backend/scripts/_seed_sections.py`, `backend/scripts/seed_sample_client.py` (RESET_TABLE_ORDER), `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:** new idempotent helpers `seed_alerts(session, client_id)`, `seed_equipment(session, client_id)`, `seed_break_times(session, client_id)`; `seed_employees` marks ≥1 employee floating-pool. All wired into `seed_client`. New per-client tables added to `RESET_TABLE_ORDER`.

**Reference:** read `backend/orm/alert.py` (Alert), `backend/orm/equipment.py`, `backend/orm/break_time.py`, `backend/orm/floating_pool.py` + `backend/orm/employee_client_assignment.py` (`AssignmentType.FLOATING_POOL`); mirror `init_demo_database.py` (search `Alert(`, `Equipment(`, `BreakTime(`, `is_floating_pool`, `FloatingPool(`).

- [ ] **Step 1: Write the failing tests**

```python
def test_empty_screens_populated(db_session):
    from backend.orm.alert import Alert
    from backend.orm.equipment import Equipment
    from backend.orm.break_time import BreakTime
    from backend.orm.employee import Employee

    _seed_admin(db_session)
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=8, anchor=FIXED_ANCHOR)
    db_session.commit()
    cid = "DEMO-PIECE"
    assert db_session.query(Alert).filter_by(client_id=cid).count() >= 1
    assert db_session.query(Equipment).filter_by(client_id=cid).count() >= 1
    assert db_session.query(BreakTime).filter_by(client_id=cid).count() >= 1
    fp = db_session.query(Employee).filter_by(client_id_assigned=cid, is_floating_pool=1).count()
    assert fp >= 1  # at least one floating-pool employee


def test_floating_and_dedicated_assignments_both_present(db_session):
    from backend.orm.employee_client_assignment import EmployeeClientAssignment

    _seed_admin(db_session)
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=8, anchor=FIXED_ANCHOR)
    db_session.commit()
    types = {
        a.assignment_type
        for a in db_session.query(EmployeeClientAssignment).filter_by(client_id="DEMO-PIECE").all()
    }
    assert "DEDICATED" in types and "FLOATING" in types
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -k "empty_screens or floating" -q`
Expected: FAIL — helpers/entities not seeded yet; the Equipment/Alert/BreakTime imports resolve (tables exist) but counts are 0.

- [ ] **Step 3: Implement the four additions**

- `seed_break_times(session, client_id)`: read `backend/orm/break_time.py`; for each `Shift` of the client, add ~2 breaks (Morning 15 min @ 120, Lunch 30 min @ 240) mirroring `init_demo_database`. Idempotent (skip if any BreakTime for the client's shifts exists).
- `seed_equipment(session, client_id)`: read `backend/orm/equipment.py`; for each operational `ProductionLine`, add ~2 typed `Equipment` rows (deterministic codes embedding `client_id`, e.g. `f"{client_id}-EQ-{n}"`, `status=ACTIVE`). Idempotent.
- `seed_alerts(session, client_id)`: read `backend/orm/alert.py`; add ~3 active `Alert` rows (mixed category/severity, `status="active"`, `alert_id=f"ALERT-{client_id}-{n}"`). Idempotent.
- Floating pool in `seed_employees`: mark the last `k` (e.g. 2) of the `num_employees` employees `is_floating_pool=1` and give them a `FLOATING` `EmployeeClientAssignment` (via `assign_employee_to_client(..., assignment_type="FLOATING")` — confirm the param name/enum by reading `employee_client_assignment.py`) instead of / in addition to DEDICATED. Ensure the `test_master_data_seeded_and_idempotent` count assertions still hold (or update them for the floating split).

Wire into `seed_client` (in `seed_sample_client.py`, after `seed_employees`, before `seed_capacity_graph`): `seed_break_times`, `seed_equipment`, `seed_alerts`. Add them to the import block from `_seed_sections`.

- [ ] **Step 4: Add the new per-client tables to `RESET_TABLE_ORDER`**

In `seed_sample_client.py` `_reset_table_order()`, add (children-first — these are leaf-ish, place before their parents): `Alert` (client_id), `Equipment` (client_id, child of ProductionLine → place before ProductionLine), `BreakTime` (client_id, child of Shift → before Shift), `FloatingPool` if a row is created (client_id). Read each ORM for the exact client column. Extend `test_reset_table_order_children_before_parents` with the new FK edges (ProductionLine→Equipment, Shift→BreakTime).

- [ ] **Step 5: Run the suite + mypy**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q && python -m mypy backend`
Expected: new tests pass; reset/idempotency tests still pass (new tables cleaned by `--reset`).

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/_seed_sections.py backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): populate Alert/Equipment/BreakTime + floating-pool employees; extend reset order"
```

---

### Task 5: Variety + workflow configuration — DEMOTED/REJECTED WOs, custom workflow config, downtime/absence variety

**Files:**
- Modify: `backend/scripts/_seed_sections.py`, `backend/tests/test_scripts/test_seed_sample_client.py`

**Reference:** `backend/orm/work_order.py` (`DEMOTED`, `REJECTED`, `rejection_reason`/`rejected_by`/`rejected_date`), `backend/orm/client_config.py` (`workflow_statuses`/`workflow_transitions` JSON), `backend/orm/attendance_entry.py` (`AbsenceType`).

- [ ] **Step 1: Write the failing tests**

```python
def test_demoted_and_rejected_workorders_present(db_session):
    from backend.orm import WorkOrder, WorkOrderStatus

    _seed_admin(db_session)
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=8, anchor=FIXED_ANCHOR)
    db_session.commit()
    statuses = {wo.status for wo in db_session.query(WorkOrder).filter_by(client_id="DEMO-PIECE").all()}
    assert WorkOrderStatus.DEMOTED in statuses
    assert WorkOrderStatus.REJECTED in statuses
    rejected = next(
        wo for wo in db_session.query(WorkOrder).filter_by(client_id="DEMO-PIECE").all()
        if wo.status == WorkOrderStatus.REJECTED
    )
    assert rejected.rejection_reason is not None


def test_workflow_config_present_for_demo_clients(db_session):
    from backend.orm.client_config import ClientConfig

    _seed_admin(db_session)
    for cid in ("DEMO-PIECE", "DEMO-HYBRID"):
        seed.seed_client(db_session, seed.CLIENT_SPECS[cid], days=5, anchor=FIXED_ANCHOR)
    db_session.commit()
    for cid in ("DEMO-PIECE", "DEMO-HYBRID"):
        cfg = db_session.query(ClientConfig).filter_by(client_id=cid).first()
        assert cfg is not None and cfg.workflow_statuses and cfg.workflow_transitions
    # One client exercises a customized (non-default) workflow_statuses.
    hybrid = db_session.query(ClientConfig).filter_by(client_id="DEMO-HYBRID").first()
    piece = db_session.query(ClientConfig).filter_by(client_id="DEMO-PIECE").first()
    assert hybrid.workflow_statuses != piece.workflow_statuses


def test_absence_type_variety(db_session):
    from backend.orm import AttendanceEntry

    _seed_admin(db_session)
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=60, anchor=FIXED_ANCHOR)
    db_session.commit()
    types = {
        a.absence_type
        for a in db_session.query(AttendanceEntry).filter_by(client_id="DEMO-PIECE").all()
        if a.is_absent == 1 and a.absence_type is not None
    }
    assert len(types) >= 2
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -k "demoted or workflow_config or absence_type" -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

- In `seed_work_orders`, extend the `states` list with `WorkOrderStatus.DEMOTED` and `WorkOrderStatus.REJECTED` (2 more WOs, ids continue `WO-{cid}-009/010`); for the REJECTED one set `rejection_reason`/`rejected_by=entered_by`/`rejected_date` (read the ORM). Extend `_transition_chain` for DEMOTED (`[RECEIVED, RELEASED, DEMOTED]`) and REJECTED (`[RECEIVED, RELEASED, IN_PROGRESS, REJECTED]` or per the ORM's documented transitions).
- In `seed_config_layer`, give a customized `workflow_statuses` to clients whose `client_id` is in a small set (e.g. `DEMO-HYBRID` gets a reordered/subset JSON) so the non-default path is exercised; others keep the `ClientConfig()` default. Pass the JSON explicitly for that client.
- In `seed_daily_data` attendance, when `absent`, choose `absence_type` from ≥2 `AbsenceType` values deterministically (`rng.choice([AbsenceType.UNSCHEDULED_ABSENCE, AbsenceType.VACATION, AbsenceType.MEDICAL_LEAVE])`), and broaden `downtime_reason` to ~5 reasons.

- [ ] **Step 4: Run the suite (status-coverage test now expects 10 statuses)**

Update the Wave-1 `test_work_orders_cover_all_statuses_...` required-status set to include DEMOTED + REJECTED. Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q && python -m mypy backend`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/_seed_sections.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): DEMOTED/REJECTED WOs + custom workflow config + absence/downtime variety"
```

---

### Task 6: Global tables — DashboardWidgetDefaults + metric dependencies (seeded once from main)

**Files:**
- Modify: `backend/scripts/_seed_sections.py`, `backend/scripts/seed_sample_client.py`, `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:** new idempotent `seed_global_defaults(session) -> None` (no client_id — GLOBAL); called once in `main()` before the per-client loop.

**Reference:** `backend/scripts/init_demo_database.py` — the dashboard-widget-defaults block and `seed_metric_dependencies(session)` call near the end; read `backend/orm/` for the widget-defaults ORM class and confirm `seed_metric_dependencies` is importable.

- [ ] **Step 1: Write the failing test**

```python
def test_global_defaults_seeded_once(db_session):
    # DashboardWidgetDefaults + metric dependencies are global (no client scope).
    from backend.scripts import _seed_sections

    # (import the widget-defaults ORM + the metric-dependency table the reference uses)
    from backend.orm.dashboard_widget_defaults import DashboardWidgetDefaults  # adjust to real module

    _seed_sections.seed_global_defaults(db_session)
    _seed_sections.seed_global_defaults(db_session)  # idempotent
    db_session.commit()
    assert db_session.query(DashboardWidgetDefaults).count() >= 1
```

(If the widget-defaults ORM lives in a differently-named module, fix the import to the real path found while implementing.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py::test_global_defaults_seeded_once -q`
Expected: FAIL — `seed_global_defaults` undefined.

- [ ] **Step 3: Implement `seed_global_defaults` + wire into `main`**

In `_seed_sections.py`, add `seed_global_defaults(session)`: idempotently seed `DashboardWidgetDefaults` (mirror the sibling's role-scoped rows) and call `seed_metric_dependencies(session)` (import from wherever `init_demo_database` gets it). Guard each with skip-if-exists. NO `create_all`/`drop`/`DEMO_MODE`.

In `seed_sample_client.py` `main()`, import `seed_global_defaults` and call it ONCE inside the `with Session(...)` block, before the `for client_id in targets` loop, then `session.commit()`.

- [ ] **Step 4: Run the suite + static-safety scan (must still pass)**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q && python -m mypy backend`
Expected: pass; `test_prod_safety_static_scan` still green (no forbidden tokens introduced).

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/_seed_sections.py backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): seed global DashboardWidgetDefaults + metric dependencies once from main"
```

---

### Task 7: Integration — full suite, CLI smoke with --anchor, docs

**Files:**
- Modify: `backend/tests/test_scripts/test_seed_sample_client.py`; `docs/deployment/vm-deploy-runbook.md` (or wherever the seed command is documented — grep for `seed_sample_client`)

- [ ] **Step 1: Extend the CLI-smoke test to exercise `--anchor`**

Update `test_cli_smoke_seeds_and_reports` (or add a sibling) to pass `--anchor 2026-06-15` and assert exit 0 + data present; and a case with an invalid `--anchor notadate` asserting exit 1.

- [ ] **Step 2: Run the FULL backend suite + coverage**

Run: `cd backend && python -m pytest tests/ -q`
Expected: full suite green, coverage ≥75%. Investigate any failure; a Wave-2 change to shared seed behavior must not break other tests.

- [ ] **Step 3: Lint/format/type across both files**

Run: `cd backend && black --check scripts/seed_sample_client.py scripts/_seed_sections.py tests/test_scripts/test_seed_sample_client.py && flake8 scripts/seed_sample_client.py scripts/_seed_sections.py && cd .. && python -m mypy backend`
Expected: clean.

- [ ] **Step 4: Update the VM seed docs**

If a runbook/doc references `python -m backend.scripts.seed_sample_client`, note that it now seeds with **today's date by default** (recent, visible data) and mention `--anchor YYYY-MM-DD` for reproducible/backdated seeding. Keep it to the exact doc lines that mention the command.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_scripts/test_seed_sample_client.py docs/
git commit -m "test(seed): --anchor CLI smoke; docs note real-date default"
```

---

## Verification (whole-PR definition of done — Wave 1 + Wave 2)

1. `cd backend && python -m pytest tests/ -q` green, coverage ≥75; `_seed_sections.py` + `seed_sample_client.py` both < 500 lines; mypy/flake8/black clean.
2. `git diff main...HEAD --stat` shows the two script files + the test file + the two spec/plan docs (+ runbook line).
3. New behaviors all deterministic-tested: anchor determinism (two-run identical), plan↔actual sums, capacity bridge non-null, stored KPIs, floating+dedicated both present, Alert/Equipment/BreakTime counts, DEMOTED/REJECTED, workflow-config non-empty + one customized, absence-type variety, global defaults idempotent. Prod-safety static scan + allowlist refusal still green.
4. Final whole-branch review + `/code-review` + `/cross-review`; rebase onto main (post-#139); all 7 CI checks green; merge on user confirmation.
5. Post-merge: seed the VM with the real-date default (`docker compose -f docker-compose.prod.yml exec backend python -m backend.scripts.seed_sample_client --days 90`), then the 2A UI-validation pass confirms every Planning/Operations/Simulation screen is populated, coherent, and shows recent data.
