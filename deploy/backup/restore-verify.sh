#!/usr/bin/env bash
# Restore-verify: find the latest DB dump, restore it into a SCRATCH database,
# and assert the restore produced tables. This is the shared restore-check used
# both by compose-smoke.sh (proof 5) and as the documented restore-verification
# step (docs/DEPLOYMENT.md, Backups). It never touches the live database.
#
#   restore-verify.sh [scratch_db_name]       (default scratch: smoke_restore)
#   DB_NAME env: source database for dump discovery (default: kpi_platform)
#
# Requires the compose stack to be up. COMPOSE_FILE is read natively by
# `docker compose` (single path or colon-joined for a local override).
set -euo pipefail

SCRATCH_DB="${1:-smoke_restore}"
DB_NAME="${DB_NAME:-kpi_platform}"
export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

echo "[restore-verify] latest ${DB_NAME} dump -> scratch DB '${SCRATCH_DB}'"
dump=$(docker compose exec -T backup sh -c "ls -t /backups/${DB_NAME}-*.sql.gz | head -1" | tr -d '\r')
[ -n "$dump" ] || { echo "[restore-verify] FAIL: no dump found under /backups"; exit 1; }

# MYSQL_PWD (env), not -p on argv: command-line args are visible to any host
# user via `ps`/`docker top`; env vars are not.
docker compose exec -T db sh -c \
  "MYSQL_PWD=\"\$MARIADB_ROOT_PASSWORD\" mariadb -u root -e \"DROP DATABASE IF EXISTS ${SCRATCH_DB}; CREATE DATABASE ${SCRATCH_DB}\""
docker compose exec -T backup sh -c \
  "zcat < ${dump} | MYSQL_PWD=\"\$DB_ROOT_PASSWORD\" mariadb -h db -u root ${SCRATCH_DB}"

tables=$(docker compose exec -T db sh -c \
  "MYSQL_PWD=\"\$MARIADB_ROOT_PASSWORD\" mariadb -u root -N -e \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${SCRATCH_DB}'\"" \
  | tr -d '\r[:space:]')
[ "$tables" -gt 0 ] || { echo "[restore-verify] FAIL: restore produced 0 tables"; exit 1; }

echo "[restore-verify] OK: ${dump} restored into ${SCRATCH_DB} (${tables} tables)"
echo "$tables"
