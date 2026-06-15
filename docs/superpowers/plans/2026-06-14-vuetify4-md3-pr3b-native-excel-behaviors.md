# Vuetify 4 + MD3 — PR3b: Native Community Excel behaviors — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the `agGridExcelBehaviors` module with the native-tier Excel behaviors (undo/redo consolidated in, whole-row copy, Excel cell-editing commit, freeze-panes + quick-find as registered metadata) — all flag-gated, registered, documented.

**Architecture:** No new architecture — grow the PR3a module's flags, registry metadata, and `gridOptions` fragment builder. `useAGGridBase` already spreads the fragment to all 9 grids; `AGGridBase.vue` drops its hardcoded undo/redo props so they come from the module.

**Tech Stack:** Vue 3.5 composables, AG Grid Community 35, Vitest. Loose typing to match the codebase.

**Spec:** `docs/superpowers/specs/2026-06-14-vuetify4-md3-pr3b-native-excel-behaviors-design.md`.

**Branch:** `feat/vuetify-4-pr3b-native-excel-behaviors` (spec already committed here).

---

## File structure (PR3b)

- `frontend/src/composables/agGridExcelBehaviors.ts` *(modify)* — add 5 flags, defaults, `BEHAVIOR_META` rows, and `gridOptions` fragments for undoRedo/copy/cellEditing.
- `frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts` *(modify)* — extend for the new fragments/flags.
- `frontend/src/components/grids/AGGridBase.vue` *(modify)* — remove hardcoded `:undoRedoCellEditing` / `:undoRedoCellEditingLimit`.
- `frontend/src/composables/__tests__/agGridExcelBehaviorsConsolidation.spec.ts` *(new)* — asserts `AGGridBase.vue` no longer hardcodes undo/redo.
- `docs/frontend/ag-grid-excel-behaviors.md` *(modify)* — append 5 rows (doc-coverage test from PR3a picks them up).

---

## Task 1: Extend the module (flags + metadata + fragments)

**Files:**
- Modify: `frontend/src/composables/agGridExcelBehaviors.ts`
- Test: `frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts`

- [ ] **Step 1: Add the failing tests.**
Append these `it` blocks inside the existing `describe('agGridExcelBehaviors', ...)` in `agGridExcelBehaviors.spec.ts`:
```ts
  it('emits the native-behavior fragments by default', () => {
    const { gridOptions, registry } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    expect(gridOptions.undoRedoCellEditing).toBe(true)
    expect(gridOptions.undoRedoCellEditingLimit).toBe(20)
    expect(gridOptions.suppressCopyRowsToClipboard).toBe(false)
    expect(gridOptions.stopEditingWhenCellsLoseFocus).toBe(true)
    const enabled = (k: string) => registry.find((e) => e.key === k)?.enabled
    expect(enabled('undoRedo')).toBe(true)
    expect(enabled('copy')).toBe(true)
    expect(enabled('cellEditing')).toBe(true)
    expect(enabled('freezePanes')).toBe(true)
  })

  it('registers quickFind but leaves it off by default (deferred to per-screen Search)', () => {
    const { registry } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    expect(registry.find((e) => e.key === 'quickFind')?.enabled).toBe(false)
  })

  it('master:false also drops the native fragments', () => {
    const { gridOptions } = useAgGridExcelBehaviors({ ...DEFAULT_EXCEL_BEHAVIOR_FLAGS, master: false })
    expect(gridOptions.undoRedoCellEditing).toBeUndefined()
    expect(gridOptions.suppressCopyRowsToClipboard).toBeUndefined()
    expect(gridOptions.stopEditingWhenCellsLoseFocus).toBeUndefined()
    expect(Object.keys(gridOptions)).toHaveLength(0)
  })

  it('freezePanes and quickFind emit no gridOptions fragment (config/registration only)', () => {
    const { gridOptions } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    // freeze = existing pinned columns; quickFind = deferred. Neither adds a grid option.
    expect('rowPinned' in gridOptions).toBe(false)
    expect('quickFilterText' in gridOptions).toBe(false)
  })
```

- [ ] **Step 2: Run to see them fail.**
Run from `frontend/`: `npx vitest run src/composables/__tests__/agGridExcelBehaviors.spec.ts`
Expected: FAIL — `undoRedoCellEditing` etc. undefined; `undoRedo`/`copy`/… not in registry.

- [ ] **Step 3: Add the flags + defaults.**
In `agGridExcelBehaviors.ts`, extend the `ExcelBehaviorFlags` interface (after `xlsxExport: boolean`):
```ts
  undoRedo: boolean
  copy: boolean
  cellEditing: boolean
  freezePanes: boolean
  quickFind: boolean
```
and `DEFAULT_EXCEL_BEHAVIOR_FLAGS` (after `xlsxExport: true,`):
```ts
  undoRedo: true,
  copy: true,
  cellEditing: true,
  freezePanes: true,
  quickFind: false,
```

