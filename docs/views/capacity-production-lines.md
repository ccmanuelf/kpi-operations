# Capacity — Production Lines Worksheet — Surface Brief

**Route:** tab inside `/capacity-planning`
**View:** `frontend/src/views/CapacityPlanning/components/grids/ProductionLinesGrid.vue`
**Composable:** `frontend/src/composables/useProductionLinesGridData.ts`
**Persistence:** workbook-level via `useCapacityPlanningStore.saveWorksheet('productionLines')` → `PUT /capacity/...`
**Backend canonical schema:** `backend/routes/capacity/_models.py` `ProductionLineCreate`

Migrated 2026-05-01 from a v-data-table + per-cell `v-text-field`/`v-select` to AG Grid (Group D Surface #19 of inventory).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Line Code | `line_code` | text (pinned left) | required, unique within client |
| Line Name | `line_name` | text | required |
| Department | `department` | text or select | optional |
| Capacity / Hour | `capacity_per_hour` | `agNumberCellEditor` | optional, ≥ 0 |
| Capacity / Day | `capacity_per_day` | `agNumberCellEditor` | optional, ≥ 0 |
| Operators | `operators_count` | `agNumberCellEditor` | integer ≥ 0 |
| Active | `is_active` | checkbox / boolean editor | default true |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional |
| Actions | — | inline delete | row-action chip |

`client_id` flows through the workbook store from `useWorkbookStore.clientId`.

---

## Validation rules

1. **Per-cell editor constraints** — numeric fields use `min: 0`.
2. **Workbook-level save** — edits accumulate in `worksheets.productionLines.data` with `dirty: true`. The panel Save button triggers `store.saveWorksheet('productionLines')`.
3. **Backend Pydantic** — `ProductionLineCreate` requires `line_code` and `line_name`. 422s rollback via `loadWorkbook()`.

---

## CSV format

CSV import / export use the AGGridBase toolbar. Header row:

```
line_code,line_name,department,capacity_per_hour,capacity_per_day,operators_count,is_active,notes
```

Round-trip safe: column field names match the export and import header.

---

## Tests

- `frontend/src/composables/__tests__/useProductionLinesGridData.spec.ts` — covers column shape, addRow defaults, dirty-flag propagation, and store-bound CRUD wrappers.
