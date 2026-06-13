# Changelog

All notable changes to the Manufacturing KPI Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-13

Audit Run 7 (Fable5) remediation plus the accumulated maintenance since 1.0.5.
Reports archived under `_audit/` (local-only). Both critical findings fixed;
all four CI required checks green throughout.

### Security
- **Demo auto-seed gated behind `DEMO_MODE`** (C-1) — the startup seeder could run `Base.metadata.drop_all()` against any database missing the demo client IDs, with nothing reading `DEMO_MODE`. Pointing `DATABASE_URL` at a populated production database would erase it on boot. The seeder (`backend/main.py:_auto_seed_demo_data`) is now gated on `settings.DEMO_MODE` as its first statement; `FORCE_RESEED` can no longer bypass it.
- **Self-registration locked down** (C-2) — `POST /api/auth/register` was unauthenticated and accepted a caller-supplied role (including `admin`). It is now demo-mode-only (403 otherwise), uses a `UserRegister` schema with no role/client fields, and always creates `operator` accounts. Privileged roles are assigned only by an admin via `/api/users`.
- **DB-backed token revocation** (H-1) — logout was an in-memory set, lost on every restart and invisible across workers. Replaced with a `TOKEN_BLACKLIST` table keyed by JWT `jti` (sha256 fallback for legacy tokens), pruned on insert.
- **Password-reset token no longer logged** (H-2) — the 24h reset JWT was emitted at DEBUG level; removed in favor of a security-event record.
- **`detail=str(exc)` removed from 7 endpoints** (H-4) — internal exception text no longer surfaced to clients.
- **Blocking secret scanning** (H-6) — `detect-secrets` now runs in CI with a committed `.secrets.baseline` and fails on new findings (was non-blocking); added to pre-commit.
- **Dependency CVE audit** (M-14) — `pip-audit` added as a blocking CI step. Patched starlette PYSEC-2026-161 (fastapi 0.129.0 → 0.136.3, starlette 1.3.1) and the esbuild GHSA-gv7w-rqvm-qjhr / GHSA-g7r4-m6w7-qqqr advisories.

### Added
- **Uniform authorization tiers** (M-7) — three route-level guards (admin / planner / supervisory) applied across all mutation endpoints, closing 93 previously bare-authenticated mutations (including a work-order transition that bypassed the Run-6 gate). Pinned by `test_permission_matrix.py`. `get_current_active_supervisor` was also corrected to stop denying PowerUser and Leader.

### Changed
- **Honest coverage gate** (H-3/H-5) — coverage config moved to `backend/.coveragerc` (CI previously measured the test suite itself via `--cov=.`); the gate now reflects production-code coverage (81.88%, threshold 75%). Consolidated to a single pytest config in `pyproject.toml`, restoring the Pydantic/SQLAlchemy deprecation guards.
- **`orm/` ↔ `schemas/` invariant corrected** (M-6) — four files (`alert`, `analytics`, `simulation`) moved to the directory matching their contents (SQLAlchemy in `orm/`, Pydantic in `schemas/`).
- **Toolchain** — Node 20 → 22, Python standardized on 3.11; docs (README, QUICKSTART, DEPLOYMENT) corrected for versions, test counts, coverage threshold, store count, and the admin demo password.
- **`validate_date_range` wired across all 56 query endpoints** (R6-D-001).

### Removed
- **Simulation V1 HTTP API** (M-3) — the legacy `/api/simulation/*` surface (8-module package + deprecation middleware) was retired past its 2026-06-01 sunset. V2 (`/api/v2/simulation/*`) is the sole engine; the V1 calculation library is retained internally for the floating-pool endpoints.
- Stale `backend/tests/requirements.txt` (conflicting pins, the only LGPL dependency) and 15 tracked `.claude-flow/metrics` telemetry files.

## [1.0.5] - 2026-02-16

### Changed
- **Documentation Expansion** - Expanded API documentation from 6 to 18 endpoint groups covering all 197+ routes
- **CONTRIBUTING.md** - Added code style guide (Black, ESLint 10), testing requirements (real DB only, no mocks for CRUD), and PR process
- **SECURITY.md** - Added JWT auth flow, CORS configuration, rate limiting, CSP headers, and known limitations sections
- **docs/INDEX.md** - Created navigation guide linking all documentation files by category

