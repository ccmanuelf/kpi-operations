#!/usr/bin/env bash
# End-to-end proof of the VM compose topology (run with the stack already up):
#   1 health-through-Caddy   2 login          3 write + readback
#   4 restart persistence    5 backup+restore  6 migration-ownership logs
# CI (compose-stack-smoke) and local verification both run exactly this file.
#
# Write endpoint: POST /api/hold-catalogs/statuses (201, supervisor tier — the
# demo `admin` satisfies it). Chosen over the brief's placeholder
# /api/holds/catalog (which does not exist) because a hold-status catalog entry
# is a self-contained authenticated create+list against a seeded demo client
# (ACME-MFG) with no extra setup. Proof requirement: create -> readback ->
# survives restart.
set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
CLIENT_ID="${CLIENT_ID:-ACME-MFG}"
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

step "3/6 write + readback (hold-status catalog entry)"
suffix=$RANDOM
create=$($CURL -X POST "$BASE_URL/api/hold-catalogs/statuses" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"client_id\":\"$CLIENT_ID\",\"status_code\":\"SMOKE-$suffix\",\"display_name\":\"Compose smoke $suffix\"}" \
  -o /dev/null -w '%{http_code}')
[ "$create" = "201" ] || [ "$create" = "200" ] || { echo "FAIL: create -> $create"; exit 1; }
$CURL -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/hold-catalogs/statuses?client_id=$CLIENT_ID" | grep -q "SMOKE-$suffix" \
  || { echo "FAIL: created row not found"; exit 1; }
echo "OK write persisted (SMOKE-$suffix)"

step "4/6 backend restart -> data survives (bind-mounted MariaDB)"
docker compose -f "$COMPOSE_FILE" restart backend
for i in $(seq 1 30); do
  code=$($CURL -o /dev/null -w '%{http_code}' "$BASE_URL/health/database") && [ "$code" = "200" ] && break
  sleep 2
done
[ "$code" = "200" ] || { echo "FAIL: backend not healthy after restart"; exit 1; }
$CURL -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/hold-catalogs/statuses?client_id=$CLIENT_ID" | grep -q "SMOKE-$suffix" \
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
# here-strings, not `echo | grep -q`: under pipefail, grep -q exiting at the
# first match SIGPIPEs the echo (rc 141) and fails the check spuriously.
grep -q "Running Alembic migrations" <<<"$logs" || { echo "FAIL: entrypoint migration log missing"; exit 1; }
grep -q "RUN_MIGRATIONS_ON_STARTUP disabled" <<<"$logs" || { echo "FAIL: lifespan skip log missing"; exit 1; }
echo "OK single migration owner"

echo; echo "COMPOSE SMOKE: ALL 6 PROOFS PASS"
