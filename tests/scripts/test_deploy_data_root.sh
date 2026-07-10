#!/usr/bin/env bash
# Unit tests for deploy/init-data-root.sh and deploy/preflight.sh. Pure
# filesystem ops — hermetic, no Docker/DB needed. Portable across the
# case-sensitive CI runner (ext4) and a case-insensitive macOS dev box: the
# preflight assertion is keyed off the host FS behavior, probed independently.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
INIT="$SCRIPT_DIR/deploy/init-data-root.sh"
PREFLIGHT="$SCRIPT_DIR/deploy/preflight.sh"
fail=0
assert() { # assert <desc> <cond-exit>
  if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi
}

TMP="$(mktemp -d)"

# --- init-data-root.sh: creates the full manifest ----------------------------
ROOT="$TMP/data"
bash "$INIT" "$ROOT" >/dev/null
init_exit=$?
[ "$init_exit" -eq 0 ]; assert "init-data-root.sh exits 0" $?
for d in mariadb-data backups uploads reports logs caddy/data caddy/config; do
  [ -d "$ROOT/$d" ]; assert "init-data-root creates $d" $?
done

# --- init-data-root.sh --chown <own uid>: applies to the writable mounts -----
# chown to our OWN uid always succeeds without root, exercising the path.
ROOT2="$TMP/data2"
bash "$INIT" "$ROOT2" --chown "$(id -u)" >/dev/null
chown_exit=$?
[ "$chown_exit" -eq 0 ]; assert "init-data-root.sh --chown exits 0" $?
[ -d "$ROOT2/uploads" ]; assert "init-data-root --chown still creates dirs" $?

# --- init-data-root.sh: usage error when <root> omitted ----------------------
bash "$INIT" >/dev/null 2>&1
[ "$?" -ne 0 ]; assert "init-data-root.sh without <root> exits nonzero" $?

# --- preflight.sh: verdict matches the host filesystem -----------------------
# Independently probe whether $TMP is case-insensitive: create 'f', see if 'F'
# resolves to it.
probe="$TMP/cs-probe"; mkdir -p "$probe"
printf 'x' > "$probe/f"
host_case_insensitive=0
[ -f "$probe/F" ] && host_case_insensitive=1

PFROOT="$TMP/pf"
bash "$PREFLIGHT" "$PFROOT" >/dev/null 2>&1
pf_exit=$?
if [ "$host_case_insensitive" -eq 1 ]; then
  [ "$pf_exit" -ne 0 ]; assert "preflight fails on case-insensitive host FS" $?
else
  [ "$pf_exit" -eq 0 ]; assert "preflight passes on case-sensitive host FS" $?
fi
# Either way it must have created the datadir probe directory and cleaned up its
# probe files.
[ -d "$PFROOT/mariadb-data" ]; assert "preflight creates mariadb-data probe dir" $?
[ -z "$(ls "$PFROOT/mariadb-data"/.kpi-case-probe-* 2>/dev/null)" ]; assert "preflight cleans up its probe files" $?

# --- preflight.sh: usage error when <root> omitted ---------------------------
bash "$PREFLIGHT" >/dev/null 2>&1
[ "$?" -ne 0 ]; assert "preflight.sh without <root> exits nonzero" $?

rm -rf "$TMP"
exit $fail
