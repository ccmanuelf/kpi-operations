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
