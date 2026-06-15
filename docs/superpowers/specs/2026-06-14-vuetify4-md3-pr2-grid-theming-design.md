# Vuetify 4 + MD3 — PR2: Spreadsheet-natural AG Grid theming (design)

> Focused design for **PR2** of the Vuetify 4 migration. Parent spec:
> `2026-06-14-vuetify-4-migration-design.md` (§3d "Spreadsheet-natural grids",
> gates C / C2 / D). PR1 (foundation: cascade-layer fix, Carbon color
> unification, WCAG-AA sweep) is merged. This design resolves the "how" that
> the parent spec deferred "to the plan", grounded in live before/after mockups.

## Goal

Make the 9 AG Grids feel **spreadsheet-natural** for Excel-migrating operators —
compact rows, visible cell gridlines, clear headers — while staying
color-harmonized with the Carbon-seeded MD3 theme and keeping AG Grid
**functionality and the 10 Vuetify cell-renderer composables non-negotiable**.
Scope is **theming only**; Excel *behaviors* (paste/fill, keyboard nav, xlsx
export, quick-find, range copy) are **PR3** (§3e).

## Approach

Keep the existing **CSS-variable tinting of `ag-theme-material`**
(`src/assets/aggrid-theme.css`, already wired to `--cds-*` tokens, ~675 lines).
No migration to AG Grid's Theming API — CSS-var tinting suffices (parent spec
lists Theming-API migration as out-of-scope when so). Density is **not** a CSS
concern: AG Grid 35 ignores `--ag-row-height` from CSS for layout and uses the
JS `rowHeight`/`headerHeight` grid options, set centrally in
`useResponsive.ts` + `useAGGridBase.ts`.

## Decisions (validated via live before/after mockups)

| Aspect | Decision | Notes |
|---|---|---|
| **Row height (desktop)** | 44 → **38px** | `getRowHeight()` in `useResponsive.ts`; mobile/tablet scaled proportionally (mobile 36→32, tablet 40→36 to keep the ratio). |
| **Header height (desktop)** | 48 → **40px** | `headerHeight` in `useAGGridBase.ts` (mobile/tablet scaled). |
| **Gridlines** | **Add vertical** cell + header-cell borders | `border-right` via `--cds-border-subtle-00` (cells) / `--cds-border-subtle-01` (headers); horizontal row borders already present. Single biggest spreadsheet cue. |
| **Zebra striping** | **None** | Gridlines provide separation; matches Excel default and current behavior. |
| **Status/priority cells** | **Compact tags** | Shrink chip renderers (height/font/padding) so they sit cleanly in 38px rows; keep the color cue, lose the bulk. Confirm 👁/✕ action buttons fit. |
| **Cell text** | 13px, 10px horizontal padding | `--ag-font-size` / `--ag-cell-horizontal-padding` (pure CSS, applies live). |
| **Dark mode** | Already adapts via `--cds-*` | Verify gridlines visible on dark surfaces and compact tags read in both themes. |

### Key finding from the mockups

At aggressive Excel-tight density (~32px) the **current cell renderers clip and
overflow** (chips/progress/action buttons are sized for 44px rows). At the
chosen **38px**, the chips *almost* fit — so the **compact-tags** rework is a
required companion to the density change, not optional. This is the crux of
PR2's renderer work and the main regression surface for gate C.

## Files (anticipated)

- `src/composables/useResponsive.ts` — `getRowHeight()` density.
- `src/composables/useAGGridBase.ts` — `headerHeight`.
- `src/assets/aggrid-theme.css` — vertical gridlines, font/padding, dark-mode
  gridline visibility.
- Cell-renderer composables / shared chip styling (e.g.
  `useWorkOrderGridData.ts` and peers) — compact tags + action-button fit.

## Out of scope (PR3 / later)

Excel behavior layer (§3e), AG Grid Enterprise, a user-facing density toggle,
chart restyling, any non-grid screen changes.

## Validation

- **Gate C (functional, hard):** e2e — all 9 grids render; sort / filter /
  single-cell edit / pagination / keyboard nav work; the 10 cell-renderer
  composables display. (`npm run test:e2e:sqlite`, the grid specs.)
- **Gate C2 (spreadsheet-natural):** manual pass — compact density, visible
  gridlines, clear headers, recognizable selection/edit, Carbon-harmonized.
- **Gate D (visual, light + dark):** browser-agent sweep over grid screens vs
  the PR1 baseline — no clip/overflow/overlap; renderers + sizing correct.
- **a11y contrast gate:** the PR1 vitest gate stays green; compact tags keep
  WCAG-AA (re-run the local gradient-aware audit on grid screens).
- **Static gates:** build / vue-tsc / vitest / eslint / npm-audit green.

## Harness note

Faithful local run = backend `:8010` (`DEMO_MODE=true`,
`DATABASE_URL=sqlite:////tmp/kpi_harness.db`, run `uvicorn backend.main:app`
from repo root) + dev `:3010` with a **temporary** `vite.config.ts` proxy edit
`:8000`→`:8010` that **must be reverted before any commit** (gym-platform
squats `:8000`). Density mocks require the JS height edits + a fresh page load
(not just HMR). Screenshot harness lives in `frontend/.visual-baseline/`
(gitignored).
