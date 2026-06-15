# Vuetify 4 + MD3 — PR3a: Excel-behaviors isolation module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the single, flag-isolated `agGridExcelBehaviors` module and route the existing Excel behaviors (Enter-down/Tab-right keyboard nav + paste activation) through it, with a docs file and isolation/doc-coverage tests — no new behaviors.

**Architecture:** A pure composable `useAgGridExcelBehaviors(flags)` returns a `gridOptions` fragment + a `registry` of behavior metadata. `useAGGridBase` consumes it (replacing the inline `navigateToNextCell`, deriving paste-enabled from the registry). A master flag empties the fragment → clean Enterprise hand-off. Tests prove isolation + doc coverage.

**Tech Stack:** Vue 3.5 composables, AG Grid Community 35 (legacy CSS theming), Vitest. Loose typing (`Record<string, unknown>`) to match the codebase and avoid AG Grid generic-type cascades.

**Spec:** `docs/superpowers/specs/2026-06-14-vuetify4-md3-pr3a-excel-behaviors-isolation-design.md`.

**Branch:** `feat/vuetify-4-pr3a-excel-behaviors-isolation` (spec already committed here).

---

## File structure (PR3a)

- `frontend/src/composables/agGridExcelBehaviors.ts` *(new)* — flags type + defaults, behavior metadata, the `useAgGridExcelBehaviors` function and the moved `navigateToNextCell`.
- `frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts` *(new)* — isolation + keyboard-nav unit tests.
- `frontend/src/composables/__tests__/agGridExcelBehaviorsDoc.spec.ts` *(new)* — doc-coverage test (reads the markdown).
- `frontend/src/composables/useAGGridBase.ts` *(modify)* — consume the module; remove the inline `navigateToNextCell`; derive paste-enabled from the registry.
- `docs/frontend/ag-grid-excel-behaviors.md` *(new)* — one row per registered behavior.

---

## Task 1: The isolation module (flags + registry + keyboard nav)

**Files:**
- Create: `frontend/src/composables/agGridExcelBehaviors.ts`
- Test: `frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts`

- [ ] **Step 1: Write the failing tests.**
Create `frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts`:
```ts
import { describe, it, expect } from 'vitest'
import {
  useAgGridExcelBehaviors,
  DEFAULT_EXCEL_BEHAVIOR_FLAGS,
} from '../agGridExcelBehaviors'

describe('agGridExcelBehaviors', () => {
  it('emits the keyboard-nav grid option and an all-enabled registry by default', () => {
    const { gridOptions, registry } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    expect(typeof gridOptions.navigateToNextCell).toBe('function')
    expect(registry.length).toBeGreaterThanOrEqual(5)
    expect(registry.every((e) => e.enabled)).toBe(true)
    // every entry carries the metadata the docs need
    for (const e of registry) {
      expect(e.excelFeature).toBeTruthy()
      expect(e.communityMechanism).toBeTruthy()
      expect(e.enterpriseEquivalent).toBeTruthy()
    }
  })

  it('master:false removes every shim (empty fragment, registry all disabled)', () => {
    const { gridOptions, registry } = useAgGridExcelBehaviors({
      ...DEFAULT_EXCEL_BEHAVIOR_FLAGS,
      master: false,
    })
    expect(gridOptions.navigateToNextCell).toBeUndefined()
    expect(Object.keys(gridOptions)).toHaveLength(0)
    expect(registry.every((e) => !e.enabled)).toBe(true)
  })

  it('a single per-feature flag off disables only that behavior', () => {
    const { gridOptions, registry } = useAgGridExcelBehaviors({
      ...DEFAULT_EXCEL_BEHAVIOR_FLAGS,
      keyboardNav: false,
    })
    expect(gridOptions.navigateToNextCell).toBeUndefined()
    expect(registry.find((e) => e.key === 'excelPaste')?.enabled).toBe(true)
    expect(registry.find((e) => e.key === 'keyboardNav')?.enabled).toBe(false)
  })

  it('keyboard nav is Excel-style: Enter (13) moves down, Tab (9) keeps suggested', () => {
    const { gridOptions } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    const nav = gridOptions.navigateToNextCell as (p: unknown) => unknown
    const suggested = { rowIndex: 5, column: 'X' }
    const prev = { rowIndex: 5, column: 'COL' }
    expect(nav({ key: 13, nextCellPosition: suggested, previousCellPosition: prev }))
      .toEqual({ rowIndex: 6, column: 'COL' })
    expect(nav({ key: 9, nextCellPosition: suggested, previousCellPosition: prev }))
      .toBe(suggested)
  })
})
```

- [ ] **Step 2: Run it to see it fail.**
Run from `frontend/`: `npx vitest run src/composables/__tests__/agGridExcelBehaviors.spec.ts`
Expected: FAIL — `../agGridExcelBehaviors` not found.

