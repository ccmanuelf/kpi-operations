# Vuetify 4 + MD3 — PR3c: Range selection + copy shim — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add flag-gated multi-cell range selection (Shift+click / Shift+Arrow) with a highlight and Ctrl+C → TSV copy in AG Grid Community, deferring to Enterprise when present.

**Architecture:** A `useGridRangeCopy` composable (pure helpers `rectFrom`/`isInRange`/`buildTsv` + reactive range state + AG-event handlers + a `cellClassRules` highlight) owned by the `agGridExcelBehaviors` module via a `rangeCopy` flag; `useAGGridBase` wires it. Built on public AG APIs (`getValue`, `getDisplayedRowAtIndex`, `getColumnState`, `refreshCells`) — no DOM mouse tracking.

**Tech Stack:** Vue 3.5 composables, AG Grid Community 35, Vitest. Loose typing to match the codebase.

**Spec:** `docs/superpowers/specs/2026-06-14-vuetify4-md3-pr3c-range-copy-design.md`.

**Branch:** `feat/vuetify-4-pr3c-range-copy` (spec already committed here).

---

## File structure (PR3c)

- `frontend/src/composables/useGridRangeCopy.ts` *(new)* — pure helpers + the range-copy composable.
- `frontend/src/composables/__tests__/useGridRangeCopy.spec.ts` *(new)* — pure-logic + enabled/disabled tests.
- `frontend/src/composables/agGridExcelBehaviors.ts` *(modify)* — add `rangeCopy` flag + metadata.
- `frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts` *(modify)* — assert `rangeCopy` registered/enabled.
- `frontend/src/composables/useAGGridBase.ts` *(modify)* — instantiate the composable, merge the highlight rule, wire cellClicked + keydown, Enterprise-defer.
- `frontend/src/components/grids/AGGridBase.vue` *(modify)* — remove the dead `enableRangeSelection` prop.
- `frontend/src/assets/aggrid-theme.css` *(modify)* — `.range-shim-selected` highlight.
- `docs/frontend/ag-grid-excel-behaviors.md` *(modify)* — add the `rangeCopy` row.

---

## Task 1: Pure helpers + range-copy composable

**Files:**
- Create: `frontend/src/composables/useGridRangeCopy.ts`
- Test: `frontend/src/composables/__tests__/useGridRangeCopy.spec.ts`

- [ ] **Step 1: Write the failing tests (pure logic + disabled no-op).**
Create `frontend/src/composables/__tests__/useGridRangeCopy.spec.ts`:
```ts
import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { rectFrom, isInRange, buildTsv, useGridRangeCopy } from '../useGridRangeCopy'

const COLS = ['a', 'b', 'c', 'd']

describe('useGridRangeCopy pure helpers', () => {
  it('rectFrom normalizes any anchor/focus into a rectangle (col order aware)', () => {
    expect(rectFrom({ rowIndex: 4, colId: 'c' }, { rowIndex: 1, colId: 'a' }, COLS))
      .toEqual({ rowStart: 1, rowEnd: 4, colIds: ['a', 'b', 'c'] })
    expect(rectFrom({ rowIndex: 2, colId: 'b' }, { rowIndex: 2, colId: 'b' }, COLS))
      .toEqual({ rowStart: 2, rowEnd: 2, colIds: ['b'] })
  })

  it('isInRange is true only inside the rectangle', () => {
    const rect = { rowStart: 1, rowEnd: 3, colIds: ['b', 'c'] }
    expect(isInRange(2, 'b', rect)).toBe(true)
    expect(isInRange(0, 'b', rect)).toBe(false)
    expect(isInRange(2, 'a', rect)).toBe(false)
    expect(isInRange(2, 'b', null)).toBe(false)
  })

  it('buildTsv emits tab/newline separated values via the getter', () => {
    const rect = { rowStart: 0, rowEnd: 1, colIds: ['a', 'b'] }
    const getValue = (r: number, c: string) => `${r}${c}`
    expect(buildTsv(rect, getValue)).toBe('0a\t0b\n1a\t1b')
    const withBlank = (r: number, c: string) => (r === 1 && c === 'b' ? null : `${r}${c}`)
    expect(buildTsv(rect, withBlank)).toBe('0a\t0b\n1a\t')
  })
})

describe('useGridRangeCopy composable', () => {
  const colState = COLS.map((colId) => ({ colId }))
  const makeApi = () => ({
    getColumnState: () => colState,
    getDisplayedRowAtIndex: (i: number) => ({ i }),
    getValue: (colId: string, node: { i: number }) => `${node.i}:${colId}`,
    refreshCells: () => {},
  })

  it('shift+click extends the range and reports multi-cell', () => {
    const api = ref(makeApi())
    const rc = useGridRangeCopy({ gridApi: api as never, enabled: ref(true) })
    rc.onCellClicked({ rowIndex: 1, column: { getColId: () => 'a' } })
    rc.onCellClicked({ rowIndex: 3, column: { getColId: () => 'c' }, event: { shiftKey: true } as MouseEvent })
    expect(rc.isMultiCell.value).toBe(true)
    expect(rc.rect.value).toEqual({ rowStart: 1, rowEnd: 3, colIds: ['a', 'b', 'c'] })
  })

  it('does nothing when disabled', () => {
    const api = ref(makeApi())
    const rc = useGridRangeCopy({ gridApi: api as never, enabled: ref(false) })
    rc.onCellClicked({ rowIndex: 1, column: { getColId: () => 'a' } })
    expect(rc.rect.value).toBeNull()
    expect(rc.rangeCellClassRules['range-shim-selected']({ rowIndex: 1, column: { getColId: () => 'a' } })).toBe(false)
  })
})
```

