# Reporting Data-Capture Roadmap — Engagement Design

**Date:** 2026-07-31
**Status:** Approved (user-reviewed brainstorm)
**Grounding:** `docs/reporting/reporting-capabilities-and-gaps.md` (§5 deferred-spec queue) and the management decision of 2026-07-30: no further client report samples will be shared; the engagement shifts to **data capture** for the five key operations questions, followed by a pivot/summarization layer over reportable-today data.
**Predecessor spec:** `docs/superpowers/specs/2026-07-29-reporting-capability-and-gap-decision-design.md`

## 1. Purpose

Sequence the reporting deferred-spec queue into an executable engagement. This roadmap is itself the first deliverable; each item in the active lane still gets its own brainstorm→spec→plan cycle before any build, per the living doc's standing rule.

## 2. Decisions (settled in this brainstorm)

1. **Roadmap first.** One sequencing document (this spec) before any item design.
2. **Captures before pivot.** The pivot layer is built once, over the enriched data, after the three capture items land — even though it is not technically blocked by them.
3. **Active lane = the four management-named items only.** Report subscriptions (queue #2) and the remaining model extensions (shipment #, batch traceability, cut quantities, plant/module hierarchy, operator-level production) stay deferred.
4. **Capture policy: optional first, then required.** Uniform across all three captures (details §4).
5. **Slicing: 4 cycles, small→large.** Two quick wins first, then the large capture, then the pivot layer.

## 3. Active lane — four cycles

Each cycle = brainstorm → spec → plan → subagent-driven execution → /cross-review → PR(s) → 7-check CI green → user-confirmed merge → deploy (Render + VM) → live-verify on MariaDB.

### Cycle 1 — Downtime cause taxonomy (Q2; smallest, highest leverage)
Controlled vocabulary over the existing free-form `root_cause_category` on `DowntimeEntry`: **machine / materials / scheduling / attendance / other**, with NPT sub-buckets riding on the same field structure. Entry UI becomes a select; an Alembic migration maps existing free-form values where a confident mapping exists, everything else defaults to `uncategorized`. Downtime-by-category becomes reportable.

### Cycle 2 — Justified-delay flag (Q3)
Classification on late work orders: justified / unjustified plus a reason. Delivery performance becomes reportable both **gross** and **net-of-justified** — the concept behind PGI's Delivery Performance exclusion, without the PGI layout (per the permanent no-carbon-copy position).

### Cycle 3 — Labor-hours accounting (Q1; the big capture)
OT tiers (Normal / Double / Triple — Mexican labor law, structural not client-specific), direct/indirect classification on `Employee`, and billed vs available-for-efficiency hours (the Franklin sample's central distinction; the true Q1 denominator). Expected to split into **2 PRs**: (a) capture model + entry UI, (b) derived Q1 metrics (earned vs billed vs available hours). Final split is decided in that cycle's own spec.

### Cycle 4 — Pivot/summarization layer (largest; built once, over enriched data)
Pre-defined time buckets (week/month/quarter/year), pre-defined groupings/categorizations, cross-metric comparison on the common hours basis (units ↔ SAM-earned hours ↔ operators ↔ attendance hours). Every summary downloadable as the underlying data (data-first position). Expected **2–3 PRs**; split decided in that cycle's spec.

## 4. Capture policy (uniform)

- New capture fields ship **optional or defaulted** (e.g. `uncategorized`); existing entry flows are never blocked at introduction.
- Each capture surface gets a **completeness indicator** so adoption is visible.
- **Flip-to-required** happens per field when BOTH hold: completeness ≥ 90 % over a trailing 30 days, AND management confirms the shop-floor workflow has adapted. The flip is a small, separate change.
- The demo **seeder is updated in the same cycle** that introduces a field, so demos exercise the new capture from day one.

## 5. Success criteria

- Concept-register grades in `docs/reporting/reporting-capabilities-and-gaps.md` §4 are re-graded in place as each cycle lands:
  - Q2 cause taxonomy: partial → **have** (Cycle 1)
  - Q3 justified-vs-unjustified lateness: missing → **have** (Cycle 2)
  - Q1 OT tiers, direct/indirect, billed vs available: missing → **have** (Cycle 3)
- The pivot layer answers the five management questions with downloadable data (Cycle 4).
- Engagement complete when all four cycles are merged, deployed to Render + VM, and live-validated on VM MariaDB.

## 6. Out of scope (standing positions, unchanged)

- No workbook/layout replication of any client spreadsheet (permanent).
- No chart-builder / configurable plotting mechanism.
- No reports over untracked data (capture-first rule) — captures are deliberate product decisions, never report side effects.
- Deferred remainder (report subscriptions; shipment #, batch traceability, cut quantities, plant/module hierarchy, operator-level production) stays deferred until management asks or a cycle surfaces a hard dependency.

## 7. Immediate implementation (of this roadmap)

A small **docs-only PR**:
1. This spec file.
2. `docs/reporting/reporting-capabilities-and-gaps.md`: restructure §5 into **Active lane** (the four sequenced cycles above, with the capture policy) and **Deferred remainder** (parked items with reasons); record the 2026-07-30 management decision (no further samples; capture-first focus) in §1 alongside the committed positions.

Then Cycle 1 (downtime cause taxonomy) starts its own brainstorm→spec cycle immediately.
