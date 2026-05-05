# KPI Operations Platform - Architecture Documentation

**Version**: 2.0.0
**Last Updated**: 2026-02-23
**Architecture Grade**: B+ (weighted score 85.6, targeting A- post-remediation)

---

## Executive Summary

KPI Operations is a manufacturing KPI tracking platform designed for shopfloor operators and technicians. It serves as a bridge tool for operations without a full MES system, replacing Excel spreadsheets and whiteboards with a structured, data-driven approach.

### Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Frontend** | Vue 3 + Vuetify 3 + Pinia | 3.4 / 3.5 / 3.0 |
| **Backend** | FastAPI + SQLAlchemy + Pydantic | 0.129 / 2.0.46 / 2.12 |
| **Database** | SQLite (dev) / MariaDB (prod) | 51 tables |
| **Authentication** | JWT + bcrypt | HS256, token blacklist enforced |
| **Data Grid** | AG-Grid Community | - |
| **Design System** | IBM Carbon (tokens) | - |
| **Testing** | pytest + Vitest 4.0 | 4,910+ backend / 1,476+ frontend |

---

## System Architecture

```
+-----------------------------------------------------------------+
|                         FRONTEND                                |
|  Vue 3 + Vuetify + Pinia                                       |
|  +----------+ +----------+ +----------+ +----------+           |
|  |  Views   | |Components| |  Stores  | |Composables|          |
|  +----+-----+ +----+-----+ +----+-----+ +----+-----+          |
|       +------------+------------+------------+                  |
|                         |                                       |
|                    API Service (18 sub-modules)                 |
+-------------------------+---------------------------------------+
                          | HTTP/REST
+-------------------------+---------------------------------------+
|                         BACKEND                                 |
|  FastAPI                                                        |
|  +---------------------------------------------------------+   |
|  |                  Routes (14 sub-packages)                |   |
|  |  auth | capacity/ | kpi/ | simulation/ | quality/ | ...  |   |
|  +-------------------------+-------------------------------+   |
|                            |                                    |
|  +-------------------------+-------------------------------+   |
|  |   Middleware             |         Calculations          |   |
|  |   - Auth (JWT)           |         - efficiency.py       |   |
|  |   - Rate Limit           |         - otd.py              |   |
|  |   - Client Filter        |         - ppm.py              |   |
|  |   - V1 Deprecation       |         - performance.py      |   |
|  |   - API Version Rewrite  |         - availability.py     |   |
|  +-------------------------+-------------------------------+   |
|                            |                                    |
|  +-------------------------+-------------------------------+   |
|  |                     CRUD Layer (17 modules)              |   |
|  +-------------------------+-------------------------------+   |
|                            |                                    |
|  +-------------------------+-------------------------------+   |
|  |              ORM Models (backend/orm/, 51 tables)        |   |
|  |  Client | WorkOrder | Job | Production | Quality | ...   |   |
|  +-------------------------+-------------------------------+   |
+----------------------------+------------------------------------+
                             |
+----------------------------+------------------------------------+
|                        DATABASE                                 |
|  SQLite (dev) / MariaDB (prod)                                 |
|  Multi-tenant with client_id isolation (5 demo clients)        |
+-----------------------------------------------------------------+
```

---

## Backend Architecture

### Directory Structure

