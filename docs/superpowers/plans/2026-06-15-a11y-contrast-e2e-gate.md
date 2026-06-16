# a11y Contrast Audit — blocking e2e CI gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A blocking Playwright spec in the e2e-sqlite job that checks WCAG-AA text contrast on every key screen in light + dark, failing CI on any real below-AA finding.

**Architecture:** Split clean: a pure, vitest-tested module (`src/utils/contrastAudit.ts`) does all the color math + violation-finding in Node; the in-page Playwright step only *reads* raw computed colors/geometry and returns them — no duplicated math, no in-page injection. The spec orchestrates themes × screens via the existing `e2e/helpers.ts#login` and seeded DEMO_MODE data.

**Tech Stack:** Playwright (e2e-sqlite config), Vitest (math unit tests), TypeScript.

**Spec:** `docs/superpowers/specs/2026-06-15-a11y-contrast-e2e-gate-design.md`.

**Branch:** `feat/a11y-contrast-e2e-gate` (spec already committed here).

---

## File structure

- `frontend/src/utils/contrastAudit.ts` *(new)* — pure types + math + `findViolations` (Node-side, vitest-tested).
- `frontend/src/utils/__tests__/contrastAudit.spec.ts` *(new)* — vitest unit tests.
- `frontend/e2e/a11y/collectSamples.ts` *(new)* — in-page DOM reader (returns raw samples; no math).
- `frontend/e2e/a11y/screens.ts` *(new)* — the 14-screen inventory + the allow-list.
- `frontend/e2e/a11y-contrast.spec.ts` *(new)* — orchestration (login, navigate, collect, find, assert).

`e2e/*` import the pure module via a relative path (`../../src/utils/contrastAudit`); Playwright's esbuild resolves it.

---

## Task 1: Pure contrast-audit module (math + findViolations)

**Files:**
- Create: `frontend/src/utils/contrastAudit.ts`
- Test: `frontend/src/utils/__tests__/contrastAudit.spec.ts`

- [ ] **Step 1: Write the failing tests.**
Create `frontend/src/utils/__tests__/contrastAudit.spec.ts`:
```ts
import { describe, it, expect } from 'vitest'
import { parseColor, ratio, isLargeText, findViolations, type Sample } from '../contrastAudit'

describe('contrastAudit math', () => {
  it('parseColor handles rgb(), color(srgb 0-1), hex, transparent', () => {
    expect(parseColor('rgb(255, 255, 255)')).toEqual({ r: 255, g: 255, b: 255, a: 1 })
    expect(parseColor('rgba(0,0,0,0.5)')).toEqual({ r: 0, g: 0, b: 0, a: 0.5 })
    // color(srgb …) components are 0..1 floats -> scaled to 0..255
    const c = parseColor('color(srgb 0.894118 0.886275 0.882353 / 0.6)')!
    expect(Math.round(c.r)).toBe(228)
    expect(c.a).toBeCloseTo(0.6)
    expect(parseColor('#0f62fe')).toEqual({ r: 15, g: 98, b: 254, a: 1 })
    expect(parseColor('transparent')).toEqual({ r: 0, g: 0, b: 0, a: 0 })
    expect(parseColor('oklch(0.5 0.1 200)')).toBeNull() // unknown -> null (skip, don't miscompute)
  })

  it('ratio matches known WCAG pairs', () => {
    expect(ratio({ r: 0, g: 0, b: 0, a: 1 }, { r: 255, g: 255, b: 255, a: 1 })).toBeCloseTo(21, 0)
    expect(ratio({ r: 255, g: 255, b: 255, a: 1 }, { r: 15, g: 98, b: 254, a: 1 })).toBeGreaterThan(4.5)
  })

  it('isLargeText: >=24px, or >=18.66px bold', () => {
    expect(isLargeText(24, 400)).toBe(true)
    expect(isLargeText(19, 700)).toBe(true)
    expect(isLargeText(16, 700)).toBe(false)
    expect(isLargeText(14, 400)).toBe(false)
  })

  it('findViolations flags below-AA, respects large-text threshold + gradients + allow-list', () => {
    const base = { fontWeight: 400, bgStack: ['rgb(255,255,255)'], gradientStops: [] as string[] }
    const samples: Sample[] = [
      { ...base, screen: 'x', theme: 'light', text: 'bad', cls: 'a', color: 'rgb(241,194,27)', fontSize: 14 }, // yellow on white ~1.7 -> violation
      { ...base, screen: 'x', theme: 'light', text: 'ok', cls: 'b', color: 'rgb(22,22,22)', fontSize: 14 },   // near-black on white -> fine
      { screen: 'y', theme: 'light', text: 'My Shift', cls: 'text-h5', color: 'rgb(255,255,255)', fontSize: 32, fontWeight: 600, bgStack: ['rgb(255,255,255)'], gradientStops: ['rgb(25,118,210)'] }, // white on blue gradient -> fine via worst-case stop (large)
    ]
    const v = findViolations(samples, [])
    expect(v.map((x) => x.text)).toEqual(['bad'])
  })

  it('allow-list excludes a documented false-positive', () => {
    const samples: Sample[] = [
      { screen: 'my-shift', theme: 'light', text: 'Sunday, June 14', cls: 'text-body-2', color: 'rgb(255,255,255)', fontSize: 14, fontWeight: 400, bgStack: ['rgb(255,255,255)'], gradientStops: [] },
    ]
    expect(findViolations(samples, [])).toHaveLength(1) // white-on-white = violation without context
    const allow = [{ screen: 'my-shift', classIncludes: 'text-body-2', text: 'Sunday', reason: 'on blue gradient banner' }]
    expect(findViolations(samples, allow)).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Run to see them fail.**
Run from `frontend/`: `npx vitest run src/utils/__tests__/contrastAudit.spec.ts`
Expected: FAIL — `../contrastAudit` not found.

- [ ] **Step 3: Implement the module.**
Create `frontend/src/utils/contrastAudit.ts`:
```ts
// Pure WCAG-AA contrast logic for the a11y e2e gate. All math runs in Node from
// raw samples collected in-page (e2e/a11y/collectSamples.ts) — no in-page math,
// no duplication. Mirrors the gradient-aware audit proven during the Vuetify 4
// migration. See docs/superpowers/specs/2026-06-15-a11y-contrast-e2e-gate-design.md.

