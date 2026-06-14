# Vuetify 3 → 4 Migration + MD3 Modernization — Design Spec

**Date:** 2026-06-14
**Status:** Approved (design, revised); pending implementation-plan
**Approach:** **Full MD3 modernization** with a **Carbon-seeded tonal color
system** (MD3 takes precedence over exact Carbon hues where they conflict),
**spreadsheet-natural AG Grid theming**, and a **flag-isolated, documented set
of Excel-like grid behaviors** built within AG Grid Community — for users
migrating from Microsoft Excel.
**Branch target:** `chore/vuetify-4-migration` (revertible; will split into
sequenced PRs)

---

## 1. Goal

Upgrade the frontend from Vuetify 3.5 to Vuetify 4.1.1 **and** modernize the UI
to Material Design 3, using the IBM Carbon palette as the **seed** for an MD3
tonal color system. The result should read as clearly modernized (MD3
typography, shape, elevation, state layers, tonal surfaces) while the data
grids keep a **spreadsheet-natural** feel for users migrating from Microsoft
Excel. AG Grid **functionality and compatibility are non-negotiable**.

This revises the original "look-preserving" design: the user chose full MD3
adoption with a real tonal system, prioritizing the modernized look over exact
Carbon hues, and specified that grids must feel spreadsheet-natural.

## 2. Context & findings (discovery, 2026-06-14)

**Footprint:** 74 distinct Vuetify components, ~4,794 `<v-…>` instances across
118 of 125 `.vue` files. Carbon theme in JS (`src/plugins/vuetify.ts`,
light+dark, ~16 component defaults), MDI font icons, `vite-plugin-vuetify`
`autoImport: true`. **~150+ deep `.v-*` CSS overrides** in `main.css` +
`responsive.css`, many **hardcoding Carbon hex values**. ~157 test selectors
target `.v-*` (~16 unit, ~141 e2e). Tailwind 4 coexists.

**Vuetify 4 is a styling-level major** (per upgrade guide + v4.1.1
package.json): MD2→MD3 typography, reduced grid breakpoints, CSS reset,
elevation, and styles in CSS `@layer` — each with a revert snippet. Component
public APIs (data-table/list/select/form/dialog/nav-drawer/grid) are **not**
broken; the only API change (date-adapter import path) is unused here. **We are
deliberately adopting (not reverting) the MD3 changes.**

**Versions already satisfied:** Vuetify 4.1.1 peers `vue: ^3.5.0`,
`vite-plugin-vuetify: >=2.1.0`. **Vue 3.5.34 already installed** (raise floor to
`^3.5.0`; no runtime Vue change). `vite-plugin-vuetify` already 2.1.3. No
`engines` constraint (Node 22 fine).

**AG Grid:** `ag-grid-community`/`ag-grid-vue3` 35.3.0, **Community** edition,
legacy CSS theming (`ag-grid.css` + `ag-theme-material.css`) under
`.ag-theme-material`; 9 grid mounts; 10 `use*GridData` composables render
Vuetify in cell renderers. `ag-grid-vue3@35.3.0` peer `vue: ^3.5.32` already
satisfied → **no Vue/AG-Grid incompatibility introduced**. Styles scoped under
`.ag-*`; `@layer` keeps Vuetify from bleeding in.

## 3. Approach

Three coordinated changes:

**3a. Upgrade.** `vuetify@4.1.1`, raise `vue` floor `^3.4.0`→`^3.5.0`, keep
`vite-plugin-vuetify@2.1.3`. Adopt MD3 defaults (typography, shape, elevation,
state layers) and CSS `@layer`.

**3b. MD3 tonal color system, Carbon-seeded.** Rebuild the theme: seed MD3
tonal palettes from the Carbon hues (primary `#0f62fe`, secondary, semantic
success/error/info, neutrals) and derive the full MD3 role set
(`primary`/`on-primary`/`primary-container`/`on-primary-container`, `surface`
tones, etc.) for **light and dark**. Implementation detail to confirm in the
plan: how much tonal generation Vuetify 4 does natively vs. deriving ramps from
seeds with `@material/material-color-utilities`. Where exact Carbon hues
conflict with MD3 tonal/contrast correctness, **MD3 wins**.

**3c. Rebase CSS overrides onto theme tokens.** The ~150+ `.v-*` rules that
hardcode Carbon hexes must reference theme CSS variables / tokens instead, so
they live in harmony with the tonal palette under `@layer` (this is the main
labor and the primary regression surface).

