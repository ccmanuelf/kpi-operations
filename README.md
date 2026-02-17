# KPI Operations Dashboard Platform

**Enterprise Manufacturing KPI Tracking and Analytics**

[![Status](https://img.shields.io/badge/status-Production--Ready-brightgreen)](https://github.com)
[![Version](https://img.shields.io/badge/version-1.0.4-blue)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-5771%20passing-success)](https://github.com)
[![Audit](https://img.shields.io/badge/audit-Run%205%3A%20287%20findings%2C%20remediation%20in%20progress-orange)](CHANGELOG.md)
[![Coverage](https://img.shields.io/badge/coverage-76%25-brightgreen)](https://github.com)
[![Design](https://img.shields.io/badge/design-Vuetify%20Material-blue)](https://vuetifyjs.com)
[![License](https://img.shields.io/badge/license-Proprietary-red)](https://github.com)

> Comprehensive multi-tenant KPI dashboard for manufacturing operations tracking production efficiency, quality, downtime, and labor metrics across 50+ clients with 3000+ employees.

---

## Overview

The KPI Operations Dashboard Platform is an enterprise-grade web application designed to consolidate scattered manufacturing data into a unified, real-time analytics system. It replaces manual whiteboard tracking with data-driven decision making across 10 critical KPIs.

### **Business Impact**
- **Eliminate Guesstimated KPIs** - Real-time calculations from actual production data
- **Multi-Tenant Isolation** - 50+ clients with complete data separation
- **Mobile-Ready** - Tablet-friendly data entry for shop floor use
- **Scalable** - Handles 3000+ employees, 100+ daily entries per client
- **Audit Trail** - Complete tracking of who entered what, when

---

## Key Features

### **10 Real-Time KPIs**
1. **WIP Aging** - Work-in-progress age tracking with hold management
2. **On-Time Delivery (OTD)** - TRUE-OTD and standard OTD metrics
3. **Production Efficiency** - Hours produced vs. hours available
4. **Quality PPM** - Parts per million defect rate
5. **Quality DPMO** - Defects per million opportunities
6. **First Pass Yield (FPY)** - Pass rate without rework
7. **Rolled Throughput Yield (RTY)** - Final quality after rework
8. **Availability** - Uptime vs. downtime analysis
9. **Performance** - Actual vs. ideal cycle time
10. **Absenteeism** - Labor attendance tracking with Bradford Factor

### **Enterprise Features**
- **Multi-Tenant Architecture** - Complete client data isolation
- **Role-Based Access Control** - Operator, Leader, PowerUser, Admin roles
- **Excel-like Data Grids** - AG Grid Community Edition with copy/paste
- **CSV Bulk Upload** - Import 100+ records with validation
- **Inference Engine** - Smart defaults for missing data
- **Real-Time Calculations** - KPIs update as data is entered
- **Predictive Analytics** - Forecasting for all 10 KPIs with exponential smoothing (toggle "Show Forecast" on KPI detail charts)
- **Custom Dashboards** - Role-based layouts with drag-drop widget customization
- **Advanced Filtering** - Save, apply, and manage filter configurations (Saved Filters dropdown in dashboard header)
- **QR Code Integration** - Scan QR codes for work order lookup and form auto-fill
- **Responsive Design** - Works on desktop, tablet, mobile
- **Keyboard Shortcuts** - Power-user productivity features
- **Demo Data** - Sample data generator with 5 clients, 100 employees
- **Production Line Simulation** - SimPy-based simulation with station modeling, bottleneck detection, and throughput analysis
- **Capacity Planning** - 13-worksheet workbook with orders, calendars, production lines, standards, BOM, stock, scheduling, and analysis
- **Scenario Comparison** - 11 what-if scenario types (overtime, subcontract, new line, shift changes, efficiency improvements, and more)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Vue.js 3)                       │
│  Vuetify 3 + AG Grid Community + Chart.js + Pinia Store     │
└────────────────────┬────────────────────────────────────────┘
                     │ REST API (393 endpoints)
┌────────────────────▼────────────────────────────────────────┐
│                 Backend (Python FastAPI)                     │
│  SQLAlchemy ORM + JWT Auth + KPI Calculations + Validation  │
└────────────────────┬────────────────────────────────────────┘
                     │ SQL
┌────────────────────▼────────────────────────────────────────┐
│              Database (SQLite / MariaDB)                     │
│     35 Normalized Tables + Indexes + Foreign Keys           │
└─────────────────────────────────────────────────────────────┘
```

### **Tech Stack**
- **Frontend:** Vue.js 3.4, Vuetify 3.5 (Carbon-inspired theming), AG Grid 35.0, Chart.js 4.4
- **Backend:** Python 3.11+, FastAPI 0.129, SQLAlchemy 2.0, Pydantic 2.12
- **Database:** SQLite (dev) → MariaDB 10.11+ (production)
- **Auth:** JWT tokens with role-based permissions
- **Testing:** Pytest + Vitest + Playwright (E2E)
- **Deployment:** Docker containers (Dockerfile + docker-compose.yml included), Uvicorn ASGI server

---

## Quick Start

### **Prerequisites**
- Python 3.11+
- Node.js 20+
- SQLite 3 (included with Python)
- Git

### **Installation**

```bash
# Clone repository
git clone <repository-url>
cd kpi-operations

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Initialize database and seed demo data
cd ../database
python init_sqlite_schema.py
python generators/generate_demo_data.py
python create_demo_users.py
cd ../backend

# Start backend server (PYTHONPATH required for module imports)
PYTHONPATH=.. uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Frontend setup (new terminal)
cd ../frontend
npm install --legacy-peer-deps
npm run dev  # Starts on http://localhost:3000
```

### **Default Login Credentials**

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin |
| supervisor1 | password123 | Supervisor |
| operator1 | password123 | Operator |
| operator2 | password123 | Operator |

For detailed setup including MariaDB production configuration, see [QUICKSTART.md](QUICKSTART.md).

---

## Project Structure

```
kpi-operations/
├── backend/                    # Python FastAPI backend
│   ├── calculations/           # KPI calculation engines (16 modules)
│   │   ├── efficiency.py       # KPI #3 - Efficiency
│   │   ├── performance.py      # KPI #9 - Performance
│   │   ├── availability.py     # KPI #8 - Availability
│   │   ├── wip_aging.py        # KPI #1 - WIP Aging
│   │   ├── otd.py              # KPI #2 - On-Time Delivery
│   │   ├── absenteeism.py      # KPI #10 - Absenteeism
│   │   ├── ppm.py              # KPI #4 - PPM
│   │   ├── dpmo.py             # KPI #5 - DPMO
│   │   ├── fpy_rty.py          # KPI #6, #7 - FPY, RTY
│   │   ├── predictions.py      # Forecasting engine
│   │   └── simulation.py       # SimPy simulation
│   ├── crud/                   # CRUD operations (13 modules)
│   ├── events/                 # Domain event bus
│   ├── routes/                 # API endpoint definitions (35 modules)
│   ├── schemas/                # SQLAlchemy ORM models (41 files)
│   │   └── capacity/           # Capacity planning models (11 files)
│   ├── services/               # Business logic services
│   │   └── capacity/           # Capacity planning services (7 modules)
│   ├── tests/                  # Pytest unit & integration tests
│   └── main.py                 # FastAPI application entry
│
├── frontend/                   # Vue.js 3 frontend (143 components)
│   ├── src/
│   │   ├── components/
│   │   │   ├── entries/        # Data entry forms
│   │   │   ├── grids/          # AG Grid implementations (6 grids)
│   │   │   │   ├── ProductionEntryGrid.vue
│   │   │   │   ├── AttendanceEntryGrid.vue
│   │   │   │   ├── QualityEntryGrid.vue
│   │   │   │   ├── DowntimeEntryGrid.vue
│   │   │   │   ├── HoldEntryGrid.vue
│   │   │   │   └── AGGridBase.vue
│   │   │   ├── simulation/     # Simulation components
│   │   │   └── admin/          # Admin components
│   │   ├── views/              # Page components
│   │   │   ├── kpi/            # 8 KPI detail views
│   │   │   ├── admin/          # Admin views
│   │   │   ├── CapacityPlanning/  # 13-tab capacity planning
│   │   │   ├── DashboardView.vue
│   │   │   ├── KPIDashboard.vue
│   │   │   └── LoginView.vue
│   │   ├── stores/             # Pinia state management (17 stores)
│   │   └── services/api/       # API service modules
│   ├── e2e/                    # Playwright E2E tests
│   └── package.json
│
├── database/                   # Database initialization & generators
│   ├── generators/             # Demo data generators (11 scripts)
│   ├── create_demo_users.py    # Demo user creation
│   └── init_sqlite_schema.py   # SQLite schema initialization
│
├── docs/                       # Documentation
│   ├── API_DOCUMENTATION.md
│   ├── DEPLOYMENT.md
│   ├── USER_GUIDE.md
│   ├── ARCHITECTURE.md
│   └── ...
│
├── Dockerfile                  # Multi-stage Docker build
├── docker-compose.yml          # Docker Compose configuration
├── QUICKSTART.md               # Quick start guide (SQLite + MariaDB)
├── CHANGELOG.md                # Version history
└── README.md                   # This file
```

---

## Implementation Status

### **Current Version: 1.0.4** (February 13, 2026)

| Phase | Module | Status |
|-------|--------|--------|
| **Phase 0** | Core Infrastructure | Complete |
| **Phase 1** | Production Entry | Complete |
| **Phase 2** | Downtime & WIP | Complete |
| **Phase 3** | Attendance & Labor | Complete |
| **Phase 4** | Quality Controls | Complete |
| **UI/UX** | All Grids & Forms | Complete |
| **Security** | Multi-Tenant + Auth | Complete |
| **Capacity** | 13-Worksheet Workbook | Complete |
| **Testing** | 5,771 tests, 0 failures | Complete |

---

## User Interface

### **Data Entry Grids (Excel-Like)**
- Single-click editing with inline cell editors
- Copy/paste support (Ctrl+C, Ctrl+V)
- Fill handle to drag values down
- Column sorting & filtering
- Row selection & bulk operations
- Keyboard navigation (Tab, Enter, arrows)
- Undo/Redo (Ctrl+Z, 20 operations)
- Real-time validation with colored cells

### **KPI Dashboard**
- Summary cards with trend indicators
- Interactive charts (Chart.js) with optional forecast visualization
- Filterable by date range, client, shift
- **Saved Filters** - Quick dropdown to save, load, and manage filter presets
- **QR Scanner** - Quick-access button for work order lookup
- **Bradford Factor Widget** - Absenteeism pattern analysis (enabled by default for Leader+ roles)
- Drill-down to detailed data
- Export to Excel/PDF
- **Email Reports** - Configure automated report delivery (daily/weekly/monthly)

### **Keyboard Shortcuts**
- `Ctrl+S` - Save current changes
- `Ctrl+Z` - Undo last change
- `Ctrl+Y` - Redo
- `Delete` - Clear selected cells
- `Ctrl+C/V` - Copy/Paste
- `Ctrl+/` - Show keyboard shortcuts help

---

## Simulation & Capacity Planning

The platform includes simulation and capacity planning tools for production optimization.

### **Capacity Planning (13-Worksheet Workbook)**
Full-featured capacity planning with 13 interconnected worksheets:
1. **Orders** - Customer orders and demand data
2. **Master Calendar** - Production calendar and shift definitions
3. **Production Lines** - Line capacity and availability
4. **Production Standards** - Cycle times and standard rates
5. **BOM (Bill of Materials)** - Component requirements
6. **Stock Snapshot** - Current inventory levels
7. **Component Check** - Material availability verification
8. **Capacity Analysis** - Bottleneck identification and utilization
9. **Production Schedule** - Generated production plan
10. **What-If Scenarios** - 11 scenario types for optimization
11. **KPI Tracking** - Capacity-related KPI monitoring
12. **Dashboard Inputs** - Configurable analysis parameters
13. **Instructions** - Embedded user guidance

### **Scenario Types**
The capacity planning module supports 8 core what-if scenarios backed by the `ScenarioType` enum in the backend, plus 3 frontend-only composition types:
- **Core (backend):** OVERTIME, SETUP_REDUCTION, SUBCONTRACT, NEW_LINE, THREE_SHIFT, LEAD_TIME_DELAY, ABSENTEEISM_SPIKE, MULTI_CONSTRAINT
- **Composition (frontend):** SHIFT_ADD, EFFICIENCY_IMPROVEMENT, LABOR_ADD

### **Production Line Simulation**
Model production lines using SimPy discrete-event simulation:
- Configure number of stations (2-10)
- Set workers per station
- Add floating pool workers
- Simulate shifts (1-24 hours)
- Identify bottleneck stations
- Analyze throughput and quality yield

---

## API Documentation

### **Base URL**
```
Development: http://localhost:8000/api
Production: https://your-domain.com/api
```

### **Authentication**
```bash
# Login
POST /api/auth/login
{
  "username": "admin",
  "password": "admin123"
}

# Response
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "user_id": "ADMIN",
    "role": "ADMIN"
  }
}

# Use token in headers
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

### **Core Endpoints**

**Production Entry:**
```bash
POST   /api/production/entry          # Create production entry
GET    /api/production/entries        # List entries (filtered by client)
PUT    /api/production/entry/{id}     # Update entry
DELETE /api/production/entry/{id}     # Delete entry
POST   /api/production/upload/csv     # Bulk CSV upload
```

**KPI Calculations:**
```bash
GET /api/kpi/efficiency/{client_id}?days=30     # Efficiency trend
GET /api/kpi/performance/{client_id}?days=30    # Performance trend
GET /api/kpi/all/{client_id}?days=30            # All 10 KPIs
```

**393 total API endpoints** across 35 route modules. Full documentation: [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)

---

## Testing

### **Run Backend Tests**
```bash
cd backend
source venv/bin/activate
# PYTHONPATH=.. is required so Python can resolve 'backend.*' imports
PYTHONPATH=.. pytest tests/                    # All tests
PYTHONPATH=.. pytest tests/test_calculations/  # KPI calculation tests
PYTHONPATH=.. pytest --cov                     # With coverage report
```

### **Run Frontend Tests**
```bash
cd frontend
npm run test                                   # Vitest unit tests (1,434 tests)
npm run lint                                   # ESLint checks
npx playwright test --config=playwright.sqlite.config.ts  # E2E tests (211 scenarios)
```

### **Current Test Coverage**
- **Backend:** 4,277 passed, 76.26% coverage (threshold: 70%)
- **Frontend:** 1,494 passed across 52 test files
- **E2E:** 211 Playwright scenarios (Chromium)
- **Total:** 4,277 backend + 1,494 frontend = 5,771 passing tests, 0 failures

---

## Completed Features

### **All Planned Features Delivered**
1. **Reports** - PDF and Excel export
2. **Email Delivery** - Automated daily/weekly/monthly reports (UI in v1.0.3)
3. **QR Code Integration** - Mobile barcode scanning with quick-access UI
4. **Custom Dashboards** - Role-based dashboard views
5. **Advanced Filtering** - Saved views and filter presets
6. **Predictive Analytics** - Forecast visualization on charts (v1.0.3)
7. **Capacity Planning** - 13-worksheet workbook with 11 scenario types (v1.0.4)

---

## Security

### **Authentication & Authorization**
- JWT tokens with 30-minute expiration (secure default)
- Password hashing with bcrypt
- Role-based access control (RBAC)
- Client data isolation enforced at API level

### **Multi-Tenancy**
- All queries filtered by `client_id`
- User assigned to specific client(s)
- Cross-client data access prevented

### **Input Validation**
- Pydantic models for all API inputs
- SQL injection prevention via parameterized queries
- XSS protection via Vue.js escaping

---

## Contributing

### **Development Workflow**
1. Create feature branch from `main`
2. Implement changes with tests
3. Run `pytest` and `npm run lint`
4. Submit pull request with description
5. Code review by 1+ developers
6. Merge after approval

### **Code Style**
- **Backend:** PEP 8, Black formatter, type hints
- **Frontend:** ESLint, Vue.js 3 Composition API
- **Commits:** Conventional Commits format

---

## Documentation

### **Essential Guides**
- [QUICKSTART.md](QUICKSTART.md) - Get started in 5 minutes (SQLite or MariaDB)
- [CHANGELOG.md](CHANGELOG.md) - Version history and release notes
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [API Documentation](docs/API_DOCUMENTATION.md) - All endpoints with examples
- [User Guide](docs/USER_GUIDE.md) - End-user documentation
- [Architecture](docs/ARCHITECTURE.md) - System design overview

### **Additional Resources**
- [Accessibility Audit](docs/ACCESSIBILITY_AUDIT_REPORT.md) - WCAG 2.1 AA compliance
- [Validation Report](docs/COMPREHENSIVE_VALIDATION_REPORT.md) - Platform audit results
- [AG Grid Usage](docs/AGGRID_USAGE_EXAMPLES.md) - Grid customization examples

---

## Roadmap

### **Version 2.0 (Q3 2026)** - Mobile App
- Native iOS/Android app
- Offline data entry with sync
- Push notifications for alerts
- Voice-to-text data entry

---

## Support

### **For Issues**
- Create GitHub issue with:
  - Steps to reproduce
  - Expected vs. actual behavior
  - Screenshots if applicable
  - Browser/OS version

### **For Feature Requests**
- Create GitHub discussion with:
  - Use case description
  - Business impact
  - Proposed solution (optional)

### **For Questions**
- Check [docs/](docs/) directory first

---

## License

**Proprietary** - All rights reserved.

This software is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.

---

## Acknowledgments

### **Technologies Used**
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [AG Grid](https://www.ag-grid.com/) - Enterprise data grid
- [Vuetify](https://vuetifyjs.com/) - Material Design component framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python ORM
- [Chart.js](https://www.chartjs.org/) - Charting library
- [SimPy](https://simpy.readthedocs.io/) - Discrete-event simulation

### **Development Team**
- Architecture & Backend: [Team credits]
- Frontend & UX: [Team credits]
- QA & Testing: [Team credits]
- Project Management: [Team credits]

---

## Quick Stats

```
Frontend:
- 143 Vue components
- 6 AG Grid implementations (4,100+ lines)
- 8 KPI detail views + OEE composite view
- 13-tab Capacity Planning workbook
- 17 Pinia stores (12 top-level + 5 capacity sub-stores)
- 100% responsive design

Backend:
- 35 database tables (multi-tenant architecture)
- 16 KPI calculation engines + predictive forecasting
- 35 route modules + 13 CRUD modules
- 393 REST API endpoints
- 76.26% test coverage (4,277 tests passing)
- Docker deployment ready (multi-stage Dockerfile + docker-compose.yml)
- SimPy-based production line simulation engine
- Domain event bus with collect/flush pattern
```

---

**Version:** 1.0.4
**Release Date:** February 13, 2026
**Status:** Production Ready

**Test Coverage:** 5,771 tests (4,277 backend + 1,494 frontend) | 76.26% backend coverage | Docker Support: YES | Simulation Engine: SimPy

### **Recent Updates (v1.0.4)**
- **Capacity Planning Module** - 13-worksheet workbook with full CRUD for orders, calendars, production lines, standards, BOM, stock, scheduling, and analysis
- **11 Scenario Types** - OVERTIME, SETUP_REDUCTION, SUBCONTRACT, NEW_LINE, THREE_SHIFT, LEAD_TIME_DELAY, ABSENTEEISM_SPIKE, MULTI_CONSTRAINT, SHIFT_ADD, EFFICIENCY_IMPROVEMENT, LABOR_ADD
- **Dashboard Inputs Tab** - Configurable parameters for capacity analysis
- **Instructions Tab** - Embedded user guidance within Capacity Planning
- **Undo/Redo UI** - Visual undo/redo controls for grid editing
- **CSV Export** - Export capacity planning data to CSV format
- **Event Bus Tests** - 176 new tests for domain event system
- **Router Guard Tests** - 23 new tests for Vue Router navigation guards
- **Mock CRUD Tests Replaced** - Converted 3 mock-based test files to real DB tests
- **Dependency Upgrades** - FastAPI 0.129, Pydantic 2.12, SQLAlchemy 2.0.46, happy-dom 20.6.1 (critical RCE fix)
- **Documentation** - QUICKSTART SQLite path, CHANGELOG v1.0.1-v1.0.4 entries, badge fixes

### **Previous Updates (v1.0.3)**
- **Predictive Analytics UI** - Added "Show Forecast" toggle on Efficiency and Performance KPI charts
- **Forecast Visualization** - Displays 7-30 day predictions with confidence intervals on trend charts
- **QR Scanner Quick-Access** - Added QR Scanner button directly in dashboard header
- **Saved Filters UI** - Added dropdown menu to save, load, and manage filter presets
- **Bradford Factor Widget** - Now included in default dashboard for Leader, PowerUser, and Admin roles
- **Email Reports Dialog** - Full UI for configuring automated report delivery (frequency, recipients, content)
- **Tooltip Enhancements** - Added formula and meaning tooltips to all KPI cards
- **Fixed keyboard shortcuts** - Corrected help shortcut to Ctrl+/, redo to Ctrl+Y

### **Previous Updates (v1.0.2)**
- Fixed WIP Aging view - all data tables now connected and displaying
- Added `/api/kpi/wip-aging/top` endpoint for top aging items
- Added `/api/kpi/wip-aging/trend` endpoint for trend chart data
- Fixed Hold Records History table with correct HOLD_ENTRY schema fields
- Fixed "Oldest Item" card to show actual max age (not hardcoded)
- Fixed Efficiency view with by-shift and by-product breakdown endpoints
- Added OEE KPI view with component breakdown (Availability x Performance x Quality)
- Updated response models to match database schema (WIPHoldResponse)

### **Previous Updates (v1.0.1)**
- Fixed 34 skipped tests (93 → 59 skipped)
- Increased test coverage from 43% to 77.48%
- Fixed SQLite compatibility issues (datediff → date comparison)
- Fixed ProductionEntry schema for multi-tenant isolation
- Added ImportLog SQLAlchemy schema
- Fixed SQL text() wrapper for SQLAlchemy 2.0 compatibility

---

*For full version history, see [CHANGELOG.md](CHANGELOG.md)*
