# Capacity — Standards Worksheet — Surface Brief

**Route:** tab inside `/capacity-planning`
**View:** `frontend/src/views/CapacityPlanning/components/grids/StandardsGrid.vue`
**Composable:** `frontend/src/composables/useStandardsGridData.ts`
**Persistence:** workbook-level via `useCapacityPlanningStore.saveWorksheet('standards')`
**Backend canonical schema:** `backend/routes/capacity/_models.py` `ProductionStandardCreate`

Migrated 2026-05-01 from a v-data-table + per-cell editors to AG Grid (Group D Surface #21 of inventory).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Style | `style_model` | text (pinned left) | required |
| Process | `process_step` | text | required |
| Standard SAM (min) | `standard_sam` | `agNumberCellEditor` | ≥ 0, 4 decimals |
| Standard Hours | `standard_hours` | `agNumberCellEditor` | ≥ 0, 4 decimals |
| Operators Required | `operators_required` | `agNumberCellEditor` | integer ≥ 0 |
| Effective Date | `effective_date` | `agDateStringCellEditor` | optional (YYYY-MM-DD) |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional |
| Actions | — | inline delete | row-action chip |

`client_id` flows through the workbook store.

---

## Validation rules

1. **Per-cell editor constraints** — `min: 0` on all numeric fields.
2. **Workbook-level save** — `worksheets.standards.dirty = true` on every cell change; persisted via `store.saveWorksheet('standards')`.
3. **Backend Pydantic** — `ProductionStandardCreate` requires `style_model` and `process_step`. 422s rollback via `loadWorkbook()`.

---

## CSV format

CSV import / export use the AGGridBase toolbar. Header row:

```
style_model,process_step,standard_sam,standard_hours,operators_required,effective_date,notes
```

---

## Tests

- `frontend/src/composables/__tests__/useStandardsGridData.spec.ts` — covers column shape, numeric editor parameters, dirty-flag propagation, and addRow/removeRow store-bound wrappers.
