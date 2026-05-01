# Group A — Runtime Validation of Migration Surfaces

**Phase:** Phase 0.5 (between original inventory and the Group A re-route work)
**Predecessor:** `docs/audit/entry-surface-inventory.md`, `docs/audit/entry-surface-migration-plan.md`
**Trigger:** QualityEntryGrid save was discovered to send a payload that does not match the backend Pydantic schema. This file verifies the same payload alignment for all 4 Group A surfaces before proceeding.

> Cited paths are absolute repo-relative. Only the API service path prefix (`/api/v1` per `frontend/src/services/api/client.ts:4`) is interpolated; routes below show the *resource portion* the frontend calls (e.g. `POST /quality`).

---

## 1. Quality (Form: QualityEntry / Grid: QualityEntryGrid)

### A. Backend ground truth

- **Pydantic Create schema:** `backend/schemas/quality.py:12 QualityInspectionCreate`
- **Route:** `backend/routes/quality/entries.py:38 create_quality` mounted at `backend/routes/quality/__init__.py:21 prefix="/api/quality"` plus `entries_router` at `/`. Effective URL: **`POST /api/quality/`** (frontend axios baseURL `/api/v1` → so the call goes to `/api/v1/quality/` if the v1 prefix were enforced; today the api service simply posts to `/quality` — see `frontend/src/services/api/dataEntry.ts:25`).
- **ORM model:** `backend/orm/quality_entry.py:19 QualityEntry` (table `QUALITY_ENTRY`)
- **Backend adapter:** `backend/schemas/quality.py:50 from_legacy_csv` — translates CSV-style fields (`work_order_number`, `defects_found`, `scrap_units`, `rework_units`) into the canonical schema names. *Adapter is not invoked from the JSON `POST /api/quality/` route.*

| Field | Type | Required | Constraints |
|---|---|---|---|
| `client_id` | str | **Yes** | min 1, max 50 |
| `work_order_id` | str | **Yes** | min 1, max 50 |
| `job_id` | str | No | max 50 |
| `shift_date` | date | **Yes** | — |
| `inspection_date` | date | No | — |
| `units_inspected` | int | **Yes** | `> 0` |
| `units_passed` | int | **Yes** | `>= 0` |
| `units_defective` | int | No (default 0) | `>= 0` |
| `total_defects_count` | int | No (default 0) | `>= 0` |
| `inspection_stage` | str | No | max 50 |
| `process_step` | str | No | max 100 |
| `operation_checked` | str | No | max 50 |
| `is_first_pass` | int | No (default 1) | 0 or 1 |
| `units_scrapped` | int | No (default 0) | `>= 0` |
| `units_reworked` | int | No (default 0) | `>= 0` |
| `units_requiring_repair` | int | No (default 0) | `>= 0` |
| `inspection_method` | str | No | max 100 |
| `notes` | str | No | — |

### B. Form payload (currently routed)

- **Call site:** `frontend/src/components/entries/QualityEntry.vue:348 await api.createQualityEntry(formData.value)`
- **API binding:** `frontend/src/services/api/dataEntry.ts:25 api.post('/quality', data)`

`formData` shape (defined `QualityEntry.vue:263–276`):

| Field | Matches backend? |
|---|---|
| `client_id` | YES |
| `work_order_id` | YES |
| `product_id` | NO — backend has no `product_id` (vestigial UI field) |
| `inspected_quantity` | RENAMED — backend expects `units_inspected` |
| `defect_quantity` | RENAMED — backend expects `units_defective` (and/or `total_defects_count`) |
| `rejected_quantity` | NO — vestigial UI-only field |
| `defect_type_id` | NO — `QualityEntry` ORM has no `defect_type_id` (defects live in a separate `defect_detail` table) |
| `severity` | NO — vestigial UI-only |
| `disposition` | NO — vestigial UI-only |
| `inspector_id` | RECEIVED on response (`schemas/quality.py:113`) but NOT on `Create` |
| `defect_description` | NO — `QualityEntry` ORM has only `notes` (not `defect_description`) |
| `corrective_action` | NO — vestigial UI-only |

