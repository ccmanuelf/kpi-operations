#!/bin/bash
# SQLite backup script for Render.com persistent disk
# Uses the SQLite .backup API (safe for concurrent access)
#
# Usage:
#   ./backup_sqlite.sh              # defaults: /app/database/kpi_platform.db
#   ./backup_sqlite.sh /my/backups  # custom backup directory
#
# Environment variables:
#   DB_PATH      — path to the SQLite database (default: /app/database/kpi_platform.db)
#   MAX_BACKUPS  — number of backups to retain (default: 5)

set -euo pipefail

DB_PATH="${DB_PATH:-/app/database/kpi_platform.db}"
BACKUP_DIR="${1:-/app/database/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/kpi_platform_${TIMESTAMP}.db"
MAX_BACKUPS="${MAX_BACKUPS:-5}"

# Validate source database exists
if [ ! -f "$DB_PATH" ]; then
  echo "ERROR: Database not found at ${DB_PATH}" >&2
  exit 1
fi

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Use SQLite backup API (safe for concurrent readers/writers)
sqlite3 "$DB_PATH" ".backup '${BACKUP_FILE}'"

echo "Backup created: ${BACKUP_FILE}"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"

# Rotate old backups — keep the most recent MAX_BACKUPS files
cd "$BACKUP_DIR"
# shellcheck disable=SC2012
ls -t kpi_platform_*.db 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -f

echo "Backup complete. Retained last ${MAX_BACKUPS} backups."
