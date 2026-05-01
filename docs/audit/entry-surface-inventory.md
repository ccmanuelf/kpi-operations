# Entry Surface Inventory — Phase 0

**Project:** kpi-operations
**Date:** 2026-05-01
**Status:** Phase 0 — Inventory complete, spec-owner decisions applied 2026-05-01. Cleared for Phase 1.
**Source spec:** `/Users/mcampos.cerda/Downloads/06_kpi-operations_entry_interface_audit.md`

This inventory enumerates every user-facing data-entry surface in the frontend and maps each to its backend mutation endpoint(s) and current UI pattern (Grid / Form / Mixed / Other). Compliance is judged against the Spreadsheet Standard described in the spec: AG Grid Community + range selection, fill handle, clipboard paste, Excel keyboard nav, typed cell editors, validation, add/delete row buttons, CSV import/export round-trip.

---

## 1.1 Spec-Owner Resolutions (2026-05-01)

The Phase 0 sweep surfaced three contradictions inside the source spec. Spec owner ruled as follows; these rulings amend the Spreadsheet Standard for this project. They will be carried into `docs/standards/entry-ui-standard.md` in Phase 3.

**R1. Forms disguised as tables are NOT compliant.**
`v-data-table` with per-cell `v-text-field` slots is not the canonical pattern. AG Grid (Community Edition) is the only compliant grid technology. Consequence: rows 19–24 (six Capacity-planner worksheet grids) reclassified from `Needs review` to `Non-compliant` and added to the migration list.

**R2. `enableRangeSelection` / `enableFillHandle` requirement softened.**
Both flags are AG Grid Enterprise features. Project remains on Community. Resolution: build a custom subset of cell-range selection and fill-handle behaviour where Community APIs allow (option c); fall back to dropping the requirement for surfaces where Community cannot deliver it (option b). Both paths get documented so a future Enterprise license decision is unblocked. The Standard text becomes: "Cell-range selection and fill-handle behaviour SHOULD be provided to the user through Community-feasible custom implementation. Native `enableRangeSelection` / `enableFillHandle` flags MUST NOT be enabled — they are inert under Community license."

**R3. Custom clipboard paste is canonical; native `processDataFromClipboard` is NOT required.**
The existing `handlePasteFromExcel()` pipeline in `useAGGridBase.ts:219-304` is in production behind 8 grids, has clipboard parsing schemas in `utils/clipboardParser.ts`, and is actively maintained. Working feature wins. The Standard text becomes: "Excel paste-in MUST be supported. Implementation MAY use AG Grid's native `processDataFromClipboard` OR an equivalent `navigator.clipboard` pipeline (the project's `useAGGridBase.handlePasteFromExcel`). Whatever path is chosen, paste MUST round-trip with Excel and validate per-column."

**Open question carried into Phase 1:** row 56 (`DataEntryGrid.vue`) — alive or dead code? Verification is the first task of Group I (cleanup) in the migration plan.

---

## 1.2 Runtime Validation Update (2026-05-01)

**Trigger:** while starting Phase 2 / Group A, a runtime check on `QualityEntryGrid` showed its save payload does not match the backend Pydantic schema. A focused validation pass was run on all 4 Group A surfaces. Findings are documented in `docs/audit/group-a-runtime-validation.md`.

**Headline:** the Phase 0 "Compliant" classification was based on UI-shell criteria (gridOptions config, paste pipeline, typed editors). It did **not** verify that save payloads round-trip with the backend. Under runtime validation, **all 4 Group A grids are payload-divergent** — none currently sends `client_id`; field renames and value mappings are needed before any of them can save successfully.

**Cross-cutting consequences:**

- The "Compliant" badge on rows 4 (`QualityEntryGrid`), 6 (`AttendanceEntryGrid`), 8 (`DowntimeEntryGrid`), 10 (`HoldEntryGrid`) is amended to **"UI-compliant; payload-divergent"**. They still satisfy the visual/interaction Spreadsheet Standard; the save path needs fixing as part of their migration.
- The corresponding form variants (rows 3, 5, 7, 9) are equally broken at the JSON boundary — both layers were built before the backend schemas were finalized. So the migration is *fix the grid's payload*, not *preserve the form's payload*.
- `frontend/src/utils/clipboardParser.ts` entry schemas: `quality` is correctly aligned to backend; `attendance` and `downtime` are stale (field-name drift); `hold` is mostly aligned with one extra non-backend field. clipboardParser edits are part of each migration.
- `dataEntry.ts:34` calls `/holds/{id}/resume` — **endpoint does not exist** on the backend (resume workflow is `request-resume` → `approve-resume`). Fix as part of Holds migration.
- Group B (workflow wizard step embeds, plan rows 5–7) does **not** inherit Group A's payload code — wizard steps have their own ad-hoc payloads against potentially nonexistent endpoints (`PATCH /downtime/{id}/resolve`, `POST /production-entries`, `WorkflowStepAttendance` doesn't persist at all). Group B requires its own runtime-validation pre-task before any embedding work.

**Effort impact (carried into migration plan):** Group A revised from "~½ day" → "2–4 days". Per-surface effort revised XS → **M (4–16 hours)**. Recommended ordering inside Group A: simplest-payload-first (Quality → Holds → Attendance → Downtime).

---

## 2. Methodology

The five techniques specified in the audit prompt were applied in full.

### 2.1 Route enumeration
- File read: `/Users/mcampos.cerda/Documents/Programming/kpi-operations/frontend/src/router/index.ts` (single `.ts` router; no `.js` variant exists).
- 31 named routes plus 1 alias redirect (`/simulation-v2 → /simulation`) and 1 unauthenticated route (`/login`). Every route in the file points at a view component under `frontend/src/views/` or `frontend/src/components/entries/`. Role-based landing logic (`operator → /my-shift`, `leader → /`, `poweruser → /capacity-planning`, `admin → /kpi-dashboard`) was confirmed in `router/index.ts:251-258`.
- All 31 authenticated routes map into the inventory below; 11 admin-only routes are flagged via `meta.requiresAdmin`.

### 2.2 View component scan
- Glob: `frontend/src/views/**/*.vue` → 49 files. Glob: `frontend/src/components/**/*.vue` → 87 files.
- Confirmed `frontend/src/components/entries/` exists with 4 files (all are form-style entries, all are routed directly): `AttendanceEntry.vue`, `DowntimeEntry.vue`, `HoldResumeEntry.vue`, `QualityEntry.vue`.
- The reference grids cited in the spec (`ProductionLinesGrid.vue`, `OrdersGrid.vue`, `ProductionStandardsGrid.vue`) live at `frontend/src/views/CapacityPlanning/components/grids/` not `views/CapacityPlanning/` directly. **Important finding:** these reference "compliant" grids are NOT AG Grid. They are `v-data-table` with per-cell `v-text-field` slots. The actual AG Grid components live in `frontend/src/components/grids/` (production, quality, attendance, downtime, hold). Treated below as **Needs review** — the spec author must clarify which is the canonical compliant pattern.

