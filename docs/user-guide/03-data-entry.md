# 03 — Data Entry

The data that feeds every dashboard, KPI, and simulation comes from the entry surfaces. If the entry is wrong / missing, EVERYTHING downstream is wrong / missing.

## The 5 entry surfaces

| Entry | Path | Who uses it | Frequency |
|-------|------|-------------|-----------|
| Production | `/production-entry` | Operator, Supervisor | Hourly during shift |
| Downtime | `/data-entry/downtime` | Operator, Supervisor | When it happens |
| Attendance | `/data-entry/attendance` | Supervisor, Leader | Once at shift start |
| Quality | `/data-entry/quality` | Supervisor, Quality Inspector | Per inspection point |
| Hold / Resume | `/data-entry/hold-resume` | Supervisor, Leader | When work-order pauses/resumes |

All 5 are **AG Grid spreadsheet-style entry** (per the entry-UI standard). You can paste from Excel, edit cells inline, sort/filter, and export to CSV.

## Universal patterns

### Pasting from Excel

Copy the data from Excel (Cmd/Ctrl+C). Click the first target cell in the grid, paste (Cmd/Ctrl+V). The grid auto-fills cells, validates each one, and highlights invalid cells in red.

☆ **Tip**: column order in your Excel must match the grid's order. Use the grid's CSV-template export to get a header row that matches.

### CSV upload

Each entry has a **"Import CSV"** button (top-right toolbar). Workflow:

1. Click Import CSV → modal opens
2. (Optional) Click **Download template** to get the canonical header row
3. Drop or select your CSV
4. Modal previews the first 10 rows + flags any validation issues
5. Click **Import** to commit, or **Cancel** to fix and retry

Imports are atomic: either every row commits or none does. You'll never have a half-imported file.

### CSV export

The toolbar also has **"Export CSV"** — exports the current grid (post-filter, post-sort) to a CSV the user can download. Used for ad-hoc reporting or sharing with downstream tools.

### Inline edit

Double-click a cell to edit. Enter to commit, Escape to cancel. Tab moves to the next column, Shift-Tab to the previous. Arrow keys navigate without editing.

⚠ **Caution**: edits are auto-saved. There's no "save" button. If you click off the grid or navigate away, your last edit is committed.

## Production entry (`/production-entry`)

### What you record

Per (line × product × shift × hour-block):

| Field | Required | Notes |
|-------|----------|-------|
| client_id | yes | Pre-filled from your assignment |
| line_id | yes | Pick from your assigned lines |
| product_id | yes | The product being made |
| shift_id | yes | Current shift |
| work_order_id | optional | Recommended — drives WO progress |
| job_id | optional | If multi-job |
| production_date | yes | Calendar date |
| shift_date | yes | Often same as production_date |
| units_produced | yes | Pieces in this period |
| run_time_hours | yes | Active production time |
| employees_assigned | yes | Schedule head-count |
| employees_present | optional | Actual head-count (for absenteeism correlation) |
| defect_count | yes | From quality inspection |
| scrap_count | yes | Unrecoverable |
| rework_count | optional | Reworked-but-passed |
| setup_time_hours | optional | If a changeover happened |
| downtime_hours | optional | Cross-checked against downtime entries |
| ideal_cycle_time | optional | Hours per unit (engineer-set) |
| actual_cycle_time | optional | Computed: run_time / units_produced |
| efficiency_percentage | optional | Cached for fast queries |
| performance_percentage | optional | Cached |
| quality_rate | optional | Cached |
| notes | optional | Free text |

The platform auto-computes efficiency / performance / quality if you leave them blank.

### Use cases

✅ Hourly logging: "I produced 50 t-shirts in the last hour"
✅ Shift-end summary: "Total for shift: 400 pieces in 8 hours"
✅ Multi-line operator: log each line separately

### Hints & tips

☆ Set up a CSV template with your standard fields and bulk-paste at shift end if hourly entry isn't feasible.

☆ The `units_produced` field is the LEADING input. Without it, every KPI is unable to compute. Don't skip even if you don't know defects yet.

☆ Always tag a `work_order_id` if you can — drives the work order progress widget on MyShift.

### Common pitfalls

