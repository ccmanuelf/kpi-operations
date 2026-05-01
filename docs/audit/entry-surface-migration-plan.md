# Entry Surface Migration Plan — Phase 1

**Project:** kpi-operations
**Date:** 2026-05-01
**Status:** Phase 1 — Plan drafted, pending spec-owner approval before Phase 2 execution
**Source spec:** `/Users/mcampos.cerda/Downloads/06_kpi-operations_entry_interface_audit.md`
**Predecessor:** `docs/audit/entry-surface-inventory.md` (Phase 0)

This plan converts the 20 non-compliant entry surfaces identified in Phase 0 into a sequenced, complexity-classified migration roadmap. Each surface is mapped to a reference component, complexity tier, effort estimate, validation rules to preserve, and tests that must pass post-migration.

---

## 0. Plan Updates (2026-05-01) — Runtime Validation Findings

This section supersedes the relevant rows/text in §3, §4, §5, and §12 below. The original sections remain unedited as the planning baseline; this update is the authoritative source for affected surfaces.

**Trigger:** while starting Phase 2 / Group A, a runtime check on `QualityEntryGrid` showed its save payload does not match the backend Pydantic schema. A focused validation pass was run on all 4 Group A surfaces. Full findings: `docs/audit/group-a-runtime-validation.md`.

### 0.1 Group A revised classification

| Plan row | Surface | Original effort | Revised complexity | Revised effort | Reason |
|---|---|---|---|---|---|
| 1 | Quality re-route | XS (Simple) | **Moderate** | **M (4–16 h)** | Field renames + missing required fields (`client_id`, `shift_date`, `units_passed`); ~7 dead UI fields to drop |
| 2 | Attendance re-route | XS (Simple) | **Moderate** | **M (4–16 h)** | Field renames + status enum translation + datetime format conversion + clipboardParser fix + missing `client_id`/`scheduled_hours` |
| 3 | Downtime re-route | XS (Simple) | **Moderate** | **M (4–16 h, upper end)** | Enum mapping (UI category → `DowntimeReasonEnum`) + unit conversion (hours → minutes) + clipboardParser fix + missing `client_id`/`shift_date` |
| 4 | Hold-Resume re-route | XS (Simple) | **Moderate** | **M (4–16 h)** | Field renames + reason-code catalog mapping + missing `client_id` + drop server-controlled fields + fix `dataEntry.ts:34` (`/holds/{id}/resume` is a nonexistent URL) |

**Group A revised total effort: 2–4 days** (was "~½ day").

### 0.2 Revised Group A intra-group ordering

Original plan implicitly treated the 4 surfaces as equivalent. Revised ordering, simplest-payload-first, builds the field-mapping pattern incrementally:

1. **Quality** — pure renames; clipboardParser already aligned; cleanest establishment of the "client_id from auth + payload-shape adapter" pattern.
2. **Holds** — same pattern as Quality + single string→catalog-code mapping; approval-workflow buttons already work.
3. **Attendance** — adds status enum translation + datetime format conversion + clipboardParser edit.
4. **Downtime** — largest divergence (enum mapping + unit conversion); reuses adapter pattern from #1–#3.

### 0.3 Group B Phase 0 — runtime validation findings (2026-05-01)

The Group B Phase 0 runtime validation is COMPLETE. Findings in `docs/audit/group-b-runtime-validation.md`:

| Plan row | Surface | Endpoint status | Recommended option |
|---|---|---|---|
| 5 | WorkflowStepProduction | `POST /production-entries` and `GET /work-orders/shift-production` both 404 | **(c) skip persistence** — read-only checkpoint linking out to the Group A ProductionEntryGrid |
| 6 | WorkflowStepDowntime | `PATCH /downtime/{id}/resolve` and `GET /downtime/shift` both 404 + **data-integrity bug**: catch block forges success state on failure (operator advances thinking incidents persisted when they did not) | **(c) skip persistence** — read-only checkpoint, fix the forged-success bug as part of the migration |
| 7 | WorkflowStepAttendance | Never persists; `GET /employees/shift-roster` and `GET /stations` both 404 | **(c) skip persistence** + fix the roster read to `/api/employees?shift_id=...`, drop the dead `/stations` call |

