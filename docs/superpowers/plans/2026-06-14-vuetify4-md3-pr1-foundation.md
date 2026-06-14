# Vuetify 4 + MD3 Foundation (PR1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the frontend to Vuetify 4.1.1 and adopt Material Design 3 with a Carbon-seeded tonal color system, keeping the app fully functional and AG Grid unaffected — without yet retheming the grids (PR2) or adding Excel behaviors (PR3).

**Architecture:** Bump Vuetify (Vue 3.5 already installed), switch the theme plugin to an MD3 blueprint, generate MD3 tonal role tokens from the existing IBM Carbon hues, enable Vuetify's CSS `@layer`, then rebase the ~150 hardcoded-hex `.v-*` CSS overrides onto theme tokens. Verify via the existing build/test/lint/type/e2e gates plus a browser-agent visual+contrast pass against a pre-upgrade baseline.

**Tech Stack:** Vue 3.5, Vuetify 4.1.1, vite-plugin-vuetify 2.1.3, Vite 7, TypeScript, `@material/material-color-utilities` (new dev/runtime dep for tonal generation), Tailwind 4 (coexisting), AG Grid Community 35 (unchanged in PR1).

**Spec:** `docs/superpowers/specs/2026-06-14-vuetify-4-migration-design.md` (PR1 covers phases 0–2 + gates A,B,D,E,F; AG Grid gate C is "no regression" only here — theming is PR2).

**Branch:** `chore/vuetify-4-migration` (this branch; spec already committed here).

---

## File structure (PR1)

- `frontend/package.json` — bump `vuetify`→`4.1.1`, raise `vue`→`^3.5.0`, add `@material/material-color-utilities`.
- `frontend/src/theme/carbonSeeds.ts` *(new)* — the Carbon hex seeds (single source of the brand colors).
- `frontend/src/theme/md3Tonal.ts` *(new)* — pure functions that derive MD3 tonal role tokens (light+dark) from the seeds; unit-tested.
- `frontend/src/plugins/vuetify.ts` — switch to MD3 blueprint, consume `md3Tonal` for `theme.themes.light/dark`, keep component defaults (density tuned).
- `frontend/src/main.ts` — Vuetify styles import / `@layer` enablement; icon import unchanged.
- `frontend/src/assets/main.css`, `frontend/src/assets/responsive.css` — rebase hardcoded `.v-*` hex overrides onto theme CSS variables; place app overrides in a layer after Vuetify's.
- `frontend/src/theme/__tests__/md3Tonal.spec.ts` *(new)* — token-derivation + WCAG-contrast unit tests.

---

## Task 1: Pre-upgrade baseline (safety net)

**Files:** none (verification + artifacts only).

- [ ] **Step 1: Confirm current gates green (Vuetify 3).**
Run from `frontend/`:
```bash
npm run build && npx vitest run && npx vue-tsc --noEmit && npm run lint && npm audit
```
Expected: build OK; vitest 1982 passed; vue-tsc exit 0; eslint "No issues found"; audit 0.

- [ ] **Step 2: Capture the visual baseline (browser agent).**
Use the gstack `browse` skill (or `qa`) to screenshot the spec's key-screen inventory in **light and dark** at desktop (1440px) and mobile (390px). Save under `frontend/.visual-baseline/v3/<screen>-<theme>-<width>.png`. This is the reference for gate D diffing. Start the app with `npm run dev` (or the e2e webServer) and the demo backend.
Expected: a screenshot set covering Login, KPI Dashboard, MyShift, KPI sub-views, Plan vs Actual, Capacity Planning (all tabs), Work Orders, Simulation V2, Reports, Alerts, Admin, CSV dialogs.

- [ ] **Step 3: Record the AG Grid e2e baseline.**
```bash
npm run test:e2e:sqlite -- capacity-planning capacity-bom capacity-kpi-tracking floating-pool
```
Expected: these specs pass on Vuetify 3 (records the green baseline; `.visual-baseline/` is gitignored — add it).

