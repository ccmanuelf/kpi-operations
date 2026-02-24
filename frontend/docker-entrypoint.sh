#!/bin/sh
set -e

# Replace Docker-internal backend URLs with production URL if BACKEND_URL is set
if [ -n "$BACKEND_URL" ]; then
  # Extract hostname from BACKEND_URL (e.g. "kpi-operations-api.onrender.com")
  BACKEND_HOST=$(echo "$BACKEND_URL" | sed 's|https://||; s|http://||; s|/.*||')

  sed -i "s|http://backend:8000|${BACKEND_URL}|g" /etc/nginx/conf.d/default.conf
  # Convert https:// to wss:// for WebSocket URLs
  WS_URL=$(echo "$BACKEND_URL" | sed 's|https://|wss://|; s|http://|ws://|')
  sed -i "s|ws://backend:8000|${WS_URL}|g" /etc/nginx/conf.d/default.conf

  # For HTTPS upstream on external hosts, nginx needs:
  # 1. DNS resolver (can't resolve external hostnames without it)
  # 2. proxy_ssl_server_name on (sends SNI for Cloudflare/Render TLS)
  # 3. Host header set to the backend hostname (not the frontend hostname)
  sed -i '/proxy_set_header Host \$host;/c\        proxy_set_header Host '"${BACKEND_HOST}"';' /etc/nginx/conf.d/default.conf
  # Add resolver and SSL SNI to all location blocks that proxy
  sed -i '/proxy_pass https:\/\//i\        resolver 8.8.8.8 8.8.4.4 valid=30s;\n        proxy_ssl_server_name on;' /etc/nginx/conf.d/default.conf
fi

# Replace CSP placeholder with additional allowed origins (or remove it)
if [ -n "$CSP_CONNECT_EXTRA" ]; then
  sed -i "s|CSP_CONNECT_EXTRA_PLACEHOLDER|${CSP_CONNECT_EXTRA}|g" /etc/nginx/conf.d/default.conf
else
  sed -i "s| CSP_CONNECT_EXTRA_PLACEHOLDER||g" /etc/nginx/conf.d/default.conf
fi

exec nginx -g 'daemon off;'
