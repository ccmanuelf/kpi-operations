# Luna-Agent Handoff Governance Document (Design)

**Date:** 2026-07-17
**Status:** Approved design → ready for implementation plan
**Deliverable:** a governance/integration document at `docs/governance/luna-agent-handoff-governance.md` (new `docs/governance/` directory). This spec describes what that document must contain and the classification rules behind its operation catalog; the document itself is the artifact produced during implementation.

## Context & Purpose

Upper management will ask: *"Does connecting the Luna AI agent to kpi-operations let an AI make decisions for us, or replace a person?"* The answer must be a clear, defensible **no**, backed by a written policy that any integrator can follow. This document is that artifact. It defines exactly how Luna interacts with kpi-operations so it **assists humans without replacing them or deciding on their behalf**.

The document is **dual-audience**:
- **Management / governance** — the one-line guarantee, the principles, the decision boundary, accountability, and change control.
- **Integrator** — the identity model, the concrete read-only endpoint allow-list, and the forbidden set.

It is grounded entirely in kpi-operations' **already-shipped** guardrails — no new backend code is required to make it true. The document is policy + configuration guidance, not a code change.

## Decisions locked during brainstorming

1. **Identity model — on-behalf-of the logged-in human (Option 2).** Luna operates using the authenticated human's own session/token. Every shipped authorization control (six-role model, client-scope, 403 cross-tenant, supervisor-write-block) therefore applies automatically and unchanged: Luna can never see or reach anything the human couldn't. The accepted trade-off — a borrowed session *could* technically write — is contained by decisions 2 and 3 plus Luna's own audit log. This is deliberately simpler than a dedicated Luna account and keeps a single, auditable actor identity.
2. **Operation scope — read + insights/explanations only.** Luna reads KPIs, trends, causes, and reports and surfaces analysis/explanations. It never drafts or submits data changes.
3. **Enforcement — Approach A: a documented read-only endpoint allow-list.** Luna's integration is configured with an explicit allow-list of **read/GET endpoints only**; it issues no write call, regardless of what the borrowed session could do. This turns "read-only" from a hope into a boundary Luna enforces on itself, and — by design — keeps a human in the loop: to *act*, the human must open kpi-operations and do it themselves.

## Document Structure (10 sections)

