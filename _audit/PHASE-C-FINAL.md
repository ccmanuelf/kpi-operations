# Phase C — Process Safeguards: Final Closeout

**Period**: 2026-05-07 (single-day execution following Phase B closeout)
**Status**: All sub-phases complete. Tracker file is ready for archival
pending user approval.

---

## What Phase C delivered

Phase C locks in the gains from Phases A and B by making them
structurally enforced. The output is documentation + config — no
behavioral code changes.

### C.1 — Pre-commit hooks ✅

The `.pre-commit-config.yaml` had been created during Phase A but
the install step + bypass policy weren't documented in
`CONTRIBUTING.md`. Without that, new contributors silently skipped
the local gate and relied on CI.

Added a "Pre-commit hooks" section to `docs/CONTRIBUTING.md` (commit
f887583) with:

- Install commands (`pip install pre-commit && pre-commit install`)
- Full list of configured hooks (black/flake8/mypy/bandit on backend;
  eslint/vue-tsc on frontend; whitespace + large-file guards)
- Bypass policy: `--no-verify` is forbidden as a default; documented
  exceptions; cross-reference to `feedback_no_shortcuts.md`

Hook coverage matches the CI gate exactly (minus `npm run build`
which is intentionally CI-only — too slow for pre-commit).

### C.2 — Branch protection recommendation ✅

Verified current `main` branch protection via
`gh api repos/ccmanuelf/kpi-operations/branches/main/protection`.
Most recommended settings already enabled (4 required status checks
since Phase A.13, strict=true, no force-pushes, no deletions).

Wrote `_audit/PHASE-C-BRANCH-PROTECTION.md` recommending two
optional hardening steps for explicit user decision:

1. `enforce_admins=true` — block direct push to `main` even by repo
   owner
2. `required_conversation_resolution=true` — block merge until all
   PR review threads resolved

