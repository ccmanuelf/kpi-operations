# Vuetify 4 + MD3 — PR2: Spreadsheet-natural AG Grid theming — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 9 AG Grids feel spreadsheet-natural (moderate-compact rows, visible gridlines, compact tags) while keeping every grid's function and the 10 cell-renderer composables intact.

**Architecture:** Keep CSS-variable tinting of `ag-theme-material`. Density is JS (grid `rowHeight`/`headerHeight`), set centrally in `useResponsive.ts` + `useAGGridBase.ts`. Gridlines + typography are CSS in `aggrid-theme.css`. Compact tags = a shared inline-style helper used by the status/priority HTML cell renderers. Validation is the repo's real workflow: grid e2e + the browser-screenshot harness, light + dark.

**Tech Stack:** Vue 3.5, AG Grid Community 35 (`ag-grid-vue3`, legacy CSS theming), Vitest, Playwright (e2e + local `.visual-baseline/` harness), Carbon `--cds-*` tokens.

**Spec:** `docs/superpowers/specs/2026-06-14-vuetify4-md3-pr2-grid-theming-design.md`.

**Branch:** `feat/vuetify-4-pr2-grid-theming` (design doc already committed here).

---

## File structure (PR2)

- `frontend/src/composables/useResponsive.ts` — `getRowHeight()` density (44→38 desktop, scaled).
- `frontend/src/composables/useAGGridBase.ts` — `headerHeight` (48→40 desktop, scaled).
- `frontend/src/composables/gridTagStyle.ts` *(new)* — shared compact-tag inline style; one source for status/priority/other chip renderers.
- `frontend/src/composables/useWorkOrderGridData.ts` — status/priority chip renderers → shared compact tag.
- `frontend/src/composables/__tests__/gridTagStyle.spec.ts` *(new)* — unit test for the helper.
- `frontend/src/assets/aggrid-theme.css` — vertical gridlines, cell typography, dark gridline visibility.

Other status/priority chip renderers (found via grep in Task 4) get the same shared helper.

---

## Harness setup (do once before Tasks 1–5 verification)

