#!/usr/bin/env bash
# Unit test for scripts/cross-review-gate.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
GATE="$SCRIPT_DIR/scripts/cross-review-gate.sh"
fail=0
assert() { if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi; }

TMP="$(mktemp -d)"
export CROSS_REVIEW_DIR="$TMP"
SHA="$(git -C "$SCRIPT_DIR" rev-parse HEAD)"
# Build the hook JSON with jq so commands containing quotes (e.g. a commit
# message) reach the gate intact instead of breaking raw string interpolation.
run() { jq -n --arg c "$1" '{tool_input:{command:$c}}' | (cd "$SCRIPT_DIR" && "$GATE"); }

# Non-gh command always allowed
run "git status" >/dev/null 2>&1; [ $? -eq 0 ]; assert "non-gh command allowed" $?
# gh pr view is not create/merge -> allowed
run "gh pr view 12" >/dev/null 2>&1; [ $? -eq 0 ]; assert "gh pr view allowed" $?
# gh pr create with no marker -> blocked (exit 2)
run "gh pr create --fill" >/dev/null 2>&1; [ $? -eq 2 ]; assert "gh pr create blocked without marker" $?
# gh pr merge with no marker -> blocked (exit 2)
run "gh pr merge 12 --squash" >/dev/null 2>&1; [ $? -eq 2 ]; assert "gh pr merge blocked without marker" $?
# rtk-rewritten command is still caught by the substring match
run "rtk gh pr create --fill" >/dev/null 2>&1; [ $? -eq 2 ]; assert "rtk-prefixed gh pr create blocked" $?
# commit message that merely mentions the phrase must NOT be blocked
run 'git commit -m "wire gate on gh pr merge"' >/dev/null 2>&1; [ $? -eq 0 ]; assert "gh pr in quoted arg allowed" $?
# real invocation after a separator IS gated
run "echo done && gh pr create --fill" >/dev/null 2>&1; [ $? -eq 2 ]; assert "gh pr create after && blocked" $?
# env-var / command / env wrappers must NOT let a real invocation slip past
run "FOO=1 gh pr create --fill" >/dev/null 2>&1; [ $? -eq 2 ]; assert "env-prefixed gh pr create blocked" $?
run "GH_TOKEN=x gh pr merge 5" >/dev/null 2>&1; [ $? -eq 2 ]; assert "GH_TOKEN-prefixed gh pr merge blocked" $?
run "command gh pr create" >/dev/null 2>&1; [ $? -eq 2 ]; assert "command-wrapped gh pr create blocked" $?
# create marker for HEAD -> now allowed
echo '{}' > "$TMP/$SHA.json"
run "gh pr create --fill" >/dev/null 2>&1; [ $? -eq 0 ]; assert "gh pr create allowed with marker" $?
run "gh pr merge 12 --squash" >/dev/null 2>&1; [ $? -eq 0 ]; assert "gh pr merge allowed with marker" $?

rm -rf "$TMP"
exit $fail
