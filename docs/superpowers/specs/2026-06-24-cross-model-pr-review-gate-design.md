# Cross-Model PR Review Gate (`/cross-review`) — Design

**Date:** 2026-06-24
**Status:** Approved (brainstorm), pending implementation plan
**Origin:** Evaluation of looper / superdense / coop — all three converge on a
"cross-model council" idea (a different model family judges before commit). This
spec lifts only that idea into the existing workflow. It is **workflow tooling,
not application code** — nothing here touches the FastAPI/Vue KPI app.

## Problem

The current review gate (`/code-review`, CI's 4 required checks) is **single-model**:
Claude reviews Claude's work. Self-evaluation bias is exactly the failure mode the
three surveyed tools warn about. We want an adversarial second opinion from a
*different model family* before a PR is created or merged — without new infra,
without per-push cost in CI, and without the gate being able to silently lapse.

## Constraints (these shaped the design)

1. **MCP tools are session-local.** Only the in-session model can call
   `mcp__chat-dsreasoner__chat-with-deepseek-reasoner`. A shell hook cannot invoke
   MCP. Therefore the review itself MUST run inside a Claude Code session; a hook
   can only *enforce/remind* that it happened. This rules out fully-headless CI
   review using the wired MCP tools, and rules out fully-autonomous background runs.
2. **Do not fork the built-in `/code-review`.** It is a plugin/built-in skill;
   editing its files means changes are wiped on upgrade and the gate silently dies.
   We compose around it, never modify it.
3. **Zero new infra.** Two non-Claude families are already wired as MCP tools:
   Codestral (Mistral) and DeepSeek Reasoner. No API keys, services, or CI plumbing.

## Model selection (empirical)

Both wired models were probed twice each with identical adversarial-review prompts
(a Python OEE function with a divide-by-zero / OEE>100 bug; a TS pagination function
with an off-by-one / negative-index bug). Intervals include equal harness overhead;
the relative gap is the signal:

| Model | Round 1 | Round 2 | Quality |
|---|---|---|---|
| Codestral | ~25.2s | ~25.0s | Vaguer; filler bullets ("floating-point precision") |
| **DeepSeek Reasoner** | ~12.7s | ~12.4s | ~2× faster; tighter; caught the domain bug (OEE>100), negative-index slice, NaN indices |

**Decision: DeepSeek Reasoner** — faster AND higher signal, stable across both rounds.
Codestral is not used. (Revisit only if DeepSeek's MCP reliability degrades.)

## Behavior

Semi-automatic, human-in-the-loop:

- The review is **advisory**. The hook enforces that a review *ran for this exact
  commit*, never that it "passed." The human stays the judge.
- Enforcement point is the **PR boundary** (`gh pr create` AND `gh pr merge`), so
  pushing fixes after CI invalidates a stale review and forces a re-run.
- Marker is keyed to the **HEAD sha**, so any new commit invalidates it.

## Components (4 small, isolated units)

### 1. `.claude/commands/cross-review.md` — the slash command
A project-scoped slash command (a prompt file; explicitly invoked, so a command, not
a model-invoked skill). When run, it instructs the in-session model to:

1. Resolve the PR diff: `git diff $(git merge-base HEAD origin/main)..HEAD`.
2. **Size-guard:** if changed lines exceed the threshold (~1500), review per-file and
   concatenate results rather than truncating a single oversized prompt.
3. Send the diff to DeepSeek Reasoner via
   `mcp__chat-dsreasoner__chat-with-deepseek-reasoner` with an adversarial-review
   prompt (hunt correctness/logic bugs; terse findings; no filler).
4. Present DeepSeek's findings inline to the user.
5. Write the marker for the current HEAD sha (see §2).

Flags:
- `--skip "reason"` — escape hatch. Writes the marker *with the logged reason* so a
  flaky/unreachable MCP cannot hard-block a ship. The skip is on the record.

**Open sub-choice (decide in plan):** whether the command also runs the built-in
`/code-review` (Claude pass) first, or stays purely the DeepSeek pass with
`/code-review` run separately. Default leaning: keep it purely DeepSeek (single
responsibility); the human runs `/code-review` as they already do.

### 2. Marker — `.git/cross-review.<sha>`
- Path: `.git/cross-review.<full-head-sha>`. Lives under `.git/`, so never committed
  and naturally local-only.
- Content: JSON `{ sha, timestamp, model, mode: "reviewed" | "skipped", reason? }`.
- Invalidation: implicit — a new commit changes HEAD sha, so the old marker no longer
  matches.

### 3. `scripts/cross-review-gate.sh` — the gate logic
- Invoked by the PreToolUse hook; receives the hook's tool-input JSON on stdin.
- Parses the intended Bash command. If it is NOT `gh pr create` / `gh pr merge`,
  exit 0 (allow, no-op).
- If it IS, compute `git rev-parse HEAD`; check `.git/cross-review.<sha>` exists.
  - Exists → exit 0 (allow).
  - Missing → exit 2 (block) with a stderr message: run `/cross-review` first
    (include the HEAD sha).
- Keep logic in the script (not inline JSON in settings) so it is readable and
  independently testable.

### 4. PreToolUse hook — `.claude/settings.json` (project-scoped)
- Project `.claude/settings.json`, versioned with the repo (NOT global
  `~/.claude/settings.json` — this gate is repo-specific, unlike the global RTK hook).
- Matcher: `Bash`. The script does the fine-grained `gh pr create|merge` matching, so
  the hook simply routes Bash calls to `scripts/cross-review-gate.sh`.

## Reliability guards

- **MCP unreachable:** the command reports the failure and does NOT write the marker
  → PR stays blocked. The `--skip "reason"` escape hatch writes a logged marker so a
  flaky model never hard-blocks shipping, but the bypass is recorded.
- **Oversized diff:** per-file review + concatenation instead of truncation (DeepSeek
  window is comfortably larger than the ~1500-line threshold; PRs here are surgical).
- **Advisory-only:** the gate checks *ran-for-this-sha*, never content pass/fail.

## Out of scope (YAGNI)

- No CI integration (MCP is session-local; CI plumbing rejected).
- No Codestral (lost the probe).
- No auto-fix / auto-apply of findings.
- No second-family review on every commit — only at the PR boundary.
- No changes to the KPI application code.

## Success criteria

1. Running `/cross-review` on a branch with changes produces a DeepSeek adversarial
   review inline and writes `.git/cross-review.<HEAD-sha>`.
2. `gh pr create` / `gh pr merge` is **blocked** by the hook when no marker exists for
   HEAD, with a message naming the sha and the remedy.
3. After `/cross-review` (or `--skip "reason"`), the same `gh pr` command is allowed.
4. A new commit (HEAD moves) re-blocks until `/cross-review` is re-run.
5. `scripts/cross-review-gate.sh` is unit-testable: feed it sample tool-input JSON +
   marker states, assert exit codes (0 allow / 2 block) — no live MCP needed.
6. With DeepSeek's MCP forced unreachable, `/cross-review` does not write a marker and
   the PR stays blocked; `--skip "reason"` unblocks with the reason recorded.
