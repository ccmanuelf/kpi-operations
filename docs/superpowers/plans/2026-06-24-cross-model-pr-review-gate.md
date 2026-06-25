# Cross-Model PR Review Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/cross-review` slash command that runs an adversarial DeepSeek-Reasoner pass on the PR diff, enforced at the PR boundary by a PreToolUse hook that blocks `gh pr create`/`gh pr merge` until the review ran for the current HEAD.

**Architecture:** Four isolated units — two deterministic shell scripts (a marker writer and a gate checker, both unit-tested), one hook wiring entry in project `.claude/settings.json`, and one slash-command prompt that orchestrates the DeepSeek call. The review is advisory; the hook only enforces that a review *ran for this exact commit*, never that it "passed." Composition only — the built-in `/code-review` is never modified.

**Tech Stack:** Bash, `jq` (installed, allow-listed), `git`, Claude Code PreToolUse hooks, the `mcp__chat-dsreasoner__chat-with-deepseek-reasoner` MCP tool (called from inside the session by the slash command).

## Global Constraints

- **Workflow tooling only** — no change to backend/frontend application code.
- **Never modify the built-in `/code-review`** — compose around it.
- **Judge model is DeepSeek Reasoner** (`mcp__chat-dsreasoner__chat-with-deepseek-reasoner`); Codestral is not used (lost the empirical probe).
- **Marker keyed to full HEAD sha**, stored under `.git/cross-review/<sha>.json` (never committed; `.git/` is local-only).
- **Marker dir is overridable** via `CROSS_REVIEW_DIR` env (default `.git/cross-review`) — required for testability.
- **Hook is project-scoped** in `.claude/settings.json` (NOT global `~/.claude/settings.json`).
- **Advisory gate:** the gate checks ran-for-this-sha, never content pass/fail. Human stays the judge.
- **Files organization:** scripts in `scripts/`, tests in `tests/scripts/`, command in `.claude/commands/`. Never write working files to repo root.
- **Branch:** `feat/cross-review-gate` (already created; spec already committed there).

## File Structure

| File | Responsibility |
|---|---|
| `scripts/cross-review-mark.sh` | Write the HEAD-keyed marker JSON (`reviewed`/`skipped` mode). |
| `scripts/cross-review-gate.sh` | PreToolUse gate: allow non-`gh pr create/merge`; for those, allow iff a marker exists for HEAD, else block (exit 2). |
| `tests/scripts/test_cross_review_mark.sh` | Unit test for the marker writer. |
| `tests/scripts/test_cross_review_gate.sh` | Unit test for the gate (exit codes per marker state). |
| `.claude/settings.json` | Add one PreToolUse(Bash) hook entry routing to the gate script. |
| `.claude/commands/cross-review.md` | The `/cross-review` slash command (diff → DeepSeek → present → mark). |

---

### Task 1: Marker writer script

**Files:**
- Create: `scripts/cross-review-mark.sh`
- Test: `tests/scripts/test_cross_review_mark.sh`

**Interfaces:**
- Consumes: nothing.
- Produces: `scripts/cross-review-mark.sh <mode> [reason]`, `mode` ∈ {`reviewed`,`skipped`}. Env: `CROSS_REVIEW_DIR` (default `.git/cross-review`), `CROSS_REVIEW_MODEL` (default `deepseek-reasoner`). Writes `$CROSS_REVIEW_DIR/<HEAD-sha>.json` = `{sha,timestamp,model,mode[,reason]}`. Prints the marker path on stdout. Exit 0 success; exit 1 on invalid mode.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/test_cross_review_mark.sh`:

```bash
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/scripts/test_cross_review_mark.sh`
Expected: FAIL (script `scripts/cross-review-mark.sh` does not exist yet → "No such file").

- [ ] **Step 3: Write minimal implementation**

Create `scripts/cross-review-mark.sh`:

```bash
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
```

- [ ] **Step 4: Make executable and run test to verify it passes**

Run: `chmod +x scripts/cross-review-mark.sh && bash tests/scripts/test_cross_review_mark.sh`
Expected: all lines `PASS:`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/cross-review-mark.sh tests/scripts/test_cross_review_mark.sh
git commit -m "feat(cross-review): HEAD-keyed marker writer + unit test"
```

---

### Task 2: Gate checker script

**Files:**
- Create: `scripts/cross-review-gate.sh`
- Test: `tests/scripts/test_cross_review_gate.sh`

**Interfaces:**
- Consumes: marker layout from Task 1 (`$CROSS_REVIEW_DIR/<HEAD-sha>.json`), same `CROSS_REVIEW_DIR` default.
- Produces: a PreToolUse hook command. Reads hook JSON on stdin; extracts `.tool_input.command`. Exit 0 = allow; exit 2 = block (stderr shown to Claude). Blocks only when the command is `gh pr create`/`gh pr merge` AND no marker exists for HEAD.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/test_cross_review_gate.sh`:

```bash
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
run() { echo "{\"tool_input\":{\"command\":\"$1\"}}" | (cd "$SCRIPT_DIR" && "$GATE"); }

