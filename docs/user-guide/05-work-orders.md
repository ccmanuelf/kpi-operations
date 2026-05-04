# 05 — Work Orders

Where a customer order becomes shop-floor reality. Work orders are the operational unit between the plan (Capacity Planning) and the data (Production Entry).

## What it is

A **work order (WO)** is a unit of production: "make N pieces of style X by date Y." It has a status, a priority, a planned / actual quantity, dates (received, planned ship, actual ship, required), and a workflow history.

A WO is created from:
- A committed Capacity Schedule (auto, the typical path)
- Manual entry (admin only — exceptions)
- CSV upload (bulk transfer from a legacy system)

## Path

`/work-orders` — the list view.

## What you can do

### List, filter, sort

The grid shows all WOs you have access to (filtered by `client_id_assigned`). Columns:

| Column | Meaning |
|--------|---------|
| work_order_id | Unique ID (e.g. `WO-ACME-001`) |
| client_id | Customer / business unit |
| style_model | Product spec |
| planned_quantity | Pieces requested |
| actual_quantity | Pieces produced so far |
| status | Workflow state |
| priority | LOW / MEDIUM / HIGH / URGENT |
| received_date | When the order came in |
| planned_ship_date | Promise date |
| required_date | Customer hard requirement |
| actual_delivery_date | When shipped |
| ideal_cycle_time | Hours/unit (planned) |
| calculated_cycle_time | Hours/unit (computed from actuals) |

Sort, filter, and paginate via the AG Grid controls.

### View detail

Click a WO to open its detail panel. You see:

- **Header info**: all the columns plus job assignments
- **Progress widget**: actual vs planned (bar + %)
- **Timeline**: workflow history (state transitions with timestamps)
- **Jobs**: per-job breakdown if multi-job
- **RTY**: Rolled Throughput Yield computed from quality entries on this WO

### Edit

Editable fields (admin / poweruser / leader / supervisor):

- Status (validated against allowed transitions per the client's workflow)
- Priority
- Notes
- Dates (planned / actual)

⚠ Most numeric fields (`planned_quantity`, `actual_quantity`) are MEANT to be data-driven (from production entries). Edit them only as a deliberate override — and log a note explaining why.

### Status transitions

The platform enforces per-client workflow rules. The full `WorkOrderStatus` enum (11 states):

```
RECEIVED → RELEASED → IN_PROGRESS → COMPLETED → SHIPPED → CLOSED
                          ↓             │
                       ON_HOLD          └─> REJECTED
                          ↓
                      DEMOTED  /  CANCELLED  /  ACTIVE (legacy alias)
```

Demo data exercises: SHIPPED (on-time + late), IN_PROGRESS, RECEIVED, ON_HOLD.

The `Workflow Designer` (Admin → Workflow Designer) lets admins define custom workflows per client — additional states, custom transitions.

`GET /api/workflow/work-orders/{id}/allowed-transitions` returns valid next states given the current state. The UI uses this to populate the status dropdown.

### Capacity link

A WO can be linked to a Capacity Order (the planning entity in the workbook). The link is bidirectional:

- `POST /api/work-orders/{id}/link-capacity` — link
- `POST /api/work-orders/{id}/unlink-capacity` — unlink
- `GET /api/work-orders/{id}/capacity-order` — fetch the linked order

When linked, the WO's planned quantity ties to the capacity order's planned quantity — changes propagate.

### QC approval

`POST /api/work-orders/{id}/approve-qc` — the gate before SHIPPED status. Quality team reviews the final inspection results, signs off.

### Bulk import (CSV)

`POST /api/work-orders/upload/csv` — for legacy migrations or external systems. Same template-validate-import flow as other entry surfaces.

## Use cases

✅ Daily standup: "what's in flight?"
✅ Customer service: "where's order WO-XXX-001?"
✅ Quality team: review WOs awaiting QC
✅ Shop floor: route current production entries to the right WO

## Hints & tips

☆ Sort by `planned_ship_date` ascending — your top priority WOs are at the top.

☆ The `priority` column color-codes URGENT (red), HIGH (amber), so visual scanning is fast.

☆ Use `GET /api/work-orders/status/IN_PROGRESS` to see only active WOs (filters out completed).

☆ The `RTY` value on the detail panel is gold — it's the cumulative quality across all operations this WO touched.

## Interpreting the metrics

| Metric | Healthy | Investigate |
|--------|---------|-------------|
| `actual_quantity / planned_quantity` | 95-105% | < 90% (under) or > 110% (over) |
| Time to ship (received → shipped) | within 2× lead time | > 3× lead time |
| RTY | 80%+ | < 70% |
| Status stuck at IN_PROGRESS | < 7 days | > 14 days |

A WO stuck at IN_PROGRESS for 14+ days is a chronic — usually a quality issue, material shortage, or simply forgotten. The chronic holds report flags these.

## Common pitfalls

⛔ Editing planned_quantity without a note. Six months later, no one remembers why.

⛔ Marking SHIPPED without quality approval. Workflow designer should enforce this; if your client's workflow doesn't, talk to your admin.

⛔ Not linking to a Capacity Order — the planning side loses its actuals link.

## Cross-feature integrations

| Feature | Integration |
|---------|-------------|
| Capacity Planning | WOs originate from committed schedules |
| Production Entry | Operators tag entries with `work_order_id` |
| Quality Entry | Quality entries reference `work_order_id` for RTY |
| Hold/Resume | Each pause-cycle is a hold-resume row tied to the WO |
| Plan vs Actual | Per-WO variance reporting |
| Reports | WO-level rollups in production / quality reports |
| Alerts | OTD-risk alerts trigger when actual_delivery > required_date |

## API endpoints

14 routes under `/api/work-orders/*`:

| Endpoint | Purpose |
|----------|---------|
| `GET /work-orders` | List all WOs (filtered by client_id) |
| `POST /work-orders` | Create (admin) |
| `GET /work-orders/{id}` | Detail |
| `PUT /work-orders/{id}` | Edit |
| `DELETE /work-orders/{id}` | Soft delete |
| `GET /work-orders/status/{status}` | Filter by status |
| `GET /work-orders/date-range` | Filter by date range |
| `POST /work-orders/upload/csv` | Bulk import |
| `GET /work-orders/{id}/jobs` | Jobs for the WO |
| `GET /work-orders/{id}/progress` | Progress widget data |
| `GET /work-orders/{id}/rty` | Rolled Throughput Yield |
| `GET /work-orders/{id}/timeline` | Workflow history |
| `POST /work-orders/{id}/approve-qc` | QC gate |
| `POST /work-orders/{id}/link-capacity` | Link to Capacity Order |
| `POST /work-orders/{id}/unlink-capacity` | Unlink |
| `GET /work-orders/{id}/capacity-order` | Linked Capacity Order |
| `GET /work-orders/{id}/status` | Current status |
| `POST /api/workflow/work-orders/{id}/transition` | Trigger a state transition |
| `GET /api/workflow/work-orders/{id}/allowed-transitions` | Valid next states |
| `GET /api/workflow/work-orders/{id}/history` | Full transition log |
| `GET /api/workflow/work-orders/{id}/elapsed-time` | Time per state |
| `GET /api/workflow/work-orders/{id}/transition-times` | Stats on past transitions |
| `POST /api/workflow/work-orders/{id}/validate` | Pre-flight validation of a proposed transition |

## Next

- [03 — Data Entry](03-data-entry.md) (entries that tag a WO)
- [06 — Alerts](06-alerts.md) (alerts on at-risk WOs)
- [04 — Capacity Planning](04-capacity-planning.md) (where WOs originate)