⛔ Confusing `production_date` (when the operation occurred) with `shift_date` (the shift's nominal date). For a shift that crosses midnight, they differ — the convention is shift_date = the date the shift STARTED.

⛔ Forgetting `employees_assigned` — missing it makes efficiency calculation undefined.

⛔ Entering units > capacity. The grid validates against the line's max — but a typo (50 → 500) gets caught. Trust the validation; if it warns, fix the typo.

## Downtime entry (`/data-entry/downtime`)

### What you record

Per downtime event:

| Field | Required | Notes |
|-------|----------|-------|
| client_id | yes | Pre-filled |
| line_id | optional | If line-specific |
| work_order_id | optional | If WO-attributable |
| shift_date | yes | When it happened |
| downtime_reason | yes | From the reason catalog |
| downtime_duration_minutes | yes | Total minutes lost |
| machine_id | optional | If machine-specific |
| equipment_code | optional | Asset registry code |
| root_cause_category | optional | Category (Mech, Elec, Material, etc.) |
| corrective_action | optional | Free text |
| reported_by | optional | Person who logged it |
| resolved_by | optional | Person who fixed it |
| resolution_timestamp | optional | When it returned to running |

### Use cases

✅ Real-time logging during shift
✅ Post-shift catch-up (less ideal but acceptable)
✅ Maintenance team's input feed

### Hints & tips

☆ The reason dropdown comes from `/api/downtime-reasons` — typically configured by the plant's maintenance team. If a reason is missing, contact your admin.

☆ Long-running downtime (> 1h) often gets multiple log entries — that's fine. The dashboard aggregates by shift_date.

☆ Tag `root_cause_category` consistently — drives the downtime Pareto on `/kpi/availability`.

### Common pitfalls

⛔ Logging "Other" too often → diluted Pareto. Push back to the maintenance team to add a real category.

⛔ Forgetting the `corrective_action` — the maintenance team needs it for their MTBF tracking. Set a habit of writing one sentence even if obvious.

## Attendance entry (`/data-entry/attendance`)

### What you record

One row per (employee × shift_date):

| Field | Required | Notes |
|-------|----------|-------|
| employee_id | yes | From the employee master |
| shift_date | yes | The shift's nominal date |
| shift_id | optional | The specific shift |
| scheduled_hours | yes | What they were scheduled for |
| actual_hours | optional | What they worked |
| absence_hours | optional | scheduled - actual |
| is_absent | yes | 0 or 1 |
| absence_type | optional | Sick / Personal / Vacation / Unexcused / Other |
| covered_by_employee_id | optional | If a floater covered |
| coverage_confirmed | optional | 0=pending / 1=confirmed |
| arrival_time | optional | Datetime |
| departure_time | optional | Datetime |
| is_late | optional | 0 or 1 |
| is_early_departure | optional | 0 or 1 |
| absence_reason | optional | Free text |

### Bulk shortcuts

The toolbar has **"Mark all present"** — sets `is_absent = 0` for the entire roster on the selected shift. Use this at shift start, then individually mark exceptions.

### Use cases

✅ Shift start: bulk-mark present, then flag exceptions
✅ Mid-shift: log late arrivals / early departures as they happen
✅ Coverage tracking: who covered whose absence?

### Hints & tips

☆ The `Bradford Factor` (per-employee) is computed from this data. It's a well-known absenteeism scoring formula: `B = S² × D` where S = number of separate absence spells, D = total days absent.

☆ Coverage tracking enables `/api/coverage` reports — where the floating pool is being deployed.

### Common pitfalls

⛔ Logging full-shift absence as `actual_hours = 0` AND `is_absent = 1`. Pick one — if `is_absent = 1`, the system computes hours; if you set both, validation lets it through but reporting becomes ambiguous.

⛔ Skipping `absence_type` — drives the absenteeism Pareto. Log "Other" as a last resort.

## Quality entry (`/data-entry/quality`)

### What you record

Per quality inspection:

| Field | Required | Notes |
|-------|----------|-------|
| work_order_id | yes | Required (FK to WORK_ORDER) |
| job_id | optional | If multi-job |
| shift_date | yes | The shift |
| inspection_date | optional | If different from shift_date |
| units_inspected | yes | Total inspected |
| units_passed | yes | First-pass-yield numerator |
| units_defective | yes | Failed |
| total_defects_count | yes | Number of defects (NOT same as defective units — multiple defects per unit possible) |
| inspection_stage | optional | Incoming / In-Process / Final |
| process_step | optional | For RTY calc |
| operation_checked | optional | Which station |
| is_first_pass | optional | 0=rework / 1=first |
| units_scrapped | optional | Unrecoverable |
| units_reworked | optional | Recovered |
| units_requiring_repair | optional | Needs rework |
| ppm | optional | Computed: defects/inspected × 1M |
| dpmo | optional | Computed: defects/(inspected × opportunities) × 1M |

### Use cases

✅ In-process inspections (every X bundles)
✅ Final inspections before ship
✅ Incoming inspections of raw material (separate inspection_stage)

### Hints & tips

☆ The platform doesn't enforce that `units_passed + units_defective = units_inspected` — defective units can include rework that comes back through. Instead, check `units_passed + units_defective ≤ units_inspected` and ensure the ratios are sane.

☆ Track `total_defects_count` separately from `units_defective` — a single garment can have multiple defects (loose thread, missing button, oil stain). DPMO uses the defect count.

☆ Drill into individual defects via the `Defects` admin / detail tables — useful for root-cause analysis.

### Common pitfalls

⛔ Treating FPY and PPM as interchangeable. They measure different things (yield vs ppm-of-defects). Use both.

⛔ Skipping `process_step` — you'll lose the ability to compute Rolled Throughput Yield (RTY). Tag it consistently.

## Hold / Resume entry (`/data-entry/hold-resume`)

### What you record

A **hold** pauses a work order; a **resume** restarts it. One pair per pause cycle.

| Field | Required | Notes |
|-------|----------|-------|
| work_order_id | yes | The order being held |
| client_id | yes | Pre-filled |
| hold_date | yes | Datetime when held |
| resume_date | optional | Datetime when resumed |
| hold_initiated_by | yes | User ID |
| resume_initiated_by | optional | User ID |
| hold_reason_id | yes | From per-client hold catalog |
| hold_status | yes | ACTIVE / RESOLVED |
| held_quantity | optional | Units held |
| resolution_notes | optional | Free text |
| approved_by | optional | If hold needs approval |

### Use cases

✅ Material shortage pauses a WO mid-shift → log hold; when material arrives, log resume
✅ Quality investigation pauses a batch → log hold; when cleared, log resume
✅ Customer change order pauses a WO → log hold; when scope agreed, log resume

### Hints & tips

☆ Each client maintains a `hold catalog` (per `/api/hold-catalogs`) — consistent reasons across the team.

☆ The **chronic holds** report (`/api/kpi/chronic-holds`) flags WOs held > N days. Set N per your plant's tolerance.

☆ A WO can be held multiple times. Each hold-resume pair is a row; the WO's total hold time is the sum.

### Common pitfalls

⛔ Forgetting to log the resume — the WO appears stuck on the chronic-holds dashboard forever. Build a habit: every Friday, scan the chronic-holds list and either resume or close out.

⛔ Logging `hold_date` and `resume_date` as the same minute → 0-min hold, no signal. Either log a real hold (> 30 min) or skip.

## Cross-entry checks

Some KPIs require data from MULTIPLE entry surfaces:

- **Efficiency** = production_entry × attendance (head-count present, not assigned)
- **OEE** = production + downtime (availability) + quality (quality)
- **OTD** = work-orders + production (delivered date)
- **Absenteeism** = attendance only

A common gap: efficiency drops because production was logged for `employees_assigned = 6` but actual `employees_present = 4` (not logged). The KPI uses `assigned`. Fix: always log `employees_present` if it differs.

## API endpoints

All under `/api/`:

| Surface | List | Create | Update | Delete |
|---------|------|--------|--------|--------|
| Production | `/production` | `POST /production` | `PUT /production/{id}` | `DELETE /production/{id}` |
| Downtime | `/downtime` | `POST /downtime` | (rare) | (rare) |
| Attendance | `/attendance` | `POST /attendance/bulk` | `PUT /attendance/{id}` | (rare) |
| Quality | `/quality` | `POST /quality` | (rare) | (rare) |
| Hold/Resume | `/holds` | `POST /holds` | `PUT /holds/{id}` | (rare) |
| CSV uploads | (entry-specific path) | `/api/{entry}/upload/csv` | n/a | n/a |

## Next

- [02 — Dashboards](02-dashboards.md) (where the entered data shows up)
- [05 — Work Orders](05-work-orders.md) (the entity entries are tagged to)