**Recommendation: option (c) for all three surfaces.** Total revised effort: **1.5–2.5 days** (option c) vs 3–5 days (option a) vs 6–8 days (option b — the original plan).

Why (c) wins:
- (b) would require reopening the just-closed Group A grids to add `compactMode` props, risking regressions
- (a) papers over the cracks but the wizard's UX still falls short of the dedicated grid
- (c) is the smallest change, directly serves the "Excel adoption" goal (operators use the dedicated grid for entry, the wizard becomes a checkpoint), and **runs cleanly in parallel** with later groups (no shared composables / stores touched)

### 0.4 Cross-cutting findings from Group B Phase 0 — to fix in scope

Per CLAUDE.md "Self-audit findings expand scope; no tech debt allowed", four findings from the wizard validation expand Group B's scope:

1. **All 3 steps swallow API errors with `console.error` only** — no `useNotificationStore` (the Run-5 silent-catch fix was never applied here). Fix in scope.
2. **None of the 3 steps import `useAuthStore` / `useKPIStore`** — same systemic gap as Group A's "client_id missing" finding. Even if the steps no longer create records (option c), reads should be tenant-aware. Fix in scope.
3. **WorkflowStepDowntime forges success on failure** (`WorkflowStepDowntime.vue:323-331`) — active data-integrity bug. Independent of endpoint mismatch. Fix in scope (delete the forged-success path).
4. **All 3 steps ship hard-coded mock fixtures in fetch catch blocks** — pre-dates the seeded-DB era and now hides endpoint failures from developers. Remove the fixtures so failures surface clearly.

### 0.5 Status badge amendment

### 0.4 Status badge amendment

The 4 grids classified "Compliant" in Phase 0 inventory (rows 4, 6, 8, 10) are amended to **"UI-compliant; payload-divergent"**. They satisfy the visual/interaction Spreadsheet Standard; the save path needs fixing as part of each surface's migration. The "Compliant" status is restored only when the grid completes a full save round-trip with the backend.

### 0.6 Effort summary delta

| Group | Original estimate | Revised estimate | Delta |
|---|---|---|---|
| A | ½ day | **2.5 days actual** (Quality M, Holds M, Attendance M, Downtime M) | +2 days |
| B Phase 0 | n/a | ½ day actual | +½ day |
| B migrations (option c) | 1–2 days (embed plan) | 1.5–2.5 days (option c — skip persistence, fix reads, fix integrity bug) | minor delta |
| B can parallelise? | no (was embed) | **yes** (no shared composables touched) | enables overlap |

**Phase 2 total estimate revised:** 5.5–7 weeks → **6–7.5 weeks** (single-engineer, sequential per surface). Group A actual outcome confirmed lower bound.

---

## 1. Standard amendments carried from Phase 0

The Spreadsheet Standard for this project is the source-spec text **with** the three resolutions documented in `entry-surface-inventory.md` § 1.1:

- **R1.** AG Grid Community is the only canonical grid technology. `v-data-table` with per-cell editors is **not** compliant.
- **R2.** Cell-range selection and fill-handle are provided through Community-feasible custom code; the native Enterprise flags `enableRangeSelection` / `enableFillHandle` MUST NOT be enabled.
- **R3.** Custom clipboard paste via `useAGGridBase.handlePasteFromExcel` is canonical. Native `processDataFromClipboard` is acceptable but not required.

Every migration in this plan is verified against the amended Standard, not the original spec text.

---

## 2. Reference components (canonical patterns)

Migrations copy from these in-tree references. Any deviation must be justified per surface.

