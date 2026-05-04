# 04 — Capacity Planning

The 13-tab workbook for the planner / scheduler. Modeled after Excel — same logical flow as a spreadsheet but database-backed, multi-user, version-controlled, and integrated with simulation.

## When to use it

✅ Weekly / monthly production planning
✅ Customer order intake & confirmation
✅ Material readiness check before committing
✅ What-if scenario exploration (absenteeism spike, demand surge, OT cost analysis)
✅ Schedule generation with auto-allocation across lines
✅ Schedule commitment to work orders

⛔ NOT a real-time MES — there's no per-piece transaction history
⛔ NOT a finite-element capacity model — uses aggregate hours/day per line, not minute-by-minute station modeling

## The 13 tabs (the workbook flow)

The tabs are ordered to match a planner's typical workflow. You can jump around, but reading top-to-bottom mirrors the natural plan-build cycle.

### 1. Orders

The customer order book. Where you start.

| Field | Notes |
|-------|-------|
| order_number | Customer / internal PO |
| customer_name | The buyer |
| style_model | Product spec |
| status | PLANNED / IN_PROGRESS / SHIPPED / ON_HOLD |
| priority | LOW / MEDIUM / HIGH / URGENT |
| planned_quantity | Pieces requested |
| planned_ship_date | Promised ship date |
| required_date | Customer's hard requirement |
| received_date | When the order arrived |

☆ **Use case**: customer service drops in new orders; planner reviews.

### 2. Master Calendar

Working days vs holidays, per client.

| Field | Notes |
|-------|-------|
| date | The calendar day |
| is_working | 1 = work day, 0 = holiday/weekend |
| shift_pattern | Which shift schedule applies (1-shift, 2-shift, 3-shift) |
| ot_planned | Whether overtime is pre-authorized |
| capacity_factor | Multiplier on the day's base capacity (e.g. 0.5 for half-day) |

☆ **Use case**: maintain a rolling 12-month calendar so the schedule generator skips holidays.

### 3. Production Lines

The lines (cells) in the plant.

| Field | Notes |
|-------|-------|
| line_name | Human-readable name |
| line_code | Short ID (e.g. LINE-A) |
| daily_capacity_hours | Base hours/day |
| efficiency_factor | Default efficiency assumption (0.75-0.95) |
| absenteeism_factor | Default absenteeism (0.03-0.10) |
| daily_capacity_units | Computed: daily_capacity_hours / cycle_time × efficiency × (1 - absenteeism) |

☆ **Use case**: any new line gets registered here before scheduling can use it.

### 4. Production Standards

Per (style × operation) — the engineer-set SAM and routing.

| Field | Notes |
|-------|-------|
| style_model | Links to Orders |
| operation_step | 1, 2, 3… within style |
| operation_name | Human-readable |
| sam_minutes | The SAM (see Glossary) |
| machine_required | Resource type |
| operators_required | Standard head-count |
| total_sam_per_unit | Computed: sum of SAMs across all ops for the style |

☆ **Use case**: BOMs reference standards. Schedule generation uses `total_sam_per_unit` to convert orders into capacity hours.

The endpoint `/api/capacity/standards/style/{style_model}/total-sam` returns the rolled-up SAM for a style — useful for quick hours estimates.

### 5. BOM (Bill of Materials)

What raw materials does each style need?

| Field | Notes |
|-------|-------|
| bom_header.style_model | The style |
| bom_header.version | BOM revision |
| bom_detail.item_code | Raw material SKU |
| bom_detail.qty_per_unit | Material per finished unit |
| bom_detail.uom | Unit of measure |
| bom_detail.is_critical | Substitution allowed? |

The **explode** action (`POST /api/capacity/bom/explode`) computes total material needed for a planned production quantity.

☆ **Use case**: when accepting a 1000-piece order, explode the BOM to know how much fabric, thread, buttons you need.

### 6. Stock Snapshot

Periodic inventory levels.

| Field | Notes |
|-------|-------|
| snapshot_date | When taken |
| item_code | Material SKU |
| on_hand | Physical inventory |
| committed | Already allocated to other orders |
| available | on_hand - committed |
| reorder_point | Trigger to reorder |

