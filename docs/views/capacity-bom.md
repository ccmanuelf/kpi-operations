# Capacity — BOM Worksheet — Surface Brief

**Route:** tab inside `/capacity-planning`
**View:** `frontend/src/views/CapacityPlanning/components/grids/BOMGrid.vue`
**Composable:** `frontend/src/composables/useBOMGridData.ts`
**Persistence:** workbook-level via `useCapacityPlanningStore.saveWorksheet('bom')`
**Backend canonical schema:** `backend/routes/capacity/_models.py` `BOMHeaderCreate` / `BOMComponentCreate`

Migrated 2026-05-01 as a master-detail surface using two stacked AGGridBase grids — the AG Grid Community Edition equivalent of Enterprise's `masterDetail` config (Group F Surface #16 of inventory).

---

## Master grid (BOM Headers)

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| BOM ID | `bom_id` | text (pinned left) | required, unique |
| Style | `style_model` | text | required |
| Description | `description` | text | optional |
| Effective Date | `effective_date` | `agDateStringCellEditor` | optional |
| Components Count | (computed) | read-only `valueGetter` | counts the selected BOM's components |
| Active | `is_active` | boolean editor | default true |
| Actions | — | inline select / delete | clicking a row sets `selectedBOMIndex`, populating the child grid |

## Detail grid (BOM Components, populated when a master row is selected)

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Item Code | `item_code` | text | required |
| Description | `item_description` | text | optional |
| Quantity | `quantity` | `agNumberCellEditor` | required, ≥ 0 |
| UoM | `unit_of_measure` | text or select | optional |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional |
| Actions | — | inline delete | — |

`client_id` flows through the workbook store.

---

## Validation rules

1. **Selection-driven detail rendering** — the child grid only renders when `selectedBOMIndex !== null`; this is the master-detail Community fallback.
2. **Per-cell editor constraints** — `min: 0` on `quantity`.
3. **Workbook-level save** — both header and component edits set `worksheets.bom.dirty = true`; persisted via `store.saveWorksheet('bom')`.
4. **Backend Pydantic** — header `bom_id` and `style_model` required; component `item_code` and `quantity > 0` required.

---

## CSV format

The master and detail grids each have their own AGGridBase toolbar (separate Import/Export buttons).

Header CSV:
```
bom_id,style_model,description,effective_date,is_active
```

Component CSV (re-imports against the currently-selected master row):
```
item_code,item_description,quantity,unit_of_measure,notes
```

---

## Tests

- `frontend/src/composables/__tests__/useBOMGridData.spec.ts` — covers master + detail column shape, components-count valueGetter, selection state, dirty-flag propagation across both grids.
