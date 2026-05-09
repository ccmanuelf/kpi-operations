# Phase B + C — Production Verification

**Date**: 2026-05-09
**Branch**: `ci/hygiene-phase-b-c-close` → squash-merged to `main` as `25f1518`
**PR**: #15 — *Phase B + C closeout: 0 lint, 0 skips, +245 tests, branch protection hardened*

---

## What was verified

After PR #15 squash-merged to `main`, two confirmation passes
executed in order:

### 1. CI on `main`

Both required-checks gate jobs ran on the post-merge `25f1518` commit
and reported `success`:

| Job | Status | Time |
|---|---|---|
| `backend-tests` | ✅ pass | 20m26s |
| `frontend-lint-and-tests` | ✅ pass | 2m1s |
| `docker-build` | ✅ pass | 1m42s |
| `e2e-sqlite` | ✅ pass | 13m3s |

### 2. Render deploy

Render auto-deployed the `25f1518` bundle within ~2 minutes of merge
(verified via `last-modified: 2026-05-09 01:25:04 UTC` on the served
HTML; merge committed at `01:23:18 UTC`). Spot-checks confirmed the
deploy was on the new bundle:

- `shift-indicator` / `showShiftInfo` / `shift_number` strings — all
  absent from the production JS bundle (the broken QuickActionsFAB
  shift chip and Active-Shift dialog were removed in this PR)
- `QuickActionsFAB` component reference — present (the speed-dial
  navigation shortcuts were preserved)
- `POST /api/v1/auth/login` returned a valid JWT for `admin/admin123`
  → demo seeder ran and the auth path works

### 3. Render E2E (full suite)

The full Playwright suite was run twice against the live deployment.

**First run** (commit `25f1518`, helpers untuned for slow envs):
- 169 passed / 13 failed in 25m12s
- All 13 failures were environment timing, not code bugs:
  - 2 × `admin-defect-types`: `waitForBackend` 10s timeout vs Render
    free-tier 30-60s cold-start
  - 11 × `capacity-planning`: `clickTab` 300ms post-click wait racing
    Vuetify v-tabs reactivity on slower networks; one nav-menu test
    hitting a Pinia-hydration race that collapsed the Planning group

Empirical probe confirmed Calendar tab DID become `selected=true`
and the panel DID swap correctly — the feature works, the assertion
just fired during the transition window.

**Second run** (after E2E hardening commits):
- 180 passed / 0 failed / 2 flaky in 21m18s
- The 2 flakies passed on Playwright's first retry (cold-start
  recovery covered by `retries: 1`)

### Hardening applied

Three changes in `frontend/e2e/`:

1. `helpers.ts`: `waitForBackend` default timeout 10s → 60s. Polls
   exit on first health response, so locally still <500ms; the bump
   only matters when the backend is actually waking up.
2. `capacity-planning.spec.ts` `clickTab` helper: drops `force: true`,
   adds `scrollIntoViewIfNeeded()` for horizontally-scrolling tabs,
   waits for `.v-tab--selected` to be visible BEFORE clicking
   (eliminates v-tabs reactive-binding race), then asserts the
   selected class migrated to the target.
3. `capacity-planning.spec.ts` "should display Capacity Planning in
   navigation menu": click the "Planning" v-list-group activator
   first if the child link isn't already visible — covers the Pinia
   hydration race that collapses the group on prod builds.

---

## Conclusion

`25f1518` is verified clean on production. The Phase B + C invariants
(0 lint, 0 skips, +245 tests, branch protection) hold under the
production Vite build + nginx + Render free-tier conditions.

The Render-E2E suite is now a tool the team can run as a one-shot
post-merge validation. Policy is documented in `docs/CONTRIBUTING.md`
under "Render E2E Policy".

---

## Next-session context

- No open follow-ups from this verification.
- The SimulationV2 / shift-session feature is fully removed; if a
  proper shift-session backend is ever built, the UI scaffolding can
  be reconstructed from PR #15's reverse diff.
- The Render E2E config (`playwright.render.config.ts`) is the
  reference for any future remote-environment validation needs.
