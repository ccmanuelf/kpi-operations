# Capacity — Calendar Worksheet — Surface Brief

**Route:** tab inside `/capacity-planning`
**View:** `frontend/src/views/CapacityPlanning/components/grids/CalendarGrid.vue`
**Composable:** `frontend/src/composables/useCalendarGridData.ts`
**Persistence:** workbook-level via `useCapacityPlanningStore.saveWorksheet('calendar')`
**Backend canonical schema:** `backend/routes/capacity/_models.py` `CalendarEntryCreate`

Migrated 2026-05-01 from a v-data-table + per-cell editors to AG Grid (Group D Surface #22 of inventory).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Date | `entry_date` | `agDateStringCellEditor` (pinned left) | required (YYYY-MM-DD) |
| Day Type | `day_type` | `agSelectCellEditor` | one of WORKING / WEEKEND / HOLIDAY / PARTIAL |
| Description | `description` | text | optional |
| Working Hours | `working_hours` | `agNumberCellEditor` | ≥ 0, 2 decimals |
| Active Lines | `active_lines_count` | `agNumberCellEditor` | integer ≥ 0 |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional |
| Actions | — | inline delete | row-action chip |

`client_id` flows through the workbook store.

---

## Validation rules

1. **Per-cell editor constraints** — `min: 0` on numeric fields; `day_type` constrained to enum values.
2. **Workbook-level save** — `worksheets.calendar.dirty = true` on every cell change; persisted via `store.saveWorksheet('calendar')`.
3. **Backend Pydantic** — `CalendarEntryCreate` requires `entry_date`. 422s rollback via `loadWorkbook()`.

---

## CSV format

CSV import / export use the AGGridBase toolbar. Header row:

```
entry_date,day_type,description,working_hours,active_lines_count,notes
```

---

## Tests

- `frontend/src/composables/__tests__/useCalendarGridData.spec.ts` — covers column shape, date editor wiring, day-type enum, dirty-flag propagation.
