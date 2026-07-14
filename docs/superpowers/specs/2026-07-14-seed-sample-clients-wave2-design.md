# Seed Sample Clients — Wave 2 (completeness + visibility) — Design

**Date:** 2026-07-14
**Status:** Design approved (user: "validate all options including workflow configurations"; split "only if more robust and manageable")
**Trigger:** A completeness audit of `seed_sample_client.py` against the proven sibling `init_demo_database.py` found real gaps — most critically that the fixed past anchor makes the seeded data **invisible** on the app's "Last 30 Days" dashboards, plus several coherence gaps and unpopulated UI screens. This wave closes them and splits the growing file for manageability.

Wave-1 spec/plan: `2026-07-14-seed-sample-clients-design.md` / `...-plan.md`. Audit source: comparison agent report (recorded in the SDD ledger).

## Decisions (locked)

1. **Scope = full comprehensive** — all audit items (1–11) plus explicit workflow-configuration coverage.
2. **File split** — move the section-builder helpers into a sibling module so the entrypoint file stays focused (the file exceeds 1000 lines and grows this wave; splitting is the more manageable, reliable structure).
3. **Anchor** — real seeding uses `date.today()` (recent, visible data); tests pass a fixed anchor (determinism preserved). The no-wall-clock **source-scan** guard is replaced by a **two-run determinism** test.

## Wave-2 changes

### A. Temporal anchor (CRITICAL — item 1/2a)
- Thread an `anchor: date` parameter through `seed_client` and the four date-using helpers (`seed_capacity_graph`, `seed_work_orders`, `seed_holds`, `seed_daily_data`). Remove the module-level `ANCHOR_DATE` as the value source.
- `main()` adds `--anchor YYYY-MM-DD` (default = `date.today()`); tests pass a fixed date (e.g. `date(2026, 6, 15)`).
- Operations history (work orders / holds / daily data) ends at `anchor`; capacity planning spans forward from `anchor` — same coherence as today, but now relative to the real run date so "Last N Days" dashboards show data.
- **Guard rework:** delete `test_seeder_uses_no_wall_clock` (source-scan) — it would fail on the intentional `date.today()` default. Replace with `test_seed_values_deterministic_for_fixed_anchor`: run `seed_client` twice into two fresh DBs with the SAME explicit anchor, assert identical generated values (units/run_time/defects for production, order quantities, etc.). Determinism is now guaranteed *given an anchor*, which is the real invariant.

