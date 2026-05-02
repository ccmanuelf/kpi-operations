# Capacity — Stock Worksheet — Surface Brief

**Route:** tab inside `/capacity-planning`
**View:** `frontend/src/views/CapacityPlanning/components/grids/StockGrid.vue`
**Composable:** `frontend/src/composables/useStockGridData.ts`
**Persistence:** workbook-level via `useCapacityPlanningStore.saveWorksheet('stock')`
**Backend canonical schema:** `backend/routes/capacity/_models.py` `StockSnapshotCreate`

Migrated 2026-05-01 from a v-data-table + per-cell editors to AG Grid (Group D Surface #24 of inventory).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Item Code | `item_code` | text (pinned left) | required, unique within snapshot |
| Item Description | `item_description` | text | optional |
| On Hand | `on_hand_quantity` | `agNumberCellEditor` | ≥ 0 |
| Allocated | `allocated_quantity` | `agNumberCellEditor` | ≥ 0 |
| On Order | `on_order_quantity` | `agNumberCellEditor` | ≥ 0 |
| Available | (computed) | read-only `valueGetter` | `= on_hand − allocated` |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional |
| Actions | — | inline delete | row-action chip |

A search filter (`v-text-field`) above the grid is Exception 3 (filter input). The CSV-paste import dialog accepts the same header schema as the AGGridBase toolbar import.

---

## Validation rules

1. **Per-cell editor constraints** — `min: 0` on all numeric fields.
2. **Workbook-level save** — edits accumulate; persisted via `store.saveWorksheet('stock')`.
3. **Backend Pydantic** — `StockSnapshotCreate` requires `item_code`. 422s rollback via `loadWorkbook()`.

---

## CSV format

CSV import / export use the AGGridBase toolbar. Header row:

```
item_code,item_description,on_hand_quantity,allocated_quantity,on_order_quantity,notes
```

A legacy CSV-paste textarea dialog also accepts the same schema (Exception 4 — single-action data import).

---

## Tests

- `frontend/src/composables/__tests__/useStockGridData.spec.ts` — covers column shape, available-stock valueGetter, dirty-flag propagation.
