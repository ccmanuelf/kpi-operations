# KPI-Operations — Production Deployment to VM Linux (MariaDB) — Design

**Date:** 2026-06-26
**Status:** Design approved — pending spec review → implementation plan
**Scope:** KPI-operations only. The sibling projects (Luna agent / superprompt, Novalink-Bridge) deploy from their own repos in their own sessions; this effort does not touch them.

---

## Context

KPI-operations is now considered robust enough to release to a small group of real users in production. Two VMware VMs have been provisioned as production servers; KPI-operations targets the **Linux VM `192.168.2.234`** (SSH `manuel@…`, key-auth working; we are co-administrators). Today it runs on SQLite (ephemeral demo on Render free tier). Production requires a server-grade read-write database, a single schema-evolution mechanism, secrets injection, TLS, and a non-hibernating self-hosted host.

This is "production deployment **#1**" of the broader platform. Within the platform vision, only **Luna agent** (via APIs) and **UI users** consume KPI-operations; KPI-operations owns its own production-control DB and never writes to NovaLink's upstream production systems.

### Verified environment (VM `192.168.2.234`)
- Ubuntu **26.04 LTS** (codename `resolute`), x86_64, VMware VM.
- **8 cores / 30 GiB RAM / 98 GB disk (59 GB free)** — ample for the full Docker stack incl. containerized DB.
- **Docker not installed**; `sudo` requires a password (not passwordless); only port 22 listening; no existing MariaDB/MySQL.
- Hostname is `novalink-bridge` (the box was named for the bridge) — **confirmed by the user as the KPI-operations host**; the bridge may co-locate here later, reinforcing clean isolation.

---

## Locked decisions

| # | Decision | Choice |
|---|----------|--------|
| DB engine | MariaDB vs Postgres | **MariaDB** — the only server engine the code supports today (full provider/dialect already built; `pymysql` pinned; Postgres explicitly unimplemented, `db/factory.py:120`). Also matches NovaLink's existing MariaDB ops. |
| MariaDB hosting | container vs native | **Containerized** in the Compose stack, **data on a host bind-mount** (`/opt/kpi-operations/mariadb-data:/var/lib/mysql`) + nightly `mysqldump` + VMware snapshots. Reproducible & isolated with native-grade durability. |
| TLS | nginx vs Caddy | **Caddy** reverse proxy with its **internal CA** (auto-issue/rotate). Robust cert lifecycle and **consistent with the Luna-agent deployment** on the MacBook Pro. |
| Access model | — | HTTPS over the LAN now; topology must allow future VPN/VNC/home access without rework. |
| Initial data | fresh vs migrate | **Fresh start** — empty schema, `DEMO_MODE=false`, real admin + small user group created post-deploy. |
| Schema mechanism (C5) | collapse now vs defer | **Full collapse to Alembic now** — gate #1. Startup stops calling `create_all`; Alembic is the single source of truth. |
| Test schema source | create_all+gate vs Alembic | **Alembic builds the test schema** (not `create_all`), implemented as a **session-scoped Alembic build + per-test transactional rollback** for fidelity without per-test cost. |
| Runtime migration API | keep vs remove | **Remove** the schema/data-mutating endpoints in `routes/database_config.py` — no runtime schema mutation in prod; least privilege, single source of truth. |

---

## Target architecture

```
                 LAN  /  (later) VPN · VNC
                          │  HTTPS :443
                          ▼
   ┌──────────────────────────────────────────────────────────┐  docker-compose.prod.yml
   │  caddy   :443  TLS (internal CA)                             │
   │       ├─ /api/*  → backend:8000   (direct; 120s for capacity)│
   │       └─ /*      → frontend:80    (static SPA, try_files)     │
   │  frontend (nginx) :80   static SPA only (no /api proxy)       │
   │  backend (gunicorn + UvicornWorker, 4 workers)               │
   │       │ mysql+pymysql://kpi_user:***@db:3306/kpi_platform     │
   │  db (mariadb, sha-pinned)                                     │
   │       └─ /var/lib/mysql  ⇄  host bind-mount                   │
   └──────────────────────────────────────────────────────────┘
   host: /opt/kpi-operations/{mariadb-data, backups, uploads, reports, logs, caddy}
   nightly mysqldump → backups/   +   VMware snapshots
   ufw: allow 22, 443 only.  3306 NOT published to host (Docker network only).
```

- **Migrations run once in the backend entrypoint** (`alembic upgrade head`) before gunicorn workers start — avoids multi-worker races.
- Caddy terminates TLS; its root cert is distributed to client machines (or accepted on first use). Frontend nginx stays HTTP-only behind Caddy (keeps its existing `/api` proxy + CSP).

---

## Implementation sequence (small, merge-on-green PRs)

### PR-1 — MariaDB portability fixes (small, low-risk, independently verifiable)
- **Blocker:** `backend/orm/user.py:62` `client_id_assigned: mapped_column(Text, index=True)` → `String(50), index=True` (MariaDB cannot index a `TEXT` column without a prefix length). Match the `String(50)` convention used by other client-id columns; verify length against `client.id`.
- `backend/db/providers/mariadb.py`: enforce `charset=utf8mb4` (+ `utf8mb4_unicode_ci`) like the MySQL provider already does.
- Verify all `JSON` columns round-trip on real MariaDB: `orm/event_store.py`, `orm/simulation_scenario.py`, `orm/capacity/scenario.py`, `orm/capacity/schedule.py`, `orm/alert.py`.