```
backend/
  main.py                  # App setup, lifespan, middleware, route registration
  config.py                # Configuration with production validation (DEFAULT_INSECURE_VALUES guard)
  database.py              # Connection pooling, session management
  dependencies.py          # Shared FastAPI Depends (PaginationParams)
  auth/
    jwt.py                 # JWT token utilities (HS256, blacklist enforcement)
    password_policy.py     # Password strength validation
  calculations/            # Business logic (12 modules)
    efficiency.py          # Efficiency with inference engine
    otd.py                 # On-Time Delivery calculations
    ppm.py                 # Parts Per Million (quality)
    performance.py         # Performance metrics
    availability.py        # Machine availability
    ...
  crud/                    # Data access layer (17 modules)
    production.py
    quality.py
    attendance.py
    ...
  orm/                     # SQLAlchemy ORM models (all imported in __init__.py)
    __init__.py            # Central registry -- every model file MUST be imported here
    client.py, user.py, work_order.py, job.py, ...
    capacity/              # 13 capacity planning tables
  models/                  # Pydantic request/response schemas
  routes/                  # API endpoint modules (14 sub-packages + single-file routes)
    capacity/              # 10 modules: analysis, bom_stock, calendar, lines, orders, scenarios, standards, kpi_workbook, work_order_bridge, _models
    kpi/                   # 7 modules: dashboard, calculations, efficiency, otd, thresholds, trends
    simulation/            # 8 modules: capacity, efficiency, staffing, shift_coverage, floating_pool, production_line, overview, comprehensive
    alerts/                # 3 modules: config_history, crud, generate
    analytics/             # 4 modules: _helpers, comparisons, predictions, trends
    quality/               # 4 modules: entries, fpy_rty, pareto, ppm_dpmo
    reports/               # 5 modules: _models, comprehensive_reports, email_config, kpi_reports, production_reports
    [single-file routes]   # auth, attendance, work_orders, jobs, holds, downtime, shifts, employees, production, users, floating_pool, onboarding, simulation_v2, simulation_scenarios (D3), simulation_calibration (D4), etc.
  services/capacity/       # 7 capacity planning services (facade pattern)
  services/                # simulation_calibration.py (D4) and other cross-cutting services
  events/                  # Domain event bus (collect/flush pattern)
  simulation_v2/           # SimPy discrete-event engine + Monte Carlo + MiniZinc optimization/ (4 patterns)
  reports/                 # PDF/Excel generation
  db/migrations/           # Demo seeder (demo_seeder.py) + capacity table creation
  scripts/                 # init_demo_database.py, backup utilities
  utils/
    logging_utils.py       # get_module_logger() -- used by all route modules
```

### Key Design Patterns

#### 1. Multi-Tenant Isolation (Security)

Every query is filtered by `client_id` to ensure data isolation:

```python
def build_client_filter_clause(current_user):
    """Build client filter for multi-tenant isolation"""
    if current_user.is_admin:
        return True  # Admins see all
    return Entity.client_id == current_user.client_id
```

#### 2. Inference Engine (Efficiency Calculation)

When actual data is missing, the system infers values with confidence scores:

```python
@dataclass
class InferredEmployees:
    count: int
    is_inferred: bool
    inference_source: str  # "employees_assigned", "employees_present", "historical_avg", "default"
    confidence_score: float  # 1.0 actual, 0.8 present, 0.5 historical, 0.3 default
```

**Inference Chain:**
1. `employees_assigned` (confidence: 1.0) - Direct entry
2. `employees_present` (confidence: 0.8) - Attendance data
3. `historical_shift_avg` (confidence: 0.5) - Historical average
4. `default` (confidence: 0.3) - Configurable default

#### 3. Role-Based Access Control

| Role | Permissions |
|------|-------------|
| ADMIN | Full access, all clients |
| POWERUSER | Full access, own client |
| LEADER | Read/write, own client |
| OPERATOR | Read/limited write, own client |

#### 4. Route Sub-Package Pattern

All major route groups have been refactored from monolithic files into sub-packages with `__init__.py` assembling sub-routers:

```
routes/kpi/
  __init__.py       # Assembles sub-routers into kpi_router
  dashboard.py      # GET /api/kpi/dashboard
  calculations.py   # GET /api/kpi/calculate/{id}
  efficiency.py     # Efficiency-specific endpoints
  otd.py            # On-Time Delivery endpoints
  thresholds.py     # Threshold CRUD
  trends.py         # Trend analysis
```

All route modules use `get_module_logger(__name__)` from `backend.utils.logging_utils` for structured logging (100% coverage).

#### 5. Lifespan Context Manager