- [ ] **Step 4: Gitignore the baseline dir + commit the marker.**
Add `frontend/.visual-baseline/` to `frontend/.gitignore`.
```bash
git add frontend/.gitignore && git commit -m "chore(frontend): ignore local visual-baseline screenshots (PR1 safety net)"
```

---

## Task 2: Tonal token derivation (pure, test-first)

**Files:**
- Create: `frontend/src/theme/carbonSeeds.ts`
- Create: `frontend/src/theme/md3Tonal.ts`
- Test: `frontend/src/theme/__tests__/md3Tonal.spec.ts`

- [ ] **Step 1: Add the color-utilities dependency.**
Run from `frontend/`:
```bash
npm install --save @material/material-color-utilities
```
Expected: installs; `npm audit` still 0 (verify).

- [ ] **Step 2: Write the Carbon seeds module.**
Create `frontend/src/theme/carbonSeeds.ts` with the existing brand hues (copy the exact values currently in `src/plugins/vuetify.ts`):
```ts
// IBM Carbon brand hues — the SEEDS for the MD3 tonal system (Run: Vuetify 4 + MD3).
// These are the single source of brand color. md3Tonal.ts derives MD3 role
// tokens (primary/on-primary/containers/surfaces, light+dark) from them.
export const carbonSeeds = {
  primary: '#0f62fe',
  secondary: '#393939',
  success: '#198038',
  error: '#da1e28',
  info: '#0072c3',
  warning: '#f1c21b',
} as const
export type CarbonSeedKey = keyof typeof carbonSeeds
```

- [ ] **Step 3: Write the failing tonal-derivation test.**
Create `frontend/src/theme/__tests__/md3Tonal.spec.ts`:
```ts
import { describe, it, expect } from 'vitest'
import { buildMd3Theme, contrastRatio } from '../md3Tonal'
import { carbonSeeds } from '../carbonSeeds'

describe('md3Tonal', () => {
  it('derives light + dark role tokens for every seed', () => {
    const light = buildMd3Theme('light')
    const dark = buildMd3Theme('dark')
    for (const t of [light, dark]) {
      expect(t.colors.primary).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(t.colors['on-primary']).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(t.colors.surface).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(t.colors.error).toMatch(/^#[0-9a-fA-F]{6}$/)
    }
    expect(light.dark).toBe(false)
    expect(dark.dark).toBe(true)
  })

  it('keeps the Carbon primary recognizable in the seed (hue within tolerance)', () => {
    // The derived primary need not equal the seed exactly (MD3 tonal), but must
    // stay in the Carbon blue family — assert it is bluish, not drifted to another hue.
    const { colors } = buildMd3Theme('light')
    const b = parseInt(colors.primary.slice(5, 7), 16)
    const r = parseInt(colors.primary.slice(1, 3), 16)
    expect(b).toBeGreaterThan(r) // blue dominant
  })

  it('on-* roles meet WCAG AA (>=4.5) against their backgrounds, light + dark', () => {
    for (const mode of ['light', 'dark'] as const) {
      const c = buildMd3Theme(mode).colors
      expect(contrastRatio(c['on-primary'], c.primary)).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(c['on-surface'], c.surface)).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(c['on-error'], c.error)).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('exposes the seeds it was built from', () => {
    expect(Object.keys(carbonSeeds)).toContain('primary')
  })
})
```

- [ ] **Step 2 (run): verify it fails.**
Run: `npx vitest run src/theme/__tests__/md3Tonal.spec.ts`
Expected: FAIL — `../md3Tonal` not found.

