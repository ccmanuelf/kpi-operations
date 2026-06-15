# Vuetify 4 + MD3 — PR3a: Excel-behaviors isolation module (design)

> First sub-project of **PR3** (the Excel-in-Community behavior layer, §3e of the
> parent spec `2026-06-14-vuetify-4-migration-design.md`). PR1 (foundation) and
> PR2 (spreadsheet-natural theming) are merged. PR3 is decomposed into:
> **PR3a — isolation architecture + consolidate existing (this doc)**;
> PR3b — new native behaviors (undo/redo, quick-find, copy, freeze panes,
> keyboard-nav completion); PR3c — flag-gated range selection + copy.

## Goal

Establish the spec's mandated **single, flag-isolated home** for Excel grid
behaviors — `agGridExcelBehaviors` — and route the behaviors that **already
exist** through it, with **no new behaviors**. This proves the isolation
architecture and clean Enterprise hand-off before PR3b/3c extend it.

## Problem

Excel behaviors today are scattered: Excel paste (`useAGGridBase.ts` +
`utils/clipboardParser.ts` + the paste dialog), CSV import/export and `.xlsx`
export (`exportDataAsCsv`/`exportDataAsExcel` + `utils/excelExport.ts`), and a
custom `navigateToNextCell` (Enter→down, Tab→right) inline in `useAGGridBase`.
None is gated by a master switch or registered, so there is no clean way to
hand off to AG Grid Enterprise (its native equivalents would collide with these
shims) and no single place to document/disable them. §3e requires exactly that.

## Architecture

### The module — `frontend/src/composables/agGridExcelBehaviors.ts`

`useAgGridExcelBehaviors(flags: ExcelBehaviorFlags)` returns:

```ts
interface ExcelBehaviorsResult {
  gridOptions: Partial<GridOptions>   // fragment merged into the grid's options
  registry: ExcelBehaviorEntry[]      // the active (and known) behaviors + metadata
}
interface ExcelBehaviorEntry {
  key: string                 // e.g. 'keyboardNav', 'excelPaste', 'csvExport', 'xlsxExport'
  excelFeature: string        // human label of the Excel behavior emulated
  communityMechanism: string  // how we do it in Community
  enterpriseEquivalent: string// the AG Grid Enterprise feature it must defer to
  flag: keyof ExcelBehaviorFlags
  enabled: boolean
}
```

It is the **only** place that emits Excel-behavior `gridOptions` fragments. The
heavy parsing/formatting stays in `clipboardParser.ts` / `excelExport.ts`
(implementation details the module activates); PR3a does **not** rewrite those.

### Flag model

```ts
interface ExcelBehaviorFlags {
  master: boolean        // single kill-switch; false => empty fragment, native AG Grid only
  keyboardNav: boolean   // Excel Enter→down / Tab→right
  excelPaste: boolean    // paste-from-Excel pipeline
  csvImport: boolean
  csvExport: boolean
  xlsxExport: boolean
}
export const DEFAULT_EXCEL_BEHAVIOR_FLAGS: ExcelBehaviorFlags // all true (Community default-on)
```

`useAGGridBase` computes effective flags = `DEFAULT_EXCEL_BEHAVIOR_FLAGS`
overridden by the existing per-grid props (`enableExcelPaste`,
`enableCsvImport`, `enableExport` → `excelPaste`/`csvImport`/`csvExport`+`xlsxExport`),
all forced off when `master` is false. Per-grid behavior is preserved; the new
global master switch + per-feature flags are added.

### Integration (single point)

`useAGGridBase` calls `useAgGridExcelBehaviors(effectiveFlags)` once and spreads
`result.gridOptions` into `mergedGridOptions`. The `navigateToNextCell` block
**moves out of `useAGGridBase` into the module** under the `keyboardNav` flag
(PR3a's one real code move). Paste/export wiring stays in `useAGGridBase` but is
**gated by the module's effective flags** and **registered** in the registry.
No monkey-patching of AG Grid internals.

### Enterprise hand-off

Each registry entry names its `enterpriseEquivalent`; each shim site carries an
inline comment pointing to `docs/frontend/ag-grid-excel-behaviors.md` and its
Enterprise feature. With `master: false` (or a per-feature flag false), the
module emits nothing for that behavior, so the native Enterprise feature takes
over with no duplicated/conflicting handler.

## Documentation (hard requirement)

`docs/frontend/ag-grid-excel-behaviors.md` — one row per registry entry: behavior
key, Excel feature emulated, Community mechanism, Enterprise-native equivalent to
defer to, and the exact flag to disable it. PR3a documents the behaviors it
registers (keyboardNav, excelPaste, csvImport, csvExport, xlsxExport); PR3b/3c
append their rows.

## Testing

- **Isolation test** (`agGridExcelBehaviors.spec.ts`): with `master: false`,
  `gridOptions` is empty (no `navigateToNextCell`, etc.) and `registry` reports
  all behaviors disabled; with defaults, the expected keys are enabled and
  `gridOptions.navigateToNextCell` is a function. Proves the kill-switch.
- **Doc-coverage test:** every `registry` key appears as a documented row in
  `docs/frontend/ag-grid-excel-behaviors.md` (asserts the doc exists + covers
  each registered behavior key).
- **Keyboard-nav behavior test:** the moved `navigateToNextCell` still returns
  the down-cell on Enter (key 13) and the suggested cell on Tab (key 9) — i.e.
  the move is behavior-preserving.

## Scope

**In (PR3a):** the module + flag model + registry; move `navigateToNextCell`
into it; gate + register the existing paste/CSV/xlsx behaviors; the docs file
(covering the registered behaviors); the isolation, doc-coverage, and
keyboard-nav tests; inline Enterprise-deferral comments.

**Out (PR3b):** undo/redo (`undoRedoCellEditing`), quick-find, single-cell/
whole-row copy config, type-to-edit/Esc completion, freeze-panes-as-a-feature.
**Out (PR3c):** multi-cell range selection + range copy shim.
**Out (always):** fill-handle (Enterprise-deferred), Enterprise licensing.

## Validation

- **Gate C (AG Grid functional):** grid e2e green — paste, CSV/xlsx export, and
  keyboard nav still work on the entry grids (verified by this PR's `e2e-sqlite`
  CI check; local e2e can't run — its webServer binds :8000/:3000, occupied).
- **Isolation gate (G):** the isolation + doc-coverage tests pass; flipping
  `master` off leaves grids functional with no Excel shims.
- **Static gates:** build / vitest / vue-tsc / eslint / npm-audit green.
- No visual change expected (behavior-only); a quick browser sanity on one
  entry grid (e.g. Production Entry) confirms the toolbar + paste still render.
