# 07 — Simulation V2 + MiniZinc

This is the platform's most powerful — and conceptually densest — feature set. If you only read one section deeply, make it this one.

## What it is

**Simulation V2** is a discrete-event production-line simulator (built on SimPy) that asks: *"if I run my line with this configuration, what would happen?"* It models bundle flow, station queues, bottlenecks, breakdowns, operator skill, fatigue, rework — everything that makes a real line behave un-textbook-like.

Layered on top, four **MiniZinc patterns** ask the prescriptive complement: *"what configuration would be best?"* Each pattern answers a different planning question.

| | SimPy V2 (descriptive) | MiniZinc (prescriptive) |
|---|---|---|
| Question | What HAPPENS? | What's BEST? |
| Inputs | A specific config | Bounds + objective |
| Output | Stochastic results with CI bands | Deterministic optimum |
| Use case | "Stress-test my plan" | "Find me a better plan" |

The two layers compose: optimize with MiniZinc (deterministic), validate the result with SimPy (under variability).

## When to use it

✅ Before changing operator allocation
✅ Before committing to a multi-product schedule for the week
✅ When demand spikes and you need to know if you can hit it
✅ When a bottleneck appears and you don't know where to move people
✅ When evaluating "what if we add a 2nd shift?" or "what if we reduce SAM by 5%?"

⛔ NOT a real-time monitoring tool — for that, use [02 — Dashboards](02-dashboards.md)
⛔ NOT a final commitment — it's a planning aid; final approval still needs human review

## The 4 input tabs

When you open the Simulation page, you see 4 tabs that together define a config:

### Operations tab

The heart of the model: one row per (product × step). Each row defines:

| Column | What it means | Example |
|--------|---------------|---------|
| Product | Product identifier (must match across operations & demands) | `Basic T-Shirt` |
| Step | 1-based sequence within product (no gaps) | `1` |
| Operation | Human-readable name | `Cut Fabric Panels` |
| Machine/Tool | Resource identifier (creates pooled resources) | `Cutting Table` |
| SAM (min) | Standard Allowed Minutes per piece | `0.80` |
| Operators | Workers at this station | `2` |
| Grade % | Operator skill (100 = fully trained) | `90` |
| FPD % | Fatigue & personal delay | `5` |
| Rework % | Pieces requiring rework at this op | `1` |
| Variability | `triangular` (default), `deterministic`, `uniform` | `triangular` |
| Sequence | Phase category for grouping/reporting | `Cutting` |
| Grouping | Sub-category | `Preparation` |

☆ **Tip**: paste from Excel directly into the grid. The platform respects multi-row paste and validates cell-by-cell.

⚠ **Caution**: products are MATCHED BY NAME between Operations and Demands. A typo in either creates an orphan ("operations without demand" warning).

### Schedule tab

| Field | Meaning |
|-------|---------|
| Shifts enabled | 1, 2, or 3 |
| Shift1/2/3 hours | Duration of each (sum must ≤ 24) |
| Work days | 1-7 per week |
| OT enabled | Toggle weekday + weekend overtime |
| Weekday OT hours | Additional hours per workday |
| Weekend OT days | 0-2 |
| Weekend OT hours | Hours per weekend day |

The simulator turns these into "available minutes per day" and "weekly capacity hours" used everywhere downstream.

### Demand tab

| Column | When it's used |
|--------|----------------|
| Product | Must match an Operations product |
| Bundle size | 1+ pieces per bundle (typical: 10) |
| Daily demand | Pieces per day target |
| Weekly demand | Pieces per week target |
| Mix share % | (mix-driven mode only) % of total throughput |

Two modes:
- **Demand-driven** (default): explicit per-product targets
- **Mix-driven**: percentages of an external total (`total_demand` config)

### Breakdowns tab

Optional. Per machine/tool, set a `breakdown_pct` chance per operation. The simulator applies a fixed 30-min repair delay when a breakdown fires.

⚠ The breakdown model is intentionally simplified — no MTBF/MTTR distributions, no repair queue. For complex maintenance modeling, use a dedicated CMMS tool.

## The 5 actions in the toolbar

Once a config is loaded, the toolbar carries 5 buttons:

### Validate Configuration

Runs validation rules WITHOUT executing the simulation. Cheap (< 1s). Returns errors / warnings / info.

