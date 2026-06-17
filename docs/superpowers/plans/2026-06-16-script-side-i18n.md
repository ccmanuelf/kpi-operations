# Script-side i18n sweep + referenced-key gate (C1b) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Localize the residual user-facing strings in `.ts`/script contexts (en + es, parity preserved) with reactive resolution, and add a vitest gate asserting every referenced i18n key resolves in both locales.

**Architecture:** Resolve strings with the pattern that fits the execution context (`useI18n().t` in setup composables; `i18n.global.t` in Pinia getters; module-level `const` arrays → factory functions/`computed`). Surgical shared factories only for lists used in ≥2 files (order status, export sheets). A new `referenced-keys.spec.ts` is the script-side regression gate (the `no-raw-text` ESLint rule is template-only).

**Tech Stack:** Vue 3.5, vue-i18n 11.4 (`legacy:false`, `createI18n` in `src/i18n/index.ts`, `i18n.global.t` available outside setup), Pinia, Vitest, ESLint flat config.

**Spec:** `docs/superpowers/specs/2026-06-16-script-side-i18n-design.md`.

**Branch:** `feat/script-side-i18n` (spec already committed here @ `8d280d6`).

## Global Constraints

- **en/es parity preserved** — every new key added to BOTH `src/i18n/locales/en.json` and `es.json`; the existing `locale-parity.spec.ts` must stay green.
- **Reactive correctness** — every converted string must update on the live `LanguageToggle` (no reload). Never bake a localized string into a module-level `const` evaluated at import; resolve inside `computed`/getter/function.
- **Reuse existing keys** — if a string already maps to a key (grep `src/i18n/locales/en.json`), reference it; do not duplicate.
- **Identifiers are never localized** — router route `name:`, `value:`/enum codes, `mdi-*`, object/property keys, API field names, `console.*`/`throw new Error(...)`.
- **Spanish** — real, fluent; flagged for native review. The gate enforces presence + parity, not fluency.
- **Verify on the repo's workflow** — from `frontend/`: `npm run build`, `npx vitest run`, `npx vue-tsc --noEmit`, `npm run lint`, `npm audit`. Use `rtk proxy npx …` when a command's JSON/exit output is needed verbatim (rtk compresses otherwise).
- **Locale-file edits** — append keys to the existing namespaces; keep 2-space indent + trailing newline (`JSON.stringify(obj,null,2)+"\n"`). The `detect-secrets` pre-commit hook rewrites `.secrets.baseline` line numbers on locale edits — `git add .secrets.baseline` and re-commit until it passes (converges in 1–2 retries).

---

## Task 1: Reactivity spike — prove `i18n.global.t` in a getter recomputes on toggle

De-risks the whole store/getter approach (pattern 2) before bulk work. Keep the test as a permanent reactivity regression guard.

**Files:**
- Create: `frontend/src/i18n/__tests__/reactive-resolution.spec.ts`

- [ ] **Step 1: Write the test.**
```ts
import { describe, it, expect } from 'vitest'
import { setActivePinia, createPinia, defineStore } from 'pinia'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { defineComponent, h } from 'vue'

const i18n = createI18n({
  legacy: false, globalInjection: true, locale: 'en', fallbackLocale: 'en',
  messages: { en: { kpi: { efficiency: 'Efficiency' } }, es: { kpi: { efficiency: 'Eficiencia' } } },
})

describe('reactive i18n.global.t inside a Pinia getter', () => {
  it('getter re-resolves when the locale changes', async () => {
    setActivePinia(createPinia())
    const useStore = defineStore('probe', {
      getters: { label: () => i18n.global.t('kpi.efficiency') },
    })
    const Probe = defineComponent({ setup() { const s = useStore(); return () => h('span', s.label) } })
    const w = mount(Probe, { global: { plugins: [i18n] } })
    expect(w.text()).toBe('Efficiency')
    i18n.global.locale.value = 'es'
    await w.vm.$nextTick()
    expect(w.text()).toBe('Eficiencia')
  })
})
```