### 2.3 Form-element search
- Grep pattern: `v-text-field|v-textarea|v-select|v-autocomplete|v-radio-group|v-checkbox|v-form\b` over `frontend/src/` → **86 files** matched.
- After excluding test files (`__tests__`, `.spec.ts`, `.test.ts`, `setup.ts`), CSS (`responsive.css`), pure read-only filter rows on KPI dashboards, and grid-internal slot usage in already-AG-Grid components, ~50 files contain user-facing form inputs that drive a mutation.

### 2.4 Mutation endpoint cross-reference
- Grep pattern: `router\.(post|put|patch)` over `backend/routes/` → **190 mutation endpoints across 41 router files** (top-level + sub-packages capacity, alerts, quality, reports, simulation).
- Each endpoint was traced to its frontend caller via `frontend/src/services/api/*.ts` (24 service files) and the Pinia stores in `frontend/src/stores/` (22 store files). Endpoints with no frontend caller (e.g. internal-only seeding, password-reset link generation, cache clear) are noted but excluded from "entry surface" since they are not user-facing.
- Auth endpoints (`/auth/*`) are exempt per Spec Exception 1; calculation/orchestration endpoints (e.g. `/dual-view-calculate/*`, `/simulation/run`, `/alerts/generate/*`, `/workflow/.../transition`) are not data-entry endpoints — they consume already-saved data and are excluded. They're tagged "Other (orchestration)" where they appear via a button in a UI surface.

### 2.5 AG Grid presence check
- Grep pattern: `AgGridVue|ag-grid|gridOptions|AGGridBase` → 24 files (excluding tests, css, main.ts).
- Authoritative AG Grid implementations:
  - `frontend/src/components/grids/AGGridBase.vue` — the wrapper, pulls in `useAGGridBase` composable.
  - `frontend/src/components/grids/{Production,Quality,Attendance,Downtime,Hold}EntryGrid.vue` — 5 entry grids.
  - `frontend/src/components/simulation/{Operations,Demand,Breakdowns}Grid.vue` — 3 simulation grids using `AgGridVue` directly.
- Verification of Spreadsheet Standard items per surface:
  - **Typed cell editors** (`agNumberCellEditor`, `agDateStringCellEditor`, `agSelectCellEditor`, `agTextCellEditor`, `agLargeTextCellEditor`, `agCheckboxCellEditor`) — confirmed in `useProductionGridData.ts:189-279`, `useQualityGridData.ts:176-322`, `useDowntimeGridData.ts:199-294`, `OperationsGrid.vue:175-253`, `BreakdownsGrid.vue:151-159`, `DemandGrid.vue:152-187`.
  - **Excel keyboard nav** — `enterMovesDownAfterEdit`, `enterNavigatesVertically`, `navigateToNextCell` (Tab/Enter handling) confirmed in `AGGridBase.vue:32-34` and `useAGGridBase.ts:149-168`.
  - **Clipboard paste** — implemented via custom `handlePasteFromExcel()` in `useAGGridBase.ts:219-304` reading `navigator.clipboard` and parsing through `utils/clipboardParser.ts` (custom; **not** native AG Grid `processDataFromClipboard`).
  - **enableRangeSelection / enableFillHandle** — declared as a prop in `AGGridBase.vue:90` but never wired into `mergedGridOptions` (`useAGGridBase.ts:133-175`). These are AG Grid Enterprise features; the project uses Community, so they cannot work. The spec text says "AG Grid Community + ALL of: enableRangeSelection, enableFillHandle..." which is internally inconsistent — these flags are Enterprise-only. Flagged as **Needs review**.
  - **Add/delete row buttons** — present in every grid (`addRow`/`removeRow`/`saveAll` toolbar buttons).
  - **CSV import/export** — every entry grid pairs with a `CSVUploadDialog*.vue` and the AG Grid `exportDataAsCsv` is exposed in `AGGridBase.vue:154`.
  - **Per-cell validation with visual flagging** — partial: cell change flash via `enableCellChangeFlash` (`useAGGridBase.ts:121`) and inline-edit highlight via CSS `.ag-cell-inline-editing` (`AGGridBase.vue:188-191`). True per-cell validation rules (cellClassRules / valueParser failures) are inconsistent — some grids have them, others don't.

### 2.6 Borderline cases ruled out (read-only display, not entry)
- All `frontend/src/views/kpi/*.vue` (8 files) — KPI dashboards with date/client filter inputs only; no mutation calls. Filter inputs fall under Spec Exception 3.
- `KPIDashboard.vue`, `DashboardView.vue`, `MyShiftDashboard.vue` (parent shell), `AlertsView.vue`, `PlanVsActualView.vue`, `AssumptionVarianceReport.vue` — display dashboards. Filter `v-text-field`/`v-select` inputs are not entry surfaces.
- `frontend/src/components/dashboard/`, `frontend/src/components/widgets/`, `frontend/src/components/alerts/{AlertCard,AbsenteeismAlert,AlertDashboard,AlertGuideDialog}.vue`, `frontend/src/components/simulation/{ResultsView,ValidationPanel,SimulationGuideDialog}.vue`, `WorkflowMermaidPanel.vue`, `KeyboardShortcutsHelp.vue`, `OnboardingChecklist.vue`, `LanguageToggle.vue`, `DarkModeToggle.vue`, `QRCodeScanner.vue` (read-only or non-data-entry UX).
- `frontend/src/components/dialogs/{ReadBackConfirmation,PastePreviewDialog}.vue` — internal dialogs invoked by other entry surfaces, no direct mutation. Not standalone surfaces.
- `frontend/src/components/admin/MigrationProgress.vue` — progress display only.

---

## 3. Primary Inventory Table

