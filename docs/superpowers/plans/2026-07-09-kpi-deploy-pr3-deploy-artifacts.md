# PR-3: Production Deploy Artifacts (MariaDB + Caddy + gunicorn) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the compose stack that deploys to the VM — MariaDB 11.4 + Caddy internal-CA TLS + gunicorn backend + static frontend + backup sidecar — proven end-to-end by a CI smoke job, with zero Render-demo impact.

**Architecture:** `docker-compose.prod.yml` (vestigial today) becomes the real 5-service VM stack, parameterized by `KPI_DATA_ROOT` so CI runs the identical topology in a runner temp dir. New static assets live under `deploy/` (Caddyfile, backup loop, smoke script); the smoke script is shared by local verification and the new CI job. The backend image is untouched except for gunicorn entering the hash-pinned lockfile; the gunicorn switch is a compose `command:` override so Render's Dockerfile-CMD path is untouched.

**Tech Stack:** Docker Compose v2, MariaDB 11.4, Caddy 2, gunicorn + UvicornWorker, bash, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-07-09-kpi-deploy-pr3-deploy-artifacts-design.md` (decisions D1–D3 locked).

## Global Constraints

- Zero Render impact: do NOT touch `Dockerfile` CMD, `frontend/Dockerfile`, `frontend/docker-entrypoint.sh`, `frontend/nginx.conf`, or `render.yaml`.
- `db` service: NO `ports:` mapping (3306 never reaches the host). Collation pinned via server args `--character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci`.
- All images digest-pinned (`image: name:tag@sha256:...`) matching the repo convention; resolve current digests at implementation time via `docker pull <ref> && docker inspect --format='{{index .RepoDigests 0}}' <ref>`.
- gunicorn only via hash-pinned lock (`scripts/lock-deps.sh`); never a bare pip install. No other dependency versions change.
- Backend suite green, coverage ≥75%; `black --check .`/`flake8 .` (backend/), `mypy backend --ignore-missing-imports` (root); pre-commit clean, never `--no-verify`.
- No permissive assertions in any test (`in [...]` forbidden).
- The 4 required CI checks + `mariadb-portability` + `tooling-tests` stay green; `compose-stack-smoke` is additive.
- detect-secrets: CI-only throwaway credentials in workflow/scripts carry `# pragma: allowlist secret`.
- Cross-review gate before `gh pr create`/`merge`.
- Shell scripts pass `bash -n`; new tooling shell tests follow the existing `scripts/tests/` pattern (they run in the `tooling-tests` CI job).

---

### Task 1: gunicorn into the hash-pinned lockfile

**Files:**
- Modify: `backend/requirements.txt` (append)
- Modify: `backend/requirements.lock`, `backend/requirements-dev.lock` (regenerated — never hand-edited)

**Interfaces:**
- Produces: `gunicorn` importable in the production image; Task 5's compose `command:` relies on `gunicorn` + `uvicorn.workers.UvicornWorker` both present.

- [ ] **Step 1: Append to `backend/requirements.txt`**

After the `simpy==4.1.2` line add:

```
# Production WSGI/ASGI process manager (VM compose stack; Render stays on plain uvicorn)
gunicorn==23.0.0
```