- [ ] **Step 2: Run to see them fail.**
Run from `frontend/`: `npx vitest run src/composables/__tests__/useGridRangeCopy.spec.ts`
Expected: FAIL — `../useGridRangeCopy` not found.

- [ ] **Step 3: Implement the composable.**
Create `frontend/src/composables/useGridRangeCopy.ts`:
```ts
// Flag-gated multi-cell range selection + TSV copy for AG Grid Community
// (range selection is Enterprise-only). Built on public AG APIs + events; no
// DOM mouse tracking. Owned by agGridExcelBehaviors via the `rangeCopy` flag.
// Enterprise: native cell selection / range copy — disable this when present.
// See docs/frontend/ag-grid-excel-behaviors.md.
import { ref, computed, type Ref } from 'vue'

export interface CellPos {
  rowIndex: number
  colId: string
}
export interface RangeRect {
  rowStart: number
  rowEnd: number
  colIds: string[]
}

export function rectFrom(anchor: CellPos, focus: CellPos, colOrder: string[]): RangeRect {
  const rowStart = Math.min(anchor.rowIndex, focus.rowIndex)
  const rowEnd = Math.max(anchor.rowIndex, focus.rowIndex)
  const ai = colOrder.indexOf(anchor.colId)
  const fi = colOrder.indexOf(focus.colId)
  const lo = Math.max(0, Math.min(ai, fi))
  const hi = Math.max(ai, fi)
  return { rowStart, rowEnd, colIds: colOrder.slice(lo, hi + 1) }
}

export function isInRange(rowIndex: number, colId: string, rect: RangeRect | null): boolean {
  if (!rect) return false
  return rowIndex >= rect.rowStart && rowIndex <= rect.rowEnd && rect.colIds.includes(colId)
}

export function buildTsv(
  rect: RangeRect,
  getValue: (_rowIndex: number, _colId: string) => unknown,
): string {
  const rows: string[] = []
  for (let r = rect.rowStart; r <= rect.rowEnd; r++) {
    rows.push(
      rect.colIds
        .map((c) => {
          const v = getValue(r, c)
          return v == null ? '' : String(v)
        })
        .join('\t'),
    )
  }
  return rows.join('\n')
}

interface GridApiLike {
  getColumnState?: () => { colId: string }[]
  getDisplayedRowAtIndex?: (_i: number) => unknown
  getValue?: (_colId: string, _node: unknown) => unknown
  refreshCells?: (_p?: { force?: boolean }) => void
}
interface ClickedCell {
  rowIndex: number
  column: { getColId: () => string }
  event?: MouseEvent
}

export function useGridRangeCopy(opts: { gridApi: Ref<GridApiLike | null>; enabled: Ref<boolean> }) {
  const anchor = ref<CellPos | null>(null)
  const focus = ref<CellPos | null>(null)

  const colOrder = (): string[] =>
    (opts.gridApi.value?.getColumnState?.() ?? []).map((c) => c.colId)

  const rect = computed<RangeRect | null>(() =>
    anchor.value && focus.value ? rectFrom(anchor.value, focus.value, colOrder()) : null,
  )
  const isMultiCell = computed(() => {
    const r = rect.value
    return !!r && (r.rowStart !== r.rowEnd || r.colIds.length > 1)
  })

  const refresh = (): void => opts.gridApi.value?.refreshCells?.({ force: true })

  const rangeCellClassRules = {
    'range-shim-selected': (p: { rowIndex: number; column: { getColId: () => string } }) =>
      opts.enabled.value && isInRange(p.rowIndex, p.column.getColId(), rect.value),
  }

  const onCellClicked = (e: ClickedCell): void => {
    if (!opts.enabled.value) return
    const pos = { rowIndex: e.rowIndex, colId: e.column.getColId() }
    if (e.event?.shiftKey && anchor.value) {
      focus.value = pos
    } else {
      anchor.value = pos
      focus.value = pos
    }
    refresh()
  }

  const getValue = (rowIndex: number, colId: string): unknown => {
    const api = opts.gridApi.value
    const node = api?.getDisplayedRowAtIndex?.(rowIndex)
    return node ? api?.getValue?.(colId, node) : undefined
  }

  const copyRange = async (): Promise<boolean> => {
    if (!opts.enabled.value || !isMultiCell.value || !rect.value) return false
    await navigator.clipboard.writeText(buildTsv(rect.value, getValue))
    return true
  }

  const extend = (dRow: number, dCol: number): void => {
    if (!focus.value) return
    const order = colOrder()
    const ci = order.indexOf(focus.value.colId)
    const nextCi = Math.max(0, Math.min(order.length - 1, ci + dCol))
    focus.value = {
      rowIndex: Math.max(0, focus.value.rowIndex + dRow),
      colId: order[nextCi] ?? focus.value.colId,
    }
    refresh()
  }

  const ARROWS: Record<string, [number, number]> = {
    ArrowUp: [-1, 0],
    ArrowDown: [1, 0],
    ArrowLeft: [0, -1],
    ArrowRight: [0, 1],
  }

  const onKeyDown = (e: KeyboardEvent): void => {
    if (!opts.enabled.value) return
    if (e.shiftKey && e.key in ARROWS) {
      if (!anchor.value) return
      e.preventDefault()
      const [dr, dc] = ARROWS[e.key]
      extend(dr, dc)
    } else if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C') && isMultiCell.value) {
      e.preventDefault()
      void copyRange()
    }
  }

  const clear = (): void => {
    anchor.value = null
    focus.value = null
    refresh()
  }

  return { rect, isMultiCell, rangeCellClassRules, onCellClicked, onKeyDown, copyRange, clear }
}
```