- [ ] **Step 3: Implement the module.**
Create `frontend/src/composables/agGridExcelBehaviors.ts`:
```ts
// Single, flag-isolated home for Excel-like AG Grid behaviors (spec §3e).
// The ONLY place that emits Excel-behavior gridOptions fragments. Flip `master`
// (or a per-feature flag) off and the corresponding shim disappears so AG Grid
// Enterprise's native feature can take over with no conflicting handler.
// See docs/frontend/ag-grid-excel-behaviors.md.

export interface ExcelBehaviorFlags {
  master: boolean
  keyboardNav: boolean
  excelPaste: boolean
  csvImport: boolean
  csvExport: boolean
  xlsxExport: boolean
}

export const DEFAULT_EXCEL_BEHAVIOR_FLAGS: ExcelBehaviorFlags = {
  master: true,
  keyboardNav: true,
  excelPaste: true,
  csvImport: true,
  csvExport: true,
  xlsxExport: true,
}

export type ExcelBehaviorKey = Exclude<keyof ExcelBehaviorFlags, 'master'>

export interface ExcelBehaviorEntry {
  key: ExcelBehaviorKey
  excelFeature: string
  communityMechanism: string
  enterpriseEquivalent: string
  enabled: boolean
}

// Metadata for every behavior — drives both the registry and the docs table.
const BEHAVIOR_META: Omit<ExcelBehaviorEntry, 'enabled'>[] = [
  {
    key: 'keyboardNav',
    excelFeature: 'Enter moves down, Tab moves right',
    communityMechanism: 'navigateToNextCell gridOption',
    enterpriseEquivalent: 'Built-in AG Grid cell navigation (disable shim, use native)',
  },
  {
    key: 'excelPaste',
    excelFeature: 'Paste tabular data copied from Excel',
    communityMechanism: 'clipboard read + clipboardParser + paste-preview dialog',
    enterpriseEquivalent: 'Enterprise clipboard (processDataFromClipboard)',
  },
  {
    key: 'csvImport',
    excelFeature: 'Import a CSV file into the grid',
    communityMechanism: 'file read -> TSV -> shared paste pipeline',
    enterpriseEquivalent: 'n/a (Community-capable; no Enterprise overlap)',
  },
  {
    key: 'csvExport',
    excelFeature: 'Export the grid to CSV',
    communityMechanism: 'api.exportDataAsCsv (Community)',
    enterpriseEquivalent: 'n/a (Community-capable; no Enterprise overlap)',
  },
  {
    key: 'xlsxExport',
    excelFeature: 'Export the grid to .xlsx',
    communityMechanism: 'exceljs over row data (utils/excelExport)',
    enterpriseEquivalent: 'Enterprise api.exportDataAsExcel',
  },
]

// Excel-style cell navigation: Enter commits + moves down the same column;
// Tab keeps AG Grid's suggested next cell (moves right). Moved here from
// useAGGridBase so it lives behind the keyboardNav flag.
const excelNavigateToNextCell = (params: {
  key: number
  nextCellPosition: unknown
  previousCellPosition: { rowIndex: number; column: unknown }
}) => {
  if (params.key === 13) {
    return {
      rowIndex: params.previousCellPosition.rowIndex + 1,
      column: params.previousCellPosition.column,
    }
  }
  return params.nextCellPosition
}

export interface ExcelBehaviorsResult {
  gridOptions: Record<string, unknown>
  registry: ExcelBehaviorEntry[]
}

export function useAgGridExcelBehaviors(flags: ExcelBehaviorFlags): ExcelBehaviorsResult {
  const on = (key: ExcelBehaviorKey): boolean => flags.master && flags[key]
  const gridOptions: Record<string, unknown> = {}
  if (on('keyboardNav')) {
    gridOptions.navigateToNextCell = excelNavigateToNextCell
  }
  const registry: ExcelBehaviorEntry[] = BEHAVIOR_META.map((m) => ({
    ...m,
    enabled: on(m.key),
  }))
  return { gridOptions, registry }
}
```

- [ ] **Step 4: Run the tests to PASS.**
Run: `npx vitest run src/composables/__tests__/agGridExcelBehaviors.spec.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/composables/agGridExcelBehaviors.ts frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts
git commit -m "feat(grid): agGridExcelBehaviors isolation module (flags + registry)"
```

---

## Task 2: Integrate into useAGGridBase

**Files:**
- Modify: `frontend/src/composables/useAGGridBase.ts`

- [ ] **Step 1: Import the module.**
Near the other composable imports at the top of `useAGGridBase.ts`, add:
```ts
import {
  useAgGridExcelBehaviors,
  DEFAULT_EXCEL_BEHAVIOR_FLAGS,
} from './agGridExcelBehaviors'
```

