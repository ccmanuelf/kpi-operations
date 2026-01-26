# Changelog

All notable changes to the Manufacturing KPI Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
| 1.0.0 | 2026-01-25 | Production Release |
| 0.9.0 | 2026-01-15 | Pre-Release (Predictive Analytics) |
| 0.8.0 | 2026-01-08 | Beta (AG Grid Integration) |
| 0.7.0 | 2025-12-31 | Alpha (Initial Release) |

---

**Full Changelog**: Compare versions at your repository URL
