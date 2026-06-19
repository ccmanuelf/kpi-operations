# Python lockfile + hash pinning (C4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate hash-pinned, fully-resolved lockfiles from the existing source requirements and install them everywhere with `--require-hashes --only-binary=:all:`, add a hermetic lock-drift + build-free verify CI gate, and pin the Docker base image to its digest — reproducible, tamper-resistant builds.

**Architecture:** `pip-tools` compiles `requirements.txt`/`requirements-dev.txt` → committed `requirements.lock`/`requirements-dev.lock` (resolved + sha256 hashes), generated HERMETICALLY inside the digest-pinned `python:3.11.11` container so output is byte-reproducible. Docker installs the prod lock, CI/e2e install the dev lock, all wheels-only + hash-required. A CI step recompiles (sticky/no-`--upgrade`) and asserts zero drift + dry-run-verifies hashes/wheels without building.

**Tech Stack:** pip-tools 7.5.3, pip `--require-hashes`/`--only-binary`, Docker, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-06-18-python-lockfile-hash-pinning-design.md`.

**Branch:** `chore/python-lockfile-hash-pinning` (spec committed here @ `9b08a99`).

## Global Constraints

- **Exact pins:** `pip-tools==7.5.3`; base image `python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5`.
- **Hermetic generation:** locks are ALWAYS generated inside that digest-pinned container **with `docker run --platform linux/amd64`** (the CI runner + Render + Docker-build target arch) so output is byte-reproducible regardless of the host's arch — a maintainer on an arm64 Mac must still produce the amd64 lock the amd64 drift gate expects. (Verified 2026-06-18: this dep set resolves identically on arm64/amd64, but pinning the platform keeps it deterministic if a future dep carries platform markers.) Canonical compile flags: `pip-compile --generate-hashes --no-header --output-file=<lock> <source>` (the `--no-header` keeps output path-independent; pip-compile is *sticky* — without `--upgrade` it keeps the versions already in the committed lock, changing only when a source constraint changed).
- **Install flags everywhere:** `--require-hashes --only-binary=:all:` (wheels-only ⇒ no sdist builds ⇒ self-contained hashed set).
- **No version changes:** the lock pins the CURRENT resolution; do NOT bump any dependency. The CVE-annotated `==` pins in the sources stay the source of truth.
- **Sources unchanged except adding `pip-tools`:** keep `backend/requirements.txt` and the CVE comments as-is; add only `pip-tools==7.5.3` to `backend/requirements-dev.txt`.
- **CI must stay green:** the 4 required checks (`backend-tests`, `frontend-lint-and-tests`, `docker-build`, `e2e-sqlite`). The drift+verify gate is added as STEPS inside the existing `backend-tests` job so it is covered by an already-required check (no branch-protection change needed).
- Commit per task. Docker is available locally for build verification. detect-secrets/pre-commit may reformat/abort the first commit — re-add + re-commit.

---

## Task 1: Add pip-tools + generate the hash-pinned locks (hermetic, reproducible)

**Files:**
- Modify: `backend/requirements-dev.txt`
- Create: `backend/requirements.lock`, `backend/requirements-dev.lock` (generated)

- [ ] **Step 1: Add pip-tools to the dev sources.** Append to `backend/requirements-dev.txt` (under a new `# Lock tooling` comment, after the security-gates block):
```
# Lock tooling (C4) — compiles the hash-pinned *.lock files
pip-tools==7.5.3
```

- [ ] **Step 2: Generate both locks hermetically.** Run from the repo root:
```bash
IMAGE="python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5"
docker run --rm -v "$PWD/backend:/work" -w /work "$IMAGE" sh -ec '
  pip install --quiet --no-cache-dir pip-tools==7.5.3
  pip-compile --generate-hashes --no-header --output-file=requirements.lock requirements.txt
  pip-compile --generate-hashes --no-header --output-file=requirements-dev.lock requirements-dev.txt
'
```
Expected: `backend/requirements.lock` (prod, every pinned package with `--hash=sha256:…` lines) and `backend/requirements-dev.lock` (superset incl. pytest/black/etc. + pip-tools). `requirements-dev.txt`'s `-r requirements.txt` means the dev lock is a superset; the prod portion pins identical versions to `requirements.lock`.

