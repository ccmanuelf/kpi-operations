#!/usr/bin/env bash
# Unit test for deploy/backup/backup-loop.sh: --once produces a pruned,
# gzipped dump using the mysqldump on PATH; retention removes old files.
# Stubs mysqldump so the test is hermetic (no DB needed).
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$SCRIPT_DIR/deploy/backup/backup-loop.sh"
fail=0
assert() { # assert <desc> <cond-exit>
  if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi
}

TMP="$(mktemp -d)"
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
run_exit=$?
[ "$run_exit" -eq 0 ]; assert "backup-loop.sh --once exits 0" $?

new_dump=$(ls "$TMP/backups"/kpi_platform-2*.sql.gz 2>/dev/null | head -1)
[ -n "$new_dump" ]; assert "timestamped dump produced" $?

if [ -n "$new_dump" ]; then
  gzip -t "$new_dump" >/dev/null 2>&1; assert "dump is valid gzip" $?
  zcat < "$new_dump" 2>/dev/null | grep -q "fake dump"; assert "dump content present" $?
fi

grep -q -- "--single-transaction" "$TMP/bin/mysqldump.args" 2>/dev/null
assert "--single-transaction passed to mysqldump" $?

[ ! -f "$TMP/backups/kpi_platform-old.sql.gz" ]; assert "old backup pruned" $?
[ -f "$TMP/backups/kpi_platform-fresh.sql.gz" ]; assert "fresh backup not pruned" $?

rm -rf "$TMP"
exit $fail
