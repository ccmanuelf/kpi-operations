# Luna-Agent Handoff Governance Document Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write the governance/integration document at `docs/governance/luna-agent-handoff-governance.md` that defines how the Luna AI agent interacts with kpi-operations to assist humans without replacing them or deciding on their behalf.

**Architecture:** A single Markdown document with the approved 10 sections. It is grounded in the already-shipped kpi-operations guardrails (six-role model, uniform client-scope authz, supervisor-write-block) and the REST endpoint inventory; **no code changes**. Enforcement is Approach A — a GET-verb-based read-only allow-list Luna applies to itself. Verification is a spec-coverage + factual-accuracy review, not a test suite.

**Tech Stack:** Markdown only. Cross-checked against `backend/routes/**`, `backend/bootstrap/routers.py`, `backend/middleware/write_access.py`, and project memory.

## Global Constraints

- Deliverable path is exactly `docs/governance/luna-agent-handoff-governance.md` (create the new `docs/governance/` directory).
- **No code changes.** This is documentation + configuration guidance only. Do not modify any `.py`, test, or config file.
- **Identity model:** Luna acts **on-behalf-of the logged-in human** (their session/token); all shipped authz applies automatically and unchanged. State the borrowed-session trade-off and its containment (allow-list + audit log). Do NOT describe a dedicated Luna account or a new role — that was explicitly not chosen.
- **Scope:** read + insights/explanations only. Luna never writes, drafts, or submits. No proposal/draft mechanism (out of scope).
- **Enforcement (Approach A):** the allow-list is **HTTP GET verb-based**, fail-safe. A POST is never allowed — including the compute-only `POST /api/v2/simulation/validate` and `POST /api/shifts/check-overlap`. No carve-out exception (user signed off on the fail-safe default).
- **Operation catalog** must give **both** concrete endpoint paths **and** capability-level descriptions (user requirement). The configured allow-list is the source of truth; the document says so.
- **Three edge cases must appear explicitly:** (1) compute-only POSTs stay forbidden under the GET-only rule; (2) `/upload/csv` writes interleave with read resources → prefer verb-based over prefix-based matching; (3) `GET /api/reports/email-config` is allowed while its POST/PUT/test/send-manual siblings are forbidden.
- **Single-tenancy:** Luna has its **own DB container** per the VM deploy runbook and reaches kpi-operations **only via the REST API** — never sharing/reading kpi-operations' DB directly.
- Tone: dual-audience (management + integrator), plain and defensible. No hedging on the core guarantee.

---

### Task 1: Write the governance document

**Files:**
- Create: `docs/governance/luna-agent-handoff-governance.md`

**Interfaces:**
- Consumes: the approved spec `docs/superpowers/specs/2026-07-17-luna-agent-handoff-governance-design.md` (section structure, decisions, operation-catalog classification rules, edge cases). The spec's "Operation Catalog — classification rules" section already lists the capability groups with representative endpoint paths — use it as the backbone of §5.
- Produces: the final governance artifact. Nothing downstream consumes it programmatically.

**Source-of-truth for factual accuracy** (verify every guardrail/endpoint claim against these — do not invent):
- Endpoint inventory: the ALLOWED/FORBIDDEN capability groups in the spec (§ "Operation Catalog — classification rules"). If a specific path must be confirmed, grep the route module (e.g. `grep -rn '@router' backend/routes/reports/` ) rather than guessing.
- Six-role model + guard tiers: project memory `user-roles-dialog-fix` and `uniform-client-scope-authz`; roles are admin/poweruser/leader/supervisor/operator/viewer; viewer is read-only on transactional data entry.
- Client-scope authz (403 cross-tenant): `backend/auth/jwt.py` (`ClientScope`, `resolve_client_scope`) — memory `uniform-client-scope-authz`.
- Supervisor/poweruser capacity-write block: `backend/middleware/write_access.py` (`require_capacity_write`).
- Single-tenancy / own-DB-container: memory `production-deployment-planning` and `render-demo-vm-prod-split`.

- [ ] **Step 1: Create the directory and document skeleton**

Create `docs/governance/luna-agent-handoff-governance.md` with a title, a one-line status/date header, and the 10 section headings in order:

```markdown
# Luna-Agent Handoff Governance

**Status:** Active governance policy · **Owner:** KPI-Operations platform owner · **Last reviewed:** 2026-07-17

> How the Luna AI agent works *within* kpi-operations to assist people — without replacing them or making decisions on their behalf.

## 1. Purpose & the guarantee
## 2. Core principles
## 3. Identity & access model
## 4. Enforcement — the read-only allow-list
## 5. Operation catalog
## 6. The decision boundary
## 7. How kpi-operations' guardrails carry through Luna
## 8. Audit & accountability
## 9. Single-tenancy & deployment
## 10. Governance ownership & change control
```