---

## [1.0.4+1] - 2026-02-14

### Changed
- **Full Dependency Upgrade** - 9-phase gate-based upgrade across 371 files
- **Security Upgrades** - cryptography 44 to 46, python-jose 3.3 to 3.5, python-multipart 0.0.6 to 0.0.22, xlsx replaced with ExcelJS
- **Backend Upgrades** - FastAPI 0.109 to 0.129, Pydantic 2.5 to 2.12, uvicorn 0.27 to 0.40, SQLAlchemy 2.0.25 to 2.0.46, httpx 0.26 to 0.28, black 23 to 25 (353 files reformatted), mypy 1.8 to 1.15, pytest 7 to 8
- **Frontend Major Upgrades** - Pinia 2 to 3, vue-router 4 to 5, vue-i18n 9 to 11, mermaid 10 to 11, date-fns 3 to 4, happy-dom 14 to 20 (GHSA-96g7-g7g9-jxw8 resolved)
- **Tooling Upgrades** - ESLint 8 to 10 (flat config), Tailwind CSS 3 to 4, Vite 5 to 7, Vitest 1 to 4

### Fixed
- **E2E Flaky Tests** - Fixed 3 flaky tests and 28 skipped capacity-planning tests (214 passed, 0 failed)
- **E2E Navigation** - Replaced `text=` selectors with `a[href="/path"]`, added `scrollIntoViewIfNeeded()` and URL verification
- **E2E Serial Mode** - Removed `describe.serial` from capacity-planning (was cascading single failure to 28 skips)
- **Skeleton Loader Waits** - Added proper waits in clipboard-paste tests for quality/downtime pages

### Testing
- **Gate results** - 4,188 backend (76.26% coverage) + 1,434 frontend + 595 E2E, 0 failures
- **npm audit** - 0 HIGH/CRITICAL vulnerabilities

---

## [1.0.4] - 2026-02-13

### Added
- **Capacity Planning Module** - 13-worksheet workbook pattern with full CRUD
- **8 Scenario Types** - OVERTIME, SETUP_REDUCTION, SUBCONTRACT, NEW_LINE, THREE_SHIFT, LEAD_TIME_DELAY, ABSENTEEISM_SPIKE, MULTI_CONSTRAINT
- **Dashboard Inputs Tab** - Configurable parameters for capacity analysis
- **Instructions Tab** - Embedded user guidance within Capacity Planning
- **Undo/Redo UI** - Visual undo/redo controls for grid editing
- **CSV Export** - Export capacity planning data to CSV format
- **Planner Notes** - Per-worksheet planner notes column
- **Stock Staleness Warning** - Alerts for outdated stock data
- **Event Bus Tests** - 176 new tests for domain event system
- **Router Guard Tests** - 23 new tests for Vue Router navigation guards

### Changed
- **Scenario Types Expanded** - Increased from 4 to 8 scenario types
- **kpiStore Renamed** - `kpiStore.js` renamed to `productionDataStore.js` to resolve naming collision
- **Mock CRUD Tests Replaced** - Converted 3 mock-based test files to real DB tests (71 mock refs eliminated)

### Fixed
- **EventBus Handler Dispatch** - Fixed shadowed asyncio import causing silent handler failures
- **Production Bugs** - Fixed non-existent columns (hold_timestamp, resume_timestamp) and date/datetime mismatches
- **E2E Test Stability** - Fixed 70 failing E2E tests, resolved flaky login selectors

### Testing
- **6,217 total tests** (4,188 backend + 1,434 frontend + 595 E2E), 0 failures
- **76.26% backend coverage** (threshold: 55%)

---

## [1.0.3] - 2026-02-01

### Added
- **Predictive Analytics UI** - "Show Forecast" toggle on Efficiency and Performance KPI charts
- **Forecast Visualization** - 7-30 day predictions with confidence intervals on trend charts
- **QR Scanner Quick-Access** - QR Scanner button directly in dashboard header
- **Saved Filters UI** - Dropdown menu to save, load, and manage filter presets
- **Bradford Factor Widget** - Included in default dashboard for Leader, PowerUser, and Admin roles
- **Email Reports Dialog** - UI for configuring automated report delivery