**Form is missing required fields:** `shift_date`, `units_passed`. The form does not send them, so backend Pydantic validation should 422 every time. (Form is currently routed to operators — implies the route is either unused or an exception path masks the failure.)

### C. Grid payload (target of re-route)

- **Save call:** `frontend/src/composables/useQualityGridData.ts:445 await api.createQualityEntry(data)`
- **Payload built:** `useQualityGridData.ts:430–441`

| Field | Matches backend? |
|---|---|
| `inspection_date` | YES (optional on backend) |
| `work_order_id` | YES (string in backend; grid sends string|number) |
| `product_id` | NO — vestigial |
| `inspected_quantity` | RENAMED — backend `units_inspected` |
| `defect_quantity` | RENAMED — backend `units_defective` and/or `total_defects_count` |
| `defect_type_id` | NO — vestigial |
| `severity` | NO — vestigial |
| `disposition` | NO — vestigial |
| `inspector_id` | NO — not on `Create` |
| `defect_description` | NO — would need to be `notes` |

**Grid is missing required fields:** `client_id`, `shift_date`, `units_passed`. Same root failure mode as form.

### D. Reconciliation gaps

- **Required-but-missing fields the grid must send:** `client_id`, `shift_date`, `units_passed` (`gt 0` for `units_inspected`, `ge 0` for `units_passed`).
- **Field renames needed:** `inspected_quantity` → `units_inspected`; `defect_quantity` → `units_defective` (and probably copy into `total_defects_count`); `defect_description` → `notes`.
- **Dead fields in grid (sent, ignored by backend):** `product_id`, `defect_type_id`, `severity`, `disposition`, `inspector_id` (on Create), `defect_description` (if not renamed to `notes`).
- **Dead fields in form (sent, ignored by backend):** Same as grid plus `rejected_quantity` and `corrective_action`. None of these are vestigial-but-useful — they all simply disappear at the JSON boundary.
- **clipboardParser.ts schema alignment:** `frontend/src/utils/clipboardParser.ts:321` `quality:` schema **already aligns with backend** (`shift_date`, `units_inspected`, `units_passed`, `units_defective`, `units_reworked`, `units_scrapped`). The clipboard parser is the source of truth that confirms the *grid* is the divergent code.

### E. Migration scope estimate

**M (4–16 hours)** — Field-name reconciliation + missing required fields + payload restructure. Cannot be a pure route swap because the existing grid would 422 just as the existing form does.

Test files that will need updating (greppable by `inspected_quantity`, `defect_quantity`, `createQualityEntry`):

- `frontend/src/components/grids/__tests__/QualityEntryGrid.spec.*` (if present — check `frontend/src/components/grids/__tests__/`)
- `frontend/src/composables/__tests__/useQualityGridData.spec.*`
- `frontend/src/components/entries/__tests__/QualityEntry.spec.*`
- Any seed/factory referring to those field names

---

## 2. Attendance (Form: AttendanceEntry / Grid: AttendanceEntryGrid)

### A. Backend ground truth

- **Pydantic Create schema:** `backend/schemas/attendance.py:22 AttendanceRecordCreate`
- **Route:** `backend/routes/attendance.py:43 create_attendance` at `prefix="/api/attendance"` (`backend/routes/attendance.py:40`). Effective URL: **`POST /api/attendance`**.
- **ORM model:** `backend/orm/attendance_entry.py:29 AttendanceEntry` (table `ATTENDANCE_ENTRY`)
- **Backend adapter:** `backend/schemas/attendance.py:59 from_legacy_csv` translates legacy `status` strings (`Present` / `Absent` / `Late` / `Leave` / `Vacation` / `Medical`) into `is_absent` + `absence_type` enum.

