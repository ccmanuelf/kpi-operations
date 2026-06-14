# 10 — Roles & Permissions

## The 6 roles

| Role | Designed for | Default landing | Can see |
|------|--------------|-----------------|---------|
| **Admin** | Plant manager, IT admin | `/kpi-dashboard` | Everything |
| **PowerUser** | Planner, scheduler, engineer | `/capacity-planning` | All non-admin features |
| **Leader** | Line/quality lead | `/` | Operations + Monitoring |
| **Supervisor** | Shift supervisor | `/` (fallback) | Operations + Monitoring |
| **Operator** | Line operator (data collector) | `/my-shift` | Operations + Monitoring (single client) |
| **Viewer** | Read-only stakeholder | `/` | Operations + Monitoring (single client), **read-only** |

> **Canonical role set (Run 7):** all six are values of the `UserRole` enum
> (`backend/orm/user.py`) and are accepted by the user-management API. For
> **write** authority they collapse into the guard tiers below: Leader and
> Supervisor are equivalent (supervisory tier), and Viewer can read but
> cannot create or modify any record (it is excluded from every write guard).

## What each role can do

### Read access

| Surface | Admin | PowerUser | Leader | Supervisor | Operator | Viewer |
|---------|:-----:|:---------:|:------:|:----------:|:--------:|:------:|
| Home / KPI Dashboard | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| MyShift | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| KPI sub-views (Efficiency, OEE, etc.) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Plan vs Actual | ✓ | ✓ | ✓ | ✓ | — | — |
| Capacity Planning workbook | ✓ | ✓ | view-only | view-only | — | — |
| Work Orders | ✓ | ✓ | ✓ | ✓ | view-only | view-only |
| Alerts (their data) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Reports | ✓ | ✓ | ✓ | — | — | — |
| Admin section | ✓ | — | — | — | — | — |

### Write / mutate

| Action | Admin | PowerUser | Leader | Supervisor | Operator | Viewer |
|--------|:-----:|:---------:|:------:|:----------:|:--------:|:------:|
| Production entry | ✓ | ✓ | ✓ | ✓ | ✓ (own line) | — |
| Downtime / Attendance / Quality / Hold entry | ✓ | ✓ | ✓ | ✓ | ✓ (own line) | — |
| Create / edit / patch-status work orders | ✓ | ✓ | ✓ | ✓ | — (Run-6 audit added explicit gate) | — |
| Delete work orders | ✓ | — | — | ✓ | — | — |
| Edit capacity workbook | ✓ | ✓ | — | — | — | — |
| Save scenarios | ✓ | ✓ | — | — | — | — |
| Run simulation (V2) | ✓ | ✓ | ✓ | ✓ | — | — |
| Run MiniZinc patterns (P1-P4) | ✓ | ✓ | ✓ | ✓ | — | — |
| Manage users / clients | ✓ | — | — | — | — | — |
| Trigger DB migrations | ✓ | — | — | — | — | — |

### How this is enforced (Run 7)

Every mutation endpoint carries one of four route-level guard tiers
(`backend/auth/jwt.py`), applied uniformly in the Run 7 permission sweep:

| Tier | Roles | Covers |
|------|-------|--------|
| **admin** | admin | users/clients management, client CSV import, DB migrations, cache invalidation, nightly batch triggers |
| **planner** | admin, poweruser | capacity workbook/orders/BOM/calendar/lines/standards/schedules, capacity scenarios, KPI thresholds, client configuration |
| **supervisory** | admin, poweruser, leader, supervisor | operations master data (employees, jobs, floating pool, part opportunities), work-order transitions, bulk/CSV imports, simulation V2 runs & scenarios, alert generation/config, report email config |
| **contributor** | admin, poweruser, leader, supervisor, operator (everyone except viewer) | transactional data entry (production, downtime, attendance, quality, holds, coverage, defects) |
| *(authenticated)* | all roles incl. viewer | personal-scoped writes (own filters, preferences) and alert acknowledge/resolve |

Viewer is the read-only floor: it passes the `(authenticated)` row only, and is
denied by the contributor tier and above. These tiers are pinned by
`backend/tests/test_security/test_permission_matrix.py`.

## Multi-tenant isolation

Every database row carries a `client_id`. The platform filters queries server-side based on the user's `client_id_assigned`:

| Role | Sees data from |
|------|----------------|
| Admin / PowerUser | All clients |
| Leader | One or more clients (comma-separated `client_id_assigned`, e.g. `ACME-MFG,TEXTILE-PRO`) |
| Operator / Supervisor | Exactly one client |

⚠ This is enforced at the API layer (every backend route filters), so you cannot bypass it from a non-admin browser session even if you craft a URL by hand.

## Audit trail

Mutations are logged to the `[AUDIT]` log channel with:
- Endpoint + HTTP method
- User identifier
- Status code
- Latency

Look at the backend logs (`/tmp/backend-uvicorn.log` locally; Render dashboard logs in production) for forensic review. Sensitive operations (login, logout, role change, password change) also log to `[SECURITY]`.

## Token lifecycle

- Login returns a JWT (HS256) valid for 30 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- Logout records the token's `jti` in the `TOKEN_BLACKLIST` table; the revocation persists across restarts and is enforced on every request until the token expires (Run 7)
- Refresh: the platform does NOT auto-refresh; on expiry you're sent to login

## Adding / managing users

Admin → **Administration** → **Users**:
- Create user with role (must match one of the 5 enum values)
- Assign client(s) — comma-separated `client_id_assigned`
- Reset password (admin-initiated)
- Activate / deactivate (no hard delete — preserves audit references)

⛔ Don't share the admin login. The audit log will attribute every action to that single account, defeating accountability.

## When access is denied

| Symptom | Cause | What to do |
|---------|-------|------------|
| 401 + redirect to `/login` | Token missing or expired | Log in again |
| 403 on a backend call | Your role doesn't include this action | Check this matrix; ask admin to escalate role or grant client |
| Admin URL bounces to `/` | `requiresAdmin: true` and you're not admin | Expected behavior |
| You see no data on a dashboard | Your `client_id_assigned` doesn't match any data | Verify client assignment with admin |