### Fixed
- **Keyboard Shortcuts** - Corrected help shortcut to Ctrl+/, redo to Ctrl+Y
- **Tooltip Enhancements** - Added formula and meaning tooltips to all KPI cards

---

## [1.0.2] - 2026-01-30

### Added
- **OEE KPI View** - Component breakdown (Availability x Performance x Quality)
- **WIP Aging Endpoints** - `/api/kpi/wip-aging/top` and `/api/kpi/wip-aging/trend`
- **Efficiency Breakdowns** - By-shift and by-product breakdown endpoints

### Fixed
- **WIP Aging View** - All data tables connected and displaying correctly
- **Hold Records History** - Corrected to use HOLD_ENTRY schema fields
- **Oldest Item Card** - Shows actual max age instead of hardcoded value
- **Response Models** - Aligned WIPHoldResponse with database schema

---

## [1.0.1] - 2026-01-27

### Changed
- **Test Coverage** - Increased from 43% to 77.48% backend coverage
- **Skipped Tests** - Reduced from 93 to 59 skipped tests

### Fixed
- **SQLite Compatibility** - Replaced datediff with proper date comparison functions
- **ProductionEntry Schema** - Fixed for multi-tenant isolation
- **SQL text() Wrapper** - Fixed for SQLAlchemy 2.0 compatibility
- **TestDataFactory** - Updated for new schema fields
- **ImportLog Schema** - Added missing SQLAlchemy schema

---

## [1.0.0] - 2026-01-25

### Added

#### Core Platform
- **Multi-Tenant Architecture** - Complete client data isolation across 50+ manufacturing clients
- **Role-Based Access Control** - Four user roles: Admin, PowerUser, Leader, Operator
- **JWT Authentication** - Secure token-based authentication with bcrypt password hashing
- **SQLite/MariaDB Support** - Development SQLite with production MariaDB compatibility

#### 10 Real-Time KPI Calculations
- **KPI #1: WIP Aging** - Work-in-progress tracking with hold management and aging alerts
- **KPI #2: On-Time Delivery (OTD)** - TRUE-OTD and standard OTD metrics with date inference
- **KPI #3: Efficiency** - Hours produced vs. hours available with 5-level inference engine
- **KPI #4: Quality PPM** - Parts per million defect rate calculation
- **KPI #5: Quality DPMO** - Defects per million opportunities with Sigma level
- **KPI #6: First Pass Yield (FPY)** - Pass rate without rework per process step
- **KPI #7: Rolled Throughput Yield (RTY)** - Final quality yield after all stages
- **KPI #8: Availability** - Uptime vs. downtime analysis
- **KPI #9: Performance** - Actual vs. ideal cycle time with inference fallbacks
- **KPI #10: Absenteeism** - Labor attendance tracking with Bradford Factor scoring

#### Data Entry Features
- **AG Grid Integration** - Excel-like data grids with copy/paste, fill handle, undo/redo
- **CSV Bulk Upload** - Import 100+ records with validation and read-back confirmation
- **QR Code Scanner** - Mobile-friendly work order lookup via QR code scanning
- **Data Completeness Indicators** - Visual indicators showing data entry coverage

#### Dashboard Features
- **Predictive Analytics** - 7-30 day forecasting with exponential smoothing (Show Forecast toggle)
- **Custom Dashboards** - Role-based layouts with drag-and-drop widget customization
- **Saved Filters** - Save, load, and manage filter presets via dropdown
- **Bradford Factor Widget** - Absenteeism pattern analysis for Leader+ roles
- **Operations Health Dashboard** - High-level manufacturing status overview
- **My Shift Dashboard** - Personalized operator view with current shift metrics

#### Reports
- **PDF Report Generation** - Comprehensive KPI reports with charts and tables
- **Excel Export** - Multi-sheet workbooks with raw data and summaries
- **Email Delivery** - Automated daily/weekly/monthly report delivery via SendGrid/SMTP
- **Work Order Management** - Full work order lifecycle tracking and reporting

