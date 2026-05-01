# Hold/Resume Entry — Surface Brief

**Route:** `/data-entry/hold-resume`
**Wrapper view:** `frontend/src/views/HoldResumeEntry.vue`
**Grid component:** `frontend/src/components/grids/HoldEntryGrid.vue`
**Composables:** `frontend/src/composables/useHoldGridData.ts` (state + columns) and `useHoldGridForms.ts` (CRUD + approval workflow)
**Backend canonical schema:** `backend/schemas/hold.py` `WIPHoldCreate`
**Backend ORM:** `backend/orm/hold_entry.py` (`HOLD_ENTRY` table)
**Backend route:** `backend/routes/holds.py` (mounted at `/api/holds`)

This surface migrated from a `v-form`-based component (`components/entries/HoldResumeEntry.vue`) to the AG Grid spreadsheet pattern on 2026-05-01 as Surface #2 of the entry-interface audit (`docs/audit/entry-surface-migration-plan.md`, Group A).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Hold Date | `hold_date` | `agDateStringCellEditor` | optional but recommended (YYYY-MM-DD); pinned-left, default sort desc |
| Work Order | `work_order_id` | `agSelectCellEditor` | required, populated from `useProductionDataStore.workOrders` |
| Hold Reason | `hold_reason` | `agSelectCellEditor` | optional; values are the canonical `HOLD_REASON_CODES` (8 codes — see below) |
| Hold Description | `hold_reason_description` | `agLargeTextCellEditor` (popup) | optional free text |
| Status | `hold_status` | read-only | server-controlled; defaults to `ON_HOLD` on create; transitions via approval endpoints |
| Expected Resolution | `expected_resolution_date` | `agDateStringCellEditor` | optional |
| Resume Date | `resume_date` | read-only | server-set by `approve-resume` route |
| Days on Hold | (computed) | read-only `valueGetter` | `differenceInDays(resume_date ?? now, hold_date)`; >7 red, >3 amber |
| Initiated By | `hold_initiated_by` | read-only | server-set from `current_user` on create |
| Approved By | `hold_approved_by` | read-only | server-set by `approve-hold` route |
| Resumed By | `resumed_by` | read-only | server-set by `approve-resume` route |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional free text |
| Actions (column override in grid wrapper) | — | inline buttons | conditional on hold_status: Approve Hold / Request Resume / Approve Resume / Delete |

`client_id` is **not a column** — it is derived from `useAuthStore().user.client_id_assigned` (operators) or `useKPIStore().selectedClient` (admin). Save aborts with `grids.holds.errors.noClient` if neither is set.

`hold_status` defaults to `ON_HOLD` server-side; the create payload does not send it.

---

## HOLD_REASON_CODES catalog

Canonical reason codes that mirror `backend/schemas/hold.py:56–71`. The set is enforced server-side per-client via `validate_hold_reason_for_client`; the grid sends the code, not a UI label.

| Code | Typical use |
|---|---|
| `QUALITY_ISSUE` | Defects detected requiring inspection or rework |
| `MATERIAL_INSPECTION` | Material defects, supplier-side issues |
| `ENGINEERING_REVIEW` | Engineering change request, design clarification |
| `CUSTOMER_REQUEST` | Customer-initiated hold |
| `MISSING_SPECIFICATION` | Missing or unclear specification, drawing |
| `EQUIPMENT_UNAVAILABLE` | Equipment downtime blocking continuation |
| `CAPACITY_CONSTRAINT` | Capacity reallocation hold |
| `OTHER` | Anything not covered above |

Legacy UI labels (`'Quality Issue'`, `'Material Defect'`, `'Process Non-Conformance'`, etc.) were removed in this migration. Operators select from the 8 codes directly via the dropdown.

---

## Validation rules

1. **Per-cell editor constraints** — typed editors (`agDateStringCellEditor`, `agSelectCellEditor`) constrain entry shape.
2. **Pre-save check** — `saveChanges` aborts with snackbar error if no `client_id` is resolvable from auth/kpi stores.
3. **Backend Pydantic** — `WIPHoldCreate` requires `client_id` (1–50 chars), `work_order_id` (1–50 chars). All other fields optional.
4. **Backend route validator** — `holds.py:49–53` validates `hold_reason` against the per-client `HOLD_REASON_CATALOG` and 422s if absent.

---

## Approval workflow

The grid does **not** send approval-state fields on create. Instead, three buttons in the actions column drive the workflow against the backend's existing endpoints:

| Trigger state | Button | Backend endpoint |
|---|---|---|
| `PENDING_HOLD_APPROVAL` | Approve Hold | `POST /holds/{id}/approve-hold` |
| `ON_HOLD` | Request Resume | `POST /holds/{id}/request-resume` |
| `PENDING_RESUME_APPROVAL` | Approve Resume | `POST /holds/{id}/approve-resume` |

These endpoints take no body — the backend reads `current_user` from the JWT. `hold_status`, `hold_approved_by`, `resumed_by`, `resume_date` are all updated server-side.

The legacy resume dialog (which set `actual_resume_date`/`resumed_by_user_id` locally and sent them to a non-existent `POST /holds/{id}/resume` URL) has been removed entirely. The dead URL was also removed from `services/api/dataEntry.ts`.

---

## CSV format

The legacy form referenced a `CSVUploadDialogHold` component that **does not exist** in the repo — CSV file import for Holds was non-functional. The grid retains Excel-style **clipboard paste** via `AGGridBase` + `useAGGridBase.handlePasteFromExcel`, with the parser schema at `frontend/src/utils/clipboardParser.ts` `hold:`:

```
hold_date (required, date)
work_order_id (required, string)
hold_reason (string)
hold_reason_description (string)
expected_resolution_date (date)
notes (string)
```

A first-class CSV file upload dialog is a future enhancement and should mirror the `CSVUploadDialogQuality.vue` pattern.

---

## Tests

- `frontend/src/composables/__tests__/useHoldGridData.spec.ts` — 31 tests covering catalog codes, column-shape conformance to backend schema (verifies absence of legacy `placed_on_hold_date` / `expected_resume_date` / `actual_resume_date` / `resumed_by_user_id` / `hold_approved_at` / `resume_approved_at` columns), days_on_hold valueGetter, aggregate counts, avgDaysOnHold, and applyFilters behavior.
- The legacy form spec (`frontend/src/components/__tests__/HoldResumeEntry.spec.ts`, 28 tests) was deleted.
- The resumeHold test in `services/__tests__/dataEntry.spec.ts` was deleted (the URL it tested no longer exists).
- Net: +2 tests.