- [ ] **Step 2: Run it.**
Run from `frontend/`: `rtk proxy npx vitest run src/i18n/__tests__/reactive-resolution.spec.ts`
Expected: PASS. **If it FAILS** (getter doesn't recompute), STOP — pattern 2 is invalid; switch stores/getters to read `useI18n().t` from a component-level wrapper or a `computed` that explicitly references `i18n.global.locale.value`, and update this plan before continuing.

- [ ] **Step 3: Commit.**
```bash
git add frontend/src/i18n/__tests__/reactive-resolution.spec.ts
git commit -m "test(i18n): prove i18n.global.t in a Pinia getter is reactive (C1b spike)"
```

---

## Task 2: Referenced-key gate test

The script-side regression gate. Currently passes (C1 fixed all 17 prior misses) — so it is a guard, committed before the sweep adds keys.

**Files:**
- Create: `frontend/src/i18n/__tests__/referenced-keys.spec.ts`

- [ ] **Step 1: Write the test.**
```ts
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import en from '../locales/en.json'
import es from '../locales/es.json'

// ESM-safe dir resolution (Vitest does not reliably define __dirname)
const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '../../')
function walk(dir: string): string[] {
  const out: string[] = []
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) {
      if (/node_modules|__tests__|[/\\]test([/\\]|$)/.test(p)) continue
      out.push(...walk(p))
    } else if (/\.(ts|vue)$/.test(p) && !/\.(spec|test)\.ts$/.test(p) && !/\.d\.ts$/.test(p)) {
      out.push(p)
    }
  }
  return out
}
function get(obj: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((a, k) => (a && typeof a === 'object' ? (a as Record<string, unknown>)[k] : undefined), obj)
}
// literal keys only: t('a.b') / $t("a.b") / keypath="a.b"; skip `${...}` template-literal (dynamic) keys
const KEY_RE = /(?:\$t|[^\w.]t)\(\s*['"]([A-Za-z0-9_.]+)['"]|keypath=["']([A-Za-z0-9_.]+)["']/g

describe('referenced i18n keys resolve in both locales', () => {
  it('every literal t()/$t()/keypath key exists in en and es', () => {
    const missing: string[] = []
    const seen = new Set<string>()
    for (const file of walk(SRC)) {
      const src = readFileSync(file, 'utf8')
      let m: RegExpExecArray | null
      while ((m = KEY_RE.exec(src))) {
        const key = m[1] || m[2]
        if (!key || seen.has(key)) continue
        seen.add(key)
        if (get(en as Record<string, unknown>, key) === undefined || get(es as Record<string, unknown>, key) === undefined) {
          missing.push(key)
        }
      }
    }
    expect(missing).toEqual([])
  })
})
```

- [ ] **Step 2: Run it — must PASS now (baseline).**
Run from `frontend/`: `rtk proxy npx vitest run src/i18n/__tests__/referenced-keys.spec.ts`
Expected: PASS (C1 already made every referenced key resolve). If it fails, the listed keys are real pre-existing misses — add them to both locales (same as C1's fold-in) before committing.

- [ ] **Step 3: Commit.**
```bash
git add frontend/src/i18n/__tests__/referenced-keys.spec.ts
git commit -m "test(i18n): gate every referenced i18n key resolves in en+es (C1b)"
```

---

## Task 3: Batch 1 — stores + registries

**Files (localize en+es; reuse keys where they exist):**
- `frontend/src/stores/kpi.ts` (11) — getter titles → reuse existing `kpi.*` keys.
- `frontend/src/stores/dashboardStore.ts` (~16 `widget_name`) — see widget_name note below.
- `frontend/src/components/widgets/index.ts` (8) — widget registry `name`/`description`.
- `frontend/src/components/alerts/index.ts` (2) — alert registry labels.
- `frontend/src/stores/authStore.ts` (≤3) — only genuinely user-facing strings (skip internal/log).
- Modify: `frontend/src/i18n/locales/en.json` + `es.json`.

> **widget_name decision (resolve first):** check whether `dashboardStore` `widget_name` is persisted/round-tripped to the backend or is display-only default data. Grep consumers + the persistence path. If it is **display-only**, localize via a getter that maps `widget_key → t('dashboard.widgets.<key>')`. If it is **persisted data** (the stored English is what renders), do NOT localize the stored value — instead localize at the render site by mapping `widget_key` to an i18n key there, and leave the store data as the stable key/id. Document the choice in the commit.

- [ ] **Step 1: Worked example — getter reuse (`stores/kpi.ts`).**
```ts
// before
allKPIs: (state): KPISummary[] => [
  { key: 'efficiency', title: 'Efficiency', /* … */ },
// after  (i18n.global.t is reactive inside the getter — proven in Task 1)
import i18n from '@/i18n'
// …
allKPIs: (state): KPISummary[] => [
  { key: 'efficiency', title: i18n.global.t('kpi.efficiency'), /* … */ },
```
Grep `src/i18n/locales/en.json` for each title (`"Efficiency"`, `"OEE"`, `"Quality (FPY)"`, …) and reuse the existing `kpi.*` key; only add a key if none exists.

- [ ] **Step 2: Worked example — registry display name (`components/widgets/index.ts`).**
```ts
// before
{ id: 'downtime_impact', name: 'Downtime Impact on OEE', component: () => import('…') }
// after — registry is module-level; expose a localized getter rather than baking the string
import i18n from '@/i18n'
{ id: 'downtime_impact', get name() { return i18n.global.t('widgets.registry.downtimeImpact') }, component: () => import('…') }
```
Add `widgets.registry.<id>` keys to en+es. (A getter keeps reactivity without changing the consuming shape.) If consumers spread/destructure `name` eagerly, convert the consumer to read it at render instead.

- [ ] **Step 3: Localize each file** per the patterns above; add every new key to en.json + es.json (parity).

- [ ] **Step 4: Converge + verify.** From `frontend/`:
```
rtk proxy npx vitest run src/i18n/__tests__/referenced-keys.spec.ts src/i18n/__tests__/locale-parity.spec.ts
rtk proxy npx vue-tsc --noEmit
```
Expected: both specs PASS; tsc 0. Fix existing store/registry tests that assert old English by mounting real i18n (pattern from C1's `ResultsView`/`ValidationPanel` fix).

- [ ] **Step 5: es-toggle spot-check.** `rtk proxy npx vitest run` the dashboard-customizer / KPI-summary component tests; add or extend one test that toggles locale to `es` and asserts a converted title renders in Spanish.

- [ ] **Step 6: Commit** (`git add` the touched files + locales + `.secrets.baseline` as needed):
```bash
git commit -m "i18n(c1b): localize store + registry display strings (en+es, reactive)"
```

---

## Task 4: Batch 2 — composable option/label arrays + targeted factories

**Files:**
- Create: `frontend/src/composables/useOrderStatusOptions.ts` (shared factory).
- Create: `frontend/src/composables/useExportSheetOptions.ts` (shared factory).
- Modify: `frontend/src/composables/useFilterBarData.ts` (6 — date presets), `usePlanVsActual.ts` (status), `useWorkOrderData.ts` (status), `useCapacityExport.ts` (sheets), `useClientConfigForms.ts` (OTD modes), `useKPIFilters.ts` (5), plus the consumers `WorkOrderDetailDrawer.vue` (reads order status).
- Modify: `frontend/src/i18n/locales/en.json` + `es.json`.

- [ ] **Step 1: Create the shared order-status factory.**
```ts
// useOrderStatusOptions.ts
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
export function useOrderStatusOptions() {
  const { t } = useI18n()
  return computed(() => [
    { title: t('workOrders.status.pending'), value: 'PENDING' },
    { title: t('workOrders.status.inProgress'), value: 'IN_PROGRESS' },
    { title: t('workOrders.status.completed'), value: 'COMPLETED' },
    { title: t('workOrders.status.onHold'), value: 'ON_HOLD' },
    { title: t('workOrders.status.cancelled'), value: 'CANCELLED' },
  ])
}
```
Add `workOrders.status.*` keys (reuse if `workOrders.*` already has them — grep first). Replace the three inline copies (`usePlanVsActual`, `useWorkOrderData`, `WorkOrderDetailDrawer`) with this factory.

- [ ] **Step 2: Worked example — module-const → reactive (`useFilterBarData.ts`).**
```ts
// before (module-level const — frozen at import)
export const DATE_PRESETS = [ { value: '7d', label: 'Last 7 Days', icon: 'mdi-calendar-week', days: 7 }, /* … */ ]
// after (factory returning a computed; consumers call it inside setup)
import { computed } from 'vue'; import { useI18n } from 'vue-i18n'
export function useDatePresets() {
  const { t } = useI18n()
  return computed(() => [ { value: '7d', label: t('filterBar.presets.last7Days'), icon: 'mdi-calendar-week', days: 7 }, /* … */ ])
}
```
Update every consumer of `DATE_PRESETS` to call `useDatePresets()` in setup. (`value`/`icon`/`days` stay; only `label` is localized.) Same shape for `useCapacityExport` → `useExportSheetOptions` and `useClientConfigForms` OTD modes.

- [ ] **Step 3: Localize remaining one-off lists inline** (`useKPIFilters`, etc.) using `useI18n().t` + `computed`.

- [ ] **Step 4: Converge + verify** (same commands as Task 3 Step 4) — referenced-keys + parity PASS, tsc 0; update affected composable/component tests to mount real i18n.

- [ ] **Step 5: es-toggle spot-check** on the filter bar + work-order status surfaces.

- [ ] **Step 6: Commit.**
```bash
git commit -m "i18n(c1b): localize option-list labels + shared status/export factories (en+es)"
```

---

## Task 5: Batch 3 — call-site messages, chart labels, render-functions

**Files:**
- `frontend/src/composables/useKPIDashboardHelpers.ts` (27 — KPI tooltips: `title:'Formula:'`, `formula`, `meaning`).
- `frontend/src/components/dashboard/WidgetGrid.vue` (render-fn `template:` strings — reuse existing `kpi.aiPredictions`).
- `frontend/src/composables/useProductionGridData.ts` (10), `useShiftDashboardData.ts` (9), `useDefectTypesData.ts` (8), `useShiftForms.ts` (4), `utils/workflow/workflowValidator.ts` (4), `useAttendanceGridData.ts` (2), `useHoldGridForms.ts` (2), `useCSVExport.ts` (2), and the remaining ≤1-hit files (`useKPIDashboardActions`, `useKPIDashboardData`, `useMetricLineage`, `useQRScanner`, `useQualityGridData`, `useQualityData`, `useKPIChartData`).
- Modify: `frontend/src/i18n/locales/en.json` + `es.json`.

- [ ] **Step 1: Worked example — call-site message (`showError`).**
```ts
// before
notify.showError('Failed to load production data')
// after
import { useI18n } from 'vue-i18n'; const { t } = useI18n()  // (in setup) — or i18n.global.t outside setup
notify.showError(t('errors.loadProductionFailed'))
```
Where a `t('x') || 'fallback'` defensive pattern already exists from C1, the key now exists; the fallback may stay (harmless) or be dropped — do not add new `|| 'literal'` fallbacks.

- [ ] **Step 2: Worked example — render-function template (`WidgetGrid.vue`).**
```ts
// before
template: '<div class="text-center pa-4"><v-icon>mdi-crystal-ball</v-icon><p class="text-grey mt-2">AI Predictions</p></div>'
// after — render functions run inside a component; use the injected $t via a functional render or pass the resolved string in.
//   Prefer replacing the inline render-fn string with a real <template> slot, OR build it via h() with t():
import { useI18n } from 'vue-i18n'
// in setup: const { t } = useI18n()
render: () => h('div', { class: 'text-center pa-4' }, [ h('v-icon', 'mdi-crystal-ball'), h('p', { class: 'text-grey mt-2' }, t('kpi.aiPredictions')) ])
```
(`kpi.aiPredictions` already exists — reuse.) If the render-fn cannot reach `t`, lift the fallback into the parent `<template>` with `{{ $t('kpi.aiPredictions') }}`.

- [ ] **Step 3: Localize tooltips (`useKPIDashboardHelpers.ts`).** Each `kpiTooltips.<kpi>` entry has `title:'Formula:'` (one shared key `kpi.tooltips.formulaLabel`), `formula` (math string — localize the prose around symbols; keep the equation), and `meaning` (full sentence). Add `kpi.tooltips.<kpi>.{formula,meaning}` keys, en+es.

- [ ] **Step 4: Localize the remaining grid/shift/defect/validator messages** with `useI18n().t` (setup) or `i18n.global.t` (module/util like `workflowValidator.ts`).

- [ ] **Step 5: Converge + full verify.** From `frontend/`:
```
rtk proxy npx vitest run src/i18n/__tests__/referenced-keys.spec.ts src/i18n/__tests__/locale-parity.spec.ts
rtk proxy npm run build && rtk proxy npx vue-tsc --noEmit && rtk proxy npm run lint
```
Expected: gate + parity PASS; build OK; tsc 0; lint clean. Update any remaining `.ts`/component tests asserting old English to mount real i18n.

- [ ] **Step 6: Commit.**
```bash
git commit -m "i18n(c1b): localize call-site messages, tooltips, chart + render-fn text (en+es)"
```

---

## Task 6: Final verification + PR

**Files:** none (verification).

- [ ] **Step 1: Full gates.** From `frontend/`:
```
rtk proxy npm run build && rtk proxy npx vitest run && rtk proxy npx vue-tsc --noEmit && rtk proxy npm run lint && npm audit
```
Expected: build OK; full vitest PASS (incl. `referenced-keys`, `locale-parity`, `reactive-resolution`); tsc 0; lint clean; audit 0.

- [ ] **Step 2: Whole-codebase audit re-run.** Confirm 0 remaining in-scope `.ts` user-facing literals via the spec's grep heuristic, and that `referenced-keys.spec.ts` covers them. Log anything intentionally left (and why).

- [ ] **Step 3: es-toggle render review** across representative surfaces (dashboard customizer, KPI summary + tooltips, filter bar, work-order status, capacity export dialog): toggle to Spanish, confirm strings switch with no `[intlify] Not found` warnings.

- [ ] **Step 4: Push + PR.**
```bash
git push -u origin feat/script-side-i18n
gh pr create --base main --head feat/script-side-i18n \
  --title "feat(i18n): script-side localization + referenced-key gate (C1b)" \
  --body "C1b. Localizes user-facing .ts/script strings (render-fns, option lists, store getters, registries, chart/tooltip/notify text) en+es with reactive resolution; shared factories for order-status + export-sheet lists; adds referenced-keys.spec.ts gating that every literal i18n key resolves in both locales. Spanish flagged for native review. Spec/plan under docs/superpowers/."
```
Expected: 4 required checks green; report for merge approval (do not auto-merge). After merge: sync local main 0/0, confirm post-merge main CI, verify local == GitHub == Render.

---

## Self-review notes (author)

- **Spec coverage:** reactive patterns (Tasks 3–5 worked examples) · targeted factories (Task 4) · referenced-key gate (Task 2) · de-risking spike (Task 1) · 3 sequenced batches each verified (Tasks 3–5) · final verify + es-toggle + PR (Task 6). All spec sections map to a task.
- **No placeholders:** Tasks 1–2 carry complete test code; Tasks 3–5 give complete worked examples per pattern + enumerated file lists. The per-string bulk is bounded by enumeration + the referenced-keys gate (done-gate = both i18n specs green), per the enumerate-then-fix style accepted for C1.
- **Type/name consistency:** `i18n.global.t` (default export `@/i18n`), `useI18n().t`, factory names `useOrderStatusOptions`/`useExportSheetOptions`/`useDatePresets`, key namespaces match existing locale structure (`kpi.*`, `workOrders.status.*`, `widgets.registry.*`, `filterBar.presets.*`, `errors.*`).
- **Open decision flagged in-plan:** `dashboardStore.widget_name` persisted-vs-display (Task 3) — resolved first during execution, choice documented in the commit.
- **Risk:** Task 1 spike gates the entire getter approach; if it fails, stores switch to a component-level `computed` referencing `i18n.global.locale.value` and the plan is revised before bulk work.
