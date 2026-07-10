# KPI-Operations — PR-3: Production Deploy Artifacts (MariaDB + Caddy + gunicorn) — Design

**Date:** 2026-07-09
**Status:** Design approved (user, 2026-07-09) — pending implementation plan
**Parent:** `2026-06-26-kpi-operations-production-deployment-design.md` (PR-3 section; its locked decisions carry over). PR-1 (#128) and PR-2 (#129) are merged: the schema is MariaDB-proven and Alembic-only, the entrypoint migrates fatally, and `RUN_MIGRATIONS_ON_STARTUP=false` is the established container convention.
**Scope:** The compose stack that deploys to VM `192.168.2.234` — MariaDB service, Caddy TLS, gunicorn backend, static frontend, backup sidecar — plus a CI job that proves the exact topology. No VM host actions (PR-4).

---

## Context (verified against the codebase 2026-07-09)

- `docker-compose.prod.yml` is **vestigial**: no CI job, script, or deploy consumes it (Render uses native Docker services per `render.yaml`; `docker-build` CI builds Dockerfiles directly). Free to repurpose.
- The frontend entrypoint (`frontend/docker-entrypoint.sh`) already has three `BACKEND_URL` branches; the **empty-value branch is static-only** (no proxy, no wake-injection). The Render-critical branch (`https://…` → proxy + #127 wake-origin/CSP injection) is untouched by using the empty branch on the VM.
- Root `Dockerfile` CMD is plain uvicorn; `render.yaml` points at this Dockerfile — so the gunicorn switch must be a compose `command:` override, not a Dockerfile edit.
- Unauthenticated `GET /health/database` (`SELECT 1`, 503 on failure) already exists (`backend/routes/health.py:57-71`) and is used by nothing — it becomes the compose readiness healthcheck. `/health/live` stays liveness; auth-gated `/health/ready` stays untouched.
- gunicorn is in **no** requirements file (only a bare `pip install` mention in DEPLOYMENT.md's systemd section) — it must be added hash-pinned (`scripts/lock-deps.sh`) before anything invokes it.
- `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD` in `backend/config.py:63-67` are **dead config** — read by nothing; only `DATABASE_URL` drives connections.
- The MariaDB healthcheck command (`healthcheck.sh --connect --innodb_initialized`) is already proven in the `mariadb-portability` CI job.
- No Caddy artifacts exist anywhere — greenfield.

## Decisions (user-approved 2026-07-09)

| # | Decision | Choice |
|---|----------|--------|
| D1 | CI scope | **Compose-stack smoke job**: prove the real topology end-to-end in CI. Full-suite-on-MariaDB (needs the int-fixture cleanup + conftest parametrization) is deferred to a follow-up **PR-3b** — carry-forward list in §PR-3b below. |
| D2 | Stack location | **Repurpose `docker-compose.prod.yml`** as the real VM stack. `docker-compose.yml` stays the SQLite dev stack. DEPLOYMENT.md's "reference-only" note is replaced by real documentation. |
| D3 | Backups | **Sidecar container** in the stack: nightly `mysqldump --single-transaction --routines` → gzip → `${KPI_DATA_ROOT}/backups`, prune >14 days. Complemented by VMware snapshots (locked in parent). |

Design facts settled by exploration (no user fork): Dockerfile CMD untouched (Render safety); frontend runs the entrypoint's existing static-only branch (`BACKEND_URL=""`); Caddy is a catch-all `:443` site with `tls internal` + `:80` redirect; collation pinned via MariaDB server args (PR-2 carry-forward).

## The stack — `docker-compose.prod.yml` (five services, network `kpi-network`)

All host paths are parameterized: `${KPI_DATA_ROOT:-/opt/kpi-operations}` — the VM uses the default; CI points it at a runner temp dir.

### `db`
- Image `mariadb:11.4` **digest-pinned** (`@sha256:…`, matching the repo's base-image pinning convention).
- `command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci` — the auto-created database inherits both (closes the PR-2 collation carry-forward).
- Env: `MARIADB_DATABASE=kpi_platform`, `MARIADB_USER=kpi_user`, `MARIADB_PASSWORD=${DB_PASSWORD:?…}`, `MARIADB_ROOT_PASSWORD=${DB_ROOT_PASSWORD:?…}`.
- Volume: `${KPI_DATA_ROOT}/mariadb-data:/var/lib/mysql` (bind mount — native-grade durability per locked decision).
- Healthcheck: `healthcheck.sh --connect --innodb_initialized` (10s interval, retries sized for first-boot init).
- **No `ports:`** — 3306 is reachable only on the compose network.

### `backend`
- Same image/build as today. `command:` override: `gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000` (worker count 4 per parent spec; Dockerfile CMD remains uvicorn so Render is untouched). The entrypoint still runs first (DB wait → fatal `alembic upgrade head`).
- Env: `DATABASE_URL=mysql+pymysql://kpi_user:${DB_PASSWORD}@db:3306/kpi_platform`, `SECRET_KEY=${SECRET_KEY:?…}`, `DEMO_MODE=${DEMO_MODE:-false}`, `RUN_MIGRATIONS=true`, `RUN_MIGRATIONS_ON_STARTUP=false`, `CORS_ORIGINS=${CORS_ORIGINS:?…}`, `ENVIRONMENT=production`.
- `depends_on: db: condition: service_healthy` (avoids racing MariaDB first-boot init).
- Compose healthcheck: `curl -f http://localhost:8000/health/database` (readiness incl. DB ping); image HEALTHCHECK (`/health/live`) remains liveness.
- Volumes: `${KPI_DATA_ROOT}/{uploads,reports,logs}` bind mounts (no database volume — the DB lives in MariaDB now).
- **gunicorn added to `backend/requirements.txt` + hash-pinned locks via `scripts/lock-deps.sh`** (no other version changes).

### `caddy`
- Image `caddy:2` digest-pinned; host ports `443:443` and `80:80` (frontend's old `80:80` publication removed).
- Config: new **`deploy/caddy/Caddyfile`** (mounted read-only):
  - catch-all `:443` site, `tls internal` (internal CA, auto-issue/rotate);
  - `handle /api/capacity/*` → `reverse_proxy backend:8000` with 120s read/write timeouts (moves here from nginx);
  - `handle /api/*` and `handle /health/*` → `reverse_proxy backend:8000` (default timeouts);
  - `handle` (fallback) → `reverse_proxy frontend:80`;
  - `:80` → permanent redirect to https.
- Volumes: `${KPI_DATA_ROOT}/caddy/data:/data`, `${KPI_DATA_ROOT}/caddy/config:/config` (CA + cert persistence). The root CA cert (`/data/caddy/pki/authorities/local/root.crt`) is what PR-4 distributes to client machines.

### `frontend`
- Same image. `BACKEND_URL=""` → the entrypoint's existing static-only branch (no `/api` proxy, no wake-injection, CSP placeholder resolves with no extra origins). No host ports (Caddy fronts it). Healthcheck unchanged (`wget --spider http://localhost:80`).
- **No frontend code changes.** The Render path (proxy + wake-injection) is preserved bit-for-bit.

### `backup` (sidecar)
- Image: same digest-pinned `mariadb:11.4` (client tools included). Runs new **`deploy/backup/backup-loop.sh`** (mounted): loop — sleep until 02:00 local, `mysqldump --single-transaction --routines --events -h db -u root -p"$DB_ROOT_PASSWORD" kpi_platform | gzip > ${stamp}.sql.gz` into `/backups`, prune files older than 14 days, repeat. Writes to `${KPI_DATA_ROOT}/backups`. The script accepts `--once` (single dump+prune cycle, then exit) — that is what CI invokes via `docker compose exec backup /backup-loop.sh --once`.
- `depends_on: db: service_healthy`. Restart policy `unless-stopped` (like the rest of the stack).

### Secrets scaffold
- New committed **`.env.prod.example`**: `SECRET_KEY` (32+ chars, generation command), `DB_PASSWORD`, `DB_ROOT_PASSWORD`, `CORS_ORIGINS` (comma list; example `https://192.168.2.234` with a comment noting the future Luna-agent origin is appended here), optional `KPI_DATA_ROOT`/`DEMO_MODE` overrides. The real `.env` lives only on the VM (never committed) and is validated by `validate_production_config` at boot.

## CI — `compose-stack-smoke` job (additive)

Steps: checkout → create `$RUNNER_TEMP/kpi/{mariadb-data,backups,uploads,reports,logs,caddy}` → write a CI `.env` (throwaway credentials, allowlist-pragma'd) → `docker compose -f docker-compose.prod.yml up -d --build` with `KPI_DATA_ROOT=$RUNNER_TEMP/kpi` and **`DEMO_MODE=true`** (a fresh prod DB has no users until PR-4's `create_admin.py`; demo mode also makes this the first CI exercise of the **full demo seeder on InnoDB**) → wait for backend healthy → proof sequence, all through Caddy TLS (`curl -k` against `https://localhost`, or trusting the exported root CA):
1. `GET /health/database` → exactly 200.
2. `POST /api/auth/login` admin/admin123 → token.
3. One authenticated write → 200/201, then read it back.
4. `docker compose restart backend` → data still present (bind-mount durability through the real topology).
5. Trigger one backup cycle (run the sidecar's dump function once directly), assert a non-empty `.sql.gz` exists, and restore it into a scratch database (`mysql < dump`) asserting table count > 0.
6. `docker compose logs backend` asserts the entrypoint ran Alembic and the lifespan skipped (`RUN_MIGRATIONS_ON_STARTUP disabled`).
- Job is additive; the 4 required checks + `mariadb-portability` are untouched. Compose config is also statically validated (`docker compose -f docker-compose.prod.yml config -q`) in the job before `up`.

## Cleanups riding along
- Remove dead `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD` from `backend/config.py` and both `.env.example` files (read by nothing; misleading next to the compose work). Grep-verified before removal; suite green after.
- `docs/DEPLOYMENT.md`: the "compose files run the SQLite demo / MariaDB example is reference-only" note (lines ~7-12) and the §Docker section are rewritten to document the real stack (env vars, first boot, backup/restore, CA cert location). The systemd/gunicorn alternative section stays (it legitimately keeps `RUN_MIGRATIONS_ON_STARTUP=true`).

## Risks & mitigations
- **Smoke-job wall-clock** (two image builds + stack up): bounded by GH Actions build cache (`docker/build-push-action` cache or plain layer cache); job is additive and not branch-protection-required until proven stable.
- **Caddy internal CA in CI**: use `curl -k` for the smoke (trust boundary is the compose network in CI); the CA-trust procedure for real clients is PR-4 runbook material.
- **MariaDB first boot** is slow (init + tz tables): healthcheck retries ≥ 15 × 10s; `depends_on: service_healthy` shields the backend entrypoint.
- **Render regression risk ≈ 0 by construction**: no Dockerfile, entrypoint, nginx, or render.yaml changes; the only shared file touched is `requirements.lock` (+gunicorn, installed but unused on Render).

## Verification (definition of done)
- `docker compose -f docker-compose.prod.yml config -q` clean; all 6 existing CI checks green; new `compose-stack-smoke` green with the full proof sequence.
- Backend suite green, coverage ≥75% (config.py cleanup shifts nothing material); frontend untouched (suite green as-is).
- Local run of the stack (docker desktop) reproduces the smoke sequence.
- Cross-review + `/code-review` per repo gates; PR merges on green; Render post-merge verify (deploy live, health, login) confirms zero demo impact.

## PR-3b (follow-up, separate PR — carry-forward inventory)
Full backend suite on MariaDB in CI: parametrize the conftest template/clone mechanism for a MariaDB service container, fix the int-user-id fixtures (`test_line_id_filtering.py:248,322`, `test_multi_tenant_isolation.py:207,219,267,302,314`, `test_aggregators.py:58`, `conftest.py:224`, `test_critical_services.py:650,687-688`), and decide skip-vs-run for SQLite-specific tests. Optional: always-on `rebuild_schema` unit test.

## Out of scope
- PR-4: VM bootstrap (`vm-bootstrap.sh`, Docker CE install w/ Ubuntu 26.04 fallback, ufw 22/443, `/opt/kpi-operations` dirs, `.env` scaffold on host), `scripts/create_admin.py`, deploy runbook (incl. CA distribution + the user hard-delete FK note), VMware snapshot cadence.
- Luna-agent origin (CORS list is ready to append).
