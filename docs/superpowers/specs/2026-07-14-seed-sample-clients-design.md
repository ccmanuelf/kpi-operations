# Seed Sample Demo Clients — Design

**Date:** 2026-07-14
**Status:** Design drafted — pending user review
**Trigger:** The VM (MariaDB prod) has only the empty `SAMPLE_REF` client, so grids/dashboards render empty and the app can't be validated as a real user across Planning / Operations / Simulation. We need a controlled, **prod-safe** way to populate a few clearly-marked DEMO clients with a full, credible dataset — for onboarding/training and end-to-end validation — WITHOUT enabling `DEMO_MODE` (whose lifespan auto-seeder runs a destructive `rebuild_schema` = `drop_all` on boot).

## Goal

A standalone CLI script `backend/scripts/seed_sample_client.py` that INSERTs a full, credible, UI-functional dataset for a small fixed allowlist of DEMO clients, safe to run against the production MariaDB DB. Mirrors the discipline of `backend/scripts/create_admin.py` (own engine, `ensure_migrated` guard, fail-fast, argv-safe) and reuses the battle-tested credible-value logic from the Run-8 unified seeder (`backend/scripts/init_demo_database.py::init_database`) — without inheriting its demo-bootstrap coupling, weak-password demo users, or drop/create behavior.

## Key design decisions (locked with user)

1. **Separate INSERT-only script, not `init_database` reuse wholesale.** `init_database()` is all-or-nothing, seeds 5 fixed clients + weak-password demo users (`admin/admin123`), and is wired to the DEMO_MODE bootstrap. It is unsuitable to run against prod. The new script is INSERT-only, allowlist-guarded, per-client, and creates NO users with known/default passwords.
2. **Reuse Run-8 credibility patterns** (user: "as long as you add a validation test"). Mirror `init_demo_database`'s proven formulas (performance target 0.82–0.96, realistic availability via seeded downtime/setup/maintenance, defect/scrap/rework ratios, OEE ≤ 100, utilization/on-time clamps) and reuse `backend/db/factories.py::TestDataFactory` where it fits. A **credibility-validation test** (bounds assertions) is a hard deliverable.
3. **Full UI-credible client** (user: "including planning-scheduling and workflow variations"). Each client gets the full transactional set PLUS the config/catalog layer so every UI screen renders client-tuned values, PLUS the capacity planning-scheduling graph, PLUS deliberate workflow-state variety.
4. **Hard safety.** Fixed DEMO-client ALLOWLIST — the script refuses any client id not on it. No `drop_all`/`create_all`/`rebuild_schema`; no reference to `DEMO_MODE`. Enforced by a static-scan test.

## Demo clients

Three new clients spanning `ClientType` values (stored as the human-readable value string, e.g. `"Piece Rate"`), plus the existing `SAMPLE_REF` kept on the allowlist:

| client_id | client_name | client_type |
|---|---|---|
| `DEMO-PIECE` | Demo Piece-Rate Garments | `PIECE_RATE` ("Piece Rate") |
| `DEMO-HOURLY` | Demo Hourly Assembly | `HOURLY_RATE` ("Hourly Rate") |
| `DEMO-HYBRID` | Demo Hybrid Works | `HYBRID` ("Hybrid") |

**ALLOWLIST** = `{"DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID", "SAMPLE_REF"}`. Any `--client` value outside this set → fail-fast error, no writes. Default (no `--client`) seeds the three `DEMO-*` clients (not `SAMPLE_REF`, which stays a clean reference).

## Per-client build (grounded in the real schema)

All tables are multi-tenant via `client_id → CLIENT.client_id`. Order respects FK dependencies. Every record is deterministic (see Determinism). Naming traps to respect: `JOB.client_id_fk` and `DEFECT_DETAIL.client_id_fk` (not `client_id`); `ClientType`/`OrderStatus` store value strings; two line concepts (`PRODUCTION_LINE` operational vs `capacity_production_lines`).

**Prerequisites / catalogs (must exist before dependents):**
- `Client` row (`is_active=1`, timezone default).
- `HoldStatusCatalog` + `HoldReasonCatalog` (required before `HoldEntry`) — seed the standard status/reason sets per client.
- `DefectTypeCatalog` (required before `DefectDetail`) — reuse the catalog data from `backend/scripts/seed_defect_types.py`.

**Config / credibility layer (so the client is fully UI-functional):**
- `ClientConfig` (KPI display / dual-view settings), `KPIThreshold` (green/amber/red bands), `DashboardWidgetDefaults`, `AlertConfig` — mirror what `init_database` populates for a demo client.

