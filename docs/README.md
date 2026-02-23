# KPI Operations Platform

Manufacturing KPI tracking and capacity planning platform with multi-tenant architecture. Designed for shopfloor operators and technicians as a bridge tool for operations without a full MES system, replacing Excel spreadsheets and whiteboards with structured, data-driven workflows.

## Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Backend** | Python, FastAPI, SQLAlchemy, Pydantic, uvicorn | 3.12, 0.129, 2.0.46, 2.12, 0.40 |
| **Frontend** | Vue 3, Pinia, Vuetify 3, vue-router, vue-i18n, Vite | 3.4, 3, 3, 5, 11, 7.3 |
| **Database** | SQLite (dev/demo), MariaDB (production) | |
| **Testing** | pytest + Vitest | 6,386+ tests (4,910 backend, 1,476 frontend) |
| **Auth** | JWT + bcrypt | Role-based, multi-tenant |

## Modules

- **Production Data Entry** -- Work orders, jobs, line items, production tracking with CSV bulk upload and read-back confirmation
- **Quality Management** -- Defect tracking (PPM, DPMO, FPY, RTY), inspection records, Pareto analysis, quality KPIs
- **Attendance and Absenteeism** -- Employee attendance, floating pool management, shift coverage tracking
- **Downtime Tracking** -- Equipment downtime, reason codes, availability KPIs
- **KPI Dashboard** -- OEE, efficiency, performance, quality, availability, on-time delivery, WIP aging, absenteeism with configurable thresholds and trend analysis
- **Capacity Planning** -- 13-worksheet workbook: orders, BOM, standards, production lines, calendar, stock, component check, analysis, schedule, scenarios, KPI tracking, plan vs actual, instructions
- **Alert System** -- Configurable thresholds, alert dashboard, notification management with history
- **Work Order Management** -- Full lifecycle (active, on-hold, completed, cancelled, rejected) with hold catalog support
- **Shift Management** -- Shift definitions, break times, shift coverage analysis
- **Onboarding** -- Guided workflow for new client setup
- **Simulation** -- Line balancing V1 (deprecated, sunset 2026-06-01) + V2 (SimPy discrete-event) with what-if scenarios
- **Admin** -- Users, clients, defect types, part opportunities, employee-line assignments, equipment management

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
python scripts/init_demo_database.py   # Seeds demo data (5 clients, 51 tables)
uvicorn backend.main:app --reload
```

Backend available at http://localhost:8000. API docs at http://localhost:8000/docs.

### Frontend

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

Frontend available at http://localhost:5173.

## Demo Credentials

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | admin |
| supervisor1 | password123 | supervisor |
| operator1 | password123 | operator |
| operator2 | password123 | operator |

Five demo clients are seeded: ACME-MFG, TechCorp, GlobalMfg, PrecisionParts, SmartFactory.

## Docker

```bash
docker-compose up --build
```

The backend auto-seeds demo data on first startup when it detects an empty database. No manual SQL import or migration step is required.

## API

80+ endpoints across 14 route sub-packages, all requiring JWT authentication (except auth and health):

| Sub-Package | Prefix | Modules |
|-------------|--------|---------|
| `auth` | `/api/token`, `/api/register` | Authentication, registration |
| `capacity/` | `/api/capacity/*` | 10 modules (orders, BOM, lines, calendar, standards, analysis, scenarios, KPI workbook, stock, WO bridge) |
| `kpi/` | `/api/kpi/*` | 7 modules (dashboard, calculations, efficiency, OTD, thresholds, trends) |
| `simulation/` | `/api/simulation/*` | 8 modules (capacity, efficiency, staffing, shift coverage, floating pool, production line, overview, comprehensive) |
| `alerts/` | `/api/alerts/*` | Config history, CRUD, generation |
| `analytics/` | `/api/analytics/*` | Comparisons, predictions, trends |
| `quality/` | `/api/quality/*` | Entries, PPM/DPMO, FPY/RTY, Pareto |
| `reports/` | `/api/reports/*` | Production, KPI, comprehensive, email config |
| Single-file routes | Various | attendance, work orders, jobs, holds, downtime, shifts, employees, production, users, floating pool, onboarding, and more |

All routes use structured logging via `get_module_logger(__name__)` (100% coverage).

## Tests

| Suite | Count | Coverage |
|-------|-------|----------|
| Backend (pytest) | 4,910+ passed | 75%+ |
| Frontend (Vitest) | 1,476+ passed | 30%+ (V8 provider) |
| **Total** | **6,386+** | |

```bash
# Backend
cd backend && pytest tests/ -v --cov=backend

# Frontend
cd frontend && npm run test
```

## Project Structure

```
kpi-operations/
  backend/
    main.py                  # FastAPI app, lifespan, middleware
    config.py                # Settings with production validation
    database.py              # Connection pooling, session management
    auth/                    # JWT, password policy
    calculations/            # KPI business logic (12 modules)
    crud/                    # Data access layer (17 modules)
    orm/                     # SQLAlchemy ORM models (all imported in __init__.py)
    models/                  # Pydantic request/response schemas
    routes/                  # API endpoints (14 sub-packages + single-file routes)
      capacity/              # 10 modules
      kpi/                   # 7 modules
      simulation/            # 8 modules
      alerts/                # 3 modules
      analytics/             # 4 modules
      quality/               # 4 modules
      reports/               # 5 modules
    services/capacity/       # 7 capacity planning services
    events/                  # Domain event bus (collect/flush pattern)
    simulation_v2/           # SimPy-based simulation engine
    db/migrations/           # Demo seeder + capacity table creation
    scripts/                 # init_demo_database.py, backup, utilities
  frontend/src/
    views/                   # Page views (admin/, kpi/, CapacityPlanning/, etc.)
    components/              # Vue components (grids, entries, widgets, filters)
    composables/             # Reusable logic (6 composables extracted from large views)
    stores/                  # Pinia state management
      capacity/              # Capacity planning sub-stores
    services/api/            # API sub-modules (18 modules)
    router/                  # Vue Router definitions
    assets/                  # CSS (Carbon Design tokens, responsive, Tailwind)
  database/                  # SQLite DB file (dev)
  docs/                      # Documentation
  render.yaml                # Render.com deployment blueprint
  docker-compose.yml         # Docker orchestration
  Dockerfile                 # Backend Docker image
  frontend/Dockerfile        # Frontend Docker image (nginx)
```

## Deployment

See `docs/DEPLOYMENT.md` for full deployment instructions covering:

- Bare-metal with systemd + nginx
- Docker Compose
- Render.com (one-click deploy via `render.yaml`)

## Naming Convention

This project uses a non-standard naming convention:

| Directory | Contains | Standard Convention |
|-----------|----------|---------------------|
| `backend/models/` | Pydantic schemas | Usually SQLAlchemy models |
| `backend/orm/` | SQLAlchemy ORM models | Usually `models/` |

This is documented and internally consistent.

## License

Proprietary -- All rights reserved.

---

**Last Updated**: 2026-02-23