1. **Purpose & the one-line guarantee.** Management-facing opening: Luna helps humans read and understand their KPIs; it never acts, submits, or decides on a human's behalf.
2. **Core principles (non-negotiables).** (a) read-only — Luna never writes; (b) no decisions on a human's behalf — Luna presents, the human decides and acts; (c) human-in-the-loop by construction — Luna's output is an insight; the *action* requires the human to open the app; (d) full accountability — every Luna interaction is logged.
3. **Identity & access model.** On-behalf-of the human (decision 1). Explains that all shipped authz applies automatically because Luna *is* the human at the server, and states the borrowed-session trade-off and its containment (allow-list + audit).
4. **Enforcement — the read-only allow-list (Approach A).** The binding technical rule and the pattern-based allow-list (see Operation Catalog below). Names the three edge cases explicitly.
5. **Operation catalog.** Two tables — ALLOWED (read/analytics) and FORBIDDEN (writes/mutations/admin) — each with **concrete endpoint paths *and* a capability-level description** (both, per the user's requirement), plus the allow-list note that the configured list is the source of truth.
6. **The decision boundary.** Concrete ✅/❌ examples separating "surface an insight" from "make/execute a decision."
7. **How the shipped guardrails carry through Luna.** Short mapping table: viewer-read-only, client-scope 403, supervisor-write-block → each still enforced because Luna is the human.
8. **Audit & accountability.** Luna keeps its own interaction log (prompt → endpoints read → what it surfaced); how to review it when behavior is questioned. This is the recourse the on-behalf-of model relies on.
9. **Single-tenancy & deployment.** Luna has its **own DB container** per the VM runbook and reaches kpi-operations **only via the REST API** — never sharing or reading kpi-operations' database directly — so the API's authz is the only door.
10. **Governance ownership & change control.** Who owns the policy; that widening the allow-list or scope requires re-approval.

## Operation Catalog — classification rules (the heart of the document)

The catalog is defined by **path pattern**, because the read surface is large (~200 GET endpoints) while the write surface is a small, well-bounded set. The governance document lists concrete endpoint paths grouped by capability, but the **enforceable rule** is pattern-based:

### ALLOWED (read-only) — the allow-list

**Rule:** HTTP **GET** endpoints under the analytics/read surface. Enumerated by capability group in the document, including:

- **KPI metrics / dashboard** — `GET /api/kpi/dashboard`, `/api/kpi/dashboard/aggregated`, `/api/kpi/otd`, `/api/kpi/availability`, `/api/kpi/wip-aging*`, `/api/kpi/chronic-holds`, `/api/kpi/late-orders`, `/api/kpi/calculate/{entry_id}`, `/api/kpi/efficiency/by-*`.
- **Trends** — `GET /api/kpi/*/trend` (efficiency, performance, quality, availability, oee, on-time-delivery, absenteeism, throughput-time, wip-aging) + `/api/kpi/performance/by-*`.
- **Cause / diagnostics** — `GET /api/kpi/{metric}/cause`.
- **Quality / defects** — `GET /api/quality/**`, `GET /api/defects/**` (all GET).
- **Attendance / coverage reads** — `GET /api/attendance/**`, `GET /api/coverage/**`.
- **Plan-vs-actual** — `GET /api/plan-vs-actual*`.
- **Simulation reads** — `GET /api/v2/simulation/` , `/schema`, `/calibration`, `/scenarios*`; `GET /api/floating-pool/simulation/insights`.
- **Capacity / planning reads** — `GET /api/capacity/**` (calendar, lines, orders, standards, bom, stock, shortages, bottlenecks, schedules, scenarios, kpi/commitments, kpi/variance, workbook).
- **My-shift / alerts reads** — `GET /api/my-shift/**`, `GET /api/alerts/**`.
- **Analytics / predictions** — `GET /api/analytics/**`, `GET /api/predictions/**`.
- **Reference / catalog reads** — `GET /api/products`, `/api/shifts*`, `/api/downtime-reasons`, `/api/production-lines/**`, `/api/equipment/**`, `/api/employee-line-assignments/**`, `/api/hold-catalogs/**`, `/api/defect-types/**`, `/api/part-opportunities*`, `/api/break-times`, `/api/calendar/**`.
- **Core entity reads** — `GET /api/production*`, `/api/work-orders/**`, `/api/clients/**`, `/api/employees/**`, `/api/floating-pool/**`, `/api/holds/**`, `/api/downtime/**`, `/api/jobs/**`.
- **Workflow reads** — `GET /api/workflow/**` (allowed-transitions, history, elapsed-time, config, templates, analytics, statistics).
- **Data completeness / assumptions / metric-results / filters / preferences / QR reads** — `GET /api/data-completeness/**`, `/api/assumptions/**`, `/api/metrics/results*`, `/api/filters/**`, `/api/preferences/**`, `/api/qr/lookup`, `/api/qr/**/image`.
- **Client config / users / auth-me / onboarding reads** — `GET /api/client-config/**`, `/api/users*`, `/api/auth/me`, `/api/onboarding/status`.
- **Report retrieval / generation** — `GET /api/reports/production/{pdf,excel}`, `/quality/{pdf,excel}`, `/attendance/{pdf,excel}`, `/comprehensive/{pdf,excel}`, `/available`, and `GET /api/reports/email-config` (a read of the config).
- **Data export** — `GET /api/export/**`.
- **Health / monitoring** — `GET /health/**`, `GET /api/cache/{health,stats}`, `GET /api/admin/database/{status,providers}` (read-only diagnostics; the document notes these are operational, not KPI data).

### FORBIDDEN — everything that mutates state or makes a decision

**Rule:** all **POST / PUT / PATCH / DELETE** endpoints. Enumerated by capability group, including: auth register/password/login/logout; user & admin management; **all data-entry** (production, quality/defects, attendance, coverage, downtime, holds incl. approve/resume, jobs, work-orders incl. status/QC/link); **all `/upload/csv`** endpoints; clients/employees/floating-pool writes; part-opportunities writes; reference/topology/catalog writes (shifts, break-times, production-lines, equipment, line-assignments, hold-catalogs, defect-types); **capacity/planning writes** (already server-guarded by `require_capacity_write`); simulation/capacity **scenario writes and runs**; workflow config & transition writes; alerts writes (create/ack/resolve/dismiss/generate); preferences/filters writes; QR generation writes; client-config writes; **calculation-assumption writes** (create/approve/retire); dual-view **on-demand metric calculation** writes (`POST /api/metrics/calculate/**`); **report email-config / scheduling / send** writes; cache-management writes; predictions demo-seed.

### Three edge cases the document must call out explicitly

1. **Compute-only POSTs are still FORBIDDEN by the allow-list.** `POST /api/v2/simulation/validate` and `POST /api/shifts/check-overlap` persist nothing (semantically reads), but the allow-list is **GET-only** — so they are excluded. Rationale in the doc: the enforcement rule is "GET verb," which is simple, unambiguous, and fail-safe; a POST — even a harmless one — is never on the list. (If a future read genuinely needs a POST body, widening the allow-list requires re-approval per §10.)
2. **`/upload/csv` writes interleave with read resources.** CSV-upload endpoints are absolute paths like `POST /api/quality/upload/csv`, sitting beside that resource's GET reads. Because the allow-list is GET-only, they are excluded automatically — but the document flags the `/upload/csv` suffix so an integrator building a path-prefix allow-list does not accidentally whitelist a resource prefix that would sweep in its uploads. Prefer verb-based (GET) matching over prefix-based.
3. **`/api/reports/email-config` — GET vs write split.** `GET /api/reports/email-config` (read the config) is ALLOWED; its `POST`/`PUT`/`test`/`send-manual` siblings are FORBIDDEN. Luna may report *what* the scheduled-report config is; it may not change it or trigger a send.

## What is explicitly NOT in scope

- **No kpi-operations code changes.** This is a governance/config document. The shipped guardrails already enforce authz server-side; the allow-list is Luna-side configuration. If a later decision wants a hard server wall (e.g. a dedicated `viewer`-role Luna account, Option C from brainstorming), that is a separate spec.
- **No drafting / proposal mechanism.** Scope is read + insights only (decision 2); the "drafts but never submits" pathway is deliberately out of scope for v1.
- **No Luna-internal architecture.** How Luna is built, prompts, or its own DB schema are Luna's concern; this document governs only the kpi-operations boundary (API-only, allow-list, on-behalf-of identity, audit-log expectation).

## Success Criteria

- The document exists at `docs/governance/luna-agent-handoff-governance.md` with all 10 sections.
- A reader can answer "can Luna change anything or decide for me?" with a grounded no, citing the GET-only allow-list, the on-behalf-of authz inheritance, and the human-in-the-loop-by-construction principle.
- An integrator can build Luna's allow-list from the catalog: GET-only, the enumerated capability groups, and the three edge-case rules.
- Every claim about a guardrail (six-role, client-scope 403, supervisor-write-block, single-tenant own-DB, API-only) is consistent with the shipped system as described in project memory and the audit status.

## Related Memory

[[uniform-client-scope-authz]] (the client-scope authz Luna inherits), [[user-roles-dialog-fix]] (the six-role model), [[production-deployment-planning]] (single-tenancy / own-DB-container policy on the VM), [[render-demo-vm-prod-split]] (deployment context).