export interface Rgb {
  r: number
  g: number
  b: number
  a: number
}

export interface Sample {
  screen: string
  theme: 'light' | 'dark'
  text: string
  cls: string
  color: string // computed CSS color of the text
  fontSize: number // px
  fontWeight: number
  bgStack: string[] // ancestor backgroundColors, nearest-first
  gradientStops: string[] // colors from any ancestor background-image gradient
}

export interface Violation extends Sample {
  ratio: number
  threshold: number
  bgUsed: string
}

export interface AllowEntry {
  screen: string
  classIncludes: string
  text: string // substring match
  reason: string
}

export function parseColor(c: string | null | undefined): Rgb | null {
  if (!c) return null
  const s = c.trim()
  if (s === 'transparent') return { r: 0, g: 0, b: 0, a: 0 }
  if (s.startsWith('color(')) {
    const m = s.match(/[\d.]+/g)
    if (!m || m.length < 3) return null
    return { r: +m[0] * 255, g: +m[1] * 255, b: +m[2] * 255, a: m[3] === undefined ? 1 : +m[3] }
  }
  if (s.startsWith('rgb')) {
    const m = s.match(/[\d.]+/g)
    if (!m) return null
    return { r: +m[0], g: +m[1], b: +m[2], a: m[3] === undefined ? 1 : +m[3] }
  }
  if (s.startsWith('#')) {
    let h = s.slice(1)
    if (h.length === 3) h = h.split('').map((x) => x + x).join('')
    if (h.length < 6) return null
    return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16), a: 1 }
  }
  return null // unknown (e.g. oklch) — skip rather than miscompute
}

function composite(fg: Rgb, bg: Rgb): Rgb {
  return {
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  }
}

