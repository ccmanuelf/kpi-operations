# AG-Grid Header-Text Clipping Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop AG-Grid column-header text from clipping at the top (D→U, E→F) by reconciling the header height and giving the header label a self-contained, centered line-box — app-wide via the shared theme.

**Architecture:** Two shared-theme CSS changes (align the base `--ag-header-height` to the JS `headerHeight`, and center the header label with `line-height: normal`) plus a vitest source-parsing guard that pins JS-height == CSS-var and the presence of the non-clip label rules. No JS/grid-option change.

**Tech Stack:** CSS (`frontend/src/assets/aggrid-theme.css`), Vue 3 + AG Grid legacy Material theme, vitest.

**Spec:** `docs/superpowers/specs/2026-07-13-grid-header-clipping-design.md`.

## Global Constraints

- Fix is CSS-only in the shared theme + one guard test. **Do not change** `useAGGridBase.ts` (the JS `headerHeight` 40/36/34 stays the row-height source).
- Base (desktop) `--ag-header-height` must equal the JS desktop `headerHeight` = **40px**. Responsive vars (`40px` @≤768px, `36px` compact) stay.
- Header text must not clip at any breakpoint: `.ag-header-cell-label { align-items: center }` + `.ag-header-cell-text { line-height: normal }` (keep the existing `overflow: hidden; text-overflow: ellipsis` on `.ag-header-cell-text` for horizontal truncation).
- No color/token change (the WCAG-AA contrast a11y gate must stay green untouched).
- Frontend: `npm run test`, `npm run lint`, `npm run typecheck`; coverage thresholds 32/25/25/34. Conventional commits. Files under 500 lines.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/assets/aggrid-theme.css` | Modify (L20; `.ag-header-cell-label` ~L94; `.ag-header-cell-text` ~L98) | The fix: 48→40 base header height + centered, non-clipping label |
| `frontend/src/theme/__tests__/aggrid-header-height.spec.ts` | Create | Guard: JS `headerHeight` == CSS base `--ag-header-height`; label non-clip rules present |

---

### Task 1: Reconcile header height + non-clipping label + guard test

**Files:**
- Modify: `frontend/src/assets/aggrid-theme.css`
- Test: `frontend/src/theme/__tests__/aggrid-header-height.spec.ts`

**Interfaces:** none (self-contained shared-theme fix + guard).

- [ ] **Step 1: Write the failing guard test**

Create `frontend/src/theme/__tests__/aggrid-header-height.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Source-parsing guard (mirrors contrast.a11y.spec.ts): the header row height is
// set in JS (useAGGridBase headerHeight) AND the theme var (--ag-header-height);
// when they disagree the legacy theme clips the header text. Pin them equal, and
// pin the label rules that keep the text vertically centered and un-clipped.

const css = readFileSync(
  fileURLToPath(new URL('../../assets/aggrid-theme.css', import.meta.url)),
  'utf8',
)
const base = readFileSync(
  fileURLToPath(new URL('../../composables/useAGGridBase.ts', import.meta.url)),
  'utf8',
)

/** The desktop JS header height = the final integer in the headerHeight ternary. */
function jsDesktopHeaderHeight(src: string): number {
  const line = src.split('\n').find((l) => l.includes('headerHeight:'))
  if (!line) throw new Error('headerHeight not found in useAGGridBase.ts')
  const ints = line.match(/\d+/g)
  if (!ints || ints.length === 0) throw new Error('no integer in headerHeight line')
  return Number(ints[ints.length - 1]) // desktop is the trailing ternary value
}

/** The base (desktop) --ag-header-height = the first declaration in the file
 *  (inside `.ag-theme-material {}`, before the @media / compact overrides). */
function cssBaseHeaderHeight(src: string): number {
  const m = src.match(/--ag-header-height:\s*(\d+)px/)
  if (!m) throw new Error('--ag-header-height not found in aggrid-theme.css')
  return Number(m[1])
}

describe('AG-Grid header height consistency (anti-clipping)', () => {
  it('base --ag-header-height equals the JS desktop headerHeight', () => {
    expect(cssBaseHeaderHeight(css)).toBe(jsDesktopHeaderHeight(base))
  })

  it('the header label is vertically centered', () => {
    // .ag-header-cell-label { ... align-items: center ... }
    expect(css).toMatch(/\.ag-header-cell-label\s*\{[^}]*align-items:\s*center/)
  })

  it('the header text uses a self-contained line-height so it cannot clip', () => {
    // .ag-header-cell-text { ... line-height: normal ... }
    expect(css).toMatch(/\.ag-header-cell-text\s*\{[^}]*line-height:\s*normal/)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/theme/__tests__/aggrid-header-height.spec.ts`
Expected: FAIL — the first test fails (`48` !== `40`), and the label/line-height tests fail (rules absent).

- [ ] **Step 3: Reconcile the base header height (48 → 40)**

In `frontend/src/assets/aggrid-theme.css`, inside the base `.ag-theme-material {}` block, change line ~20:

```css
  /* Header - Carbon Data Table Header */
  --ag-header-height: 40px;   /* was 48px — must match useAGGridBase headerHeight (40) so the theme's header line-box fits the 40px row and doesn't clip the text top */
```

(Leave the `@media (max-width: 768px)` `--ag-header-height: 40px` and the `.ag-compact` `36px` overrides unchanged.)

- [ ] **Step 4: Center the header label + give the text a non-clipping line-height**

In `frontend/src/assets/aggrid-theme.css`, update the two existing header rules (~L94 and ~L98):

```css
.ag-theme-material .ag-header-cell-label {
  justify-content: flex-start;
  align-items: center;   /* vertically center the label so text can't overhang/clip */
}

.ag-theme-material .ag-header-cell-text {
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: normal;   /* font-intrinsic line-box (~17px) fits any 34-40px header */
}
```

- [ ] **Step 5: Run the guard test to verify it passes**

Run: `cd frontend && npx vitest run src/theme/__tests__/aggrid-header-height.spec.ts`
Expected: 3 passed.

- [ ] **Step 6: Run the a11y contrast gate + full frontend suite + lint + typecheck**

Run: `cd frontend && npx vitest run src/theme/__tests__/contrast.a11y.spec.ts && npm run test && npm run lint && npm run typecheck`
Expected: contrast gate still passes (no token/color change), full suite passes with the new guard, lint clean, `vue-tsc` clean, coverage thresholds met.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/assets/aggrid-theme.css frontend/src/theme/__tests__/aggrid-header-height.spec.ts
git commit -m "fix(grid): reconcile AG-Grid header height + center label so header text stops clipping"
```

---

## Verification (whole-PR definition of done)

1. `cd frontend && npm run test && npm run lint && npm run typecheck` — all pass; the new guard + contrast a11y gate green.
2. `git diff main...HEAD --stat` shows only `aggrid-theme.css` + the new guard test (+ the spec/plan docs).
3. Final whole-branch review + `/code-review` + `/cross-review`; all 7 CI checks green (incl. the e2e browser a11y gate over the 14 screens); merge on user confirmation.
4. Post-merge: rebuild + deploy the frontend to the VM (`docker compose -f docker-compose.prod.yml build frontend && up -d`) and **live-verify** header readability — screenshot a data grid (Floating-Pool) and a capacity grid header in light and dark; confirm no top clipping.
