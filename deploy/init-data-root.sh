#!/usr/bin/env bash
# Single source of truth for the KPI data-root layout (the persistent bind
# mounts declared in docker-compose.prod.yml). Creates every state directory
# under <root>; with --chown <uid> also chowns the backend-writable mounts
# (uploads, reports, logs) to the backend image's dynamically-assigned UID.
#
#   init-data-root.sh <root> [--chown <uid>]
#
# Idempotent: safe to run before the build (no uid yet) and again after (with
# --chown <uid> queried from the built image).
set -euo pipefail

ROOT="${1:-}"
[ -n "$ROOT" ] || { echo "usage: $0 <root> [--chown <uid>]" >&2; exit 1; }
shift

CHOWN_UID=""
if [ "${1:-}" = "--chown" ]; then
  CHOWN_UID="${2:-}"
  [ -n "$CHOWN_UID" ] || { echo "$0: --chown requires a uid" >&2; exit 1; }
fi

# The full manifest — keep in lockstep with the bind mounts in
# docker-compose.prod.yml (db datadir, backups, backend uploads/reports/logs,
# caddy data/config).
DIRS=(mariadb-data backups uploads reports logs caddy/data caddy/config)
for d in "${DIRS[@]}"; do
  mkdir -p "$ROOT/$d"
done

# The backend runs as a non-root, build-time-dynamic UID; the three
# host-writable mounts must be owned by it or CSV upload / report generation
# fail with EACCES while everything else keeps working (easy to misdiagnose).
if [ -n "$CHOWN_UID" ]; then
  chown -R "$CHOWN_UID" "$ROOT/uploads" "$ROOT/reports" "$ROOT/logs"
fi

echo "[init-data-root] ready: $ROOT (${#DIRS[@]} dirs${CHOWN_UID:+, chown $CHOWN_UID -> uploads/reports/logs})"
