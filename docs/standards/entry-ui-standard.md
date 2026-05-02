# Entry-UI Standard

**Status:** Normative (Phase 3 of the entry-interface audit, 2026-05-02).
**Scope:** All user-facing surfaces in `frontend/src/views/**` and
`frontend/src/components/entries/**` whose primary job is to mutate
backend records (POST / PUT / DELETE).
**Predecessor:** `docs/audit/entry-surface-inventory.md`,
`docs/audit/entry-surface-migration-plan.md`.

The audit's user-adoption goal — Excel-fluent maquiladora operators
treating kpi-operations as a spreadsheet — drives everything below.
"Form on a web page" is rejected; "spreadsheet that talks to the
backend" is the contract.

---

## 1. Spreadsheet Standard (mandatory for entry surfaces)

Every entry surface MUST satisfy all of:

1. **AG Grid component**: built on `frontend/src/components/grids/AGGridBase.vue`.
   No new `v-data-table` + per-cell `v-text-field` / `v-textarea` /
   `v-select` constructions. No new `v-form`-wrapped entry dialogs.
2. **Excel paste-in**: paste from Excel must round-trip.
   Implementation MAY use AG Grid's native `processDataFromClipboard`
   OR the project's `useAGGridBase.handlePasteFromExcel` pipeline
   (`frontend/src/composables/useAGGridBase.ts:219-304`).
2.a **CSV export (round-trip safe)**: every entry surface exposes a
   "Export CSV" button. AGGridBase ships this in its toolbar by
   default (`enableExport: true`), backed by AG Grid's native
   `exportDataAsCsv`. Set `:enableExport="false"` only on read-only
   summaries where export isn't appropriate. Override the filename
   with the `exportFilename` prop; the default is
   `<entryType>_export_<yyyy-mm-dd>.csv`.
3. **Per-column validation**: schemas live in
   `frontend/src/utils/clipboardParser.ts` (`entrySchemas`) and the
   backend Pydantic models. The backend Pydantic schema is the
   canonical field shape — frontend payloads must match exactly
   (see §3 below).
4. **Inline cell editing**: edit on click; commit on blur, Enter, or
   Tab. No modal "edit dialog" detour.
5. **Native AG Grid editors**: `agTextCellEditor`,
   `agNumberCellEditor`, `agSelectCellEditor`,
   `agDateStringCellEditor`, `agLargeTextCellEditor` (popup for
   notes). Do not wrap Vuetify form controls inside cells.
6. **Multi-tenant context**: `client_id` is resolved from
   `useAuthStore.user.client_id_assigned` falling back to
   `useKPIStore.selectedClient`. Never hardcode.

---

## 2. Save patterns

Two patterns are blessed; pick by surface kind:

### 2.a Workbook-level save (Group D — capacity worksheets)

- Edits accumulate in the store as `dirty: true`.
- A single `store.saveWorksheet(<key>)` action POSTs/PUTs the whole
  worksheet on operator click.
- Use when: the surface is one tab in a workbook with a top-level
  Save button (Capacity Planning Production Lines, Stock,
  Standards, Calendar, Orders).

Reference: `useProductionLinesGridData.ts`, `useStockGridData.ts`,
`useStandardsGridData.ts`, `useCalendarGridData.ts`,
`useOrdersGridData.ts`.

### 2.b Inline-edit autosave (Group E / H — admin catalogs, operational data)

- Existing rows: `onCellValueChanged` fires PUT immediately on the
  changed row. Failures rollback by calling the load function to
  refresh from the server.
- New rows: `addRow()` adds a draft (`_isNew: true`) to local state.
  Operator fills required fields, then clicks the green Save button
  in the row's actions column → POST. Cancel button discards.
- Required-field validation runs client-side before POST; mirror
  the backend `*Create` Pydantic schema.

Reference: `useDefectTypesGridData.ts`, `usePartOpportunitiesGridData.ts`,
`useWorkOrderGridData.ts`, `useScenariosGridData.ts`,
`useFloatingPoolGridData.ts`.

---

## 3. Backend payload alignment

The backend Pydantic schema at `backend/schemas/<entity>.py` (or
`backend/routes/<area>/_models.py`) is the canonical field shape.
Frontend payload helpers MUST match field names, types, and
required-vs-optional shape **exactly**.

### Anti-patterns observed in the audit

