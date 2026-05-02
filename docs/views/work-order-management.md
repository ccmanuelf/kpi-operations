# Work Order Management — Surface Brief

**Route:** `/work-orders`
**View:** `frontend/src/views/WorkOrderManagement.vue`
**Composables:** `frontend/src/composables/useWorkOrderData.ts` (load + filters), `useWorkOrderForms.ts` (delete + status transitions), `useWorkOrderGridData.ts` (grid columns + autosave)
**Backend canonical schema:** `backend/schemas/work_order.py` `WorkOrderCreate` / `WorkOrderUpdate`

Migrated 2026-05-01 from a v-data-table list + 12-field create/edit dialog to inline AG Grid (Group H Surface #19).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Work Order ID | `work_order_id` | text (pinned left) | required, locked after creation (natural key) |
| Style | `style_model` | text | required |
| Quantity Ordered | `planned_quantity` | `agNumberCellEditor` | required, integer ≥ 1 |
| Quantity Completed | `actual_quantity` | `agNumberCellEditor` | integer ≥ 0, default 0 |
| Progress | (computed) | read-only progress bar renderer | `= min(100, round(actual / planned × 100))` |
| Status | `status` | `agSelectCellEditor` | one of `WORK_ORDER_STATUS_OPTIONS` (RECEIVED, RELEASED, DEMOTED, ACTIVE, IN_PROGRESS, ON_HOLD, COMPLETED, SHIPPED, CLOSED, REJECTED, CANCELLED) |
| Priority | `priority` | `agSelectCellEditor` | one of HIGH / MEDIUM / LOW (optional) |
| Planned Start | `planned_start_date` | `agDateStringCellEditor` | optional (YYYY-MM-DD) |
| Planned End | `planned_ship_date` | `agDateStringCellEditor` | optional; cell turns red and prepends ⚠ when overdue |
| Cycle Time | `ideal_cycle_time` | `agNumberCellEditor` | optional, ≥ 0, 4 decimals |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional free text |
| Actions | — | Save+Cancel for new rows; Detail+Delete for existing | row-action chip |

`client_id` is resolved from `useAuthStore().user.client_id_assigned` falling back to `useKPIStore().selectedClient`. Save aborts with a notification if neither is set.

---

## Validation rules

1. **Per-cell editor constraints** — `min: 1` on `planned_quantity`, `min: 0` on `actual_quantity` and `ideal_cycle_time`, AG Grid blocks entry of out-of-range values.
2. **Required-field check before POST** — `requiredFieldsPresent(row)` asserts `work_order_id`, `style_model`, and `planned_quantity > 0`. Pre-save fail surfaces `workOrders.errors.fillRequired`.
3. **Backend Pydantic** — `WorkOrderCreate` requires `work_order_id`, `client_id`, `style_model`, `planned_quantity > 0`. Mismatched payloads 422; `loadWorkOrders()` re-fetches to recover row state.

Existing rows: every cell-value change PUTs to `/work-orders/{work_order_id}` immediately. Failures rollback by reloading from the server.
New rows: accumulate locally with `_isNew: true` until the operator clicks the green Save button → POST `/work-orders`.

Status transitions (`updateStatus`) flow through `transitionWorkOrder` (`/workflow`) with a direct `/work-orders/{id}` PUT fallback.

---

## CSV format

CSV import / export both use the AGGridBase toolbar (default `enableCsvImport: true`, `enableExport: true`). Header row matches column field names:

```
work_order_id,style_model,planned_quantity,actual_quantity,status,priority,planned_start_date,planned_ship_date,ideal_cycle_time,notes
```

Round-trip safe: exporting a grid and re-importing the same file replays unchanged.

---

## Tests

- `frontend/src/composables/__tests__/useWorkOrderGridData.spec.ts` — 30 tests covering `WORK_ORDER_STATUS_OPTIONS` / `WORK_ORDER_PRIORITY_OPTIONS` enums, `calculateProgress` helper, `isOverdue` helper, column shape, addRow defaults, saveNewRow validation + POST, removeNewRow, onCellValueChanged PUT + rollback.
