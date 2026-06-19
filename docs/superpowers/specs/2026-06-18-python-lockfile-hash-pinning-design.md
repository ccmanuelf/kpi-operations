# C4 — Python lockfile + hash pinning — Design

**Status:** Approved (brainstorm 2026-06-18). PR4 robustness slate, Run-7 audit "L" (Python lockfile/hash pinning). C5 (single schema mechanism) remains deferred to MariaDB go-live; C4 is DB-independent and shipped now.

## Goal

Make Python dependency installs **reproducible** and **supply-chain tamper-resistant**: generate fully-resolved, sha256-hash-pinned lockfiles from the existing hand-curated source requirements, install them everywhere with `--require-hashes --only-binary=:all:`, and add a CI gate that fails if a lock drifts from its source. The reliability bar is a *deterministic guarantee* (wheels-only + hermetic reproducibility + a build-free verify), not a "build it and see" probe.

## Background

Current state:
- `backend/requirements.txt` — ~31 direct prod deps hand-pinned `==` with CVE annotations (some security-relevant transitives pinned too). **No hashes, no full transitive lock.**
- `backend/requirements-dev.txt` — `-r requirements.txt` + test/quality/security tooling (pytest, black, flake8, mypy, bandit, detect-secrets, pip-audit, type stubs), all `==`.
- Docker installs prod `requirements.txt` via plain `pip install` (Dockerfile:19). Base image is **tag-pinned** `python:3.11.11-slim-bookworm` (a Dockerfile comment notes it *should* be `@sha256`-digest-pinned).
- CI (`ci.yml:35`) + e2e (`e2e.yml:35`) install `requirements-dev.txt`; `pip-audit` already gates known CVEs against the installed env.

Gap: transitive deps can float (non-reproducible builds) and nothing verifies package integrity (no hashes). This is the audit's "L — Python lockfile/hash pinning."

## Scope (comprehensive + drift gate — user choice 2026-06-18)

Lockfiles for prod (Docker) AND dev (CI/e2e), installed `--require-hashes --only-binary=:all:`; a hermetic lock-drift CI gate; Docker base-image `@sha256` pin. C5 (schema mechanism) explicitly out of scope.

## Architecture

### Tool: `pip-tools`
`pip-compile --generate-hashes` — pip-native, fits the existing pip/dependabot flow with minimal new toolchain (uv considered; rejected to avoid introducing a new toolchain). Pin `pip-tools==<version>` in the dev tooling.

### Files
- **Sources (unchanged, human-edited, keep `==` pins + CVE comments — the inputs):** `backend/requirements.txt`, `backend/requirements-dev.txt`.
- **Generated, committed locks (resolved + sha256 hashes, all transitives):**
  - `backend/requirements.lock` ← compiled from `requirements.txt` (prod).
  - `backend/requirements-dev.lock` ← compiled from `requirements-dev.txt` (dev superset).
- Add `pip-tools==<version>` to `requirements-dev.txt` (so CI can compile/verify) → it flows into `requirements-dev.lock`.

### Reliability guarantee (replaces "empirical validation")
1. **Wheels-only install — `--require-hashes --only-binary=:all:`** everywhere. No sdist builds at install ⇒ no PEP-517 build backends needed ⇒ the hash-pinned set is fully self-contained. A dependency lacking a compatible wheel **fails deterministically** (at lock generation / the dry-run gate), not as a surprise build error. (For this set — cryptography, pillow, pymysql, reportlab, etc. — manylinux wheels exist; if any package genuinely lacked a wheel, it is surfaced at lock time and handled explicitly.)
2. **Hermetic, reproducible lock generation:** compile AND drift-check inside the **digest-pinned `python:3.11.11` container** (the same base Docker/CI use), so the lock is byte-reproducible and the gate is deterministic — not subject to local-env variance.
3. **Build-free verify gate:** `pip install --require-hashes --only-binary=:all: --dry-run -r <lock>` resolves, verifies every hash, and enforces wheel availability **without building/installing** — a fast gate ahead of the Docker build.

The actual `docker-build` then merely *confirms* an already-guaranteed property.

## Install wiring

- **Dockerfile:19** → `RUN pip install --no-cache-dir --require-hashes --only-binary=:all: --prefix=/usr/local -r backend/requirements.lock` (copy `requirements.lock` instead of `requirements.txt`).
- **ci.yml:35 / e2e.yml:35** → install `backend/requirements-dev.lock` with `--require-hashes --only-binary=:all:` (update `cache-dependency-path` to the lock). `pip` is still upgraded first (ci.yml:34) so it is present before the hashed install. `pip-audit` unchanged (audits the now-locked installed env).

## Lock-drift CI gate + regeneration + dependabot

- **Drift gate (new CI step, hermetic):** in the digest-pinned container, re-run `pip-compile --generate-hashes` for both sources **with the committed `*.lock` present and WITHOUT `--upgrade`** (pip-compile is *sticky* — it keeps the already-pinned versions and only changes the lock when a source constraint changed), write to temp files, and assert byte-identical to the committed locks; ALSO run the dry-run verify (#3) on both locks. So the gate fires **only on a genuine source edit that wasn't re-locked** — not when a new transitive is merely published upstream. Determinism comes from the pinned container + pinned `pip-tools` + the sticky no-upgrade recompile.
- **Regeneration:** `scripts/lock-deps.sh` (runs `pip-compile --generate-hashes --only-binary=:all:` for both sources inside the pinned container) — the single command to refresh locks.
- **Dependabot:** keeps bumping the **source** `requirements*.txt` (unchanged config). Its PRs trip the drift gate until the lock is regenerated — which fits the established **batch-and-validate** dependabot flow (regenerate the lock when batching bumps). Documented in `docs/CONTRIBUTING.md` (a short "updating dependencies" section: edit source → `scripts/lock-deps.sh` → commit both).

## Docker base-image digest pin

Resolve `python:3.11.11-slim-bookworm` → its `@sha256:…` digest and pin **both** `FROM` lines (builder + production stages) to `python:3.11.11-slim-bookworm@sha256:…`. Completes reproducibility (a tag can be re-pushed; a digest cannot). The Dockerfile comment already prescribes this.

## Verification & success criteria

- `scripts/lock-deps.sh` produces byte-identical locks on re-run (reproducible); the drift gate is green.
- `pip install --require-hashes --only-binary=:all: --dry-run` passes for both locks (no missing hash/wheel).
- `docker-build` green (image installs from the hash-pinned prod lock, wheels-only); `backend-tests` + `e2e-sqlite` green (dev lock); `pip-audit` green; `frontend-lint-and-tests` unaffected.
- Coverage/test outcomes unchanged (same resolved versions — the lock pins what was already effectively installed).
- Post-merge main CI green; Render redeploys from the locked image (boots + `/health/live` 200); local == GitHub == Render.

## Non-goals

- No dependency version CHANGES — the lock pins the *current* resolution (if pip-compile surfaces a newer compatible transitive, the source pins constrain it; any intentional bump is a separate dependabot/PR concern, not C4).
- No switch to uv/poetry; no change to the CVE-annotated source pins (they remain the source of truth).
- C5 (Alembic vs `create_all`) — deferred to MariaDB go-live.

## Delivery

One PR, sequenced commits: add pip-tools + generate both locks (hermetic) → wire Docker (lock + flags + base digest) → wire CI/e2e installs → add the drift+verify gate + `scripts/lock-deps.sh` + CONTRIBUTING note → verify. Own brainstorm→spec→plan→execute→PR→merge-on-green cycle.