**Errors** = block the run (sequence gaps, demand without operations, etc.)
**Warnings** = run but flag potential issues (typo'd machine names, demand-driven without demand)
**Info** = informational

☆ **Tip**: always validate after pasting bulk data. It catches typos before you waste a 10-second simulation run.

### Run Simulation

Single replication. Runs the engine, returns 8 result blocks (see [Output blocks](#output-blocks) below). Typical runtime: 2-5 seconds for a single product, 5-10 seconds for 5 products.

When the **Monte Carlo** toggle is ON, this button runs N replications instead and returns aggregated stats (mean, std, 95% CI bounds for every numeric metric).

### Optimize Operators (Pattern 1)

[Section below.](#pattern-1--optimize-operators)

### Rebalance Bottleneck (Pattern 2)

[Section below.](#pattern-2--rebalance-bottleneck)

### Sequence Products (Pattern 3)

[Section below.](#pattern-3--sequence-products)

### Plan Horizon (Pattern 4)

[Section below.](#pattern-4--plan-horizon)

### Import / Export Config

JSON snapshots of the entire config. Use Export to save a known-good baseline; use Import to restore it or share with a colleague. Validation runs automatically on import.

### Reset

Two options:
- **Clear all** — empty config
- **Load sample T-Shirt** — populates with the worked-example garment line

## Saved scenarios (D3 — persistence)

The toolbar carries two scenario buttons in the new "Save / Load" group:

- **Save Scenario** — captures the current Operations / Schedule / Demand / Breakdowns config under a name. Add a description, tags, and optionally pin it to a specific client.
- **Scenarios** — opens a list of all scenarios visible to you (filtered server-side by your client assignment). From the list:
  - **Load** — replaces the current workbench config with the saved scenario
  - **Run** — executes the engine on the saved config and pins a result summary on the row (so the next time you visit, you see the headline metrics without re-running)
  - **Duplicate** — clones the scenario (with a `(copy)` suffix or a new name)
  - **Delete** — soft-deletes (recoverable by an admin)

Permissions:
- Anyone authenticated can list scenarios visible to their client(s).
- Operators can read but cannot save / run / duplicate / delete.
- Leader / supervisor / poweruser / admin can mutate.
- Admin / poweruser can also create global (NULL `client_id`) scenarios that act as templates visible to all clients.

The scenario stores the SimulationConfig as a JSON blob, so engine upgrades preserve old saves. If a stored config becomes incompatible with the current engine schema (e.g. a field was renamed), the **Run** button surfaces a 422 with a helpful message; re-save from the UI to migrate it.

## Output blocks

After **Run Simulation** completes, you get 8 result blocks:

### Block 1 — Weekly Demand vs Capacity

Per product: weekly demand, max weekly capacity, coverage %, status.

| Status | When it triggers | What it means |
|--------|------------------|---------------|
| ✅ OK | coverage ≥ 110% | Healthy headroom |
| ⚠ Tight | 100% ≤ coverage < 110% | Just enough; first hiccup costs delivery |
| 🛑 Shortfall | coverage < 100% | Cannot meet demand without changes |

☆ **Tip**: a "Tight" status is a leading indicator — escalate before a Shortfall locks in.

### Block 2 — Daily Summary

The dashboard view in one row:

| Metric | Interpret |
|--------|-----------|
| Total shifts/day | From the schedule |
| Daily planned hours | shifts × hours, OT included |
| Daily throughput pcs | What the simulation delivered |
| Daily demand pcs | What was asked |
| Daily coverage % | throughput / demand × 100 |
| Avg cycle time min | Time per finished piece (line-level) |
| Avg WIP pcs | Average work-in-process inventory |
| Bundles processed/day | Bundle throughput |
| Bundle size pcs | Single value or "mixed" |

⚠ **Caution**: a high coverage % with high cycle time means the line is *fast but uneven* — operators are racing then waiting, which compounds quality risk.

### Block 3 — Station / Operation Performance

One row per (product × step). Columns include the operation's input config plus simulated outputs:

- `total_pieces_processed` — pieces this station handled
- `total_busy_time_min` — cumulative active time
- `avg_processing_time_min` — should be close to SAM × (1 / grade)
- `util_pct` — utilization, **the bottleneck signal**
- `queue_wait_time_min` — average minutes a piece waits before this station picks it up
- `is_bottleneck` — true when util > 95%
- `is_donor` — true when util < 70%

☆ **How to read it**: scan the `util_pct` column. The bottleneck is whichever station tops the list. Donors are candidates to give up an operator.

### Block 4 — Free Capacity Analysis

One row showing line-level slack:

- `daily_demand_pcs`
- `daily_max_capacity_pcs`
- `demand_usage_pct` (demand / max_capacity)
- `free_line_hours_per_day` — how many idle hours across the line
- `free_operator_hours_at_bottleneck_per_day` — typically 0 (the bottleneck is always busy)
- `equivalent_free_operators_full_shift` — translate idle hours into "operators we don't need"

☆ **Tip**: `equivalent_free_operators_full_shift = 1.5` means "you have 1.5 operators of slack" — round down, that's 1 operator you could redeploy.

### Block 5 — Bundle Behavior Metrics

Per product: bundle size, bundles arriving/day, avg bundles in system, max bundles in system, avg bundle cycle time. Used for diagnosing WIP buildup.

### Block 6 — Per-Product Summary

Per product: bundle size, mix %, daily/weekly demand, daily/weekly throughput, daily/weekly coverage. The "scoreboard view" — one row per product.

### Block 7 — Rebalancing Suggestions

One row per (station × role). Role is `Bottleneck` or `Donor`. Includes operators_before/after, util_before/after, and a comment.

This is the OUTPUT of a built-in heuristic. For the full optimization see Pattern 2.

### Block 8 — Assumption Log

Audit-grade record of:
- Timestamp & engine version
- Configuration mode (demand-driven / mix-driven)
- Schedule details
- Per-product bundle sizes
- Per-operation defaults that were applied
- Breakdowns configured
- Formula implementations used
- Limitations & caveats

☆ **Always export this log** when sharing simulation results — without it, a stakeholder can't reproduce or audit your conclusions.

## Monte Carlo

Single-replication simulation gives you ONE possible future. Real production has variance — operators have good days and bad days, machines hiccup, raw material differs. Monte Carlo runs the simulation N times (10-50 typical) with different RNG seeds and aggregates the results.

### Inputs

- **# Replications**: 2-100. Typical: 10 for fast feedback, 50 for committed plans.
- **Base seed**: optional integer. Replication `i` uses `base_seed + i`, making the entire run reproducible. Leave blank for independent randomness each time.

### Output: confidence intervals

Every numeric field in the 8 blocks is replaced by a `{mean, std, ci_lo_95, ci_hi_95, n}` shape:

```
daily_throughput_pcs:
  mean: 487
  std:  23
  ci_lo_95: 472
  ci_hi_95: 502
  n: 30
```

How to read this:
- **mean = 487** — your best point estimate
- **CI [472, 502]** — 95% of the time, the true daily throughput on this config will be in this band
- **std = 23** — half the variance comes from within ~23 pieces
- Use `ci_lo_95` for **conservative planning** (the worst plausible day)
- Use `ci_hi_95` for **upside scoping** (best plausible day)

⚠ **Caution**: a wide CI ≠ a bad config. It means the line is sensitive — small input changes ripple. To narrow the CI:
1. Reduce variability (lower triangular spread)
2. Increase grade % (more skilled operators)
3. Reduce breakdown_pct
4. Stabilize bundle sizes

### Worked example

Config: 1 product, 5-station T-shirt line, demand 500/day.

Run 30 replications:
- daily_throughput_pcs.mean = 487
- daily_throughput_pcs.std = 23
- ci_lo_95 = 472

You're planning for delivery 500/day. The lower bound says "5% of the time we'll only hit 472" — i.e. 1 day in 20 you'll miss demand by 28 pcs. Decision: that's 1 day a month — acceptable buffer, ship the plan. Or: add 1 operator to the bottleneck and re-run; if `ci_lo_95` jumps to 510 you've eliminated the risk.

## Pattern 1 — Optimize Operators

### What it does

Given a config, finds the **minimum** operator count per station that meets each station's daily demand under deterministic capacity assumptions.

Equivalent question: *"Can I run this line with fewer people?"*

### How to use it

1. Load your config in the Operations / Schedule / Demand tabs
2. Click **Optimize Operators** (purple button)
3. The result dialog shows:
   - `total_operators_before` → `total_operators_after` (savings)
   - Per-station table with `operators_before`, `operators_after`, `predicted_pcs/day`, `demand_pcs/day`
4. If satisfied, click **Apply to operations** to write the proposal back into your Operations grid

### Worked example

T-Shirt line with 9 operations, current allocation: 11 operators. Daily demand: 500 pcs.

Click Optimize → result:
- Before: 11 operators
- After: 8 operators
- 3 stations dropped from 2→1, 1 station went 1→1 (already minimal)

Predicted pcs/day on the optimized config: 502 (slightly above demand, perfect).

Then click **Apply to operations**, click **Run Simulation** with Monte Carlo (30 reps) to validate. If `daily_throughput_pcs.ci_lo_95 ≥ 500`, ship it. If it's below, the deterministic optimum is too lean — bump max_operators_per_op or accept a 5-10% buffer per station.

### Hints & tips

☆ Run Pattern 1 BEFORE Pattern 2. Pattern 1 sets a tight baseline; Pattern 2 reshuffles around it.

☆ The default `max_operators_per_op` is 10. If your line legitimately runs more (e.g. final QC with 5 inspectors), raise it via the API or a future UI control.

☆ If you set `total_operators_budget`, the model treats it as a hard cap. If infeasible, you get `is_satisfied = false` and a clear message.

### Common pitfalls

⛔ Pattern 1 doesn't account for cross-training or operator personality. The math says "1 operator at this station is enough" — reality may need 2 if that one person needs lunch coverage.

⛔ Don't optimize a line that's just been recommissioned. Wait until grade % stabilizes (typically 4-6 weeks of training data).

## Pattern 2 — Rebalance Bottleneck

### What it does

Given an existing allocation (typically one where Block 7 already flagged a bottleneck), reshuffles operators across stations to lift the bottleneck WITHOUT (by default) growing the head-count.

Equivalent question: *"I have 11 people — where should they go to get more pieces out?"*

### How to use it

1. Load a config that has a bottleneck (Block 7 or Block 3 will flag it)
2. Click **Rebalance Bottleneck** (orange button)
3. The dialog shows:
   - `total_operators_before` → `total_operators_after` (Δ — typically 0)
   - `min_slack_pcs` — pieces of headroom on the worst station
   - Per-station table: before, **delta** (color-coded green/red), after, predicted, demand, slack
4. Apply to operations if happy

### Worked example

3-op line: Cut(4) / Sew(1, SAM 3.5) / Pack(1). Demand 200/day. The slow Sew station bottlenecks the whole line.

Click Rebalance → result:
- Before: 4/1/1, total 6
- After: 2/3/1, total 6 — **strict swap** preserves head-count
- `min_slack_pcs = +149` — every station now has 149+ pcs of buffer

The bottleneck moved from Sew (was 100% util) to a comfortable 70%. The 2 operators that left Cut went to Sew where they were needed.

### When the demand is unattainable

If even with all operators on the bottleneck the demand can't be met, you get a best-effort result:
- `is_satisfied = true` (a plan was found)
- `min_slack_pcs < 0` (negative — can't fully meet demand)
- Solver message: "Demand cannot be met fully — worst station still short by 28 pcs/day. Consider permitting growth (raise total_delta_max) or per-station ceiling (max_operators_per_op)."

### Bounds you can tweak

| Bound | Default | Meaning |
|-------|---------|---------|
| `min_operators_per_op` | 1 | Per-station floor |
| `max_operators_per_op` | 10 | Per-station ceiling |
| `total_delta_max` | 0 | Max NET added (0 = strict swap) |
| `total_delta_min` | -50 | Max NET removed |

To allow growth: set `total_delta_max = 2` for example, allowing up to 2 new hires.

### Hints & tips

☆ The result table's **delta** column is color-coded: green for adds, red for removes. Glance at this column to understand the move at a single read.

☆ "Already balanced" is a valid result — `delta = 0` for every station. Don't reshuffle a line that's already humming.

☆ If you want to validate the rebalancer's output under variability, click Apply, then run Monte Carlo (30 reps).

### Common pitfalls

⛔ Cross-training is invisible to Pattern 2 — it assumes any operator can run any station. If your operators are specialists, post-process the result manually.

⛔ The model treats operators as identical (no per-person grade). Real operators differ; the line's grade % captures the average but not the variance.

## Pattern 3 — Sequence Products

### What it does

Given a multi-product config and a pairwise setup-time matrix, find the **production order** that minimizes total wallclock makespan.

Equivalent question: *"I'm running A, B, and C today — what's the best order to minimize changeover waste?"*

### How to use it

1. Load a config with **2+ products** (with demand for each)
2. Click **Sequence Products** (teal button)
3. A setup-time editor opens with one row per ordered pair (asymmetric — A→B and B→A are separate)
4. Enter the setup minutes for each transition. Values default to 0.
5. Click **Find Optimal Sequence**
6. The result dialog shows:
   - Total wallclock + production + setup
   - Ordered timeline: position, product, start (min), production (min), setup-from-prev (min), end (min)

### Worked example

3 products on a shared line:

| | Production time | Setup A→ | A→B | A→C | B→A | B→C | C→A | C→B |
|---|---|---|---|---|---|---|---|---|
| A | 2h |  | 30 | 10 |  |  |  |  |
| B | 1.5h |  |  |  | 20 | 60 |  |  |
| C | 1h |  |  |  |  |  | 30 | 90 |

Naive sequence A→B→C: production 4.5h + setup (30 + 60) = 6h.

Optimal sequence (Pattern 3): A→C→B → production 4.5h + setup (10 + 90) = 6.7h?

Wait — actually **A→B→A→…** is invalid (each product runs once). Optimal of A,B,C with these setups: probably A→B→C at 30+60=90 min, or A→C→B at 10+90=100 min, or B→A→C at 20+10=30 min ✓ — fewest setup min, makespan 4.5h + 0.5h = 5h.

The platform finds the genuine minimum by testing every permutation under the constraint structure. For 5 products that's 120 permutations; the solver typically finds the optimum in <5s.

### When is it useful?

✅ Campaign mode (run product A all morning, product B all afternoon)
✅ Lines where setup time is non-trivial (>15 min or >5% of production time)
✅ When setup times are known/measured and roughly stable

⛔ Continuous-flow lines that produce a single product
⛔ Make-to-order lines with unpredictable mix
⛔ Setup times that vary wildly day-to-day (model breaks down)

### Hints & tips

☆ Setup matrix is **asymmetric** — fill in BOTH directions for each pair. The platform won't assume A→B = B→A.

☆ Stale entries (a product no longer in the config) are silently ignored. The matrix can outlive product launches.

☆ Result table shows `setup_from_previous_minutes` highlighted (color: warning) when > 0 — visual cue for where the changeovers happen.

### Common pitfalls

⛔ Forgetting to enter setup times for some pairs → defaults to 0, may over-optimize. Better to enter "10 min minimum" everywhere than have zeros sneak in.

⛔ Mistaking makespan for total operator time. If the line has 6 operators running through the sequence, the human-hours = makespan × 6, not just makespan.

## Pattern 4 — Plan Horizon

### What it does

Given a multi-product config with **weekly demand**, distribute the work across the planning horizon (typically 5 work days) to minimize the maximum daily utilization (smoothest workload).

Equivalent question: *"My weekly target is 1000 of A and 500 of B. How do I split it day by day so my line stays balanced?"*

### How to use it

1. Load a config with weekly_demand set on each product
2. Click **Plan Horizon** (indigo button)
3. Enter the horizon (1-31 days, default 5)
4. Click **Find Optimal Plan**
5. Result dialog shows:
   - Total wallclock summary
   - One row per day: day #, pieces by product (one column per product), total pcs, minutes used, **load %** (color-coded green <75%, warning 75-90%, error >90%)
   - Footer: weekly fulfilled / weekly demand per product

### Why "smoothest" instead of "fastest"?

Imagine a 5-day plan that does 100% on Monday and 30% on Tue-Fri. That plan:
- Has zero buffer Monday — first absentee or breakdown blows the week
- Wastes capacity Tue-Fri — operators are idle, can't ship from idle
- Loses cumulative learning — operators perform best at steady-state

A smoothed plan keeps every day at the same load %, distributing risk evenly. That's what Pattern 4 optimizes.

### Worked example

2-product config: 500 weekly of A (~2 min/piece), 300 weekly of B (~1.5 min/piece).

Click Plan Horizon → result:
- Per-day load: 67-68% on every day (smoothed)
- Day 1: 95 of A, 68 of B, 323 min used (67.3%)
- Day 5: 0 of A, 220 of B, 322 min used (67.1%)
- Weekly totals: A 500/500 ✅, B 300/300 ✅

Different products land on different days because the math finds the load-balanced split — products with longer per-piece time get spread out more.

### When demand exceeds capacity

Two failure modes:

1. **Single-product capacity exceeded** (trivial path): if demand × per-piece-time > horizon × daily-minutes, you get `is_satisfied = false`, `status = capacity-exceeded`, max_load_pct > 100. The schedule still shows pieces (capacity-bounded fallback) but flags the gap clearly.

2. **Multi-product infeasible**: best-effort proportional fill with a shortfall message: "Weekly demand exceeds horizon capacity. Best-effort plan fills each day to capacity; remaining shortfall: A: short 200, B: short 50."

### Hints & tips

☆ Use Pattern 4 with Pattern 3 as a one-two punch:
1. Pattern 4: how to distribute the week
2. Pattern 3: per-day, what order to produce

☆ Start with horizon=5 (default work week). For a 4-day work week (some clients), set 4. For mid-month replanning, set whatever days are left.

☆ The trivial path (single-product OR single-day) skips MiniZinc entirely — the answer is mathematically fixed. So Pattern 4 is fast for those cases (no solver call).

### Common pitfalls

⛔ Forgetting weekly_demand. Pattern 4 needs it; daily_demand alone won't drive the optimizer (the platform falls back to `daily_demand × work_days` but it's clearer to set weekly directly).

⛔ Setting horizon to a value larger than the work week. Pattern 4 assumes every day in the horizon is a working day — if you specify 7, the model expects 7 work days of capacity.

## Putting it all together: a recommended workflow

A planner facing "I have a new mix coming in next week, how do I run the line?" might:

1. **Load config** in Operations / Schedule / Demand tabs (with weekly_demand)
2. **Validate** — fix any errors before going further
3. **Run Simulation** (single rep) to see the baseline behavior
4. **Optimize Operators (Pattern 1)** — find the lean head-count
5. Apply, **Run Monte Carlo** (30 reps) — does the lean allocation hit demand under variability?
6. If close, **Rebalance Bottleneck (Pattern 2)** — reshuffle the people you have for headroom
7. **Plan Horizon (Pattern 4)** — split the weekly demand across days for smooth load
8. Per day, **Sequence Products (Pattern 3)** — pick the changeover-minimizing order
9. **Export Config** as the committed plan; share with stakeholders + assumption log

Total time: 30-45 minutes for a complex multi-product week. The platform replaces hours of spreadsheet-juggling.

## API endpoints (for power users / integrators)

All under `/api/v2/simulation/`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Tool info + capabilities |
| `/schema` | GET | Pydantic JSON schema for the config object |
| `/validate` | POST | Validate a config (no run) |
| `/run` | POST | Single replication |
| `/run-monte-carlo` | POST | N replications |
| `/optimize-operators` | POST | Pattern 1 |
| `/rebalance-bottlenecks` | POST | Pattern 2 |
| `/sequence-products` | POST | Pattern 3 |
| `/plan-horizon` | POST | Pattern 4 |

Auth: leader / poweruser / supervisor / admin. Operator gets 403.

Returns 503 when MiniZinc isn't installed on the host (Patterns 1-4 only).

## Limitations & caveats

The simulator is solid but not exhaustive. Known limitations:

1. **Linear routing only** — no parallel ops, no merge points, no skip logic
2. **Simplified breakdowns** — fixed 30-min repair, no MTBF/MTTR distributions, no repair queue
3. **Static grade %** — no learning curves; an operator's grade doesn't improve mid-simulation
4. **No shift breaks** — modeled as continuous run within shift hours (FPD captures the average reduction)
5. **No material constraints** — assumes infinite raw material supply
6. **No WIP cap** — bundles flow freely between stations
7. **Pattern coverage**:
   - Pattern 1: minimum operator count (single objective)
   - Pattern 2: head-count-preserving rebalance (one-shot)
   - Pattern 3: TSP-style sequencing (no batching)
   - Pattern 4: max-load smoothing (objective could also be makespan, profit, etc. — not currently exposed)

For configurations beyond these, treat the simulator as a diagnostic and combine with operator judgment.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| 503 "MiniZinc not installed" on Pattern 1-4 | Server lacks the binary | Contact admin; locally install via `apt install minizinc` |
| Run takes > 30s | Many products or heavy variability | Reduce horizon_days or n_replications |
| `is_satisfied = false` on Pattern 1 | Budget too tight | Raise `total_operators_budget` or remove the cap |
| `min_slack_pcs < 0` on Pattern 2 | Demand mathematically unattainable | Allow growth (raise `total_delta_max`) or accept demand cut |
| `status = capacity-exceeded` on Pattern 4 | Weekly demand > horizon capacity | Extend horizon, add operators, or split demand |
| Validation says "operations without demand" | Product name mismatch between Operations & Demands tabs | Check spelling, case-sensitive |
| Monte Carlo CI is very wide | Line is sensitive to variability | Reduce variability inputs (grade %, breakdown_pct, FPD %) |

## Next

- [Glossary](glossary.md) — every term used here
- [04 — Capacity Planning](04-capacity-planning.md) — for committing the simulation result to a workbook
