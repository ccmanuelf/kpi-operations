#!/bin/sh
set -e

# ENTRYPOINT_* overrides exist for the shell unit test
# (tests/scripts/test_frontend_entrypoint.sh); production uses the defaults.
CONF="${ENTRYPOINT_CONF:-/etc/nginx/conf.d/default.conf}"
UPSTREAM="${ENTRYPOINT_UPSTREAM:-/etc/nginx/conf.d/upstream.inc}"
INDEX_HTML="${ENTRYPOINT_INDEX_HTML:-/usr/share/nginx/html/index.html}"

# --- Generate proxy config based on BACKEND_URL ---
if [ -z "$BACKEND_URL" ]; then
  # No backend URL — no proxy, frontend calls API directly via VITE_API_URL
  : > "$UPSTREAM"

elif echo "$BACKEND_URL" | grep -q "^https://"; then
  # External HTTPS backend (e.g. Render) — needs resolver + variable proxy_pass + SNI
  BACKEND_HOST=$(echo "$BACKEND_URL" | sed 's|https://||; s|/.*||')
  cat > "$UPSTREAM" <<UPSTREAM_EOF
# Auto-generated: external HTTPS proxy to $BACKEND_URL
resolver 8.8.8.8 1.1.1.1 valid=30s;

location /api/ {
    set \$backend $BACKEND_URL;
    proxy_pass \$backend;
    proxy_http_version 1.1;
    proxy_ssl_server_name on;
    proxy_set_header Host $BACKEND_HOST;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    # Rewrite backend redirect URLs to stay on frontend origin.
    # Without this, 307 trailing-slash redirects expose the backend host,
    # causing cross-origin redirects that strip the Authorization header.
    proxy_redirect https://$BACKEND_HOST/ /;
    proxy_connect_timeout 120s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
}
UPSTREAM_EOF

  # Free-tier hibernation wake (spec: 2026-07-02-cold-start-direct-wake-design.md):
  # requests proxied from this container originate from the host's shared egress
  # IPs, which the hosting edge 429s (hibernate-rate-limited) WITHOUT waking the
  # backend. Expose the backend origin to the SPA so the VISITOR'S browser sends
  # the wake request directly — that path reliably wakes it in ~90-100s.
  if [ -f "$INDEX_HTML" ]; then
    sed -i "s|</head>|<meta name=\"backend-wake-origin\" content=\"https://$BACKEND_HOST\"></head>|" "$INDEX_HTML"
  fi
  # The direct wake fetch needs the backend origin in CSP connect-src even when
  # CSP_CONNECT_EXTRA is not configured (duplicates are harmless in a CSP list).
  CSP_CONNECT_EXTRA="${CSP_CONNECT_EXTRA:+$CSP_CONNECT_EXTRA }https://$BACKEND_HOST"

else
  # Internal Docker backend (e.g. http://backend:8000) — static proxy_pass
  cat > "$UPSTREAM" <<UPSTREAM_EOF
# Auto-generated: internal proxy to $BACKEND_URL
location /api/ {
    proxy_pass ${BACKEND_URL}/api/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_cache_bypass \$http_upgrade;
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}

location /api/capacity/ {
    proxy_pass ${BACKEND_URL}/api/capacity/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_cache_bypass \$http_upgrade;
    proxy_connect_timeout 120s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
}
UPSTREAM_EOF
fi

# --- CSP connect-src handling ---
if [ -n "$CSP_CONNECT_EXTRA" ]; then
  sed -i "s|CSP_CONNECT_EXTRA_PLACEHOLDER|${CSP_CONNECT_EXTRA}|g" "$CONF"
else
  sed -i "s| CSP_CONNECT_EXTRA_PLACEHOLDER||g" "$CONF"
fi

# Test hook: the shell unit test can't exec a real nginx.
if [ "${ENTRYPOINT_SKIP_NGINX:-0}" = "1" ]; then
  exit 0
fi

exec nginx -g 'daemon off;'