- [ ] **Step 2: Compute effective behaviors (paste stays opt-in via the existing prop).**
Immediately after the `gridApi`/`columnApi` refs (around line 72), add:
```ts
  // All Excel behaviors route through the one isolated module. Paste remains
  // opt-in per grid via the existing `enableExcelPaste` prop; everything else
  // is Community default-on. A master switch lives in the module for the
  // Enterprise hand-off (see docs/frontend/ag-grid-excel-behaviors.md).
  const excelBehaviors = computed(() =>
    useAgGridExcelBehaviors({
      ...DEFAULT_EXCEL_BEHAVIOR_FLAGS,
      excelPaste: !!props.enableExcelPaste,
    }),
  )
  const pasteEnabled = computed(
    () => excelBehaviors.value.registry.find((e) => e.key === 'excelPaste')?.enabled ?? false,
  )
```

- [ ] **Step 3: Replace the inline navigateToNextCell with the module fragment.**
In the `mergedGridOptions` computed, delete the entire inline `navigateToNextCell: (params: {...}) => {...},` block (the ~20 lines shown in the spec) and instead spread the module fragment. The block becomes:
```ts
    singleClickEdit: isMobile.value || isTouchDevice(),

    ...excelBehaviors.value.gridOptions,

    ...(isMobile.value && {
```
(Everything else in `mergedGridOptions` stays unchanged.)

- [ ] **Step 4: Route paste-gating + toolbar height through the module.**
Replace `const toolbarHeight = computed(() => (props.enableExcelPaste ? 56 : 0))` with:
```ts
  const toolbarHeight = computed(() => (pasteEnabled.value ? 56 : 0))
```
Then `grep -n "props.enableExcelPaste" src/composables/useAGGridBase.ts` and replace each remaining `props.enableExcelPaste` used for paste gating (e.g. the keydown binding around line 375) with `pasteEnabled.value`. Leave the `AGGridBaseProps.enableExcelPaste` declaration itself.

- [ ] **Step 5: Expose the registry (for the doc test + future PRs) from the return.**
In `useAGGridBase`'s returned object, add `excelBehaviorRegistry: computed(() => excelBehaviors.value.registry),` alongside the other returns.

- [ ] **Step 6: Type-check + unit tests + keyboard-nav behavior unchanged.**
Run from `frontend/`: `npx vue-tsc --noEmit && npx vitest run`
Expected: tsc 0; all pass (the new module tests + the full suite; no existing spec asserted the inline nav).

- [ ] **Step 7: Commit.**
```bash
git add frontend/src/composables/useAGGridBase.ts
git commit -m "refactor(grid): route keyboard-nav + paste gating through agGridExcelBehaviors"
```

---

## Task 3: Documentation + doc-coverage test

**Files:**
- Create: `docs/frontend/ag-grid-excel-behaviors.md`
- Test: `frontend/src/composables/__tests__/agGridExcelBehaviorsDoc.spec.ts`

- [ ] **Step 1: Write the doc.**
Create `docs/frontend/ag-grid-excel-behaviors.md`:
```markdown
# AG Grid Excel behaviors

All Excel-like grid behaviors live in one isolated module
(`frontend/src/composables/agGridExcelBehaviors.ts`), gated by per-feature flags
plus a `master` switch. Flip a flag off and that shim disappears so AG Grid
Enterprise's native feature can take over with no conflicting handler. This file
documents every registered behavior; a test asserts it covers each registry key.

| Flag (key) | Excel feature | Community mechanism | Enterprise equivalent to defer to |
|---|---|---|---|
| `keyboardNav` | Enter moves down, Tab moves right | `navigateToNextCell` gridOption | Built-in AG Grid cell navigation (disable shim, use native) |
| `excelPaste` | Paste tabular data copied from Excel | clipboard read + clipboardParser + paste-preview dialog | Enterprise clipboard (processDataFromClipboard) |
| `csvImport` | Import a CSV file into the grid | file read → TSV → shared paste pipeline | n/a (Community-capable; no Enterprise overlap) |
| `csvExport` | Export the grid to CSV | `api.exportDataAsCsv` (Community) | n/a (Community-capable; no Enterprise overlap) |
| `xlsxExport` | Export the grid to .xlsx | exceljs over row data (`utils/excelExport`) | Enterprise `api.exportDataAsExcel` |

To disable everything (e.g. when adopting Enterprise), set `master: false` in the
flags passed to `useAgGridExcelBehaviors`; to defer a single behavior, set its
per-feature flag false. PR3b adds undo/redo, quick-find, copy, and freeze panes;
PR3c adds range selection + copy.
```

