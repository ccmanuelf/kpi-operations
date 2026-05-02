# Capacity — Scenarios Panel — Surface Brief

**Route:** tab inside `/capacity-planning`
**View:** `frontend/src/views/CapacityPlanning/components/panels/ScenariosPanel.vue`
**Composable:** `frontend/src/composables/useScenariosGridData.ts`
**Backend canonical schema:** `backend/routes/capacity/_models.py` `ScenarioCreate`

Migrated 2026-05-01 from a card grid + 16-input v-dialog form to inline AG Grid (Group H Surface #20). Backend has no scenario update endpoint, so **only new rows are editable** — existing scenarios are point-in-time records (DRAFT → EVALUATED → APPLIED/REJECTED).

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| (selection) | — | checkbox (existing rows only) | drives multi-row Compare button |
| Scenario Name | `scenario_name` | text (pinned left, new rows only) | required |
| Scenario Type | `scenario_type` | `agSelectCellEditor` (new rows only) | one of `SCENARIO_TYPE_OPTIONS`: OVERTIME, SETUP_REDUCTION, SUBCONTRACT, NEW_LINE, THREE_SHIFT, LEAD_TIME_DELAY, ABSENTEEISM_SPIKE, MULTI_CONSTRAINT |
| Parameters | `parameters` | `agLargeTextCellEditor` popup (new rows only) | JSON object; type-switch resets to that type's defaults via `valueSetter` |
| Status | `status` | read-only chip | DRAFT / EVALUATED / APPLIED / REJECTED |
| Total Output | `results.total_output` (or `results_json.total_output`) | read-only number | populated by `runScenario` |
| Utilization | `results.avg_utilization` | read-only `%` formatter | populated by `runScenario` |
| On-Time | `results.on_time_rate` | read-only `%` formatter | populated by `runScenario` |
| Actions | — | Save+Cancel for new rows; Run (DRAFT only) + Delete for existing | row-action chip |

`client_id` flows through `useCapacityPlanningStore.createScenario` from `useWorkbookStore.clientId`.

---

## Validation rules

1. **Required-field check before POST** — `requiredFieldsPresent(row)` asserts `scenario_name` and `scenario_type` are set. Otherwise `capacityPlanning.scenarios.errors.fillRequired`.
2. **JSON parameters parser** — popup editor only commits when `JSON.parse(input)` returns an object (not array, not malformed). Empty input → `{}`.
3. **Type-switch reset** — changing `scenario_type` on a draft row replaces `parameters` with `DEFAULT_PARAMETERS[newType]` (matches the legacy dialog's per-type input swap).
4. **Backend Pydantic** — `ScenarioCreate` requires `scenario_name`. **Bug-fix during this migration:** API client used to send `name` (silent 422); now sends `scenario_name`.

---

## CSV format

CSV import / export use the AGGridBase toolbar. Header row:

```
scenario_name,scenario_type,parameters,status
```

`parameters` is JSON-encoded inside the cell. Round-trip note: exporting will include `parameters` as a JSON string; re-importing will need that cell to remain a single CSV field (Papaparse handles quoted JSON correctly).

Multi-row selection drives `compareScenarios([id1, id2, ...])` which opens the existing comparison dialog.

---

## Tests

- `frontend/src/composables/__tests__/useScenariosGridData.spec.ts` — 33 tests covering `SCENARIO_TYPE_OPTIONS` catalogue, `DEFAULT_PARAMETERS` per type, type-switch parameter reset, JSON valueSetter (valid / malformed / array / empty), existing-row immutability, addRow defaults, saveRow validation, runRow gating to DRAFT only, delete handler.
- `frontend/src/services/__tests__/capacityPlanning.spec.ts:994` — service-level test asserting the exact POST body shape (`scenario_name` not `name`).
