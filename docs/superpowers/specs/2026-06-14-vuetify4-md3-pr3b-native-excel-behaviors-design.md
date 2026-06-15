# Vuetify 4 + MD3 — PR3b: Native Community Excel behaviors (design)

> Second sub-project of **PR3** (§3e of the parent spec
> `2026-06-14-vuetify-4-migration-design.md`). PR1, PR2, and **PR3a** (the
> `agGridExcelBehaviors` isolation module) are merged. PR3b extends that module
> with the remaining **native AG-Grid-Community** behaviors; PR3c adds the
> flag-gated range selection + copy.

## Goal

Deliver the native-tier Excel ergonomics from §3e — undo/redo, whole-row copy,
Excel-style cell-editing commit/cancel, freeze panes, and (deferred) quick-find —
**entirely through the PR3a module**, so each is flag-gated, registered,
documented, and yields cleanly to AG Grid Enterprise.

## What already exists (consolidate, don't rebuild)

- **undo/redo** is live but hardcoded as `:undoRedoCellEditing="true"` /
  `:undoRedoCellEditingLimit="20"` props on `AGGridBase.vue` (lines 76–77) —
  *not* flag-isolated. PR3b moves it into the module.
- **single-cell copy** works (AG Community default Ctrl+C).
- **column pinning** exists per-grid (`pinned: 'left'/'right'` in several
  `*GridData` composables); the header row is sticky by default.
- **per-screen Search** boxes already filter grid data → AG quick-find would
  duplicate them.

## Behaviors (all via `agGridExcelBehaviors`)

Each adds a flag to `ExcelBehaviorFlags` + `DEFAULT_EXCEL_BEHAVIOR_FLAGS`, a
`BEHAVIOR_META` row (Excel feature, Community mechanism, Enterprise equivalent),
and — where it needs grid wiring — a `gridOptions` fragment emitted when the
flag is on (and `master` is on).

| Flag | Default | gridOptions fragment | Notes |
|---|---|---|---|
| `undoRedo` | `true` | `{ undoRedoCellEditing: true, undoRedoCellEditingLimit: 20 }` | Moved from `AGGridBase.vue`; native Ctrl+Z / Ctrl+Y. Enterprise: same native option (no shim) — flag stays. |
| `copy` | `true` | `{ suppressCopyRowsToClipboard: false }` | Single-cell is default; this makes **whole-row** copy explicit (select rows + Ctrl+C). Enterprise: native clipboard. |
| `cellEditing` | `true` | `{ stopEditingWhenCellsLoseFocus: true }` | Excel-style commit-on-blur; type-to-edit + Esc-cancel are AG defaults (asserted, not configured). |
| `freezePanes` | `true` | *(none)* | Registration + docs only: the existing per-grid `pinned` columns + sticky header ARE the freeze mechanism. No new pinning code/UI. Enterprise: same pinning. |
| `quickFind` | `false` | *(none)* | Registered but deferred-off — the per-screen Search covers it. Documented as available-but-off; no UI. |

`useAGGridBase` already spreads `excelBehaviors.value.gridOptions`, so the new
fragments reach all 9 grids with no further wiring. `AGGridBase.vue` drops its
hardcoded undo/redo props (now sourced from the module).

## Architecture / isolation

No new architecture — PR3b only grows the PR3a module's flag set, metadata, and
fragment builder. The `master: false` kill-switch automatically drops the new
fragments too (extends the existing isolation test). Each new shim site carries
an inline comment pointing to `docs/frontend/ag-grid-excel-behaviors.md` and its
Enterprise equivalent.

## Documentation

Append the five rows above to `docs/frontend/ag-grid-excel-behaviors.md`. The
PR3a doc-coverage test then asserts the new keys are documented automatically
(it iterates the registry). `quickFind` and `freezePanes` rows note their
"no-fragment" nature and (for quickFind) the deferred-off default.

## Testing

- **Module unit tests (extend PR3a's spec):** with defaults, the fragment
  includes `undoRedoCellEditing`, `suppressCopyRowsToClipboard === false`, and
  `stopEditingWhenCellsLoseFocus`; the registry marks `undoRedo`/`copy`/
  `cellEditing`/`freezePanes` enabled and `quickFind` disabled; with
  `master:false`, none of the new keys appear in the fragment.
- **Consolidation test:** `AGGridBase.vue` no longer hardcodes
  `undoRedoCellEditing` (grep-style assertion in a component test, or verify the
  merged options carry it from the module).
- **Doc-coverage test (PR3a):** passes for the new keys.
- **Gate C (functional):** grid e2e green — editing + undo/redo + copy still
  work on the entry grids (this PR's `e2e-sqlite` CI check; local e2e can't run,
  webServer binds :8000/:3000).

## Scope

**In (PR3b):** the five flags/registry rows above; the undo/redo move; the copy
+ cellEditing fragments; freezePanes/quickFind registration + docs; extended
module tests; doc updates.

**Out:** range selection + multi-cell copy (PR3c); fill-handle (Enterprise);
any new toolbar UI; quick-find UI; backend changes.

## Validation

Static gates (build / vitest / vue-tsc / eslint / npm-audit) + the module
isolation/doc tests + gate C via CI. Behavior-preserving for undo/redo (relocated
only); copy/cellEditing are additive AG-Community options with low regression risk.
