# Group B — Runtime Validation of Wizard Step Embeds

**Phase:** Phase 1.0.3 (between Group A completion and Group B execution)
**Predecessor:** `docs/audit/group-a-runtime-validation.md`, `docs/audit/entry-surface-migration-plan.md`
**Trigger:** Group A's "Sanity check on Group B" (`group-a-runtime-validation.md` § "Sanity check on Group B") flagged that the 3 wizard steps targeted by Group B do not share payload code with the Group A grids and that at least one step targets a non-existent backend endpoint. This file verifies, per surface, what the wizard step actually does today and costs the three migration options spelled out in the plan (fix-call / embed-grid / skip-persistence).

> Cited paths are absolute repo-relative. The frontend axios `baseURL` is `/api/v1` per `frontend/src/services/api/client.ts:4`; all wizard-step calls below are issued via that client unless otherwise noted, so they hit `/api/v1/<path>`. The backend mounts these routers at `/api/<resource>` (no `/v1` segment) — every step call is therefore subject to the same `/api/v1` ↔ `/api` mismatch as the Group A grids, and the same dev-proxy / nginx rewrite that papers it over. That mismatch is **not** the subject of this report; it affects all surfaces equally.

---

## 1. WorkflowStepProduction (plan #5 / inv 43)

**File:** `frontend/src/components/workflow/steps/WorkflowStepProduction.vue`
**Wizard slot:** `WorkflowWizard.vue:175 currentStepData?.id === 'complete-production'` — sits inside the `shift-end` workflow at index 1 (after `review-completeness`, before `close-downtime`). Step definition: `workflowStore.ts:99-105 { id: 'complete-production', required: true, component: 'WorkflowStepProduction' }`.

### A. Step component summary

- **Operator action:** During shift-end, the operator sees the work orders that were running this shift, fills in `produced` and `defects` per row, and clicks Submit (per row) or "Mark Remaining as Zero" (bulk). Once `pendingEntries === 0`, the confirmation checkbox un-locks and `complete` is emitted upward.
- **Local state owned (`WorkflowStepProduction.vue:176-189`):** `loading`, `confirmed`, `workOrders[]` (each row has `id`, `product`, `target`, `produced`, `defects`, `targetCompletion`, `hasEntry`, `submitting`).
- **Wizard-flow contract:**
  - `emit('update', { workOrders, totalProduced, targetCompletion, isValid })` is wired to `WorkflowWizard.vue:177 onStepUpdate` → `workflowStore.updateStepData('complete-production', data)`.
  - `emit('complete', {...})` only fires when `confirmed && pendingEntries === 0` (`WorkflowStepProduction.vue:277-285`) → `workflowStore.completeStep('complete-production', data)`.
  - The step's `isValid` (`WorkflowStepProduction.vue:273`) gates `workflowStore.canProceed` (`workflowStore.ts:180-189`), which in turn gates the wizard's "Next" button. **The step blocks the wizard until every row has `hasEntry === true`** — i.e. until every row has been individually persisted (or *appears* to have been; see §B).

### B. Current API behaviour

| Call | File:line | Method+URL | Payload | Endpoint exists? |
|---|---|---|---|---|
| Fetch shift work orders | `WorkflowStepProduction.vue:292` | `GET /work-orders/shift-production` | — | **NO** — `backend/routes/work_orders.py` has no such route (verified by grep). The closest live route is `GET /api/work-orders` with filters and `GET /api/work-orders/status/{status}`. |
| Submit per-row entry | `WorkflowStepProduction.vue:244` | `POST /production-entries` | `{ work_order_id, quantity_produced, defect_quantity, date }` | **NO** — there is no `POST /production-entries` route on the backend. The only `production-entries` endpoint is `GET /api/export/production-entries` (CSV export, `backend/routes/export.py:142`). The canonical create route is **`POST /api/production`** (`backend/routes/production.py:50`), which expects a completely different schema — `client_id`, `product_id` (int), `shift_id` (int), `production_date`, `units_produced` (int >0), `run_time_hours` (Decimal >0), `employees_assigned` (int >0) are all required (`backend/schemas/production.py:11-44`). |