- [ ] **Step 4: Run the tests to PASS.**
Run: `npx vitest run src/composables/__tests__/useGridRangeCopy.spec.ts`
Expected: PASS (5 tests). Note: `navigator.clipboard` isn't exercised here (copyRange path is covered by the integration/manual check, not these unit tests).

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/composables/useGridRangeCopy.ts frontend/src/composables/__tests__/useGridRangeCopy.spec.ts
git commit -m "feat(grid): useGridRangeCopy — range selection + TSV copy shim (pure + composable)"
```

---

## Task 2: Register `rangeCopy` in the module

**Files:**
- Modify: `frontend/src/composables/agGridExcelBehaviors.ts`
- Test: `frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts`

- [ ] **Step 1: Add the failing test.**
Append inside the `describe('agGridExcelBehaviors', ...)` block in `agGridExcelBehaviors.spec.ts`:
```ts
  it('registers rangeCopy, enabled by default', () => {
    const { registry } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    const entry = registry.find((e) => e.key === 'rangeCopy')
    expect(entry?.enabled).toBe(true)
    expect(entry?.enterpriseEquivalent).toMatch(/Enterprise/i)
  })
```

- [ ] **Step 2: Run to see it fail.**
Run: `npx vitest run src/composables/__tests__/agGridExcelBehaviors.spec.ts`
Expected: FAIL — no `rangeCopy` entry.

- [ ] **Step 3: Add the flag, default, and metadata.**
In `agGridExcelBehaviors.ts`: add `rangeCopy: boolean` to `ExcelBehaviorFlags` (after `quickFind`); add `rangeCopy: true,` to `DEFAULT_EXCEL_BEHAVIOR_FLAGS`; and append to `BEHAVIOR_META` (after the `quickFind` entry):
```ts
  {
    key: 'rangeCopy',
    excelFeature: 'Select a cell range (Shift+click / Shift+Arrow) and copy it',
    communityMechanism: 'useGridRangeCopy shim — AG events + getValue + TSV clipboard',
    enterpriseEquivalent: 'Enterprise cell selection + range copy (disable this flag)',
  },
