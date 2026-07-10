#!/usr/bin/env bash
# Nightly mariadb-dump sidecar for the KPI VM stack (docker-compose.prod.yml).
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
    # mariadb-dump, not mysqldump: the mariadb:11.x image dropped the mysql-*
    # compat names (only mariadb-* binaries exist in /usr/bin).
    # Dump to a .tmp and rename on success: a failed dump must never leave a
    # truncated *.sql.gz that a later restore could silently pick up.
    # Explicit if/return, NOT set -e: when the loop calls `dump_once || ...`,
    # errexit is suspended inside the function body (bash semantics), so a
    # failed pipeline would otherwise fall through to the mv and publish a
    # truncated dump under the good name.
    # MYSQL_PWD (env), not -p on argv: command-line args are visible to any
    # host user via `ps`/`docker top`; env vars are not.
    if ! MYSQL_PWD="$DB_ROOT_PASSWORD" mariadb-dump --single-transaction --routines --events \
            -h "$DB_HOST" -u root "$DB_NAME" | gzip > "$file.tmp"; then
        rm -f "$file.tmp"
        echo "[backup] dump FAILED for ${DB_NAME}" >&2
        return 1
    fi
    mv "$file.tmp" "$file"
    echo "[backup] pruning dumps older than ${RETENTION_DAYS} days"
    find "$BACKUP_DIR" -name "${DB_NAME}-*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
    # Sweep stale .tmp files (>1 day) left by a dump that died mid-write, so
    # they never accumulate.
    find "$BACKUP_DIR" -name "${DB_NAME}-*.sql.gz.tmp" -mtime +1 -delete
    echo "[backup] done: $(ls -lh "$file" | awk '{print $5}')"
}

if [ "${1:-}" = "--once" ]; then
    dump_once
    exit 0
fi

echo "[backup] nightly loop armed (hour=${BACKUP_HOUR}, retention=${RETENTION_DAYS}d)"
while true; do
    now_h=$(date +%H)
    # 10# forces base-10 so a zero-padded hour ("08"/"09") isn't parsed as octal
    # and "2" matches "02".
    if [ "$((10#$now_h))" -eq "$((10#$BACKUP_HOUR))" ]; then
        # A single dump failure must NOT kill the sidecar — log and retry next
        # cycle (--once keeps its fail-fast exit; only the loop is resilient).
        dump_once || echo "[backup] dump failed (will retry next cycle)"
        sleep 3600  # skip past the backup hour
    fi
    sleep 300
done
