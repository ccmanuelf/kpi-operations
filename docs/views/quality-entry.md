# Quality Entry — Surface Brief

**Route:** `/data-entry/quality`
**Wrapper view:** `frontend/src/views/QualityEntry.vue`
**Grid component:** `frontend/src/components/grids/QualityEntryGrid.vue`
**Composable:** `frontend/src/composables/useQualityGridData.ts`
**Backend canonical schema:** `backend/schemas/quality.py` `QualityInspectionCreate`
**Backend ORM:** `backend/orm/quality_entry.py` (`QUALITY_ENTRY` table)

This surface migrated from a `v-form`-based entry component (`components/entries/QualityEntry.vue`) to the AG Grid spreadsheet pattern on 2026-05-01 as Surface #1 of the entry-interface audit (`docs/audit/entry-surface-migration-plan.md`, Group A).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Shift Date | `shift_date` | `agDateStringCellEditor` | required (YYYY-MM-DD) |
| Work Order | `work_order_id` | text | required, non-empty |
| Inspected Qty | `units_inspected` | `agNumberCellEditor` | required, integer ≥ 1 |
| Passed Qty | `units_passed` (computed) | read-only `valueGetter` | `= max(0, units_inspected − units_defective)` |
| Defect Qty | `units_defective` | `agNumberCellEditor` | integer ≥ 0; cell turns red when > 0 |
| Total Defects | `total_defects_count` | `agNumberCellEditor` | integer ≥ 0; auto-defaults to `units_defective` on first defect entry |
| FPY % | (computed) | read-only `valueGetter` | `= (1 − units_defective / units_inspected) × 100`; ≥99 green, ≥95 amber, else red |
| PPM | (computed) | read-only `valueGetter` | `= (units_defective / units_inspected) × 1,000,000`; 0 green, ≤10 000 amber, else red |
| Inspection Stage | `inspection_stage` | `agSelectCellEditor` | optional; values `Incoming` / `In-Process` / `Final` |
| Scrapped | `units_scrapped` | `agNumberCellEditor` | integer ≥ 0, default 0 |
| Reworked | `units_reworked` | `agNumberCellEditor` | integer ≥ 0, default 0 |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional free text |
| Actions | — | inline delete button | confirms before removing row |

`client_id` is **not a column** — it is derived from `useAuthStore().user.client_id_assigned` for operators or, when the operator role allows multi-tenant access (admin), from `useKPIStore().selectedClient`. If neither is set, save aborts with the snackbar message `grids.quality.errors.noClient`.

`inspection_date` is sent equal to `shift_date` automatically; the backend accepts both fields and stores them independently.

---

## Validation rules

Validation runs at three layers, all of which must pass before a row reaches the backend:

1. **Per-cell editor constraints** — set on each `cellEditorParams` (e.g. `min: 1` on `units_inspected`). AG Grid prevents entry of out-of-range values directly.
2. **Pre-save check** — `saveInspections` rejects the save with a snackbar error if no `client_id` is resolvable.
3. **Backend Pydantic** — final validator. The Create schema requires `client_id` (1–50 chars), `work_order_id` (1–50 chars), `shift_date` (date), `units_inspected` (`> 0`), `units_passed` (`≥ 0`). Any violation 422s and the row is left in the grid with `_hasChanges = true` so the operator can correct and retry.

The cross-row invariant `units_passed + units_defective ≤ units_inspected` is enforced by the CSV import dialog (`CSVUploadDialogQuality.vue:333-340`); the in-grid editor does not currently enforce it because `units_passed` is computed (not user-editable). This is by design — the cell-level constraints prevent the operator from entering inconsistent values.

---

## CSV format

CSV import is wired into the wrapper view's header via `frontend/src/components/CSVUploadDialogQuality.vue`. Required columns:

```
client_id,work_order_id,shift_date,units_inspected,units_passed,units_defective,total_defects_count
```

Optional columns:

```
job_id,inspection_date,inspection_stage,process_step,operation_checked,is_first_pass,units_scrapped,units_reworked,units_requiring_repair,inspection_method,notes
```

The dialog provides a downloadable template (`Download CSV Template` button) with two example rows. Backend endpoint: `POST /quality/upload/csv` (multipart/form-data).

CSV export uses AG Grid's native `exportDataAsCsv` exposed by `AGGridBase.vue:154`. Round-trip safety: the export column names match the import expected names, so an exported CSV can be re-imported without column-name editing.

---

## Tests

- `frontend/src/composables/__tests__/useQualityGridData.spec.ts` — 31 tests covering FPY/PPM/units_passed valueGetters, aggregate stats (totalInspected / totalDefects / avgFPY / avgPPM), initial state, and column-shape conformance to the backend schema.
- The legacy form spec (`frontend/src/components/__tests__/QualityEntry.spec.ts`, 24 tests) was deleted in the same change. Net: +7 tests.