The application uses FastAPI's `lifespan` context manager (not the deprecated `@app.on_event`). The lifespan handler:
1. Runs `Base.metadata.create_all()` to ensure all tables exist
2. Validates ORM registry completeness (warns if <45 tables detected)
3. Creates capacity planning tables
4. Initializes domain event infrastructure
5. Starts the daily report scheduler
6. Auto-seeds demo data if the database is empty

### API Endpoints Summary

| Category | Prefix | Sub-Package | Authentication |
|----------|--------|-------------|----------------|
| Auth | `/api/token`, `/api/register`, `/api/users/me` | Single file | Public/Protected |
| Production | `/api/production/*` | Single file | Protected |
| Quality | `/api/quality/*` | `quality/` (4 modules) | Protected |
| Attendance | `/api/attendance/*` | Single file | Protected |
| KPI | `/api/kpi/*` | `kpi/` (7 modules) | Protected |
| Reports | `/api/reports/*` | `reports/` (5 modules) | Protected |
| Work Orders | `/api/work-orders/*` | Single file | Protected |
| Jobs | `/api/jobs/*` | Single file | Protected |
| Capacity Planning | `/api/capacity/*` | `capacity/` (10 modules) | Protected |
| Simulation V1 | `/api/simulation/*` | `simulation/` (8 modules) | Protected (deprecated) |
| Simulation V2 | `/api/v2/simulation/*` | Single file | Protected |
| Alerts | `/api/alerts/*` | `alerts/` (3 modules) | Protected |
| Analytics | `/api/analytics/*` | `analytics/` (4 modules) | Protected |
| Floating Pool | `/api/floating-pool/*` | Single file | Protected |

---

## Schema-ORM Integrity

The project maintains a strict discipline to prevent schema-ORM drift, which was the root cause of 503 errors on fresh installs during the 2026-02-23 deployment-readiness audit.

### ORM Registry Pattern

All SQLAlchemy ORM models are centrally imported in `backend/orm/__init__.py`. This file serves as the authoritative registry of every database table. `Base.metadata.create_all()` can only create tables for models that have been imported into the Python process, so a missing import means a missing table.

**Rule**: Every new ORM model file added to `backend/orm/` MUST be imported in `backend/orm/__init__.py` and exported in `__all__`.

### Lifespan Safety Check

`backend/main.py` includes a runtime check during application startup:

```python
_actual_table_count = len(Base.metadata.tables)
if _actual_table_count < 45:
    _logger.warning(
        "Schema registry may be incomplete: expected >=45 tables, got %d. "
        "Check that all ORM models are imported in backend/orm/__init__.py.",
        _actual_table_count,
    )
```

As of the deployment-readiness audit, the database has 51 tables. The threshold of 45 provides margin for the check to remain useful without false positives.

### Dual Seeder Architecture

Two seeders must stay aligned:

| Seeder | Location | Used By |
|--------|----------|---------|
| `init_demo_database.py` | `backend/scripts/` | Local development (`python scripts/init_demo_database.py`) |
| `demo_seeder.py` | `backend/db/migrations/` | Docker / auto-seed on empty DB (called from `main.py` lifespan) |

Both seeders import ALL ORM models and create the same comprehensive demo dataset (5 clients, employees, work orders, production data, quality entries, capacity planning data, hold catalogs, break times, production lines, equipment, and assignments).

---

## Frontend Architecture

### Directory Structure