- [ ] **Step 3: Prove reproducibility.** Re-run the exact Step-2 command; `git diff --stat backend/*.lock` → **no changes** (byte-identical on re-run). If it differs, the generation isn't hermetic — stop and report.

- [ ] **Step 4: Build-free verify (hashes + wheels-only) — inside the pinned container.**
```bash
IMAGE="python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5"
docker run --rm -v "$PWD/backend:/work" -w /work "$IMAGE" sh -ec '
  python -m pip install --quiet --upgrade pip
  pip install --require-hashes --only-binary=:all: --dry-run -r requirements.lock
  pip install --require-hashes --only-binary=:all: --dry-run -r requirements-dev.lock
'
```
Expected: both resolve with all hashes satisfied and every package available as a wheel (no "could not find a version that satisfies … (only sdist)"). If a package is sdist-only, report it — that package needs its wheel sourced or its build backend hash-pinned explicitly (do NOT silently drop `--only-binary`).

- [ ] **Step 5: Commit.**
```bash
git add backend/requirements-dev.txt backend/requirements.lock backend/requirements-dev.lock
git commit -m "build(deps): hash-pinned lockfiles via pip-tools (C4 Task 1)"
```

---

## Task 2: Install the prod lock in Docker (wheels-only, hash-required) + pin base image digest

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Pin both base-image `FROM` lines to the digest.** Replace each `FROM python:3.11.11-slim-bookworm as builder` and `FROM python:3.11.11-slim-bookworm as production` with:
```dockerfile
FROM python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5 as builder
```
```dockerfile
FROM python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5 as production
```
(Keep the existing explanatory comments above each FROM.)

- [ ] **Step 2: Install from the lock with the flags.** In the builder stage, change the copy + install (Dockerfile ~16/19):
```dockerfile
# Copy the hash-pinned lock first for layer caching
COPY backend/requirements.lock ./backend/

# Install Python dependencies — hash-verified, wheels-only (reproducible, tamper-resistant)
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: --prefix=/usr/local -r backend/requirements.lock
```
(If a later stage or step also `COPY backend/requirements.txt`, leave the source file in the image only if something needs it; the install now uses the lock.)

- [ ] **Step 3: Build the image (full confirmation).** Run from repo root:
```bash
docker build -t kpi-c4-test .
```
Expected: builds successfully; the `pip install --require-hashes --only-binary=:all:` step completes (every prod dep installed from a hash-verified wheel). If it fails on a missing hash/wheel, that's a real gap surfaced — report it (do not relax the flags).

- [ ] **Step 4: Commit.**
```bash
git add Dockerfile
git commit -m "build(docker): install hash-pinned lock wheels-only + digest-pin base image (C4 Task 2)"
```

---

## Task 3: Install the dev lock in CI + e2e (wheels-only, hash-required)

**Files:**
- Modify: `.github/workflows/ci.yml`, `.github/workflows/e2e.yml`

- [ ] **Step 1: ci.yml — install the dev lock.** The `backend-tests` job has `defaults.run.working-directory: backend`, so the install runs from `backend/` (paths are relative to it). Change the install step (ci.yml ~34-35) to:
```yaml
        run: |
          python -m pip install --upgrade pip
          pip install --require-hashes --only-binary=:all: -r requirements-dev.lock
```
And update the `cache-dependency-path` (ci.yml ~28, repo-root-relative — not subject to working-directory) from `backend/requirements-dev.txt` to `backend/requirements-dev.lock`.

- [ ] **Step 2: e2e.yml — install the dev lock.** Change e2e.yml ~35 to:
```yaml
        run: pip install --require-hashes --only-binary=:all: -r backend/requirements-dev.lock
```
And `cache-dependency-path` (e2e.yml ~26) → `backend/requirements-dev.lock`.