- [ ] **Step 4: Add the metadata rows.**
Append to the `BEHAVIOR_META` array (after the `xlsxExport` entry):
```ts
  {
    key: 'undoRedo',
    excelFeature: 'Undo / redo cell edits (Ctrl+Z / Ctrl+Y)',
    communityMechanism: 'undoRedoCellEditing gridOption (limit 20)',
    enterpriseEquivalent: 'Same native AG Grid option (no shim; flag stays on)',
  },
  {
    key: 'copy',
    excelFeature: 'Copy focused cell or whole selected rows (Ctrl+C)',
    communityMechanism: 'AG default cell copy + suppressCopyRowsToClipboard:false',
    enterpriseEquivalent: 'Enterprise clipboard (richer range copy — see PR3c)',
  },
  {
    key: 'cellEditing',
    excelFeature: 'Type-to-edit, Esc cancels, commit on blur',
    communityMechanism: 'stopEditingWhenCellsLoseFocus + AG default key editing',
    enterpriseEquivalent: 'n/a (Community-capable; no Enterprise overlap)',
  },
  {
    key: 'freezePanes',
    excelFeature: 'Freeze columns + header row',
    communityMechanism: 'per-grid colDef pinned + sticky header (no extra option)',
    enterpriseEquivalent: 'Same native pinning',
  },
  {
    key: 'quickFind',
    excelFeature: 'Instant global filter (Ctrl+F style)',
    communityMechanism: 'deferred — per-screen Search box covers this (off by default)',
    enterpriseEquivalent: 'n/a (Community-capable; deferred by product choice)',
  },
```

- [ ] **Step 5: Emit the new fragments.**
In `useAgGridExcelBehaviors`, after the existing `if (on('keyboardNav')) {...}` block and before building `registry`, add:
```ts
  if (on('undoRedo')) {
    gridOptions.undoRedoCellEditing = true
    gridOptions.undoRedoCellEditingLimit = 20
  }
  if (on('copy')) {
    // Single-cell Ctrl+C is the AG default; this makes whole-row copy explicit.
    // Enterprise: native clipboard / range copy (PR3c) supersedes — flag off then.
    gridOptions.suppressCopyRowsToClipboard = false
  }
  if (on('cellEditing')) {
    // Excel-style commit-on-blur; type-to-edit + Esc-cancel are AG defaults.
    gridOptions.stopEditingWhenCellsLoseFocus = true
  }
  // freezePanes = per-grid pinned columns + sticky header; quickFind = deferred.
  // Neither emits a gridOptions fragment — they are registry/doc entries only.
```

- [ ] **Step 6: Run the module tests to PASS.**
Run: `npx vitest run src/composables/__tests__/agGridExcelBehaviors.spec.ts`
Expected: PASS (the 4 PR3a tests + the 4 new ones).

- [ ] **Step 7: Commit.**
```bash
git add frontend/src/composables/agGridExcelBehaviors.ts frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts
git commit -m "feat(grid): native Excel behaviors (undo/redo, copy, cell-editing) in the module"
```

---

## Task 2: Consolidate undo/redo off AGGridBase.vue

**Files:**
- Modify: `frontend/src/components/grids/AGGridBase.vue`
- Test: `frontend/src/composables/__tests__/agGridExcelBehaviorsConsolidation.spec.ts`

- [ ] **Step 1: Write the failing consolidation test.**
Create `frontend/src/composables/__tests__/agGridExcelBehaviorsConsolidation.spec.ts`:
```ts
// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

const src = readFileSync(
  fileURLToPath(new URL('../../components/grids/AGGridBase.vue', import.meta.url)),
  'utf-8',
)

describe('undo/redo is sourced from the isolation module, not hardcoded', () => {
  it('AGGridBase.vue no longer hardcodes undoRedoCellEditing props', () => {
    expect(src).not.toContain('undoRedoCellEditing')
  })
})
```

- [ ] **Step 2: Run it to see it fail.**
Run: `npx vitest run src/composables/__tests__/agGridExcelBehaviorsConsolidation.spec.ts`
Expected: FAIL — `AGGridBase.vue` still contains `:undoRedoCellEditing` (lines 76–77).

- [ ] **Step 3: Remove the hardcoded props.**
In `frontend/src/components/grids/AGGridBase.vue`, delete these two lines from the `<ag-grid-vue>` tag (around lines 76–77):
```html
      :undoRedoCellEditing="true"
      :undoRedoCellEditingLimit="20"
```
(The module now supplies them via `mergedGridOptions`, which the same tag already binds with `:gridOptions="mergedGridOptions"`.)