```
(No `gridOptions` fragment — the stateful work is in `useGridRangeCopy`, gated by the same flag.)

- [ ] **Step 4: Run the module tests to PASS.**
Run: `npx vitest run src/composables/__tests__/agGridExcelBehaviors.spec.ts`
Expected: PASS (all prior + the new one).

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/composables/agGridExcelBehaviors.ts frontend/src/composables/__tests__/agGridExcelBehaviors.spec.ts
git commit -m "feat(grid): register rangeCopy behavior + metadata in the module"
```

---

## Task 3: Integrate into useAGGridBase + remove the dead prop

**Files:**
- Modify: `frontend/src/composables/useAGGridBase.ts`
- Modify: `frontend/src/components/grids/AGGridBase.vue`

- [ ] **Step 1: Import the composable.**
After the `agGridExcelBehaviors` import block in `useAGGridBase.ts`, add:
```ts
import { useGridRangeCopy } from './useGridRangeCopy'
```

- [ ] **Step 2: Instantiate it with Enterprise-deferral.**
After the existing `pasteEnabled` computed, add:
```ts
  // rangeCopy is a Community shim; it yields to AG Grid Enterprise when its
  // native cell selection is present (Enterprise adds api.getCellRanges).
  const rangeCopyEnabled = computed(() => {
    const registered =
      excelBehaviors.value.registry.find((e) => e.key === 'rangeCopy')?.enabled ?? false
    const enterprisePresent =
      typeof (gridApi.value as { getCellRanges?: unknown } | null)?.getCellRanges === 'function'
    return registered && !enterprisePresent
  })
  const rangeCopy = useGridRangeCopy({ gridApi, enabled: rangeCopyEnabled })
```

- [ ] **Step 3: Merge the highlight rule into defaultColDef.**
In the `defaultColDef` computed, add a `cellClassRules` property (after `enableCellChangeFlash: true,`):
```ts
    cellClassRules: rangeCopy.rangeCellClassRules,
```

- [ ] **Step 4: Route cellClicked + add the keydown listener.**
Change `handleCellClicked` to also feed the range shim:
```ts
  const handleCellClicked = (event: unknown): void => {
    rangeCopy.onCellClicked(event as Parameters<typeof rangeCopy.onCellClicked>[0])
    emit('cell-clicked', event)
  }
```
And register/unregister the keydown listener alongside the existing paste listener. In the existing `onMounted`, after the paste block, add:
```ts
    if (rangeCopyEnabled.value) {
      document.addEventListener('keydown', rangeCopy.onKeyDown, true)
    }
```
In the existing `onUnmounted`, add:
```ts
    document.removeEventListener('keydown', rangeCopy.onKeyDown, true)
```