```
frontend/src/
  assets/
    main.css             # Carbon Design integration
    responsive.css       # Mobile-first breakpoints
    carbon-tokens.css    # Design tokens
  components/
    grids/               # AG-Grid wrappers
    entries/              # Data entry forms
    widgets/              # Dashboard widgets
    filters/              # Filter components
    dashboard/            # Dashboard customization
  composables/           # Reusable logic (extracted from large views)
    useKPIDashboardData.js
    useKPIReports.js
    useKPIFilters.js
    useKPIChartData.js
    useShiftDashboardData.js
    useShiftForms.js
    useKeyboardShortcuts.js
    useResponsive.js
    useMobileGrid.js
  services/
    api.js               # Backward-compat stub
    api/                  # API sub-modules (18 modules, 57+ exports)
  stores/                # Pinia state management
    authStore.js         # Authentication
    productionDataStore.js  # Production data
    kpi.js               # KPI metrics
    dashboardStore.js    # Dashboard customization
    capacityPlanningStore.js  # Main capacity store (delegates to sub-stores)
    capacity/            # Sub-stores: defaults, historyManager, useWorksheetOps, useWorkbookStore, useAnalysisStore
  views/
    admin/               # Admin pages
    kpi/                 # KPI detail views
    CapacityPlanning/    # 13-tab capacity planning view
  router/
    index.js             # Route definitions
  App.vue                # Root component
```

### Key Features

#### 1. Accessibility (WCAG 2.1 AA)

- Skip-to-main-content links
- ARIA attributes on all interactive elements
- Keyboard navigation with shortcuts (Ctrl+/ for help)
- High contrast mode support
- Reduced motion support

#### 2. Responsive Design

- Mobile-first with 3 breakpoints (768px, 1024px)
- 44px minimum touch targets
- AG-Grid mobile optimizations
- Print styles

#### 3. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+/` | Show shortcuts help |
| `Ctrl+D` | Go to Dashboard |
| `Ctrl+E` | Go to Data Entry |
| `Ctrl+K` | Go to KPI Overview |
| `Ctrl+S` | Save current form |

---

## Data Model

### Core Entities (51 tables)

```
+-----------+     +-----------+     +-----------+
|   CLIENT  |----<| WORK_ORDER|----<|    JOB    |
+-----------+     +-----------+     +-----------+
                        |                 |
                        |                 |
                  +-----+-----+     +-----+-----+
                  |           |     |           |
            +-----+----+ +---+-----+ +---+ +----+----+
            |PRODUCTION| | QUALITY | |HOLD| |DOWNTIME |
            +----------+ +---------+ +----+ +---------+
```

### Work Order Lifecycle

```
ACTIVE -> ON_HOLD -> ACTIVE -> COMPLETED
   |          ^          |
   +----------+          +--> REJECTED
                         +--> CANCELLED
```

### Key Relationships

| Entity | Relationships |
|--------|---------------|
| Client | Has many: Work Orders, Employees, Products, Configuration |
| Work Order | Has many: Jobs; belongs to Client; optional link to Capacity Order |
| Job | Has many: Production, Quality, Holds, Downtime |
| Production | Belongs to: Job, Employee, Shift |
| Quality | Belongs to: Job, Product |

### Capacity Planning Tables (13)

| Table | Purpose |
|-------|---------|
| CapacityCalendar | Working days, shifts, holidays |
| CapacityProductionLine | Line specifications and operator counts |
| CapacityOrder | Planning orders with priority and status |
| CapacityProductionStandard | SAM (Standard Allowed Minutes) per style |
| CapacityBOMHeader / BOMDetail | Bill of Materials |
| CapacityStockSnapshot | Current inventory positions |
| CapacityComponentCheck | MRP explosion results |
| CapacityAnalysis | 12-step utilization calculation |
| CapacitySchedule / ScheduleDetail | Production schedule generation |
| CapacityScenario | What-if analysis (8 types) |
| CapacityKPICommitment | Plan vs. actual variance tracking |

---

## Security Architecture

### Authentication Flow

1. User submits credentials
2. Server validates, generates JWT (HS256)
3. JWT contains: user_id, client_id, role, exp
4. Client stores JWT in localStorage
5. All API requests include Authorization header
6. Server validates JWT + client_id on each request
7. Token blacklist checked on every authenticated request (logout invalidation)

### Security Measures

| Measure | Implementation |
|---------|----------------|
| Password Hashing | bcrypt with salt |
| Token Security | JWT with configurable expiration, blacklist enforcement |
| Rate Limiting | 10 req/min on auth endpoints |
| Input Validation | Pydantic with field constraints |
| SQL Injection | Parameterized queries via SQLAlchemy |
| Multi-Tenant | Client filter on all queries |
| Production Config | DEFAULT_INSECURE_VALUES guard hard-fails in production |
| CORS | Validated origins, CORSMiddleware added last (outermost in LIFO) |

