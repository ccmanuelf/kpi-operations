#!/usr/bin/env bash
# Write a cross-review marker keyed to the current HEAD sha.
# Usage: cross-review-mark.sh <reviewed|skipped> [reason]
set -euo pipefail

mode="${1:-}"
reason="${2:-}"
case "$mode" in
  reviewed|skipped) ;;
  *) echo "usage: cross-review-mark.sh <reviewed|skipped> [reason]" >&2; exit 1 ;;
esac

dir="${CROSS_REVIEW_DIR:-.git/cross-review}"
model="${CROSS_REVIEW_MODEL:-deepseek-reasoner}"
sha="$(git rev-parse HEAD)"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$dir"
marker="$dir/$sha.json"
jq -n --arg sha "$sha" --arg ts "$ts" --arg model "$model" \
      --arg mode "$mode" --arg reason "$reason" \
  '{sha:$sha, timestamp:$ts, model:$model, mode:$mode}
   + (if $reason == "" then {} else {reason:$reason} end)' > "$marker"
echo "$marker"
