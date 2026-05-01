# Downtime Entry — Surface Brief

**Route:** `/data-entry/downtime`
**Wrapper view:** `frontend/src/views/DowntimeEntry.vue`
**Grid component:** `frontend/src/components/grids/DowntimeEntryGrid.vue`
**Composable:** `frontend/src/composables/useDowntimeGridData.ts`
**Backend canonical schema:** `backend/schemas/downtime.py` `DowntimeEventCreate`
**Backend ORM:** `backend/orm/downtime_entry.py` (`DOWNTIME_ENTRY` table)
**Backend route:** `backend/routes/downtime.py` (mounted at `/api/downtime`)

This surface migrated from a `v-form`-based component (`components/entries/DowntimeEntry.vue`) to the AG Grid spreadsheet pattern on 2026-05-01 as Surface #4 of the entry-interface audit (`docs/audit/entry-surface-migration-plan.md`, Group A). It was the most divergent of the 4 Group A surfaces — both the form and the grid were sending fields the backend ignored, and reasons used UI-only English labels rather than the backend enum.

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Shift Date | `shift_date` | `agDateStringCellEditor` | required (YYYY-MM-DD); pinned-left, default sort desc |
| Work Order | `work_order_id` | `agSelectCellEditor` | optional; populated from `useProductionDataStore.workOrders` |
| Reason | `downtime_reason` | `agSelectCellEditor` | required; values are `DOWNTIME_REASON_CODES` (7 codes — see below) |
| Duration (min) | `downtime_duration_minutes` | `agNumberCellEditor` | required, integer 1–1440 (max 24 h); cell turns amber ≥120 min, red ≥240 min |
| Machine ID | `machine_id` | text | optional, ≤100 chars |
| Equipment Code | `equipment_code` | text | optional, ≤50 chars |
| Root Cause Category | `root_cause_category` | text | optional, ≤100 chars |
| Corrective Action | `corrective_action` | `agLargeTextCellEditor` (popup) | optional free text |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional free text |
| Actions | — | inline delete button | confirms before removing row |

`client_id` is **not a column** — it is derived from `useAuthStore().user.client_id_assigned` (operators) or `useKPIStore().selectedClient` (admin). Save aborts with `grids.downtime.errors.noClient` if neither is set.

---

## DOWNTIME_REASON_CODES catalog

Canonical enum codes that mirror `backend/schemas/downtime.py:13-22 DowntimeReasonEnum`.

| Code | Typical use |
|---|---|
| `EQUIPMENT_FAILURE` | Unplanned equipment breakdown |
| `MATERIAL_SHORTAGE` | Production halted waiting for material |
| `SETUP_CHANGEOVER` | Tooling / setup changeover between runs |
| `QUALITY_HOLD` | Production halted by quality issue |
| `MAINTENANCE` | Planned preventive maintenance |
| `POWER_OUTAGE` | Power loss |
| `OTHER` | Anything not covered above |

Legacy UI categories (`'Planned Maintenance'`, `'Unplanned Breakdown'`, `'Changeover'`, `'Material Shortage'`, `'Quality Issue'`, `'Operator Absence'`, `'Other'`) were removed in this migration. Operators select from the 7 codes directly.

---

## What changed vs the legacy grid/form

**Renamed:**
- `downtime_start_time` (datetime) → `shift_date` (date). The backend tracks the shift; per-event start timestamps were never stored.
- `duration_hours` (decimal) → `downtime_duration_minutes` (integer ×60). Backend stores minutes for KPI calculation precision.
- `resolution_notes` → `corrective_action` (matches backend field name).
- `category` (UI label) → `downtime_reason` (catalog code). The two were redundant; the grid had both `category` *and* `downtime_reason` columns sending different values.

**Dropped (vestigial — backend has no equivalent):**
- `impact_on_wip_hours` — UI-only metric
- `is_resolved` — UI-only flag (no backend `resolved` field)
- `resolution_notes` (replaced by `corrective_action`)

**Added (backend-supported, not exposed before):**
- `machine_id`, `equipment_code` — for maintenance tracking
- `root_cause_category` — for analysis
- `corrective_action` — replaces resolution_notes

**Filter changes:**
- `categoryFilter` (legacy) → `reasonFilter` (catalog code dropdown)
- `statusFilter` (Resolved/Unresolved) — dropped; the resolved/unresolved aggregation is no longer tracked
- `dateFilter` now filters on `shift_date` rather than `downtime_start_time`

---

## Validation rules

1. **Per-cell editor constraints** — `downtime_duration_minutes` editor enforces `min: 1, max: 1440, precision: 0`. `downtime_reason` editor restricts to `DOWNTIME_REASON_CODES`.
2. **Pre-save check** — `saveChanges` aborts with snackbar error if no `client_id` is resolvable from auth/kpi stores.
3. **Backend Pydantic** — `DowntimeEventCreate` requires `client_id` (1–50 chars), `shift_date`, `downtime_reason` (enum value), `downtime_duration_minutes` (>0, ≤1440). All other fields optional.

---

## CSV format

CSV import is wired into the wrapper view's header via `frontend/src/components/CSVUploadDialogDowntime.vue`. Backend endpoint: `POST /downtime/upload/csv`.

Excel-style **clipboard paste** uses `frontend/src/utils/clipboardParser.ts` `downtime:` schema:

```
shift_date (required, date)
downtime_duration_minutes (required, number 0–1440)
downtime_reason (required, string — must match a DOWNTIME_REASON_CODES value)
machine_id (string)
equipment_code (string)
corrective_action (string)
notes (string)
```

Renamed in this migration: `downtime_minutes` → `downtime_duration_minutes`. Added `downtime_reason` as required (matches backend Pydantic).

---

## Tests

- `frontend/src/composables/__tests__/useDowntimeGridData.spec.ts` — 25 tests covering catalog codes, column-shape conformance to backend schema (verifies absence of legacy `downtime_start_time` / `category` / `impact_on_wip_hours` / `is_resolved` / `resolution_notes` / `duration_hours` columns + presence of `machine_id` / `equipment_code` / `root_cause_category` / `corrective_action`), aggregations (totalMinutes / totalHours / eventCount), applyFilters (date/reason/line), and initial state.
- The legacy form spec (`frontend/src/components/__tests__/DowntimeEntry.spec.ts`, 18 tests) was deleted.
- Net: +7 tests.