#### User Experience
- **Keyboard Shortcuts** - Power-user shortcuts (Ctrl+S save, Ctrl+Z undo, Ctrl+/ help)
- **Responsive Design** - Mobile-first design with tablet-friendly data entry
- **Dark Mode Support** - Full dark theme compatibility
- **WCAG 2.1 AA Accessibility** - Screen reader support, ARIA labels, skip links

#### Developer Experience
- **197+ API Endpoints** - Comprehensive REST API with FastAPI auto-documentation
- **Modular Route Architecture** - Organized route files by domain
- **Type Hints** - Full Python type annotations with Pydantic validation
- **Test Coverage** - 77.48% backend coverage, 1,558 passing tests

### Changed

- **Refactored main.py** - Extracted all routes into modular files under `backend/routes/`
- **Pinia Store Consolidation** - Fixed duplicate store ID conflicts
- **API Service Split** - Separated frontend API service into domain-specific modules
- **Loading States** - Standardized loading indicators across all components
- **Error Handling** - Extended error snackbar timeouts to 5000ms for readability

### Fixed

- **OTD Date Inference** - Implemented proper fallback chain (planned_ship_date -> required_date -> calculated)
- **WIP Aging View** - Connected all data tables and fixed "Oldest Item" card calculation
- **Efficiency View** - Added by-shift and by-product breakdown endpoints
- **Hold Records History** - Fixed table schema to match HOLD_ENTRY structure
- **Test Mocks** - Corrected field names in test fixtures to match actual schemas
- **Contrast Ratios** - Fixed WCAG contrast issues in KPI cards and widgets
- **SQLite Compatibility** - Replaced datediff with proper date comparison functions

### Security

- **Rate Limiting** - 10 requests/minute on authentication endpoints
- **Password Policy** - Minimum length and complexity requirements
- **Input Validation** - Pydantic models for all API inputs
- **SQL Injection Prevention** - Parameterized queries via SQLAlchemy ORM
- **XSS Protection** - Vue.js automatic escaping and Content Security Policy headers
- **Client Isolation** - `client_id` filter on all database queries

### Documentation

- **Architecture Documentation** - System design and component diagrams
- **API Documentation** - All endpoints with request/response examples
- **Deployment Guide** - Production deployment instructions
- **Accessibility Audit Report** - WCAG 2.1 AA compliance verification
- **Comprehensive Validation Report** - Full platform audit results

---

## [0.9.0] - 2026-01-15 (Pre-Release)

### Added
- Initial predictive analytics API endpoints
- QR code generation and scanning functionality
- User preferences persistence
- Saved filter configurations

### Fixed
- 34 previously skipped tests now passing
- Coverage increased from 43% to 77.48%

---

## [0.8.0] - 2026-01-08 (Beta)

### Added
- AG Grid Community Edition integration
- CSV upload with validation wizard
- Read-back confirmation workflow
- Bradford Factor widget for absenteeism

### Changed
- Migrated from basic tables to AG Grid
- Improved mobile responsiveness

---

## [0.7.0] - 2025-12-31 (Alpha)

### Added
- Initial platform release
- Core KPI calculations (Efficiency, Performance)
- Basic production entry forms
- JWT authentication system
- Multi-tenant database schema

---

## Version History Summary

| Version | Date | Milestone |
|---------|------|-----------|
| 1.0.5 | 2026-02-16 | Documentation expansion (API, Security, Contributing) |
| 1.0.4+1 | 2026-02-14 | Full dependency upgrade + E2E stability fixes |
| 1.0.4 | 2026-02-13 | Capacity Planning (13 worksheets, 8 scenarios) |
| 1.0.3 | 2026-02-01 | Predictive Analytics UI |
| 1.0.2 | 2026-01-30 | OEE KPI View, WIP Aging fixes |
| 1.0.1 | 2026-01-27 | Test coverage boost (43% to 77%) |
| 1.0.0 | 2026-01-25 | Production Release |
| 0.9.0 | 2026-01-15 | Pre-Release (Predictive Analytics) |
| 0.8.0 | 2026-01-08 | Beta (AG Grid Integration) |
| 0.7.0 | 2025-12-31 | Alpha (Initial Release) |

---

**Full Changelog**: Compare versions at your repository URL
