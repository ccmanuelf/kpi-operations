# Luna-Agent Handoff Governance

**Status:** Active governance policy · **Owner:** KPI-Operations platform owner · **Last reviewed:** 2026-07-17

> How the Luna AI agent works *within* kpi-operations to assist people — without replacing them or making decisions on their behalf.

---

## 1. Purpose & the guarantee

**Luna helps humans read and understand their KPIs; it never acts, submits, or decides on a human's behalf.**

This document exists to answer, in writing and without hedging, the question leadership will ask before connecting an AI agent to the operations platform: *does this let an AI make decisions for us, or replace a person?* The answer is **no**, and this document defines exactly how that "no" is enforced.

Everything here is grounded in controls **already shipped** in kpi-operations — the six-role permission model, uniform per-client authorization, and the supervisor write-block. Connecting Luna requires **no new code** in kpi-operations: the platform's existing server-side authorization plus a read-only configuration on Luna's side are what make the guarantee true.

The document is written for two readers: **leadership / governance** (§1, §2, §6, §8, §10) and the **integrator** who connects Luna (§3, §4, §5, §7, §9).

## 2. Core principles

1. **Read-only.** Luna never writes to kpi-operations. It reads data and explains it.
2. **No decisions on a human's behalf.** Luna presents information and analysis; the human decides and acts.
3. **Human-in-the-loop by construction.** Luna's output is an insight, not an action. To *do* anything — enter data, approve a hold, adjust a plan — the human must open kpi-operations and do it themselves. Luna cannot close that loop for them.
4. **Full accountability.** Every Luna interaction is logged and reviewable (see §8).

## 3. Identity & access model

Luna authenticates and operates **on-behalf-of the logged-in human**, using that human's own authenticated session/token. It does not have a separate account of its own inside kpi-operations.

The consequence is the property that makes this model safe: **at the server, Luna *is* that human.** Every authorization control kpi-operations already enforces applies automatically and unchanged — Luna can never see, reach, or affect anything the human themselves could not. There is nothing new to secure on the kpi-operations side, because Luna inherits the exact permission envelope of the person it is helping (see §7).

**The accepted trade-off, stated plainly:** because Luna borrows a human's session, that session *may* technically carry write permission. "Read-only" is therefore guaranteed by two things working together — the **GET-only allow-list** Luna enforces on itself (§4) and the **audit log** that records everything Luna did (§8) — plus the straightforward organizational expectation that people do not ask Luna to perform actions for them. This design was chosen deliberately over giving Luna a dedicated account: it keeps a **single, auditable actor identity**, so any question about "who did this?" has one answer — the human — with Luna's log showing exactly what was read on their behalf.

## 4. Enforcement — the read-only allow-list

**The binding rule:** Luna's integration is configured with an **allow-list of HTTP `GET` endpoints only**. Luna issues **no `POST`, `PUT`, `PATCH`, or `DELETE` request to kpi-operations, ever** — regardless of what the borrowed session could technically do.

The allow-list is defined **by HTTP verb (GET), not by URL prefix**, and that choice is deliberate. In this API, every state change uses a non-GET verb; a read never does. A GET-only list is therefore **fail-safe**: it *cannot* mutate anything, because no mutating call is representable on it. It is also unambiguous — there is no per-endpoint judgment call about whether something is "safe."

The allow-list **may be narrowed** further — for example, to only the KPI-relevant reads, following least-privilege — but it must **never be widened** beyond GET, and any change requires re-approval under §10. The concrete list and its three edge cases follow in §5.

## 5. Operation catalog

Two tables follow: what Luna **may** call (read-only) and what it **may not**. Each row gives both the concrete endpoint path(s) and the capability in plain language. Path globs (`**`) denote a uniform group; notable individual paths are spelled out.

### 5.1 ALLOWED (read-only)

