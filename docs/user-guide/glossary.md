# Glossary

Domain terms used across the platform. If you've ever stopped at a metric and thought "what is that, exactly?" — start here.

## Production timing

### SAM (Standard Allowed Minutes)

The textbook minutes a single piece **should** take at one operation. It's the engineering-set baseline, NOT the actual.

- Example: a single-needle stitch on a t-shirt collar might have SAM = 1.20 min/piece.
- Used as the denominator for Efficiency: `Efficiency = (Earned SAM / Available SAM) × 100`.

### Cycle time

The actual time from one finished piece to the next. Different from SAM:

- **SAM** = ideal target  → set by the engineer
- **Ideal cycle time** = best the line can do at 100% efficiency
- **Actual cycle time** = what's happening today; equals `run_time / units_produced`

### Bundle

A bundle is a group of pieces that move through the line together (e.g. 10 t-shirts cut at once). Bundle size affects throughput because the line waits for the slowest piece in a bundle before passing the bundle along.

- Common sizes: 10, 12, 24
- Smaller bundles = lower WIP but more handling overhead
- Larger bundles = higher throughput but higher WIP

### Run time

The minutes a station actually spent producing — excludes setup, breakdowns, breaks. Used as the numerator for Performance.

### Setup time / changeover

Minutes lost when switching from product A to product B on the same machine — re-threading, swapping templates, calibration. **Asymmetric**: A→B may take 10 min while B→A takes 60 min (e.g. switching from a generic stitch to a specialized one is harder than the reverse).

Pattern 3 (Sequence Products) optimizes for the order that minimizes total setup time across the day.

## Quality

### FPY (First Pass Yield)

Of pieces inspected, what % passed first time without rework?

`FPY = units_passed / units_inspected × 100`

Industry target: 95%+ for garment, 99%+ for electronics.

### RTY (Rolled Throughput Yield)

The probability that a unit gets through ALL operations defect-free. Computed as `FPY₁ × FPY₂ × … × FPYₙ`.

A line with 5 stations each at 95% FPY has RTY = 0.95⁵ ≈ 77%. RTY is what management cares about for cost-of-quality.

### DPMO (Defects Per Million Opportunities)

The Six-Sigma quality metric: defects per million opportunities. Lower is better.

`DPMO = (defects / (units × opportunities)) × 1,000,000`

Mappings: 6σ = 3.4 DPMO, 4σ = 6210 DPMO, 3σ = 66807 DPMO.

### PPM (Parts Per Million)

Defects per million units shipped. Simpler than DPMO (no "opportunities" factor).

### Rework

A piece that failed inspection but is repairable. Tracked at each operation as `rework_pct`. The line-level rework rate is the SUM of per-station rates because pieces can be reworked at different stages.

## OEE family

### OEE (Overall Equipment Effectiveness)

The composite KPI:

`OEE = Availability × Performance × Quality`

World-class: 85%+. Manufacturing average: 60%. Below 40%: investigate root cause.

### Availability

% of scheduled time the line was actually producing — excludes downtime and changeovers.

`Availability = run_time / planned_production_time`

Common targets: 90%+ for steady-state, 75%+ for new lines.

### Performance

% of theoretical throughput actually achieved at the bottleneck. Captures slow-running, minor stops.

`Performance = (ideal_cycle_time × units_produced) / run_time`

Will be < 100% even on a healthy line — operators take micro-pauses, balance varies through the day.

### Quality

For OEE purposes, this is the % of produced units that passed first time:

`Quality = good_units / total_units_produced`

NOT the same as FPY (which is per-station); OEE Quality is the line-rolled-up rate of ship-able output.

## Bottleneck terminology

### Bottleneck

The operation with the highest utilization (closest to 100%). The line's throughput is limited by the bottleneck — adding people anywhere else just creates queues.

The platform flags a station as a bottleneck when its utilization exceeds 95%.

### Donor station

A station with utilization < 70% — it has slack capacity that could be reallocated. Pattern 2 (Rebalance Bottleneck) typically moves operators FROM donors TO bottlenecks.

### Slack

Operators × time available - operators × time used. Pieces of headroom. Negative slack = the demand can't be met (mathematically infeasible).

The Pattern 1 / Pattern 2 result tables show **slack_pcs/day** per station — an immediately actionable view of "where's the breathing room?"

### Throughput

Pieces completed per unit time. Can be reported as pcs/day or pcs/hr.

The line's throughput is the bottleneck's throughput, plus any rework loss downstream.

## Work order lifecycle

### Status flow (full enum)

The actual `WorkOrderStatus` enum:

```
RECEIVED → RELEASED → IN_PROGRESS → COMPLETED → SHIPPED → CLOSED
                          ↓
                       ON_HOLD → IN_PROGRESS (when resumed)
                          ↓
                       CANCELLED  /  REJECTED  /  DEMOTED
```

Allowed transitions are configured per-client in the Workflow Designer. Default workflows ship with three templates (Standard / Simple / Express).

Demo data exercises 4 of the 11 states: SHIPPED (on-time + late), IN_PROGRESS, RECEIVED, ON_HOLD.

### Priority

WO `priority` is a free-form `String(20)` column (no enum constraint at the schema level). Customary values: `LOW, MEDIUM, HIGH, URGENT`.

For Capacity Orders (separate enum): `LOW, NORMAL, HIGH, URGENT` — note that CPO uses `NORMAL` where WO uses `MEDIUM`.

A previous audit migrated WO data from `CRITICAL` to `URGENT`; old data may still surface `CRITICAL` in stale exports.

### Hold

A pause on a work order for any reason — material shortage, quality investigation, change order. Tracked separately from downtime (which is equipment-side).

A hold has a category (Material, Quality, Process, etc.) drawn from the per-client hold catalog.

## Multi-tenancy

### Client

The customer or business unit a work order, line, or operator belongs to. Every record has a `client_id` and queries are filtered server-side.

The 5 demo clients seeded in the platform: ACME-MFG, BOOT-LINE-A, TEXTILE-PRO, CIRCUIT-WORLD, ELECTRONICS-OEM.

### Multi-client user

A leader or operator may be assigned to multiple clients via comma-separated `client_id_assigned`. Switching clients in the UI re-scopes all data.

## Simulation-specific

### Operator grade %

A multiplier on SAM that captures operator skill. A 70% grade means this operator works at 70% of the SAM rate.

`Effective rate = (1 / SAM) × (operators) × (grade_pct / 100)`

Newly trained operators start at ~70%; experienced reach 95-100%.

### FPD (Fatigue & Personal Delay) %

A blanket reduction for human factors — operators don't run at peak speed all 8 hours. Typical: 5-15%.

The platform uses FPD as a multiplier on the available time, not on the SAM.

### Variability

Three modes per station, controlling how the simulation samples processing times:

- **deterministic**: every piece takes exactly SAM minutes
- **triangular** (default): random between [SAM - 20%, SAM + 30%], peak at SAM
- **uniform** (planned): even spread across a range

Triangular is the most realistic for hand-paced manufacturing.

### Makespan

The total wallclock time from "start producing" to "finished producing" — for a Pattern-3 sequence run, this is what we minimize. Includes production + setup transitions.

If you produce A (4h) → B (3h) with a 30-min setup, the makespan is 7.5h.

### Daily load %

The Pattern-4 result. For each day in the planning horizon: `(minutes_used / minutes_available) × 100`. A smooth plan keeps every day at the same load %; an unsmoothed plan would peak on day 1 and idle later.

### Confidence interval (CI 95%)

Monte Carlo result. After N replications: 95% of the time, the true mean falls within `[mean - 1.96 × std/√n, mean + 1.96 × std/√n]`.

Wider CI = more variability in your line; narrower CI = predictable. Use the lower bound for conservative planning.

## Capacity planning

### Mix-driven vs demand-driven

Two ways to specify what to build:

- **Demand-driven**: "I need 500 of A and 300 of B" (absolute targets per product)
- **Mix-driven**: "I want 60% of capacity on A, 40% on B" (percentages of total throughput)

Pattern 4 needs demand-driven; Patterns 1-3 work with either.

### Planning horizon

The number of working days the plan covers. Default 5 (a typical work week). Pattern 4 takes this as input; Patterns 1-3 are single-day.

### Workbook

The 13-tab capacity planning sheet, modeled after Excel: orders, calendar, lines, standards, BOM, stock, component check, capacity analysis, schedule, scenarios, KPI tracking, dashboard inputs, instructions.

## Statistical / mathematical

### Standard deviation (σ)

Width of the bell-curve around the mean. ~68% of values fall within 1σ of the mean; ~95% within 2σ.

In Monte Carlo results, look at `std` for each metric — high std means the line is sensitive to that input.

### MiniZinc

The open-source constraint-programming solver the platform uses for prescriptive optimization. We wrap it in `optimization/*.mzn` model files + Python services that build inputs and parse results.

You don't need to know MiniZinc to use the platform — just know that the four "patterns" are MiniZinc-powered.

### Pareto

A bar chart sorted descending. The 80/20 rule: typically 80% of defects come from 20% of causes. The Analytics → Pareto view exposes this view per KPI.