- [ ] **Step 3 (impl): write `md3Tonal.ts`.**
Create `frontend/src/theme/md3Tonal.ts`. Derive MD3 tonal palettes from each seed with `material-color-utilities` (HCT tones), map to Vuetify theme `colors`, and provide a WCAG contrast helper. Concrete implementation:
```ts
import {
  argbFromHex, hexFromArgb, Hct, TonalPalette,
} from '@material/material-color-utilities'
import { carbonSeeds } from './carbonSeeds'

type Tone = number
const tone = (seedHex: string, t: Tone): string => {
  const hct = Hct.fromInt(argbFromHex(seedHex))
  const tp = TonalPalette.fromHueAndChroma(hct.hue, hct.chroma)
  return hexFromArgb(tp.tone(t))
}

// MD3 standard tones: light vs dark roles use mirrored tones.
const ROLE_TONES = {
  light: { base: 40, on: 100, container: 90, onContainer: 10, surface: 98, onSurface: 10 },
  dark:  { base: 80, on: 20,  container: 30, onContainer: 90, surface: 6,  onSurface: 90 },
} as const

export interface VuetifyThemeColors { [k: string]: string }
export interface VuetifyTheme { dark: boolean; colors: VuetifyThemeColors }

export function buildMd3Theme(mode: 'light' | 'dark'): VuetifyTheme {
  const T = ROLE_TONES[mode]
  const colors: VuetifyThemeColors = {
    background: tone(carbonSeeds.secondary, T.surface),
    surface: tone(carbonSeeds.secondary, T.surface),
    'on-surface': tone(carbonSeeds.secondary, T.onSurface),
    'on-background': tone(carbonSeeds.secondary, T.onSurface),
  }
  for (const key of Object.keys(carbonSeeds) as (keyof typeof carbonSeeds)[]) {
    colors[key] = tone(carbonSeeds[key], T.base)
    colors[`on-${key}`] = tone(carbonSeeds[key], T.on)
    colors[`${key}-container`] = tone(carbonSeeds[key], T.container)
    colors[`on-${key}-container`] = tone(carbonSeeds[key], T.onContainer)
  }
  return { dark: mode === 'dark', colors }
}

// WCAG relative-luminance contrast ratio between two #rrggbb colors.
export function contrastRatio(fg: string, bg: string): number {
  const lum = (hex: string) => {
    const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
  }
  const a = lum(fg), b = lum(bg)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}
```

- [ ] **Step 4: Run the tonal tests to PASS.**
Run: `npx vitest run src/theme/__tests__/md3Tonal.spec.ts`
Expected: PASS (4 tests). If the contrast test fails for a role, adjust that role's tone in `ROLE_TONES` (e.g., push `on` to a higher/lower tone) until AA holds — this is the gate-E guarantee at the source.

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/theme frontend/package.json frontend/package-lock.json
git commit -m "feat(theme): Carbon-seeded MD3 tonal token derivation (WCAG-AA tested)"
```

---

## Task 3: Upgrade Vuetify + wire the MD3 theme

**Files:**
- Modify: `frontend/package.json` (vuetify, vue floor)
- Modify: `frontend/src/plugins/vuetify.ts`
- Modify: `frontend/src/main.ts` (if styles/@layer wiring needed)

- [ ] **Step 1: Bump versions.**
Edit `frontend/package.json`: `"vuetify": "^4.1.1"`, `"vue": "^3.5.0"` (keep `vite-plugin-vuetify` `^2.1.3`). Then:
```bash
npm install --legacy-peer-deps && npm audit
```
Expected: installs clean; vue stays 3.5.x; vuetify 4.1.x; audit 0. If audit > 0, stop and assess.

- [ ] **Step 2: Switch the plugin to MD3 + tonal theme.**
In `frontend/src/plugins/vuetify.ts`: import the `md3` blueprint and `buildMd3Theme`; set `blueprint: md3`, and `theme.themes.light = buildMd3Theme('light')`, `theme.themes.dark = buildMd3Theme('dark')`. Remove the old hardcoded `colors` maps (now derived). Keep the existing `defaults` block but add density where dashboards need it (e.g., `VTextField`/`VSelect`/`VList` `density: 'compact'`, `VDataTable` `density: 'compact'`). Concrete shape:
```ts
import { createVuetify } from 'vuetify'
import { md3 } from 'vuetify/blueprints/md3'
import { buildMd3Theme } from '@/theme/md3Tonal'
// ...mdi icon set import unchanged...

