# 02 — Dashboards

Where you spend most of your day if you're a leader, manager, or admin.

## The 4 main dashboards

| Dashboard | Path | Default for | Purpose |
|-----------|------|-------------|---------|
| Home | `/` | Leader | Cross-client production scorecard |
| KPI Dashboard | `/kpi-dashboard` | Admin | Aggregated KPI cards, drill-down to detail views |
| MyShift | `/my-shift` | Operator | Shift-personal view: my numbers, my work orders, my activity |
| Plan vs Actual | `/plan-vs-actual` | (link from Planning) | Capacity orders performance vs commitment |

Plus 8 KPI **detail views** (drill-down from the KPI Dashboard cards).

## Home dashboard (`/`)

### What it shows

- **Production summary** for selected client(s) and date range
- **KPI cards**: efficiency, OEE, FPY, downtime hours, absenteeism
- **Recent work orders** with status pills
- **Email Reports** dialog (subscribe / send manual)
- **Filter chips**: client, product, shift, date range
- **Export to Excel** button

### Use cases

✅ Quick morning check: "Is the line running today?"
✅ Pre-meeting glance: numbers ready before stand-up
✅ Cross-client view (admin / poweruser only — others see their assigned client)

### Hints & tips

☆ Set the date range to "Yesterday" or "Last 7 days" — most useful for steady-state monitoring. Today's data is incomplete until shift close.

☆ Click any KPI card to drill into the detail view (efficiency card → `/kpi/efficiency`).

☆ Filter chips persist across navigation — set them once, see them applied throughout.

### Interpreting the numbers

| Metric | Healthy | Investigate |
|--------|---------|-------------|
| Efficiency | 85%+ | < 75% |
| OEE | 65%+ (manufacturing avg 60%) | < 50% |
| FPY | 95%+ (garment), 99%+ (electronics) | < 90% |
| Daily downtime hours | < 1h | > 2h |
| Absenteeism | < 5% | > 8% |

A healthy line hits the green band on at least 4 of 5. Below that, root-cause time.

## KPI Dashboard (`/kpi-dashboard`)

### What it shows

- **9 KPI cards**, each with a sparkline trend + current vs target band
- **Date range filter** (default: last 30 days)
- **Client filter** (admin / poweruser)
- **Drill-down**: click a card → its detail view

### The 9 cards

| Card | Drill-down route | What good looks like |
|------|------------------|----------------------|
| Efficiency | `/kpi/efficiency` | Trend flat or rising; daily values close together |
| Performance | `/kpi/performance` | 80%+ at the bottleneck |
| Quality (FPY) | `/kpi/quality` | 95%+; rising trend (quality improvement) |
| Availability | `/kpi/availability` | 90%+ steady |
| OEE | `/kpi/oee` | 65%+ (and ideally rising over months) |
| WIP Aging | `/kpi/wip-aging` | Median age < 3 days, no orders > 14 days |
| On-Time Delivery | `/kpi/on-time-delivery` | 95%+ |
| Absenteeism | `/kpi/absenteeism` | < 5%, no spikes |
| (Cross-cutting summary card) | — | (varies) |

### Use cases

✅ Monthly business review prep
✅ Identifying which KPI to investigate this week
✅ Comparing two clients' performance side-by-side (filter dropdown)

### Hints & tips

☆ The sparklines are 30-day windows by default. To zoom in / out, use the date range filter on the page.

☆ A card showing "—" (blank) means there's not enough data in the selected window to compute the metric. Widen the date range.

☆ Email Reports dialog (top-right) lets you schedule daily/weekly emails of the dashboard.

### Common pitfalls

⛔ Treating the dashboard as real-time. It refreshes on navigation, not on a timer. Force a refresh by selecting another nav item and back.

⛔ Comparing two clients with very different bundle sizes — efficiency-by-product is more reliable than efficiency-by-client when bundle sizes differ.

## MyShift Dashboard (`/my-shift`)

The personalized dashboard for line operators / supervisors.

### What it shows

- **Today's shift stats**: units produced, efficiency, downtime incidents/minutes, quality checks, defect count
- **Assigned work orders**: order ID, product, target, produced, progress %
- **Recent activity**: last 5 events (production logs, downtime, quality)
- **Data completeness widget**: % production / downtime / quality entered this shift

### Use cases

✅ Operator quick check at start of shift / mid-shift
✅ Supervisor walks the floor and confirms data was entered
✅ Pre-shift handoff: "where did we leave off?"

### Hints & tips

☆ The data completeness widget is the operator's "did I do my job today?" indicator. Aim for green (≥90%) by end of shift.

☆ Click a work order to see its full detail (linked to Work Orders view).

☆ The widget assumes 8 production entries / shift and 2 quality checks. If your shift convention differs, this is a known UX edge case (the absolute counts are still correct).

### Filtering

- `shift_date` — defaults to today; pass YYYY-MM-DD to view another day
- `shift_id` — defaults to current shift; pass an integer to scope a specific shift

(These are URL parameters when integrating; the UI presents them as date pickers.)

### Common pitfalls

⛔ MyShift is per-day, per-shift, per-client. If you don't see your data, check the date filter — yesterday's data won't show on today's view.