| Reference | Path | What it demonstrates |
|---|---|---|
| `AGGridBase.vue` | `frontend/src/components/grids/AGGridBase.vue` | The wrapper. All entry grids consume it. |
| `useAGGridBase.ts` | `frontend/src/components/grids/composables/useAGGridBase.ts` | Shared paste, snackbar, mergedGridOptions, exportToCsv, navigation. |
| `ProductionEntryGrid.vue` | `frontend/src/components/grids/ProductionEntryGrid.vue` | Typed cell editors, save batching, CSV upload pairing. |
| `useProductionGridData.ts` | `frontend/src/components/grids/composables/useProductionGridData.ts` | Domain-specific column defs, validators, save logic. Mirror for new domains. |
| `clipboardParser.ts` | `frontend/src/utils/clipboardParser.ts` | `entrySchemas` validation per entry type. New domains add a schema entry here. |
| `CSVUploadDialogProduction.vue` | `frontend/src/components/grids/dialogs/CSVUploadDialogProduction.vue` | CSV import UX paired with each entry grid. |

---

## 3. Migration list (20 surfaces, classified)

| # | Surface | Inv row | File path | Complexity | Effort | Reference | Backend endpoints (preserve) |
|---|---|---|---|---|---|---|---|
| 1 | Re-route /data-entry/quality | 3 | `frontend/src/components/entries/QualityEntry.vue` | **Simple** | XS | grid #4 already built | `POST /quality/entries`, `PUT /quality/entries/{id}` |
| 2 | Re-route /data-entry/attendance | 5 | `frontend/src/components/entries/AttendanceEntry.vue` | **Simple** | XS | grid #6 already built | `POST /attendance`, `POST /attendance/bulk`, `POST /attendance/mark-all-present` |
| 3 | Re-route /data-entry/downtime | 7 | `frontend/src/components/entries/DowntimeEntry.vue` | **Simple** | XS | grid #8 already built | `POST /downtime`, `PUT /downtime/{id}` |
| 4 | Re-route /data-entry/hold-resume | 9 | `frontend/src/components/entries/HoldResumeEntry.vue` | **Simple** | XS | grid #10 already built | `POST /holds`, `PUT /holds/{id}`, `POST /holds/{id}/approve-hold`, `POST /holds/{id}/request-resume`, `POST /holds/{id}/approve-resume` |
| 5 | Workflow Wizard — Production step | 43 | `frontend/src/components/workflow/steps/WorkflowStepProduction.vue` | **Simple** | S | embed `ProductionEntryGrid` | `POST /production` |
| 6 | Workflow Wizard — Downtime step | 48 | `frontend/src/components/workflow/steps/WorkflowStepDowntime.vue` | **Simple** | S | embed `DowntimeEntryGrid` | `POST /downtime` |
| 7 | Workflow Wizard — Attendance step | 49 | `frontend/src/components/workflow/steps/WorkflowStepAttendance.vue` | **Moderate** | M | embed `AttendanceEntryGrid` (compact, roster-shape) | `POST /attendance/bulk`, `POST /attendance/mark-all-present` |
| 8 | MyShift quick-action dialogs (Production / Downtime / Quality) | 12 | `frontend/src/components/dialogs/ShiftDashboardDialogs.vue` | **Moderate** | M | embed entry grids in compact dialog mode | `POST /production`, `POST /downtime`, `POST /defect-details` |
| 9 | Capacity — Production Lines worksheet | 19 | `frontend/src/views/CapacityPlanning/components/grids/ProductionLinesGrid.vue` | **Moderate** | M | rebuild on `AGGridBase` | `POST /capacity/lines`, `PUT /capacity/lines/{id}` |
| 10 | Capacity — Orders worksheet | 20 | `frontend/src/views/CapacityPlanning/components/grids/OrdersGrid.vue` | **Moderate** | M | rebuild on `AGGridBase` | `POST /capacity/orders`, `PUT /capacity/orders/{id}`, `PATCH /capacity/orders/{id}` |
| 11 | Capacity — Standards worksheet | 21 | `frontend/src/views/CapacityPlanning/components/grids/StandardsGrid.vue` | **Moderate** | M | rebuild on `AGGridBase` | `POST /capacity/standards`, `PUT /capacity/standards/{id}` |
| 12 | Capacity — Calendar worksheet | 22 | `frontend/src/views/CapacityPlanning/components/grids/CalendarGrid.vue` | **Moderate** | M | rebuild on `AGGridBase`; date-pinned columns | `POST /capacity/calendar`, `PUT /capacity/calendar/{id}` |
| 13 | Capacity — BOM worksheet | 23 | `frontend/src/views/CapacityPlanning/components/grids/BOMGrid.vue` | **Complex** | L | master-detail grid (parent BOM + child components) | `POST /capacity/bom`, `PUT /capacity/bom/{id}`, `POST /capacity/bom/{id}/components`, `PUT /capacity/bom/{id}/components/{cid}` |
| 14 | Capacity — Stock worksheet | 24 | `frontend/src/views/CapacityPlanning/components/grids/StockGrid.vue` | **Moderate** | M | rebuild on `AGGridBase` | `POST /capacity/stock`, `PUT /capacity/stock/{id}` |
| 15 | Admin — Defect Types catalog | 34 | `frontend/src/views/admin/AdminDefectTypes.vue` | **Simple** | S | inline grid replacing edit dialog | `POST /defect-type-catalog`, `PUT /defect-type-catalog/{id}`, `POST /defect-type-catalog/upload/{client_id}` |
| 16 | Admin — Part Opportunities | 35 | `frontend/src/views/admin/PartOpportunities.vue` | **Simple** | S | inline grid replacing edit dialog | `POST /part-opportunities`, `PUT /part-opportunities/{part_number}`, `POST /part-opportunities/bulk-import` |
| 17 | Workflow Wizard — Targets step | 46 | `frontend/src/components/workflow/steps/WorkflowStepTargets.vue` | **Moderate** | M | 24-row hourly target grid | `PUT /workflow/config/{client_id}` |
| 18 | Capacity — KPI Tracking thresholds | 28 | `frontend/src/views/CapacityPlanning/components/panels/KPITrackingPanel.vue` | **Moderate** | M | thresholds grid | `PUT /capacity/kpi-workbook/...`, `PUT /kpi/thresholds` |
| 19 | Capacity — Scenarios | 30 | `frontend/src/views/CapacityPlanning/components/panels/ScenariosPanel.vue` | **Complex** | L | scenarios-as-rows grid; redesign 16-field dialog into column set | `POST /capacity/scenarios`, `POST /capacity/scenarios/...` |
| 20 | Floating Pool assignment | 37 | `frontend/src/views/admin/FloatingPoolManagement.vue` | **Complex** | L | assignment grid with employee-pool master-detail | `POST /floating-pool`, `PUT /floating-pool/{id}`, `POST /floating-pool/assign`, `POST /floating-pool/unassign`, `POST /employees/{id}/floating-pool/assign` |
| 21 | WorkOrderManagement create/edit | 11 | `frontend/src/views/WorkOrderManagement.vue` | **Complex** | L | replace 12-field dialog with inline grid; preserve QC approval + capacity-link side-actions as row context-menu | `POST /work-orders`, `PUT /work-orders/{id}`, `PATCH /work-orders/{id}/status`, `POST /work-orders/{id}/approve-qc`, `POST /work-orders/{id}/link-capacity`, `POST /work-orders/{id}/unlink-capacity` |

