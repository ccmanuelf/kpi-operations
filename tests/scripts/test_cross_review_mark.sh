#!/usr/bin/env bash
# Unit test for scripts/cross-review-mark.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
MARK="$SCRIPT_DIR/scripts/cross-review-mark.sh"
fail=0
assert() { # assert <desc> <cond-exit>
  if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi
}

TMP="$(mktemp -d)"
export CROSS_REVIEW_DIR="$TMP"
SHA="$(git -C "$SCRIPT_DIR" rev-parse HEAD)"

# Case 1: reviewed marker is written with correct fields
out="$(cd "$SCRIPT_DIR" && "$MARK" reviewed)"
[ -f "$TMP/$SHA.json" ]; assert "reviewed: marker file created" $?
[ "$(jq -r '.mode' "$TMP/$SHA.json")" = "reviewed" ]; assert "reviewed: mode=reviewed" $?
[ "$(jq -r '.model' "$TMP/$SHA.json")" = "deepseek-reasoner" ]; assert "reviewed: default model" $?
[ "$(jq -r '.sha' "$TMP/$SHA.json")" = "$SHA" ]; assert "reviewed: sha matches HEAD" $?

# Case 2: skipped marker records the reason
(cd "$SCRIPT_DIR" && "$MARK" skipped "mcp unreachable") >/dev/null
[ "$(jq -r '.mode' "$TMP/$SHA.json")" = "skipped" ]; assert "skipped: mode=skipped" $?
[ "$(jq -r '.reason' "$TMP/$SHA.json")" = "mcp unreachable" ]; assert "skipped: reason recorded" $?

# Case 3: invalid mode exits non-zero
(cd "$SCRIPT_DIR" && "$MARK" bogus) >/dev/null 2>&1; [ $? -ne 0 ]; assert "invalid mode exits non-zero" $?

rm -rf "$TMP"
exit $fail