- **Errors surfaced to operator?** No. Both calls have `try/catch` blocks that only `console.error` (`WorkflowStepProduction.vue:253` and `:302`). The fetch failure path silently substitutes hard-coded mock work orders (`:304-310`); the submit failure path silently leaves the row with `hasEntry === false` and prints to console — the operator sees no notification. There is no `useNotificationStore` import.
- **Does it persist?** **No.** `POST /production-entries` 404s. The catch swallows the 404, the row keeps `hasEntry === false`, and the operator hits the wizard's "Next" gate — they can never advance unless they click "Mark Remaining as Zero" *and that also 404s on every row*. **The step is currently un-completable in production**; in development it appears to "work" only via the mock-data fallback, which sets `hasEntry: true` on rows 1, 2, 4 in fixtures (`:304-310`) so two rows remain submittable and the operator can hit "Mark Remaining as Zero" — those calls 404 and still leave the rows pending. The step is structurally broken; the only way past it is the wizard's "Skip" button, which the step disallows because `required: true` (`workflowStore.ts:103`).

### C. Migration options

#### (a) Fix the wizard's API call

Replace `POST /production-entries` with `POST /api/production` and the canonical Pydantic-aligned payload, plus `GET /work-orders/shift-production` with `GET /api/work-orders` filtered by today's date and `status=in_progress`.

- **Effort:** 6–10 hours.
  - Acquire `client_id` (auth context) and `shift_id` (active-shift store) — same gap as Group A grids.
  - Resolve `product_id` (int) per work order — work orders carry a product; the row needs to surface it. Today's UI displays `product` (string) but never holds the int FK.
  - Build a `production_date` (today) and decide where `run_time_hours` and `employees_assigned` come from — neither is gathered by the wizard step today; both are required `>0`.
  - Replace fetch with `GET /api/work-orders` filtered server-side (or in-memory), enrich the row with the open production entry if one exists.
- **Risk:** Medium-high. `run_time_hours` and `employees_assigned` are not available in the step's UI. Inventing a fixed `8.0` and `1` would technically satisfy validation but produces garbage KPI input. A real fix needs new UI fields or a reduced "draft entry" backend endpoint.
- **UX impact:** The step becomes functional for the first time, but operators must enter additional fields (run-time, headcount) that are not on the design today. Or accept that values are placeholder and overwritten later by the standalone Group A grid.

#### (b) Embed the Group A `ProductionEntryGrid` in compact mode

Replace the step's bespoke table + per-row submit with `<ProductionEntryGrid embedMode="compact" :workOrderFilter="todaysOpenWorkOrders" />`.

- **Effort:** 12–18 hours.
  - The grid (`frontend/src/components/grids/ProductionEntryGrid.vue`) does **not** today expose a `compact` or `embed` prop — `density="compact"` is used on individual filter inputs only (verified by grep). A compact-mode prop would have to be added: hide the toolbar (`v-card-title`), hide the global filters, hide the summary card row, lock height to ~400px, and accept a row filter from props. ~4 hours of grid changes.
  - Wire the grid's `onSave` callback (currently routes via `useProductionGridData`, which does **not** exist in the same shape as the other Group A composables — verified: `useProductionGridData.ts` uses `useProductionDataStore` and is a more elaborate AG-Grid wrapper than `useDowntimeGridData` / `useAttendanceGridData`) to also fire `onStepUpdate({ isValid: pendingCount === 0 })` so the wizard's `canProceed` advances.
  - Pre-filter the grid to today's open work orders (the grid currently ships with date / product / shift / line filters defaulting to "all"; the wizard would need to seed them).
  - The grid's "save" applies to multiple rows at once and persists via `productionDataStore` — semantics differ from the wizard's per-row submit. The wizard's `pendingEntries` gate must adapt: it has to reflect *the grid's* unsaved/saved state, not the step's local `hasEntry` flag.
- **Risk:** Medium. AG-Grid inside a 900-px modal in compact mode needs design review. The "advance only after save" wizard semantics couple the wizard to grid internals.
- **UX impact:** Operator gets the same entry grid they will later use in the Group A page — consistent UX, paste support, editable cells. Mobile (`isMobile` fullscreen) needs verification — AG-Grid in a fullscreen mobile dialog is untested. The wizard's Next button has to reflect grid-save state, not step-local state.

#### (c) Skip the step's persistence; rely on the Group A grid post-shift

Demote `WorkflowStepProduction` to a *review-only* step: list the work orders, show today's `units_produced` from the live API, prompt the operator to confirm "production data is entered for all work orders," and link out to the standalone `ProductionEntryGrid` page in a new tab. No POST happens inside the wizard.

