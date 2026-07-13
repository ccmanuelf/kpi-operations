# AG-Grid Header-Text Clipping — Root-Cause Fix — Design

**Date:** 2026-07-13
**Status:** Design approved (user, 2026-07-13) — pending implementation plan
**Trigger:** On the live VM (ES locale), every AG-Grid column header renders with its top ~third clipped — "Disponible" reads "Uisponible" (D top cut), "Estado" reads "Fstado" (E→F), "Orden #" reads "Urgen #". App-wide (all grids inherit the shared theme). Screenshots from Capacity-Planning Órdenes and Floating-Pool grids.

## Root cause

The header row **height is set in two places that disagree**:
- `frontend/src/composables/useAGGridBase.ts:171` — the JS grid option `headerHeight: isMobile ? 34 : isTablet ? 36 : 40` (desktop **40px**) sets the actual header-row DOM height.
- `frontend/src/assets/aggrid-theme.css:20` — the legacy Material theme variable `--ag-header-height: 48px` (desktop) drives the theme's internal header label sizing (line-box / vertical metrics).

The theme sizes the header label's line-box off the 48px variable, but the row is only 40px tall, so the line-box overhangs the top of the cell; with `.ag-header-cell-text { overflow: hidden }` (aggrid-theme.css:99) the overhang is clipped — cutting the tops of the letters. The responsive variants are also inconsistent (JS 40/36/34 vs CSS 48 / 40 @≤768px / 36 compact).

The header text has **no** explicit `line-height` today, so it inherits the theme's height-derived metric — which is exactly the 48-vs-40 overhang.

## Design (Approach A — reconcile to one height + guarantee non-clipping label)

Two-part fix in the shared theme so it applies to every grid, plus a guard test:

### 1. Reconcile the desktop header height (single source of truth)

In `frontend/src/assets/aggrid-theme.css`, change the base (desktop) `--ag-header-height` from `48px` to **`40px`** (line 20) so it matches the JS `headerHeight` desktop value (40). The responsive vars stay (`40px` @≤768px line 582, `36px` compact line 605) — they are ≥ the text height and, after part 2, cannot clip regardless.

### 2. Make the header label vertically centered with a self-contained line-height (universal no-clip guarantee)

Add to the `.ag-theme-material` header rules in `aggrid-theme.css`:

```css
.ag-theme-material .ag-header-cell-label {
  align-items: center;   /* vertically center the label within the header row */
}

.ag-theme-material .ag-header-cell-text {
  line-height: normal;   /* natural line-box that fits any header height ≥ ~20px */
  /* keep the existing overflow:hidden + text-overflow:ellipsis for horizontal truncation */
}
```

`line-height: normal` gives the header text a font-intrinsic line-box (~1.2×14px ≈ 17px) that fits comfortably inside a 34–40px header, and `align-items: center` centers it — so the top can never be clipped at ANY of the breakpoint heights. This is the actual guarantee; part 1 removes the specific 48-vs-40 overhang and keeps the numbers honest.

`useAGGridBase.ts` is **not** changed — the JS `headerHeight` (40/36/34) stays as the row-height source; the CSS is aligned to it.

## Verification

### Deterministic guard (vitest)
New `frontend/src/assets/__tests__/aggrid-header-height.spec.ts`:
- Parse `useAGGridBase.ts`, extract the desktop `headerHeight` literal (the value after the last ternary `:` → `40`).
- Parse `aggrid-theme.css`, extract the base (`:root`/`.ag-theme-material` desktop) `--ag-header-height` (`40px`).
- **Assert they are equal** (40 == 40) — pins the reconciliation so the mismatch can't silently return.
- Assert the CSS contains `.ag-header-cell-text { … line-height: normal … }` and `.ag-header-cell-label { … align-items: center … }` — pins the non-clip guarantee.

This mirrors the repo's existing source-parsing gates (the deterministic contrast a11y gate parses `carbon-tokens.css`).

### Live visual check
After deploy-to-preview or on the VM: screenshot representative grid headers (a data grid like Floating-Pool and a capacity grid) in **light and dark** at desktop and a narrower (tablet) width; confirm full-height header text with no top clipping. Cell-content readability is verified separately once the demo-seed data populates the grids (next work item).

### Existing gates
Frontend `npm run test` (incl. the contrast a11y gate — unaffected: no color/token change), `npm run lint`, `vue-tsc`; the e2e browser a11y gate (14 screens light/dark) must stay green (header height/line-height change must not regress contrast or layout).

## Definition of done

- Base `--ag-header-height` == JS desktop `headerHeight` (both 40); header label centered with `line-height: normal`; no header text clips at any breakpoint.
- Guard test pins both invariants; full frontend suite + lint + typecheck green; a11y gates green; all 7 CI checks green; `/code-review` + `/cross-review`; merge on user confirmation.
- Post-merge: deploy the frontend to the VM (rebuild frontend image + `up -d`) and visually confirm headers are readable in the live app.

## Out of scope

- Changing header height to Carbon's 48px (considered; rejected — keeps the current compact look with minimal visual change).
- Cell/row-height or any non-header grid styling; the `--ag-row-height`/`.ag-cell { line-height: 46px }` rules are unrelated to the header clip and unchanged.
- Broader grid readability of *content* (verified on seeded data in the follow-on UI-validation pass), and any per-grid column-width/wrapping tuning.
