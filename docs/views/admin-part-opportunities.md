# Admin — Part Opportunities — Surface Brief

**Route:** `/admin/part-opportunities`
**View:** `frontend/src/views/admin/PartOpportunities.vue`
**Composable:** `frontend/src/composables/usePartOpportunitiesGridData.ts`
**Backend canonical schema:** `backend/schemas/part_opportunity.py`
**Backend endpoints:** `POST /part-opportunities`, `PUT /part-opportunities/{id}`, `DELETE /part-opportunities/{id}`, `POST /part-opportunities/upload-csv`

Migrated 2026-05-01 from a v-data-table list + create/edit dialog to inline AG Grid (Group E Surface #47).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Part Number | `part_number` | text (pinned left) | required, locked after creation; new rows only |
| Description | `part_description` | text | optional |
| Opportunities Per Unit | `opportunities_per_unit` | `agNumberCellEditor` | required, integer ≥ 1 |
| Complexity | `complexity` | `agSelectCellEditor` | values from `COMPLEXITY_OPTIONS` (LOW / MEDIUM / HIGH) |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional |
| Active | `is_active` | boolean editor | default true |
| Actions | — | Save+Cancel for new rows; delete confirmation for existing | row-action chip |

Per-client filter via `selectedClient` from `usePartOpportunitiesData`.

---

## Validation rules

1. **Per-cell editor constraints** — `min: 1` on `opportunities_per_unit`; complexity enum constrained.
2. **Required-field check before POST** — asserts `part_number` and `opportunities_per_unit > 0`.
3. **Inline-edit autosave** — every cell-value change on existing rows PUTs immediately; failures rollback.
4. **Backend Pydantic** — `PartOpportunityCreate` requires `part_number` (unique within client) and `opportunities_per_unit > 0`.

---

## CSV format

CSV import / export use the AGGridBase toolbar AND a dedicated CSV-upload dialog with a `replaceExisting` checkbox (Exception 4).

Header row:
```
part_number,part_description,opportunities_per_unit,complexity,notes,is_active
```

Downloadable template available via the `Download Template` button.

The view also exposes summary stats (total parts / avg / min / max opportunities) and an in-line "How to Use" guide (Exception 4 — read-only).

---

## Tests

- `frontend/src/composables/__tests__/usePartOpportunitiesGridData.spec.ts` — covers `COMPLEXITY_OPTIONS` enum, column shape, addRow defaults, saveNewRow validation + POST, removeNewRow, onCellValueChanged PUT + rollback.
