#!/bin/sh
set -e

# Replace Docker-internal backend URLs with production URL if BACKEND_URL is set
if [ -n "$BACKEND_URL" ]; then
  sed -i "s|http://backend:8000|${BACKEND_URL}|g" /etc/nginx/conf.d/default.conf
  # Convert https:// to wss:// for WebSocket URLs
  WS_URL=$(echo "$BACKEND_URL" | sed 's|https://|wss://|; s|http://|ws://|')
  sed -i "s|ws://backend:8000|${WS_URL}|g" /etc/nginx/conf.d/default.conf

  # Nginx needs a resolver for external hostnames (not needed for Docker-internal names)
  # Use Google DNS as resolver with 30s cache
  sed -i '/location \/api\//a\        resolver 8.8.8.8 8.8.4.4 valid=30s;' /etc/nginx/conf.d/default.conf
fi

# Replace CSP placeholder with additional allowed origins (or remove it)
if [ -n "$CSP_CONNECT_EXTRA" ]; then
  sed -i "s|CSP_CONNECT_EXTRA_PLACEHOLDER|${CSP_CONNECT_EXTRA}|g" /etc/nginx/conf.d/default.conf
else
  sed -i "s| CSP_CONNECT_EXTRA_PLACEHOLDER||g" /etc/nginx/conf.d/default.conf
fi

exec nginx -g 'daemon off;'
