# 06 — Alerts

The platform's exception engine. Surfaces things that warrant human attention without burying them in dashboards.

## What it is

An **alert** is a structured notification triggered when a metric crosses a threshold (or a pattern fires — late delivery risk, quality trend, capacity overload, attendance spike, hold approval pending).

Alerts have:

| Field | Meaning |
|-------|---------|
| category | What kind: otd, delivery, quality, efficiency, capacity, attendance, downtime, maintenance, availability, hold, trend, quality_ppm, absenteeism |
| severity | LOW / MEDIUM / HIGH / CRITICAL |
| title | One-line summary |
| message | Detail body |
| recommendation | Suggested action |
| status | ACTIVE / ACKNOWLEDGED / RESOLVED / DISMISSED |
| created_at, acknowledged_at, resolved_at | Lifecycle timestamps |

## Path

`/alerts` — the inbox view.

## What you can do

### Triage (the daily routine)

Open `/alerts`. Default sort: severity descending, then created_at descending. Walk top-down:

1. **CRITICAL** → drop everything; immediate action
2. **HIGH** → today
3. **MEDIUM** → this week
4. **LOW** → review at standup

Each row has 4 actions:

- **Acknowledge** — "I see this, I'm working on it"
- **Resolve** — "Done; root cause addressed"
- **Dismiss** — "Not actionable / false positive"
- **Detail view** — full context, recommended action

### Acknowledge

`POST /api/alerts/{id}/acknowledge` — moves status from ACTIVE to ACKNOWLEDGED. The alert stays visible but with reduced urgency styling.

### Resolve

`POST /api/alerts/{id}/resolve` — final state. Captures `resolved_by` and an optional resolution note. Used for KPIs (alert response time).

### Dismiss

`POST /api/alerts/{id}/dismiss` — false positive or no-longer-relevant. Captures dismissal reason.

⚠ **Caution**: dismissing should be rare. If a category of alert dismisses repeatedly, raise the threshold (in Alert Config) instead of dismissing each instance.

### Generate (manually)

By default, the platform auto-generates alerts on a schedule. You can also trigger:

- `POST /api/alerts/generate/check-all` — scan all categories
- `POST /api/alerts/generate/otd-risk` — OTD risk
- `POST /api/alerts/generate/quality` — quality trend
- `POST /api/alerts/generate/capacity` — capacity overload

Useful when you've just made a config change and want immediate visibility.

## The alert configuration

Admin → manages alert thresholds via `/api/alerts/config/`. Each config has:

| Field | Meaning |
|-------|---------|
| client_id | Per-client (or NULL = global) |
| alert_type | Category |
| enabled | Toggle on/off |
| warning_threshold | Triggers MEDIUM |
| critical_threshold | Triggers HIGH/CRITICAL |
| notification_email | Email out on trigger |
| notification_sms | SMS out on trigger |
| check_frequency_minutes | How often the rule runs |

Examples (from the demo seed):

| Config | Warning | Critical |
|--------|---------|----------|
| efficiency (global) | 75% | 60% (low) |
| quality_ppm (global) | 5000 PPM | 10000 PPM |
| OTD (global) | 90% | 80% (low) |
| absenteeism (global) | 5% | 10% |
| efficiency (ACME-MFG) | 80% | 65% |

Per-client configs override globals.

## Use cases

✅ Daily morning triage: scan CRITICAL/HIGH, plan the day around them
✅ Customer-facing escalation: OTD risk alerts come days before the missed ship
✅ Quality trend signal: PPM creeping → investigate before it becomes a recall
✅ Capacity overload: alert before the line is fully booked → buys time to negotiate

## Hints & tips

☆ The alerts dashboard (`/api/alerts/dashboard`) is also embedded as a card on the Home page — keep it visible.

☆ Acknowledge alerts you're working on so other team members don't duplicate effort. Use Resolve only when truly closed.

☆ The **alert accuracy** view (`/api/alerts/history/accuracy`) tracks how often dismissed alerts came back as real issues. If accuracy > 80%, the system is working; if < 50%, raise the thresholds.

☆ Email + SMS notifications are configured per alert type. CRITICAL alerts should always notify; LOW never should — it's the operator's eyeball job.

## Interpreting alert payload

When you read an alert, look for:

1. **Title** — what's the headline?
2. **Severity** — how urgent?
3. **Recommendation** — what should you do? The platform tries to suggest a concrete action (e.g. "Reduce changeover frequency on Line A — 6 changeovers today vs 3-4 baseline").
4. **Linked entity** — alerts often carry a `work_order_id`, `line_id`, or `employee_id`. Click to jump to the entity's detail view.

A good alert is **actionable**, not informational. If you find an alert that just says "metric crossed threshold" with no recommendation, file feedback — the recommendation engine should be improved.

## Common pitfalls

⛔ Letting CRITICAL alerts pile up. The inbox is a worklist, not a log. If you have > 10 CRITICAL alerts, you've lost control.

⛔ Dismissing repeatedly without raising thresholds. The pattern of dismissal IS the signal — adjust config.

⛔ Treating LOW alerts as noise. If they go un-actioned for weeks they may indicate a real chronic issue. Skim them.

## Cross-feature integration

| Feature | How it triggers alerts |
|---------|------------------------|
| Production Entry | Efficiency / performance below threshold |
| Quality Entry | DPMO / FPY trend break |
| Attendance Entry | Absenteeism spike |
| Hold/Resume | Hold > N days = chronic alert |
| Work Orders | OTD risk (planned_ship_date approaching, low actual progress) |
| Capacity Planning | Line overload, material shortage |

## API endpoints

13 routes under `/api/alerts/*`:

| Endpoint | Purpose |
|----------|---------|
| `GET /alerts/` | List active alerts |
| `GET /alerts/dashboard` | Dashboard card data |
| `GET /alerts/summary` | Aggregated counts |
| `GET /alerts/{id}` | Detail |
| `POST /alerts/{id}/acknowledge` | ACK |
| `POST /alerts/{id}/dismiss` | Dismiss |
| `POST /alerts/{id}/resolve` | Resolve |
| `POST /alerts/generate/check-all` | Scan all |
| `POST /alerts/generate/otd-risk` | OTD scan |
| `POST /alerts/generate/quality` | Quality scan |
| `POST /alerts/generate/capacity` | Capacity scan |
| `GET /alerts/history/accuracy` | Triage accuracy KPI |
| `GET /alerts/config/` | Alert config CRUD |

## Next

- [02 — Dashboards](02-dashboards.md) (where alert-causing metrics live)
- [05 — Work Orders](05-work-orders.md) (the entity most alerts attach to)
