# Capacity — KPI Tracking Panel — Surface Brief

**Route:** tab inside `/capacity-planning`
**View:** `frontend/src/views/CapacityPlanning/components/panels/KPITrackingPanel.vue`
**Composable:** `frontend/src/composables/useKPITrackingGridData.ts`
**Persistence:** workbook-level via `useCapacityPlanningStore.saveWorksheet('kpiTracking')` → `PUT /capacity/kpi-workbook/...`

Migrated 2026-05-01 from a v-data-table list to AG Grid (Group G Surface #28).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| KPI Name | `kpi_name` | text (pinned left) | required |
| Target | `target_value` | `agNumberCellEditor` | required, 2 decimals |
| Actual | `actual_value` | read-only renderer | populated by `store.loadKPIActuals(period)` against backend actuals data |
| Variance % | `variance_percent` | read-only chip renderer | color-coded by `classifyVariance` helper: `ON_TARGET` (≤5%) green, `OFF_TARGET` (≤10%) amber, `CRITICAL` (>10%) red |
| Status | `status` | read-only chip | PENDING / ON_TRACK / AT_RISK / OFF_TARGET / ACHIEVED |
| Period | `period_start` / `period_end` (combined) | read-only `valueGetter` | range-formatted dates |
| Actions | — | inline delete button | row-action chip |

Only `kpi_name` and `target_value` are operator-editable. The other fields are populated by the actuals load.

---

## Validation rules

1. **Per-cell editor constraints** — `precision: 2` on `target_value`.
2. **Workbook-level dirty flag** — every `cellValueChanged` sets `worksheets.kpiTracking.dirty = true`. The Save button on the panel triggers `store.saveWorksheet('kpiTracking')`.
3. **Backend Pydantic** — KPI threshold writes go through `PUT /kpi/thresholds`; KPI actuals are read-only from this surface.

The Load Actuals period-picker dialog is preserved as Exception 3 (search/parameter dialog).

---

## CSV format

CSV import / export use the AGGridBase toolbar. Header row:

```
kpi_name,target_value,actual_value,variance_percent,status,period_start,period_end
```

Importable columns are `kpi_name` and `target_value`; the others round-trip but won't override the loaded actuals on next refresh.

---

## Tests

- `frontend/src/composables/__tests__/useKPITrackingGridData.spec.ts` — 21 tests covering `classifyVariance` at the bucket boundaries (5%, 10%), chip renderers, column shape, dirty-flag propagation, and helper computations.