- [ ] **Step 2: Write §1 Purpose & the guarantee and §2 Core principles**

§1: state the management-facing guarantee in the first sentence — *Luna helps humans read and understand their KPIs; it never acts, submits, or decides on a human's behalf.* One short paragraph on why the document exists (the upper-management question) and that it is grounded in already-shipped controls (no new code).

§2: a bulleted list of the four non-negotiables, each one sentence:
1. **Read-only** — Luna never writes to kpi-operations.
2. **No decisions on a human's behalf** — Luna presents information; the human decides and acts.
3. **Human-in-the-loop by construction** — Luna's output is an insight; performing any action requires the human to open kpi-operations and do it themselves.
4. **Full accountability** — every Luna interaction is logged and reviewable.

- [ ] **Step 3: Write §3 Identity & access model**

Explain: Luna authenticates and operates **on-behalf-of the logged-in human**, using that human's own session/token. Consequence: every shipped authorization control applies automatically and unchanged, because at the server Luna *is* that human — it can never see or reach anything the human couldn't. State the accepted trade-off plainly: a borrowed session could technically carry write permission, so "read-only" is guaranteed by the §4 allow-list and the §8 audit log, plus the expectation that people do not ask Luna to act for them. Explicitly note this design keeps a single, auditable actor identity (simpler than a dedicated Luna account).

- [ ] **Step 4: Write §4 Enforcement — the read-only allow-list**

State the binding rule: **Luna's integration is configured with an allow-list of HTTP GET endpoints only; it issues no POST/PUT/PATCH/DELETE call, ever.** Explain why GET-verb-based (not path-prefix-based) — it is simple, unambiguous, and fail-safe: any state change in this API uses a non-GET verb, so a GET-only list cannot mutate anything. Add that the allow-list MAY be narrowed further to the KPI-relevant reads (least privilege) but never widened without re-approval (§10). Forward-reference §5 for the concrete list and the three edge cases.

- [ ] **Step 5: Write §5 Operation catalog (the two tables)**

Two subsections, **ALLOWED (read-only)** and **FORBIDDEN**, each a table with columns `Capability | Endpoint path(s) | What Luna may/among may not do`. Populate from the spec's capability groups. Give concrete paths AND a capability description per row (both). Use path globs where a group is uniform (e.g. `GET /api/quality/**`) and spell out notable individual paths (e.g. `GET /api/kpi/{metric}/cause`, `GET /api/reports/comprehensive/pdf`). ALLOWED groups: KPI/dashboard, trends, cause/diagnostics, quality/defects, attendance/coverage reads, plan-vs-actual, simulation reads, capacity/planning reads, my-shift/alerts reads, analytics/predictions, reference/catalog reads, core-entity reads, workflow reads, data-completeness/assumptions/metric-results/filters/preferences/QR reads, client-config/users/auth-me/onboarding reads, report retrieval (incl. `GET /api/reports/email-config`), data export, health/monitoring. FORBIDDEN groups: all data-entry (production/quality/defects/attendance/coverage/downtime/holds incl. approve-resume/jobs/work-orders), all `/upload/csv`, clients/employees/floating-pool writes, part-opportunities writes, reference/topology/catalog writes, capacity/planning writes (note `require_capacity_write` already blocks poweruser/supervisor server-side), simulation & capacity **scenario runs/writes**, workflow config & transition writes, alerts writes, preferences/filters writes, QR generation writes, client-config writes, calculation-assumption writes, dual-view metric-calculation writes (`POST /api/metrics/calculate/**`), report email-config/scheduling/send writes, cache-management writes, predictions demo-seed, auth register/password. End the section with one line: **"The configured GET-only allow-list is the authoritative source of truth; this catalog is its human-readable rationale."**

- [ ] **Step 6: Write §5 edge-case callouts (the three)**

Immediately after the tables, a short "Edge cases the allow-list resolves" subsection with three bullets, verbatim intent from the spec:
1. **Compute-only POSTs stay forbidden.** `POST /api/v2/simulation/validate` and `POST /api/shifts/check-overlap` persist nothing but are excluded because the rule is GET-only — fail-safe by design.
2. **`/upload/csv` writes interleave with read resources.** CSV-upload endpoints are absolute paths (e.g. `POST /api/quality/upload/csv`) sitting beside that resource's GET reads. A GET-only rule excludes them automatically — build the allow-list by verb, not by resource prefix, so an upload is never swept in.
3. **`GET /api/reports/email-config` vs its writes.** Reading the scheduled-report config is allowed; changing it or sending (`POST`/`PUT`/`/test`/`/send-manual`) is forbidden. Luna may report *what* is scheduled, never change or trigger it.

