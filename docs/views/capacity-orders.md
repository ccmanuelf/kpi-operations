# Capacity — Orders Worksheet — Surface Brief

**Route:** tab inside `/capacity-planning`
**View:** `frontend/src/views/CapacityPlanning/components/grids/OrdersGrid.vue`
**Composable:** `frontend/src/composables/useOrdersGridData.ts`
**Persistence:** workbook-level via `useCapacityPlanningStore.saveWorksheet('orders')`
**Backend canonical schema:** `backend/routes/capacity/_models.py` `OrderCreate`

Migrated 2026-05-01 from a v-data-table + per-cell editors to AG Grid (Group D Surface #20 of inventory).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Order Number | `order_number` | text (pinned left) | required, unique within client |
| Customer | `customer_name` | text | optional |
| Style | `style_model` | text | required |
| Quantity | `quantity` | `agNumberCellEditor` | required, integer ≥ 1 |
| Priority | `priority` | `agSelectCellEditor` | one of LOW / NORMAL / HIGH / URGENT |
| Status | `status` | `agSelectCellEditor` | one of `OrderStatus` enum |
| Due Date | `due_date` | `agDateStringCellEditor` | optional |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional |
| Actions | — | inline delete | row-action chip |

**Bug fix during this migration:** the legacy UI offered `CRITICAL` priority but the backend `OrderPriority` enum is `LOW / NORMAL / HIGH / URGENT`. The grid now mirrors the backend enum exactly.

`client_id` flows through the workbook store.

---

## Validation rules

1. **Per-cell editor constraints** — `min: 1` on `quantity`; priority/status constrained to enum values.
2. **Workbook-level save** — edits accumulate in `worksheets.orders.data`; persisted via `store.saveWorksheet('orders')`.
3. **Backend Pydantic** — `OrderCreate` requires `order_number`, `style_model`, and `quantity > 0`. 422s rollback via `loadWorkbook()`.

---

## CSV format

CSV import / export use the AGGridBase toolbar. Header row:

```
order_number,customer_name,style_model,quantity,priority,status,due_date,notes
```

---

## Tests

- `frontend/src/composables/__tests__/useOrdersGridData.spec.ts` — covers column shape, `OrderPriority` / `OrderStatus` enum alignment with backend, dirty-flag propagation.