| Field | Type | Required | Constraints |
|---|---|---|---|
| `client_id` | str | **Yes** | min 1, max 50 |
| `employee_id` | int | **Yes** | `> 0` |
| `line_id` | int | No | — |
| `shift_date` | date | **Yes** | — |
| `shift_id` | int | No | `> 0` |
| `scheduled_hours` | Decimal | **Yes** | `> 0`, `<= 24` |
| `actual_hours` | Decimal | No (default 0) | `>= 0`, `<= 24` |
| `absence_hours` | Decimal | No (default 0) | `>= 0`, `<= 24` |
| `is_absent` | int | No (default 0) | 0 or 1 |
| `absence_type` | enum (`UNSCHEDULED_ABSENCE` / `VACATION` / `MEDICAL_LEAVE` / `PERSONAL_LEAVE`) | No | — |
| `covered_by_employee_id` | int | No | `> 0` |
| `coverage_confirmed` | int | No (default 0) | 0 or 1 |
| `arrival_time` | datetime | No | — |
| `departure_time` | datetime | No | — |
| `is_late` | int | No (default 0) | 0 or 1 |
| `is_early_departure` | int | No (default 0) | 0 or 1 |
| `absence_reason` | str | No | — |
| `notes` | str | No | — |

### B. Form payload (currently routed)

- **Call site:** `frontend/src/components/entries/AttendanceEntry.vue:257 await api.createAttendanceEntry(formData.value)`
- **API binding:** `frontend/src/services/api/dataEntry.ts:14 api.post('/attendance', data)`

`formData` (`AttendanceEntry.vue:205–216`):

| Field | Matches backend? |
|---|---|
| `employee_id` | YES (string in form, int on backend; coerce) |
| `date` | RENAMED — backend `shift_date` |
| `shift_id` | YES |
| `status` | NO — backend has `is_absent` + `absence_type`. Adapter `from_legacy_csv` would handle this, but the JSON route does NOT call the adapter; would need either a route-level translator or restructure. |
| `absence_reason` | YES (free-form text accepted) |
| `is_excused` | NO — vestigial UI-only |
| `late_minutes` | NO — backend tracks `is_late` flag + `arrival_time`, not minutes |
| `clock_in` | RENAMED — backend `arrival_time` (and is `datetime` not `time`) |
| `clock_out` | RENAMED — backend `departure_time` |
| `notes` | YES |

**Form is missing required fields:** `client_id`, `scheduled_hours`. Form is broken at the JSON boundary today.

### C. Grid payload (target of re-route)

- **Save call:** `frontend/src/composables/useAttendanceGridData.ts:391 / 394 / 397 await api.createAttendanceEntry(data)`
- **Payload built:** `useAttendanceGridData.ts:376–387`

| Field | Matches backend? |
|---|---|
| `employee_id` | YES |
| `date` | RENAMED — backend `shift_date` |
| `shift_id` | YES |
| `status` | NO — same translation problem as form |
| `clock_in` | RENAMED — `arrival_time` (datetime expected; grid sends `''` or HH:MM string) |
| `clock_out` | RENAMED — `departure_time` |
| `late_minutes` | NO — vestigial |
| `absence_reason` | YES |
| `is_excused` | NO — vestigial |
| `notes` | YES |

**Grid is missing required fields:** `client_id`, `scheduled_hours`.

### D. Reconciliation gaps

- **Required-but-missing fields the grid must send:** `client_id`, `scheduled_hours` (with `gt 0`).
- **Field renames needed:** `date` → `shift_date`; `clock_in` → `arrival_time` (with full ISO datetime, not just HH:MM); `clock_out` → `departure_time`.
- **Status translation:** the grid's `status` ∈ {Present, Absent, Late, Half Day, Leave} must be mapped to `is_absent` (0/1) and `absence_type` enum on the way out — same mapping as `from_legacy_csv` (`backend/schemas/attendance.py:67–80`). Half Day is unmapped on backend. `late_minutes` and `is_excused` are dead.
- **Dead fields in grid (sent, ignored):** `late_minutes`, `is_excused`, `employee_name`, `department` (the latter two are reference data attached for display, never expected in payload).
- **Dead fields in form (sent, ignored):** same as grid.
- **clipboardParser.ts schema alignment:** `frontend/src/utils/clipboardParser.ts:332` `attendance:` schema is **outdated** — it requires `attendance_date` but backend wants `shift_date`. `worked_hours` should be `actual_hours`. **clipboardParser entry needs editing as part of this migration.**

