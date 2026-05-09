# Phase C.2 — Branch protection recommendation

**Repo**: `ccmanuelf/kpi-operations`
**Branch**: `main`
**Status**: Most recommended settings already enabled. Two optional
hardening steps documented for explicit user decision.

## Current state (verified 2026-05-07)

```bash
gh api repos/ccmanuelf/kpi-operations/branches/main/protection
```

| Setting | Current | Recommended | Status |
|---|---|---|---|
| Required status checks | `backend-tests, frontend-lint-and-tests, docker-build, e2e-sqlite` | All 4 (added during Phase A.13) | ✅ matches |
| `strict=true` (branches up-to-date before merge) | true | true | ✅ matches |
| Allow force pushes | false | false | ✅ matches |
| Allow deletions | false | false | ✅ matches |
| Required signatures (GPG/SSH) | false | n/a | not required by repo policy |
| Enforce admins | false | true (recommended) | ⏸ optional |
| Required linear history | false | true (optional) | ⏸ optional |
| Required conversation resolution | false | true (recommended) | ⏸ optional |
| Lock branch | false | false | ✅ matches |
| Block creations | false | false | ✅ matches |
| Allow fork syncing | false | n/a | n/a |

The 4 required status checks were finalized during Phase A.13 — that
PR (#14) was the first in 50+ commits where all four jobs went green
in one run. Adding `e2e-sqlite` to the gate was the explicit user
decision in A.13 ("option 3").

## Recommended additional hardening (user decision required)

### 1. `enforce_admins: true`

Without this, the user/owner can push directly to `main` bypassing
the required-checks gate. With it, every change to `main` (including
the user's own) must go through a green PR.

**Tradeoff**: a small slowdown for hot-fix scenarios where the user
wants to push a typo fix to `main` directly. Mitigation: keep a
separate `hotfix/*` branch convention that uses an expedited review
flow.

**Recommendation**: enable. The cost of bypassing the gate even once
is higher than the cost of the extra PR step.

```bash
gh api repos/ccmanuelf/kpi-operations/branches/main/protection \
    --method PUT \
    --input <(gh api repos/ccmanuelf/kpi-operations/branches/main/protection \
              | jq '.enforce_admins.enabled = true | { ...current settings... }')
```

(The full PUT payload re-asserts every existing setting alongside
`enforce_admins: true` — GitHub's API is non-merging.)

### 2. `required_conversation_resolution: true`

Blocks merge until every PR comment thread is resolved. Catches
"reviewer asked, author didn't address" cases where a `LGTM` from a
second reviewer would otherwise let an unaddressed concern through.

**Tradeoff**: minor — reviewers occasionally leave threads open
intentionally as "FYI / no action needed" comments and have to mark
them resolved before merging.

**Recommendation**: enable. The robustness audit found multiple
"interesting" warnings (B.4 batches) where a casual reviewer could
have missed dead code or a copy-paste bug. Forcing thread resolution
adds one more checkpoint.

### 3. `required_linear_history: true` (optional)

Forces every merge to be a fast-forward or rebase — no merge commits.
The Phase A.13 closeout already used a single merge-commit on PR #14
deliberately to "preserve traceability of all work done" (per user
direction). That means the team has expressed a preference for merge
commits in some scenarios.

**Recommendation**: do NOT enable, given the explicit preference for
merge commits when consolidating multi-commit PRs.

### 4. `required_signatures: true` (optional)

Requires every commit to be GPG- or SSH-signed. Adds a significant
local-setup burden for new contributors and AI agents. The repo
doesn't have any documented threat model that needs commit-level
provenance verification.

**Recommendation**: do NOT enable unless a concrete threat appears.

## How to apply (user action)

The agent does not modify branch protection without explicit
per-action approval. To enable both recommended changes
(`enforce_admins` + `required_conversation_resolution`):

```bash
# Capture the current protection JSON first (for safety)
gh api repos/ccmanuelf/kpi-operations/branches/main/protection \
    > /tmp/main-protection-backup.json

# Apply the two recommended changes
gh api repos/ccmanuelf/kpi-operations/branches/main/protection \
    --method PUT \
    --raw-field 'required_status_checks[strict]=true' \
    --raw-field 'required_status_checks[contexts][]=backend-tests' \
    --raw-field 'required_status_checks[contexts][]=frontend-lint-and-tests' \
    --raw-field 'required_status_checks[contexts][]=docker-build' \
    --raw-field 'required_status_checks[contexts][]=e2e-sqlite' \
    --raw-field 'enforce_admins=true' \
    --raw-field 'required_conversation_resolution=true' \
    --raw-field 'allow_force_pushes=false' \
    --raw-field 'allow_deletions=false' \
    --raw-field 'restrictions=null' \
    --raw-field 'required_pull_request_reviews=null'
```

(GitHub's PUT payload requires every field — omitting one resets it
to default. The `gh api` flags above are the minimal idempotent set
matching the current state plus the two changes.)

## Acceptance

- [x] Recommendation document written
- [x] User authorized agent to apply settings 2026-05-08
- [x] `enforce_admins=true` applied
- [x] `required_conversation_resolution=true` applied

## Audit log

| When | Setting | Change |
|---|---|---|
| 2026-05-06 (Phase A.13) | Required status checks | `backend-tests, frontend-lint-and-tests, docker-build, e2e-sqlite` (4-job gate). Set via `gh api repos/.../branches/main/protection PUT` per user mandate "option 3". |
| 2026-05-06 (Phase A.13) | strict, allow_force_pushes, allow_deletions | Already in line with recommendations. |
| 2026-05-07 (Phase C.2) | Documentation | This file written. No live changes applied. |
| 2026-05-08 (Phase C.2) | enforce_admins | Set to true. User authorized agent to apply via `gh api PUT`. Backup of prior config saved to `/tmp/main-protection-backup.json`. |
| 2026-05-08 (Phase C.2) | required_conversation_resolution | Set to true. Same PUT call. |