- [ ] **Step 4: Run the consolidation test + full suite + type-check.**
Run from `frontend/`: `npx vitest run src/composables/__tests__/agGridExcelBehaviorsConsolidation.spec.ts && npx vue-tsc --noEmit && npx vitest run`
Expected: consolidation test PASS; tsc 0; full suite green.

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/components/grids/AGGridBase.vue frontend/src/composables/__tests__/agGridExcelBehaviorsConsolidation.spec.ts
git commit -m "refactor(grid): source undo/redo from agGridExcelBehaviors (drop hardcoded props)"
```

---

## Task 3: Documentation

**Files:**
- Modify: `docs/frontend/ag-grid-excel-behaviors.md`

- [ ] **Step 1: Append the new behavior rows.**
Add these rows to the table in `docs/frontend/ag-grid-excel-behaviors.md` (after the `xlsxExport` row):
```markdown
| `undoRedo` | Undo / redo cell edits (Ctrl+Z / Ctrl+Y) | `undoRedoCellEditing` gridOption (limit 20) | Same native AG Grid option (no shim; flag stays on) |
| `copy` | Copy focused cell or whole selected rows (Ctrl+C) | AG default cell copy + `suppressCopyRowsToClipboard:false` | Enterprise clipboard / range copy (PR3c) |
| `cellEditing` | Type-to-edit, Esc cancels, commit on blur | `stopEditingWhenCellsLoseFocus` + AG default key editing | n/a (Community-capable) |
| `freezePanes` | Freeze columns + header row | per-grid colDef `pinned` + sticky header (no extra option) | Same native pinning |
| `quickFind` | Instant global filter (Ctrl+F style) | deferred — per-screen Search covers it (off by default) | n/a (deferred by product choice) |
```

- [ ] **Step 2: Run the doc-coverage test (from PR3a).**
Run from `frontend/`: `npx vitest run src/composables/__tests__/agGridExcelBehaviorsDoc.spec.ts`
Expected: PASS — every registry key (now 10) appears in the doc.

- [ ] **Step 3: Commit.**
```bash
git add docs/frontend/ag-grid-excel-behaviors.md
git commit -m "docs(grid): document the native Excel behaviors (PR3b)"
```

---

## Task 4: Verify — gates + PR

**Files:** none (verification).

- [ ] **Step 1: Static + unit gates.**
Run from `frontend/`:
```bash
npm run build && npx vitest run && npx vue-tsc --noEmit && npm run lint && npm audit
```
Expected: build OK; vitest pass (incl. the new module/consolidation tests); tsc 0; eslint clean; audit 0.

- [ ] **Step 2: Push + open PR (gate C + isolation/doc tests via CI).**
```bash
git push -u origin feat/vuetify-4-pr3b-native-excel-behaviors
gh pr create --base main --head feat/vuetify-4-pr3b-native-excel-behaviors \
  --title "feat(grid): PR3b — native Community Excel behaviors" \
  --body "PR3b of the Vuetify 4 migration §3e (see docs/superpowers/specs/2026-06-14-vuetify4-md3-pr3b-native-excel-behaviors-design.md). Extends the agGridExcelBehaviors module with undo/redo (consolidated off AGGridBase.vue), explicit whole-row copy, Excel cell-editing commit-on-blur, and registers freeze-panes (existing pinning + sticky header) + quick-find (deferred-off). Behavior-only; gate C verified by this PR's e2e-sqlite check. PR3c adds range selection + copy."
```
Expected: PR opens; 4 required checks run; merge on green; then PR3c.

---

## Self-review notes (author)

- **Spec coverage:** undoRedo consolidation (Tasks 1+2), copy fragment (Task 1), cellEditing fragment (Task 1), freezePanes registration (Task 1 meta + Task 3 doc), quickFind deferred-off (Task 1 default+meta, Task 3 doc); isolation extended (Task 1 master:false test); doc-coverage (Task 3); gate C via CI (Task 4).
- **No placeholders:** every flag, default, metadata row, fragment, and test is concrete; the AGGridBase.vue edit names the exact lines to delete.
- **Type consistency:** new flag keys `undoRedo`/`copy`/`cellEditing`/`freezePanes`/`quickFind` are used identically in the interface, defaults, `BEHAVIOR_META`, the fragment `on()` checks, tests, and doc rows; `ExcelBehaviorKey` (derived from the flags) stays correct automatically.
- **Risk:** undo/redo is behavior-preserving (relocated; the consolidation test + e2e prove it). copy/cellEditing are additive AG-Community options. freeze/quickFind add no runtime behavior (registration/doc only).