- [ ] **Step 2: Write the failing doc-coverage test.**
Create `frontend/src/composables/__tests__/agGridExcelBehaviorsDoc.spec.ts`:
```ts
// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import {
  useAgGridExcelBehaviors,
  DEFAULT_EXCEL_BEHAVIOR_FLAGS,
} from '../agGridExcelBehaviors'

const doc = readFileSync(
  fileURLToPath(new URL('../../../../docs/frontend/ag-grid-excel-behaviors.md', import.meta.url)),
  'utf-8',
)

describe('ag-grid-excel-behaviors doc coverage', () => {
  it('documents every registered behavior key', () => {
    const { registry } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    for (const entry of registry) {
      expect(doc).toContain(`\`${entry.key}\``)
    }
  })

  it('explains the master kill-switch', () => {
    expect(doc).toContain('master: false')
  })
})
```

- [ ] **Step 3: Run it.**
Run: `npx vitest run src/composables/__tests__/agGridExcelBehaviorsDoc.spec.ts`
Expected: PASS (the doc from Step 1 covers all 5 keys + the master switch). If a key is missing, add its row to the doc.

- [ ] **Step 4: Commit.**
```bash
git add docs/frontend/ag-grid-excel-behaviors.md frontend/src/composables/__tests__/agGridExcelBehaviorsDoc.spec.ts
git commit -m "docs(grid): Excel-behaviors reference + doc-coverage test"
```

---

## Task 4: Verify — gates + grid sanity + PR

**Files:** none (verification).

- [ ] **Step 1: Static + unit gates.**
Run from `frontend/`:
```bash
npm run build && npx vitest run && npx vue-tsc --noEmit && npm run lint && npm audit
```
Expected: build OK; vitest pass (incl. the 3 new specs); tsc 0; eslint clean; audit 0.

- [ ] **Step 2: Grid sanity (behavior-only change) — one entry grid, light.**
With the harness running (backend :8010 + dev :3010 + temp proxy per the PR2 plan's harness note), screenshot an entry grid to confirm the toolbar + grid still render:
```bash
cd frontend
node .visual-baseline/mockshot.mjs .visual-baseline/mock/pr3a-workorders.png light
```
Expected: "shot OK (grid present)"; toolbar + grid render unchanged (this PR changes behavior wiring, not looks). View the PNG to confirm. Then REVERT the temp proxy: `sed -i '' "s|target: 'http://localhost:8010'|target: 'http://localhost:8000'|" frontend/vite.config.ts` and confirm `git status` shows no `vite.config.ts`.

- [ ] **Step 3: Push + open PR (gate C + isolation gate via CI).**
```bash
git push -u origin feat/vuetify-4-pr3a-excel-behaviors-isolation
gh pr create --base main --head feat/vuetify-4-pr3a-excel-behaviors-isolation \
  --title "feat(grid): PR3a — Excel-behaviors isolation module" \
  --body "PR3a of the Vuetify 4 migration §3e (see docs/superpowers/specs/2026-06-14-vuetify4-md3-pr3a-excel-behaviors-isolation-design.md). Introduces the single flag-isolated agGridExcelBehaviors module (per-feature flags + master switch + registry), routes the existing Enter-down/Tab-right keyboard nav + paste gating through it, and adds docs/frontend/ag-grid-excel-behaviors.md + isolation & doc-coverage tests. No new behaviors (PR3b/3c follow). Gate C (AG Grid functional) verified by this PR's e2e-sqlite check."
```
Expected: PR opens; the 4 required checks run; merge on green; then PR3b.

---

## Self-review notes (author)

- **Spec coverage:** module + flags + registry (Task 1); single integration point + move navigateToNextCell + paste gating (Task 2); docs (Task 3 Step 1); isolation test (Task 1 master:false test) + doc-coverage test (Task 3); Enterprise-deferral metadata (module + doc). Gate C via CI (Task 4 Step 3); static gates (Task 4 Step 1).
- **No placeholders:** the full module, all four unit tests, the integration edits with exact anchors, the complete doc, and the doc test are concrete.
- **Type consistency:** `ExcelBehaviorFlags`, `ExcelBehaviorKey`, `ExcelBehaviorEntry`, `ExcelBehaviorsResult`, `useAgGridExcelBehaviors`, `DEFAULT_EXCEL_BEHAVIOR_FLAGS`, and registry keys (`keyboardNav`/`excelPaste`/`csvImport`/`csvExport`/`xlsxExport`) are used identically across module, tests, integration, and doc.
- **Risk:** integration is the only behavior-touching change; the keyboard-nav move is verified behavior-identical by Task 1's nav test, and paste gating is behavior-preserving when `master` is true (the only mode shipped). Local e2e can't run (port conflict) → gate C via CI.
