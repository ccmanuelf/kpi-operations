#!/usr/bin/env bash
# Unit test for frontend/docker-entrypoint.sh: wake-origin meta injection,
# CSP connect-src append, and proxy timeouts, per BACKEND_URL branch.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENTRYPOINT="$SCRIPT_DIR/frontend/docker-entrypoint.sh"
fail=0
assert() { if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi; }

# The entrypoint uses `sed -i` (GNU/busybox form); macOS BSD sed differs — skip there.
if ! sed --version >/dev/null 2>&1; then echo "SKIP: requires GNU sed"; exit 0; fi

setup() {
  TMP="$(mktemp -d)"
  echo 'connect-src self CSP_CONNECT_EXTRA_PLACEHOLDER;' > "$TMP/default.conf"
  printf '<html><head><title>x</title></head><body></body></html>' > "$TMP/index.html"
}
run_entrypoint() {
  ENTRYPOINT_CONF="$TMP/default.conf" ENTRYPOINT_UPSTREAM="$TMP/upstream.inc" \
  ENTRYPOINT_INDEX_HTML="$TMP/index.html" ENTRYPOINT_SKIP_NGINX=1 \
  BACKEND_URL="${1-}" CSP_CONNECT_EXTRA="${2-}" sh "$ENTRYPOINT"
}

# --- external HTTPS branch ---
setup; run_entrypoint "https://kpi-operations-api.onrender.com" ""
grep -q '<meta name="backend-wake-origin" content="https://kpi-operations-api.onrender.com">' "$TMP/index.html"
assert "https: wake-origin meta tag injected" $?
grep -q 'proxy_read_timeout 120s' "$TMP/upstream.inc"; assert "https: proxy_read_timeout 120s" $?
grep -q 'proxy_connect_timeout 120s' "$TMP/upstream.inc"; assert "https: proxy_connect_timeout 120s" $?
grep -q 'connect-src self https://kpi-operations-api.onrender.com;' "$TMP/default.conf"
assert "https: CSP gains backend origin without CSP_CONNECT_EXTRA" $?
rm -rf "$TMP"

# --- external HTTPS branch with CSP_CONNECT_EXTRA preset keeps both origins ---
setup; run_entrypoint "https://kpi-operations-api.onrender.com" "https://other.example.com"
grep -q 'connect-src self https://other.example.com https://kpi-operations-api.onrender.com;' "$TMP/default.conf"
assert "https: preset CSP_CONNECT_EXTRA preserved alongside backend origin" $?
rm -rf "$TMP"

# --- internal Docker branch: no meta tag, no CSP origin, timeouts unchanged ---
setup; run_entrypoint "http://backend:8000" ""
grep -q 'backend-wake-origin' "$TMP/index.html"; [ $? -ne 0 ]; assert "internal: no meta tag" $?
grep -q 'proxy_read_timeout 60s' "$TMP/upstream.inc"; assert "internal: 60s timeout kept" $?
grep -q 'CSP_CONNECT_EXTRA_PLACEHOLDER' "$TMP/default.conf"; [ $? -ne 0 ]; assert "internal: placeholder removed" $?
rm -rf "$TMP"

# --- no-backend branch: empty upstream, untouched index.html ---
setup; run_entrypoint "" ""
[ -s "$TMP/upstream.inc" ]; [ $? -ne 0 ]; assert "empty: upstream.inc empty" $?
grep -q 'backend-wake-origin' "$TMP/index.html"; [ $? -ne 0 ]; assert "empty: no meta tag" $?
rm -rf "$TMP"

exit $fail
