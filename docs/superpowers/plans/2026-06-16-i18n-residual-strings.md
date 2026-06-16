# i18n residual strings + no-raw-text gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Localize the residual hardcoded user-facing strings (en + es + `$t`) and add `@intlify/vue-i18n/no-raw-text` as a CI lint gate, plus an en/es key-parity test.

**Architecture:** Install the i18n lint plugin to *enumerate* raw template text; localize the genuine strings into both locales (real Spanish, parity preserved) and replace with `$t`; configure ignores for genuinely non-translatable literals; flip the rule to `error` so CI blocks regressions; lock parity with a vitest test.

**Tech Stack:** vue-i18n 11.4, `@intlify/eslint-plugin-vue-i18n`, ESLint flat config, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-16-i18n-residual-strings-design.md`.

**Branch:** `feat/i18n-residual-strings` (spec already committed here).

---

## File structure

- `frontend/package.json` + lockfile — `@intlify/eslint-plugin-vue-i18n` (dev).
- `frontend/eslint.config.js` — plugin + `no-raw-text` rule + `localeDir` + ignore config.
- `frontend/src/i18n/locales/en.json` + `es.json` — new keys (parity preserved).
- `frontend/src/i18n/__tests__/locale-parity.spec.ts` *(new)* — en/es key-parity test.
- ~60–75 `.vue` components — literals → `$t`.

---

## Task 1: Install the plugin + wire `no-raw-text` (warn) + enumerate

**Files:**
- Modify: `frontend/package.json` (+ lockfile), `frontend/eslint.config.js`

- [ ] **Step 1: Install the plugin (dev).**
Run from `frontend/`:
```bash
npm install -D @intlify/eslint-plugin-vue-i18n
```
Expected: installs; `npm audit` still 0 (verify; if it pulls a vulnerable transitive, stop and assess).

- [ ] **Step 2: Wire the rule at `warn` (so the suite still passes while we enumerate).**
In `eslint.config.js`: add the import at the top —
```js
import vueI18n from '@intlify/eslint-plugin-vue-i18n'
```
and add this config block to the exported array, immediately after the existing `{ files: ['**/*.vue'], … 'vue/valid-v-slot' … }` block:
```js
  {
    files: ['**/*.vue'],
    plugins: { '@intlify/vue-i18n': vueI18n },
    settings: {
      'vue-i18n': {
        localeDir: './src/i18n/locales/*.json',
        messageSyntaxVersion: '^11.0.0',
      },
    },
    rules: {
      // Start at warn to enumerate; flipped to error in Task 4.
      '@intlify/vue-i18n/no-raw-text': ['warn', {
        // ignore pure symbols / numbers / punctuation / formula glyphs
        ignorePattern: '^[\\s\\d%·°.,:;!?#()\\[\\]{}\\-+*×÷=/|<>$€%]+$',
        // domain acronyms that are identical in es and not translated
        ignoreText: ['OEE', 'KPI', 'DPMO', 'FPY', 'WIP', 'PPM', 'CSV', 'AI', 'BOM', 'ID'],
      }],
    },
  },
```

- [ ] **Step 3: Enumerate the raw-text hits (size the work).**
Run from `frontend/`:
```bash
npx eslint "src/**/*.vue" 2>&1 | grep -c 'no-raw-text'
npx eslint "src/**/*.vue" 2>&1 | grep -B1 'no-raw-text' > /tmp/rawtext.txt; sed -n '1,80p' /tmp/rawtext.txt
```
Expected: the working list of raw-text findings. If the count is far above ~75, tighten `ignorePattern`/`ignoreText` (Step 2) for symbol/number noise and re-run, so the list is the genuine user-facing prose. This list bounds Task 3.

- [ ] **Step 4: Commit the tooling (rule at warn — non-blocking for now).**
```bash
git add frontend/package.json frontend/package-lock.json frontend/eslint.config.js
git commit -m "build(i18n): add @intlify no-raw-text rule (warn) to enumerate raw text"
```

---

## Task 2: en/es key-parity test (guard)

**Files:**
- Create: `frontend/src/i18n/__tests__/locale-parity.spec.ts`

- [ ] **Step 1: Write the parity test.**
Create `frontend/src/i18n/__tests__/locale-parity.spec.ts`:
```ts
import { describe, it, expect } from 'vitest'
import en from '../locales/en.json'
import es from '../locales/es.json'

function flatKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const out: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      out.push(...flatKeys(v as Record<string, unknown>, key))
    } else {
      out.push(key)
    }
  }
  return out
}

describe('locale parity (en <-> es)', () => {
  it('en and es define exactly the same key set', () => {
    const enKeys = flatKeys(en as Record<string, unknown>).sort()
    const esKeys = flatKeys(es as Record<string, unknown>).sort()
    const missingInEs = enKeys.filter((k) => !esKeys.includes(k))
    const missingInEn = esKeys.filter((k) => !enKeys.includes(k))
    expect({ missingInEs, missingInEn }).toEqual({ missingInEs: [], missingInEn: [] })
  })
})
```

- [ ] **Step 2: Run it (passes now — 0 drift baseline; guards Task 3 additions).**
Run: `npx vitest run src/i18n/__tests__/locale-parity.spec.ts`
Expected: PASS. (If it can't import JSON, confirm `resolveJsonModule` is set in tsconfig — it is, since other code imports the locale JSON.)

- [ ] **Step 3: Commit.**
```bash
git add frontend/src/i18n/__tests__/locale-parity.spec.ts
git commit -m "test(i18n): lock en/es key parity (0-drift guard)"
```

---

## Task 3: Localize the genuine strings (methodology + worked example)

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/es.json`, and the ~60–75 `.vue` files from Task 1's list.