| # | Surface name | File path | Route or trigger | Data domain | Backend endpoint(s) | Current pattern | Compliance status | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Login | `frontend/src/views/LoginView.vue` | `/login` | Auth (username, password) + registration | `POST /auth/login`, `POST /auth/register`, `POST /auth/forgot-password` | Form | **Exception** | Spec Exception 1 (Login/auth). `v-form` at `LoginView.vue:12,132`. |
| 2 | Production Entry | `frontend/src/views/ProductionEntry.vue` → `frontend/src/components/grids/ProductionEntryGrid.vue` | `/production-entry` | Production runs (units, runtime, defects) | `POST /production`, `PUT /production/{id}`, `POST /production/upload/csv`, `POST /production/batch-import` | Grid | **Compliant** | Verified in `useProductionGridData.ts`: typed editors `agDateStringCellEditor`/`agSelectCellEditor`/`agNumberCellEditor` (lines 189, 201, 213, 232, 245, 258, 267, 278); paste via `useAGGridBase.ts:219`; CSV import via `CSVUploadDialogProduction`; export via `AGGridBase.vue:154`; add row + save toolbar in `ProductionEntryGrid.vue:90`. **Missing:** native AG Grid range/fill (Enterprise); per-cell `cellClassRules` validation (only `enableCellChangeFlash`). |
| 3 | ~~Quality Entry (form)~~ | ~~`frontend/src/components/entries/QualityEntry.vue`~~ | (deleted) | Quality inspections | — | — | **MIGRATED 2026-05-01** — file deleted; route now points to grid (row 4) via wrapper view `frontend/src/views/QualityEntry.vue`. |
| 4 | Quality Entry (grid) | `frontend/src/components/grids/QualityEntryGrid.vue` (mounted via `frontend/src/views/QualityEntry.vue`) | `/data-entry/quality` | Quality inspections | `POST /quality`, `PUT /quality/{id}` | Grid | **Compliant** (migrated 2026-05-01) | Wrapper view `views/QualityEntry.vue` adds `CSVUploadDialogQuality` header + `<QualityEntryGrid />`. Composable `useQualityGridData.ts` reconciled to backend Pydantic schema: payload now sends `client_id` (from auth/kpi store), `shift_date`, `units_inspected`, `units_passed` (computed), `units_defective`, `total_defects_count`, `notes`. Dropped vestigial UI fields (product_id, defect_type_id, severity, disposition, inspector_id). Tests in `useQualityGridData.spec.ts` (31 tests). See `docs/views/quality-entry.md`. |
| 5 | ~~Attendance Entry (form)~~ | ~~`frontend/src/components/entries/AttendanceEntry.vue`~~ | (deleted) | Attendance | — | — | **MIGRATED 2026-05-01** — file deleted; route now points to grid (row 6) via wrapper view `frontend/src/views/AttendanceEntry.vue`. |
| 6 | Attendance Entry (grid) | `frontend/src/components/grids/AttendanceEntryGrid.vue` (mounted via `frontend/src/views/AttendanceEntry.vue`) | `/data-entry/attendance` | Attendance | `POST /attendance`, `PUT /attendance/{id}`, `POST /attendance/bulk`, `POST /attendance/mark-all-present` | Grid | **Compliant** (migrated 2026-05-01) | Wrapper view adds `CSVUploadDialogAttendance` header + `<AttendanceEntryGrid />`. Composable `useAttendanceGridData.ts` reconciled to backend Pydantic schema: payload sends `client_id` (auth/kpi store), `employee_id`, `shift_date`, `shift_id`, `scheduled_hours`, `actual_hours`, `absence_hours`, `is_absent`, `absence_type` enum, `arrival_time`/`departure_time` (ISO datetimes built from clock_in/clock_out HH:MM + shift_date), `is_late`. Status string translated via `translateStatus()` helper; status set adds Vacation/Medical (matching backend AbsenceTypeEnum). Vestigial UI fields dropped (`late_minutes`, `is_excused`). clipboardParser entry renamed `attendance_date` → `shift_date`, `worked_hours` → `actual_hours`. Tests in `useAttendanceGridData.spec.ts` (30 tests). See `docs/views/attendance-entry.md`. |
| 7 | ~~Downtime Entry (form)~~ | ~~`frontend/src/components/entries/DowntimeEntry.vue`~~ | (deleted) | Downtime events | — | — | **MIGRATED 2026-05-01** — file deleted; route now points to grid (row 8) via wrapper view `frontend/src/views/DowntimeEntry.vue`. |
| 8 | Downtime Entry (grid) | `frontend/src/components/grids/DowntimeEntryGrid.vue` (mounted via `frontend/src/views/DowntimeEntry.vue`) | `/data-entry/downtime` | Downtime events | `POST /downtime`, `PUT /downtime/{id}` | Grid | **Compliant** (migrated 2026-05-01) | Wrapper view adds `CSVUploadDialogDowntime` header + `<DowntimeEntryGrid />`. Composable `useDowntimeGridData.ts` reconciled to backend Pydantic schema: payload sends `client_id` (auth/kpi store), `shift_date`, `downtime_reason` (catalog code), `downtime_duration_minutes` (1–1440), `work_order_id`, `line_id`, `machine_id`, `equipment_code`, `root_cause_category`, `corrective_action`, `notes`. Replaces legacy UI categories (`'Planned Maintenance'`, `'Unplanned Breakdown'`, etc.) with canonical `DOWNTIME_REASON_CODES` (7 codes: EQUIPMENT_FAILURE, MATERIAL_SHORTAGE, SETUP_CHANGEOVER, QUALITY_HOLD, MAINTENANCE, POWER_OUTAGE, OTHER). Drops vestigial UI fields (`downtime_start_time`, `category`, `impact_on_wip_hours`, `is_resolved`, `resolution_notes`, `duration_hours`). Adds new fields (`machine_id`, `equipment_code`, `root_cause_category`, `corrective_action`). clipboardParser entry renamed `downtime_minutes` → `downtime_duration_minutes` and adds reason field. Tests in `useDowntimeGridData.spec.ts` (25 tests). See `docs/views/downtime-entry.md`. |
| 9 | ~~Hold/Resume Entry (form)~~ | ~~`frontend/src/components/entries/HoldResumeEntry.vue`~~ | (deleted) | WIP holds | — | — | **MIGRATED 2026-05-01** — file deleted (and its composable `useHoldResumeData.ts`); route now points to grid (row 10) via wrapper view `frontend/src/views/HoldResumeEntry.vue`. The dead `POST /holds/{id}/resume` URL also removed from `services/api/dataEntry.ts`. |
| 10 | Hold/Resume Entry (grid) | `frontend/src/components/grids/HoldEntryGrid.vue` (mounted via `frontend/src/views/HoldResumeEntry.vue`) | `/data-entry/hold-resume` | WIP holds | `POST /holds`, `PUT /holds/{id}`, `POST /holds/{id}/approve-hold`, `POST /holds/{id}/request-resume`, `POST /holds/{id}/approve-resume` | Grid | **Compliant** (migrated 2026-05-01) | Composables `useHoldGridData.ts` + `useHoldGridForms.ts` reconciled to backend Pydantic schema: payload sends `client_id` (from auth/kpi store), `work_order_id`, `hold_date`, `hold_reason` (catalog code), `hold_reason_description`, `expected_resolution_date`, `notes`. Server-controlled fields dropped from Create payload (resume_date, hold_initiated_by, hold_approved_by, resumed_by). Reason values use canonical HOLD_REASON_CATALOG codes (8 codes: QUALITY_ISSUE, MATERIAL_INSPECTION, ENGINEERING_REVIEW, CUSTOMER_REQUEST, MISSING_SPECIFICATION, EQUIPMENT_UNAVAILABLE, CAPACITY_CONSTRAINT, OTHER). Vestigial resume dialog removed; approval-workflow buttons (approve-hold, request-resume, approve-resume) are the canonical resume path. Tests in `useHoldGridData.spec.ts` (31 tests). See `docs/views/hold-entry.md`. |
| 11 | Work Order Management | `frontend/src/views/WorkOrderManagement.vue` | `/work-orders` | Work orders (CRUD, QC approval, capacity link) | `POST /work-orders`, `PUT /work-orders/{id}`, `PATCH /work-orders/{id}/status`, `POST /work-orders/{id}/approve-qc`, `POST /work-orders/{id}/link-capacity`, `POST /work-orders/{id}/unlink-capacity` | Mixed | **Non-compliant** | Display = `v-data-table` (read-only listing). Create/edit = `v-dialog`+`v-form` at line 248-330 with 12 `v-text-field`/`v-select`/`v-textarea`. **Missing:** all Spreadsheet items in the create/edit path. The list view itself is fine; the entry dialog must become a grid. |
| 12 | My Shift Dashboard | `frontend/src/views/MyShiftDashboard.vue` (uses `frontend/src/components/dialogs/ShiftDashboardDialogs.vue`) | `/my-shift` | Quick production / downtime / quality entries during a shift | `POST /production`, `POST /downtime`, `POST /defect-details` (and shift start/end via `/shifts`) | Mixed | **Non-compliant** | Parent dashboard is fine. The 4 modal `v-dialog` entries in `ShiftDashboardDialogs.vue` (Production lines 3-53, Downtime 56-108, Quality 111-165, Help 168-203) are single-row forms. **Missing:** all Spreadsheet items. Could be redirected to existing AG Grids for unified UX, or kept as Exception 4 (quick action) — needs spec-owner ruling: see Section 2.6 below. |
| 13 | Alerts View | `frontend/src/views/AlertsView.vue` (+ `frontend/src/components/alerts/AlertResolveDialog.vue`) | `/alerts` | Alert resolution / acknowledgment | `POST /alerts/{id}/acknowledge`, `POST /alerts/{id}/resolve`, `POST /alerts/{id}/dismiss`, `POST /alerts` | Form | **Exception** | Spec Exception 4 (confirmation/approval). `AlertResolveDialog.vue:1-20` is a textarea-only resolve-with-notes confirmation flow. Acknowledge/dismiss are zero-input button actions. |
| 14 | Simulation V2 — Operations | `frontend/src/components/simulation/OperationsGrid.vue` | `/simulation` (tabbed inside `SimulationV2View.vue`) | Manufacturing process operations (SAM, operators, FPD%) | (client-side store; persisted via `POST /simulation-v2/run`) | Grid | **Compliant** | Verified `agTextCellEditor`/`agNumberCellEditor`/`agSelectCellEditor` at `OperationsGrid.vue:175-253`; `singleClickEdit`, `enterNavigatesVertically`, `undoRedoCellEditing` in `gridOptions` at line 142-149. CSV import via paste-textarea dialog (line 76-104). **Missing:** native AG Grid `processDataFromClipboard` — uses bespoke CSV-paste textarea instead of the AGGridBase paste-from-clipboard pipeline. Not as polished as entry grids. |
| 15 | Simulation V2 — Demand | `frontend/src/components/simulation/DemandGrid.vue` | `/simulation` | Demand schedule per product/period | `POST /simulation-v2/run` (client-side store) | Grid | **Compliant** | Typed editors at `DemandGrid.vue:152-187`. Same caveats as #14. |
| 16 | Simulation V2 — Breakdowns | `frontend/src/components/simulation/BreakdownsGrid.vue` | `/simulation` | Equipment breakdown profiles | `POST /simulation-v2/run` (client-side store) | Grid | **Compliant** | Typed editors at `BreakdownsGrid.vue:151-159`. Same caveats as #14. |
| 17 | Simulation V2 — Schedule | `frontend/src/components/simulation/ScheduleForm.vue` | `/simulation` | Simulation schedule parameters (horizon, working hours, break time, target eff) | `POST /simulation-v2/validate`, `POST /simulation-v2/run` | Form | **Exception** | Spec Exception 3 (parameter dialog). 6 numeric `v-text-field`s at lines 34, 47, 60, 109, 122, 134 — these are simulation run parameters, not data entries. |
| 18 | Capacity Planning Workbook | `frontend/src/views/CapacityPlanning/CapacityPlanningView.vue` | `/capacity-planning` | Container for 13-tab workbook | (delegates to child grids/panels) | Other (container) | **N/A** | Tab orchestration only; no direct mutation. See rows 19-29. |
| 19 | Capacity — Production Lines (worksheet grid) | `frontend/src/views/CapacityPlanning/components/grids/ProductionLinesGrid.vue` | tab inside `/capacity-planning` | Production line definitions (worksheet) | Persisted via `useCapacityPlanningStore` save (`PUT capacity/.../{id}`) and direct CRUD `POST /capacity/lines`, `PUT /capacity/lines/{id}` (`backend/routes/capacity/lines.py:49,92`) | Grid (v-data-table) | **Non-compliant** (per R1) | `v-data-table` + per-cell `v-text-field` (lines 22-92). Per spec-owner R1: forms-disguised-as-tables are not compliant. Migrate to AG Grid using `AGGridBase` pattern. **Missing:** all Spreadsheet Standard items. |
| 20 | Capacity — Orders (worksheet grid) | `frontend/src/views/CapacityPlanning/components/grids/OrdersGrid.vue` | tab inside `/capacity-planning` | Customer orders for capacity scheduling | `POST /capacity/orders`, `PUT /capacity/orders/{id}`, `PATCH /capacity/orders/{id}` | Grid (v-data-table) | **Non-compliant** (per R1) | Same pattern as row 19. CSV import is a `v-textarea` paste in a dialog (line 121-139) — replace with AG Grid native paste. |
| 21 | Capacity — Standards (worksheet grid) | `frontend/src/views/CapacityPlanning/components/grids/StandardsGrid.vue` | tab inside `/capacity-planning` | Production standards | `POST /capacity/standards`, `PUT /capacity/standards/{id}` | Grid (v-data-table) | **Non-compliant** (per R1) | Same pattern as row 19. Migrate to AG Grid. |
| 22 | Capacity — Calendar grid | `frontend/src/views/CapacityPlanning/components/grids/CalendarGrid.vue` | tab inside `/capacity-planning` | Calendar / shift availability per date | `POST /capacity/calendar`, `PUT /capacity/calendar/{id}` | Grid (v-data-table) | **Non-compliant** (per R1) | Same pattern as row 19. Migrate to AG Grid; consider date-pinned column structure. |
| 23 | Capacity — BOM grid | `frontend/src/views/CapacityPlanning/components/grids/BOMGrid.vue` | tab inside `/capacity-planning` | Bill of materials | `POST /capacity/bom`, `PUT /capacity/bom/{id}`, `POST /capacity/bom/{id}/components`, `PUT /capacity/bom/{id}/components/{cid}` | Grid (v-data-table) | **Non-compliant** (per R1) | Same pattern. Migrate to AG Grid. Component-level mutations (orphaned endpoints, see 6.7) should be folded into a master-detail grid in this migration. |
| 24 | Capacity — Stock grid | `frontend/src/views/CapacityPlanning/components/grids/StockGrid.vue` | tab inside `/capacity-planning` | Component stock snapshots | `POST /capacity/stock`, `PUT /capacity/stock/{id}` | Grid (v-data-table) | **Non-compliant** (per R1) | Same pattern as row 19. Migrate to AG Grid. |
| 25 | Capacity — Dashboard Inputs panel | `frontend/src/views/CapacityPlanning/components/panels/DashboardInputsPanel.vue` | tab inside `/capacity-planning` | Workbook-level config (planning horizon, alert thresholds, default eff) | `useCapacityPlanningStore` save (eventually persists to `/capacity/...`) | Form | **Exception** | Spec Exception 2 (admin config, scoped to a single workbook owner). 4 `v-text-field`/slider inputs (lines 21-60). |
| 26 | Capacity — Schedule panel | `frontend/src/views/CapacityPlanning/components/panels/SchedulePanel.vue` | tab inside `/capacity-planning` | Schedule date-range filter + commit dialog | `POST /capacity/schedules`, `POST /capacity/scenarios`, `POST /capacity/scenarios/{id}/...` | Mixed | **Exception** | Spec Exception 3 (filter/parameter inputs at lines 148-164) + Exception 4 (commit confirmation in `ScheduleCommitDialog.vue`). Schedule commit is an action with notes; not free-form data entry. |
| 27 | Capacity — Capacity Analysis panel | `frontend/src/views/CapacityPlanning/components/panels/CapacityAnalysisPanel.vue` | tab inside `/capacity-planning` | Analysis filter inputs + run analysis | `POST /capacity/analysis/...` | Form (parameters) | **Exception** | Spec Exception 3. Inputs at lines 147, 155 are analysis parameters. |
| 28 | Capacity — KPI Tracking panel | `frontend/src/views/CapacityPlanning/components/panels/KPITrackingPanel.vue` | tab inside `/capacity-planning` | KPI threshold edits + workbook save | `PUT /capacity/kpi-workbook/...`, `PUT /kpi/thresholds` | Mixed | **Non-compliant** | Threshold-edit `v-text-field`/`v-select` at lines 75, 85, 165 are real data entries. **Missing:** Spreadsheet Standard items. Could be folded into a thresholds grid. |
| 29 | Capacity — Component Check panel | `frontend/src/views/CapacityPlanning/components/panels/ComponentCheckPanel.vue` | tab inside `/capacity-planning` | Component shortage report + override values | `POST /capacity/analysis/...` (override flow) | Mixed | **Exception** | Spec Exception 3 (filter inputs at lines 65, 108 are query parameters; results shown read-only). |
| 30 | Capacity — Scenarios panel | `frontend/src/views/CapacityPlanning/components/panels/ScenariosPanel.vue` | tab inside `/capacity-planning` | Scenario creation (what-if) | `POST /capacity/scenarios`, `POST /capacity/scenarios/...` | Form (dialog) | **Non-compliant** | `v-dialog` at line 156 with 16+ `v-text-field`/`v-select` inputs (lines 160-282). Each scenario is a standalone parameterized record. Could be a grid (one row per scenario). **Missing:** all Spreadsheet items. |
| 31 | Admin — Settings | `frontend/src/views/admin/AdminSettings.vue` | `/admin/settings` | System settings, KPI thresholds, email config | `PUT /kpi/thresholds`, `PUT /email-config`, etc. | Form | **Exception** | Spec Exception 2 (admin config). Two `v-form`s (lines 21, 105). |
| 32 | Admin — Users | `frontend/src/views/admin/AdminUsers.vue` | `/admin/users` | User accounts (CRUD) | `POST /users`, `PUT /users/{id}` | Form (dialog) | **Exception** | Spec Exception 2 (user provisioning). `v-form` in `v-dialog` at line 108. Project users count expected <5 in normal demo (admin/leader/poweruser/operator); fits the <5 rule. |
| 33 | Admin — Clients | `frontend/src/views/admin/AdminClients.vue` | `/admin/clients` | Tenant client records | `POST /clients`, `PUT /clients/{id}` | Form (dialog) | **Exception** | Spec Exception 2 (tenant config). 6 `v-text-field`s in dialog (lines 97-146). 5 demo clients per project memory; well under "few users" threshold. |
| 34 | Admin — Defect Types | `frontend/src/views/admin/AdminDefectTypes.vue` | `/admin/defect-types` | Per-client defect catalog | `POST /defect-type-catalog`, `PUT /defect-type-catalog/{id}`, `POST /defect-type-catalog/upload/{client_id}` | Mixed | **Non-compliant** | List uses `v-data-table`. Edit dialog (line 161) is `v-form` with 4 `v-text-field`s. CSV upload exists via a separate dialog. The catalog can grow large (per-client × many defect types), so a grid is appropriate. **Missing:** all Spreadsheet items in the create/edit path. |
| 35 | Admin — Part Opportunities | `frontend/src/views/admin/PartOpportunities.vue` | `/admin/part-opportunities` | Per-part opportunity classification | `POST /part-opportunities`, `PUT /part-opportunities/{part_number}`, `POST /part-opportunities/bulk-import` | Mixed | **Non-compliant** | Same shape as #34: `v-data-table` + edit dialog (line 196) with `v-text-field`/`v-select` (lines 206-281), plus bulk-import dialog. Per-part records are spreadsheet-natural. **Missing:** all Spreadsheet items in edit path. |
| 36 | Admin — Client Config | `frontend/src/views/admin/ClientConfigView.vue` | `/admin/client-config` | Per-client configuration overrides | `POST /client-config`, `PUT /client-config/{client_id}`, `POST /client-config/{client_id}/reset-to-defaults` | Form (dialog) | **Exception** | Spec Exception 2. Edit dialog at line 137; configures one client at a time. |
| 37 | Admin — Floating Pool | `frontend/src/views/admin/FloatingPoolManagement.vue` | `/admin/floating-pool` | Floating-pool employee assignment, simulation | `POST /floating-pool`, `PUT /floating-pool/{id}`, `POST /floating-pool/assign`, `POST /floating-pool/unassign`, `POST /employees/{id}/floating-pool/assign`, etc. | Mixed | **Non-compliant** | Filter selects (lines 161, 172) and assign-dialog `v-select`/`v-text-field` (lines 287-319) drive real assignment writes. Pool can have many employees. **Missing:** all Spreadsheet items in the assignment path. |
| 38 | Admin — Workflow Config | `frontend/src/views/admin/WorkflowConfigView.vue` | `/admin/workflow-config` | Per-client workflow configuration | `PUT /workflow/config/{client_id}`, `POST /workflow/config/{client_id}/apply-template` | Form (dialog) | **Exception** | Spec Exception 2 (admin config). Edit dialog at line 246 + template-apply confirm at 373. |
| 39 | Admin — Workflow Designer | `frontend/src/views/admin/WorkflowDesignerView.vue` | `/admin/workflow-designer/:clientId?` | Visual workflow state-machine designer | `PUT /workflow/config/{client_id}` | Other (canvas editor) | **Exception** | No `v-form`/`v-text-field` at the view level (visual node-edge editor via `WorkflowDesigner.vue`). Spec Exception 2 (admin config). |
| 40 | Admin — Database Config | `frontend/src/views/admin/DatabaseConfigView.vue` (uses `frontend/src/components/admin/MigrationWizard.vue`) | `/admin/database` | DB connection test, migration | `POST /database-config/test-connection`, `POST /database-config/migrate` | Form (wizard) | **Exception** | Spec Exception 2 (system settings). Wizard `v-text-field`s at `MigrationWizard.vue:34, 115`. |
| 41 | Admin — Variance Report | `frontend/src/views/admin/AssumptionVarianceReport.vue` | `/admin/variance-report` | Read-only variance report | (none — read) | Other (read-only) | **N/A** | No mutation endpoints. Excluded as not an entry surface. |
| 42 | Calculation Assumptions (admin embed) | drawn into Plan-vs-Actual / Capacity? entry surface unclear | (no dedicated route; called from Capacity context) | Calculation assumptions create/approve/retire | `POST /calculation-assumptions`, `PATCH /calculation-assumptions/{id}`, `POST /calculation-assumptions/{id}/approve`, `POST /calculation-assumptions/{id}/retire` | Other | **Deferred — dual-view spec #1** | Backend endpoints exist; UI surface to be designed in dual-view spec #1 (assumption registry). Per the source spec § "Coordination with the dual-view architecture work", any UI introduced there must follow the Spreadsheet Standard. Not a Phase 2 migration target — handled when dual-view spec reaches that phase. |
| 43 | Workflow Wizard — Production step | `frontend/src/components/workflow/steps/WorkflowStepProduction.vue` | Inside guided shift wizard (shift-end) | Production data review (read-only) | `GET /production` (read-only) | Other (read-only checkpoint) | **Compliant** (migrated 2026-05-01, option c) | Per Group B Phase 0: previous step targeted nonexistent `POST /production-entries` and `GET /work-orders/shift-production`; was structurally un-completable. Now refactored to a read-only checkpoint that fetches `GET /production?start_date=today&end_date=today&client_id=<auth>`, aggregates entries by `work_order_id` (entry count + units_produced + defect_count), gates wizard advance on "≥1 entry exists for the shift", and links out to `/production-entry` (Group A grid) for entry creation. Wired `useNotificationStore` for fetch errors. Mock-fixture fallback removed. Tests in `WorkflowStepProduction.spec.ts` (10 tests). |
| 44 | Workflow Wizard — Start Shift step | `frontend/src/components/workflow/steps/WorkflowStepStartShift.vue` | shift wizard | Shift start (operator, line, equipment) | `POST /shifts/`, `POST /shifts/.../start-shift` | Form | **Exception** | Spec Exception 4 (start-of-shift confirmation flow). Single-purpose start action. |
| 45 | Workflow Wizard — End Shift step | `frontend/src/components/workflow/steps/WorkflowStepEndShift.vue` | shift wizard | Shift end submission | `PUT /shifts/{id}` (close shift) | Form | **Exception** | Spec Exception 4. |
| 46 | Workflow Wizard — Targets step | `frontend/src/components/workflow/steps/WorkflowStepTargets.vue` | shift wizard | Hourly target overrides | `PUT /workflow/config/{client_id}` (or shift-scoped state) | Form | **Non-compliant** | `v-text-field` at line 130. **Missing:** all Spreadsheet items. A 24-hour target grid would be more natural. |
| 47 | Workflow Wizard — Equipment step | `frontend/src/components/workflow/steps/WorkflowStepEquipment.vue` | shift wizard | Equipment readiness checklist | (workflow state transitions) | Form | **Exception** | Spec Exception 4 (checklist confirmation). |
| 48 | Workflow Wizard — Downtime step | `frontend/src/components/workflow/steps/WorkflowStepDowntime.vue` | shift wizard | Downtime events during shift (review-only) | `GET /downtime` (read-only) | Other (read-only checkpoint) | **Compliant** (migrated 2026-05-01, option c) | Per Group B Phase 0: previous step targeted nonexistent `PATCH /downtime/{id}/resolve` and forged success on failure (data-integrity bug). Now refactored to a read-only checkpoint that fetches `GET /downtime?shift_date=today&client_id=<auth>`, classifies rows by presence/absence of `corrective_action`, gates wizard advance on `openCount === 0`, and links out to `/data-entry/downtime` (Group A grid) for resolution. Forged-success path removed. Wired `useNotificationStore` for fetch errors. Mock-fixture fallback removed. Tests in `WorkflowStepDowntime.spec.ts` (10 tests including a regression test that asserts no fake "resolved" state on fetch failure). |
| 49 | Workflow Wizard — Attendance step | `frontend/src/components/workflow/steps/WorkflowStepAttendance.vue` | shift wizard | Roll call | `POST /attendance/bulk`, `POST /attendance/mark-all-present` | Form | **Non-compliant** | `v-text-field`/`v-select` at lines 33, 125. Roster of N employees is grid-natural. **Missing:** all Spreadsheet items. |
| 50 | Workflow Wizard — Handoff step | `frontend/src/components/workflow/steps/WorkflowStepHandoff.vue` | shift wizard | Shift handoff notes | (workflow state) | Form | **Exception** | Spec Exception 4 (confirmation/handoff). One textarea (line 130). |
| 51 | Workflow Wizard — Previous Shift step | `frontend/src/components/workflow/steps/WorkflowStepPreviousShift.vue` | shift wizard | Display previous shift summary | (read) | Other (read-only) | **N/A** | No form inputs found in grep. |
| 52 | Workflow Wizard — Summary / Completeness | `frontend/src/components/workflow/steps/WorkflowStepSummary.vue`, `WorkflowStepCompleteness.vue` | shift wizard | Display + final confirmation | (workflow state transition) | Form (confirm) | **Exception** | Spec Exception 4. |
| 53 | Email Reports Dialog | `frontend/src/components/dialogs/EmailReportsDialog.vue` | global FAB / report screen | Email-report config (recipients, schedule) | `POST /email-config`, `PUT /email-config`, `POST /email-config/test`, `POST /email-config/send-manual` | Form | **Exception** | Spec Exception 2 (admin config — email recipients per tenant). 7 `v-text-field`/`v-select`s at lines 9-104. |
| 54 | Save Filter Dialog | `frontend/src/components/filters/SaveFilterDialog.vue` (used by `FilterBar.vue` / `FilterManager.vue`) | KPI screens | Saved filter definition | `POST /filters`, `PUT /filters/{id}`, `POST /filters/{id}/duplicate`, `POST /filters/{id}/set-default`, `POST /filters/{id}/unset-default` | Form (small) | **Exception** | Spec Exception 3 (filter parameter dialog). 1 `v-text-field` + 1 `v-select` at lines 16, 33. Saving a filter is a filter operation, not a data entry. |
| 55 | Filter Bar / Filter Manager | `frontend/src/components/filters/FilterBar.vue`, `FilterManager.vue` | KPI screens | Active filter state | `POST /filters/{id}/apply`, `POST /filters/history` | Form (filter inputs) | **Exception** | Spec Exception 3. |
| 56 | DataEntryGrid (legacy) | `frontend/src/components/DataEntryGrid.vue` | (no route) | (legacy) | unknown | Mixed | **Needs review** | Component file exists with form-style inputs. Grep matched it. **Spec-owner question:** is this dead code or in use? Confirm before classifying. |
| 57 | LineSelector | `frontend/src/components/common/LineSelector.vue` | global header / shift wizard | Production line selection | (no mutation — selector only) | Other | **Exception** | Spec Exception 3 (selector). |
| 58 | QR Code Scanner | `frontend/src/components/QRCodeScanner.vue` | wired into MyShift / production entry | Scan-to-enter for work-order ID etc. | `POST /qr/...` (2 endpoints in `qr.py:370, 456`) | Other (input device) | **Exception** | Spec Exception 4 (scan = single-action confirmation). |