| Capability | Endpoint path(s) | What Luna may do |
|---|---|---|
| KPI metrics / dashboard | `GET /api/kpi/dashboard`, `/api/kpi/dashboard/aggregated`, `/api/kpi/otd`, `/api/kpi/availability`, `/api/kpi/late-orders`, `/api/kpi/wip-aging**`, `/api/kpi/chronic-holds`, `/api/kpi/efficiency/by-*`, `/api/kpi/calculate/{entry_id}` | Read current KPI values and dashboards |
| Trends | `GET /api/kpi/*/trend` (efficiency, performance, quality, availability, oee, on-time-delivery, absenteeism, throughput-time, wip-aging), `/api/kpi/performance/by-*` | Read historical KPI trends |
| Cause / diagnostics | `GET /api/kpi/{metric}/cause` | Read the root-cause breakdown behind a metric |
| Quality / defects | `GET /api/quality/**`, `GET /api/defects/**` | Read inspections, PPM/DPMO/FPY, defect Pareto |
| Attendance / coverage | `GET /api/attendance/**`, `GET /api/coverage/**` | Read attendance records, absenteeism, coverage |
| Plan vs actual | `GET /api/plan-vs-actual`, `/api/plan-vs-actual/summary` | Read plan-vs-actual comparisons |
| Simulation (reads) | `GET /api/v2/simulation/`, `/schema`, `/calibration`, `/scenarios**`; `GET /api/floating-pool/simulation/insights` | Read simulation inputs, saved scenarios, insights |
| Capacity / planning (reads) | `GET /api/capacity/**` (calendar, lines, orders, standards, bom, stock, shortages, bottlenecks, schedules, scenarios, `kpi/commitments`, `kpi/variance`, workbook) | Read capacity plans, standards, BOM, stock, variance |
| My-shift / alerts (reads) | `GET /api/my-shift/**`, `GET /api/alerts/**` | Read shift summaries and existing alerts |
| Analytics / predictions | `GET /api/analytics/**`, `GET /api/predictions/**` | Read trend analysis, forecasts, benchmarks, heatmaps |
| Reference / catalog | `GET /api/products`, `/api/shifts**`, `/api/downtime-reasons`, `/api/production-lines/**`, `/api/equipment/**`, `/api/employee-line-assignments/**`, `/api/hold-catalogs/**`, `/api/defect-types/**`, `/api/part-opportunities**`, `/api/break-times`, `/api/calendar/**` | Read reference/catalog/topology data |
| Core entity reads | `GET /api/production**`, `/api/work-orders/**`, `/api/clients/**`, `/api/employees/**`, `/api/floating-pool/**`, `/api/holds/**`, `/api/downtime/**`, `/api/jobs/**` | Read the operational records themselves |
| Workflow (reads) | `GET /api/workflow/**` (allowed-transitions, history, elapsed-time, config, templates, analytics, statistics) | Read workflow state, history, timings |
| Completeness / assumptions / lineage / filters / prefs / QR | `GET /api/data-completeness/**`, `/api/assumptions/**`, `/api/metrics/results**`, `/api/filters/**`, `/api/preferences/**`, `/api/qr/lookup`, `/api/qr/**/image` | Read completeness, assumption sets, metric lineage, saved views |
| Config / users / self / onboarding (reads) | `GET /api/client-config/**`, `/api/users**`, `/api/auth/me`, `/api/onboarding/status` | Read configuration and directory information the human can already see |
| Report retrieval | `GET /api/reports/{production,quality,attendance,comprehensive}/{pdf,excel}`, `/api/reports/available`, `GET /api/reports/email-config` | Generate/download reports; read the scheduled-report config |
| Data export | `GET /api/export/**` | Export data the human is authorized to see |
| Health / monitoring | `GET /health/**`, `GET /api/cache/{health,stats}`, `GET /api/admin/database/{status,providers}` | Read operational/diagnostic status (not KPI data); include only if operationally needed |

### 5.2 FORBIDDEN (all state changes and actions)

