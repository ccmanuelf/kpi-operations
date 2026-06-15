# Vuetify 4 + MD3 — PR3c: Flag-gated range selection + copy (design)

> Final sub-project of **PR3** (§3e) and of the whole Vuetify 4 migration. PR1,
> PR2, **PR3a** (isolation module), and **PR3b** (native behaviors) are merged.
> PR3c shims the one §3e behavior with real Enterprise overlap: multi-cell
> **range selection + range copy**, behind a flag that yields to Enterprise.

## Goal

Let users select a rectangular cell range (Shift+click / Shift+Arrow), see it
highlighted, and Ctrl+C copy it to the clipboard as Excel-default TSV — in AG
Grid **Community** (which has no native range selection), behind the
`rangeCopy` flag in the `agGridExcelBehaviors` module, deferring to AG Grid
Enterprise's native cell selection when present.

## Why a shim

AG Grid range/cell selection is **Enterprise-only**; the app registers
`AllCommunityModule`, so it is unavailable. A leftover `enableRangeSelection`
prop on `AGGridBase.vue` is a no-op under Community. PR3c provides a contained,
flag-gated Community shim built on **public AG Community APIs + events** (no raw
DOM mouse tracking), so it is robust against virtualization/scroll and removes
cleanly for Enterprise.

## Architecture

The pure `agGridExcelBehaviors` module stays the flag/registry source of truth;
the stateful shim is its own composable it owns.

### `frontend/src/composables/useGridRangeCopy.ts` *(new)*

A composable `useGridRangeCopy(opts)` where `opts = { gridApi: Ref, enabled: Ref<boolean> }`. Responsibilities:

- **State:** `anchor` and `focus` cell positions (`{ rowIndex, colId }`), reactive.
- **Pure helpers (unit-tested):**
  - `rectFrom(anchor, focus, colOrder)` → `{ rowStart, rowEnd, colIds: string[] }` (normalized rectangle; `colOrder` is the displayed column id order so the rectangle spans contiguous columns).
  - `isInRange(rowIndex, colId, rect)` → boolean (drives the highlight).
  - `buildTsv(rect, getValue)` → string (rows joined by `\n`, cells by `\t`; `getValue(rowIndex, colId)` supplied by the caller).
- **Interaction handlers:**
  - `onCellClicked(e)` — plain click sets `anchor` (+ clears range); Shift+click sets `focus` (extend).
  - `onKeyDown(e)` — Shift+Arrow extends `focus` by one cell; Ctrl/Cmd+C, when a multi-cell range is active, builds TSV via `gridApi.getValue` over `getDisplayedRowAtIndex` and writes it with `navigator.clipboard.writeText`, then `preventDefault`.
- **Highlight:** exposes a `rangeCellClass(params)` returning the class when `isInRange`; the caller merges it into `defaultColDef.cellClassRules`. On any range-state change, call `gridApi.refreshCells({ force: true })` so AG re-evaluates the rule (survives scroll — no DOM hacking).
- When `enabled` is false, all handlers no-op and no class is applied (fully inert).

### `agGridExcelBehaviors.ts`

Add the `rangeCopy` flag (default `true`) + `BEHAVIOR_META` row
(`enterpriseEquivalent: 'Enterprise cell selection + range copy'`). The module
stays pure; `rangeCopy` is registry/flag metadata (the stateful work is in the
composable, gated by the same effective flag).

### `useAGGridBase.ts`

When `rangeCopy` is effectively enabled, instantiate `useGridRangeCopy`, merge
`rangeCellClass` into `defaultColDef.cellClassRules`, route the existing
`cellClicked` to `onCellClicked`, and add a keydown listener for `onKeyDown`
(removed on unmount, like the paste listener).

### Highlight CSS — `aggrid-theme.css`

`.ag-theme-material .range-shim-selected` → a Carbon blue tint
(`--cds-highlight`/`--cds-blue-20` light, a translucent blue in dark) with an
AA-safe foreground, echoing Excel's range box. Reuses the existing
`--ag-range-selection-*` token values already defined in the theme.

## Enterprise deferral

Effective-enabled = `master && rangeCopy && !enterprisePresent`, where
`enterprisePresent` is a runtime feature-detect: `typeof gridApi.getCellRanges === 'function'` (Enterprise adds `getCellRanges` to the grid API; Community lacks
it). When Enterprise is adopted, the shim disables itself and native cell
selection takes over — zero conflicting handlers. An inline comment + the doc
row record this.

## Documentation

Append a `rangeCopy` row to `docs/frontend/ag-grid-excel-behaviors.md` (Excel
feature, Community mechanism = "Shift+click/arrow shim + TSV clipboard",
Enterprise equivalent, disable flag). The PR3a doc-coverage test then asserts it
automatically.

## Testing

- **Pure-logic unit tests** (`useGridRangeCopy.spec.ts`): `rectFrom` normalizes
  any anchor/focus into a correct rectangle; `isInRange` is true only inside it;
  `buildTsv` produces correct TSV from a stub `getValue` (incl. single-cell and
  multi-row/col cases).
- **Registry/isolation:** `rangeCopy` registered + enabled by default; flag/master
  off → the composable attaches no handlers and `rangeCellClass` yields no class.
- **Enterprise-defer test:** with a stubbed `gridApi.getCellRanges`, effective
  enabled is false.
- **Doc-coverage:** the new key is documented (PR3a test).
- **Gate C (functional):** grid e2e green; a manual harness check on one grid
  confirms Shift-select highlight + Ctrl+C TSV (local e2e can't run — webServer
  binds :8000/:3000).

## Scope

**In:** Shift+click/Shift+Arrow rectangular selection, highlight, Ctrl+C TSV
copy; flag-gated + Enterprise-deferring + documented; pure-logic + isolation
tests. Remove the dead `enableRangeSelection` no-op prop from `AGGridBase.vue`
(superseded by `rangeCopy`).

**Out:** click-drag selection, fill-handle (Enterprise), paste-into-range (paste
exists separately), headers in the copied TSV, multi-range (non-contiguous).

## Validation

Static gates (build / vitest / vue-tsc / eslint / npm-audit) + isolation/doc
tests + gate C via CI + a manual harness spot-check of the highlight & copy in
light and dark. This completes §3e and the Vuetify 4 migration.