### E. Migration scope estimate

**M (4–16 hours)** — Same class as Quality. Rename + missing required fields + status-translation helper + clipboardParser schema fix.

Test files that will need updating:

- `frontend/src/composables/__tests__/useAttendanceGridData.spec.*`
- `frontend/src/components/grids/__tests__/AttendanceEntryGrid.spec.*` (if present)
- `frontend/src/components/entries/__tests__/AttendanceEntry.spec.*`
- `frontend/src/utils/__tests__/clipboardParser.spec.ts` (already exists)

---

## 3. Downtime (Form: DowntimeEntry / Grid: DowntimeEntryGrid)

### A. Backend ground truth

- **Pydantic Create schema:** `backend/schemas/downtime.py:25 DowntimeEventCreate`
- **Route:** `backend/routes/downtime.py:36 create_downtime` at `prefix="/api/downtime"` (`backend/routes/downtime.py:33`). Effective URL: **`POST /api/downtime`**.
- **ORM model:** `backend/orm/downtime_entry.py:17 DowntimeEntry` (table `DOWNTIME_ENTRY`)
- **Backend adapter:** `backend/schemas/downtime.py:61 from_legacy_csv` maps category strings (EQUIPMENT/MATERIAL/SETUP/etc.) into `DowntimeReasonEnum` and converts `duration_hours` → `downtime_duration_minutes`.

| Field | Type | Required | Constraints |
|---|---|---|---|
| `client_id` | str | **Yes** | min 1, max 50 |
| `work_order_id` | str | No | max 50 |
| `line_id` | int | No | — |
| `shift_date` | date | **Yes** | — |
| `downtime_reason` | enum (`EQUIPMENT_FAILURE` / `MATERIAL_SHORTAGE` / `SETUP_CHANGEOVER` / `QUALITY_HOLD` / `MAINTENANCE` / `POWER_OUTAGE` / `OTHER`) | **Yes** | — |
| `downtime_duration_minutes` | int | **Yes** | `> 0`, `<= 1440` |
| `machine_id` | str | No | max 100 |
| `equipment_code` | str | No | max 50 |
| `root_cause_category` | str | No | max 100 |
| `corrective_action` | str | No | — |
| `notes` | str | No | — |

### B. Form payload (currently routed)

- **Call site:** `frontend/src/components/entries/DowntimeEntry.vue:268 await api.createDowntimeEntry(formData.value)`
- **API binding:** `frontend/src/services/api/dataEntry.ts:8 api.post('/downtime', data)`

`formData` (`DowntimeEntry.vue:190–198`):

| Field | Matches backend? |
|---|---|
| `equipment_id` | NO — backend has `equipment_code` (str, not id), `machine_id`, and `line_id`. Form treats this as a generic "line" select. |
| `reason_id` | NO — backend expects `downtime_reason` *enum string*, not an id |
| `start_time` | NO — backend has `shift_date` only; no start/end timestamps on the schema |
| `end_time` | NO — same |
| `duration_minutes` | RENAMED — backend `downtime_duration_minutes` |
| `category` | NO — these UI category strings (`Planned Maintenance`, `Unplanned Breakdown`, etc.) do not match the `DowntimeReasonEnum` set |
| `notes` | YES |

**Form is missing required fields:** `client_id`, `shift_date`, `downtime_reason` (correct enum value).

### C. Grid payload (target of re-route)

- **Save call:** `frontend/src/composables/useDowntimeGridData.ts:428 / 437 await kpiStore.createDowntimeEntry(data)` (note: routes through Pinia store, but the store calls `api.createDowntimeEntry` per `productionDataStore.ts`).
- **Payload built:** `useDowntimeGridData.ts:415–424`