- **Effort:** 3–5 hours. Replace the per-row inputs and Submit buttons with a read-only summary table sourced from `GET /api/production?shift_date=today&shift_id=<active>`. Add a "Open Production Entry Grid" button. Keep the confirmation checkbox; gate it on "every work order has at least one entry today."
- **Risk:** Low. No new persistence path, no new endpoint dependencies. The check ("every work order has an entry") is a single GET.
- **UX impact:** Operators have one extra click out of the wizard to add missing entries, then return. The wizard becomes an audit checkpoint, not an entry surface — which matches the Group A "post-shift entry, not pre-shift" mental model.

### D. Recommendation

**(c) Skip persistence inside the wizard.** The step is currently broken (404 on every save), the data model needs values the wizard never collects (`run_time_hours`, `employees_assigned`, `product_id` as int), and the standalone Group A `ProductionEntryGrid` already handles this with the right schema. The wizard's role here is to *gate* shift-end on "production is entered," not to *be* the entry surface.

### E. Test impact

- **Existing tests:** None. `frontend/src/components/workflow/__tests__/` and `frontend/src/components/workflow/steps/__tests__/` do not exist (verified by glob). The only related file is `frontend/src/stores/__tests__/workflowStore.spec.ts`, which mocks `api` and tests state transitions, not step components.
- **For (a) fix-call:** New `WorkflowStepProduction.spec.ts` with mocked `api.post('/api/production')` happy and 422 paths; assert that step's `isValid` toggles when the row's `hasEntry` becomes true.
- **For (b) embed-grid:** New `WorkflowStepProduction.spec.ts` mounting the embedded `ProductionEntryGrid` with stub composable + grid component; assert the wizard's `update` event reflects grid save state. Plus `ProductionEntryGrid.spec.ts` updates to cover the new `embedMode` / row-filter props (no current spec exists for this grid).
- **For (c) skip-persistence:** New `WorkflowStepProduction.spec.ts` covering: read-only table renders, "all entries present" detection, link-out button. Simpler than (a) and (b) — no save path to test.

---

## 2. WorkflowStepDowntime (plan #6 / inv 48)

**File:** `frontend/src/components/workflow/steps/WorkflowStepDowntime.vue`
**Wizard slot:** `WorkflowWizard.vue:180 currentStepData?.id === 'close-downtime'` — `shift-end` workflow at index 2 (after `complete-production`, before `enter-handoff`). Step definition: `workflowStore.ts:107-113 { id: 'close-downtime', required: true, component: 'WorkflowStepDowntime' }`.

### A. Step component summary

- **Operator action:** During shift-end, the operator sees a list of currently-open downtime incidents (no `endTime`), clicks "Resolve" on each, fills a dialog (`endTime`, `rootCause`, `resolution`), and submits. Once `openCount === 0`, the confirmation checkbox un-locks and `complete` is emitted.
- **Local state owned (`WorkflowStepDowntime.vue:230-242`):** `loading`, `confirmed`, `resolveDialog`, `resolving`, `selectedIncident`, `incidents[]`, `resolveForm` (`endTime`, `rootCause`, `resolution`).
- **Wizard-flow contract:**
  - `emit('update', { incidents, openCount, totalMinutes, isValid })` → `workflowStore.updateStepData('close-downtime', data)`.
  - `emit('complete', ...)` fires when `confirmed && openCount === 0` (`WorkflowStepDowntime.vue:347-355`) → `workflowStore.completeStep('close-downtime', data)`.
  - **Wizard cannot advance until every open incident is "resolved"** (per `:153` `:disabled="openCount > 0"` on the checkbox). Whether the resolve actually persisted is irrelevant — see §B.

### B. Current API behaviour

| Call | File:line | Method+URL | Payload | Endpoint exists? |
|---|---|---|---|---|
| Fetch open incidents | `WorkflowStepDowntime.vue:362` | `GET /downtime/shift` | — | **NO** — `backend/routes/downtime.py` exposes only `GET /api/downtime` (list with filters), `GET /api/downtime/{id}`, no `/shift` sub-route (verified by grep). |
| Resolve incident | `WorkflowStepDowntime.vue:307` | `PATCH /downtime/{id}/resolve` | `{ end_time, root_cause, resolution }` | **NO** — the only `/resolve` route on the entire backend is `POST /api/alerts/{alert_id}/resolve` (`backend/routes/alerts/crud.py:266`). The downtime router has only `PUT /api/downtime/{downtime_id}` for updates (`backend/routes/downtime.py:94`); no `PATCH`, no `/resolve`. Already flagged in `group-a-runtime-validation.md` § "Sanity check on Group B". |