---

## Capacity Planning Architecture

Capacity Planning follows a **13-worksheet workbook pattern** that mirrors a physical planning workbook. Each worksheet maps to a backend CRUD module and a frontend grid/panel component.

### Backend Services (7)

All services live in `backend/services/capacity/` with a facade orchestrator:

```
CapacityPlanningService          (capacity_service.py)   - Orchestrator / unified API
  BOMService                     (bom_service.py)        - Single-level BOM explosion
  MRPService                     (mrp_service.py)        - Component availability / shortage detection
  CapacityAnalysisService        (analysis_service.py)   - 12-step capacity calculation
  SchedulingService              (scheduling_service.py) - Schedule generation & commitment
  ScenarioService                (scenario_service.py)   - What-if scenario engine
  KPIIntegrationService          (kpi_integration_service.py) - Commitment vs. actuals variance
```

### Scenario Types (8)

| Type | Effect |
|------|--------|
| `OVERTIME` | +20% available hours |
| `SETUP_REDUCTION` | -30% setup time |
| `SUBCONTRACT` | Outsource 40% of cutting |
| `NEW_LINE` | Add a sewing line |
| `THREE_SHIFT` | Switch to 3-shift operation |
| `LEAD_TIME_DELAY` | Simulate material delay |
| `ABSENTEEISM_SPIKE` | +15% absenteeism |
| `MULTI_CONSTRAINT` | Combined multi-factor scenario |

### API Surface

Capacity planning endpoints are organized at `backend/routes/capacity/` with 10 modules: `__init__.py`, `analysis.py`, `bom_stock.py`, `calendar.py`, `kpi_workbook.py`, `lines.py`, `orders.py`, `scenarios.py`, `standards.py`, `work_order_bridge.py`. Every endpoint enforces multi-tenant isolation via `client_id`.

---

## Event Bus

The domain event infrastructure lives in `backend/events/` and provides loose coupling between modules.

### Collect/Flush Pattern

```
Transaction Start
    bus.collect(event)      <- events buffered, not dispatched
    bus.collect(event)
    db.commit()
    bus.flush_collected()   <- all events dispatched after commit

    On rollback:
    bus.discard_collected() <- events thrown away
```

Events are collected during a transaction and only dispatched after a successful commit. On rollback, `discard_collected()` discards the buffer.

### Key Components

| Component | Location | Role |
|-----------|----------|------|
| `DomainEvent` | `events/base.py` | Immutable Pydantic base class (frozen model) |
| `EventHandler` | `events/base.py` | Abstract handler with `can_handle()` filter and `priority` |
| `EventBus` | `events/bus.py` | Singleton bus with subscribe, publish, collect/flush |
| Domain events | `events/domain_events.py` | Concrete events (e.g., `ComponentShortageDetected`, `KPIVarianceAlert`) |

### Features

- **Priority-based dispatch**: handlers sorted by priority (lower = first).
- **Async handlers**: flagged `is_async=True`, scheduled via `asyncio.create_task` to run after HTTP response.
- **Wildcard subscription**: subscribing to `"*"` receives all event types.
- **Error isolation**: handler failures are logged but do not block other handlers.
- **Optional persistence**: `set_persistence_handler()` enables writing events to an event store.

---

## Simulation System

Two simulation implementations coexist in the codebase.

### V1 (Deprecated) - `calculations/simulation.py`

- **Route**: `/api/simulation/*` (sub-package at `routes/simulation/`, 8 modules)
- Pure-function calculator for capacity requirements, staffing, efficiency, shift coverage, and floating pool optimization.
- Tightly coupled to the **floating pool** module: `routes/floating_pool.py` imports `optimize_floating_pool_allocation` and `simulate_shift_coverage` from V1.
- **Cannot be removed** until the floating pool dependency is decoupled.
- **Sunset date**: 2026-06-01 (deprecation headers added via middleware).