- [ ] **Step 3: Verify the dev lock installs + the suite runs (local proxy for CI).** In a clean throwaway venv on Python 3.11:
```bash
python3.11 -m venv /tmp/c4venv && /tmp/c4venv/bin/python -m pip install --upgrade pip
/tmp/c4venv/bin/pip install --require-hashes --only-binary=:all: -r backend/requirements-dev.lock
cd backend && /tmp/c4venv/bin/python -m pytest tests/test_bootstrap/ -q
```
Expected: the hashed wheels-only install succeeds and the smoke tests pass (confirms the locked env is functional). (Full `pytest tests/` runs in CI.)

- [ ] **Step 4: Commit.**
```bash
git add .github/workflows/ci.yml .github/workflows/e2e.yml
git commit -m "ci(deps): install hash-pinned dev lock wheels-only in ci + e2e (C4 Task 3)"
```

---

## Task 4: Lock-drift + verify gate, regeneration script, CONTRIBUTING note

**Files:**
- Create: `scripts/lock-deps.sh`
- Modify: `.github/workflows/ci.yml` (add steps to the existing `backend-tests` job), `docs/CONTRIBUTING.md`

- [ ] **Step 1: Create `scripts/lock-deps.sh`.**
```bash
#!/usr/bin/env bash
# Regenerate the hash-pinned dependency locks HERMETICALLY (inside the
# digest-pinned python base image) so output is byte-reproducible across hosts.
# Run after editing backend/requirements.txt or backend/requirements-dev.txt,
# then commit both backend/*.lock.
set -euo pipefail
IMAGE="python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5"
ROOT="$(git rev-parse --show-toplevel)"
# --platform linux/amd64 pins generation to the CI/Render/Docker target arch so
# the lock is byte-identical regardless of the maintainer's host arch.
docker run --rm --platform linux/amd64 -v "$ROOT/backend:/work" -w /work "$IMAGE" sh -ec '
  pip install --quiet --no-cache-dir pip-tools==7.5.3
  pip-compile --generate-hashes --no-header --output-file=requirements.lock requirements.txt
  pip-compile --generate-hashes --no-header --output-file=requirements-dev.lock requirements-dev.txt
'
echo "Regenerated backend/requirements.lock + backend/requirements-dev.lock"
```
Make it executable: `chmod +x scripts/lock-deps.sh`.

