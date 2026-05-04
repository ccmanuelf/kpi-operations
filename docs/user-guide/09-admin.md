# 09 — Admin

The 11 admin views, all under `/admin/*`. Restricted to users with role = admin (router-gated + backend-enforced).

## Quick reference

| Path | Purpose |
|------|---------|
| `/admin/users` | Create / edit / deactivate users |
| `/admin/clients` | Tenant management |
| `/admin/defect-types` | Quality catalog |
| `/admin/client-config` | Per-client behavioral config |
| `/admin/part-opportunities` | Manufacturing opportunities catalog |
| `/admin/floating-pool` | Cross-line operator pool |
| `/admin/workflow-config` | Workflow lifecycle rules |
| `/admin/workflow-designer/:clientId?` | Visual workflow designer (Vue Flow) |
| `/admin/database` | DB connection + migrations |
| `/admin/variance-report` | Calculation assumption variance |
| `/admin/settings` | Platform-wide settings |

## /admin/users

CRUD on the user table.

### Create user

| Field | Notes |
|-------|-------|
| Username | Unique, alphanumeric |
| Email | Unique, used for password reset |
| Full name | For display |
| Password | Server hashes (bcrypt) |
| Role | admin / poweruser / leader / supervisor / operator |
| client_id_assigned | Comma-separated client IDs (NULL for admin/poweruser) |
| Is active | 1 = active, 0 = deactivated |

⚠ Once created, you can't delete a user (referential integrity with audit logs). Deactivate instead — `is_active = 0`.

### Reset password

Admin-initiated. Generates a temporary password, emails to user. User must change on next login.

### Hints

☆ Match `client_id_assigned` to the user's actual access need. Operators should have ONE client; leaders may have several.

☆ Roles map to landing pages (see [01 — Getting Started](01-getting-started.md)). When changing a user's role, advise them their default page changes.

## /admin/clients

The tenant catalog. Each client is a separate scope of data isolation.

### Create client

| Field | Notes |
|-------|-------|
| client_id | Short ID (e.g. `ACME-MFG`) — primary key |
| name | Full name |
| timezone | Default `America/New_York`; affects date rollups |
| created_at | Auto |
| is_active | Toggle |

⚠ `client_id` cannot be changed once set. Choose carefully.

### Per-client features

After creating a client, configure:

1. **Client Config** — efficiency targets, OEE benchmarks, hold catalog
2. **Production Lines** — register the lines (in Capacity Planning)
3. **Hold catalogs** — categories of holds (Material, Quality, etc.)
4. **Default users** — at least one operator + one supervisor

## /admin/client-config

Per-client behavioral parameters:

| Setting | Purpose |
|---------|---------|
| efficiency_target_percent | Card target on dashboard |
| performance_target_percent | Card target |
| availability_target_percent | Card target |
| oee_target_percent | Card target |
| fpy_target_percent | Card target |
| rty_target_percent | Card target |
| quality_target_ppm | Threshold for alerts |
| dpmo_opportunities_default | Default for DPMO calc |
| wip_aging_threshold_days | "Aged" cutoff |
| wip_critical_threshold_days | Critical cutoff |
| default_cycle_time_hours | Fallback when style standard missing |
| otd_mode (standard/true/both) | Which OTD basis |
| absenteeism_target_percent | Card target |

These show up on the dashboards as the green-target lines.

☆ Most clients keep defaults. Tune per-client when:
- Targets are aspirational (industry leaders) — raise
- Targets are recovery-mode (turnaround plant) — lower temporarily

## /admin/defect-types

The catalog of defect types per client (e.g. "Loose Thread", "Missing Button", "Oil Stain").

| Field | Notes |
|-------|-------|
| defect_type_id | Auto |
| client_id | Per-client |
| code | Short code (TH-LOOSE) |
| name | Full name |
| category | Visual / Functional / Cosmetic / Critical |
| is_critical | Boolean — drives ship-blocking |

The platform also has GLOBAL defect types (`/api/defect-types/global`) — common across all clients (typos, count error, etc.). Per-client adds to this list.

### Bulk upload

`POST /api/defect-types/upload/{client_id}` with a CSV. Use the **Download Template** action for the canonical header row.

### Use case

When a client adds a new product family, identify defect types specific to it and add them. Quality entries reference these.

## /admin/floating-pool

The pool of operators who can cover any line. Used for absenteeism mitigation.

| Field | Notes |
|-------|-------|
| employee_id | The pool member |
| skill_level | NOVICE / INTERMEDIATE / EXPERT |
| certified_lines | Which lines they can run |
| availability | DAYS / NIGHTS / FLEX |
| cost_factor | OT premium |

