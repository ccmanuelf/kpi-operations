#!/usr/bin/env bash
# Unit tests for deploy/vm-bootstrap.sh non-privileged logic. Hermetic:
# sudo/python3 are stubbed onto PATH (sudo records argv, python3 emits a
# deterministic "secret") — no privileged action, no network, no Docker.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BOOTSTRAP="$SCRIPT_DIR/deploy/vm-bootstrap.sh"
fail=0
assert() { # assert <desc> <cond-exit>
  if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi
}

TMP="$(mktemp -d)"

# --- stub bin: sudo logs its argv; python3 emits a deterministic secret ------
STUB="$TMP/bin"; mkdir -p "$STUB"
cat > "$STUB/sudo" <<'EOF'
#!/usr/bin/env bash
echo "sudo $*" >> "${SUDO_LOG:?}"
exit 0
EOF
cat > "$STUB/python3" <<'EOF'
#!/usr/bin/env bash
echo "STUBSECRET1234567890abcdefghijkl"  # pragma: allowlist secret
EOF
chmod +x "$STUB/sudo" "$STUB/python3"
export PATH="$STUB:$PATH"
export SUDO_LOG="$TMP/sudo.log"; : > "$SUDO_LOG"

# --- bash -n: script parses ---------------------------------------------------
bash -n "$BOOTSTRAP"
assert "bash -n parses vm-bootstrap.sh" $?

# --- --print-config: defaults -------------------------------------------------
out=$(bash "$BOOTSTRAP" --print-config)
echo "$out" | grep -qx 'ROOT=/opt/kpi-operations'; assert "default ROOT" $?
echo "$out" | grep -qx 'APP_DIR=/opt/kpi-operations/app'; assert "default APP_DIR" $?
echo "$out" | grep -qx 'IP=192.168.2.234'; assert "default IP" $?

# --- --print-config: --app-dir follows --root unless given --------------------
out=$(bash "$BOOTSTRAP" --root /srv/kpi --print-config)
echo "$out" | grep -qx 'APP_DIR=/srv/kpi/app'; assert "APP_DIR follows --root" $?
out=$(bash "$BOOTSTRAP" --root /srv/kpi --app-dir /x --ip 10.0.0.5 --print-config)
echo "$out" | grep -qx 'APP_DIR=/x'; assert "explicit --app-dir wins" $?
echo "$out" | grep -qx 'IP=10.0.0.5'; assert "--ip override" $?

# --- unknown argument exits nonzero -------------------------------------------
bash "$BOOTSTRAP" --bogus >/dev/null 2>&1
[ "$?" -ne 0 ]; assert "unknown argument exits nonzero" $?

# --- scaffold-env: all keys populated, mode 600 --------------------------------
ENVDIR="$TMP/app"; mkdir -p "$ENVDIR"
cp "$SCRIPT_DIR/.env.prod.example" "$ENVDIR/"
bash "$BOOTSTRAP" --scaffold-env-only "$ENVDIR" >/dev/null
assert "scaffold-env exits 0" $?
grep -q '^SECRET_KEY=STUBSECRET' "$ENVDIR/.env"; assert "SECRET_KEY populated" $?
grep -q '^DB_PASSWORD=STUBSECRET' "$ENVDIR/.env"; assert "DB_PASSWORD populated" $?
grep -q '^DB_ROOT_PASSWORD=STUBSECRET' "$ENVDIR/.env"; assert "DB_ROOT_PASSWORD populated" $?
grep -qx 'CORS_ORIGINS=https://192.168.2.234' "$ENVDIR/.env"; assert "CORS_ORIGINS set" $?
grep -qx 'TZ=America/Monterrey' "$ENVDIR/.env"; assert "TZ set" $?
perms=$(stat -f %Lp "$ENVDIR/.env" 2>/dev/null || stat -c %a "$ENVDIR/.env")
[ "$perms" = "600" ]; assert ".env is mode 600" $?

# --- scaffold-env: secrets are never echoed to stdout/stderr -------------------
rm -f "$ENVDIR/.env"
outerr=$(bash "$BOOTSTRAP" --scaffold-env-only "$ENVDIR" 2>&1)
echo "$outerr" | grep -q 'STUBSECRET'
[ "$?" -ne 0 ]; assert "generated secrets never echoed" $?

# --- scaffold-env: idempotent re-run keeps the existing .env -------------------
echo "SENTINEL=1" >> "$ENVDIR/.env"
bash "$BOOTSTRAP" --scaffold-env-only "$ENVDIR" >/dev/null
grep -qx 'SENTINEL=1' "$ENVDIR/.env"; assert "re-run keeps existing .env" $?

# --- scaffold-env: missing example file exits nonzero --------------------------
EMPTY="$TMP/empty"; mkdir -p "$EMPTY"
bash "$BOOTSTRAP" --scaffold-env-only "$EMPTY" >/dev/null 2>&1
[ "$?" -ne 0 ]; assert "scaffold without example exits nonzero" $?

# --- confirm gate: declining every y/N prompt invokes zero sudo commands -------
# Full run with all confirms declined. On a case-insensitive dev FS the script
# exits at the phase-1 preflight (also sudo-free); on ext4 CI it walks all
# phases declining each gate. Either way the sudo stub log must stay empty.
yes n | bash "$BOOTSTRAP" --root "$TMP/root" >/dev/null 2>&1 || true
[ ! -s "$SUDO_LOG" ]; assert "declined confirms invoke no sudo" $?

rm -rf "$TMP"
exit $fail