(If pip-compile reports the version doesn't exist, pin the current stable from PyPI instead and note it in the report.)

- [ ] **Step 2: Regenerate locks hermetically**

Run: `bash scripts/lock-deps.sh`
Expected: "Regenerated backend/requirements.lock + backend/requirements-dev.lock"; `git diff --stat` shows only the two lock files + requirements.txt.

- [ ] **Step 3: Verify the lock**

Run: `grep -A2 "^gunicorn==" backend/requirements.lock | head -5`
Expected: `gunicorn==23.0.0 \` followed by `--hash=sha256:...` lines.

- [ ] **Step 4: Verify the image builds and imports it**

```bash
docker build -t kpi-backend-pr3 .
docker run --rm kpi-backend-pr3 python -c "import gunicorn, uvicorn.workers; print(gunicorn.__version__)"
```
Expected: prints `23.0.0` (or the pinned version), exit 0.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/requirements.lock backend/requirements-dev.lock
git commit -m "build(deps): hash-pin gunicorn for the VM compose stack"
```

---

### Task 2: Remove dead DB_* config fields

**Files:**
- Modify: `backend/config.py:63-67` (fields) and `:209-215` (the one reader — a validation block on the dead field)
- Modify: `.env.example:35-41`, `backend/.env.example:6-10`
- Test: existing config tests (locate: `grep -rln "DB_PASSWORD\|validate_production_config" backend/tests/`)

**Interfaces:**
- Produces: `Settings` no longer has `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`. Only `DATABASE_URL` drives connections (already true at runtime). `model_config` has `extra="ignore"`, so compose-level `DB_PASSWORD` env vars reaching a container are harmlessly ignored.

- [ ] **Step 1: Find and update tests pinning the dead validation**

Run: `grep -rn "DB_PASSWORD" backend/tests/`
For each hit that pins the `Default database password detected` validation, DELETE that test case (the check validated a field that never drove connections; the real check — default password embedded in `DATABASE_URL`, config.py:239-249 — stays and keeps its tests). Report every test removed.

- [ ] **Step 2: Remove the fields and their validation block**

In `backend/config.py` delete lines 63-67:

```python
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "kpi_platform"
    DB_USER: str = "kpi_user"
    DB_PASSWORD: str = ""
```

and the block at 209-215:

```python
    # Check database password security
    if settings.DB_PASSWORD in DEFAULT_INSECURE_VALUES:
        if is_production:
            result.errors.append("CRITICAL: Default database password detected in production!")
            result.is_valid = False
        else:
            result.warnings.append("WARNING: Using default database password. Change before production.")
```

(Keep `DEFAULT_INSECURE_VALUES` — the DATABASE_URL check at :239-249 still uses it.)

- [ ] **Step 3: Update both .env.example files**

In root `.env.example`, replace the block (lines ~35-41: the "When switching to MariaDB..." comment + five `DB_*` lines) with:

```
# For MariaDB, set DATABASE_URL to a mysql+pymysql:// URI, e.g.:
#   DATABASE_URL=mysql+pymysql://kpi_user:CHANGE_ME@localhost:3306/kpi_platform  # pragma: allowlist secret
# (The VM compose stack builds this from .env.prod values — see .env.prod.example.)
```

In `backend/.env.example`, delete lines 6-10 (the five `DB_*` lines) and add the same 2-line comment after the `DATABASE_URL` entry.

- [ ] **Step 4: Run the suite**

Run: `cd backend && pytest tests/ 2>&1 | tail -3 && flake8 config.py`
Expected: green, coverage ≥75%, flake8 clean.

- [ ] **Step 5: Commit**

```bash
git add backend/config.py .env.example backend/.env.example backend/tests/
git commit -m "refactor(config): remove dead DB_* fields — DATABASE_URL is the single connection source"
```

---

### Task 3: Caddyfile

**Files:**
- Create: `deploy/caddy/Caddyfile`

**Interfaces:**
- Produces: the config Task 5 mounts at `/etc/caddy/Caddyfile`. Routes: `/api/capacity/*` → backend (120s), `/api/*` + `/health/*` → backend, fallback → frontend; `:80` → https redirect; internal CA.

- [ ] **Step 1: Write `deploy/caddy/Caddyfile`**

```
# KPI Operations — VM edge (TLS termination, path routing).
# Internal CA: Caddy self-manages a local root cert at
# /data/caddy/pki/authorities/local/root.crt — PR-4's runbook distributes it
# to client machines. Data persists via the ${KPI_DATA_ROOT}/caddy volumes.

{
	# LAN deployment: no public ACME; issue from the internal CA.
	local_certs
}

:443 {
	tls internal

	# Capacity endpoints run long analyses — extended upstream timeout
	# (moved here from the frontend nginx proxy, which the VM topology bypasses).
	handle /api/capacity/* {
		reverse_proxy backend:8000 {
			transport http {
				response_header_timeout 120s
			}
		}
	}

	# All other API + health probes go straight to the backend.
	handle /api/* {
		reverse_proxy backend:8000
	}
	handle /health/* {
		reverse_proxy backend:8000
	}

	# Everything else: the static SPA (nginx, static-only branch).
	handle {
		reverse_proxy frontend:80
	}
}

:80 {
	redir https://{host}{uri} permanent
}
```

- [ ] **Step 2: Validate with the real Caddy image**

```bash
CADDY_REF=$(docker pull caddy:2 >/dev/null && docker inspect --format='{{index .RepoDigests 0}}' caddy:2)
echo "$CADDY_REF"  # record for Task 5
docker run --rm -v "$PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 caddy validate --config /etc/caddy/Caddyfile
```
Expected: `Valid configuration` (exit 0). Record the digest for Task 5.

- [ ] **Step 3: Commit**

```bash
git add deploy/caddy/Caddyfile
git commit -m "feat(deploy): Caddyfile — internal-CA TLS, /api+/health→backend (120s capacity), /*→frontend"
```

---

### Task 4: Backup sidecar script + tooling test

**Files:**
- Create: `deploy/backup/backup-loop.sh`
- Test: `scripts/tests/test_backup_loop.sh` (follows the existing `scripts/tests/` pattern; runs in the `tooling-tests` CI job — read one existing test there first and match its harness/assert style)

**Interfaces:**
- Produces: `backup-loop.sh` — env: `DB_ROOT_PASSWORD` (required), `BACKUP_DIR` (default `/backups`), `DB_HOST` (default `db`), `DB_NAME` (default `kpi_platform`), `RETENTION_DAYS` (default `14`), `BACKUP_HOUR` (default `02`). Flag: `--once` = single dump+prune then exit 0. Task 5 mounts it; the smoke script (Task 6) calls `--once`.

- [ ] **Step 1: Write the failing tooling test**

`scripts/tests/test_backup_loop.sh` (adapt the header/assert helpers to match the existing tests in that directory):

```bash
#!/usr/bin/env bash
# backup-loop.sh contract: --once produces a pruned, gzipped dump using the
# mysqldump on PATH; retention removes old files. Stubs mysqldump so the test
# is hermetic (no DB needed).
set -euo pipefail
SCRIPT="$(git rev-parse --show-toplevel)/deploy/backup/backup-loop.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/backups"

# Stub mysqldump: emits deterministic SQL, records its args.
cat > "$TMP/bin/mysqldump" <<'EOF'
#!/usr/bin/env bash
echo "$@" > "$(dirname "$0")/mysqldump.args"
echo "-- fake dump: CREATE TABLE x (id int);"
EOF
chmod +x "$TMP/bin/mysqldump"

# An old backup that must be pruned (15 days) and a fresh one that must survive.
touch -d "15 days ago" "$TMP/backups/kpi_platform-old.sql.gz" 2>/dev/null \
  || touch -t "$(date -v-15d +%Y%m%d0000)" "$TMP/backups/kpi_platform-old.sql.gz"  # macOS fallback
touch "$TMP/backups/kpi_platform-fresh.sql.gz"

PATH="$TMP/bin:$PATH" DB_ROOT_PASSWORD=stub BACKUP_DIR="$TMP/backups" RETENTION_DAYS=14 \
  bash "$SCRIPT" --once

new_dump=$(ls "$TMP/backups"/kpi_platform-2*.sql.gz 2>/dev/null | head -1)
[ -n "$new_dump" ] || { echo "FAIL: no timestamped dump produced"; exit 1; }
gzip -t "$new_dump" || { echo "FAIL: dump is not valid gzip"; exit 1; }
zcat < "$new_dump" | grep -q "fake dump" || { echo "FAIL: dump content missing"; exit 1; }
grep -q -- "--single-transaction" "$TMP/bin/mysqldump.args" || { echo "FAIL: --single-transaction not passed"; exit 1; }
[ ! -f "$TMP/backups/kpi_platform-old.sql.gz" ] || { echo "FAIL: old backup not pruned"; exit 1; }
[ -f "$TMP/backups/kpi_platform-fresh.sql.gz" ] || { echo "FAIL: fresh backup wrongly pruned"; exit 1; }
echo "PASS: backup-loop --once contract"
```

- [ ] **Step 2: Run it — must fail (script doesn't exist)**

Run: `bash scripts/tests/test_backup_loop.sh`
Expected: FAIL (backup-loop.sh not found).

- [ ] **Step 3: Write `deploy/backup/backup-loop.sh`**

```bash
#!/usr/bin/env bash
# Nightly mysqldump sidecar for the KPI VM stack (docker-compose.prod.yml).
#   default: loop — sleep until BACKUP_HOUR (02:00), dump, prune, repeat.
#   --once : single dump + prune cycle, then exit (CI smoke / manual runs).
# Complemented by VMware snapshots; never a replacement for them.
set -euo pipefail

: "${DB_ROOT_PASSWORD:?DB_ROOT_PASSWORD is required}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
DB_HOST="${DB_HOST:-db}"
DB_NAME="${DB_NAME:-kpi_platform}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
BACKUP_HOUR="${BACKUP_HOUR:-02}"

dump_once() {
    local stamp file
    stamp=$(date +%Y%m%d-%H%M%S)
    file="$BACKUP_DIR/${DB_NAME}-${stamp}.sql.gz"
    echo "[backup] dumping ${DB_NAME} -> ${file}"
    mysqldump --single-transaction --routines --events \
        -h "$DB_HOST" -u root -p"$DB_ROOT_PASSWORD" "$DB_NAME" | gzip > "$file"
    echo "[backup] pruning dumps older than ${RETENTION_DAYS} days"
    find "$BACKUP_DIR" -name "${DB_NAME}-*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
    echo "[backup] done: $(ls -lh "$file" | awk '{print $5}')"
}

if [ "${1:-}" = "--once" ]; then
    dump_once
    exit 0
fi

echo "[backup] nightly loop armed (hour=${BACKUP_HOUR}, retention=${RETENTION_DAYS}d)"
while true; do
    now_h=$(date +%H)
    if [ "$now_h" = "$BACKUP_HOUR" ]; then
        dump_once
        sleep 3600  # skip past the backup hour
    fi
    sleep 300
done
```

- [ ] **Step 4: Run the test — must pass; syntax-check both**

Run: `bash -n deploy/backup/backup-loop.sh && bash scripts/tests/test_backup_loop.sh`
Expected: `PASS: backup-loop --once contract`.

- [ ] **Step 5: Verify tooling-tests discovery**

Read how `.github/workflows/ci.yml`'s `tooling-tests` job enumerates `scripts/tests/*` (it globs the directory — confirm the new file's name matches the glob and it is executable if the glob requires it: `chmod +x scripts/tests/test_backup_loop.sh` to match siblings).

- [ ] **Step 6: Commit**

```bash
git add deploy/backup/backup-loop.sh scripts/tests/test_backup_loop.sh
git commit -m "feat(deploy): nightly mysqldump backup sidecar script (+ hermetic tooling test)"
```

---

### Task 5: `docker-compose.prod.yml` — the real VM stack + `.env.prod.example`

**Files:**
- Modify: `docker-compose.prod.yml` (full rewrite below)
- Create: `.env.prod.example`

**Interfaces:**
- Consumes: `deploy/caddy/Caddyfile` (Task 3), `deploy/backup/backup-loop.sh` (Task 4), gunicorn in the image (Task 1).
- Produces: the stack Tasks 6-7 run. Env contract (from `.env`): `SECRET_KEY`, `DB_PASSWORD`, `DB_ROOT_PASSWORD`, `CORS_ORIGINS` (required); `KPI_DATA_ROOT` (default `/opt/kpi-operations`), `DEMO_MODE` (default `false`).

- [ ] **Step 1: Resolve digests**

```bash
docker pull mariadb:11.4 && docker inspect --format='{{index .RepoDigests 0}}' mariadb:11.4
docker pull caddy:2 && docker inspect --format='{{index .RepoDigests 0}}' caddy:2
```
Record both full `name@sha256:...` refs; substitute them for the `<MARIADB_DIGEST>`/`<CADDY_DIGEST>` placeholders below (these two placeholders are the ONLY permitted substitutions).

- [ ] **Step 2: Replace `docker-compose.prod.yml` in full**

```yaml
# Production Docker Compose — the KPI Operations VM stack (192.168.2.234).
# Usage (on the VM):  docker compose -f docker-compose.prod.yml up -d --build
# Host paths parameterize via KPI_DATA_ROOT (default /opt/kpi-operations) so the
# CI smoke job (compose-stack-smoke) can run this exact file in a temp dir.
# Secrets come from .env (see .env.prod.example); never commit a real .env.

services:
  db:
    image: <MARIADB_DIGEST>  # mariadb:11.4, digest-pinned
    container_name: kpi-db
    # Pin server charset/collation so the auto-created database inherits them
    # (PR-2 carry-forward: collation must not depend on image defaults).
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
    environment:
      - MARIADB_DATABASE=kpi_platform
      - MARIADB_USER=kpi_user
      - MARIADB_PASSWORD=${DB_PASSWORD:?DB_PASSWORD must be set (see .env.prod.example)}
      - MARIADB_ROOT_PASSWORD=${DB_ROOT_PASSWORD:?DB_ROOT_PASSWORD must be set (see .env.prod.example)}
    volumes:
      # Bind mount (not a named volume): native-grade durability + direct host
      # access for VMware snapshots and offline copies.
      - ${KPI_DATA_ROOT:-/opt/kpi-operations}/mariadb-data:/var/lib/mysql
    # NO ports: 3306 is reachable only on kpi-network, never from the host/LAN.
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 18          # first boot initializes the datadir — allow ~3 min
      start_period: 30s
    networks:
      - kpi-network

  backend:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    container_name: kpi-backend
    # gunicorn override lives HERE (not in the Dockerfile) so Render's plain
    # uvicorn CMD is untouched. The entrypoint still runs first:
    # DB wait -> fatal `alembic upgrade head` -> exec this command.
    command: ["gunicorn", "backend.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
    environment:
      - DATABASE_URL=mysql+pymysql://kpi_user:${DB_PASSWORD}@db:3306/kpi_platform
      - SECRET_KEY=${SECRET_KEY:?SECRET_KEY must be set in production}
      - ALGORITHM=${ALGORITHM:-HS256}
      - ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES:-30}
      - CORS_ORIGINS=${CORS_ORIGINS:?CORS_ORIGINS must be set (comma list, e.g. https://192.168.2.234)}
      - ENVIRONMENT=production
      - DEBUG=false
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - DEMO_MODE=${DEMO_MODE:-false}
      - RUN_MIGRATIONS=true
      # The entrypoint owns migrations (once, before the 4 workers start) —
      # the in-process startup migration stays off in every container deploy.
      - RUN_MIGRATIONS_ON_STARTUP=false
    volumes:
      - ${KPI_DATA_ROOT:-/opt/kpi-operations}/uploads:/app/uploads
      - ${KPI_DATA_ROOT:-/opt/kpi-operations}/reports:/app/reports
      - ${KPI_DATA_ROOT:-/opt/kpi-operations}/logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      # Readiness incl. DB ping (unauthenticated SELECT 1). The image's own
      # HEALTHCHECK (/health/live) remains the liveness probe.
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/database"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 45s
    networks:
      - kpi-network
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          memory: 512M

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: production
      args:
        - VITE_API_URL=${VITE_API_URL:-/api}
    container_name: kpi-frontend
    # No host ports — Caddy fronts it. BACKEND_URL empty selects the
    # entrypoint's static-only branch (no /api proxy, no wake injection);
    # Caddy routes /api directly to the backend.
    environment:
      - BACKEND_URL=
      - CSP_CONNECT_EXTRA=${CSP_CONNECT_EXTRA:-}
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:80"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    networks:
      - kpi-network
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          memory: 128M

  caddy:
    image: <CADDY_DIGEST>  # caddy:2, digest-pinned
    container_name: kpi-caddy
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - ${KPI_DATA_ROOT:-/opt/kpi-operations}/caddy/data:/data
      - ${KPI_DATA_ROOT:-/opt/kpi-operations}/caddy/config:/config
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - kpi-network

  backup:
    image: <MARIADB_DIGEST>  # same digest as db — client tools included
    container_name: kpi-backup
    entrypoint: ["bash", "/backup-loop.sh"]
    environment:
      - DB_ROOT_PASSWORD=${DB_ROOT_PASSWORD}
      - DB_HOST=db
      - DB_NAME=kpi_platform
      - RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14}
      - BACKUP_HOUR=${BACKUP_HOUR:-02}
    volumes:
      - ./deploy/backup/backup-loop.sh:/backup-loop.sh:ro
      - ${KPI_DATA_ROOT:-/opt/kpi-operations}/backups:/backups
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - kpi-network

networks:
  kpi-network:
    name: kpi-network
    driver: bridge
```

(The old named volumes block is gone — the DB lives in MariaDB; uploads/reports/logs are host bind mounts.)

- [ ] **Step 3: Write `.env.prod.example`**

```
# KPI Operations — VM production stack secrets/config (docker-compose.prod.yml).
# Copy to .env next to the compose file ON THE VM. Never commit a real .env.

# JWT signing key, 32+ chars. Generate:
#   python3 -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=

# MariaDB application user + root passwords (root is used by the backup sidecar).
DB_PASSWORD=
DB_ROOT_PASSWORD=

# Comma-separated HTTPS origins allowed by the API. The frontend origin first;
# append the Luna-agent origin here later without any code change.
CORS_ORIGINS=https://192.168.2.234

# --- Optional overrides (defaults shown) -----------------------------------
# Host directory that holds all persistent state (db, backups, caddy CA, files):
#KPI_DATA_ROOT=/opt/kpi-operations
# Demo auto-seed (leave false in production; CI's smoke job overrides to true):
#DEMO_MODE=false
# Backup rotation:
#BACKUP_RETENTION_DAYS=14
#BACKUP_HOUR=02
```

- [ ] **Step 4: Static validation**

```bash
export KPI_DATA_ROOT=/tmp/kpi-validate DEMO_MODE=false
export SECRET_KEY=validate-only-secret-key-32-chars-min DB_PASSWORD=x DB_ROOT_PASSWORD=y CORS_ORIGINS=https://localhost  # pragma: allowlist secret
docker compose -f docker-compose.prod.yml config -q && echo "COMPOSE CONFIG OK"
```
Expected: `COMPOSE CONFIG OK`.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.prod.yml .env.prod.example
git commit -m "feat(deploy)!: docker-compose.prod.yml is the real VM stack (MariaDB+Caddy+gunicorn+backup)"
```

---

### Task 6: Shared smoke script + full local stack verification

**Files:**
- Create: `deploy/smoke/compose-smoke.sh`

**Interfaces:**
- Consumes: the Task 5 stack, running and healthy.
- Produces: `compose-smoke.sh` — assumes the stack is UP; env: `BASE_URL` (default `https://localhost`), `COMPOSE_FILE` (default `docker-compose.prod.yml`). Exit 0 = all proofs pass. Task 7's CI job calls exactly this script.

- [ ] **Step 1: Write `deploy/smoke/compose-smoke.sh`**

```bash
#!/usr/bin/env bash
# End-to-end proof of the VM compose topology (run with the stack already up):
#   1 health-through-Caddy   2 login          3 write + readback
#   4 restart persistence    5 backup+restore  6 migration-ownership logs
# CI (compose-stack-smoke) and local verification both run exactly this file.
set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
CURL="curl -sk"   # -k: Caddy's internal CA isn't in the host trust store

step() { echo; echo "=== $1 ==="; }

step "1/6 /health/database through Caddy TLS"
code=$($CURL -o /dev/null -w '%{http_code}' "$BASE_URL/health/database")
[ "$code" = "200" ] || { echo "FAIL: /health/database -> $code"; exit 1; }
echo "OK 200"

step "2/6 login (demo admin)"
TOKEN=$($CURL -X POST "$BASE_URL/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')  # pragma: allowlist secret
[ -n "$TOKEN" ] || { echo "FAIL: no token"; exit 1; }
echo "OK token issued"

step "3/6 write + readback (hold catalog entry)"
suffix=$RANDOM
create=$($CURL -X POST "$BASE_URL/api/holds/catalog" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"client_id\":\"ACME-MFG\",\"hold_code\":\"SMOKE-$suffix\",\"hold_name\":\"Compose smoke $suffix\",\"category\":\"OTHER\"}" \
  -o /dev/null -w '%{http_code}')
[ "$create" = "200" ] || [ "$create" = "201" ] || { echo "FAIL: create -> $create"; exit 1; }
$CURL -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/holds/catalog?client_id=ACME-MFG" | grep -q "SMOKE-$suffix" \
  || { echo "FAIL: created row not found"; exit 1; }
echo "OK write persisted (SMOKE-$suffix)"

step "4/6 backend restart -> data survives (bind-mounted MariaDB)"
docker compose -f "$COMPOSE_FILE" restart backend
for i in $(seq 1 30); do
  code=$($CURL -o /dev/null -w '%{http_code}' "$BASE_URL/health/database") && [ "$code" = "200" ] && break
  sleep 2
done
[ "$code" = "200" ] || { echo "FAIL: backend not healthy after restart"; exit 1; }
$CURL -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/holds/catalog?client_id=ACME-MFG" | grep -q "SMOKE-$suffix" \
  || { echo "FAIL: row lost across restart"; exit 1; }
echo "OK data survived restart"

step "5/6 backup --once + restore into scratch DB"
docker compose -f "$COMPOSE_FILE" exec -T backup bash /backup-loop.sh --once
dump=$(docker compose -f "$COMPOSE_FILE" exec -T backup sh -c 'ls -t /backups/kpi_platform-*.sql.gz | head -1' | tr -d '\r')
[ -n "$dump" ] || { echo "FAIL: no dump produced"; exit 1; }
docker compose -f "$COMPOSE_FILE" exec -T db sh -c \
  'mariadb -u root -p"$MARIADB_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS smoke_restore; CREATE DATABASE smoke_restore"'
docker compose -f "$COMPOSE_FILE" exec -T backup sh -c \
  "zcat < $dump | mariadb -h db -u root -p\"\$DB_ROOT_PASSWORD\" smoke_restore"
tables=$(docker compose -f "$COMPOSE_FILE" exec -T db sh -c \
  'mariadb -u root -p"$MARIADB_ROOT_PASSWORD" -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=\"smoke_restore\""' | tr -d '\r[:space:]')
[ "$tables" -gt 0 ] || { echo "FAIL: restore produced 0 tables"; exit 1; }
echo "OK backup restored ($tables tables)"

step "6/6 migration ownership (entrypoint ran Alembic; lifespan skipped)"
logs=$(docker compose -f "$COMPOSE_FILE" logs backend)
echo "$logs" | grep -q "Running Alembic migrations" || { echo "FAIL: entrypoint migration log missing"; exit 1; }
echo "$logs" | grep -q "RUN_MIGRATIONS_ON_STARTUP disabled" || { echo "FAIL: lifespan skip log missing"; exit 1; }
echo "OK single migration owner"

echo; echo "COMPOSE SMOKE: ALL 6 PROOFS PASS"
```

Notes for the implementer: verify the write-endpoint choice against the real API before finalizing — `grep -rn "holds/catalog" backend/routes/` for the exact path/payload/auth tier, and pick a simpler authenticated write if that one needs extra setup; the proof requirement is create → readback → survives restart, not this specific entity. Adjust payload/asserts to the real contract and note the final choice in your report. `chmod +x deploy/smoke/compose-smoke.sh`; `bash -n` clean.

- [ ] **Step 2: Full local run of the stack + smoke**

```bash
export KPI_DATA_ROOT=$(mktemp -d)/kpi && mkdir -p "$KPI_DATA_ROOT"/{mariadb-data,backups,uploads,reports,logs,caddy/data,caddy/config}
export SECRET_KEY=local-smoke-secret-key-32-chars-minimum DB_PASSWORD=smokepw DB_ROOT_PASSWORD=smokerootpw CORS_ORIGINS=https://localhost DEMO_MODE=true  # pragma: allowlist secret
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps   # wait until backend healthy (demo seed on MariaDB takes ~1-3 min)
bash deploy/smoke/compose-smoke.sh
docker compose -f docker-compose.prod.yml down
```
Expected: `COMPOSE SMOKE: ALL 6 PROOFS PASS`. Paste the full smoke output in the report. (This is also the first-ever full demo seed on MariaDB — if the seeder trips on an InnoDB-ism the portability suite missed, STOP and report with the traceback; that's a product bug to fix, not to work around.)

- [ ] **Step 3: Commit**

```bash
git add deploy/smoke/compose-smoke.sh
git commit -m "feat(deploy): shared compose-stack smoke script (6 end-to-end proofs)"
```

---

### Task 7: CI job `compose-stack-smoke`

**Files:**
- Modify: `.github/workflows/ci.yml` (append after the `mariadb-portability` job, line ~337)

**Interfaces:**
- Consumes: `deploy/smoke/compose-smoke.sh`, the Task 5 stack.
- Produces: additive CI job `compose-stack-smoke`.

- [ ] **Step 1: Append the job**

```yaml
  compose-stack-smoke:
    # Proves the exact VM topology (docker-compose.prod.yml): MariaDB + Caddy
    # internal-CA TLS + gunicorn backend + static frontend + backup sidecar.
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-lint-and-tests]
    env:
      KPI_DATA_ROOT: ${{ runner.temp }}/kpi
      SECRET_KEY: ci-compose-smoke-secret-32-chars-min  # pragma: allowlist secret
      DB_PASSWORD: ci-smoke-db-pw  # pragma: allowlist secret
      DB_ROOT_PASSWORD: ci-smoke-root-pw  # pragma: allowlist secret
      CORS_ORIGINS: https://localhost
      DEMO_MODE: "true"   # fresh MariaDB has no users until PR-4's create_admin;
                          # also the only CI exercise of the full demo seed on InnoDB
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3

      - name: Prepare data root
        run: mkdir -p "$KPI_DATA_ROOT"/{mariadb-data,backups,uploads,reports,logs,caddy/data,caddy/config}

      - name: Validate compose config
        run: docker compose -f docker-compose.prod.yml config -q

      - name: Build and start the stack
        run: docker compose -f docker-compose.prod.yml up -d --build

      - name: Wait for backend healthy (demo seed on first boot)
        run: |
          for i in $(seq 1 90); do
            status=$(docker inspect --format='{{.State.Health.Status}}' kpi-backend 2>/dev/null || echo starting)
            [ "$status" = "healthy" ] && exit 0
            sleep 5
          done
          echo "backend never became healthy"; docker compose -f docker-compose.prod.yml logs backend | tail -100
          exit 1

      - name: Run smoke proofs
        run: bash deploy/smoke/compose-smoke.sh

      - name: Dump logs on failure
        if: failure()
        run: docker compose -f docker-compose.prod.yml logs --tail 200

      - name: Tear down
        if: always()
        run: docker compose -f docker-compose.prod.yml down -v
```

- [ ] **Step 2: Validate workflow YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"`
Expected: `YAML OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: compose-stack-smoke — end-to-end proof of the VM topology on every PR"
```

---

### Task 8: Documentation

**Files:**
- Modify: `docs/DEPLOYMENT.md` (top note lines ~7-12; the Docker Deployment section)
- Modify: `README.md` (deployment pointer, if it references the compose files)

- [ ] **Step 1: Replace the DEPLOYMENT.md top note**

The note saying the checked-in compose files run "the SQLite demo" and the MariaDB compose is "reference only" is now false. Replace it with:

```markdown
> **Note:** `docker-compose.prod.yml` IS the production VM stack (MariaDB 11.4 +
> Caddy internal-CA TLS + gunicorn backend + static frontend + nightly-backup
> sidecar), proven by the `compose-stack-smoke` CI job on every PR.
> `docker-compose.yml` remains the SQLite development stack. Render deploys the
> Dockerfiles natively (`render.yaml`) and is unaffected by the prod stack.
```

- [ ] **Step 2: Rewrite the Docker Deployment section**

Replace the old compose walkthrough with (adapt heading levels to the file):
- Prereqs: Docker Engine + Compose v2 on the VM; `/opt/kpi-operations/{mariadb-data,backups,uploads,reports,logs,caddy/data,caddy/config}` created (PR-4's bootstrap does this).
- Setup: `cp .env.prod.example .env`, fill `SECRET_KEY`/`DB_PASSWORD`/`DB_ROOT_PASSWORD`/`CORS_ORIGINS`.
- Run: `docker compose -f docker-compose.prod.yml up -d --build`; verify with `bash deploy/smoke/compose-smoke.sh` (DEMO_MODE=false skips the login/write proofs until an admin exists — note that PR-4's `create_admin.py` provides the first admin, and the full smoke runs in CI with demo mode).
- TLS: Caddy's internal CA; root cert at `${KPI_DATA_ROOT}/caddy/data/caddy/pki/authorities/local/root.crt`; distribution to clients is in the PR-4 runbook.
- Backups: sidecar dumps nightly at 02:00 to `${KPI_DATA_ROOT}/backups` (14-day rotation); manual run `docker compose -f docker-compose.prod.yml exec backup bash /backup-loop.sh --once`; restore procedure (the smoke script's step 5 commands, spelled out).
- Keep the existing systemd/gunicorn alternative section as-is (it legitimately keeps `RUN_MIGRATIONS_ON_STARTUP=true`).

Also update the environment-variable table: remove `DB_HOST/DB_PORT/DB_NAME/DB_USER` rows if present (Task 2 removed the fields); `DB_PASSWORD`/`DB_ROOT_PASSWORD` are compose-level (.env) values, not app settings — say so.

- [ ] **Step 3: Check README + sweep**

Run: `grep -rn "docker-compose.prod" README.md QUICKSTART.md docs/README.md docs/UAT_PREPARATION_REPORT.md docs/UAT_TESTING_GUIDE.md`
Update any description that contradicts the new reality (one line each; UAT docs likely just reference commands — verify they still hold).

- [ ] **Step 4: Gates + commit**

```bash
cd backend && pytest tests/ 2>&1 | tail -3 && black --check . && flake8 . && cd ..
mypy backend --ignore-missing-imports
git add docs/ README.md QUICKSTART.md
git commit -m "docs: DEPLOYMENT.md documents the real VM compose stack"
```

---

## Post-implementation (PR open + verification)

- [ ] Full backend suite green, coverage ≥75%; frontend untouched (`git diff --stat main.. -- frontend/` shows nothing).
- [ ] Push branch; all existing checks + `tooling-tests` (new backup test) + `compose-stack-smoke` green — the smoke's 6 proofs are the release evidence.
- [ ] `/cross-review` for HEAD + `/code-review`.
- [ ] PR body: D1–D3 decisions, Render-safety statement (no shared files touched except requirements.lock), the first-demo-seed-on-InnoDB milestone, PR-3b carry-forward list, PR-4 hand-offs (dirs, CA distribution, create_admin, ufw).
- [ ] Merge on green (user confirms). Post-merge: Render deploy verify (health + login) — expected unchanged.

## Self-Review (against the spec)

- **Spec coverage:** stack §db/backend/caddy/frontend/backup → Task 5 (+3,4); gunicorn lock → Task 1; dead DB_* cleanup → Task 2; Caddyfile w/ 120s capacity + /health routing → Task 3; sidecar + `--once` → Task 4; CI smoke w/ all 6 proofs incl. backup-restore + log assertions → Tasks 6-7; docs → Task 8; `.env.prod.example` → Task 5. ✓
- **Type consistency:** env-var names (`KPI_DATA_ROOT`, `DB_PASSWORD`, `DB_ROOT_PASSWORD`, `BACKUP_RETENTION_DAYS`, `BACKUP_HOUR`) match across compose/scripts/CI; `backup-loop.sh --once` invoked identically in Task 4 test, Task 6 smoke, Task 8 docs. ✓
- **No placeholders:** the two image-digest placeholders are explicit implementation-time substitutions with the exact resolution command; the smoke write-endpoint carries a verify-against-real-API instruction with the proof requirement stated. ✓
- **Known judgment points:** smoke write endpoint choice (verify real contract); gunicorn exact version if 23.0.0 is superseded; digest values.