| Field | Matches backend? |
|---|---|
| `work_order_id` | YES (optional) |
| `downtime_start_time` | NO — schema has no start time field |
| `downtime_reason` | PARTIAL — backend expects `DowntimeReasonEnum` string; grid sends free-form `reason_name` from `kpiStore.downtimeReasons` (likely arbitrary text) |
| `category` | NO — grid's category strings don't match enum |
| `duration_hours` | RENAMED + UNIT-CONVERTED — backend wants `downtime_duration_minutes` (int) |
| `impact_on_wip_hours` | NO — vestigial UI-only |
| `is_resolved` | NO — vestigial UI-only |
| `resolution_notes` | RENAMED — would map to `corrective_action` (and/or `notes`) |

**Grid is missing required fields:** `client_id`, `shift_date`, `downtime_duration_minutes` (must be derived from `duration_hours × 60`), and a valid `downtime_reason` enum value.

### D. Reconciliation gaps

- **Required-but-missing fields the grid must send:** `client_id`, `shift_date` (probably derived from `downtime_start_time`), `downtime_duration_minutes` (from `duration_hours`), `downtime_reason` (correct enum value).
- **Field renames needed:** `duration_hours` → `downtime_duration_minutes` (×60); `resolution_notes` → `corrective_action` or `notes`; `category` is dropped or merged into `root_cause_category`.
- **Reason mapping table required:** existing categorical strings (`'Planned Maintenance'`, `'Unplanned Breakdown'`, `'Changeover'`, `'Material Shortage'`, `'Quality Issue'`, `'Operator Absence'`, `'Other'`) must map to the seven `DowntimeReasonEnum` values. `'Operator Absence'` has no enum equivalent (closest: `OTHER`); `'Changeover'` → `SETUP_CHANGEOVER`. The backend adapter at `backend/schemas/downtime.py:65–78` is the canonical mapping for legacy CSV but operates on different keys.
- **Dead fields in grid (sent, ignored):** `downtime_start_time` (no schema field), `impact_on_wip_hours`, `is_resolved`, `resolution_notes` (if not renamed).
- **Dead fields in form (sent, ignored):** `equipment_id`, `reason_id`, `start_time`, `end_time`, `category` (unless mapped). Form is more divergent than grid.
- **clipboardParser.ts schema alignment:** `frontend/src/utils/clipboardParser.ts:340` `downtime:` schema requires `shift_date` and `downtime_minutes` — `downtime_minutes` does not match backend's `downtime_duration_minutes`. **clipboardParser needs aligning** as part of migration.

### E. Migration scope estimate

**M (4–16 hours)**, leaning toward the higher end. This surface has the largest field divergence and a unit-conversion + enum-mapping requirement. Both form and grid are equally broken, but the grid has more vestigial UI fields.

Test files that will need updating:

- `frontend/src/composables/__tests__/useDowntimeGridData.spec.*`
- `frontend/src/components/grids/__tests__/DowntimeEntryGrid.spec.*` (if present)
- `frontend/src/components/entries/__tests__/DowntimeEntry.spec.*`
- `frontend/src/utils/__tests__/clipboardParser.spec.ts`
- `frontend/src/stores/__tests__/productionDataStore.spec.*` (the store wraps `createDowntimeEntry`)

---

## 4. Holds (Form: HoldResumeEntry / Grid: HoldEntryGrid)

### A. Backend ground truth

- **Pydantic Create schema:** `backend/schemas/hold.py:26 WIPHoldCreate`
- **Route:** `backend/routes/holds.py:35 create_hold` at `prefix="/api/holds"` (`backend/routes/holds.py:32`). Effective URL: **`POST /api/holds`**. Resume workflow uses the approval endpoints, not a `/resume` POST: `POST /api/holds/{id}/request-resume` (`holds.py:195`), `POST /api/holds/{id}/approve-resume` (`holds.py:232`).
- **ORM model:** `backend/orm/hold_entry.py:89 HoldEntry` (table `HOLD_ENTRY`)
- **Backend adapter:** `backend/schemas/hold.py:52 from_legacy_csv` translates `hold_category` / `hold_reason` strings into canonical reason codes (`MATERIAL_INSPECTION`, `QUALITY_ISSUE`, `ENGINEERING_REVIEW`, `CUSTOMER_REQUEST`, `MISSING_SPECIFICATION`, `EQUIPMENT_UNAVAILABLE`, `CAPACITY_CONSTRAINT`, `OTHER`).