- **Errors surfaced to operator?** **No, and worse: the catch path actively lies.** `WorkflowStepDowntime.vue:323-331` — on save failure, the catch block sets `incident.resolved = true` locally, closes the dialog, and emits `update` as if the resolve succeeded. The operator sees the incident move from "Open" to "Resolved" in the UI; nothing was persisted. The wizard's `openCount` drops to 0; the operator advances to the next step having "resolved" nothing. This is a data-integrity bug, not just a missing endpoint.
- **Does it persist?** **No.** Both calls 404 in production; the resolve handler hides the failure with a forged success state.

### C. Migration options

#### (a) Fix the wizard's API call

Replace `PATCH /downtime/{id}/resolve` with the existing `PUT /api/downtime/{downtime_id}` route (`backend/routes/downtime.py:94`) using `DowntimeEventUpdate` shape. Replace `GET /downtime/shift` with `GET /api/downtime?shift_date=<today>&client_id=<auth>` plus a client-side filter for "no resume / not closed."

- **Effort:** 4–8 hours.
  - The "open" concept on `DowntimeEntry` is *implicit*: there is no `is_resolved` column; the convention used by Group A's grid is that an entry has a `corrective_action` and `notes` once it's closed. Need to decide what "resolve" means in DB terms. Options: (1) add a `corrective_action` write that triggers the entry to be considered closed; (2) require an `end_time` field — but `DowntimeEventCreate`/`Update` schema (`backend/schemas/downtime.py`) has no `end_time`; the schema only has `downtime_duration_minutes`. The wizard's `end_time` UI field has no mapping target.
  - `rootCause` UI value (e.g. `'Mechanical Failure'`, `'Electrical Issue'`) can map to `root_cause_category` (str, free text per schema).
  - `resolution` maps to `corrective_action` (per the Group A reconciliation in `group-a-runtime-validation.md` § 3D).
  - Remove the silent-success forgery in the catch block; show a snackbar via `useNotificationStore`.
- **Risk:** Medium. The fundamental mismatch — wizard models incidents as start/end events, backend models them as duration-only entries — means even after the fix, "resolving an open incident" doesn't quite map. The wizard would have to either compute duration on resolve (now − start_time) or stop pretending incidents have a runtime resolve concept.
- **UX impact:** Operator sees real success / failure feedback. The "End Time" field in the dialog becomes informational only (or computes duration_minutes).

#### (b) Embed the Group A `DowntimeEntryGrid` in compact mode

Replace the open-incidents list + resolve dialog with `<DowntimeEntryGrid embedMode="compact" :scope="todaysShiftDowntime" />`.

- **Effort:** 14–20 hours.
  - Same compact-mode prop work as Production (~4 hours): the grid shell needs to hide the title bar / filters / summary cards.
  - Group A's grid is a *creation* surface — paste rows, edit, save. Today's wizard step is a *resolution* surface — close existing rows. To make them one component, the grid needs an "open vs. resolved" view and an inline-edit affordance to add `corrective_action` to existing rows.
  - The wizard's `openCount` gate must read the grid's row state (count rows where `corrective_action` is empty), and `update` must fire whenever a row is saved.
  - The wizard step's design (avatar list with a "Resolve" CTA per incident, time + reason + duration triplet) is a fundamentally different pattern from a tabular grid. Embedding the grid changes the operator's mental model significantly.
- **Risk:** High. The grid's create-and-paste flow does not match the wizard step's "resolve existing" workflow. Trying to embed without rethinking the wizard step's UX produces a worse UI than today.
- **UX impact:** Loses the focused "resolve this incident" CTA; gains paste support and grid consistency. Probably the wrong tradeoff for this surface.

#### (c) Skip the step's persistence; rely on the Group A grid post-shift

Demote `WorkflowStepDowntime` to a *review-only* step: list incidents from `GET /api/downtime?shift_date=today` (read-only), highlight any without `corrective_action`, gate the confirmation checkbox on "all incidents have a corrective_action." Link out to `DowntimeEntryGrid` for resolution.

- **Effort:** 3–5 hours. Replace the resolve dialog and per-incident PATCH with a read-only list and a "needs attention" badge. Add a link/button to open the standalone Downtime grid in a new tab/modal.
- **Risk:** Low. No new endpoints, no schema work. The "needs attention" check is a single GET.
- **UX impact:** Same as (c) for Production. Operators do their data-entry in the Group A grid; the wizard checkpoints completeness. Mental model: "the wizard verifies, the grid records."

### D. Recommendation