Two other settings considered and explicitly NOT recommended:
- `required_linear_history` (user preference for merge commits per
  PR #14 close-out)
- `required_signatures` (no documented threat model warrants the
  setup burden)

The agent does not modify branch protection without explicit
per-action approval. The PUT payload is documented for user
execution.

### C.3 — Documentation update ✅

Updated:

- **`CLAUDE.md`** (this commit): added two new behavior defaults:
  - "CI must stay green" — references Phase A.13's first-green run
    and requires `gh run list --branch main --limit 1` verification
    before claiming "tests pass"
  - "Permissive assertions are forbidden" — references Phase B.2's
    cleanup and rejects new `assert response.status_code in [...]`
    at review

- **`docs/CONTRIBUTING.md`** (C.1 commit): pre-commit install +
  bypass policy

- **`_audit/PHASE-B-FINAL.md`** (B.6 closeout): full Phase B verdict

- **`_audit/PHASE-C-BRANCH-PROTECTION.md`** (C.2 closeout): branch
  protection recommendation

- **`_audit/PHASE-C-FINAL.md`** (this file): Phase C closeout

The `MEMORY.md` index entry for `ci-hygiene-tracker.md` and the
tracker file itself can be archived/removed once the user explicitly
closes Phase B (the deferred items in B.4/B.7 are documented in the
respective audit files and CLAUDE.md).

---

## Cumulative project results

Across Phases A, B, and C:

### Lint hygiene (Phase A)

| Check | Baseline | After Phase A | Status |
|---|---|---|---|
| Total flake8 errors | 1300 | **0** | ✅ |
| F401 unused imports | 680 | 0 | ✅ |
| F841 unused locals | 328 | 0 | ✅ |
| E402 module-level import not at top | 211 | 0 | ✅ |
| E501 line too long >120 | 39 | 0 | ✅ |
| E741 ambiguous `l` | 18 | 0 | ✅ |
| F811 redefinition | 10 | 0 | ✅ |
| W291 trailing whitespace | 8 | 0 | ✅ |
| F541 f-string | 4 | 0 | ✅ |
| E731 lambda | 2 | 0 | ✅ |
| Mypy errors | 33 | 0 | ✅ |
| Black --check | clean (after E712 fix) | clean | ✅ |
| CI on `main` | red 50+ runs | green | ✅ |

### Robustness (Phase B)

| Metric | Baseline | After Phase B | Status |
|---|---|---|---|
| Backend pytest | 5306 (with 480+ padding) | 4842 (real coverage) | ✅ |
| Frontend vitest | 1826 | 1915 (+89, +5 missing-assertion fixes) | ✅ |
| Permissive assertions | 778 | 0 | ✅ |
| Frontend lint warnings | 395 | 33 (remainder structural — deferred) | partial |
| Frontend coverage thresholds | 22/20/15/24 | 32/25/25/34 | ✅ |
| 0%-coverage views | 47 | 18 (rest covered by E2E) | ✅ |
| Test pollution | unverified | zero artifacts confirmed | ✅ |
| Real bugs uncovered + fixed | — | 2 | ✅ |

### Process safeguards (Phase C)

| Item | Status |
|---|---|
| Pre-commit hooks installed + documented | ✅ |
| Branch protection (4 required checks) | ✅ |
| Branch protection (additional hardening) | ⏸ documented, awaiting user apply |
| CLAUDE.md updated with CI-green + no-permissive-asserts rules | ✅ |
| CONTRIBUTING.md updated with install + bypass policy | ✅ |
| `_audit/PHASE-A-CLOSEOUT.md` (Phase A) | written during A.12 |
| `_audit/PHASE-B-FINAL.md` (Phase B) | ✅ |
| `_audit/PHASE-C-BRANCH-PROTECTION.md` (C.2) | ✅ |
| `_audit/PHASE-C-FINAL.md` (this file) | ✅ |

---

## Deferred items (carry forward)

These are documented and tracked but not closed in this audit cycle:

1. **Phase B.4 — 31 `vue/no-mutating-props` warnings** in
   `WorkbookActionDialogs.vue` and `ShiftDashboardDialogs.vue`. The
   children mutate parent's `state` prop directly; works due to
   `reactive()` auto-unwrap but is the canonical Vue 3 anti-pattern.
   Real fix requires structural refactor: convert to
   `defineModel`-per-property or individual `v-model:propName` API.
   Substantial work — separate batch with explicit user approval.

2. **Phase B.4 — 1 `vue/no-unused-vars`** at
   `DashboardCustomizer.vue:63` and **1 `no-console`** in
   `ProductionKPIs.spec.ts` test fixture. Trivial; left as-is.

3. **Phase B.7 — 8 `// FIXME(2026-06-01)` skipped E2E describe
   blocks**. Owned by the team for the 2026-06-01 deadline per
   `docs/standards/entry-ui-standard.md` §7. The
   `scripts/check-skipped-tests.sh` CI guard prevents new skips
   without similar tracking.

4. **5 of 8 KPI detail pages** still inline their logic in
   `<script setup>` (Availability, OEE, Absenteeism, OnTimeDelivery,
   WIPAging). The composable extraction pattern was only applied to
   Efficiency, Performance, Quality. Smoke-mount provides 60-72%
   line coverage today; refactor when one of these views needs new
   features.

5. **Phase C.2 — `enforce_admins` and
   `required_conversation_resolution`** branch protection settings
   recommended but not yet applied (require explicit user action).

---

## Acceptance for Phase C

- [x] Documentation updated (CLAUDE.md, CONTRIBUTING.md, audit files)
- [x] After C.3 ✅, this tracker file may be deleted (with user
  approval) and removed from MEMORY.md

The tracker `memory/ci-hygiene-tracker.md` is now ready for
archival. The deferred items are documented in:
- `_audit/PHASE-B-FINAL.md` (B.4, B.7, refactor backlog)
- `_audit/PHASE-C-BRANCH-PROTECTION.md` (C.2 user-action items)
- `CLAUDE.md` (process invariants)

After the user explicitly approves closing the audit, remove the
tracker entry from `memory/MEMORY.md` and either archive
`ci-hygiene-tracker.md` to a history folder or delete it.

---

## Final invariants

These rules now apply going forward and are enforced by a
combination of pre-commit hooks, CI gates, and reviewer convention:

1. **Mypy stays at 0 errors.**
2. **Black --check stays clean.**
3. **Flake8 stays at 0 errors.**
4. **Backend pytest count never drops** (4842 baseline; only goes
   up unless a deletion is explicitly tracked as dead-code removal).
5. **Frontend coverage thresholds 32/25/25/34** stay green; only
   ratchet up.
6. **CI on `main` stays green.** The 4-job gate is required. Agents
   must verify with `gh run list --branch main --limit 1` before
   claiming a passing build.
7. **No permissive assertions** (`status_code in [...]`). Each test
   asserts ONE expected code.
8. **No `# noqa` / `eslint-disable` as default**. Real fixes only.
   Per-line suppression with justifying comment is the last resort.
9. **No autoflake. No regex sweeps. No global sed.** All changes
   per-file, manually verified.
10. **Pre-commit hooks installed locally.** Bypassing `--no-verify`
    is forbidden as a default.
