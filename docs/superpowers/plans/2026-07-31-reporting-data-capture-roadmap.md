# Reporting Data-Capture Roadmap (docs-only PR) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the docs-only PR defined in §7 of the approved roadmap spec: restructure `docs/reporting/reporting-capabilities-and-gaps.md` §5 into an Active lane + Deferred remainder, record the 2026-07-30 management decision in §1, and fix every in-doc cross-reference made stale by the restructure.

**Architecture:** One markdown file is edited (`docs/reporting/reporting-capabilities-and-gaps.md`); the roadmap spec (`docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md`) is already committed on branch `docs/reporting-data-capture-roadmap`. No code, no tests, no migrations. Verification is grep-based consistency checking (no stale phrases survive) plus CI.

**Tech Stack:** Markdown; git; GitHub PR pipeline (7 required checks); /cross-review gate.

## Global Constraints

- Docs-only: NO changes outside `docs/`.
- Branch: `docs/reporting-data-capture-roadmap` (already exists, spec committed at HEAD).
- Committed positions in §1 of the living doc are permanent — extend, never reword or delete them.
- Concept-register grades in §4 are NOT re-graded in this PR (grades move only when a cycle lands).
- The `/cross-review` HEAD marker is required before `gh pr create` (PreToolUse hook enforces it); a new commit invalidates the marker, so run it after the final commit.
- Merge is user-confirmed only — create the PR, never merge it.

---

### Task 1: Restructure the living doc

**Files:**
- Modify: `docs/reporting/reporting-capabilities-and-gaps.md` (§1, §3 three rows, §4 tail, §5 wholesale)

**Interfaces:**
- Consumes: approved spec `docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md` (§2 decisions, §3 cycles, §4 capture policy).
- Produces: the restructured living doc that Cycle 1's brainstorm will ground in.

- [ ] **Step 1: Record the management decision in §1**

Append this paragraph at the end of §1 (after the "No reports without underlying data" paragraph, before `## 2.`):

```markdown
**Capture-first focus (management decision, 2026-07-30).** No further client report samples are coming — management chose this deliberately to avoid Excel reconstruction. The engagement shifts to **data capture** for the five key operations questions (§4): downtime cause taxonomy, justified-delay classification, and labor-hours accounting, followed by a pivot/summarization layer built once over the enriched data. Sequencing lives in §5; roadmap spec: `docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md`.
```

- [ ] **Step 2: Update the three now-sequenced rows in the §3 gap register**

Replace these three table rows exactly:

Old:
```markdown
| Pivot/summarization layer | **Future spec #1** — blocked on remaining samples + concept register | Deferred |
```
New:
```markdown
| Pivot/summarization layer | **Active lane — Cycle 4** (§5); the remaining-samples blocker was dissolved by the 2026-07-30 management decision | Sequenced (§5) |
```

Old:
```markdown
| Downtime cause taxonomy | **Future spec** — small, high leverage for Q2 | Deferred |
```
New:
```markdown
| Downtime cause taxonomy | **Active lane — Cycle 1** (§5) — small, high leverage for Q2 | Sequenced (§5) |
```

Old:
```markdown
| Labor-hours accounting (OT tiers, direct/indirect, billed vs available) | **Future spec** — prerequisite for full Q1 | Deferred |
```
New:
```markdown
| Labor-hours accounting (OT tiers, direct/indirect, billed vs available) | **Active lane — Cycle 3** (§5) — prerequisite for full Q1 | Sequenced (§5) |
```

(The three email/scheduler rows keep their "Defer to report-subscriptions spec" decisions — report subscriptions is in the deferred remainder, so their text stays true.)

- [ ] **Step 3: Fix the stale §4 cross-reference**

In "How to update this register", replace:

Old:
```markdown
it is routed to the deferred-spec queue (§5) as a capture-first item
```
New:
```markdown
it is routed to the roadmap's deferred remainder (§5) as a capture-first item
```

- [ ] **Step 4: Replace §5 wholesale**

Replace everything from `## 5. Deferred-spec queue` to end-of-file with:

