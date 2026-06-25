#!/usr/bin/env bash
# PreToolUse gate: require a cross-review marker for HEAD before `gh pr create|merge`.
# Reads the hook JSON on stdin. Exit 0 = allow, exit 2 = block.
set -uo pipefail

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"

# Only gate PR creation/merge; everything else passes through.
# Anchor to a command position (start of string or after a shell separator),
# optionally rtk-prefixed, so the phrase inside a quoted arg (e.g. a commit
# message) does NOT falsely match. BSD-grep-safe (no \b) for macOS.
if ! printf '%s' "$cmd" | grep -Eq '(^|[;&|(])[[:space:]]*(rtk[[:space:]]+)?gh[[:space:]]+pr[[:space:]]+(create|merge)([[:space:]]|$)'; then
  exit 0
fi

dir="${CROSS_REVIEW_DIR:-.git/cross-review}"
sha="$(git rev-parse HEAD 2>/dev/null || echo unknown)"

if [ -f "$dir/$sha.json" ]; then
  exit 0
fi

echo "BLOCKED: no cross-model review recorded for HEAD $sha." >&2
echo "Run /cross-review (DeepSeek adversarial pass) before opening/merging this PR." >&2
echo "If the model is unreachable, use /cross-review --skip \"<reason>\"." >&2
exit 2