> The exact list isn't knowable until Task 1 Step 3 runs; that list bounds this
> task. For EACH genuine raw-text finding, apply the worked example below; for
> genuinely non-translatable findings, extend the ignore config instead.

- [ ] **Step 1: Localize each genuine string (repeat per finding).**
Worked example — `src/views/KPIDashboard.vue` has `>AI Predictions<`:
  1. Add the key to **en.json** under the right namespace:
     ```json
     "kpi": { "aiPredictions": "AI Predictions" }
     ```
  2. Add the **es.json** counterpart at the identical path (real Spanish):
     ```json
     "kpi": { "aiPredictions": "Predicciones de IA" }
     ```
  3. Replace the literal in the template:
     ```html
     <!-- before -->  <span>AI Predictions</span>
     <!-- after  -->  <span>{{ $t('kpi.aiPredictions') }}</span>
     ```
  For attribute literals: `:label="$t('…')"` (bind), not `label="…"`.
  Reuse an existing key if the same string already exists (grep the locale first:
  `grep -i '"ai predictions"' src/i18n/locales/en.json`).

- [ ] **Step 2: For non-translatable findings, extend the ignore config (don't localize).**
Formula/data displays (e.g. `DPMO = 750`, `Σ`, unit suffixes) → add to
`ignoreText` or widen `ignorePattern` in `eslint.config.js`; for a one-off block,
`<!-- eslint-disable-next-line @intlify/vue-i18n/no-raw-text -->` with a comment
saying why (formula display, not UI copy).

- [ ] **Step 3: Re-run the rule until only intended ignores remain.**
Run from `frontend/`: `npx eslint "src/**/*.vue" 2>&1 | grep -c 'no-raw-text'`
Expected: `0` (every genuine string localized; the rest matched by ignore config).

- [ ] **Step 4: Parity + type + render checks.**
Run from `frontend/`:
```bash
npx vitest run src/i18n/__tests__/locale-parity.spec.ts && npx vue-tsc --noEmit
```
Expected: parity PASS (every new key added to both locales); tsc 0.

- [ ] **Step 5: Commit (may split across a few commits as you work through files).**
```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/es.json frontend/src/**/*.vue frontend/eslint.config.js
git commit -m "i18n: localize residual hardcoded strings (en + es)"
```

---

## Task 4: Flip the gate to error

**Files:**
- Modify: `frontend/eslint.config.js`

- [ ] **Step 1: Change `no-raw-text` from `warn` to `error`.**
In `eslint.config.js`, in the `@intlify/vue-i18n` block, change `['warn', {…}]` to `['error', {…}]`.

- [ ] **Step 2: Lint must be clean (the gate now blocks).**
Run from `frontend/`: `npm run lint`
Expected: `ESLint: No issues found` (exit 0). If anything remains, it's either a missed genuine string (localize it, Task 3) or a non-translatable one (ignore it, Task 3 Step 2).

- [ ] **Step 3: Commit.**
```bash
git add frontend/eslint.config.js
git commit -m "build(i18n): enforce no-raw-text (error) so new hardcoded text is blocked"
```

---

## Task 5: Verify + PR

**Files:** none (verification).

- [ ] **Step 1: Full static + unit gates.**
Run from `frontend/`:
```bash
npm run build && npx vitest run && npx vue-tsc --noEmit && npm run lint && npm audit
```
Expected: build OK; vitest pass (incl. locale-parity); tsc 0; eslint clean; audit 0.

- [ ] **Step 2: es-toggle render spot-check (one or two converted screens).**
With the local harness (backend :8010 + dev :3010, TEMP `vite.config` proxy
`:8000`→`:8010`, **revert after**): load a converted screen, toggle to Spanish,
and confirm the new strings render in Spanish with no `[intlify] Not found …`
console warnings. Revert the proxy; confirm `git status` shows no `vite.config.ts`.

- [ ] **Step 3: Push + open PR.**
```bash
git push -u origin feat/i18n-residual-strings
gh pr create --base main --head feat/i18n-residual-strings \
  --title "feat(i18n): localize residual hardcoded strings + no-raw-text gate (C1)" \
  --body "C1 (Run-7 audit debt). Localizes the residual hardcoded user-facing strings (en + es, real Spanish flagged for native review, parity preserved) and adds @intlify/vue-i18n/no-raw-text as a CI lint gate so new hardcoded template text is blocked. Adds an en/es key-parity vitest test. Spec/plan under docs/superpowers/. Spanish strings flagged for a native-speaker review pass."
```
Expected: PR opens; 4 required checks green; merge on green.

---

## Self-review notes (author)

- **Spec coverage:** install + rule wiring + enumerate (Task 1); parity test (Task 2); localize genuine strings + ignore non-translatable (Task 3); gate at error (Task 4); verify + es spot-check + PR (Task 5).
- **No placeholders:** the rule config, parity test, and worked localization example are concrete; the full per-string list is intentionally bounded by Task 1 Step 3's enumeration (not knowable beforehand) — methodology + worked example + the `0 findings` done-gate cover it, per the writing-plans guidance for enumerate-then-fix work.
- **Type consistency:** `flatKeys` is the only defined helper; locale key paths use the existing dotted-namespace convention; `$t('namespace.key')` matches the app's usage.
- **Risk:** rule noisiness — Task 1 Step 3 sizes it and Step 2's `ignorePattern`/`ignoreText` keep the gate targeting prose. Spanish quality is flagged for native review; the gate enforces presence + parity, not fluency.
