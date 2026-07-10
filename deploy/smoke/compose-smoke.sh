#!/usr/bin/env bash
# End-to-end proof of the VM compose topology (run with the stack already
# built + `up -d`):
#   0 stack readiness (owns the wait)  1 health through Caddy TLS
#   1w uploads writability             2 login
#   3 write + JSON readback            4 restart persistence
#   5 backup + restore (scratch DB)    6 migration ownership logs
# CI (compose-stack-smoke) and local verification both run exactly this file.
#
# SIDE EFFECTS: writes SMOKE-#### hold-status rows (client ACME-MFG) and leaves a
# `smoke_restore` scratch database behind (proof 5's restore target). Harmless on
# CI / fresh installs; run knowingly against a live system.
#
# Write endpoint: POST /api/hold-catalogs/statuses (201, supervisor tier — the
# demo `admin` satisfies it). Chosen because a hold-status catalog entry is a
# self-contained authenticated create+list against a seeded demo client
# (ACME-MFG) with no extra setup. Proof requirement: create -> readback ->
# survives restart.
set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost}"
# `docker compose` reads COMPOSE_FILE natively — a single path or a colon-joined
# value (e.g. the local named-volume override) both work — so we just export it.
export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
CLIENT_ID="${CLIENT_ID:-ACME-MFG}"
CURL="curl -sk"   # -k: Caddy's internal CA isn't in the host trust store
READY_DEADLINE="${READY_DEADLINE:-600}"   # proof 0 owns the boot/seed wait
RETRY_DEADLINE="${RETRY_DEADLINE:-120}"   # per-request bounded retry (slow boot)

dc() { docker compose "$@"; }

# retry_until <deadline-seconds> <cmd...>: run cmd every 5s until it exits 0 or
# the deadline elapses; return 0 on success, 1 on timeout. Kills the duplicated
# seq/sleep scaffolding across proofs 0, 2 and 3.
retry_until() {
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}

step() { echo; echo "=== $1 ==="; }

# --- Proof 0: stack readiness (replaces the CI YAML health-wait step) ---------
step "0 stack readiness (health through Caddy, <= ${READY_DEADLINE}s)"
unhealthy_streak=0
backend_ready() {
  # Fail fast on a dead stack rather than waiting out the full budget.
  local state health code
  state=$(docker inspect --format '{{.State.Status}}' kpi-backend 2>/dev/null || echo missing)
  if [ "$state" = "exited" ]; then
    echo "FAIL: kpi-backend exited"; dc logs backend | tail -100; exit 1
  fi
  health=$(docker inspect --format '{{.State.Health.Status}}' kpi-backend 2>/dev/null || echo starting)
  if [ "$health" = "unhealthy" ]; then
    unhealthy_streak=$((unhealthy_streak + 1))
    if [ "$unhealthy_streak" -ge 3 ]; then
      echo "FAIL: kpi-backend unhealthy 3 polls running"; dc logs backend | tail -100; exit 1
    fi
  else
    unhealthy_streak=0
  fi
  # Poll THROUGH Caddy so this also proves Caddy is serving TLS.
  code=$($CURL -o /dev/null -w '%{http_code}' "$BASE_URL/health/database" 2>/dev/null || echo 000)
  [ "$code" = "200" ]
}
retry_until "$READY_DEADLINE" backend_ready \
  || { echo "FAIL: stack not ready in ${READY_DEADLINE}s"; dc logs backend | tail -100; exit 1; }
echo "OK stack ready"

# --- Proof 1: health through Caddy TLS (single-shot assert) -------------------
step "1 /health/database through Caddy TLS"
code=$($CURL -o /dev/null -w '%{http_code}' "$BASE_URL/health/database")
[ "$code" = "200" ] || { echo "FAIL: /health/database -> $code"; exit 1; }
echo "OK 200"

# --- Proof 1w: uploads mount is writable by the backend uid -------------------
step "1w uploads mount writable (backend dynamic uid vs host owner)"
dc exec -T backend sh -c 'touch /app/uploads/.smoke-write && rm /app/uploads/.smoke-write' \
  || { echo "FAIL: backend cannot write /app/uploads (chown the mount to the image uid)"; exit 1; }
