# User Guide

Welcome — this is the operator/planner/admin handbook for the Manufacturing KPI Platform. It explains every screen, every feature, and (most importantly) what the numbers mean and when to act on them.

## How this guide is organized

| Section | What's covered | Read this if you are… |
|---------|----------------|----------------------|
| [01 — Getting Started](01-getting-started.md) | Login, roles, navigation, dark mode, language | New here |
| [02 — Dashboards](02-dashboards.md) | Home, KPI Dashboard, MyShift, Plan vs Actual + 8 KPI sub-views | Reading metrics |
| [03 — Data Entry](03-data-entry.md) | Production, downtime, attendance, quality, hold/resume | A line operator or supervisor entering data |
| [04 — Capacity Planning](04-capacity-planning.md) | 13-tab workbook (orders, calendar, lines, BOM, stock, schedule, scenarios) | A planner / scheduler |
| [05 — Work Orders](05-work-orders.md) | List, statuses, scenarios, capacity links | Tracking work-order progress |
| [06 — Alerts](06-alerts.md) | Generation, acknowledge, dismiss, configuration | Triaging exceptions |
| [07 — Simulation V2 + MiniZinc](07-simulation-v2.md) | Validate / Run / Monte Carlo / 4 optimization patterns / save & load scenarios / pre-fill from history | Doing what-if analysis or planning a campaign |
| [08 — Reports](08-reports.md) | Excel / PDF generation, scheduling, email | Building executive reports |
| [09 — Admin](09-admin.md) | Users, clients, defect types, client config, floating pool, workflow designer, database | A system admin |
| [10 — Roles & Permissions](10-roles-permissions.md) | Who can do what | Setting up access |
| [Glossary](glossary.md) | SAM, FPD, OEE, makespan, bottleneck, etc. | Decoding terms |

## Quick reference for the new MiniZinc features (2026-05)

The platform now pairs SimPy stochastic simulation with MiniZinc deterministic optimization. Four "patterns" answer different planning questions:

| Pattern | Question it answers | Section |
|---------|---------------------|---------|
| 1 — Optimize Operators | What's the **fewest operators** I can run with and still hit demand? | [Pattern 1](07-simulation-v2.md#pattern-1--optimize-operators) |
| 2 — Rebalance Bottleneck | I have N operators total — where should they go to **lift the bottleneck**? | [Pattern 2](07-simulation-v2.md#pattern-2--rebalance-bottleneck) |
| 3 — Sequence Products | I'm running multiple products on the same line — **what order minimizes setup waste**? | [Pattern 3](07-simulation-v2.md#pattern-3--sequence-products) |
| 4 — Plan Horizon | I have a weekly demand target — **how do I split it across the week** for smooth load? | [Pattern 4](07-simulation-v2.md#pattern-4--plan-horizon) |

All four are explained with worked examples in section 07.

## Quick reference for scenarios + calibration (2026-05)

Two new productivity surfaces sit on top of the simulation workbench:

| Feature | What it solves | Section |
|---------|----------------|---------|
| Save Scenario / Scenarios | Stop losing your work between sessions; share named configs with your team; pin a "last run" summary so you don't have to re-run to remember the numbers | [Saved Scenarios](07-simulation-v2.md#saved-scenarios-d3--persistence) |
| Pre-fill from history | Don't type SAM, grade %, rework %, demand, and shift hours from scratch — the platform reads its own production / quality / downtime / shift records and fills the form | [Pre-fill from history](07-simulation-v2.md#pre-fill-from-history-d4--calibration) |

Both surfaces are gated to leader / supervisor / poweruser / admin (operators are data-entry, not planners) and tenant-fenced server-side.

## How to read each guide

Every section follows the same outline:

1. **What it does** — the one-sentence purpose
2. **When to use it** — the right-tool-for-the-job filter
3. **How to use it** — step-by-step, with screenshots where helpful
4. **A worked example** — realistic numbers you can compare your own against
5. **Hints & tips** — gotchas and shortcuts
6. **Interpreting the results** — what the numbers actually mean and when to act
7. **Common pitfalls** — things to avoid

If you only have 2 minutes, read sections 1, 2, and 6.

## Conventions used in this guide

- **Bold** = a UI label or button name
- `code` = an exact value, file path, or API endpoint
- ☆ Tip / ⚠ Caution / ⛔ Don't / ✅ Do — quick visual scan markers (only added where they materially help)
- Numbers in worked examples are realistic but illustrative; your numbers will differ

## Need a deeper dive?

- Architecture → `docs/ARCHITECTURE.md`
- API reference → `docs/API_DOCUMENTATION.md`
- Per-screen technical docs → `docs/views/`
- Standards (entry UI, AG Grid) → `docs/standards/`
- Contributing → `docs/CONTRIBUTING.md`