- [ ] **Step 2: Add drift + verify steps to the `backend-tests` job in ci.yml.** Add after the "Install dependencies" step. The job default working-directory is `backend/`, but the script + lock paths are repo-root-relative, so BOTH new steps set `working-directory: .` (the same override the mypy step uses). Docker is available on ubuntu-latest.
```yaml
      - name: Lock drift check (sources must be re-locked)
        working-directory: .
        run: |
          ./scripts/lock-deps.sh
          git diff --exit-code -- backend/requirements.lock backend/requirements-dev.lock \
            || { echo "::error::Lock drift — a source requirements file changed without regenerating the lock. Run scripts/lock-deps.sh and commit backend/*.lock."; exit 1; }
      - name: Build-free hash + wheel verify
        working-directory: .
        run: |
          pip install --require-hashes --only-binary=:all: --dry-run -r backend/requirements.lock
          pip install --require-hashes --only-binary=:all: --dry-run -r backend/requirements-dev.lock
```
(The drift step re-runs the hermetic compile and `git diff --exit-code` is empty when the committed lock matches the sources; pip-compile's stickiness means a mere upstream release does NOT cause drift.)

- [ ] **Step 3: Document the dependency-update flow in `docs/CONTRIBUTING.md`.** Add a short section:
```markdown
## Updating Python dependencies

Edit the SOURCE files only — `backend/requirements.txt` (prod) or
`backend/requirements-dev.txt` (dev/test/tooling), keeping the `==` pins and
CVE annotations. Then regenerate the hash-pinned locks:

    ./scripts/lock-deps.sh

Commit both `backend/requirements.lock` and `backend/requirements-dev.lock`
alongside the source change. CI's lock-drift gate fails if a source changed
without re-locking. Dependabot bumps the source files; when batching its PRs,
run `./scripts/lock-deps.sh` and commit the regenerated locks.
```

- [ ] **Step 4: Verify the gate passes on the committed locks.** Run from repo root: `./scripts/lock-deps.sh && git diff --exit-code -- backend/requirements.lock backend/requirements-dev.lock` → exit 0 (no drift). Then the two `--dry-run` verifies (Task 1 Step 4 form) → pass.

- [ ] **Step 5: Commit.**
```bash
git add scripts/lock-deps.sh .github/workflows/ci.yml docs/CONTRIBUTING.md
git commit -m "ci(deps): hermetic lock-drift + verify gate, lock-deps.sh, CONTRIBUTING (C4 Task 4)"
```

---

## Task 5: Final verification + PR

**Files:** none (verification).

- [ ] **Step 1: End-to-end local verification.** From repo root:
```bash
./scripts/lock-deps.sh && git diff --exit-code -- backend/*.lock   # reproducible, no drift
docker build -t kpi-c4-final .                                      # prod lock installs wheels-only, hash-verified
```
Expected: no drift; image builds. (CI runs the full pytest + e2e against the dev lock.)

- [ ] **Step 2: Confirm no dependency versions changed.** `git diff main -- backend/requirements.txt backend/requirements-dev.txt` shows ONLY the added `pip-tools==7.5.3` line (no version bumps to existing deps); the locks pin the pre-existing resolution.

- [ ] **Step 3: Push + PR.**
```bash
git push -u origin chore/python-lockfile-hash-pinning
gh pr create --base main --head chore/python-lockfile-hash-pinning \
  --title "build(deps): Python lockfiles + hash pinning (C4)" \
  --body "C4. Adds pip-tools-generated, sha256-hash-pinned lockfiles (backend/requirements.lock + requirements-dev.lock), installed everywhere with --require-hashes --only-binary=:all: (wheels-only ⇒ self-contained, tamper-resistant). Locks are generated hermetically inside the digest-pinned python:3.11.11 image (byte-reproducible). Docker base image pinned to @sha256; Docker/CI/e2e install from the locks. A hermetic lock-drift + build-free dry-run verify gate runs in backend-tests; scripts/lock-deps.sh + CONTRIBUTING document the dependabot/batch flow. No dependency versions changed. Spec/plan under docs/superpowers/."
```
Expected: 4 required checks green (incl. the new drift+verify steps in backend-tests); report for merge approval (do not auto-merge). After merge: sync local main 0/0, confirm post-merge main CI, verify local == GitHub == Render (Render redeploys from the hash-pinned image; `/health/live` 200).

---

## Self-review notes (author)

- **Spec coverage:** pip-tools + locks (Task 1) · wheels-only/hash-required install in Docker + base digest (Task 2) · CI/e2e dev-lock install (Task 3) · hermetic drift gate + dry-run verify + lock-deps.sh + CONTRIBUTING/dependabot flow (Task 4) · reproducibility + no-version-change + PR (Tasks 1,5). All spec sections map to a task.
- **No placeholders:** every command carries the exact pinned image digest + `pip-tools==7.5.3`; the lockfiles are GENERATED artifacts (the generation command is the concrete instruction — the hundreds of hash lines are not hand-written). Dockerfile/CI edits are exact.
- **Consistency:** the same `IMAGE` digest + `pip-tools==7.5.3` + `pip-compile --generate-hashes --no-header` invocation appear identically in Task 1, `scripts/lock-deps.sh`, and the CI drift step → the drift gate is comparing like with like (deterministic).
- **Risk:** if a dependency is sdist-only (no wheel), Task 1 Step 4 / the dry-run gate surfaces it deterministically (not at an opaque Docker-build failure); the plan says to source the wheel or hash-pin its build backend explicitly, never to relax `--only-binary`.
```