echo "OK uploads writable"

# --- Proof 2: login (demo admin) ---------------------------------------------
step "2 login (demo admin)"
TOKEN=""
LOGIN_JSON='{"username":"admin","password":"admin123"}'  # pragma: allowlist secret
login_once() {
  TOKEN=$($CURL -X POST "$BASE_URL/api/auth/login" -H 'Content-Type: application/json' \
    -d "$LOGIN_JSON" 2>/dev/null \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])' 2>/dev/null) \
    && [ -n "$TOKEN" ]
}
retry_until "$RETRY_DEADLINE" login_once || { echo "FAIL: no token"; exit 1; }
echo "OK token issued"

# --- Proof 3: write + JSON readback ------------------------------------------
step "3 write + readback (hold-status catalog entry)"
suffix=$RANDOM
create=""
do_create() {
  # Retry only connection-level curl failures; once curl gets an HTTP response
  # (any code) it exits 0 and the status is asserted single-shot below.
  create=$($CURL -X POST "$BASE_URL/api/hold-catalogs/statuses" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"client_id\":\"$CLIENT_ID\",\"status_code\":\"SMOKE-$suffix\",\"display_name\":\"Compose smoke $suffix\"}" \
    -o /dev/null -w '%{http_code}')
}
retry_until "$RETRY_DEADLINE" do_create || { echo "FAIL: create never got an HTTP response"; exit 1; }
[ "$create" = "201" ] || { echo "FAIL: create -> $create (want 201)"; exit 1; }

# JSON-parse the readback (kills the grep -q SIGPIPE-under-pipefail trap and the
# weak substring match): assert an entry whose status_code == SMOKE-$suffix.
assert_row_present() {
  local body
  body=$($CURL -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/hold-catalogs/statuses?client_id=$CLIENT_ID")
  printf '%s' "$body" | WANT="SMOKE-$suffix" python3 -c '
import json, os, sys
want = os.environ["WANT"]
rows = json.load(sys.stdin)
codes = [r.get("status_code") for r in rows if isinstance(r, dict)]
sys.exit(0 if want in codes else 1)
'
}
assert_row_present || { echo "FAIL: created row (SMOKE-$suffix) not found in readback"; exit 1; }
echo "OK write persisted (SMOKE-$suffix)"

# --- Proof 4: restart persistence (bind-mounted MariaDB) ---------------------
step "4 backend restart -> data survives"
dc restart backend
restart_ready() {
  local code
  code=$($CURL -o /dev/null -w '%{http_code}' "$BASE_URL/health/database" 2>/dev/null || echo 000)
  [ "$code" = "200" ]
}
retry_until "$RETRY_DEADLINE" restart_ready || { echo "FAIL: backend not healthy after restart"; exit 1; }
assert_row_present || { echo "FAIL: row (SMOKE-$suffix) lost across restart"; exit 1; }
echo "OK data survived restart"

# --- Proof 5: backup --once + restore into scratch DB ------------------------
step "5 backup --once + restore-verify (scratch DB)"
dc exec -T backup bash /backup-loop.sh --once
bash deploy/backup/restore-verify.sh smoke_restore
echo "OK backup restored"

# --- Proof 6: migration ownership --------------------------------------------
step "6 migration ownership (entrypoint ran Alembic; lifespan skipped)"
logs=$(dc logs backend)
# here-strings, not `echo | grep -q`: under pipefail, grep -q exiting at the
# first match SIGPIPEs the echo (rc 141) and fails the check spuriously.
grep -q "Running Alembic migrations" <<<"$logs" || { echo "FAIL: entrypoint migration log missing"; exit 1; }
grep -q "RUN_MIGRATIONS_ON_STARTUP disabled" <<<"$logs" || { echo "FAIL: lifespan skip log missing"; exit 1; }
echo "OK single migration owner"

echo; echo "COMPOSE SMOKE: ALL PROOFS PASS"
