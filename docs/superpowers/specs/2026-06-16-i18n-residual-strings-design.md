# i18n — localize residual hardcoded strings + no-raw-text gate (design)

> PR C1 — second of the "PR4" robustness efforts (Run-7 audit debt: "~55 residual
> hardcoded i18n strings"). Independent of the a11y gate (PR4a, merged).

## Goal

Localize the residual user-facing hardcoded strings (add keys to **both**
`en.json` + `es.json`, replace with `$t`), and add the
`@intlify/vue-i18n/no-raw-text` lint rule as a CI gate so new hardcoded template
text is blocked. Outcome: the app is fully translated again (no English leaking
into the Spanish UI) and stays that way.

## Context

vue-i18n 11.4, composition API (`legacy: false`), `fallbackLocale: 'en'`,
`missingWarn` in dev. Locales `src/i18n/locales/{en,es}.json` are **3,564 keys
each with perfect parity (0 drift)** — the app is genuinely bilingual; the
residual hardcoded strings are the only gaps (they're in neither locale). A
heuristic found **~62 template prose literals + ~14 hardcoded `label`/
`placeholder`/`title` attrs** (~60–75 genuine), matching the audit's "~55". No
i18n lint plugin is installed yet, so there's no systematic enumeration today.

## Approach

1. **Install** `@intlify/eslint-plugin-vue-i18n` (dev dep). Wire a **targeted**
   flat-config block into `eslint.config.js` enabling only `no-raw-text` (not the
   whole recommended set — keep scope tight), with
   `settings['vue-i18n'].localeDir = './src/i18n/locales/*.json'`.
2. **Enumerate + triage** every raw-text hit:
   - **Genuine prose/labels** → add a key under the existing namespace convention
     (the 67 namespaces: `kpi`, `capacity`, `reports`, `dashboard`, …), in **en +
     es** (real Spanish, flagged in the PR for native review), replace with
     `{{ $t('…') }}` / `:label="$t('…')"`.
   - **Non-translatable** (formula displays like `DPMO = 750`, units/symbols,
     acronyms `OEE`/`KPI`/`DPMO`, bare numbers) → handled by the rule's
     `ignorePattern` / `ignoreText` config (or a single scoped
     `eslint-disable-next-line` on a one-off formula block) — *not* localized.
3. **Enable** `no-raw-text` at `error`, so `npm run lint` (the CI
   `frontend-lint-and-tests` gate) blocks new hardcoded template text.
4. **Parity guard** — a small vitest test asserting the en/es key sets are
   identical, locking the codebase's 0-drift property against future additions.

## Scope

**In:** user-facing hardcoded strings in `.vue` **templates** (the rule's
domain), plus any obvious script-side `.ts` user-facing strings encountered;
en+es keys with real Spanish; the lint gate; the parity test.

**Out:** deep script-side `.ts` i18n coverage (the rule is template-only — rare in
this app; not gated here), copy rewrites, RTL/new locales, the `onboarding-keys.json`
mechanism. No behavior changes — text + lint config + a parity test only.

## Files

- `frontend/package.json` + lockfile — `@intlify/eslint-plugin-vue-i18n` (dev).
- `frontend/eslint.config.js` — plugin + `no-raw-text` rule + `localeDir` + ignore config.
- `frontend/src/i18n/locales/en.json` + `es.json` — new keys (parity preserved).
- `frontend/src/i18n/__tests__/locale-parity.spec.ts` *(new)* — en/es key-parity test.
- ~60–75 `.vue` components — literals replaced with `$t`.

## Verification

- `npm run lint` clean (the `no-raw-text` rule passes after fixes + ignore config).
- vitest green incl. the new **parity test** (en keys === es keys).
- `vue-tsc` + `npm run build` green.
- A quick **es-toggle spot-check** of one or two converted screens via the local
  harness to confirm the new keys render and no `missingWarn` fires.
- All 4 required CI checks green; main stays green.

## Risk

If `no-raw-text` flags far more than the heuristic's ~75 (lots of punctuation /
symbols / formula text), the ignore-config grows. Mitigation: **size the rule's
raw output first**, then tune `ignorePattern`/`ignoreText` so the gate targets
genuine prose, not symbols — keeping the fix bounded to the genuine ~60–75. The
Spanish translations are flagged for native-speaker review (the gate enforces
*presence* + parity, not translation quality).