⛔ Activity list is capped at 5. For deeper history, navigate to the per-event view (Production / Downtime / Quality entry pages).

## Plan vs Actual (`/plan-vs-actual`)

For Capacity Planning's commitment view: how are we doing against the plan?

### What it shows

- One row per **capacity order** with: order #, customer, style, status, priority, planned qty, actual completed, variance, completion %, risk level
- **Summary tile**: total orders, total planned qty, total actual, overall variance, overall completion %, risk distribution

### Risk levels

- **OK** — completion % ≥ 90% and on schedule
- **At Risk** — completion 70-90% or trailing schedule
- **Critical** — completion < 70% or significantly behind schedule

### Use cases

✅ Daily standup: "what's at risk?"
✅ Customer-facing reports: confirm delivery commitments
✅ Pre-shipping: confirm planned units are met before allocation

### Interpreting "overall_completion_pct = 211%"

If you see > 100% it means the line over-produced versus the plan. That's not necessarily good — it means the plan was wrong (under-forecast) or you've got over-stock. Work with planning to right-size the next plan.

### Hints & tips

☆ The risk distribution tile is the fastest way to see how the entire portfolio is doing. If 80% are OK and 5 are Critical, the portfolio is healthy with localized concerns.

☆ Variance can be negative (under-built) or positive (over-built). A pattern of consistent over-builds points at a forecasting issue.

## KPI Detail Views

Each card on the KPI Dashboard drills into a detail view at `/kpi/{name}`. They share a layout:

- **Top section**: trend chart (line or area) over the selected date range
- **Filter bar**: client, product, shift, date range
- **Breakdown table**: per-product or per-shift values
- **Annotations**: targets, threshold lines, trend arrows

### `/kpi/efficiency`

What it computes: `(units_produced × SAM) / (operators × run_time × 60)`. Displayed as percentage.

Insight to look for:
- Trend stable or improving? → healthy
- Trend declining? → operator skill drift, equipment degradation, or new product mix
- Big day-to-day swings? → variability too high — investigate (or smooth via Pattern 4 plan)

### `/kpi/wip-aging`

Aging buckets (typically 1-3 days, 4-7, 8-14, 15+). Each bar shows count of orders stuck at that age.

Look for:
- Big bar at 15+ days → chronic blockages; look at hold/quality issues
- All bars below 3 days → healthy flow
- A growing bar at 8-14 → trend toward chronic; intervene now

### `/kpi/on-time-delivery`

`OTD = on_time_orders / total_shipped_orders × 100`. Two modes:
- **Standard OTD**: based on planned_ship_date
- **True OTD**: based on customer's required_date (more strict)

The detail view shows both and a breakdown of late deliveries with reason categorization.

### `/kpi/availability`

`Availability = run_time / planned_production_time × 100`. Affected by downtime, breakdowns, changeovers.

The detail view includes a downtime Pareto — top reasons sorted by hours.

### `/kpi/performance`

`Performance = (ideal_cycle_time × units_produced) / run_time × 100`. Captures slowness — micro-pauses, learning curve, etc.

### `/kpi/quality`

FPY trend + DPMO trend + defect type Pareto. Click a defect type to drill into root-cause data.

### `/kpi/oee`

The composite OEE metric (Availability × Performance × Quality). The detail view shows the 3 components stacked so you see which is dragging.

### `/kpi/absenteeism`

Absent days / scheduled days × 100. Includes per-employee Bradford factor (scoring chronic vs short absences).

## API endpoints feeding the dashboards

All under `/api/kpi/`:

| Endpoint | Use |
|----------|-----|
| `/api/kpi/dashboard` | Aggregated card data for KPI Dashboard |
| `/api/kpi/dashboard/aggregated` | Cross-client / cross-product aggregation |
| `/api/kpi/efficiency/by-product` | Detail breakdown |
| `/api/kpi/efficiency/by-shift` | Detail breakdown |
| `/api/kpi/efficiency/trend` | Trend chart data |
| (similar for all 8 KPIs) | |
| `/api/kpi/wip-aging` | Current WIP by age bucket |
| `/api/kpi/wip-aging/top` | Worst-aged orders list |
| `/api/kpi/late-orders` | Late deliveries list |
| `/api/kpi/chronic-holds` | Holds older than threshold |

Plus `/api/my-shift/{summary,stats,activity}` for MyShift, and `/api/plan-vs-actual{,/summary}` for Plan vs Actual.

## Common dashboard troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Card shows "—" | Not enough data in window | Widen date range |
| Trend line is flat at 0 | No production entries in window | Check data entry — operator may have skipped logging |
| Numbers don't match Excel | Different calculation conventions | Check the assumption log (Block 8 of Simulation, or `/admin/variance-report`) |
| Slow page load | Big date range × many products | Narrow filters; the per-product break can hit 100s of rows |
| Dark mode chart unreadable | Contrast issue | Toggle back to light; report so we can adjust the palette |

## Next

- [03 — Data Entry](03-data-entry.md) (the data feeding all this)
- [07 — Simulation V2](07-simulation-v2.md) (when you want to predict where these numbers are going)
- [Glossary](glossary.md) (decode any term)