| Capability | Endpoint path(s) | Why forbidden |
|---|---|---|
| Auth / password | `POST /api/auth/{register,login,logout,forgot-password,reset-password,change-password}` | Session & credential actions |
| User / admin management | `POST/PUT/DELETE /api/users**` | Administrative decisions |
| Production data entry | `POST/PUT/DELETE /api/production**`, `POST /api/production/{upload/csv,batch-import}` | Enters/edits operational data |
| Quality / defect data entry | `POST/PUT/DELETE /api/quality/**`, `/api/defects**` | Enters/edits quality data |
| Attendance / coverage data entry | `POST/PUT/DELETE /api/attendance**`, `/api/coverage**`, `POST /api/attendance/{bulk,mark-all-present}` | Enters/edits attendance |
| Downtime data entry | `POST/PUT/DELETE /api/downtime**` | Enters/edits downtime |
| WIP holds & approvals | `POST/PUT/DELETE /api/holds**`, `POST /api/holds/{hold_id}/{approve-hold,request-resume,approve-resume}` | Creating/approving/resuming holds are decisions |
| Jobs / work orders | `POST/PUT/DELETE /api/jobs**`, `/api/work-orders**`, `PATCH /api/work-orders/{id}/status`, `POST …/approve-qc`, `POST …/{link,unlink}-capacity` | Changes production records & status |
| CSV upload (all) | `POST /api/**/upload/csv` | Bulk data writes |
| Clients / employees / floating-pool | `POST/PUT/DELETE /api/clients**`, `/api/employees**`, `/api/floating-pool**`, assign/unassign actions | Master-data & assignment decisions |
| Part opportunities | `POST/PUT/DELETE /api/part-opportunities**` | Master-data writes |
| Reference / topology / catalog writes | `POST/PUT/DELETE /api/{shifts,break-times,production-lines,equipment,employee-line-assignments,hold-catalogs,defect-types}**` | Configuration changes |
| Capacity / planning writes | `POST/PUT/PATCH/DELETE /api/capacity/**`, incl. `…/schedules/generate`, `…/schedules/{id}/commit`, `…/analysis/calculate` | Planning decisions (the `poweruser` role is additionally server-blocked from these writes via `require_capacity_write`) |
| Simulation & capacity scenario runs/writes | `POST/PUT/DELETE /api/capacity/scenarios**`, `POST /api/v2/simulation/{run,run-monte-carlo,validate,optimize-operators,rebalance-bottlenecks,sequence-products,plan-horizon,scenarios**}` | Running/altering what-if analysis |
| Workflow config & transitions | `POST /api/workflow/**/transition`, `/bulk-transition`, `PUT /api/workflow/config/{client_id}`, `…/apply-template` | Advances work-order state / changes config |
| Alerts writes | `POST /api/alerts/**` (create, acknowledge, resolve, dismiss, generate/*) | Acting on or generating alerts is a decision |
| Preferences / filters writes | `POST/PUT/PATCH/DELETE /api/preferences**`, `/api/filters**` | Changes saved state |
| QR generation | `POST /api/qr/generate**` | Creates artifacts |
| Client config writes | `POST/PUT/DELETE /api/client-config/**` | Configuration changes |
| Calculation assumptions | `POST/PATCH /api/assumptions**`, `POST …/{approve,retire}` | Approving/retiring assumptions is a governance decision |
| Metric calculation writes | `POST /api/metrics/calculate/**` | Persists computed metric results |
| Report scheduling / send | `POST/PUT /api/reports/email-config`, `…/test`, `POST /api/reports/send-manual` | Changes scheduling / sends communications |
| Cache management | `POST /api/cache/clear`, `DELETE /api/cache/invalidate/**` | Operational mutation |
| Predictions demo seed | `POST /api/predictions/demo/seed` | Writes demo data |

**The configured GET-only allow-list is the authoritative source of truth; this catalog is its human-readable rationale.**

### 5.3 Edge cases the allow-list resolves

1. **Compute-only POSTs stay forbidden.** `POST /api/v2/simulation/validate` and `POST /api/shifts/check-overlap` persist nothing (they only compute), yet they are excluded because the rule is **GET-only**. This is fail-safe by design: Luna never issues a POST, so there is no line to draw about "harmless" writes.
2. **`/upload/csv` writes interleave with read resources.** CSV-upload endpoints are absolute paths (e.g. `POST /api/quality/upload/csv`) that sit *beside* that resource's GET reads rather than under a separate `/upload` prefix. A GET-only rule excludes them automatically — which is exactly why the allow-list is built **by verb, not by resource prefix**: whitelisting a resource prefix could otherwise sweep an upload endpoint in.
3. **`GET /api/reports/email-config` vs its writes.** Reading the scheduled-report configuration is allowed; changing it or sending (`POST`/`PUT /api/reports/email-config`, `…/test`, `POST /api/reports/send-manual`) is forbidden. Luna may report *what* is scheduled — never change it or trigger a send.

## 6. The decision boundary

Luna **surfaces**; it never **settles**. The line:

| ✅ Luna may (surface an insight) | ❌ Luna may not (make/execute a decision) |
|---|---|
| "OTD fell to 68% on the 14th; 5 orders ran late — here's the dominant driver." | Adjust a capacity plan or commit a schedule. |
| "WIP aging is trending up; the oldest active hold is 65 days." | Approve or resolve a hold. |
| "FPY is 4 points below last month; defects concentrate in one part." | Confirm or edit a production or quality entry. |
| "This assumption drives OEE and hasn't changed in 90 days." | Change a KPI threshold or approve/retire a calculation assumption. |
| "There are 3 unacknowledged OTD-risk alerts." | Acknowledge, resolve, or dismiss an alert. |
| "Here's the comprehensive report for last week." | Schedule or send a report. |

*Luna surfaces; it never settles.* Where an insight implies an action, Luna names the action for the human to take — it does not take it.

## 7. How kpi-operations' guardrails carry through Luna

Because Luna calls the API **as the human** (§3), every shipped control applies unchanged — the server enforces it identically whether the request originates from the person's browser or from Luna acting on their behalf:

| Shipped guardrail | Still enforced through Luna because… |
|---|---|
| **Viewer read-only** on transactional data entry | Luna only reads anyway; and if the human is a viewer, the server refuses writes regardless of caller. |
| **Client-scope isolation (403 cross-tenant)** via `resolve_client_scope` / `ClientScope` | Luna's requests carry the human's scope; the server returns 403 for any client the human can't access — Luna cannot widen that scope. |
| **Poweruser capacity-write block** via `require_capacity_write` | Even if Luna's read-only rule failed, the server independently blocks capacity-planning writes for the `poweruser` role. |
| **Six-role permission tiers** (admin / poweruser / leader / supervisor / operator / viewer) | Luna inherits the human's role exactly; it gains no capability the human lacks. |

The read-only allow-list (§4) and this server-side enforcement are **defense in depth**: two independent layers, either of which alone prevents Luna from changing anything.

## 8. Audit & accountability

Luna maintains its **own interaction log**. For each interaction it records: the human on whose behalf it ran, the prompt/intent, the endpoints it read, and what it surfaced back. This log is the recourse the on-behalf-of model depends on — when Luna's behavior is questioned, the log is the record that answers *what did Luna do, for whom, and on what data*.

Server-side, kpi-operations sees Luna's calls as **ordinary authenticated reads by that user** — they appear in the same access path as the human's own requests, with the same authorization applied. There is no separate privileged channel. Accountability therefore has two mutually reinforcing records: kpi-operations' own request handling, and Luna's interaction log.

## 9. Single-tenancy & deployment

Luna is deployed with its **own database container**, per the kpi-operations VM deployment runbook's single-tenancy policy — Luna's data store is separate from kpi-operations' data store.

Luna integrates with kpi-operations **only via the REST API**. It never reads or shares kpi-operations' database directly. This matters: it means the API — with its authorization (§7) and the GET-only allow-list (§4) — is the **single door** through which Luna reaches any kpi-operations data. Per-client isolation is preserved end-to-end, because the only path in is the one that already enforces it.

## 10. Governance ownership & change control

This document is the **authority for the kpi-operations ↔ Luna boundary**. It is owned by the **KPI-Operations platform owner**.

Any of the following requires **re-approval and a revision of this document** before it takes effect:
- Widening the allow-list (adding any non-GET verb, or expanding beyond the read surface in §5).
- Changing the identity model (e.g. moving off on-behalf-of to a dedicated account or a new role).
- Expanding Luna's scope beyond read + insights (e.g. introducing any drafting or write pathway).

Until such a revision is approved, the guarantee in §1 and the principles in §2 are binding: Luna reads and explains; humans decide and act.