# Non-gh command always allowed
run "git status" >/dev/null 2>&1; [ $? -eq 0 ]; assert "non-gh command allowed" $?
# gh pr view is not create/merge -> allowed
run "gh pr view 12" >/dev/null 2>&1; [ $? -eq 0 ]; assert "gh pr view allowed" $?
# gh pr create with no marker -> blocked (exit 2)
run "gh pr create --fill" >/dev/null 2>&1; [ $? -eq 2 ]; assert "gh pr create blocked without marker" $?
# gh pr merge with no marker -> blocked (exit 2)
run "gh pr merge 12 --squash" >/dev/null 2>&1; [ $? -eq 2 ]; assert "gh pr merge blocked without marker" $?
# create marker for HEAD -> now allowed
echo '{}' > "$TMP/$SHA.json"
run "gh pr create --fill" >/dev/null 2>&1; [ $? -eq 0 ]; assert "gh pr create allowed with marker" $?
run "gh pr merge 12 --squash" >/dev/null 2>&1; [ $? -eq 0 ]; assert "gh pr merge allowed with marker" $?

rm -rf "$TMP"
exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/scripts/test_cross_review_gate.sh`
Expected: FAIL (script does not exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `scripts/cross-review-gate.sh`:

```bash
#!/usr/bin/env bash
# PreToolUse gate: require a cross-review marker for HEAD before `gh pr create|merge`.
# Reads the hook JSON on stdin. Exit 0 = allow, exit 2 = block.
set -uo pipefail

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"

# Only gate PR creation/merge; everything else passes through.
if ! printf '%s' "$cmd" | grep -Eq 'gh[[:space:]]+pr[[:space:]]+(create|merge)'; then
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
```

- [ ] **Step 4: Make executable and run test to verify it passes**

Run: `chmod +x scripts/cross-review-gate.sh && bash tests/scripts/test_cross_review_gate.sh`
Expected: all `PASS:`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/cross-review-gate.sh tests/scripts/test_cross_review_gate.sh
git commit -m "feat(cross-review): PR-boundary gate script + unit test"
```

---

### Task 3: Wire the PreToolUse hook

**Files:**
- Modify: `.claude/settings.json` (the `hooks.PreToolUse` array, currently `[]`)

**Interfaces:**
- Consumes: `scripts/cross-review-gate.sh` from Task 2.
- Produces: a live gate — every Bash tool call is routed through the gate script; only `gh pr create/merge` without a marker is blocked.

- [ ] **Step 1: Edit settings.json**

Replace `"PreToolUse": [],` with:

```json
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/scripts/cross-review-gate.sh"
          }
        ]
      }
    ],
```

- [ ] **Step 2: Validate JSON**

Run: `jq . .claude/settings.json > /dev/null && echo OK`
Expected: `OK` (no parse error).

- [ ] **Step 3: Verify the gate path resolves and is executable**

Run: `test -x scripts/cross-review-gate.sh && echo "gate executable"`
Expected: `gate executable`

- [ ] **Step 4: Manual block check (no marker for a throwaway sha)**

Simulate the hook input against an empty marker dir:

Run: `CROSS_REVIEW_DIR="$(mktemp -d)" bash -c 'echo "{\"tool_input\":{\"command\":\"gh pr create --fill\"}}" | scripts/cross-review-gate.sh; echo "exit=$?"'`
Expected: `BLOCKED:` message on stderr and `exit=2`.

- [ ] **Step 5: Commit**

```bash
git add .claude/settings.json
git commit -m "feat(cross-review): wire PreToolUse gate on gh pr create/merge"
```

> NOTE: The hook only fires for the agent's Bash tool calls. A PR opened by the human directly (GitHub web, or a `!`-prefixed manual command) bypasses the gate by design — this is an advisory, human-in-the-loop gate, not a hard security control. This limitation is intentional and documented in the spec.

---

### Task 4: The `/cross-review` slash command

**Files:**
- Create: `.claude/commands/cross-review.md`

**Interfaces:**
- Consumes: `mcp__chat-dsreasoner__chat-with-deepseek-reasoner` (MCP, session-local); `scripts/cross-review-mark.sh` from Task 1.
- Produces: the `/cross-review` user command. On success: DeepSeek findings shown inline + a `reviewed` marker for HEAD. With `--skip "reason"`: a `skipped` marker (no model call).

- [ ] **Step 1: Create the command file**

Create `.claude/commands/cross-review.md`:

```markdown
---
description: Adversarial cross-model (DeepSeek Reasoner) review of the PR diff; writes the HEAD marker that unblocks gh pr create/merge.
---

You are running the cross-model PR review gate. Arguments: `$ARGUMENTS`.

## Mode A — skip (only if arguments start with `--skip`)

If `$ARGUMENTS` begins with `--skip`, treat the remainder (quoted text) as the reason.
Do NOT call any model. Run:

    scripts/cross-review-mark.sh skipped "<reason>"

Then tell the user the PR boundary is unblocked for the current HEAD and that the skip
was recorded with the reason. Stop.

## Mode B — review (default)

1. Compute the PR diff against the merge base with main:

       git fetch -q origin main 2>/dev/null || true
       BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main)
       git diff "$BASE"..HEAD

   If the diff is empty, tell the user there is nothing to review and stop (do NOT mark).

2. Size-guard: get the changed-line count with `git diff --stat "$BASE"..HEAD`.
   - If total changed lines ≤ 1500: send the whole diff in one DeepSeek call.
   - If > 1500: split by file (`git diff "$BASE"..HEAD -- <file>` per changed file) and
     send one DeepSeek call per file, so no single prompt is truncated.

3. For each chunk, call `mcp__chat-dsreasoner__chat-with-deepseek-reasoner` with:

       You are an adversarial code reviewer. Review this diff and list ONLY real
       correctness/logic bugs, security issues, and data-integrity risks as terse
       bullets. No style nits, no filler, no praise. If you find nothing real, say
       "No real issues found." Diff:
       <chunk>

4. Present DeepSeek's findings to the user inline, grouped by file if chunked. Add a one-
   line summary: number of real issues raised. Do not auto-fix anything.

5. If at least one DeepSeek call returned a response, record the review:

       scripts/cross-review-mark.sh reviewed

   Then tell the user the PR boundary is unblocked for the current HEAD.

6. If EVERY DeepSeek call failed/errored (MCP unreachable), do NOT write a marker.
   Tell the user the review could not run and that the PR stays blocked; suggest
   retrying, or `/cross-review --skip "<reason>"` to bypass with the reason logged.
```

- [ ] **Step 2: Verify the command is discoverable**

Run: `test -f .claude/commands/cross-review.md && head -1 .claude/commands/cross-review.md`
Expected: prints the `---` frontmatter opening line.

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/cross-review.md
git commit -m "feat(cross-review): /cross-review slash command (DeepSeek pass + marker)"
```

---

### Task 5: End-to-end verification + workflow note

**Files:**
- Modify: `CLAUDE.md` (add a one-paragraph note under the workflow/verification section)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a verified, documented gate.

- [ ] **Step 1: Run both unit suites**

Run: `bash tests/scripts/test_cross_review_mark.sh && bash tests/scripts/test_cross_review_gate.sh`
Expected: all `PASS:`, exit 0 for both.

- [ ] **Step 2: Live gate verification (in-session)**

In this Claude Code session, with the hook active and NO marker for HEAD, attempt:

Run: `gh pr create --fill --draft`
Expected: the call is BLOCKED by the hook with the `BLOCKED: no cross-model review...` message (the agent sees stderr and does not create the PR).

- [ ] **Step 3: Run the command, then confirm the allow path (without opening a stray PR)**

Invoke `/cross-review`. Confirm DeepSeek findings appear inline and a marker file exists:

Run: `ls .git/cross-review/$(git rev-parse HEAD).json`
Expected: the marker path prints (file exists).

Confirm the gate now ALLOWS `gh pr create` for this HEAD by exercising the gate script
directly (avoids actually opening a draft PR during verification):

Run: `echo '{"tool_input":{"command":"gh pr create --fill"}}' | scripts/cross-review-gate.sh; echo "exit=$?"`
Expected: `exit=0` (allowed, because the marker from `/cross-review` now exists for HEAD).

- [ ] **Step 4: Add the workflow note to CLAUDE.md**

Add this paragraph under the "Agent Behavior Defaults" / verification area:

```markdown
- **Cross-model PR gate.** Before `gh pr create`/`gh pr merge`, a PreToolUse hook
  (`scripts/cross-review-gate.sh`) requires a cross-model review for the current HEAD.
  Run `/cross-review` to get an adversarial DeepSeek-Reasoner pass on the PR diff (it
  writes `.git/cross-review/<sha>.json`); `/cross-review --skip "<reason>"` bypasses with
  the reason logged. Advisory only — it enforces that a review ran for this commit, not
  that it passed. Complements (does not replace) `/code-review`.
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(cross-review): document the cross-model PR gate in CLAUDE.md"
```

---

## Notes for the implementer

- `date -u +%Y-%m-%dT%H:%M:%SZ` is portable on macOS (BSD `date`) and Linux — no `-d` flags used.
- The gate matches with `grep -Eq 'gh[[:space:]]+pr[[:space:]]+(create|merge)'`, so it still catches an `rtk gh pr ...` rewrite (substring match). A `gh pr create` appearing inside an unrelated string is a harmless false-positive (an extra review).
- Do not add this gate to CI — MCP tools are session-local; CI integration is explicitly out of scope (see spec).
- Keep `scripts/cross-review-*.sh` POSIX-bash; do not introduce a `bats` dependency (not installed).
