# Floating Pool Management — Surface Brief

**Route:** `/admin/floating-pool`
**View:** `frontend/src/views/admin/FloatingPoolManagement.vue`
**Composables:** `frontend/src/composables/useFloatingPoolData.ts` (load + summary + filters), `useFloatingPoolGridData.ts` (grid columns + assign/unassign routing)
**Backend canonical schema:** `backend/schemas/floating_pool.py` `FloatingPoolAssignmentRequest`, `FloatingPoolUnassignmentRequest`

Migrated 2026-05-01 from a v-data-table + 5-field assign/edit dialog to inline AG Grid (Group H Surface #21). Pool membership is owned elsewhere (employee admin), so this view has **no Add Row** — operators only assign / unassign / re-tune existing pool entries.

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Employee ID | `employee_id` | read-only (pinned left) | — |
| Employee Name | `employee_name` | read-only (pinned left) | — |
| Status | (computed) | read-only chip | `ASSIGNED` / `AVAILABLE` based on `current_assignment` |
| Assigned To | `current_assignment` | `agSelectCellEditor` | values = loaded client list + `null`; cleared → unassign, set → assign |
| Available From | `available_from` | `agDateStringCellEditor` | optional; on assigned row, edits re-fire `/assign` |
| Available To | `available_to` | `agDateStringCellEditor` | optional; on assigned row, edits re-fire `/assign` |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional; on assigned row, edits re-fire `/assign` |
| Actions | — | Unassign quick-action button (assigned rows only) | em-dash placeholder for unassigned |

---

## Validation rules

The composable's `onCellValueChanged` is the policy router:

1. **`current_assignment` change** — clearing fires `POST /floating-pool/unassign { pool_id }`; setting fires `POST /floating-pool/assign { employee_id, client_id, available_from, available_to, notes }`.
2. **Date / notes change on an assigned row** — re-fires `/assign` with the row's current dates + notes (matches legacy "edit dialog re-POST" semantics).
3. **Date / notes change on an unassigned row** — local-only; no endpoint to set window without a client from this surface.
4. **Backend Pydantic** — `FloatingPoolAssignmentRequest` requires `employee_id > 0` and `client_id` (1–50 chars). 422s rollback by calling `fetchData()`.

---

## CSV format

CSV import / export use the AGGridBase toolbar. Header row:

```
employee_id,employee_name,current_assignment,available_from,available_to,notes
```

CSV-driven mass assignment is supported through the same shared paste pipeline. Note: `pool_id` is not exported (server-controlled), so re-importing an exported CSV creates fresh assignments rather than updating existing ones.

The view also exposes summary cards (total / available / assigned / utilization%), status & client filters, the Simulation Insights expansion panel (`getFloatingPoolSimulationInsights`), and the read-only `FloatingPoolGuideDialog`.

---

## Tests

- `frontend/src/composables/__tests__/useFloatingPoolGridData.spec.ts` — 21 tests covering column shape, status valueGetter, assign / unassign / re-fire-assign routing, error rollback via `fetchData`, actions cell renderer.
- E2E spec: `frontend/e2e/floating-pool.spec.ts`.
