#!/bin/sh
set -e

# Replace CSP placeholder with additional allowed origins (or remove it)
if [ -n "$CSP_CONNECT_EXTRA" ]; then
  sed -i "s|CSP_CONNECT_EXTRA_PLACEHOLDER|${CSP_CONNECT_EXTRA}|g" /etc/nginx/conf.d/default.conf
else
  sed -i "s| CSP_CONNECT_EXTRA_PLACEHOLDER||g" /etc/nginx/conf.d/default.conf
fi

exec nginx -g 'daemon off;'