function luminance(c: Rgb): number {
  const f = (v: number) => {
    v /= 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
}

export function ratio(a: Rgb, b: Rgb): number {
  const la = luminance(a)
  const lb = luminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

export function isLargeText(fontSizePx: number, fontWeight: number): boolean {
  return fontSizePx >= 24 || (fontSizePx >= 18.66 && fontWeight >= 700)
}

// Composite the ancestor background stack (nearest-first) over white.
function effectiveBg(bgStack: string[]): Rgb {
  const parsed = bgStack.map(parseColor).filter((c): c is Rgb => !!c && c.a > 0)
  let acc: Rgb = { r: 255, g: 255, b: 255, a: 1 }
  for (let i = parsed.length - 1; i >= 0; i--) acc = composite(parsed[i], acc)
  return acc
}

export function findViolations(samples: Sample[], allow: AllowEntry[]): Violation[] {
  const out: Violation[] = []
  for (const s of samples) {
    const fg = parseColor(s.color)
    if (!fg) continue
    const solidBg = effectiveBg(s.bgStack)
    // gradient-aware: worst-case (lowest ratio) over the solid bg + any gradient stops
    const candidates: Rgb[] = [solidBg]
    for (const g of s.gradientStops) {
      const gc = parseColor(g)
      if (gc && gc.a > 0) candidates.push(gc)
    }
    let worst = Infinity
    let bgUsed = solidBg
    for (const cand of candidates) {
      const eff = fg.a < 1 ? composite(fg, cand) : fg
      const r = ratio(eff, cand)
      if (r < worst) {
        worst = r
        bgUsed = cand
      }
    }
    const threshold = isLargeText(s.fontSize, s.fontWeight) ? 3 : 4.5
    if (worst < threshold - 0.01) {
      const allowed = allow.some(
        (a) => a.screen === s.screen && s.cls.includes(a.classIncludes) && s.text.includes(a.text),
      )
      if (!allowed) {
        out.push({
          ...s,
          ratio: +worst.toFixed(2),
          threshold,
          bgUsed: `rgb(${Math.round(bgUsed.r)},${Math.round(bgUsed.g)},${Math.round(bgUsed.b)})`,
        })
      }
    }
  }
  return out
}
```

- [ ] **Step 4: Run the tests to PASS.**
Run: `npx vitest run src/utils/__tests__/contrastAudit.spec.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/utils/contrastAudit.ts frontend/src/utils/__tests__/contrastAudit.spec.ts
git commit -m "feat(a11y): pure gradient-aware contrast-audit module (Node-side, vitest-tested)"
```

---

## Task 2: In-page sample collector + screen inventory

**Files:**
- Create: `frontend/e2e/a11y/collectSamples.ts`
- Create: `frontend/e2e/a11y/screens.ts`

- [ ] **Step 1: Write the screen inventory + allow-list.**
Create `frontend/e2e/a11y/screens.ts`:
```ts
import type { AllowEntry } from '../../src/utils/contrastAudit'

export const SCREENS: { name: string; path: string }[] = [
  { name: 'dashboard', path: '/kpi-dashboard' },
  { name: 'my-shift', path: '/my-shift' },
  { name: 'kpi-efficiency', path: '/kpi/efficiency' },
  { name: 'kpi-quality', path: '/kpi/quality' },
  { name: 'kpi-oee', path: '/kpi/oee' },
  { name: 'plan-vs-actual', path: '/plan-vs-actual' },
  { name: 'work-orders', path: '/work-orders' },
  { name: 'capacity-planning', path: '/capacity-planning' },
  { name: 'simulation-v2', path: '/simulation-v2' },
  { name: 'alerts', path: '/alerts' },
  { name: 'reports-admin-settings', path: '/admin/settings' },
  { name: 'admin-users', path: '/admin/users' },
  { name: 'admin-defect-types', path: '/admin/defect-types' },
]

// Verified false-positives: the MyShift header sits on a blue gradient banner the
// DOM contrast read can't see (manually verified white-on-#1976d2 = 4.6:1). The
// gradient-aware logic covers most cases; these remain in case a stop isn't read.
export const ALLOWLIST: AllowEntry[] = [
  { screen: 'my-shift', classIncludes: 'text-h5', text: 'My Shift', reason: 'white on blue gradient banner (verified 4.6:1)' },
  { screen: 'my-shift', classIncludes: 'text-body-2', text: 'June', reason: 'date subtitle on blue gradient banner (verified)' },
]
```

- [ ] **Step 2: Write the in-page collector (reads raw, no math).**
Create `frontend/e2e/a11y/collectSamples.ts`:
```ts
import type { Page } from '@playwright/test'
import type { Sample } from '../../src/utils/contrastAudit'

// Reads computed colors + geometry for every visible text element on the current
// page. Pure DOM extraction — all contrast math happens in Node (contrastAudit).
export async function collectSamples(
  page: Page,
  screen: string,
  theme: 'light' | 'dark',
): Promise<Sample[]> {
  const raw = await page.evaluate(() => {
    const out: Array<Omit<Sample, 'screen' | 'theme'>> = []
    for (const el of Array.from(document.querySelectorAll('body *'))) {
      const own = Array.from(el.childNodes)
        .filter((n) => n.nodeType === 3)
        .map((n) => (n.textContent || '').trim())
        .join('')
        .trim()
      if (!own) continue
      const cs = getComputedStyle(el)
      if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue
      const r = el.getBoundingClientRect()
      if (r.width < 1 || r.height < 1) continue
      if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) continue
      const bgStack: string[] = []
      const gradientStops: string[] = []
      let node: Element | null = el
      while (node) {
        const ncs = getComputedStyle(node)
        if (ncs.backgroundColor) bgStack.push(ncs.backgroundColor)
        const bi = ncs.backgroundImage
        if (bi && bi.includes('gradient')) {
          const ms = bi.match(/rgba?\([^)]*\)|#[0-9a-fA-F]{3,8}/g) || []
          gradientStops.push(...ms)
        }
        node = node.parentElement
      }
      out.push({
        text: own.slice(0, 60),
        cls: el.className?.toString?.() || '',
        color: cs.color,
        fontSize: parseFloat(cs.fontSize) || 0,
        fontWeight: parseInt(cs.fontWeight) || 400,
        bgStack,
        gradientStops,
      })
    }
    return out
  })
  return raw.map((s) => ({ ...s, screen, theme }))
}
```

- [ ] **Step 3: Type-check (no vitest for e2e files; tsc covers them via the e2e tsconfig/IDE — verify the imports resolve).**
Run from `frontend/`: `npx vue-tsc --noEmit`
Expected: 0 errors (the new src module + e2e imports type-check).

- [ ] **Step 4: Commit.**
```bash
git add frontend/e2e/a11y/collectSamples.ts frontend/e2e/a11y/screens.ts
git commit -m "feat(a11y): in-page sample collector + key-screen inventory + allow-list"
```

---

## Task 3: The blocking Playwright spec

**Files:**
- Create: `frontend/e2e/a11y-contrast.spec.ts`

- [ ] **Step 1: Write the spec.**
Create `frontend/e2e/a11y-contrast.spec.ts`:
```ts
import { test, expect } from '@playwright/test'
import { login } from './helpers'
import { collectSamples } from './a11y/collectSamples'
import { SCREENS, ALLOWLIST } from './a11y/screens'
import { findViolations } from '../src/utils/contrastAudit'

const THEMES = ['light', 'dark'] as const

// Settle colors before sampling (no transition/animation mid-flight).
const FREEZE_CSS = '*,*::before,*::after{transition:none !important;animation:none !important}'

for (const theme of THEMES) {
  test.describe(`a11y contrast — ${theme}`, () => {
    test(`every key screen meets WCAG-AA (${theme})`, async ({ page }) => {
      test.slow() // 13 screens × audit; allow generous time
      await page.setViewportSize({ width: 1440, height: 900 })
      await page.addInitScript((d) => localStorage.setItem('kpi-theme', JSON.stringify({ isDark: d })), theme === 'dark')
      await login(page, 'admin')
      await page.addStyleTag({ content: FREEZE_CSS })

      const all: ReturnType<typeof findViolations> = []
      for (const screen of SCREENS) {
        await page.goto(screen.path)
        await page.waitForLoadState('networkidle').catch(() => {})
        await page.waitForTimeout(800)
        await page.addStyleTag({ content: FREEZE_CSS }).catch(() => {})
        const samples = await collectSamples(page, screen.name, theme)
        all.push(...findViolations(samples, ALLOWLIST))
      }

      const msg = all
        .map((v) => `  [${v.screen}/${v.theme}] ${v.ratio} (<${v.threshold}) "${v.text}" ${v.color} on ${v.bgUsed} .${v.cls}`)
        .join('\n')
      expect(all, `WCAG-AA contrast violations (${theme}):\n${msg}`).toEqual([])
    })
  })
}
```

- [ ] **Step 2: Lint (eslint must accept e2e + the new files; e2e isn't gitignored).**
Run from `frontend/`: `npm run lint`
Expected: clean. (If eslint flags `no-console` etc. in e2e, none are used here; fix any real issue.)

- [ ] **Step 3: Commit.**
```bash
git add frontend/e2e/a11y-contrast.spec.ts
git commit -m "test(a11y): blocking e2e contrast gate over 14 screens x light/dark"
```

---

## Task 4: Verify + PR

**Files:** none (verification).

- [ ] **Step 1: Static + unit gates (local).**
Run from `frontend/`:
```bash
npx vitest run && npx vue-tsc --noEmit && npm run lint && npm run build
```
Expected: vitest green (incl. the new `contrastAudit` tests); tsc 0; eslint clean; build OK.

- [ ] **Step 2: Validate the audit LOGIC against the live local harness (sanity).**
The e2e spec can't run locally (its webServer binds :8000/:3000, occupied by gym-platform). Sanity-check the *logic* via the existing local harness: bring up backend :8010 + dev :3010 (TEMP `vite.config` proxy `:8000`→`:8010`, **revert after**) and run `node .visual-baseline/contrast.mjs light` / `dark` — confirm it still reports 0 real failures (the committed logic mirrors it). Revert the proxy; confirm `git status` shows no `vite.config.ts`.

- [ ] **Step 3: Push + open PR — the e2e gate runs in CI (the real integration check).**
```bash
git push -u origin feat/a11y-contrast-e2e-gate
gh pr create --base main --head feat/a11y-contrast-e2e-gate \
  --title "feat(a11y): blocking e2e contrast gate (PR4a)" \
  --body "PR4a (robustness B). Adds a Playwright spec to the e2e-sqlite suite that audits WCAG-AA text contrast on the 14 key screens in light + dark (gradient-aware), failing on any real below-AA finding. Pure math in src/utils/contrastAudit.ts (vitest-tested); in-page collector reads raw colors; documented allow-list for verified gradient-banner false-positives. Complements the token-level vitest gate (#74). The e2e spec is verified on this PR's e2e-sqlite run (can't run locally — webServer binds :8000/:3000)."
```
Expected: PR opens; **watch the `e2e-sqlite` check closely** — it now includes the contrast gate. If it reports violations, triage: a real regression → fix the color; a false-positive the gradient logic can't read → add a documented allow-list entry; a timing issue → adjust the readiness wait. Iterate on the PR until all 4 checks green, then merge.

---

## Self-review notes (author)

- **Spec coverage:** pure math + findViolations + vitest (Task 1); in-page collector + 14-screen inventory + allow-list (Task 2); blocking spec in e2e-sqlite, both themes, login reuse, freeze-animations determinism (Task 3); verification via vitest + CI (Task 4). Placement = e2e spec in the required job (Task 3/4). Gradient-aware worst-case (Task 1 `findViolations`).
- **No placeholders:** the full module, its tests, the collector, inventory, allow-list, and spec are concrete.
- **Type consistency:** `Rgb`/`Sample`/`Violation`/`AllowEntry`/`parseColor`/`ratio`/`isLargeText`/`findViolations` are used identically across the module, its tests, `collectSamples` (produces `Sample`), `screens.ts` (`AllowEntry`), and the spec (`findViolations(samples, ALLOWLIST)`).
- **DRY:** one math implementation (Node, tested); the in-page step does zero math.
- **Risk:** the only thing unverifiable locally is the Playwright wiring (login/navigation/timing) — contained to Task 3 and proven on the PR's CI run; the contrast logic is unit-tested + harness-sanity-checked. If the gate flakes on a screen, the allow-list + readiness wait are the levers; worst case the spec can be quarantined (`test.fixme`) without affecting the rest of the suite.