```markdown
## 5. Roadmap — active lane and deferred remainder

Sequenced per the approved roadmap spec (`docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md`, 2026-07-31). Every cycle still requires its own brainstorm→spec cycle before any build.

### Active lane (in order)

1. **Cycle 1 — Downtime cause taxonomy** (Q2; smallest, highest leverage): controlled vocabulary — **machine / materials / scheduling / attendance / other**, with NPT sub-buckets — over the existing free-form `root_cause_category` on `DowntimeEntry`; entry UI becomes a select; migration maps confidently-matchable free-form values, everything else defaults to `uncategorized`.
2. **Cycle 2 — Justified-delay flag** (Q3): justified/unjustified classification plus reason on late work orders; delivery performance becomes reportable both gross and net-of-justified (the concept behind PGI's exclusion, never its layout).
3. **Cycle 3 — Labor-hours accounting** (Q1; the big capture): OT tiers (Normal/Double/Triple — Mexican labor law, structural), direct/indirect classification on `Employee`, billed vs available-for-efficiency hours. Expected 2 PRs — capture model + entry UI, then derived Q1 metrics; the split is decided in that cycle's spec.
4. **Cycle 4 — Pivot/summarization layer** (largest; built once, over the enriched data): pre-defined time buckets (week/month/quarter/year), pre-defined groupings/categorizations, cross-metric comparison on the common hours basis (units ↔ SAM-earned hours ↔ operators ↔ attendance hours), every summary downloadable as its underlying data. Expected 2–3 PRs; split decided in that cycle's spec.

**Capture policy (uniform across all cycles):** new capture fields ship optional or defaulted (e.g. `uncategorized`) and never block existing entry flows at introduction; each capture surface gets a completeness indicator; flip-to-required happens per field once completeness ≥ 90 % over a trailing 30 days AND management confirms the shop-floor workflow has adapted (the flip is its own small change); the demo seeder is updated in the same cycle that introduces a field.

### Deferred remainder

Parked until management asks or an active-lane cycle surfaces a hard dependency:

- **Report subscriptions** — persisted email config (DB table replacing the in-memory `_email_configs`), `include_*` toggles actually consumed by the generators, scheduler honoring the configured frequency (daily/weekly/monthly) and recipients.
- **Model extensions** *(capture-first)* — shipment #, material-batch traceability, cut-quantity capture, plant/module hierarchy, operator-level production. Same standing rule: capture first, report after.
```

- [ ] **Step 5: Verify no stale phrases survive**

Run:
```bash
rtk proxy grep -n "Deferred-spec queue\|deferred-spec queue\|blocked on remaining samples\|Future spec" docs/reporting/reporting-capabilities-and-gaps.md
```
Expected: NO matches. Any match = a missed edit; fix it and re-run.

- [ ] **Step 6: Verify doc structure is intact**

Run:
```bash
rtk proxy grep -n "^## " docs/reporting/reporting-capabilities-and-gaps.md
```
Expected: exactly five `##` headings — `## 1. Committed positions`, `## 2. What works today — report catalog`, `## 3. Gap register — decisions`, `## 4. Concept register (living)`, `## 5. Roadmap — active lane and deferred remainder`.

- [ ] **Step 7: Commit**

```bash
git add docs/reporting/reporting-capabilities-and-gaps.md
git commit -m "docs(reporting): restructure §5 into active lane + deferred remainder per roadmap spec

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Cross-review and PR

**Files:**
- None modified (verification + PR only).

**Interfaces:**
- Consumes: branch `docs/reporting-data-capture-roadmap` with both commits (spec + living-doc restructure).
- Produces: an open PR against `main`; merge remains user-confirmed.

- [ ] **Step 1: Confirm the branch delta is docs-only**

Run:
```bash
git diff --stat main...HEAD
```
Expected: exactly three files, all under `docs/` — `docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md` (add), `docs/superpowers/plans/2026-07-31-reporting-data-capture-roadmap.md` (add), and `docs/reporting/reporting-capabilities-and-gaps.md` (modify). Anything else = stop and investigate.

- [ ] **Step 2: Run /cross-review** (main session — it is a user-invocable skill)

Run the `cross-review` skill to write the DeepSeek HEAD marker for the current commit. If the MCP is unreachable, use `/cross-review --skip "<reason>"` per the documented bypass.

- [ ] **Step 3: Push and create the PR**

```bash
git push -u origin docs/reporting-data-capture-roadmap
gh pr create --title "docs(reporting): data-capture roadmap — active lane + deferred remainder" --body "$(cat <<'EOF'
## Summary
- Adds the approved roadmap spec for the reporting data-capture engagement (4 cycles: downtime taxonomy → justified-delay flag → labor-hours accounting → pivot layer)
- Restructures `docs/reporting/reporting-capabilities-and-gaps.md` §5 from a deferred-spec queue into an **Active lane + Deferred remainder**
- Records the 2026-07-30 management decision (no further samples; capture-first focus) as a committed position in §1
- Updates the three now-sequenced §3 gap rows and the stale §4 cross-reference

Docs-only; no code, tests, or migrations. Concept-register grades are unchanged (they move only when cycles land).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Verify CI goes green, then hand off**

Run:
```bash
gh pr checks --watch
```
Expected: all 7 required checks pass (docs-only, so this is mechanical). Then report the PR URL to the user — merge is **user-confirmed only**.