### Pool actions

- **Assign to line** — temporary deployment (today only)
- **Release** — return to pool
- **Coverage report** — `/api/coverage` shows where the pool's been deployed

### Insights

- `/api/floating-pool/simulation/insights` — predictions on pool demand
- `/api/floating-pool/simulation/optimize-allocation` — finds the optimal pool deployment
- `/api/floating-pool/simulation/shift-coverage` — shift coverage report

## /admin/workflow-config

Defines the lifecycle states + allowed transitions for work orders, per client.

Default workflow:

```
PLANNED → IN_PROGRESS → SHIPPED
              ↓
            ON_HOLD → IN_PROGRESS
```

Some clients have additional states: `CUSTOMER_REVIEW`, `EXPEDITED`, `RESERVED`, etc. Configurable here.

### Templates

The platform ships 3 templates (`/api/workflow/templates`):

- **Standard** — full lifecycle (8 states)
- **Simple** — minimal (3 states: PLANNED, IN_PROGRESS, COMPLETE)
- **Express** — closure-trigger workflow (auto-transitions on conditions)

## /admin/workflow-designer/:clientId?

The visual designer. Drag-and-drop nodes (states), edges (transitions), conditions. Saves to `WorkflowConfigView` data.

Built on Vue Flow + Mermaid.

⚠ Editing a live workflow can break in-flight work orders. Best practice:
1. Drafts in isolation (load the workflow as DRAFT)
2. Test on a small client / test client
3. Roll out to production client during low-traffic window

## /admin/database

DB connection + migrations.

| Action | Purpose |
|--------|---------|
| Status | Connection health, version, table count |
| Test connection | Round-trip ping |
| Migrate | Run pending Alembic migrations |
| Migration status | Currently applied vs pending |
| Providers | List supported DB backends (SQLite for dev, MariaDB for prod) |

⚠ Migrations modify schema. Always:
1. Backup before
2. Run during low-traffic window
3. Have a rollback plan (or accept downtime)

## /admin/variance-report

Reports on calculation assumption variances. The platform computes some KPIs with assumptions (e.g. "if efficiency_percentage is missing, compute from earned SAM / available SAM"). This view shows where assumptions kicked in vs explicit values.

| Column | Meaning |
|--------|---------|
| metric | The KPI |
| computed_value | What the platform got |
| input_value | What was logged |
| variance | Difference |
| assumption_used | Which formula/default |
| applied_at | Timestamp |

☆ Use this when a KPI looks "off" — the variance report tells you what assumption was applied.

## /admin/settings

Platform-wide settings:

- App name / logo
- Default timezone
- Default locale (en/es)
- Email / SMTP config
- SendGrid API key
- Notification defaults

Most are environment variables — the UI is for runtime overrides only.

## /admin/part-opportunities

A catalog of "manufacturing opportunities" — process improvements, automation candidates, cost-reduction targets. Each opportunity has:

| Field | Notes |
|-------|-------|
| opportunity_id | Auto |
| client_id | Per-client |
| title | Short name |
| description | Full text |
| category | Process / Automation / Cost / Quality |
| estimated_impact | Quantified benefit |
| status | IDENTIFIED / IN_PROGRESS / IMPLEMENTED / DEFERRED |

This is more "tracking ideas" than operational. Useful for continuous-improvement programs.

## API endpoints

Admin endpoints are scattered:

| Group | Routes |
|-------|--------|
| Database admin | `/api/admin/database/*` (6) |
| Users | `/api/users` (2) |
| Clients | `/api/clients` (7) |
| Client config | `/api/client-config/*` (5) |
| Defect types | `/api/defect-types/*` (7) |
| Part opportunities | `/api/part-opportunities` (4) |
| Floating pool | `/api/floating-pool/*` (11) |
| Employees | `/api/employees` (7) |
| Employee-line assignments | `/api/employee-line-assignments/*` (4) |
| Workflow | `/api/workflow/*` (15) |
| Cache | `/api/cache/*` (4) |
| Health | `/health/*` (6) |
| System | (varies) |

## Common pitfalls

⛔ Adding a user without `client_id_assigned` for non-admin roles. They'll see no data. Always assign.

⛔ Editing the workflow live without testing. Migrate carefully.

⛔ Forgetting to seed defect types for a new client. Quality entries fail silently (or with a 422).

⛔ Wholesale role changes (operator → admin). Verify the user understands the broader access; review the audit log thereafter.

## Next

- [10 — Roles & Permissions](10-roles-permissions.md) (matrix of who can do what)
- [Glossary](glossary.md)