### V2 (Current) - `simulation_v2/`

- **Route surfaces**: three sibling modules under `/api/v2/simulation/*`:
  - `routes/simulation_v2.py` — core engine + Monte Carlo + 4 MiniZinc patterns (stateless, no DB)
  - `routes/simulation_scenarios.py` — D3 scenario persistence (CRUD + run + duplicate, backed by `SIMULATION_SCENARIO`)
  - `routes/simulation_calibration.py` — D4 historical calibration (read-only, aggregates production / quality / downtime / shift history into a SimulationConfig dict)
- **SimPy-based** discrete-event simulation engine.
- Capabilities beyond V1:
  - Multi-product support (up to 5 products)
  - Configurable variability (triangular / deterministic distributions)
  - 8 output blocks with analytics
  - Rebalancing suggestions and bottleneck detection
  - **Monte Carlo** wrapper — mean ± 95% CI per metric across N replications
  - **MiniZinc pairing** (`simulation_v2/optimization/`) — 4 patterns: operator allocation, bottleneck rebalancing, product sequencing, planning horizon
  - **Persistent scenarios** — save / load / duplicate / run, tenant-scoped via `client_id` (NULL = global template, admin/poweruser only)
  - **Historical calibration** — pre-fill from production data with per-field provenance (source table, sample size, confidence bucket: high ≥14 / medium 5-13 / low 1-4 / none 0)

### V1 vs V2 Comparison

| Aspect | V1 | V2 |
|--------|----|----|
| Engine | Pure math functions | SimPy discrete-event |
| Products | Single | Up to 5 |
| Persistence | None | Optional (`SIMULATION_SCENARIO` for saved configs); core engine still ephemeral |
| Floating pool | Yes (dependency) | No |
| Optimization | None | MiniZinc — 4 patterns (operator/rebalance/sequence/plan) |
| Calibration | None | From production / quality / downtime / shift history |
| Status | Deprecated (sunset 2026-06-01) | Active |

---

## Known Technical Debt

### High Priority

| Issue | Location | Impact |
|-------|----------|--------|
| V1 simulation floating pool coupling | `routes/floating_pool.py` imports from V1 | Blocks V1 sunset |
| Inconsistent naming convention | `models/` = Pydantic, `orm/` = SQLAlchemy | Developer confusion |

### Medium Priority

| Issue | Location | Impact |
|-------|----------|--------|
| Business logic in some routes | Various single-file routes | Testability |
| 216 hardcoded i18n strings | Frontend components | Localization |

### Documented for Future

| Issue | Status |
|-------|--------|
| TypeScript migration | Planned |
| Token storage (HttpOnly cookies) | Planned |
| Redis for session data | Planned for production |
| PostgreSQL migration | Planned (SQLAlchemy makes this a config change) |

---

## Deployment

See `docs/DEPLOYMENT.md` for full deployment instructions.

### Development

```bash
# Backend
cd backend
pip install -r requirements.txt
python scripts/init_demo_database.py
uvicorn backend.main:app --reload

# Frontend
cd frontend
npm install --legacy-peer-deps
npm run dev
```

### Production Considerations

- Use MariaDB/MySQL instead of SQLite
- Configure production SECRET_KEY (config.py hard-fails on insecure defaults)
- Enable HTTPS
- Configure CORS origins
- Enable rate limiting
- Set `CSP_CONNECT_EXTRA` env var in frontend Dockerfile for production API URLs

---

## Appendix: Naming Conventions

**Note:** This project uses a non-standard naming convention:

| Directory | Contains | Common Convention |
|-----------|----------|-------------------|
| `/models/` | Pydantic schemas | Usually SQLAlchemy |
| `/orm/` | SQLAlchemy models | Usually `models/` |

This is documented and internally consistent.

---

*Updated from deployment-readiness audit reports dated 2026-02-23*