**Master data:**
- 2 `Shift` rows (e.g. Day/Night, valid `start_time`/`end_time`), unique per `(client_id, shift_name)`.
- 3 `Product` rows (`product_code` unique per client, `ideal_cycle_time` set so performance math is stable).
- 2 `ProductionLine` (operational) rows + 2 `CapacityProductionLine` rows; bridge operational→capacity via `PRODUCTION_LINE.capacity_line_id`.
- ~8 `Employee` rows (`employee_code` unique globally — namespace by client, e.g. `DP-EMP-001`); `EmployeeClientAssignment` (DEDICATED) for each; `EmployeeLineAssignment` (≤2 active lines, allocation ≤100%).
- **No new users are created.** `entered_by`/`inspector_id`/etc. resolve to an EXISTING user: prefer a client-scoped operator if one exists (e.g. `sample_operator` for `SAMPLE_REF`), else fall back to the admin user (`USER-ADMIN` or the first `role='admin'` row). This avoids injecting any account into the prod DB and matches the create_admin discipline (the script writes transactional data, not credentials). Fail-fast if no usable `entered_by` user exists.

**Capacity planning-scheduling graph:**
- `CapacityCalendar` (working days over the seed window, credible shift hours/holidays).
- `CapacityOrder` rows (spanning `OrderStatus` DRAFT→…→COMPLETED + CANCELLED and `OrderPriority`).
- `CapacityProductionStandard` (SAM minutes per style/operation), `CapacityBOMHeader`+`CapacityBOMDetail`, `CapacityStockSnapshot`, `CapacityComponentCheck` (OK/SHORTAGE/PARTIAL mix).
- `CapacitySchedule` + `CapacityScheduleDetail` + `CapacityKPICommitment` (the planning-scheduling the user explicitly asked for), `CapacityAnalysis`, `CapacityScenario`.

**Work orders + workflow variety (the "even mix" requirement):**
- ~8 `WorkOrder` rows per client, deliberately spread so **every `WorkOrderStatus` appears at least once** across RECEIVED / RELEASED / IN_PROGRESS / COMPLETED / SHIPPED / CLOSED / CANCELLED / ON_HOLD (DEMOTED/REJECTED optional-extra). Set `origin` and `capacity_order_id` for planned WOs (bridge to `CapacityOrder`); set OTD-relevant dates (`planned_ship_date`, `actual_delivery_date`) so OTD computes. Set `previous_status` on ON_HOLD/resumed WOs.
- `WorkflowTransitionLog` rows tracing each WO's path (from_status NULL on creation → subsequent to_status), with credible `transitioned_at`, `trigger_source`, and elapsed-hours fields.
- Some `Job` rows under active WOs (respect `client_id_fk`).

**Holds (full chain variety):**
- Open + historical `HoldEntry` rows spanning the full chain PENDING_HOLD_APPROVAL / ON_HOLD / PENDING_RESUME_APPROVAL / RESUMED / RELEASED / CANCELLED / SCRAPPED, with catalog-backed `hold_status`/`hold_reason`. At least some **open** (ON_HOLD) holds so WIP-aging endpoints have live data.

**Daily transactional data over the seed window (`--days`, default 90):**
- `ProductionEntry` per day/shift/line (credible: `run_time = ideal_ct * units / target_perf`, `target_perf ∈ [0.82,0.96]`; seeded downtime/setup/maintenance hours so availability ~90–92%; `defects = max(1, int(units*uniform(0.003,0.012)))`, `scrap = defects//3`, `rework = defects - scrap`). `entered_by` resolves to the client operator (else admin).
- `QualityEntry` (required `work_order_id`) + `DefectDetail` (catalog-validated `defect_type`, `client_id_fk`).
- `DowntimeEntry` (credible `downtime_duration_minutes`, reasons from a realistic set).
- `AttendanceEntry` per employee/day (`scheduled_hours` set; occasional `is_absent=1` with an `AbsenceType`).

**Simulation:**
- 1 `SimulationScenario` per client (`config_json` = a valid `SimulationConfig.model_dump()` shape, `is_active=1`, `client_id` set).

## Determinism

Per-client, per-section seeded RNG exactly as `init_database` does: `random.Random` (or `random.seed`) keyed on a stable hash of `(client_id, section[, index])` so a re-run with the same `--days` produces byte-identical values. No wall-clock in generated values except the anchored window end (today), which the CLI can pin for tests.

## Credibility bounds (validated by test)

