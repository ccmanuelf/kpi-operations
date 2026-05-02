# Admin — Defect Types — Surface Brief

**Route:** `/admin/defect-types`
**View:** `frontend/src/views/admin/AdminDefectTypes.vue`
**Composables:** `frontend/src/composables/useDefectTypesData.ts` (load + filters), `useDefectTypesForms.ts` (CSV upload + delete confirmation), `useDefectTypesGridData.ts` (grid columns + autosave)
**Backend canonical schema:** `backend/schemas/defect_type_catalog.py`
**Backend endpoints:** `POST /defect-type-catalog`, `PUT /defect-type-catalog/{id}`, `DELETE /defect-type-catalog/{id}`, `POST /defect-type-catalog/upload-csv`

Migrated 2026-05-01 from a v-data-table list + create/edit dialog to inline AG Grid (Group E Surface #14). Per-client × many-defect-types is operational data, not config — treated as Spreadsheet Standard despite the admin location.

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Defect Code | `defect_code` | text (pinned left) | required, locked after creation; new rows only |
| Defect Name | `defect_name` | text | required |
| Severity Default | `severity_default` | `agSelectCellEditor` | values from `SEVERITY_OPTIONS` (LOW / MEDIUM / HIGH / CRITICAL) |
| Category | `category` | `agSelectCellEditor` | values from `CATEGORY_OPTIONS` |
| Description | `description` | text | optional |
| Active | `is_active` | boolean editor | default true |
| Actions | — | Save+Cancel for new rows; delete confirmation for existing | row-action chip |

Client selection driver: `selectedClient` in `useDefectTypesData`. The view supports a global (system-wide) catalog mode via `GLOBAL_CLIENT_ID`.

---

## Validation rules

1. **Per-cell editor constraints** — selects bound to the catalog enums.
2. **Required-field check before POST** — asserts `defect_code`, `defect_name`, and `severity_default` are set; `defect_code` is locked after creation.
3. **Inline-edit autosave** — every cell-value change on existing rows PUTs immediately; failures rollback by reloading.
4. **Backend Pydantic** — `DefectTypeCatalogCreate` requires `defect_code`, `defect_name`, `severity_default`. `defect_code` is unique within a client.

---

## CSV format

CSV import / export use the AGGridBase toolbar AND a dedicated CSV-upload dialog (`AdminDefectTypes.vue` lines 115-154 — Exception 4 file picker with `replaceExisting` checkbox).

Header row:
```
defect_code,defect_name,severity_default,category,description,is_active
```

A downloadable template is also exposed (`Download Template` button → `downloadTemplate()`).

---

## Tests

- `frontend/src/composables/__tests__/useDefectTypesGridData.spec.ts` — covers `SEVERITY_OPTIONS` / `CATEGORY_OPTIONS`, column shape, addRow defaults, saveNewRow validation + POST, removeNewRow, onCellValueChanged PUT + rollback.