| Surface | Bug | Fixed in commit |
|---|---|---|
| Quality entry | UI sent `defect_type_id` etc.; backend wanted `units_passed`, `shift_date`, `client_id` | Group A migration |
| Holds | UI hit `/holds/{id}/resume` (404); used UI-only fields | Group A migration |
| Attendance | UI sent `attendance_date` + UI status enum; backend expected `shift_date` + `is_absent` + `absence_type` | Group A migration |
| Downtime | UI sent `downtime_minutes`; backend wanted `downtime_duration_minutes` and `DowntimeReasonEnum` codes | Group A migration |
| Scenarios | API client sent `name`; backend expected `scenario_name` (silent 422) | Group H Surface #20 |
| WorkflowStepDowntime | Catch block forged `incident.resolved = true` on API failure | Group B option (c) |

Every payload divergence MUST be caught by a service-level test
that asserts the exact body shape (see
`frontend/src/services/__tests__/capacityPlanning.spec.ts:994` for
the canonical pattern).

---

## 4. Permitted exceptions

The audit defines four exception buckets where Vuetify form
primitives (`v-form`, `v-text-field`, `v-textarea`, `v-select`) are
allowed in entry contexts:

1. **Login / Auth** (one surface). `LoginView.vue`.
2. **Admin config with <5 users**. Settings, Users, Clients,
   Client Config, Workflow Config, Workflow Designer,
   Database / Migration Wizard, Email Reports Dialog,
   Capacity Dashboard Inputs.
3. **Search / filter / parameter dialogs**. Schedule, Capacity
   Schedule, Capacity Analysis, Capacity Component Check,
   Save Filter, Filter Bar / Manager.
4. **Confirmation / approval / destructive-action dialogs**. Alert
   Resolve (textarea-only), delete confirmations, CSV-paste import
   dialogs, file pickers, How-to-Use guide dialogs (read-only).

Anything outside these buckets is non-compliant.

---

## 5. Acceptance criteria per new entry surface

Before merging a new or rewritten entry surface, ALL of the
following must hold:

1. Component imports `AGGridBase` from
   `@/components/grids/AGGridBase.vue`.
2. The composable that owns column defs lives at
   `frontend/src/composables/use<Surface>GridData.ts`.
3. A spec at
   `frontend/src/composables/__tests__/use<Surface>GridData.spec.ts`
   covers: column shape, catalog alignment with backend enum,
   addRow defaults, save validation, error-rollback behaviour, and
   any custom valueGetter / valueSetter / cellRenderer logic.
4. Service-level test (`frontend/src/services/__tests__/<area>.spec.ts`)
   asserts the exact API body shape against the backend Pydantic
   schema.
5. `npm run lint` produces no NEW errors (warnings on
   TypeScript-interface-arg-name patterns are allowed — they match
   the established baseline across the other Group D / E / H
   composables).
6. `npm test` shows all existing tests still passing AND the new
   spec is listed in the test report.
7. The surface entry in `docs/audit/entry-surface-inventory.md` is
   updated with the migration date, composable path, and test
   count.

---

## 6. ESLint guardrail

`frontend/eslint.config.js` enforces a Vue-AST `no-restricted-syntax`
rule that flags `<v-form>` inside `frontend/src/views/**` and
`frontend/src/components/entries/**`. Files in the four exception
buckets above are listed by path in the same config block (rule
disabled). The rule is at WARNING level (not ERROR) so audits
catch new violations without blocking unrelated commits — promote
to ERROR after a clean cycle.

If you genuinely need to add a `<v-form>` to a file not on the
exception list, it MUST be one of:
- A new entry into the exception list with a one-line justification
  in the inline comment.
- Wrapped with an `eslint-disable-next-line vue/no-restricted-syntax`
  pragma and a code comment explaining why the spreadsheet pattern
  doesn't fit.

The default answer is "use AGGridBase".

---

## 7. References

- Source spec: `/Users/mcampos.cerda/Downloads/06_kpi-operations_entry_interface_audit.md`
- Inventory (Phase 0): `docs/audit/entry-surface-inventory.md`
- Migration plan (Phase 1): `docs/audit/entry-surface-migration-plan.md`
- Group A runtime validation: `docs/audit/group-a-runtime-validation.md`
- Group B runtime validation: `docs/audit/group-b-runtime-validation.md`
- Canonical components: `frontend/src/components/grids/AGGridBase.vue`,
  `frontend/src/composables/useAGGridBase.ts`,
  `frontend/src/utils/clipboardParser.ts`.