**3d. Spreadsheet-natural grids.** Theme AG Grid for Excel-migrating users:
compact density, visible cell gridlines, clear column headers, familiar
selection / single-cell edit / keyboard navigation — **color-harmonized** with
the MD3 theme tokens (surface/on-surface/header/hover/border) so grids look
intentional next to MD3 chrome, but ergonomically spreadsheet-first, not
MD3-airy. Mechanism (CSS-variable tinting of `ag-theme-material`, switching to
a denser AG Grid base theme, or AG Grid's Theming API) decided in the plan,
constrained to **Community-edition capabilities**.

**3e. Excel-like behaviors (Community, flag-isolated, documented).** Add Excel
ergonomics within AG Grid Community, architected so they cleanly switch off if
the project later adopts AG Grid Enterprise (whose native equivalents must not
collide with our shims). Feasibility tiers:

- **Native Community (config only):** freeze panes (pinned columns + pinned
  top rows), undo/redo cell editing (`undoRedoCellEditing`), CSV export,
  quick-find filter, Excel-style keyboard nav (Enter commits + moves down,
  Tab moves right, type-to-edit, Esc cancels), single-cell + whole-row copy.
- **Clean custom, zero Enterprise overlap:** **.xlsx export via the existing
  `exceljs` dependency** (operates on grid row data; not an AG Grid feature, so
  it never conflicts with Enterprise's Excel export).
- **Custom, flag-gated (real Enterprise overlap):** multi-cell **range
  selection + range copy** — shimmed via cell-selection state + clipboard
  handlers, behind its own feature flag that **defers to Enterprise** when the
  Enterprise module is present.
- **Deferred (not cleanly feasible in Community):** fill-handle drag — flagged
  for Enterprise, not emulated.

**Clean-isolation architecture (mandatory):** all custom Excel behavior lives
in ONE place — an `agGridExcelBehaviors` module/composable that emits
`gridOptions` fragments + event handlers, gated by per-feature flags
(default-on for Community) with a single master switch. No monkey-patching of
AG Grid internals. Switching to Enterprise = flip the relevant flags off so the
native features take over with no duplicated/conflicting handlers. Each shim
carries an inline comment naming its Enterprise-native equivalent and how to
disable it.

## 4. Scope

**In scope:** vuetify 3.5→4.1.1; vue floor bump; MD3 adoption (type, shape,
elevation, state); Carbon-seeded MD3 tonal theme (light+dark); rebasing CSS
overrides to tokens; component-default review for density; spreadsheet-natural
grid theming (Community); the flag-isolated Excel-behavior layer (3e) with its
documentation; full functional + visual + a11y + AG Grid validation.

**Explicitly out of scope (deferred / separate decision):**
- AG Grid **Enterprise** licensing itself, and the behaviors that can't be
  cleanly shimmed (fill handle, pivot, master/detail, rich context menu,
  status bar) — flagged for the Enterprise decision. Our Community shims are
  built to **yield to** these if Enterprise is later adopted.
- AG Grid Theming-API migration if CSS-variable tinting suffices.
- Backend changes (none); unrelated audit items (lockfile, csv_upload, i18n).

## 5. Phases

**Phase 0 — Baseline / safety net.** On current Vuetify 3: confirm
build/vitest/vue-tsc/eslint green, `npm audit` 0. Capture **baseline
screenshots** (browser agent) of the key-screen inventory in light+dark at
desktop+mobile (reference for "intended change vs regression" diffing). Record
the AG-Grid e2e specs green (capacity-planning, capacity-bom,
capacity-kpi-tracking, floating-pool).

**Phase 1 — Upgrade + MD3 theme rebuild.** Bump versions; adopt MD3 defaults +
`@layer`; rebuild the theme as a Carbon-seeded MD3 tonal system (light+dark);
resolve build/type errors. App builds and boots in MD3.

**Phase 2 — Rebase CSS overrides to tokens.** Convert the ~150+ `.v-*` rules
off hardcoded Carbon hexes onto theme tokens; reconcile `@layer` specificity;
tune component density so dashboards stay information-dense under MD3.

**Phase 3 — Spreadsheet-natural grids.** Apply the grid theming (3d);
harmonize colors/typography with theme tokens; verify density, gridlines,
headers, selection/edit/keyboard nav; confirm the 10 cell-renderer composables.

**Phase 4 — Excel-behavior layer (3e).** Build the `agGridExcelBehaviors`
module with per-feature flags; wire native-Community behaviors + the exceljs
`.xlsx` export + the flag-gated range-copy shim into the 9 grids via the shared
grid composables; write the documentation deliverable (below).

**Phase 5 — Verify (gates below); land.** Sequenced PRs to keep diffs
reviewable: **PR1** Vuetify 4 + MD3 tonal theme + CSS-token rebase + chrome;
**PR2** spreadsheet-natural grid theming; **PR3** Excel-behavior layer + docs.
Each PR independently green through all applicable gates before merge.

## 6. Acceptance criteria

**A. Build & static gates** — `npm run build`, vitest (1,982), vue-tsc, eslint,
`npm audit` 0. Backend unaffected.

**B. Test selectors & CI** — the ~157 `.v-*` selectors still match (fix/restore
any renamed class); SQLite e2e green; all 4 required CI checks green.

**C. AG Grid hard gate (functional)** — all 9 grids render; sort / filter /
single-cell edit / pagination / keyboard nav work; the 10 Vuetify cell-renderer
composables display correctly. Verified by grid e2e specs + gate D.

**C2. Spreadsheet-natural grid gate** — grids read as Excel-familiar: compact
density, visible gridlines, clear headers, recognizable selection/edit; colors
harmonized with the MD3 theme (not clashing, not foreign). Confirmed on a
manual pass + gate D.

**D. Browser-agent visual & usability validation (required).** A browser agent
drives the running app across the key-screen inventory and confirms — vs the
Phase-0 baseline — that the **MD3 changes are intended and correct AND nothing
is broken, hidden, unreadable, overlapped, clipped/trimmed, or misaligned**,
explicitly checking: **cards**, **layouts** (no overlap/overflow/cut-off; nav
drawer + app bar; responsive desktop+mobile), **titles/headings**, **labels**
(no overlap; floating labels correct), **legends & charts** (Chart.js renders;
axes/legends/data-labels present + readable), **popups/overlays** (`v-dialog`,
`v-menu`, select/autocomplete dropdowns, `v-snackbar`, `v-tooltip` open,
on-screen, dismissible), and **AG Grid** (headers/rows/cells/renderers/sizing,
spreadsheet feel). Run in **light and dark**. Produces screen-by-screen
pass/fail + screenshots; any usability regression blocks merge.

**E. Accessibility / contrast (hard gate).** Derived MD3 `on-*` role colors
meet **WCAG AA** contrast against their surfaces in light and dark (the tonal
system's main risk). Spot-checked across key screens by gate D + a contrast
check.

**F. Theme integrity** — light/dark toggle works; MD3 tonal palette applied
consistently; no unstyled flash; Carbon identity recognizable in the seeds.

**G. Excel-behavior layer (functional + isolation + docs).**
- Each shipped behavior works on a representative grid (freeze panes, undo/redo
  edit, CSV + `.xlsx` export, quick-find, Excel keyboard nav, copy, flag-gated
  range-copy).
- **Isolation proof:** all custom behavior is confined to the
  `agGridExcelBehaviors` module; flipping its master flag off removes every
  shim with the grids still functional (verified by a test) — demonstrating a
  clean Enterprise hand-off with no leftover conflicting handlers.
- **Documentation present (hard requirement):** `docs/frontend/ag-grid-excel-behaviors.md`
  lists every custom behavior, the Excel feature it emulates, its
  Community mechanism, the **Enterprise-native equivalent it must defer to**,
  and the exact flag to disable it; every shim has an inline comment pointing to
  that doc + its Enterprise equivalent. A test asserts the doc exists and covers
  each registered behavior key.

**Key-screen inventory (gates D/0):** Login; KPI Dashboard; MyShift; each KPI
sub-view (Efficiency, OEE, Quality, Attendance, Downtime, …); Plan vs Actual;
Capacity Planning workbook (all tabs — grids, dialogs, expansion panels); Work
Orders; Simulation V2 view (tables/tabs/dialogs/charts); Reports; Alerts; Admin
(Users, Defect Types); CSV upload dialogs (AG Grid inside `v-dialog`).

## 7. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Tonal palette drifts Carbon identity too far | Carbon hues as seeds; gate F; review key screens early in Phase 1 |
| Hardcoded-hex CSS overrides clash with tonal roles | Phase 2 rebases them onto tokens (core labor) |
| MD3 airiness reduces dashboard density | Deliberate density tuning (Phase 2); gate D checks cut-off/overlap |
| `on-*` contrast fails WCAG | Gate E contrast gate, light+dark |
| Grids feel un-spreadsheet-like / clash | Phase 3 + gates C2/D; Community-scoped |
| AG Grid functional regression | Gate C + grid e2e specs; Vue peer already satisfied |
| Charts (Chart.js) affected by type/reset | Gate D checks charts + legends explicitly |
| Diff too large to review | Sequenced PRs (chrome / grids / excel-behaviors) |
| Community Excel shim collides with future Enterprise | Per-feature flags that defer to Enterprise; single isolated module; gate G isolation proof + docs |
| Custom range-copy shim brittle | Keep behind its own flag; if it can't be done cleanly, ship the native-Community set and defer range-copy |

## 8. Rollback

Revertible branch/PR(s). Any failed gate that can't be resolved → revert; `main`
returns to Vuetify 3.5 with no residue; Render auto-redeploys from `main`.

## 9. Definition of done

Gates A–F green; merged to `main`; post-merge `main` CI + E2E green; Render
redeploy verified (health + login + an AG-Grid screen + browser-agent
spot-check on the deployed demo, light+dark); memory + CHANGELOG updated;
AG Grid Enterprise behaviors recorded as a separate future decision.

## 10. Open questions

- **AG Grid Enterprise** remains a future licensing decision. This spec ships
  the feasible Excel behaviors within Community, isolated so they yield cleanly
  to Enterprise later (no rework, just flip flags). Fill-handle/pivot/etc. wait
  for that decision.
- Native Vuetify-4 tonal generation vs `material-color-utilities` — resolved in
  the implementation plan (outcome identical; mechanism TBD).
- Final cut of range-copy: implement now if a clean isolated shim is
  achievable, else ship native-Community set and defer (decided during Phase 4).