**Total surfaces enumerated: 58.** Surfaces flagged `N/A` (rows 18, 41, 51) are not entry surfaces and are excluded from the summary count below.

---

## 4. Summary Table

| Status | Count |
|---|---|
| Total entry surfaces (excl. N/A containers) | 55 |
| Compliant | 9 |
| Non-compliant | 14 |
| Exception (permitted) | 24 |
| Needs review | 8 |

(Compliant = rows 2, 4, 6, 8, 10, 14, 15, 16. The Hold grid (10) is included; that's 8 — and #17 ScheduleForm is Exception not Compliant, so 8 confirmed grids. Recount: 2, 4, 6, 8, 10, 14, 15, 16 = 8. Plus production grid is row 2. Recheck inventory: rows tagged Compliant = 2, 4, 6, 8, 10, 14, 15, 16 → 8 surfaces. Previous count fixed below.)

Corrected:

| Status | Count |
|---|---|
| Total entry surfaces (excl. N/A) | 55 |
| Compliant | 8 |
| Non-compliant | 14 |
| Exception (permitted) | 25 |
| Needs review | 8 |

### Post-resolution (2026-05-01, after spec-owner R1–R3)

| Status | Count | Notes |
|---|---|---|
| Total entry surfaces (excl. N/A) | 55 | unchanged |
| Compliant | 8 | rows 2, 4, 6, 8, 10, 14, 15, 16 |
| Non-compliant | 20 | original 14 + 6 capacity v-data-table grids (rows 19–24) reclassified per R1 |
| Exception (permitted) | 25 | unchanged |
| Deferred — dual-view spec #1 | 1 | row 42 (Calculation Assumptions) |
| Verify before classification | 1 | row 56 (`DataEntryGrid.vue` alive/dead check) |

**Migration target count: 20 surfaces** (Phase 1 plan groups these into 9 execution batches.)

### Phase 2 progress (2026-05-01)

| Group | Surface | Status |
|---|---|---|
| A | Quality re-route (rows 3 → 4) | ✅ **Migrated** — payload reconciled, form deleted, route swapped, +7 tests |
| A | Holds re-route (rows 9 → 10) | ✅ **Migrated** — payload reconciled, dead `/resume` URL removed, vestigial resume dialog excised, form + form composable + form spec deleted, +2 tests |
| A | Attendance re-route (rows 5 → 6) | ✅ **Migrated** — payload reconciled (status enum translation + datetime conversion), form deleted, clipboardParser fixed, +30 tests |
| A | Downtime re-route (rows 7 → 8) | ✅ **Migrated** — payload reconciled (DOWNTIME_REASON_CODES catalog + hours→minutes unit conversion), 6 vestigial fields dropped, 4 new backend-aligned fields added, form + form spec deleted, clipboardParser fixed, +7 tests |

**Group A complete (4/4 surfaces).** Migration target count: **16 surfaces remaining** out of 20 total.

Next per the Phase 1 plan: **Group B Phase 0 — runtime validation of the 3 wizard step embeds** (`WorkflowStepProduction`, `WorkflowStepDowntime`, `WorkflowStepAttendance`). Per the migration plan §0.3 these have separate ad-hoc payloads; one calls a nonexistent `PATCH /downtime/{id}/resolve`, another (`WorkflowStepAttendance`) doesn't persist at all. A Group B runtime-validation pass is required before the embeds are migrated.

---

## 5. Permitted Exceptions

### Exception 1 — Login / Auth (1 surface)
- **Login** (row 1) — username, password, optional registration. `LoginView.vue`.

### Exception 2 — Admin config with <5 users (8 surfaces)
- **Admin Settings** (31) — system thresholds, single admin owner.
- **Admin Users** (32) — 5 demo users in seeding; user provisioning is admin-only.
- **Admin Clients** (33) — 5 demo clients; tenant config.
- **Admin Client Config** (36) — per-client overrides.
- **Admin Workflow Config** (38) — per-client workflow assignment.
- **Admin Workflow Designer** (39) — visual designer; not a form.
- **Admin Database Config / Migration Wizard** (40) — system bootstrap.
- **Email Reports Dialog** (53) — recipient list config.
- **Capacity Dashboard Inputs Panel** (25) — workbook-scoped owner config.

### Exception 3 — Search / filter / parameter dialogs (5 surfaces)
- **Schedule Form** (17) — simulation parameters.
- **Capacity Schedule panel** (26) — date-range filters.
- **Capacity Analysis panel** (27) — analysis parameters.
- **Capacity Component Check panel** (29) — query inputs only.
- **Save Filter Dialog** (54) and **Filter Bar / Manager** (55) — saved-filter management.
- **Line Selector** (57) — selector only.

### Exception 4 — Confirmation / approval / single-action dialogs (10 surfaces)
- **Alerts View** (13) — resolve/acknowledge/dismiss.
- **Workflow Start Shift** (44).
- **Workflow End Shift** (45).
- **Workflow Equipment** (47) — readiness checklist.
- **Workflow Handoff** (50) — handoff notes.
- **Workflow Summary / Completeness** (52) — final confirm.
- **QR Code Scanner** (58) — single-shot input device.
- **Capacity Schedule Commit dialog** (within row 26).

---

## 6. Cross-Cutting Observations

### 6.1 Form/Grid duplication for the four primary data domains
Production, Quality, Attendance, Downtime, and Hold each have BOTH a form-style entry under `frontend/src/components/entries/` AND a fully working AG Grid implementation under `frontend/src/components/grids/`. The router currently points the four `/data-entry/*` routes at the FORM versions while the GRID versions are functionally complete and registered nowhere. The single highest-leverage migration is therefore **switching 4 router lines** (`router/index.ts:89, 95, 101, 107`) to point at the existing grid components, then deleting `entries/` once verified.

### 6.2 Capacity worksheets use a different "grid" pattern
The 6 worksheet grids in `frontend/src/views/CapacityPlanning/components/grids/` use `v-data-table` + per-cell `v-text-field` slots. They are not AG Grid. The spec text cites these as "compliant" reference grids — but they lack range selection, fill handle, paste, and typed cell editors that the standard requires. **This is a contradiction the spec owner must resolve** before any migration starts. Two options:
  - (a) the spec recognizes "v-data-table-with-cell-editors" as a second compliant pattern (lower bar), in which case 6 capacity grids and the 4 grid duplicates above get the same status; or
  - (b) AG Grid is the only compliant pattern, in which case 6 capacity worksheet grids also need migration.

### 6.3 Shared composables for AG Grid entry
- `useAGGridBase.ts` — shared paste, snackbar, mergedGridOptions, exportToCsv. 5 entry grids consume it. Migrating any new domain to this composable is low-cost.
- `useProductionGridData.ts`, `useQualityGridData.ts`, `useDowntimeGridData.ts` — domain-specific column defs + save logic. Pattern is established; new domains follow the same template.
- `clipboardParser.ts` (utils) provides validation schemas (`entrySchemas`) per entry type. Adding new entry types is a structured one-file change.

### 6.4 ReadBackConfirmation and PastePreviewDialog
Reused across the entry grids (Quality, Production, Downtime, Attendance, Hold) and one form (Quality form). Migrating an entry from form to grid does NOT require redesigning the confirmation/preview UX — it's already common.

### 6.5 Workflow wizard steps duplicate primary entry surfaces
WorkflowStepProduction (43), WorkflowStepDowntime (48), WorkflowStepAttendance (49) re-implement single-row entry forms for domains that already have AG Grid implementations. These could embed the corresponding grids in compact mode rather than re-rolling a form per step. This is a second high-leverage batch migration: refactoring 3 step components to embed grids removes ~300 lines of duplicate UI.

### 6.6 CSV upload dialogs share a pattern
`CSVUploadDialog{Production,Quality,Attendance,Downtime,Hold}.vue` are sibling files following the same layout. They are already grid-paired. New entry grids can copy this template. Backend infrastructure: `backend/utils/csv_upload.py` (per project memory).

### 6.7 Orphaned mutation endpoints
- `POST /capacity/bom/{id}/components`, `PUT /capacity/bom/{id}/components/{cid}` (capacity/bom_stock.py:148, 174) — BOM component mutations exist but BOMGrid only edits header rows. Component-level grid editing surface seems missing.
- `POST /calculation-assumptions/...` (4 endpoints) — no clear UI route. See row 42.
- `POST /workflow/bulk-transition` — no clear UI surface.

These suggest the audit also revealed coverage gaps that aren't strictly form-vs-grid issues.

---

## 7. Phase 3 Enforcement Appendix

### 7.1 Confirmation of ESLint config
- File: `frontend/eslint.config.js` (44 lines).
- Confirmed **flat config** (default-export array of config objects, ESLint 9/10 style).
- Confirmed **`pluginVue.configs['flat/essential']`** spread at line 9.
- Vue file rules block at lines 42-53 uses TypeScript parser via `tsParser`.
- Existing custom rule shape: rules object literal at lines 26-40 with override-by-glob blocks for `.vue`, `.ts`, and tests.

### 7.2 Recommendation: option (a), a custom local rule in the existing flat config

Add a single inline custom rule object to `eslint.config.js` that targets `frontend/src/views/**/*.vue` and `frontend/src/components/entries/**/*.vue` and walks the parsed Vue template AST looking for `<v-text-field>`, `<v-textarea>`, `<v-select>`, `<v-autocomplete>`, `<v-radio-group>`, `<v-checkbox>` tags — and asserts the same file ALSO contains `<AgGridVue>` or `<AGGridBase>`. Skip the rule when the file's `<template>` contains only `v-form` blocks under a `v-dialog` flagged with `data-exception="auth|admin|filter|confirm"` (a small disciplined attribute convention).

**Why this option over (b) plugin or (c) grep:**
- Option (b) (project-local plugin) is overkill: ESLint plugins require `package.json`, `index.js`, and a separate publication step. The rule logic is < 50 lines of AST walking. The only reason to plugin it is reuse across repos, and there is no second repo.
- Option (c) (CI grep check) has the right cost-of-tooling but the wrong place. The signal needs to fire **at edit time**, in the IDE, while the developer is wiring up the form. A grep step runs only in CI after a push and surfaces too late. A repo-local ESLint rule is the same effort and runs every save.
- Option (a) extends the existing flat config (already familiar to the team), inherits the existing override-by-glob pattern (line 42-53), and slots between the Vue config block and the TS config block. Estimated implementation: ~60 lines added to `eslint.config.js`, no new dev dependencies.

**Implementation sketch (NOT executed in Phase 0 — included here as recommendation only):**

Add a rule object with `meta.docs.description = 'Forbid form inputs in entry surfaces unless paired with AG Grid or marked as a permitted exception'`. Use `vue-eslint-parser` (already pulled by `eslint-plugin-vue`) to walk `VElement` nodes; collect all element names; if any of the forbidden tags is present AND `AgGridVue`/`AGGridBase` is absent AND no `data-exception` attribute is present on a containing `v-dialog`, emit a violation pointing at the offending element with a fix suggestion linking to the spec.

Glob scope: `['src/views/**/*.vue', 'src/components/entries/**/*.vue']`. Component-internal grids in `src/components/grids/` and reusable filters/dialogs in `src/components/{filters,dialogs}/` are excluded by glob, not by AST inspection.

---

## 8. Open Questions — Resolutions Log

1. **Reference grid contradiction.** ✅ **RESOLVED 2026-05-01 (R1).** AG Grid is the only canonical pattern. Capacity v-data-table worksheets (rows 19–24) are non-compliant and added to the migration list.
2. **Range selection / fill handle.** ✅ **RESOLVED 2026-05-01 (R2).** Custom Community-feasible implementation preferred (option c); drop requirement where Community cannot deliver (option b). Native flags MUST NOT be enabled. Enterprise upgrade path documented for the future.
3. **Form-vs-grid duplicates at /data-entry/\*.** ✅ **RESOLVED.** Router lines `89, 95, 101, 107` switch to grid components in Group A of the Phase 1 plan; `components/entries/` form variants are deleted.
4. **MyShift quick-action dialogs** (row 12). ✅ **RESOLVED.** Per spec-owner directive ("user adoption from Excel; spreadsheet similarity"), these are operational data entries and must become grids. Quick-action UX is preserved by embedding compact-mode AG Grids — handled in Group C of the Phase 1 plan.
5. **Calculation Assumptions** (row 42). ✅ **DEFERRED.** Surface to be designed in dual-view spec #1; will follow the Spreadsheet Standard at that time.
6. **DataEntryGrid.vue** (row 56). 🔄 **CARRIED INTO PHASE 1** as the first task of Group I (verify alive/dead; delete or migrate).

---

*End of Phase 0 inventory. Phase 1 migration plan: see `docs/audit/entry-surface-migration-plan.md`.*