- [ ] **Step 7: Write §6 The decision boundary**

A ✅/❌ table of concrete examples. ✅ e.g. "OTD fell to 68% on the 14th; 5 orders ran late — here is the dominant driver", "WIP aging is trending up; the oldest active hold is 65 days", "Here's what the FPY trend looks like versus last month." ❌ e.g. "Adjust a capacity plan / commit a schedule", "Approve or resolve a hold", "Confirm or edit a production/quality entry", "Change a KPI threshold or a calculation assumption", "Acknowledge/resolve an alert", "Send a report." One closing sentence: *Luna surfaces; it never settles.*

- [ ] **Step 8: Write §7 guardrail carry-through and §9 single-tenancy & deployment**

§7: a mapping table `Shipped guardrail | Still enforced through Luna because…` with rows for viewer-read-only, client-scope 403 cross-tenant, supervisor/poweruser capacity-write-block, and role tiers generally — each "because Luna calls as the human, so the server applies it unchanged." Cite `require_capacity_write` and `resolve_client_scope` by name.

§9: Luna runs with its **own DB container** per the VM deploy runbook; it integrates with kpi-operations **only via the REST API**, never reading or sharing kpi-operations' database directly — therefore the API (with its authz + the §4 allow-list) is the single door, and single-tenant client isolation is preserved.

- [ ] **Step 9: Write §8 Audit & accountability and §10 Governance ownership & change control**

§8: Luna maintains its own interaction log — for each interaction: the human on whose behalf it ran, the prompt/intent, the endpoints it read, and what it surfaced. State this is the recourse the on-behalf-of model relies on: to investigate questioned behavior, review Luna's log. Note that server-side, kpi-operations sees these as ordinary reads by that user.

§10: name the owner (KPI-Operations platform owner) and the change-control rule — widening the allow-list, changing the identity model, or expanding Luna's scope beyond read-only requires re-approval and a document revision. This document is the authority for the kpi-operations↔Luna boundary.

- [ ] **Step 10: Self-check — spec coverage + factual accuracy**

Verify (read the file back, cross-check against sources):
1. All 10 sections present and non-empty; §5 has both tables + the three edge cases; both concrete paths AND capability descriptions appear.
2. No forbidden endpoint appears in the ALLOWED table and vice versa. Spot-check 5 paths against the spec's classification (e.g. `GET /api/kpi/{metric}/cause` ALLOWED; `POST /api/holds/{hold_id}/approve-resume` FORBIDDEN; `GET /api/reports/email-config` ALLOWED; `POST /api/reports/email-config` FORBIDDEN; `POST /api/v2/simulation/validate` FORBIDDEN).
3. Guardrail names are correct: `require_capacity_write`, `resolve_client_scope`/`ClientScope`, roles admin/poweruser/leader/supervisor/operator/viewer. Run `grep -rn "require_capacity_write" backend/middleware/write_access.py` and `grep -rn "def resolve_client_scope" backend/auth/jwt.py` to confirm the names exist before citing them.
4. No `.py`/test/config file was modified: `git status --porcelain` shows only the new doc (and this plan/spec).
5. No mention of a dedicated Luna account or new role; identity is on-behalf-of throughout.

Fix any discrepancy inline.

- [ ] **Step 11: Commit**

```bash
git add docs/governance/luna-agent-handoff-governance.md
git commit -m "docs(governance): Luna-agent handoff governance document"
```

---

## Self-Review

**Spec coverage:** every spec section maps to a step — §1→Step 2, §2→Step 2, §3→Step 3, §4→Step 4, §5 tables→Step 5, §5 edge cases→Step 6, §6→Step 7, §7→Step 8, §8→Step 9, §9→Step 8, §10→Step 9; classification rules + both-representations requirement→Step 5; three edge cases→Step 6; single-tenancy/API-only→Step 8; accuracy verification→Step 10. **Placeholders:** none — each step names the exact content to write and the source to verify it against. **Consistency:** guardrail identifiers (`require_capacity_write`, `resolve_client_scope`, `ClientScope`, the six role names) are used identically across Steps 5, 8, and 10; the GET-only fail-safe rule is stated once (§4) and referenced (§5, edge case 1) without contradiction. **No-code-change constraint** is enforced by the Global Constraints and re-checked in Step 10.4.

## Global verification

After Task 1: `git status --porcelain` shows only the new governance doc under `docs/governance/`; the document renders with all 10 sections; a reader can answer "can Luna change anything or decide for me?" with a grounded no citing the GET-only allow-list, on-behalf-of authz inheritance, and human-in-the-loop-by-construction. This branch also carries the spec (`docs/superpowers/specs/2026-07-17-luna-agent-handoff-governance-design.md`) and this plan.
