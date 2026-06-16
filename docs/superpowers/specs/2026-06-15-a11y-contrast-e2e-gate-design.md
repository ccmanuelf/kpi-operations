# a11y Contrast Audit — blocking e2e CI gate (design)

> PR4a. First of the "PR4" robustness efforts (B). Promotes the gradient-aware
> per-screen contrast audit (built local-only during the Vuetify 4 migration)
> into a committed, blocking Playwright check, complementing the token-level
> vitest gate shipped in PR #74.

## Goal

Catch **component-level** WCAG-AA contrast regressions in CI — bespoke colors in
real rendered screens, not just design tokens. A Playwright spec drives every key
screen in **light and dark**, computes the contrast of all visible text, and
fails the `e2e-sqlite` check on any real below-AA finding.

## Why

PR #74's `contrast.a11y.spec.ts` asserts the Carbon **token** pairings meet AA —
but it can't catch a developer hardcoding a sub-AA color in a component (exactly
the class of bug the migration's manual sweep found in the alerts palette,
work-order chips, etc.). The browser audit closes that gap. The two gates are
complementary: tokens (fast, deterministic, vitest) + rendered screens
(end-to-end, Playwright).

## Placement

A committed Playwright spec in the **existing `e2e-sqlite` job** (run via
`playwright.sqlite.config.ts`), not a separate job. That job already boots the
full app (backend + frontend webServer, **DEMO_MODE seeded data**), exposes
`e2e/helpers.ts#login`, and runs with `retries: 2` in CI. Adding the spec there
makes it part of an existing **required** check (blocking) and reuses all the
deterministic infrastructure — no new app-bootstrap, no new required check to
wire.

## Components

- **`frontend/e2e/a11y/wcag.ts`** *(new)* — pure contrast math: `parseColor`
  (`rgb()`/`rgba()`/`color(srgb …)` 0–1 floats/hex/`transparent`),
  `composite(fg,bg)` (alpha), `relativeLuminance`, `contrastRatio(fg,bg)`,
  `isLargeText(fontSizePx, fontWeight)` (≥24px, or ≥18.66px bold → 3.0 else 4.5).
  Unit-tested by vitest. Injected into the page (via `addInitScript`) so the
  in-page audit reuses one implementation (no drift).
- **`frontend/e2e/a11y/contrast-audit.ts`** *(new)* — the in-page DOM sweep
  (every element with its own visible text → effective fg vs the composited
  ancestor background; **gradient-aware**: when an ancestor has a
  `background-image` gradient, evaluate worst-case contrast across its color
  stops) returning `{screen, theme, text, ratio, threshold, fg, bg, cls}[]`; plus
  `SCREENS` (the 14-key inventory: dashboard, my-shift, kpi-efficiency/quality/oee,
  plan-vs-actual, work-orders, capacity-planning, simulation-v2, alerts,
  admin/settings, admin/users, admin/defect-types).
- **`frontend/e2e/a11y/contrast-allowlist.ts`** *(new)* — a small, documented set
  of verified false-positives the DOM audit can't read (the MyShift gradient-banner
  title + subtitle, manually verified ≥4.6:1 white-on-#1976d2), keyed by
  `{screen, classIncludes, text, reason}`. Zero-tolerance for anything else.
- **`frontend/e2e/a11y-contrast.spec.ts`** *(new)* — for each theme
  (`light`,`dark`) × each screen: `login(page,'admin')`; seed
  `localStorage['kpi-theme']`; `page.goto(screen)`; wait (network-idle +
  element-ready); run the audit; drop allow-listed entries; **`expect(real).toEqual([])`**
  with a message listing each violation (screen/theme/text/ratio/fg/bg).

## Determinism (so it can block without flaking)

- Reuse e2e's **seeded DEMO_MODE data** (stable content) + the config's
  `retries: 2`.
- Fixed **1440×900** viewport.
- Inject a stylesheet disabling **transitions/animations** (`* { transition:none
  !important; animation:none !important }`) so computed colors are settled before
  sampling.
- Per-screen readiness: `waitForLoadState('networkidle')` + wait for a primary
  content selector; skip elements with zero size / offscreen / `display:none`.
- The **allow-list** guarantees the known gradient-banner false-positives never
  flake the gate even if gradient parsing misses an edge case.

## Scope

**In:** 14 key authenticated screens, light + dark, desktop viewport; blocking in
`e2e-sqlite`. **Out:** mobile-viewport a11y (later pass), non-text/icon contrast
(graphical-object 3:1 — separate effort), keeping the gitignored
`.visual-baseline/` harness for ad-hoc local runs. No app/behavior changes — this
is a test-only addition (if it surfaces a real violation, that fix is its own change).

## Verification reality

The e2e config binds `:8000`/`:3000` (occupied by the local gym-platform stack),
so this spec **can't be run locally here** — the same constraint as every e2e
spec. Validation: the `wcag.ts` math via **vitest**; the audit logic end-to-end
via the existing `:8010`/`:3010` local harness (already at 0 real failures); and
the **spec integration on the PR's own CI run** (iterate there before merge, as
with the AG-Grid functional gate).

## Validation

- vitest (incl. new `wcag.ts` unit tests) + vue-tsc + eslint green.
- The new spec passes in CI (`e2e-sqlite`) on the 14 screens × 2 themes with the
  allow-list → 0 violations; a deliberately-broken color locally (harness) proves
  the audit *detects* violations.
- All 4 required checks green; main stays green.
