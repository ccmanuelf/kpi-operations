# 01 — Getting Started

## What this is

A web-based platform that brings together:
- **Daily data entry** for production, downtime, attendance, quality
- **KPI dashboards** for efficiency, OEE, OTD, FPY/RTY, absenteeism
- **Capacity planning workbook** for orders, BOM, scenarios, schedules
- **Simulation tools** to predict line behavior under variability + 4 prescriptive optimization patterns

It runs in your browser, supports English/Spanish, and works in light or dark mode.

## Logging in

Visit `/login` (the URL depends on your deployment — local, Render staging, or production).

Demo credentials (development environments only):

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin (everything) |
| `poweruser` | `password123` | PowerUser (planning, ops, monitoring) |
| `leader1` | `password123` | Leader (ops, monitoring, multiple clients) |
| `operator1` | `password123` | Operator (single client, line-level data) |
| `supervisor1` | `password123` | Supervisor (between leader and operator) |

⚠ In production these accounts are disabled or have rotated passwords. Contact your administrator for real credentials.

### What happens after login

You're redirected to a role-specific landing page:

| Role | Lands on |
|------|----------|
| Operator | `/my-shift` |
| Leader | `/` (Home dashboard) |
| PowerUser | `/capacity-planning` |
| Admin | `/kpi-dashboard` |
| Supervisor | `/` (fallback) |

If you bookmark a deeper URL, you'll be sent to login first, then returned to your bookmark.

## The navigation drawer

The left-side drawer is grouped into 5 sections. Every authenticated user sees ALL groups; only the **default expansion** changes by role:

| Group | Default expanded for |
|-------|----------------------|
| **Planning** (Capacity Planning, Work Orders, Plan vs Actual) | Admin, PowerUser |
| **Operations** (My Shift, Production Entry, Downtime, Attendance, Quality, Hold/Resume) | Admin, PowerUser, Leader, Operator |
| **Monitoring** (Home, KPI Dashboard, Alerts) | Admin, PowerUser, Leader, Operator |
| **KPI Detail** (8 individual KPI views: Efficiency, Performance, Quality, Availability, OEE, WIP Aging, OTD, Absenteeism) | Admin |
| **Administration** (11 admin tools) | Admin only — clicking from non-admin role bounces back |

The simulation link is always visible (cross-role analysis tool).

☆ Tip: collapse the drawer to a thin rail by clicking the chevron in the upper-left — useful on smaller screens.

## Toggling theme & language

The top bar carries:

- **🌗 Dark mode toggle** — your preference is stored per-tab and synced across tabs in the same browser
- **English / Spanish** buttons — full UI translation; the toggle is also on the login screen

⚠ Some chart annotations and PDF reports still render in the source language even when the UI is switched — this is being addressed.

## Logging out

Top-right has a logout button. Logging out:
1. Clears your local token + user info
2. Adds the token to a blacklist server-side (so reuse is rejected)
3. Returns you to `/login`

## When something goes wrong

- **"Session expired" / 401 redirects to login**: your JWT timed out (default 8h). Just log in again.
- **403 on a page you "should" see**: the route requires admin (e.g. `/admin/*`). Operators clicking those see the home page instead.
- **A page loads forever / blank**: open the browser console (F12) — errors usually point at a backend that's still warming up (Render free tier sleeps after 15 min idle).
- **Numbers look stale**: most dashboards refresh on navigation, not on a timer. Click another nav item and back to force a refresh, or use the page's reload button if present.

## A 5-minute orientation tour

If you've never used the platform before, spend 5 minutes here:

1. **Login** as admin → land on `/kpi-dashboard`. Skim the cards: throughput, OEE, FPY, absenteeism. Each card is also a navigable link to its detailed view.
2. **Click "Capacity Planning"** in Planning. Cycle through the 13 tabs to see what the workbook holds (orders, lines, BOM, scenarios, etc.).
3. **Click "Simulation"** (cross-role link). The Operations tab is pre-loaded with a Basic T-Shirt sample. Click **"Run Simulation"** — you get throughput, daily summary, station performance, etc.
4. **Click "Optimize Operators"** to see Pattern 1 in action. The dialog shows a proposed allocation that minimizes head-count.
5. **Toggle dark mode** in the top bar — confirm your preferred theme.

You're oriented. The rest of this guide drills into individual features.

## Next

- [02 — Dashboards](02-dashboards.md) (you'll spend most of your screen-time here if you're a leader/admin)
- [10 — Roles & Permissions](10-roles-permissions.md) (if you need to set up other users)
- [Glossary](glossary.md) (if any term confuses you)