| Field | Type | Required | Constraints |
|---|---|---|---|
| `client_id` | str | **Yes** | min 1, max 50 |
| `work_order_id` | str | **Yes** | min 1, max 50 |
| `job_id` | str | No | max 50 |
| `hold_status` | str | No (default `ON_HOLD`) | max 50; must validate against `HOLD_STATUS_CATALOG` (`holds.py:178` is on update; create defaults) |
| `hold_date` | date | No | — |
| `hold_reason_category` | str | No | max 100 |
| `hold_reason` | str | No | max 50; **validated against `HOLD_REASON_CATALOG`** at route level (`holds.py:49–53`) — sending a non-catalog value 422s |
| `hold_reason_description` | str | No | — |
| `quality_issue_type` | str | No | max 100 |
| `expected_resolution_date` | date | No | — |
| `notes` | str | No | — |

> Note: there is no `quantity` field on the schema or ORM. `WIPAgingResponse.total_held_quantity` and the top-aging endpoint hard-code `quantity = 1` (`holds.py:449`) — quantity is a *display placeholder*, not a real column.

### B. Form payload (currently routed)

- **Call site:** `frontend/src/components/entries/HoldResumeEntry.vue:229` (in composable `useHoldResumeData.ts`) — actual call: `useHoldResumeData.ts:229 await api.createHoldEntry(holdData.value)`
- **API binding:** `frontend/src/services/api/dataEntry.ts:31 api.post('/holds', data)`

`holdData` (`useHoldResumeData.ts:71–80`):

| Field | Matches backend? |
|---|---|
| `work_order_id` | YES |
| `quantity` | NO — vestigial, no such column |
| `reason` | RENAMED — backend `hold_reason`. Also, values like `'Quality Issue'`, `'Material Defect'`, `'Customer Request'` are *not* the catalog codes (`QUALITY_ISSUE`, `MATERIAL_INSPECTION`, `CUSTOMER_REQUEST`) — would 422 against the catalog validator |
| `severity` | NO — vestigial |
| `description` | RENAMED — backend `hold_reason_description` |
| `required_action` | NO — vestigial |
| `initiated_by` | NO — backend `hold_initiated_by` is set server-side from `current_user`, not from payload (`hold_entry.py:126`); even if accepted, name differs |
| `customer_notification_required` | NO — vestigial |

**Form is missing required field:** `client_id`. Resume path: form calls `api.resumeHold(id, resumeData)` (`useHoldResumeData.ts:267`) which posts to `/holds/{id}/resume` (`dataEntry.ts:34`) — **this URL does not exist on the backend.** The backend's resume workflow is two stages (`request-resume` then `approve-resume`). The form's resume submit is broken regardless of payload shape.

### C. Grid payload (target of re-route)

- **Save call:** `frontend/src/composables/useHoldGridForms.ts:263 await kpiStore.createHoldEntry(data)` (store wraps `api.createHoldEntry` at `productionDataStore.ts:386`)
- **Payload built:** `useHoldGridForms.ts:246–255`

| Field | Matches backend? |
|---|---|
| `work_order_id` | YES |
| `placed_on_hold_date` | RENAMED — backend `hold_date` |
| `hold_reason` | PARTIAL — name matches but values like `'Quality Issue'` are not catalog codes (validator at `holds.py:49` will reject) |
| `expected_resume_date` | RENAMED — backend `expected_resolution_date` |
| `actual_resume_date` | NO — backend `resume_date` is server-controlled (set by `approve-resume` route), not a Create field |
| `resumed_by_user_id` | NO — backend `resumed_by` is server-controlled |
| `hold_approved_at` | NO — server-controlled (set by `approve-hold` route) |
| `resume_approved_at` | NO — server-controlled |