- [ ] **Step 5: Remove the dead `enableRangeSelection` prop.**
In `AGGridBase.vue`, delete the prop block (no callers use it; it's a Community no-op superseded by `rangeCopy`):
```js
  enableRangeSelection: {
    type: Boolean,
    default: true
  },
```

- [ ] **Step 6: Type-check + full suite.**
Run from `frontend/`: `npx vue-tsc --noEmit && npx vitest run`
Expected: tsc 0; all pass.

- [ ] **Step 7: Commit.**
```bash
git add frontend/src/composables/useAGGridBase.ts frontend/src/components/grids/AGGridBase.vue
git commit -m "feat(grid): wire range-copy shim into useAGGridBase (Enterprise-deferring); drop dead prop"
```

---

## Task 4: Highlight CSS

**Files:**
- Modify: `frontend/src/assets/aggrid-theme.css`

- [ ] **Step 1: Add the highlight class.**
Append to `aggrid-theme.css`:
```css
/* Range-copy shim highlight (PR3c) — reuses the Carbon range-selection token
   already themed for light + dark; mirrors Excel's range box. */
.ag-theme-material .range-shim-selected {
  background-color: var(--ag-range-selection-background-color, #edf5ff) !important;
}
```

- [ ] **Step 2: Build.**
Run: `npm run build 2>&1 | tail -2`
Expected: build OK.

- [ ] **Step 3: Commit.**
```bash
git add frontend/src/assets/aggrid-theme.css
git commit -m "style(grid): range-copy highlight (Carbon range token, light + dark)"
```

---

## Task 5: Documentation

**Files:**
- Modify: `docs/frontend/ag-grid-excel-behaviors.md`

- [ ] **Step 1: Add the row.**
Append to the table in `docs/frontend/ag-grid-excel-behaviors.md` (after the `quickFind` row):
```markdown
| `rangeCopy` | Select a cell range (Shift+click / Shift+Arrow) and copy it | `useGridRangeCopy` shim — AG events + getValue + TSV clipboard | Enterprise cell selection + range copy (disable this flag) |
```

- [ ] **Step 2: Run the doc-coverage test.**
Run from `frontend/`: `npx vitest run src/composables/__tests__/agGridExcelBehaviorsDoc.spec.ts`
Expected: PASS — all 11 registry keys documented.

- [ ] **Step 3: Commit.**
```bash
git add docs/frontend/ag-grid-excel-behaviors.md
git commit -m "docs(grid): document the rangeCopy behavior (PR3c)"
```

---

## Task 6: Verify — gates + harness check + PR

**Files:** none (verification).

- [ ] **Step 1: Static + unit gates.**
Run from `frontend/`:
```bash
npm run build && npx vitest run && npx vue-tsc --noEmit && npm run lint && npm audit
```
Expected: build OK; vitest pass (incl. the new range-copy + module + doc tests); tsc 0; eslint clean; audit 0.

- [ ] **Step 2: Manual harness check (Shift-select highlight + Ctrl+C), light + dark.**
Bring up the harness (backend :8010 + dev :3010 with the TEMP `vite.config` proxy `:8000`→`:8010`, per the PR2 plan's harness note). On the Work Orders grid, Shift+click two cells, confirm the rectangle highlights (blue tint) in light and dark, and that Ctrl+C copies TSV (paste into a text editor to verify rows/tabs). Then REVERT the temp proxy: `sed -i '' "s|target: 'http://localhost:8010'|target: 'http://localhost:8000'|" frontend/vite.config.ts` and confirm `git status` shows no `vite.config.ts`.

- [ ] **Step 3: Push + open PR (gate C + isolation/doc tests via CI).**
```bash
git push -u origin feat/vuetify-4-pr3c-range-copy
gh pr create --base main --head feat/vuetify-4-pr3c-range-copy \
  --title "feat(grid): PR3c — flag-gated range selection + copy" \
  --body "Final PR of the Vuetify 4 migration §3e (see docs/superpowers/specs/2026-06-14-vuetify4-md3-pr3c-range-copy-design.md). Adds a Community range-selection shim (Shift+click/Shift+Arrow) with a Carbon highlight and Ctrl+C TSV copy, via the useGridRangeCopy composable owned by agGridExcelBehaviors (rangeCopy flag), built on public AG APIs and deferring to Enterprise via getCellRanges feature-detect. Removes the dead enableRangeSelection prop. Gate C via this PR's e2e-sqlite check. Completes the migration."
```
Expected: PR opens; 4 required checks run; merge on green — migration complete.

---

## Self-review notes (author)

- **Spec coverage:** pure helpers + composable (Task 1), `rangeCopy` registry/flag/meta (Task 2), useAGGridBase integration + Enterprise-defer + dead-prop removal (Task 3), highlight CSS (Task 4), docs (Task 5), gates + harness (Task 6). Enterprise-deferral via `getCellRanges` (Task 3 Step 2). Isolation: disabled-no-op test (Task 1) + registry (Task 2).
- **No placeholders:** the full composable, all helpers, every test, and each integration edit are concrete with exact anchors.
- **Type consistency:** `CellPos`/`RangeRect`/`rectFrom`/`isInRange`/`buildTsv`/`useGridRangeCopy` and the `rangeCellClassRules['range-shim-selected']` key are used identically across the composable, tests, integration (`cellClassRules`), and the CSS class name (`.range-shim-selected`).
- **Risk:** the riskiest piece is the keydown/cellClicked wiring; the pure logic is fully unit-tested, the disabled path is asserted inert, and Task 6 Step 2 manually verifies the live highlight + clipboard. `refreshCells` re-applies the highlight on scroll (no DOM tracking). If the shim ever misbehaves, flipping `rangeCopy` (or `master`) off removes it entirely.