### B. Coherence (HIGH — items 2b/2c/8/§3)
- **Plan-vs-actual true-up:** distribute `ProductionEntry` units per work order so cumulative units land on a status-derived target of `WorkOrder.planned_quantity` (SHIPPED/CLOSED ≈ 100 %, COMPLETED ≈ 100 %, IN_PROGRESS ≈ 50 %, ON_HOLD ≈ 30 %, RELEASED/RECEIVED = 0 %), pinning the last entry so the sum matches; set `WorkOrder.actual_quantity` to the produced total. Test: `sum(units) per WO == expected target`.
- **WO↔CapacityOrder bridge:** for planned work orders, set `origin="CAPACITY_PLAN"`, `capacity_order_id` (a seeded `CapacityOrder.id`), and `planned_start_date`; align the bridged `CapacityOrder.completed_quantity/status`. Fixes the capacity OTD panel (0 % when `planned_start_date` is NULL). Test: planned WOs have non-null `capacity_order_id` + `planned_start_date`.
- **Stored ProductionEntry KPI fields:** set `maintenance_hours`, `employees_present`, `ideal_cycle_time`, `actual_cycle_time`, and the stored `efficiency_percentage`/`performance_percentage`/`quality_rate` (mirror the sibling's computed values) so screens reading stored columns aren't NULL.
- **WO milestones + `previous_status`:** set the per-status milestone dates (`received_date`, `dispatch_date`, `shipped_date`, `closure_date`) coherent with each status, and set `previous_status` on the ON_HOLD/resumed WOs.

### C. Populate empty screens (MODERATE — items 4/5/6/7)
- **`Alert` instances:** a few active `Alert` rows per client (mixed category/severity) so the Alerts panel is non-empty (`AlertConfig` alone doesn't feed it).
- **`Equipment`:** ~2 per operational line, typed per department; feeds the equipment screen + `oee.py`.
- **`BreakTime`:** ~2 per shift (morning + lunch).
- **Floating-pool:** mark ≥1 of the 8 employees `is_floating_pool=True` with a FLOATING `EmployeeClientAssignment` so the floating-pool/coverage UI and the DEDICATED-vs-FLOATING invariant are exercised. Test: both assignment types present.

### D. Variety + workflow configuration (item 9 + user's "workflow configurations")
- **DEMOTED + REJECTED work orders:** add one WO in each state (REJECTED with `rejection_reason`/`rejected_by`/`rejected_date`), extending the status-coverage set and exercising the workflow's demote/reject paths. Test: coverage set includes DEMOTED + REJECTED.
- **Workflow config coverage:** confirm each demo client's `ClientConfig.workflow_statuses`/`workflow_transitions`/`workflow_optional_statuses`/`workflow_closure_trigger` are populated (the Wave-1 `ClientConfig()` default already sets these) so the `/admin/workflow-config` screen renders; add a test asserting the demo clients have non-empty workflow config. If the demo clients should show *distinct* workflow variety, give one client a customized (subset/reordered) `workflow_statuses` to exercise the non-default path.
- **Downtime + absence variety:** broaden downtime to the sibling's ~5-reason set with higher density (credible Pareto); use ≥2 `AbsenceType` values across absent rows.

### E. Global tables (DECISION — item 11)
- `DashboardWidgetDefaults` and `seed_metric_dependencies` are GLOBAL (not per-client). Seed them **once**, idempotently, from `main()` (not inside the per-client loop) — guarded by skip-if-exists — so dual-view services + default dashboards work on a fresh prod DB where `init_database` never ran. Reuse the sibling's data/`seed_metric_dependencies(session)` call. Test: both populated after a run; idempotent.

### F. File split (item: manageability)
- Move the section-builder helpers (`seed_catalogs`, `seed_config_layer`, `seed_shifts/products/lines/employees`, `seed_capacity_graph`, `seed_work_orders`+`_transition_chain`, `seed_holds`, `seed_daily_data`, `seed_simulation`, and the new Wave-2 helpers) plus the `_*` constant tables into a new module `backend/scripts/_seed_sections.py`. Keep in `seed_sample_client.py`: the CLI (`main`), safety guards (`ALLOWLIST`, `SeedError`, `ensure_migrated`, `rng_for`), `ClientSpec`/`CLIENT_SPECS`, `resolve_entered_by`, `RESET_TABLE_ORDER`/`reset_client_data`, and the `seed_client` orchestrator (imports the section helpers). Both files stay well under 500 lines. No behavior change — the full test suite is the safety net; do the split FIRST (pure move) so later tasks build on the module layout.

## Out of scope (SKIP, per audit)
- User/credential seeding (Wave-1 decision, prod safety).
- `CoverageEntry`/`ShiftCoverage`/`UserPreferences`/`SavedFilter` (the sibling doesn't seed them either; add only if a demo-validation screen needs them).

## Verification
- All new behaviors get a deterministic test (counts, coherence assertions, bridge non-null, floating-pool both-types, workflow-config non-empty, global-tables populated+idempotent, plan-vs-actual sums).
- Determinism test (two-run identical) replaces the source-scan guard.
- Full backend suite green (coverage ≥75); mypy/flake8/black clean; `/code-review` + `/cross-review`; 7 CI checks green (after PR #139 setuptools unblock is merged).
- Post-merge: seed the VM with the real-date default (`--days 90`), then the 2A UI-validation pass over Planning / Operations / Simulation confirms every screen is populated, coherent, and shows recent data.

## Definition of done
Wave-2 delivers a demo dataset that is not just present but **visible today and internally coherent** across every Planning/Operations/Simulation screen, in a split, maintainable module layout, with determinism preserved for tests.