☆ **Use case**: weekly cycle counts feed this; the component-check step reads it.

### 7. Component Check

Cross-references planned orders × BOM × stock to surface shortages.

| Field | Notes |
|-------|-------|
| order_id | The order at risk |
| item_code | Material short |
| required_qty | What we need |
| available_qty | What we have |
| shortage_qty | Deficit (required - available) |
| shortage_severity | NONE / LOW / MEDIUM / HIGH |

The platform recomputes when you click **Run Component Check**. Output goes here AND surfaces in the Capacity Analysis tab.

### 8. Capacity Analysis

Per (line × week): how loaded is each line?

| Field | Notes |
|-------|-------|
| line_id | The line |
| week_starting | Monday of the week |
| capacity_hours | Available hours from calendar × line capacity |
| committed_hours | Hours already booked to orders |
| available_hours | capacity - committed |
| utilization_pct | committed / capacity × 100 |
| bottleneck_indicator | TRUE if utilization > 95% |

☆ **Use case**: visualize where the next bottleneck will be 4-6 weeks out.

### 9. Production Schedule

The committed plan: order × line × date × hours.

| Field | Notes |
|-------|-------|
| schedule_id | Unique per-week schedule |
| order_id | The order |
| line_id | Where it runs |
| scheduled_date | Day-by-day allocation |
| scheduled_hours | Hours that day |
| status | DRAFT / COMMITTED |

The platform offers two schedule actions:
- **Generate** (`POST /api/capacity/schedules/generate`) — auto-allocate orders to lines using a heuristic (greedy by priority + due date)
- **Commit** (`POST /api/capacity/schedules/{id}/commit`) — promote DRAFT to COMMITTED, generates work orders downstream

☆ **Use case**: every Friday afternoon — generate next week's schedule, review, commit.

### 10. What-If Scenarios

The "stress test" view. Each scenario is a saved deviation from the baseline:

| Scenario type | What it tests |
|---|---|
| ABSENTEEISM_SPIKE | "What if absenteeism spikes from 5% to 15%?" |
| DEMAND_SURGE | "What if a customer adds 20% to their order?" |
| OT_BUDGET | "What if I authorize overtime to cover the gap?" |
| LINE_DOWN | "What if Line A goes down for 2 days?" |
| OPERATOR_TRAINING | "What if I sacrifice 10% efficiency for a week to train?" |

Each scenario has:
- `parameters_json` — the input (e.g. `{baseline_absenteeism: 5, spike_absenteeism: 15, duration_weeks: 4}`)
- `results_json` — the computed impact (capacity change, cost impact, feasibility)

☆ **Use case**: run scenarios at month-end to brief leadership on risk exposure.

The platform's `Scenarios` panel (`useAnalysisStore`) lets you create, run, compare scenarios in the UI. Combine with Simulation V2 for stochastic versions.

### 11. KPI Tracking

Per-week target vs actual on the platform-tracked KPIs:

| Field | Notes |
|-------|-------|
| week_starting | Monday |
| kpi_name | efficiency / OEE / FPY / OTD / etc. |
| target | The committed number |
| actual | What you delivered |
| variance | actual - target |
| variance_pct | variance / target × 100 |

☆ **Use case**: weekly accountability — did the plan match reality? Patterns drive the next plan's targets.

### 12. Dashboard Inputs

Per-client config:
- `planning_horizon_days` — typical planning window
- `default_efficiency` — line-level default
- `bottleneck_threshold` — utilization % above which a line is flagged
- `shortage_alert_days` — material shortage horizon
- `auto_schedule_enabled` — toggle generator

☆ **Use case**: tune the workbook's behavior per client preferences.

### 13. Instructions

A markdown document explaining the workbook to new users — usually written by the planning team. Editable by admin / poweruser.

## The recommended weekly cycle

A planner using the workbook fully:

| Day | Action |
|-----|--------|
| Mon-Tue | Review last week's actuals; update KPI Tracking. Look at any chronic holds. |
| Wed | New customer orders into Orders tab. Update Production Standards if a new style. |
| Thu | Run Component Check; review shortages. Order materials if any. |
| Fri | Generate next week's schedule. Review w/ ops & customer service. Commit. |
| Mon | Schedule active. Monitor via Plan vs Actual + KPI Dashboard. |