Reuse Run-8 clamps and assert them in tests:
- OEE ≤ 100; availability, performance, quality each ∈ (0, 100].
- Performance target lands ~82–96% under the live dual-view recompute (not pegged at cap).
- Utilization clamped [0.10, 1.15]; on-time-rate clamped [75, 98].
- `units_produced > 0`, `run_time_hours > 0`, `employees_assigned > 0`; `defect_count ≥ 0`, `scrap_count ≥ 0`.

## CLI + safety guards (mirror create_admin.py)

- `argparse`: `--client <id>` (optional; must be on ALLOWLIST; default = the three `DEMO-*`), `--days <int>` (default 90), `--reset` (flag). `main(argv=None) -> int`, `raise SystemExit(main())`.
- **`ensure_migrated(engine)`** — require `alembic_version` + core tables present; NEVER create schema (Alembic is the single mechanism).
- Own engine from `DATABASE_URL` (default sqlite path), `with Session(engine)`, single logical transaction per client with intermediate commits like `init_database`; `except: rollback; raise`; `finally: engine.dispose()`. Malformed `DATABASE_URL` handled without echoing it.
- Custom `SeedError(RuntimeError)` for domain failures (e.g. non-allowlist client), caught in `main` → stderr + `return 1`.
- **No secrets on argv / in logs, and no credential writes.** The script creates no users and touches no `password_hash`; `DATABASE_URL` is never echoed.

## Reset semantics (`--reset`)

Scoped, FK-safe delete of ONLY the target client(s)' rows before re-seeding: delete children before parents (transactional entries → jobs → holds → work orders → workflow logs → capacity graph → assignments → master data → config/catalogs), all filtered by `client_id` (or `client_id_fk`). Leaves the `Client` row and OTHER clients untouched. Without `--reset`, the script is **skip-if-exists / idempotent**: a second run adds zero rows.

## Verification / Tests (`backend/tests/test_scripts/test_seed_sample_client.py`, using the `db_session` template-clone fixture)

1. **Per-client counts** — after seeding, each client has the expected non-zero counts across every entity family.
2. **Workflow completeness** — every `WorkOrderStatus` in the target mix appears at least once per client; `WorkflowTransitionLog` present; full hold chain represented.
3. **Idempotency** — a second run without `--reset` adds **zero** rows.
4. **Scoped reset** — `--reset` on one client removes its rows and leaves the other clients' rows intact.
5. **Credibility bounds** — the assertions listed above hold for all generated rows.
6. **Allowlist refusal** — `main(["--client", "REAL-PROD-CLIENT"])` returns 1 and writes nothing.
7. **Prod-safety static scan** — the script source contains no `drop_all` / `create_all` / `rebuild_schema` / `DEMO_MODE` tokens (mirrors the spirit of `test_no_create_all_outside_alembic`).
8. **CLI smoke** — file-based migrated DB + monkeypatched `DATABASE_URL`, `main([...])` returns 0 (mirrors `test_create_admin.py`).

## Decomposition

- Idempotent per-entity helpers (`seed_shifts`, `seed_products`, `seed_lines`, `seed_employees`, `seed_capacity_graph`, `seed_work_orders`, `seed_daily_data`, `seed_holds`, `seed_simulation`, `seed_config_layer`, `seed_catalogs`) each `skip-if-exists`.
- `seed_client(session, spec)` orchestrator + `reset_client_data(session, client_id)`.
- A `CLIENT_SPECS` table (per-client type, product/line/employee counts, RNG seeds) drives the three clients from one code path.
- Keep the file focused; if it approaches ~500 lines, split credible-value helpers into a sibling module. Reuse `TestDataFactory` and mirror `init_demo_database` formulas rather than re-deriving them.

## Out of scope

- Wiring the script into app startup or any bootstrap path (it is an operator-run CLI only).
- Enabling/altering `DEMO_MODE` or the lifespan auto-seeder.
- Seeding the existing 5 `init_database` demo clients or any real client.
- New KPI/business logic — the script only populates existing tables through the ORM.
- Operational "inventory" beyond `capacity_stock_snapshot` (no such model exists).

## Definition of done

- `backend/scripts/seed_sample_client.py` seeds the three `DEMO-*` clients (and `SAMPLE_REF` on request) with the full UI-credible + planning-scheduling + workflow-variety dataset, INSERT-only, allowlist-guarded, deterministic, credible.
- All eight test groups green; full backend suite green (coverage ≥ 75); lint/format clean.
- `/code-review` + `/cross-review`; all 7 CI checks green; merge on user confirmation.
- Post-merge: run on the VM against MariaDB (`--days 90` for all three clients) confirm-first per sudo/exec, then the follow-on 2A UI-validation pass over Planning / Operations / Simulation on the seeded data.