Effort key: XS = under 1 hour, S = 1–4 hours, M = 4–16 hours, L = 16–40 hours.

---

## 4. Complexity classifications

Per spec § "Phase 1 — Migration plan":

**Simple (5 surfaces, #1–4 + 5–6 + 15–16).**
Surface is a list of records being entered one at a time; migration is "swap the form for an existing grid (or build a thin grid against existing endpoints)." No UX redesign needed. Surfaces 1–4 are router-line changes only — the grid components already exist and pass tests.

**Moderate (8 surfaces, #7 + 8 + 9–12 + 14 + 17 + 18).**
Surface has multi-step flow, conditional fields, or relationships across entities. Migration requires UX redesign to fit the grid model (compact-mode embeds for wizard steps, master-detail for relational data, date-pinned columns for calendar). All endpoints stay; column structure and selection model are the work.

**Complex (4 surfaces, #13 + 19 + 20 + 21).**
Surface is genuinely awkward as a flat grid — wizard with branching (Scenarios), parent-child mutation (BOM, Floating Pool, WorkOrder side-actions). Per spec-owner directive, default action is **migrate AND redesign**, observing the goal: user adoption from Excel. Each Complex surface needs a one-page UX sketch shared with spec owner before its Phase 2 starts.

---

## 5. Sequencing (9 execution groups)

Sequencing principles, in order of priority:
1. **Frequency of use first** — operator-facing daily entries before admin-facing weekly entries.
2. **Risk first to lowest** — start with router-only changes that prove the migration pattern, escalate to single-component swaps, end with redesigns.
3. **Avoid colliding with the dual-view architecture work (spec #1)** — Capacity-domain migrations cluster around the dual-view coordination point; Group D is sequenced to land before dual-view's assumption-registry phase begins.

### Group A — Quick wins: re-route 4 routes (4 surfaces, ~½ day)
Migrations: #1, #2, #3, #4.
Touches `frontend/src/router/index.ts:89, 95, 101, 107`. Existing AG Grid components in `frontend/src/components/grids/` become the routed targets; the form variants in `frontend/src/components/entries/` are deleted.
**Why first:** highest user-volume domains; the migration is essentially an import path change; failure mode is contained to four routes.

### Group B — Workflow wizard step grid embeds (3 surfaces, 1–2 days)
Migrations: #5, #6, #7.
Each step component currently re-implements a single-row form for a domain that already has an entry grid. Embed the grid in compact mode inside the step's slot. Removes ~300 lines of duplicate UI code (per Phase 0 § 6.5).
**Why second:** low risk (the underlying grid is already proven); high leverage (eliminates duplicate maintenance).

### Group C — MyShift quick-action dialogs (1 surface containing 3 dialogs, 1–2 days)
Migration: #8.
Embed `ProductionEntryGrid`, `DowntimeEntryGrid`, and `QualityEntryGrid` in compact-mode AG Grid dialogs. Preserve the quick-action open-from-FAB UX. Operator-facing and the highest-frequency entry path during a shift.
**Why third:** validates the compact-mode embed pattern that Group B used, on the most operator-visible surface.

### Group D — Capacity worksheet AG Grid rebuild (5 surfaces, 1–2 weeks)
Migrations: #9, #10, #11, #12, #14 (and #13 BOM follows in Group F because of its master-detail complexity).
Replace `v-data-table` worksheets with `AGGridBase`-backed grids using the established `useXxxGridData` pattern. Each worksheet gets a domain-specific composable.
**Coordination with dual-view spec #1:** the dual-view work touches Capacity calculation paths but not these worksheet UIs. Coordinate to land Group D before dual-view's assumption-registry phase begins so that registry consumers see modern grids.

### Group E — Admin catalog grids (2 surfaces, 2–3 days)
Migrations: #15, #16.
Inline-grid the per-client defect catalog and per-part opportunity catalog. Each is "one row per record" with bulk-import already supported. The simplest of the moderate group.

### Group F — Capacity BOM master-detail (1 surface, 4–5 days)
Migration: #13.
Master-detail AG Grid with parent BOM rows and expandable child component rows. Picks up the orphaned `POST /capacity/bom/{id}/components` and `PUT /capacity/bom/{id}/components/{cid}` endpoints (Phase 0 § 6.7) — these are written for the first time as part of this migration.
**Why after Group D:** uses Group D's Capacity-specific composables as a foundation.

### Group G — Workflow wizard targets + capacity thresholds (2 surfaces, 3–4 days)
Migrations: #17, #18.
Hourly target grid (24 rows) and KPI threshold grid. Both are small, structured, and use the patterns established by Groups A–F.

### Group H — Complex redesigns (3 surfaces, 1.5–3 weeks)
Migrations: #19 (Scenarios), #20 (Floating Pool), #21 (WorkOrder).
Each gets a UX sketch reviewed with spec owner before its Phase 2 starts. Sequencing inside Group H by visibility:
- #21 WorkOrder first (most-trafficked operational view; high user-adoption value).
- #19 Scenarios second (planner-facing, contained inside Capacity tab).
- #20 Floating Pool last (admin-facing, lowest user volume).

### Group I — Verification & cleanup (continuous)
Tasks:
- I.1. Verify `frontend/src/components/DataEntryGrid.vue` (inv row 56) alive/dead. If dead → delete. If alive → classify and add to plan.
- I.2. Coordinate with dual-view spec #1 owner when assumption-registry surface is designed; confirm it adopts AG Grid patterns from this plan.
- I.3. After Group H completes, run a final grep for `v-text-field`/`v-textarea` in `views/` and `components/entries/` (excluding exception list) and confirm zero hits per source spec § "Definition of done".
- I.4. Phase 3 work begins: extract `docs/standards/entry-ui-standard.md`, add ESLint local rule, update `CONTRIBUTING.md`.

---

## 6. Per-surface acceptance criteria

Per spec § "Phase 2 — Acceptance criteria per surface", every migrated surface must meet ALL of:

- [ ] New grid component implements every item in the (amended) Spreadsheet Standard
- [ ] Existing validation rules preserved or improved (never weakened)
- [ ] CSV import works (uses or extends `backend/utils/csv_upload.py`)
- [ ] CSV export works and round-trips with import
- [ ] Existing API endpoints still work (no backend changes unless this plan calls for them — none do, except Group F formalizing the orphaned BOM-component endpoints)
- [ ] Unit tests for the grid component pass (`npm run test`)
- [ ] Integration tests for the surface (login → navigate → enter → save → verify) pass
- [ ] Manual smoke: Excel copy-paste round-trip works in the running dev environment
- [ ] Old form component **deleted** from the tree (not orphaned)
- [ ] Routes updated to point at the new grid
- [ ] Inventory updated (move row from Non-compliant to Compliant)
- [ ] `docs/views/<surface-name>.md` brief written (column set, validation rules, CSV format)

Project-wide acceptance for Phase 2 completion:
- Zero non-exception `v-text-field`/`v-textarea` matches in `frontend/src/views/**/*.vue` and `frontend/src/components/entries/**/*.vue`
- All existing tests still pass (backend ≥ 75 % coverage gate, frontend full suite green)

---

## 7. Tests that must pass after each migration

Per surface, the migration touches three test layers:

1. **Component unit tests** (`frontend/src/components/grids/__tests__/`) — column defs, validators, paste schema, save batching.
2. **Integration tests** (`frontend/tests/integration/` or equivalent) — surface renders, paste from Excel succeeds, save round-trips through the API.
3. **Backend route tests** (`backend/tests/`) — unchanged endpoints; verify nothing in the migration accidentally broke a contract.

Every migration adds at least the test count it removed. No surface is allowed to lose test coverage during migration. Project memory rule applies: zero tolerance for flaky tests; test count only goes up.

---

## 8. Validation rules to preserve (per surface, summary)

Per spec § "Cross-cutting requirements: No regressions in existing functionality", every surface's existing validation must survive migration. The full list of rules per surface is captured in the surface's existing `<v-form>` `:rules` arrays and store-side validators; rather than duplicate them here, the migrating engineer is required to:

1. Read the existing form component thoroughly and document every `:rules` entry.
2. Map each rule to a column-level `valueParser` / `cellClassRules` pair in the new grid.
3. Preserve any cross-field validation (e.g., end > start) using `cellClassRules` or `gridApi.applyTransaction` post-validation.
4. If a rule cannot be expressed in AG Grid, add a save-time check in the corresponding `useXxxGridData.saveRows()` action.

If the engineer discovers a missing or broken validation rule during the read-through (per CLAUDE.md "Self-audit findings expand scope"), it is fixed as part of the migration, not deferred.

---

## 9. CSV import compatibility

Per spec § "Cross-cutting requirements", CSV import compatibility is preserved or improved.

| Surface group | Existing CSV path | Status |
|---|---|---|
| Group A (4 routes) | `CSVUploadDialog{Quality,Attendance,Downtime,Hold}.vue` | Already present and grid-paired. Re-routing inherits. |
| Group B (3 wizard steps) | inherits domain CSV from Group A | No new CSV work. |
| Group C (MyShift dialogs) | inherits domain CSV from Group A | No new CSV work. |
| Group D (5 capacity worksheets) | mixed: some have textarea-paste dialogs; no first-class CSV | **New work:** add `CSVUploadDialog{Lines,Orders,Standards,Calendar,Stock}.vue` paired with each grid, mirroring the production grid pattern. |
| Group E (admin catalogs) | Defect Types has `POST /defect-type-catalog/upload`; Part Opportunities has `POST /part-opportunities/bulk-import` | Already present; wire to new grids. |
| Group F (BOM master-detail) | none | **New work:** CSV format that supports parent + child rows. Likely a single CSV with a parent-id column. |
| Group G (Targets, Thresholds) | none | **New work, but small:** 24-row hourly targets is a 1-column CSV; thresholds is a small fixed-row CSV. |
| Group H (Scenarios, Floating Pool, WorkOrder) | mixed | **Per surface:** WorkOrder import already exists for some fields; Scenarios has none; Floating Pool has none. Plan-owner reviews CSV format per surface before coding. |

---

## 10. Coordination with the dual-view architecture work (spec #1)

Phase 0 § 8 documents this:
- The dual-view spec's assumption-registry CRUD UI (when reached) follows this plan's Spreadsheet Standard.
- The dual-view spec's exception-review surface (when reached) follows this plan's Spreadsheet Standard.

This plan does NOT block dual-view work. Dual-view continues in parallel with Group A–C of this plan. Group D (Capacity worksheets) is sequenced to land BEFORE the dual-view assumption-registry phase begins so that registry-consuming worksheets are already on AG Grid when the registry UI is wired in.

If dual-view spec #1 reaches its registry-UI phase before Group D completes, dual-view either (a) waits for Group D, or (b) builds the registry UI on `AGGridBase` directly using this plan's reference patterns. Either way it follows the Standard.

---

## 11. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AG Grid Community lacks an API needed for a Community-feasible range-select / fill-handle subset (R2 fallback to option b) | Medium | Medium | Group A first proves the existing custom paste pipeline; if range-select can't be built within Community, drop the requirement on a per-surface basis and document the Enterprise upgrade path. |
| Capacity worksheet store coupling (`useCapacityPlanningStore`) is tighter than expected | Medium | High | Group D starts with the simplest worksheet (Production Lines, #9) to validate the pattern before tackling Calendar (#12) and BOM (#13). |
| WorkOrder side-actions (QC approval, capacity link) don't fit a row context-menu UX | Medium | Medium | UX sketch for #21 reviewed with spec owner before its Phase 2 starts. Fallback: keep side-actions as a side-panel triggered from grid row selection. |
| MyShift quick-action UX feels heavier as a grid than as a single-row dialog | Medium | High (user adoption) | Compact-mode embed in #8 keeps single-row entry as the default focus; multi-row paste is opt-in. UX validated with an operator before Group C is closed. |
| `DataEntryGrid.vue` (row 56) turns out to be load-bearing legacy | Low | Medium | I.1 verifies first; if alive, classify and slot into the plan before Group H. |
| Test coverage drops during a migration | Low | High | Per-surface acceptance criteria § 6 mandate that test count only goes up; CI enforces backend ≥ 75 % coverage gate. |

---

## 12. Effort summary

| Group | Surfaces | Est. effort | Cumulative |
|---|---|---|---|
| A | 4 | ½ day | ½ day |
| B | 3 | 1–2 days | 2½ days |
| C | 1 (3 dialogs) | 1–2 days | 4½ days |
| D | 5 | 1–2 weeks | 2½ weeks |
| E | 2 | 2–3 days | 3 weeks |
| F | 1 (BOM master-detail) | 4–5 days | 3½ weeks |
| G | 2 | 3–4 days | 4 weeks |
| H | 3 | 1.5–3 weeks | 5.5–7 weeks |
| I | continuous | — | — |

**Total Phase 2 effort estimate: 5.5–7 working weeks**, single-engineer, sequenced one surface at a time per spec § "Phase 2 — Sequencing rule". Phase 3 enforcement work adds ~1 day on top of Group I.

---

## 13. Approval gate

Per spec § "Phase 1 — Migration plan: Spec owner reviews and approves the plan before any migrations begin."

This document is ready for that review. On approval, Phase 2 starts with Group A.

---

*End of Phase 1 migration plan.*
