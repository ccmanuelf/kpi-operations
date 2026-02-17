# KPI Operations Platform - Architecture Documentation

**Version**: 1.0.0
**Last Updated**: 2026-02-16
**Architecture Grade**: B+ (Backend) / B+ (Frontend)

---

## Executive Summary

KPI Operations is a manufacturing KPI tracking platform designed for shopfloor operators and technicians. It serves as a bridge tool for operations without a full MES system, replacing Excel spreadsheets and whiteboards with a structured, data-driven approach.

### Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Frontend** | Vue 3 + Vuetify 3 + Pinia | 3.4 / 3.5 / 2.1 |
| **Backend** | FastAPI + SQLAlchemy | 0.100+ / 2.0+ |
| **Database** | SQLite (dev) / MariaDB (prod) | - |
| **Authentication** | JWT + bcrypt | - |
| **Data Grid** | AG-Grid Community | - |
| **Design System** | IBM Carbon (tokens) | - |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  Vue 3 + Vuetify + Pinia                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │  Views   │ │Components│ │  Stores  │ │Composables│          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
│       └────────────┴────────────┴────────────┘                  │
│                         │                                        │
│                    API Service                                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP/REST
┌─────────────────────────┴───────────────────────────────────────┐
│                         BACKEND                                  │
│  FastAPI                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Routes/Endpoints                      │    │
│  │  auth │ users │ production │ quality │ attendance │ ...  │    │
│  └───────────────────────┬─────────────────────────────────┘    │
│                          │                                       │
│  ┌───────────────────────┼─────────────────────────────────┐    │
│  │   Middleware          │         Calculations            │    │
│  │   • Auth              │         • efficiency.py         │    │
│  │   • Rate Limit        │         • otd.py               │    │
│  │   • Client Filter     │         • ppm.py               │    │
│  └───────────────────────┼─────────────────────────────────┘    │
│                          │                                       │
│  ┌───────────────────────┴─────────────────────────────────┐    │
│  │                     CRUD Layer                           │    │
│  │  17 modules: production, quality, attendance, etc.       │    │
│  └───────────────────────┬─────────────────────────────────┘    │
│                          │                                       │
│  ┌───────────────────────┴─────────────────────────────────┐    │
│  │                   ORM Models (SQLAlchemy)                │    │
│  │  WorkOrder │ Job │ Production │ Quality │ Attendance     │    │
│  └───────────────────────┬─────────────────────────────────┘    │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                        DATABASE                                  │
│  SQLite (dev) / MariaDB (prod)                                  │
│  Multi-tenant with client_id isolation                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Backend Architecture

### Directory Structure