export default createVuetify({
  blueprint: md3,
  theme: {
    defaultTheme: 'light',
    themes: { light: buildMd3Theme('light'), dark: buildMd3Theme('dark') },
  },
  defaults: {
    // keep existing per-component defaults; tune density for dashboard compactness
    VTextField: { variant: 'outlined', density: 'compact' },
    VSelect: { variant: 'outlined', density: 'compact' },
    VDataTable: { density: 'compact' },
    // ...preserve the rest of the existing defaults...
  },
})
```

- [ ] **Step 3: Enable CSS `@layer` for Vuetify styles.**
Per the v4 upgrade guide, ensure Vuetify styles are emitted into a CSS layer and app/Tailwind layers are ordered after it. In `vite.config.ts` the `vuetify({ autoImport: true })` plugin handles style injection; add the `@layer` ordering declaration at the top of `src/assets/main.css` (Task 5 finalizes ordering):
```css
@layer vuetify, app, utilities;
```

- [ ] **Step 4: Build + type-check; fix bump breakages.**
Run: `npm run build && npx vue-tsc --noEmit`
Expected: success. If the bump surfaces removed/renamed symbols (e.g., a date-adapter path — not used here), fix per the v4 upgrade guide. Record each fix.

- [ ] **Step 5: Commit.**
```bash
git add frontend/package.json frontend/package-lock.json frontend/src/plugins/vuetify.ts frontend/src/main.ts frontend/vite.config.ts frontend/src/assets/main.css
git commit -m "feat(ui): upgrade to Vuetify 4 + MD3 blueprint with Carbon-seeded tonal theme"
```

---

## Task 4: Smoke the app boots in MD3

**Files:** none (verification).

- [ ] **Step 1: Run unit tests.**
Run: `npx vitest run`
Expected: the 1,982 pass, OR a small set fails only on theme-token/class assumptions — triage: fix the test if it asserted an old hardcoded color; do NOT loosen behavioral assertions.

- [ ] **Step 2: Boot dev + manual sanity.**
`npm run dev`; load the KPI Dashboard in light and dark. Expected: app renders in MD3, no console errors, theme toggle works. (Deep visual review is Task 6.)

- [ ] **Step 3: Commit any test fixups.**
```bash
git add -A && git commit -m "test(ui): align unit tests with MD3 theme tokens"
```

---

## Task 5: Rebase CSS overrides onto theme tokens

**Files:**
- Modify: `frontend/src/assets/main.css`
- Modify: `frontend/src/assets/responsive.css`

- [ ] **Step 1: Inventory the hardcoded-hex `.v-*` rules.**
Run from `frontend/`:
```bash
grep -nE '#[0-9a-fA-F]{3,6}' src/assets/main.css src/assets/responsive.css | grep -iE '\.v-' | wc -l
grep -nE '#[0-9a-fA-F]{3,6}' src/assets/main.css src/assets/responsive.css | grep -iE '\.v-' > /tmp/hex-overrides.txt
```
Expected: the working list of rules to convert (the ~150 surface).

- [ ] **Step 2: Convert each to a theme token (worked example).**
Replace literal Carbon hexes with Vuetify's theme CSS variables so they track the tonal palette and respect dark mode. Pattern:
```css
/* BEFORE */
.v-navigation-drawer { background-color: #ffffff; color: #161616; border-right: 1px solid #e0e0e0; }
/* AFTER (tracks MD3 tonal surface roles + theme variables) */
.v-navigation-drawer {
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
```
Apply across `/tmp/hex-overrides.txt`. For brand accents use the matching role var (`--v-theme-primary`, `--v-theme-on-primary`, `--v-theme-error`, etc.). Where an override only fixed an MD2 quirk that MD3 now handles, delete it rather than port it.

- [ ] **Step 3: Confirm layer ordering.**
Ensure app overrides sit in the `app` layer (declared after `vuetify` in Task 3) so they win without `!important`. Wrap the app override blocks:
```css
@layer app {
  /* ported .v-* overrides */
}
```
Remove now-unneeded `!important` flags introduced for the old specificity wars.

- [ ] **Step 4: Verify no stray hardcoded brand hexes remain in `.v-*` rules.**
Run:
```bash
grep -nE '#0f62fe|#161616|#e0e0e0|#393939' src/assets/main.css src/assets/responsive.css | grep -iE '\.v-' || echo "clean"
```
Expected: `clean` (or only intentional, documented exceptions).

- [ ] **Step 5: Build + commit.**
Run: `npm run build` (expect success), then:
```bash
git add frontend/src/assets/main.css frontend/src/assets/responsive.css
git commit -m "refactor(ui): rebase .v-* overrides onto MD3 theme tokens + @layer ordering"
```

---

## Task 6: Verify — full gates + browser-agent visual/contrast pass

**Files:** none (verification; fixes loop back to Task 5).

- [ ] **Step 1: Static + unit + audit gates.**
Run from `frontend/`:
```bash
npm run build && npx vitest run && npx vue-tsc --noEmit && npm run lint && npm audit
```
Expected: build OK; vitest pass; vue-tsc 0; eslint clean; audit 0.

- [ ] **Step 2: Test selectors / e2e (chromium, AG-Grid no-regression).**
Run: `npm run test:e2e:sqlite`
Expected: green. AG Grid still renders/sorts/filters/edits (PR1 doesn't retheme grids; this proves no regression). Fix any `.v-*` selector that legitimately changed; do not weaken assertions.

- [ ] **Step 3: Browser-agent visual + usability pass (gate D).**
Re-run the gstack `browse`/`qa` agent over the same key-screen inventory, light+dark, desktop+mobile. For each screen confirm vs `.visual-baseline/v3/`: MD3 changes are intended; and **nothing is broken/hidden/unreadable/overlapped/clipped/misaligned** — explicitly checking cards, layouts, titles, labels, legends & charts, popups/overlays (dialog/menu/select-dropdown/snackbar/tooltip), and AG Grid render/sizing. Produce a screen-by-screen pass/fail with screenshots saved to `frontend/.visual-baseline/v4/`. Any usability regression → fix in Task 5 and re-run.
Expected: every screen "intended-change, no regression."

- [ ] **Step 4: Contrast gate (E).**
Confirm the `md3Tonal` contrast unit tests pass (Task 2) AND spot-check rendered text on 3 busy screens (Dashboard, Capacity Planning, Simulation V2) in light+dark for AA readability (the browser agent flags low-contrast text).
Expected: no AA failures.

- [ ] **Step 5: Theme integrity (F).**
Toggle light/dark across 5 screens; confirm consistent tonal application, no unstyled flash, Carbon identity recognizable.
Expected: pass.

- [ ] **Step 6: Final PR1 commit + open PR.**
```bash
git push -u origin chore/vuetify-4-migration
gh pr create --title "feat(ui): Vuetify 4 + MD3 foundation (Carbon-seeded tonal theme)" --body "PR1 of the Vuetify 4 migration (see docs/superpowers/specs/2026-06-14-...). Upgrade + MD3 blueprint + tonal theme + CSS-token rebase. AG Grid unchanged (PR2). Gates: build/vitest/vue-tsc/eslint/npm-audit/e2e green; browser-agent visual+contrast pass attached."
```
Expected: PR opened; monitor the 4 required checks; merge on green; verify Render; then author the PR2 (grid theming) plan.

---

## Self-review notes (author)

- **Spec coverage (PR1 scope):** phase 0 (Task 1), tonal theme 3b (Task 2/3), upgrade 3a (Task 3), CSS-token rebase 3c (Task 5), density (Task 3 defaults); gates A (Task 6.1), B (6.2), D (6.3), E (Task 2 + 6.4), F (6.5). Grid theming (3d), Excel layer (3e), and gates C2/G are **PR2/PR3** — out of this plan by design.
- **No placeholders:** token derivation, contrast helper, theme wiring, and a worked CSS-rebase example are concrete; the 150-rule sweep is methodology + example + the exact grep that bounds it + the gate that proves done (full enumeration isn't knowable until Step 1 runs).
- **Type consistency:** `buildMd3Theme(mode)`/`contrastRatio(fg,bg)`/`carbonSeeds` names are used identically across Task 2 and Task 3.
- **Risk:** if `material-color-utilities` tonal output drifts Carbon identity, Task 2 Step 4 tunes `ROLE_TONES`; if Vuetify 4 exposes sufficient native tonal handling, `md3Tonal.ts` can wrap that instead — outcome identical.

---

## PR1 Execution Findings (2026-06-14) — live-harness visual validation

**Tasks 1–3 DONE & reviewed** (commits 1c4713b, 8645c82, c0274fc): Vuetify 4.1.1 + MD3 blueprint + Carbon-seeded tonal theme; build/vitest(1986)/vue-tsc/eslint/npm-audit all green. The upgrade core is sound.

**Live visual harness built & proven** (gitignored at `frontend/.visual-baseline/`): headless Playwright (chromium) scripts — `capture.mjs` (login via "Sign In" button click, NOT Enter; per-screen screenshots + overflow/console checks), `layout.mjs`, `var.mjs`, `ab.mjs` (v4-local vs v3-Render). Faithful local run = backend on :8010 (`DEMO_MODE=true`) + `npm run dev -- --port 3010` with a TEMP `vite.config.ts` proxy edit (`:8000`→`:8010`) that must be reverted before any commit (gym-platform squats :8000/:3000 — do not tear down).

**Findings that change Task 5's scope:**
1. **KEYSTONE BUG — Tailwind 4 preflight vs Vuetify 4 cascade layers.** Vuetify 4 emits its CSS into `@layer`s (new in v4); Tailwind 4's preflight reset then wins the cascade and zeroes `.v-main { padding-left: var(--v-layout-left) }`. Result: `--v-layout-left` computes correctly (256px) but `padding-left:0`, so content renders UNDER the 280px permanent nav drawer — leftmost KPI cards + filter toolbar are CLIPPED on every authenticated screen. v3 was fine (Vuetify 3 styles unlayered → beat Tailwind). Fix = deliberate Tailwind↔Vuetify `@layer` ordering (or disable Tailwind preflight). Adding a bare `@layer vuetify, app, utilities;` (Task 3) did NOT fix it and is not the answer; needs the correct ordering with the actual Vuetify-4 layer name. THIS is the crux of the CSS reconciliation and likely resolves most layout issues at once.
2. **Three color systems, not "150 hex overrides"** (the footprint scan miscounted). Only ~14 hardcoded hex exist, mostly in CSS-var *definitions* + print/high-contrast styles (leave those). Real cohesion work = harmonizing: (a) Vuetify MD3 tonal theme, (b) `carbon-tokens.css` `--cds-*` (heavily used), (c) Tailwind `@theme --color-*` (indigo #1a237e ≠ Carbon #0f62fe). A pre-existing inconsistency the MD3 modernization should unify.
3. **Charts are NOT broken** — `canvas=0` locally is a demo-data-window artifact (default view N/A with no client/date data); all chart-data APIs 200, chart code + build fine. Validate charts on data-populated state (select client/date) or a deploy.

**Revised Task 5 reality:** it's (a) solve the @layer keystone, (b) reconcile the 3 color systems, (c) per-screen visual validation (14 screens × light/dark) — a substantial focused effort, larger/different than this plan's original "rebase 150 .v-* hex" framing. Recommend doing it as dedicated focused work using the proven harness, starting from the @layer keystone.
