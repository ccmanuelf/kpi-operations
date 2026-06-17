# C1b — Script-side i18n sweep + referenced-key gate — Design

**Status:** Approved (brainstorm 2026-06-16). Successor to C1 (`feat/i18n-residual-strings`, PR #92, merged @ `294f597`) in the PR4 robustness slate.

## Goal

Localize the residual **user-facing strings in `.ts`/script contexts** (en + es, parity preserved) that the template-only `@intlify/vue-i18n/no-raw-text` gate cannot see, with **reactive resolution** so the live `LanguageToggle` updates every string. Add a deterministic CI test that asserts every referenced i18n key resolves in both locales — the script-side equivalent of the `no-raw-text` gate.

## Background

C1 localized template text and added `no-raw-text` (error) + an en/es key-parity vitest. A verification pass during C1 found ~166 candidate user-facing strings in `.ts` files (render-functions, option/label arrays, store getters, registries, chart labels, notify/validation/error messages) plus 17 pre-existing **missing** keys (referenced but absent — already fixed in C1). The `.ts` surface is intentionally a separate cycle because it needs reactive-resolution design and would have ballooned C1.

The app supports **live language switching** (`LanguageToggle` → `setLanguage()` mutates `i18n.global.locale.value`), so any string baked at module import or resolved non-reactively will NOT update on toggle — that is the central correctness risk this design addresses.

## Scope

### In scope (localize en + es)
Genuinely user-facing strings in `.ts` and `<script>`:
- Render-function template text (e.g. `WidgetGrid` `template: '<div>…AI Predictions…</div>'`).
- Option/select-list labels in `{ title|label|name, value }` arrays.
- Pinia store getter display titles (e.g. `stores/kpi.ts` — reuse existing `kpi.*` keys).
- Registry display `name`/`description` (widget registry, alert registry).
- Chart axis/series/dataset labels.
- Call-site messages: `showError`/`showSuccess`/`showSnackbar`/`notify(...)`, validation-rule messages, user-facing error text.

Estimated ~100–130 strings across ~25 files; exact set enumerated during planning. **Reuse** an existing key whenever the string already maps to one.

### Out of scope (identifiers — never localize)
Router route `name:` fields; `value:`/enum codes; `mdi-*` icon ids; object/property keys; API field names; developer-facing `console.*` / `throw new Error(...)` / log strings. (Router `name:` fields alone account for ~34 of the 166 raw candidates and are excluded.)

### Non-goals
- No new i18n infrastructure (57 `.ts` files already import i18n).
- No broad refactoring beyond what reactive localization requires.
- C4/C5 (lockfile, Alembic) remain deferred to MariaDB go-live.

## Architecture

### Reactive resolution — three patterns by execution context
1. **Composables called from component setup** → `const { t } = useI18n()`; any option/label list is returned as `computed(() => [...])` so it re-resolves when the locale ref changes.
2. **Pinia getters** (e.g. `stores/kpi.ts allKPIs`) → already computed/reactive; resolve strings via `i18n.global.t('…')` inside the getter (reads the reactive locale ref, so the getter recomputes on toggle).
3. **Module-level `const` arrays** (e.g. `useFilterBarData` date presets) → converted from a frozen import into a **factory function / `computed`** the consumer calls; consumers of those constants are updated to call it. This is the only structural change to call sites.

### Targeted factories (surgical Approach-2)
Shared concept-lists used in ≥2 files become one shared `useXOptions()` factory (returns a `computed` localized list), eliminating label drift:
- **Work-order / order status** (`usePlanVsActual`, `useWorkOrderData`, `WorkOrderDetailDrawer`).
- **Export-sheet list** (`useCapacityExport` + capacity views).
One-off lists stay inline in their consuming composable (no premature abstraction).

> i18n keys already provide the single source of truth for the **text**; factories only de-duplicate the list **structure** where it genuinely repeats.

### Script-side gate (regression prevention)
New vitest `src/i18n/__tests__/referenced-keys.spec.ts`: scans all `src/**/*.{ts,vue}` for **literal** `t('…')` / `$t('…')` / `keypath="…"` references, asserts each key resolves in **both** `en` and `es`. Dynamic/non-literal keys (template expressions, computed key names) are skipped (documented). Pairs with the existing parity test (parity = en/es symmetric key sets; this = referenced keys exist). Lives in `frontend-lint-and-tests`.

### De-risking spike (first task)
Before any bulk work: a throwaway/keeper test that mounts a component reading a Pinia getter which resolves via `i18n.global.t`, toggles locale, and asserts the rendered text switches en→es. Confirms pattern 2's reactivity assumption holds in vue-i18n 11 before relying on it across stores.

## Sequencing (comprehensive, disciplined batches)

1. **Spike + gate test + stores/registries** — reactivity spike; add `referenced-keys.spec.ts`; localize `stores/kpi.ts` (key reuse), `dashboardStore` widget names, widget/alert registries.
2. **Composable option/label arrays + targeted factories** — filter-bar date presets, plan-vs-actual/work-order status (factory), export sheets (factory), OTD modes, client-config option lists.
3. **Call-site messages + chart labels** — notify/validation/error text, chart configs, render-function templates (`WidgetGrid` etc.).

Each batch: localize en+es (parity preserved) → run gate test + parity + build + vitest + vue-tsc + lint → es-toggle render spot-check on the affected surfaces. Existing `.ts`/component tests asserting old hardcoded text are updated to mount real i18n (same pattern used for `ResultsView`/`ValidationPanel` in C1).

## Verification & success criteria

- Every in-scope `.ts` user-facing string resolves via `t()`/`i18n.global.t`, en + es, parity preserved.
- Live `LanguageToggle` updates all converted strings (no reload needed) — verified by es-toggle spot-checks on representative surfaces per batch (dashboard/KPI, capacity, work-orders).
- `referenced-keys.spec.ts` green: every literal i18n key in `src` resolves in both locales.
- All gates green: build, vitest (full), vue-tsc, lint, npm audit; post-merge main CI + Render verified (local == GitHub == Render).
- Spanish flagged for native-speaker review (gate enforces presence + parity, not fluency).

## Delivery

One PR with sequenced, individually-verified commits (per batch) unless the diff grows large enough to warrant 2–3 stacked PRs — decided in the plan from the enumerated size. Own brainstorm→spec→plan→execute→PR→merge-on-green cycle, per the project workflow.