**(c) Skip persistence inside the wizard.** The current step has both a missing endpoint and an active data-integrity bug (forged success state). The wizard's "list of open incidents" pattern fits a review-only role better than an entry role; the Group A grid is the right place to resolve incidents because it has the correct schema mapping and notification path. (a) is feasible but solves only part of the problem because the wizard's mental model — incidents have an `end_time` — doesn't match the backend's duration-only schema; (b) over-rotates the wizard step's UX.

### E. Test impact

- **Existing tests:** None for the step. `useDowntimeGridData.spec.*` exists in spirit (per the Group A report); the wizard step has no spec.
- **For (a) fix-call:** New `WorkflowStepDowntime.spec.ts` with mocked `api.put('/api/downtime/...')` happy and 422 paths. Critical: include a regression test that the catch block surfaces the error instead of forging success — this is the data-integrity bug.
- **For (b) embed-grid:** New `WorkflowStepDowntime.spec.ts` mounting embedded grid with stubbed composable; assert wizard `update` reflects grid save state. Plus `DowntimeEntryGrid.spec.ts` (new) for the embed-mode prop. Significant churn.
- **For (c) skip-persistence:** New `WorkflowStepDowntime.spec.ts` covering read-only list rendering, "needs attention" detection, link-out. Simplest of the three.

---

## 3. WorkflowStepAttendance (plan #7 / inv 49)

**File:** `frontend/src/components/workflow/steps/WorkflowStepAttendance.vue`
**Wizard slot:** `WorkflowWizard.vue:145 currentStepData?.id === 'confirm-attendance'` — `shift-start` workflow at index 1 (after `review-previous`, before `review-targets`). Step definition: `workflowStore.ts:55-62 { id: 'confirm-attendance', required: true, component: 'WorkflowStepAttendance' }`.

### A. Step component summary

- **Operator action:** During shift-start, the operator sees the day's roster, toggles each employee Present/Absent, drags employees to stations, and confirms. The step's `isValid` requires ≥80% attendance (`WorkflowStepAttendance.vue:213-217`).
- **Local state owned (`WorkflowStepAttendance.vue:178-182`):** `loading`, `searchQuery`, `confirmed`, `employees[]`, `stations[]`. Each employee row has `present: boolean` and `station: string|null`; each station has `assignedEmployee: int|null`.
- **Wizard-flow contract:**
  - `emit('update', { employees, stations, isValid })` → `workflowStore.updateStepData('confirm-attendance', data)`.
  - `emit('complete', { employees, stations, presentCount, absentCount })` fires only when `confirmed && isValid` (`:244-252`). The `complete` payload is read by `workflowStore.completeWorkflow()` → `createShift(workflowData)` → `POST /api/shifts/` (`workflowStore.ts:413`). **The attendance data is therefore included in the shift-create body, but as nested objects keyed by step id (`workflowData['confirm-attendance']`)**, not as `AttendanceRecordCreate` rows. The backend's `POST /api/shifts/` is unlikely to know what to do with this nested structure — verifying the shift-create handler is out of scope for this report, but it suggests attendance data may be ignored even on a successful "shift start."

### B. Current API behaviour

| Call | File:line | Method+URL | Payload | Endpoint exists? |
|---|---|---|---|---|
| Fetch shift roster | `WorkflowStepAttendance.vue:268` | `GET /employees/shift-roster` | — | **NO** — `backend/routes/employees.py` has `GET /api/employees`, `GET /api/employees/floating-pool/list`, `GET /api/employees/{id}`, but no `/shift-roster` (verified by grep). The Group A attendance grid uses the canonical `GET /api/employees?shift_id=<x>&active=true` (`useAttendanceGridData.ts:333`). |
| Fetch stations | `WorkflowStepAttendance.vue:269` | `GET /stations` | — | **NO** — there is no `/stations` route on the backend (verified by grep across `backend/routes/`). The stations concept does not appear to have a backend representation at all today. |
| Save attendance | — | — | — | **N/A — does not save anything.** Already noted in `group-a-runtime-validation.md` § "Sanity check on Group B": "It only reads `/employees/shift-roster` and `/stations` (lines 268-269); employee presence/station assignment is held in local state and emitted upward. There is no `api.create*` call." |

- **Errors surfaced to operator?** No. The fetch failure path silently substitutes hard-coded mock employees and stations (`:275-292`), so in dev (and given `/employees/shift-roster` and `/stations` always 404) the operator always sees the same 8 mock employees and 5 mock stations. There is no `useNotificationStore` import.
- **Does it persist?** **No.** Per the Group A note. Local state is emitted upward into `workflowData['confirm-attendance']`, included in the `POST /api/shifts/` body at workflow completion, and probably ignored by the backend. There is no `AttendanceRecord` row created.