## Scenario workflow example

A customer adds 20% to a confirmed order Tuesday. Planner's response:

1. **Update Orders tab** with new quantity
2. **Run Component Check** — does material allow?
3. **Run Capacity Analysis** — is the line capacity available?
4. If both green: regenerate schedule, commit
5. If red: open **Simulation V2** with the updated demand → run Pattern 1 (Optimize Operators) — can we run leaner elsewhere to free up capacity? Or Pattern 4 (Plan Horizon) to redistribute the week.
6. If still infeasible: create a **What-If Scenario** "DEMAND_SURGE" → run it → quantify the cost (overtime, expedite shipping); use as the conversation with the customer.

## Permission model on the workbook

| Action | Admin | PowerUser | Leader | Operator |
|--------|:-----:|:---------:|:------:|:--------:|
| View | ✓ | ✓ | view-only | — |
| Edit any tab | ✓ | ✓ | — | — |
| Generate schedule | ✓ | ✓ | — | — |
| Commit schedule | ✓ | ✓ | — | — |
| Save scenario | ✓ | ✓ | — | — |

Leaders see the workbook (read-only) so they understand the plan; they execute it from MyShift / Production Entry.

## Hints & tips

☆ The 13 tabs share a "client_id" filter at the top. Switching clients re-loads every tab — no cross-client mixing.

☆ Use the **Scenario Compare Dialog** to put two scenarios side-by-side. Useful when deciding "OT budget vs absenteeism mitigation."

☆ The **MRP Results Dialog** is a Component Check shortcut — runs the check + shows shortages in a dialog without leaving the current tab.

☆ Workbook history (last 10 changes per worksheet) is preserved — undo via the History panel.

## Common pitfalls

⛔ Editing Production Standards mid-week: changes the SAM, which changes total_sam_per_unit, which changes capacity_hours computations. Standards changes should be quarterly, with explicit comms.

⛔ Forgetting to commit a generated schedule. A DRAFT schedule shows on Capacity Analysis but does NOT generate work orders. Always commit before relying on the plan.

⛔ Accepting a customer order before checking BOM stock. The component check is fast (< 5s) — always run it.

## API endpoints

39 routes under `/api/capacity/*`:

| Group | Routes |
|-------|--------|
| Workbook (composite) | `GET /workbook/{client_id}` returns all 13 tabs |
| Orders | `GET/POST /orders`, `GET/PUT/DELETE /orders/{id}`, `GET /orders/scheduling` |
| Calendar | `GET/POST /calendar`, `GET/PUT/DELETE /calendar/{id}` |
| Lines | `GET/POST /lines`, `GET/PUT/DELETE /lines/{id}` |
| Standards | `GET/POST /standards`, `GET /standards/style/{style}`, `/style/{style}/total-sam`, `GET/PUT/DELETE /standards/{id}` |
| BOM | `GET/POST /bom`, `GET/PUT/DELETE /bom/{header_id}`, `GET/POST /bom/{header_id}/details`, `PUT/DELETE /bom/details/{id}`, `POST /bom/explode` |
| Stock | `GET/POST /stock`, `GET /stock/item/{code}/latest`, `/item/{code}/available`, `GET /stock/shortages`, `GET/PUT/DELETE /stock/{id}` |
| Component Check | `POST /component-check/run`, `GET /component-check/shortages` |
| Capacity Analysis | `POST /analysis/calculate`, `GET /analysis/bottlenecks` |
| Schedules | `GET/POST /schedules`, `GET /schedules/{id}`, `POST /schedules/generate`, `POST /schedules/{id}/commit` |
| Scenarios | `GET/POST /scenarios`, `GET/PUT/DELETE /scenarios/{id}`, `POST /scenarios/{id}/run`, `POST /scenarios/compare` |
| KPI tracking | `GET /kpi/commitments`, `GET /kpi/variance` |

## Next

- [05 — Work Orders](05-work-orders.md) (downstream of committed schedules)
- [07 — Simulation V2](07-simulation-v2.md) (stochastic stress-test of plans)
- [08 — Reports](08-reports.md) (export the workbook for stakeholders)