### PR-2 — C5: collapse schema evolution to Alembic (the big one, gate #1)
- **Real baseline migration:** replace the no-op `backend/alembic/versions/001_baseline.py` with a full autogenerated baseline (`alembic revision --autogenerate` against a fresh DB), asserted equal to `Base.metadata`. Must render correctly for both SQLite (`render_as_batch`) and MariaDB.
- **Stop `create_all` at startup:** remove `init_schema()`'s `Base.metadata.create_all` and the redundant `create_capacity_tables()` from `backend/bootstrap/lifecycle.py` (lines ~120-129, ~181-183). Run `alembic upgrade head` from the **backend entrypoint** (`backend/scripts/docker-entrypoint.sh`) once before workers start.
- **Remove dead schema paths:** orphaned `backend/db/migrations/phase2_junction_tables.sql` (those junction tables already exist as ORM models) and the now-redundant `capacity_planning_tables.py` create path.
- **Tests onto Alembic:** rework `backend/tests/conftest.py` to build the schema via `command.upgrade(cfg, "head")` **once per session**, with each test wrapped in a transaction/SAVEPOINT rolled back on teardown (replaces the function-scoped `create_all`). Alembic — never `create_all` — is the test schema source.
- **Remove runtime migration API:** delete/strip the schema- and data-mutating endpoints in `backend/routes/database_config.py` (the `SchemaInitializer` / `DataMigrator` triggers). Audit for any genuinely read-only diagnostics to retain.

### PR-3 — Production deployment artifacts
- **Add `db` (MariaDB) service** to `docker-compose.prod.yml`: sha-pinned `mariadb:11.4-lts`, `MARIADB_*`/`MYSQL_*` from env, **bind-mount** `/opt/kpi-operations/mariadb-data:/var/lib/mysql`, healthcheck (`healthcheck.sh --connect --innodb_initialized`), `backend depends_on db (service_healthy)`. **Do not publish 3306 to the host.**
- **Add `caddy` service:** TLS termination with internal CA; **path-routes `/api/*` → backend:8000 directly** and `/*` → frontend:80 (static SPA). The capacity 120s upstream timeout moves into the Caddyfile; the frontend nginx is simplified to a **static-only** server (its runtime `/api` proxy / `upstream.inc` logic is removed). Mount `/opt/kpi-operations/caddy` for cert/data persistence. Publish `:443` (+ `:80` redirect).
- **Backend → gunicorn + UvicornWorker (4 workers)** for concurrency (per `docs/DEPLOYMENT.md`); `DATABASE_URL=mysql+pymysql://…`, `DEMO_MODE=false`.
- **Backups:** nightly `mysqldump` (host cron or sidecar) → `/opt/kpi-operations/backups`, with rotation.
- **Health probes:** liveness `/health/live` (unauth), readiness `/health/database` (unauth, `SELECT 1`); leave auth-gated `/health/ready` untouched.
- `CORS_ORIGINS` set to the HTTPS frontend origin; structured so the Luna-agent origin can be appended later without rework.

### PR-4 — Host bootstrap + deploy runbook (sudo-gated ops)
- `scripts/vm-bootstrap.sh` (reproducible/audit artifact; run by a co-admin with sudo, confirming before each privileged step):
  - Install **Docker CE** — **verify Ubuntu 26.04/`resolute` has an apt channel; fall back to the convenience script or the `noble` channel** if not.
  - Add `manuel` to the `docker` group (enables sudo-free day-to-day ops).
  - `ufw`: allow 22 + 443 only.
  - Create `/opt/kpi-operations/{mariadb-data,backups,uploads,reports,logs,caddy}`.
  - Scaffold production `.env` (operator fills `SECRET_KEY` (32+), `DB_PASSWORD`, DB root password); Caddy manages its own CA cert.
- Deploy: clone repo on the VM → `docker compose -f docker-compose.prod.yml build && up -d`.
- **First admin:** `scripts/create_admin.py` management command (see Gaps) creates the first admin under `DEMO_MODE=false`; the small user group is then created via the existing admin UI.

---

## New gaps surfaced (folded into scope)
- **No first-admin path with `DEMO_MODE=false`.** The register endpoint is demo-only/operator-only post-hardening, so a fresh prod DB has no way to mint the first admin. → add `scripts/create_admin.py`.
- **CI runs backend tests on SQLite only.** To actually prove MariaDB correctness, add a **MariaDB service-container CI job** (reuse the novalink-bridge CI pattern) that runs the Alembic baseline + the suite (or a smoke subset) on real MariaDB.

---

## Risks & mitigations
- **C5 is the highest-risk change.** The Alembic baseline must exactly reproduce the schema, and the test-infra rework is non-trivial. Guards: autogenerated baseline asserted == `Base.metadata`, the new MariaDB CI job, and full local==CI verification before merge.
- **Data durability of containerized DB.** Mitigated by host bind-mount + nightly dumps + VMware snapshots; never run `compose down -v` in prod.
- **Ubuntu 26.04 Docker availability.** Verify repo support during bootstrap; documented fallback.
- **Secrets handling.** Production `.env` lives only on the VM (never committed); validated via `backend.config.validate_production_config(raise_on_critical=True)`.

## Verification (definition of done)
- All 4 required CI checks green (`backend-tests`, `frontend-lint-and-tests`, `docker-build`, `e2e-sqlite`) + the new MariaDB job; cross-review gate satisfied per PR.
- Coverage gate ≥75% maintained.
- End-to-end smoke on the VM: `/health/live` 200, `/health/database` 200, HTTPS login via Caddy, one write transaction persists, data survives `compose down && up`.
- Backup: a `mysqldump` artifact is produced and a restore is test-validated.

## Out of scope (separate efforts / sessions)
- Luna-agent integration, the Novalink-Bridge deployment, and cross-project networking/auth. (Only forward-compat hook here: `CORS_ORIGINS` extensibility.)