```
backend/
├── main.py              # App setup, route registration (needs refactoring)
├── config.py            # Configuration with validation
├── database.py          # Connection pooling, session management
├── auth/
│   ├── jwt.py           # JWT token utilities
│   └── password_policy.py
├── calculations/        # Business logic (12 modules)
│   ├── efficiency.py    # Efficiency with inference engine
│   ├── otd.py           # On-Time Delivery calculations
│   ├── ppm.py           # Parts Per Million (quality)
│   ├── performance.py   # Performance metrics
│   ├── availability.py  # Machine availability
│   └── ...
├── crud/                # Data access layer (17 modules)
│   ├── production.py
│   ├── quality.py
│   ├── attendance.py
│   └── ...
├── middleware/
│   ├── client_auth.py   # Multi-tenant isolation
│   └── rate_limit.py
├── models/              # Pydantic request/response models
├── routes/              # API endpoint modules
├── schemas/             # SQLAlchemy ORM models
├── reports/             # PDF/Excel generation
└── services/            # External integrations
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

### API Endpoints Summary

| Category | Endpoints | Authentication |
|----------|-----------|----------------|
| Auth | `/api/token`, `/api/register`, `/api/users/me` | Public/Protected |
| Production | `/api/production/*` | Protected |
| Quality | `/api/quality/*` | Protected |
| Attendance | `/api/attendance/*` | Protected |
| KPI | `/api/kpi/*` | Protected |
| Reports | `/api/reports/*` | Protected |
| Work Orders | `/api/work-orders/*` | Protected |
| Jobs | `/api/jobs/*` | Protected |
| Capacity Planning | `/api/capacity/*` | Protected |
| Simulation V1 | `/api/simulation/*` | Protected (deprecated) |
| Simulation V2 | `/api/v2/simulation/*` | Protected |
| Floating Pool | `/api/floating-pool/*` | Protected |

---

## Frontend Architecture

### Directory Structure

```
frontend/src/
├── assets/
│   ├── main.css           # Carbon Design integration
│   ├── responsive.css     # Mobile-first breakpoints
│   └── carbon-tokens.css  # Design tokens
├── components/
│   ├── grids/             # AG-Grid wrappers
│   ├── entries/           # Data entry forms
│   ├── widgets/           # Dashboard widgets
│   ├── filters/           # Filter components
│   └── dashboard/         # Dashboard customization
├── composables/           # Reusable logic
│   ├── useKeyboardShortcuts.js
│   ├── useResponsive.js
│   └── useMobileGrid.js
├── services/
│   └── api.js             # API client
├── stores/                # Pinia state management
│   ├── authStore.js       # Authentication
│   ├── kpiStore.js        # Production data
│   ├── kpi.js             # KPI metrics
│   └── dashboardStore.js  # Dashboard customization
├── views/
│   ├── admin/             # Admin pages
│   ├── kpi/               # KPI detail views
│   └── [entry views]
├── router/
│   └── index.js           # Route definitions
└── App.vue                # Root component
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

#### 3. State Management Pattern

```javascript
// Stores use localStorage + API sync for offline resilience
const dashboardStore = defineStore('dashboard', () => {
  const layout = ref(loadFromLocalStorage() || defaultLayout)

  const saveLayout = async () => {
    saveToLocalStorage(layout.value)
    await api.saveDashboardLayout(layout.value)  // Sync to server
  }
})
```

#### 4. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+/` | Show shortcuts help |
| `Ctrl+D` | Go to Dashboard |
| `Ctrl+E` | Go to Data Entry |
| `Ctrl+K` | Go to KPI Overview |
| `Ctrl+S` | Save current form |

---

## Data Model

### Core Entities

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLIENT    │────<│ WORK_ORDER  │────<│     JOB     │
└─────────────┘     └─────────────┘     └─────────────┘
                          │                    │
                          │                    │
                    ┌─────┴─────┐        ┌─────┴─────┐
                    │           │        │           │
              ┌─────┴────┐ ┌────┴────┐ ┌─┴───┐ ┌────┴────┐
              │PRODUCTION│ │ QUALITY │ │HOLD │ │DOWNTIME │
              └──────────┘ └─────────┘ └─────┘ └─────────┘
```

### Work Order Lifecycle

```
ACTIVE → ON_HOLD → ACTIVE → COMPLETED
   │         ↑         │
   └─────────┘         └──→ REJECTED
                       └──→ CANCELLED
```

### Key Relationships

| Entity | Relationships |
|--------|---------------|
| Client | Has many: Work Orders, Employees, Products |
| Work Order | Has many: Jobs, belongs to Client |
| Job | Has many: Production, Quality, Holds, Downtime |
| Production | Belongs to: Job, Employee, Shift |
| Quality | Belongs to: Job, Product |

---

## Security Architecture

### Authentication Flow

```
1. User submits credentials
2. Server validates, generates JWT
3. JWT contains: user_id, client_id, role, exp
4. Client stores JWT in localStorage
5. All API requests include Authorization header
6. Server validates JWT + client_id on each request
```

### Security Measures

| Measure | Implementation |
|---------|----------------|
| Password Hashing | bcrypt with salt |
| Token Security | JWT with configurable expiration |
| Rate Limiting | 10 req/min on auth endpoints |
| Input Validation | Pydantic with field constraints |
| SQL Injection | Parameterized queries via SQLAlchemy |
| Multi-Tenant | Client filter on all queries |

---

## Capacity Planning Architecture

Capacity Planning follows a **13-worksheet workbook pattern** that mirrors a physical planning workbook. Each worksheet maps to a backend CRUD module and a frontend grid/panel component.

### Worksheets

| # | Worksheet | Purpose |
|---|-----------|---------|
| 1 | Master Calendar | Working days, shifts, holidays |
| 2 | Production Lines | Line specifications and operator counts |
| 3 | Orders | Planning orders with priority and status |
| 4 | Production Standards | SAM (Standard Allowed Minutes) per style |
| 5 | BOM | Bill of Materials headers and details |
| 6 | Stock Snapshots | Current inventory positions |
| 7 | Component Check | MRP explosion results |
| 8 | Capacity Analysis | 12-step utilization calculation |
| 9 | Schedules | Production schedule generation |
| 10 | Scenarios | What-if analysis (8 types) |
| 11 | KPI Commitments | Plan vs. actual variance tracking |
| 12 | Dashboard Inputs | Aggregated planning inputs |
| 13 | Instructions | User guide / reference |

### Backend Services (7)

All services live in `backend/services/capacity/` with a facade orchestrator:

```
CapacityPlanningService          (capacity_service.py)   - Orchestrator / unified API
├── BOMService                   (bom_service.py)        - Single-level BOM explosion
├── MRPService                   (mrp_service.py)        - Component availability / shortage detection
├── CapacityAnalysisService      (analysis_service.py)   - 12-step capacity calculation
├── SchedulingService            (scheduling_service.py) - Schedule generation & commitment
├── ScenarioService              (scenario_service.py)   - What-if scenario engine
└── KPIIntegrationService        (kpi_integration_service.py) - Commitment vs. actuals variance
```

`CapacityPlanningService` coordinates the others; individual services can also be used directly by routes.

### Scenario Types (8)

Defined via `ScenarioType` enum in `scenario_service.py`:

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

Each type has default parameters. Scenarios are persisted and can be compared side-by-side, emitting `CapacityScenarioCreated` and `CapacityScenarioCompared` domain events.

### API Surface

All endpoints are under `/api/capacity/*` in `backend/routes/capacity.py` (~1,900 lines). Every endpoint enforces multi-tenant isolation via `client_id`.

---

## Event Bus

The domain event infrastructure lives in `backend/events/` and provides loose coupling between modules.

### Collect/Flush Pattern

```
Transaction Start
  │  bus.collect(event)     ← events buffered, not dispatched
  │  bus.collect(event)
  │  db.commit()
  │  bus.flush_collected()  ← all events dispatched after commit
  │
  │  On rollback:
  │  bus.discard_collected() ← events thrown away
```

Events are collected during a transaction and only dispatched after a successful commit. On rollback, `discard_collected()` discards the buffer. This prevents side effects from failed transactions.

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

- **Route**: `/api/simulation/*` (in `routes/simulation.py`)
- Pure-function calculator for capacity requirements, staffing, efficiency, shift coverage, and floating pool optimization.
- Tightly coupled to the **floating pool** module: `routes/floating_pool.py` imports `optimize_floating_pool_allocation` and `simulate_shift_coverage` from V1.
- **Cannot be removed** until the floating pool dependency is decoupled.

### V2 (Current) - `simulation_v2/`

- **Route**: `/api/v2/simulation/*` (in `routes/simulation_v2.py`)
- **SimPy-based** discrete-event simulation engine.
- Stateless / ephemeral: no database persistence, operates as a pure calculator.
- Capabilities beyond V1:
  - Multi-product support (up to 5 products)
  - Configurable variability (triangular / deterministic distributions)
  - 8 output blocks with analytics
  - Rebalancing suggestions and bottleneck detection

### V1 vs V2 Comparison

| Aspect | V1 | V2 |
|--------|----|----|
| Engine | Pure math functions | SimPy discrete-event |
| Products | Single | Up to 5 |
| Persistence | None | None (ephemeral) |
| Floating pool | Yes (dependency) | No |
| Status | Deprecated | Active |

### Floating Pool Dependency

`routes/floating_pool.py` imports three functions from `calculations/simulation.py` (V1):

- `optimize_floating_pool_allocation`
- `simulate_shift_coverage`
- `run_staffing_simulation`

This is the sole reason V1 cannot be archived. Decoupling requires extracting these functions into a dedicated module.

---

## Known Technical Debt

### High Priority

| Issue | Location | Impact |
|-------|----------|--------|
| Monolithic main.py | `backend/main.py` (3,647 lines) | Maintainability |
| Duplicate KPI stores | `frontend/stores/kpi*.js` | Confusion |
| Inconsistent error handling | Frontend components | UX |

### Medium Priority

| Issue | Location | Impact |
|-------|----------|--------|
| Business logic in routes | Various route files | Testability |
| Missing service layer | Backend | Architecture |
| Large API service file | `frontend/services/api.js` | Maintainability |

### Documented for Future

| Issue | Status |
|-------|--------|
| TypeScript migration | In progress |
| Token storage (HttpOnly cookies) | Planned |
| Redis for session data | Planned for production |

---

## Deployment

### Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Production Considerations

- Use MariaDB/MySQL instead of SQLite
- Configure production SECRET_KEY
- Enable HTTPS
- Set up Redis for token blacklist
- Configure CORS origins
- Enable rate limiting

---

## Appendix: Naming Conventions

**Note:** This project uses a non-standard naming convention:

| Directory | Contains | Common Convention |
|-----------|----------|-------------------|
| `/models/` | Pydantic schemas | Usually SQLAlchemy |
| `/schemas/` | SQLAlchemy models | Usually Pydantic |

This is documented and internally consistent.

---

*Generated from architecture audit reports dated 2026-01-25*