**Grid is missing required field:** `client_id`. The "approval workflow" buttons in `useHoldGridForms.ts:357–388` correctly call `/api/holds/{id}/approve-hold|request-resume|approve-resume` — those endpoints exist and the calls are well-formed (no body needed; backend reads `current_user` from JWT).

### D. Reconciliation gaps

- **Required-but-missing fields the grid must send:** `client_id`. (`work_order_id` is sent.)
- **Field renames needed:** `placed_on_hold_date` → `hold_date`; `expected_resume_date` → `expected_resolution_date`; remove `actual_resume_date`, `resumed_by_user_id`, `hold_approved_at`, `resume_approved_at` from Create payload (server-controlled). For form: `reason` → `hold_reason`; `description` → `hold_reason_description`; remove `quantity`, `severity`, `required_action`, `initiated_by`, `customer_notification_required`.
- **Reason value mapping table required:** UI labels (`'Quality Issue'`, `'Material Defect'`, `'Process Non-Conformance'`, `'Customer Request'`, `'Engineering Change'`, `'Inspection Failure'`, `'Supplier Issue'`, `'Other'`) → catalog codes (`QUALITY_ISSUE`, etc.). Some UI labels have no catalog code (`'Material Defect'`, `'Process Non-Conformance'`, `'Inspection Failure'`, `'Supplier Issue'`); decide whether to add catalog rows or remap to closest existing code (`MATERIAL_INSPECTION`, `OTHER`).
- **Dead fields in grid (sent, ignored or rejected):** `actual_resume_date`, `resumed_by_user_id`, `hold_approved_at`, `resume_approved_at`. (Pydantic with default `model_config` accepts extras silently and drops them — these will not 422 but they will silently no-op.)
- **Dead fields in form (sent, ignored):** `quantity`, `severity`, `required_action`, `customer_notification_required`. The form's resume tab calls a nonexistent URL — separate concern.
- **clipboardParser.ts schema alignment:** `frontend/src/utils/clipboardParser.ts:349` `hold:` schema requires `hold_date` and `work_order_id`, plus optional `quantity_held` (int). `hold_date` matches backend; `work_order_id` matches; `quantity_held` is not a backend column. Two of the three fields align — clipboard parser is mostly OK but the `quantity_held` field should be removed or recognised as ignored.

### E. Migration scope estimate

**M (4–16 hours)**, with two sub-tasks:
1. Hold create: rename + drop server-controlled fields + add reason-code mapping. Comparable to Quality.
2. Hold/resume approval flow: form's `api.resumeHold(id, data)` is a dead endpoint; either fix `dataEntry.ts:34` to call `/holds/{id}/request-resume` then `/approve-resume`, or excise the form's resume tab and route operators directly to the grid's approval-workflow buttons (which already work).

Test files that will need updating:

- `frontend/src/composables/__tests__/useHoldGridData.spec.*`
- `frontend/src/composables/__tests__/useHoldGridForms.spec.*`
- `frontend/src/composables/__tests__/useHoldResumeData.spec.*` (the form's composable)
- `frontend/src/components/grids/__tests__/HoldEntryGrid.spec.*`
- `frontend/src/components/entries/__tests__/HoldResumeEntry.spec.*`
- `frontend/src/services/api/__tests__/dataEntry.spec.*` (resume endpoint URL fix)

---

## F. Recommended migration ordering for Group A

The original plan assumed all 4 surfaces were XS pure-route-swaps (~½ day total). **All 4 are field-misaligned at the JSON boundary**, none is a pure swap. Recommended order, simplest-first to build the field-mapping pattern:

1. **Quality (first).** Field-name renames are mechanical (`inspected_quantity` → `units_inspected`, etc.); no enum mapping; clipboardParser already aligned. Build the "client_id from auth context, shift_date from grid row, payload-shape adapter" pattern here.
2. **Holds (second).** Same pattern as Quality plus a single string→catalog-code mapping table for `hold_reason`. Approval-workflow buttons already work — only the create payload needs fixing. Resume tab in the form gets the additional `dataEntry.ts:34` URL fix.
3. **Attendance (third).** Adds the `status` → (`is_absent`, `absence_type`) translation layer, plus `clock_in/clock_out` HH:MM → ISO datetime conversion. clipboardParser also needs editing.
4. **Downtime (last).** Largest divergence: enum mapping (UI category → `DowntimeReasonEnum`), unit conversion (hours → minutes), several dead UI fields (`is_resolved`, `impact_on_wip_hours`, `downtime_start_time`) to either drop or hide. Doing this last lets you reuse the adapter pattern proven in #1–#3.

---

## Group A delta to migration plan

`docs/audit/entry-surface-migration-plan.md` § 3 row 1–4 (Quality, Attendance, Downtime, Hold-Resume re-routes) and § 12 row "Group A" need amending:

- **Group A re-classified.** All 4 surfaces are field-misaligned, not pure route swaps. Total revised effort: **2–4 days** (single-engineer, sequenced) instead of the original "~½ day". Per-surface effort updated XS → **M**.
- **§ 3 effort column:** rows 1–4 update from `XS` → `M`.
- **§ 5 sequencing:** Group A retains its first-position slot (still the simplest group), but the ordering inside Group A now has a recommended simplest-first sequence (Quality → Holds → Attendance → Downtime). Add this sub-ordering as a note in § 4.1.
- **§ 12 effort summary:** "Group A — Quick wins" line should read "2–4 days" not "~½ day"; cumulative downstream rows shift by ~2 days.
- **Status column:** the inventory's "Compliant / Non-compliant" classification was based on UI-shell only; for the 4 grids in Group A, append a footnote: *"UI-compliant; payload-divergent — see `group-a-runtime-validation.md`."*

The 5.5–7-week total Phase 2 estimate increases by ~1.5–3 days at the top of the funnel.

---

## Sanity check on Group B (workflow wizard step embeds)

Group B's plan was to embed Group A's grids inside the workflow wizard steps. The wizard steps **do not currently use either the form payload shape or the grid payload shape** — they have their own ad-hoc payloads written directly against the API:

- **`WorkflowStepProduction.vue:244`** — posts to `/production-entries` (a different route from the data-entry production grid which posts to `/production`) with a hand-rolled `{ work_order_id, quantity_produced, defect_quantity, date }` shape. This payload has `quantity_produced` (which matches `backend/schemas/production.py` if it exists) and `date` (not `shift_date`). The wizard step does not import the grid composable; it's a separate code path. Endpoint `POST /production-entries` should be verified to actually exist before Group B starts.

- **`WorkflowStepDowntime.vue:307`** — `PATCH /downtime/{id}/resolve` with `{ end_time, root_cause, resolution }`. This is an *update* path, not a *create* path; the wizard step does not create downtime, it resolves existing ones. The backend endpoint `PATCH /downtime/{id}/resolve` does **not exist** in `backend/routes/downtime.py` (only `PUT /downtime/{id}` for updates). The error path falls through to a hard-coded local-state mutation (`WorkflowStepDowntime.vue:325–331`) — it currently appears to "work" only because errors are swallowed.

- **`WorkflowStepAttendance.vue`** — does **not save anything**. It only reads `/employees/shift-roster` and `/stations` (lines 268–269); employee presence/station assignment is held in local state and emitted upward. There is no `api.create*` call.

**Implication for Group B:** the wizard steps don't inherit Group A's payload bugs because they don't share the payload code at all. They have their own, separate set of issues — at least one nonexistent endpoint (`PATCH /downtime/{id}/resolve`), one possibly-nonexistent endpoint (`POST /production-entries`), and one step that doesn't persist (`WorkflowStepAttendance`). Group B will require its own backend-route runtime validation pass before embedding the Group A grids; the embed itself will not magically fix the wizard's ad-hoc API surface. Recommend adding a "Group B Phase 0" runtime-validation pre-task to the migration plan.