The faithful local run (per the design doc's harness note):

```bash
# backend on :8010 with a throwaway DB (gym-platform squats :8000)
cd /Users/mcampos.cerda/Developer/Programming/kpi-operations
DEMO_MODE=true DATABASE_URL="sqlite:////tmp/kpi_harness.db" \
  backend/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 &
# TEMP proxy edit — MUST be reverted before any commit (Task 5):
sed -i '' "s|target: 'http://localhost:8000'|target: 'http://localhost:8010'|" frontend/vite.config.ts
cd frontend && npm run dev -- --port 3010 &
```

Screenshot helper (already present, gitignored): `frontend/.visual-baseline/mockshot.mjs <outfile> <light|dark>` logs in and screenshots `/work-orders`. `capture.mjs <light|dark>` does the full screen set.

---

## Task 1: Baseline safety net

**Files:** none (verification + artifacts).

- [ ] **Step 1: Confirm grid e2e is green pre-change (gate C baseline).**
Run from `frontend/`:
```bash
npm run test:e2e:sqlite -- capacity-planning capacity-bom capacity-kpi-tracking floating-pool work-order
```
Expected: pass (records the green functional baseline; if any are already red, stop and report — do not build on red).

- [ ] **Step 2: Capture pre-change grid screenshots (light + dark).**
With the harness running:
```bash
cd frontend
node .visual-baseline/mockshot.mjs .visual-baseline/mock/pr2-before-light.png light
node .visual-baseline/mockshot.mjs .visual-baseline/mock/pr2-before-dark.png dark
```
Expected: both say "shot OK (grid present)". These are the gate-D comparison references.

---

## Task 2: Moderate-compact density

**Files:**
- Modify: `frontend/src/composables/useResponsive.ts` (getRowHeight)
- Modify: `frontend/src/composables/useAGGridBase.ts:141` (headerHeight)

- [ ] **Step 1: Lower row height (desktop 44→38, scale mobile/tablet).**
In `useResponsive.ts`, replace the `getRowHeight` body:
```ts
  const getRowHeight = (): number => {
    if (isMobile.value) return 32
    if (isTablet.value) return 36
    return 38
  }
```

- [ ] **Step 2: Lower header height to match.**
In `useAGGridBase.ts` line 141, change:
```ts
    headerHeight: isMobile.value ? 40 : isTablet.value ? 44 : 48,
```
to:
```ts
    headerHeight: isMobile.value ? 34 : isTablet.value ? 36 : 40,
```

- [ ] **Step 3: Type-check + unit tests (no behavior regressions).**
Run from `frontend/`: `npx vue-tsc --noEmit && npx vitest run`
Expected: tsc exit 0; all vitest pass (density is not asserted by existing specs).

- [ ] **Step 4: Visual sanity — rows denser, renderers not yet compacted.**
```bash
node .visual-baseline/mockshot.mjs .visual-baseline/mock/pr2-density-light.png light
```
Expected: ~10 rows visible (was 8). Chips/buttons may still be a tight fit — Task 4 fixes that. No console errors.

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/composables/useResponsive.ts frontend/src/composables/useAGGridBase.ts
git commit -m "feat(grid): moderate-compact density (38px rows / 40px header)"
```

---

## Task 3: Vertical gridlines + cell typography

**Files:**
- Modify: `frontend/src/assets/aggrid-theme.css`

- [ ] **Step 1: Add vertical gridlines + tighter cell typography.**
Append to the end of `aggrid-theme.css`:
```css
/* ============================================
   SPREADSHEET-NATURAL: vertical gridlines + compact cell type (PR2)
   Horizontal row borders already exist; vertical borders give the
   Excel grid feel. Colors track the Carbon border tokens so this
   adapts to dark mode automatically.
   ============================================ */
.ag-theme-material {
  --ag-font-size: 13px;
  --ag-cell-horizontal-padding: 10px;
}
.ag-theme-material .ag-cell {
  border-right: 1px solid var(--cds-border-subtle-00, #e0e0e0);
}
.ag-theme-material .ag-header-cell {
  border-right: 1px solid var(--cds-border-subtle-01, #c6c6c6);
}
/* don't double-border the last column against the grid edge */
.ag-theme-material .ag-cell:last-of-type,
.ag-theme-material .ag-header-cell:last-of-type {
  border-right: none;
}
```

- [ ] **Step 2: Build (CSS compiles) + visual check, light + dark.**
```bash
npm run build 2>&1 | tail -2
node .visual-baseline/mockshot.mjs .visual-baseline/mock/pr2-gridlines-light.png light
node .visual-baseline/mockshot.mjs .visual-baseline/mock/pr2-gridlines-dark.png dark
```
Expected: build OK; columns visibly separated by vertical lines in both themes; gridlines visible-but-subtle on the dark surface (if invisible in dark, bump the dark line to `--cds-border-subtle-01`). Confirm by viewing the PNGs.

- [ ] **Step 3: Commit.**
```bash
git add frontend/src/assets/aggrid-theme.css
git commit -m "feat(grid): vertical gridlines + compact cell typography"
```

---

## Task 4: Compact tags (status/priority renderers)

**Files:**
- Create: `frontend/src/composables/gridTagStyle.ts`
- Create: `frontend/src/composables/__tests__/gridTagStyle.spec.ts`
- Modify: `frontend/src/composables/useWorkOrderGridData.ts` (renderStatusChip/renderPriorityChip)
- Modify: other status/priority chip renderers found via grep (Step 5)

- [ ] **Step 1: Write the failing test for the shared tag style.**
Create `frontend/src/composables/__tests__/gridTagStyle.spec.ts`:
```ts
import { describe, it, expect } from 'vitest'
import { tagStyle } from '../gridTagStyle'

describe('gridTagStyle', () => {
  it('produces a compact square tag (not a pill) with the given color', () => {
    const css = tagStyle('#198038')
    expect(css).toContain('background: #198038')
    expect(css).toContain('border-radius: 3px') // square tag, not the old 12px pill
    expect(css).toContain('font-size: 11px')
    expect(css).toMatch(/padding:\s*1px 6px/) // tighter than the old 2px 8px
    expect(css).toContain('color: #ffffff')
  })
})
```

- [ ] **Step 2: Run it to see it fail.**
Run: `npx vitest run src/composables/__tests__/gridTagStyle.spec.ts`
Expected: FAIL — `../gridTagStyle` not found.

- [ ] **Step 3: Implement the helper.**
Create `frontend/src/composables/gridTagStyle.ts`:
```ts
// Shared inline style for compact, spreadsheet-natural status/priority tags in
// AG Grid HTML cell renderers. Square (radius 3px, not a pill) and tighter than
// the old chip so it sits cleanly in the 38px compact rows. White text on the
// caller's solid color — callers pass AA-safe colors (see PR1 a11y work).
export const tagStyle = (background: string): string => `
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 600;
    line-height: 1.4;
    color: #ffffff;
    background: ${background};
  `
```

- [ ] **Step 4: Make the test pass + point the work-order renderers at it.**
Run: `npx vitest run src/composables/__tests__/gridTagStyle.spec.ts` → PASS.
Then in `useWorkOrderGridData.ts`, import the helper and replace the inline `span.style.cssText = \`...\`` blocks in BOTH `renderStatusChip` and `renderPriorityChip` with `span.style.cssText = tagStyle(color)`:
```ts
import { tagStyle } from './gridTagStyle'
// ...inside renderStatusChip, after `const color = STATUS_COLORS[...]`:
span.textContent = status
span.style.cssText = tagStyle(color)
return span
// ...inside renderPriorityChip, after `const color = PRIORITY_COLORS[...]`:
span.textContent = priority
span.style.cssText = tagStyle(color)
```

- [ ] **Step 5: Apply the same helper to the other chip renderers.**
Find them:
```bash
grep -rn "border-radius: 12px" frontend/src/composables
```
For each `render*Chip`/tag renderer that builds a colored pill span, replace its inline `cssText` with `tagStyle(color)` (import the helper). Do NOT change the color values (those are the AA-verified ones from PR1). Leave muted `'--'`/`'-'` empty-state spans as they are.

- [ ] **Step 6: Unit tests + type-check.**
Run from `frontend/`: `npx vue-tsc --noEmit && npx vitest run`
Expected: tsc 0; all pass (including any composable spec that asserts renderer output — if a spec asserts the old `border-radius: 12px`, update that assertion to `3px`, it codified the old style).

- [ ] **Step 7: Visual — tags fit 38px rows cleanly, no clipping, light + dark.**
```bash
node .visual-baseline/mockshot.mjs .visual-baseline/mock/pr2-tags-light.png light
node .visual-baseline/mockshot.mjs .visual-baseline/mock/pr2-tags-dark.png dark
```
Expected (view the PNGs): status/priority tags are compact squares fully inside their rows; progress bars and the 👁/✕ action buttons are not clipped. If action buttons still clip, reduce their renderer button size in the same composable (height ≤ 28px) — show the change.

- [ ] **Step 8: Commit.**
```bash
git add frontend/src/composables/gridTagStyle.ts frontend/src/composables/__tests__/gridTagStyle.spec.ts frontend/src/composables/*GridData.ts frontend/src/composables/useWorkOrderGridData.ts
git commit -m "feat(grid): compact square tags that fit the dense rows"
```

---

## Task 5: Verify — gates + browser-agent pass + PR

**Files:** `frontend/vite.config.ts` (revert temp proxy only).

- [ ] **Step 1: Static + unit gates.**
Run from `frontend/`:
```bash
npm run build && npx vitest run && npx vue-tsc --noEmit && npm run lint && npm audit
```
Expected: build OK; vitest pass; tsc 0; eslint clean; audit 0. (The PR1 a11y contrast gate runs here — must stay green.)

- [ ] **Step 2: Grid functional gate (C) — e2e.**
Run: `npm run test:e2e:sqlite`
Expected: green. All 9 grids render/sort/filter/single-cell-edit/paginate; the 10 renderer composables display. Fix any `.ag-*` selector a spec legitimately depends on; do not weaken assertions.

- [ ] **Step 3: Browser-agent visual + spreadsheet-natural pass (gates C2 + D), light + dark.**
Run the full capture and view the grid screens vs the Task-1 baseline:
```bash
node .visual-baseline/capture.mjs light
node .visual-baseline/capture.mjs dark
```
Confirm per grid screen (work-orders, capacity-planning, simulation-v2, the entry grids): compact density, visible gridlines, compact tags, **nothing clipped/overflowing/overlapped**, renderers + sizing correct, Carbon-harmonized in both themes. Any regression → fix and re-run.

- [ ] **Step 4: a11y re-audit on grid screens.**
```bash
node .visual-baseline/contrast.mjs light ; node .visual-baseline/contrast.mjs dark
```
Expected: 0 real AA failures (compact tags keep white-on-color AA; the empty-state muted spans are non-essential `'-'`). Fix any new failure.

- [ ] **Step 5: REVERT the temp proxy edit (mandatory before commit).**
```bash
cd /Users/mcampos.cerda/Developer/Programming/kpi-operations
sed -i '' "s|target: 'http://localhost:8010'|target: 'http://localhost:8000'|" frontend/vite.config.ts
grep -n "target:" frontend/vite.config.ts   # expect :8000
git status --short                             # expect NO frontend/vite.config.ts
```

- [ ] **Step 6: Push + open PR.**
```bash
git push -u origin feat/vuetify-4-pr2-grid-theming
gh pr create --base main --head feat/vuetify-4-pr2-grid-theming \
  --title "feat(ui): PR2 — spreadsheet-natural AG Grid theming" \
  --body "PR2 of the Vuetify 4 migration (see docs/superpowers/specs/2026-06-14-vuetify4-md3-pr2-grid-theming-design.md). Moderate-compact density (38px rows / 40px header), vertical gridlines, compact square tags. AG Grid function + the 10 cell-renderer composables unchanged. Gates: build/vitest/vue-tsc/eslint/npm-audit + grid e2e green; browser-agent visual + a11y pass, light + dark."
```
Expected: PR opens; monitor the 4 required checks; merge on green; then PR3 (Excel-behavior layer, §3e).

---

## Self-review notes (author)

- **Spec coverage:** density (Task 2), gridlines/typography (Task 3), compact tags (Task 4), dark-mode + gates C/C2/D + a11y (Tasks 3/5). Excel behaviors are explicitly PR3 — out of this plan.
- **No placeholders:** density values, the full `tagStyle` helper + its test, the exact renderer edits, and a worked grep to find sibling renderers are all concrete. The sibling-renderer count isn't enumerated until Task 4 Step 5's grep runs — that grep is the bound.
- **Type consistency:** `tagStyle(background: string): string` is used identically in the helper, its test, and the renderer edits.
- **Risk:** the renderer fit at 38px is the main regression surface (gate C). Task 4 Step 7 explicitly checks action-button/progress clipping; if 38px proves too tight for a specific renderer, the density is a one-line revert to 40px in Task 2 with no other rework.