### C. Migration options

#### (a) Fix the wizard's API call

Replace `GET /employees/shift-roster` with `GET /api/employees?shift_id=<active>&active=true` (matches the Group A grid's pattern, `useAttendanceGridData.ts:333`). For `GET /stations`: the route does not exist; either remove the station-assignment UI, or add a backend `/api/lines` or `/api/stations` route as part of the migration (substantial scope creep). For persistence: add per-employee `POST /api/attendance` calls when the operator confirms — same payload as Group A: `{ client_id, employee_id, shift_date, shift_id, scheduled_hours, is_absent, absence_type, ... }` (per `backend/schemas/attendance.py:22 AttendanceRecordCreate`).

- **Effort:** 12–18 hours.
  - Roster fetch is mechanical (~1 hour).
  - Stations fetch is open-ended: either accept that the station-assignment UI uses a frontend-only concept (no persistence), or invest in a new backend endpoint. Given the spec doesn't mention stations as a Pydantic schema, this is best deferred — see (c).
  - Per-employee attendance creates need the same translation as the Group A grid: UI `present: boolean` → `is_absent: 0|1`; UI `station: string` is unmapped; default `scheduled_hours` from the active shift's hours; combine `arrival_time`/`departure_time` from shift start (none in this UI today).
  - Concurrency: 8+ employee rows × `POST /api/attendance` is N round-trips; either batch or use Promise.all with rollback.
- **Risk:** High. The station-assignment concept has no backend home. Splitting "attendance" from "station assignment" is necessary, and the wizard's UI does both today.
- **UX impact:** Step actually persists attendance for the first time. Station assignment either becomes ephemeral (UI-only) or requires a new backend story.

#### (b) Embed the Group A `AttendanceEntryGrid` in compact mode

Replace the employee-list + station-cards UI with `<AttendanceEntryGrid embedMode="compact" :selectedDate="today" :selectedShift="activeShift.id" />`.

- **Effort:** 14–20 hours.
  - Same compact-mode prop work as Production / Downtime.
  - The Group A grid expects the operator to call `loadEmployees()` (`useAttendanceGridData.ts:325`) which fetches the active roster from `/api/employees`. The grid's row-per-employee model maps cleanly to the wizard's "toggle present/absent" UX, but the grid uses an editable status column (Present / Absent / Late / Half Day / etc.) instead of a binary toggle — different UX.
  - Station assignment is **not** an Attendance schema concept and is **not** in `AttendanceEntryGrid`. It would have to remain as a separate UI section in the wizard (the lower half of `WorkflowStepAttendance`) — the embed solves attendance only.
  - The wizard's `isValid` (≥80% attendance) must read grid row state.
- **Risk:** Medium. The grid embed handles attendance well; stations remain a separate concern. UX consistency with the Group A page is a plus — operators learn one pattern.
- **UX impact:** Operator sees the same grid in shift-start as they do post-shift. Station-assignment UI persists as a separate section below.

#### (c) Skip the step's persistence; rely on the Group A grid post-shift

Status quo persistence-wise — the step doesn't persist today. Fix the dead-link API calls to `/employees/shift-roster` and `/stations` to use canonical routes (`GET /api/employees?shift_id=...`; remove `/stations`), and surface "Attendance not yet recorded — record it in the Attendance Entry grid after the shift" as guidance. The wizard step becomes a true *roster review + station-assignment* checkpoint, not a persistence surface.

- **Effort:** 3–5 hours. Swap the roster fetch to `/api/employees?shift_id=...&active=true`. Drop the `/stations` call (no backend support); either move stations behind a feature flag or scope it to a future backend story. Add a notification when the step's local state diverges from "all employees present."
- **Risk:** Low. Matches today's actual behaviour (no persistence) but stops 404-ing on every load.
- **UX impact:** Minimal change to the wizard step. The Group A grid remains the canonical attendance entry surface.

### D. Recommendation

**(c) Skip persistence inside the wizard, but do fix the dead `/employees/shift-roster` and `/stations` calls.** The step has never persisted attendance; embedding the Group A grid (b) introduces a UX shift that doesn't match a "shift-start checkpoint" mental model; (a) requires inventing a backend story for stations. Lowest-cost path: align the read calls to the canonical routes and accept that attendance entry happens in the Group A page.

### E. Test impact

- **Existing tests:** None for the step.
- **For (a) fix-call:** New `WorkflowStepAttendance.spec.ts` with `api.get('/api/employees')` happy path, `api.post('/api/attendance')` per-row happy and 422 paths, plus a partial-failure rollback test. Plus `useAttendanceGridData.spec.ts` regression coverage if the fix shares the translation helper.
- **For (b) embed-grid:** New `WorkflowStepAttendance.spec.ts` with stubbed `AttendanceEntryGrid` + composable; assert `loadEmployees` is called when `selectedDate` and `selectedShift` change; assert wizard's `isValid` reflects grid attendance count.
- **For (c) skip-persistence:** New `WorkflowStepAttendance.spec.ts` covering canonical roster fetch, station-section rendering (UI-only), `isValid` ≥80% gate.

---

## Cross-cutting findings

### Are the 3 steps wired the same way?

**Yes, structurally.** All three:
- Import `api from '@/services/api'` directly (no composable boundary).
- Manage local-state-only data shapes; emit `update` and `complete` to the wizard.
- Have `try/catch` that `console.error` on failure and silently substitute mock data for fetches and (in Downtime's case) forge success state for writes.
- Have **no `useNotificationStore`** — operators receive no feedback when API calls fail. (Compare Group A grids, which all wire through `useNotificationStore.showError(...)` per the post-Run-5 silent-catch fix.)
- Are gated by a "confirmation checkbox" wired to `isValid`, which the wizard's `canProceed` reads (`workflowStore.ts:180-189`).

**No, in API surface.** Each step calls a different set of endpoints, and each set has a different non-existent-endpoint problem:
- Production: 2 calls, both nonexistent (`POST /production-entries`, `GET /work-orders/shift-production`).
- Downtime: 2 calls, both nonexistent (`PATCH /downtime/{id}/resolve`, `GET /downtime/shift`); plus a forged-success bug.
- Attendance: 2 calls, both nonexistent (`GET /employees/shift-roster`, `GET /stations`); zero writes.

### Is there a shared `useWorkflowStore` action that could be cleaned up centrally?

The wizard's `workflowStore.completeWorkflow()` (`workflowStore.ts:444-460`) bundles every step's `workflowData` into a single `POST /api/shifts/` (start) or `PATCH /api/shifts/{id}/end` (end) payload. **There is no per-step persistence in the store** — each step is responsible for its own persistence (or, today, lack thereof). The `completeStep` / `updateStepData` actions only mutate in-memory and localStorage state.

If the migration adopts option (c) for all three surfaces, the cleanup is conceptually small — formalise that "wizard steps are checkpoints, not persistence surfaces" and remove the steps' direct `api.post`/`api.patch` calls. If it adopts (a) or (b), there's an opportunity to add a `workflowStore.persistStep(stepId)` shared action so per-step persistence is uniform — but no such action exists today.

### Anything analogous to the Group A "client_id missing" finding?

Yes, three systemic issues:

1. **Steps have no `useAuthStore` or `useKPISelectionStore` import** (verified by grep) — i.e., `client_id` and active `shift_id` are not available in the steps' scope. Group A's grids derive `client_id` from auth context and `shift_id` from the active-shift selection; the wizard steps don't, which is part of why their payloads diverge from Group A's. Any migration option that *does* persist (a or b) must wire these stores in — same gap as Group A.

2. **All three steps swallow API errors with `console.error`-only.** The standard fix from Run 5 (Phase 5: silent-catch fixes via `useNotificationStore`) was applied to dashboards and a sub-set of components but **not** to the workflow steps. This is a pre-existing finding that should be fixed regardless of migration option.

3. **WorkflowStepDowntime's catch block forges a success state on write failure** (`:323-331`). This is a *data-integrity bug*, not a UX issue — the operator advances the wizard believing incidents are resolved when nothing was persisted. Even if option (c) is chosen and the resolve flow is removed entirely, this same anti-pattern of "if the write fails, mutate local state as if it succeeded" should be audited across the codebase. Recommend grep for `// Still update locally for demo` (the comment on `:325`) and similar phrasings.

A fourth, smaller finding: **all three steps ship with hard-coded mock fixtures** in their fetch catch blocks (`:304-310` Production, `:367-371` Downtime, `:276-292` Attendance). These predate the seeded-DB approach (`memory: ALL database data is disposable demo data`) and are now redundant — the seeded DB already provides realistic data. Mock fixtures hide endpoint failures from developers during local dev. Recommend removing them as part of any migration option (≤1 hour total).

---

## Group B revised migration plan

### Per-surface complexity & effort

| # | Surface | Recommended option | Complexity | Effort (hours) |
|---|---|---|---|---|
| 5 | WorkflowStepProduction | (c) Skip persistence | **Simple** | 3–5 |
| 6 | WorkflowStepDowntime | (c) Skip persistence + remove forged-success bug | **Simple** | 3–5 |
| 7 | WorkflowStepAttendance | (c) Skip persistence + fix dead `/employees/shift-roster` + drop `/stations` | **Simple** | 3–5 |
| — | Cross-cutting fixes (notifications, drop mock fixtures) | shared | — | 2–3 |

**Per-surface total (recommended (c) path):** 11–18 hours = **~1.5–2.5 days** for a single engineer.

If the spec-owner instead chooses (a) for all three (fix-call):
- Production (a): 6–10h
- Downtime (a): 4–8h
- Attendance (a): 12–18h (the largest because of the station problem)
- Cross-cutting: 2–3h
- **Total: 24–39h ≈ 3–5 days**

If (b) for all three (embed-grid):
- Compact-mode prop work shared across grids (one-time): ~4h
- Production (b): 12–18h
- Downtime (b): 14–20h
- Attendance (b): 14–20h
- Cross-cutting: 2–3h
- **Total: 46–65h ≈ 6–8 days**, plus design review for AG-Grid in the wizard modal at mobile widths.

### Sequencing inside Group B

If (c) for all three (recommended):

1. **Cross-cutting first** (~2–3h): introduce `useNotificationStore` in all three steps; remove mock-data fixtures; remove the forged-success bug in Downtime.
2. **WorkflowStepDowntime** (3–5h): swap to read-only list off `GET /api/downtime?shift_date=today`; gate confirmation on `corrective_action` non-empty; link out to Group A grid.
3. **WorkflowStepProduction** (3–5h): swap to read-only summary off `GET /api/production?shift_date=today`; gate on "every WO has an entry"; link out.
4. **WorkflowStepAttendance** (3–5h): swap roster fetch to `GET /api/employees?shift_id=<active>&active=true`; drop `/stations` call (UI-only); gate on ≥80% present.

Sequencing rationale: cross-cutting first to establish notification + mock-removal pattern; Downtime second because its bug is the most urgent (data integrity); Production third (most fields to wire); Attendance last (smallest payload change).

### Update to migration plan §3 — rows 5–7

The original `entry-surface-migration-plan.md` § 3 row 5–7 should be amended:

| Plan row | Surface | Original effort | Revised effort | Status footnote |
|---|---|---|---|---|
| 5 | WorkflowStepProduction | (XS / pure embed) | **S — 3–5h** (option c recommended) | "Embed-target endpoint `POST /production-entries` does not exist; payload diverges from `ProductionEntryCreate`; migrate to read-only checkpoint per `group-b-runtime-validation.md` § 1." |
| 6 | WorkflowStepDowntime | (XS / pure embed) | **S — 3–5h** (option c recommended) | "Embed-target endpoint `PATCH /downtime/{id}/resolve` does not exist; current step forges write success on failure (data-integrity bug); migrate to read-only checkpoint per `group-b-runtime-validation.md` § 2." |
| 7 | WorkflowStepAttendance | (XS / pure embed) | **S — 3–5h** (option c recommended) | "Step does not persist today; embed-target `GET /employees/shift-roster` and `GET /stations` do not exist; migrate to canonical roster + drop stations per `group-b-runtime-validation.md` § 3." |

§ 12 effort summary: "Group B" line should read **1.5–2.5 days** (option c) instead of the original "~½ day". If option (a) or (b) is chosen, update accordingly.

### Can Group B run in parallel with later groups?

**Yes for option (c).** None of the (c)-path changes touch shared composables, stores, or backend routes — they're surgical edits to three step components plus a small notification-wiring sweep. They can run in parallel with Groups C/D/E.

**Mostly yes for option (a).** The Production fix-call path needs `client_id` / `shift_id` plumbed into the wizard step, which would benefit from a shared "wizard-step context" composable. Coordinating that composable with later groups (if any introduce similar wizard contexts) requires sequencing.

**No for option (b).** Embedding the Group A grids requires adding a `compactMode` / `embedMode` prop to each grid component, which is a shared change to three of the four Group A grids. Group A is now closed; reopening those grids for Group B's needs would re-open the test surface and risk regressions to the recently-stabilised Group A migration. Strongly recommend not picking (b) for any surface.
