#!/usr/bin/env bash
# Pre-flight check for the KPI data root: the MariaDB datadir bind mount MUST
# live on a CASE-SENSITIVE filesystem. macOS / Docker-Desktop shared mounts
# (virtiofs) are case-INSENSITIVE and corrupt the InnoDB datadir — MariaDB
# errno 1033 ("Incorrect information in file"), a crash-loop on restart. Fail
# loudly here, before a half-initialized datadir exists.
#
#   preflight.sh <root>
set -euo pipefail

ROOT="${1:-}"
[ -n "$ROOT" ] || { echo "usage: $0 <root>" >&2; exit 1; }

PROBE_DIR="$ROOT/mariadb-data"
mkdir -p "$PROBE_DIR"

# Write distinct content to a lowercase and an uppercase name. On a
# case-sensitive FS these are two files with two contents; on a case-insensitive
# FS the second write lands on the same inode, so both names read back "upper".
lower="$PROBE_DIR/.kpi-case-probe-a"
upper="$PROBE_DIR/.kpi-case-probe-A"
rm -f "$lower" "$upper"
printf 'lower' > "$lower"
printf 'upper' > "$upper"
collision=0
[ "$(cat "$lower" 2>/dev/null)" = "$(cat "$upper" 2>/dev/null)" ] && collision=1
rm -f "$lower" "$upper"

if [ "$collision" -eq 1 ]; then
  cat >&2 <<EOF
[preflight] FATAL: $PROBE_DIR is on a CASE-INSENSITIVE filesystem.
MariaDB requires a case-sensitive datadir; a case-insensitive mount corrupts
InnoDB (errno 1033 "Incorrect information in file", crash-loop on restart).
Use an ext4/xfs path on the Linux VM. On macOS, substitute a named Docker
volume for the db bind mount (see docs/DEPLOYMENT.md, Docker Deployment).
EOF
  exit 1
fi

echo "[preflight] OK: $PROBE_DIR is case-sensitive"
