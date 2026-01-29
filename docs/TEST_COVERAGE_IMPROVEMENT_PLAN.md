# Test Coverage Improvement Plan

## Executive Summary

This plan addresses the identified coverage gaps in the KPI Operations Platform test suite. The goal is to achieve **85%+ coverage** across all modules by replacing aggressive mocking with real database transactions and adding comprehensive edge case testing.

---

## Current State Analysis

### Test Metrics
| Metric | Current | Target |
|--------|---------|--------|
| Backend Tests | 2,905 passed | 3,500+ |
| E2E Tests | 136 passed | 150+ |
| CRUD Coverage | 18-48% | 85%+ |
| Route Coverage | 13-56% | 80%+ |
| Calculation Coverage | 12-96% | 85%+ |

### Root Causes of Low Coverage

1. **Aggressive Mocking** - Tests mock the database layer, so CRUD code paths never execute
2. **Missing Edge Cases** - Error conditions, validation failures, constraint violations untested
3. **Authentication Bypass Issues** - Route tests can't reach CRUD code due to auth middleware

---

## Phase 1: Test Infrastructure Improvements (Foundation)

### Task 1.1: Create Real Database Test Fixtures
**Priority:** CRITICAL | **Complexity:** Medium | **Dependencies:** None

**Description:**
Replace mocked database fixtures with real SQLite transactions that populate actual test data.

**Acceptance Criteria:**
- [ ] Create `conftest.py` with database session fixtures using real transactions
- [ ] Create test data factory functions for all entities (Client, User, Product, etc.)
- [ ] Implement automatic rollback after each test
- [ ] Verify FK relationships are enforced in tests

**Files to Create/Modify:**
- `backend/tests/conftest.py` (enhance)
- `backend/tests/fixtures/factories.py` (new)

---

### Task 1.2: Create Authenticated Test Client Fixtures
**Priority:** CRITICAL | **Complexity:** Medium | **Dependencies:** Task 1.1

**Description:**
Create fixtures that provide pre-authenticated test clients for different user roles.

**Acceptance Criteria:**
- [ ] `authenticated_client` fixture with valid JWT token
- [ ] `admin_client` fixture for admin-only routes
- [ ] `supervisor_client` fixture for supervisor routes
- [ ] `operator_client` fixture for basic user routes
- [ ] `multi_tenant_client(client_id)` fixture for tenant isolation tests

**Files to Create/Modify:**
- `backend/tests/conftest.py`
- `backend/tests/fixtures/auth_fixtures.py` (new)

---

### Task 1.3: Create Test Data Seeding Utilities
**Priority:** HIGH | **Complexity:** Low | **Dependencies:** Task 1.1

**Description:**
Create utility functions to seed test database with realistic, interconnected data.

**Acceptance Criteria:**
- [ ] Function to seed minimal data for unit tests
- [ ] Function to seed comprehensive data for integration tests
- [ ] Automatic cleanup/rollback mechanisms
- [ ] Support for client isolation testing

**Files to Create/Modify:**
- `backend/tests/fixtures/seed_data.py` (new)

---

## Phase 2: CRUD Module Coverage (18-48% → 85%+)

### Task 2.1: Workflow CRUD Tests with Real Transactions
**Priority:** HIGH | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 24% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test `create_transition_log` with valid/invalid data
- [ ] Test `get_work_order_transitions` with existing/non-existing work orders
- [ ] Test `bulk_transition_work_orders` with mixed valid/invalid IDs
- [ ] Test `apply_workflow_template` with valid/invalid templates
- [ ] Test validation errors and constraint violations
- [ ] Test client isolation (user can only see their client's transitions)

---

### Task 2.2: Saved Filter CRUD Tests
**Priority:** HIGH | **Complexity:** Low | **Dependencies:** Phase 1

**Current Coverage:** 29% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test create/read/update/delete with real database
- [ ] Test `set_default_filter` clears previous defaults
- [ ] Test filter history tracking
- [ ] Test user isolation (filters are user-specific)
- [ ] Test validation errors for invalid filter criteria

---

### Task 2.3: Client Config CRUD Tests
**Priority:** HIGH | **Complexity:** Low | **Dependencies:** Phase 1

**Current Coverage:** 30% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test `get_client_config_or_defaults` returns defaults when no config exists
- [ ] Test `update_client_config` creates if not exists
- [ ] Test `get_all_client_configs` with admin vs regular user
- [ ] Test validation errors for invalid threshold values

---

### Task 2.4: Employee CRUD Tests
**Priority:** HIGH | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 34% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test floating pool assignment/removal
- [ ] Test `assign_employee_to_client` prevents double assignment
- [ ] Test client isolation for employee queries
- [ ] Test cascade behavior when deleting employees

---

### Task 2.5: Work Order CRUD Tests
**Priority:** HIGH | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 36% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test status transitions (valid and invalid)
- [ ] Test `get_work_orders_by_status` filtering
- [ ] Test `get_work_orders_by_date_range` with edge cases
- [ ] Test client isolation
- [ ] Test cascade to jobs when work order deleted

---

### Task 2.6: Hold CRUD Tests
**Priority:** MEDIUM | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 35% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test hold creation with validation
- [ ] Test resume workflow
- [ ] Test hold duration calculations
- [ ] Test `identify_chronic_holds` logic
- [ ] Test client isolation

---

## Phase 3: Route Coverage (13-56% → 80%+)

### Task 3.1: Production Routes with Authenticated Client
**Priority:** HIGH | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 27% → **Target:** 80%

**Acceptance Criteria:**
- [ ] Test POST `/api/production` with valid data
- [ ] Test POST `/api/production` with invalid product_id (404)
- [ ] Test POST `/api/production` with invalid shift_id (404)
- [ ] Test GET `/api/production` with filters
- [ ] Test PUT `/api/production/{id}` update
- [ ] Test DELETE `/api/production/{id}` (supervisor only)
- [ ] Test CSV upload with valid/invalid data
- [ ] Test batch import endpoint

---

### Task 3.2: Quality Routes Tests
**Priority:** HIGH | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 21% → **Target:** 80%

**Acceptance Criteria:**
- [ ] Test all CRUD endpoints with authenticated client
- [ ] Test defect detail creation/retrieval
- [ ] Test quality metrics calculations
- [ ] Test client isolation

---

### Task 3.3: Attendance Routes Tests
**Priority:** HIGH | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** ~30% → **Target:** 80%

**Acceptance Criteria:**
- [ ] Test clock-in/clock-out endpoints
- [ ] Test attendance entry CRUD
- [ ] Test absence type validation
- [ ] Test client isolation

---

### Task 3.4: KPI Routes Tests
**Priority:** MEDIUM | **Complexity:** High | **Dependencies:** Phase 1

**Current Coverage:** 13% → **Target:** 75%

**Acceptance Criteria:**
- [ ] Test efficiency calculation endpoints
- [ ] Test OTD calculation endpoints
- [ ] Test quality metrics endpoints
- [ ] Test aggregated dashboard endpoint
- [ ] Test date range filtering
- [ ] Test client isolation

---

### Task 3.5: Reports Routes Tests
**Priority:** MEDIUM | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 24% → **Target:** 75%

**Acceptance Criteria:**
- [ ] Test daily report generation
- [ ] Test PDF export
- [ ] Test Excel export
- [ ] Test date range validation

---

## Phase 4: Calculation Module Coverage (12-96% → 85%+)

### Task 4.1: Alerts Module Tests
**Priority:** HIGH | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 11% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test all alert generation functions with real threshold data
- [ ] Test threshold breach detection (above, below, equal)
- [ ] Test alert severity assignment
- [ ] Test prediction-based alerts with confidence scores

---

### Task 4.2: WIP Aging Module Tests
**Priority:** HIGH | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 42% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test `calculate_wip_aging` with real work orders
- [ ] Test hold duration adjustments
- [ ] Test `identify_chronic_holds` with real data
- [ ] Test threshold retrieval from client config

---

### Task 4.3: Performance Module Tests
**Priority:** HIGH | **Complexity:** Low | **Dependencies:** Phase 1

**Current Coverage:** 54% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test `calculate_performance` with various inputs
- [ ] Test `calculate_quality_rate` with real production entries
- [ ] Test `calculate_oee` component multiplication
- [ ] Test edge cases (zero values, negative values)

---

### Task 4.4: Trend Analysis Module Tests
**Priority:** MEDIUM | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 61% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test moving average calculations
- [ ] Test trend direction detection
- [ ] Test with insufficient data points
- [ ] Test with seasonal patterns

---

### Task 4.5: OTD Module Tests
**Priority:** MEDIUM | **Complexity:** Medium | **Dependencies:** Phase 1

**Current Coverage:** 64% → **Target:** 85%

**Acceptance Criteria:**
- [ ] Test OTD percentage calculation with real work orders
- [ ] Test risk assessment with approaching deadlines
- [ ] Test lead time calculations
- [ ] Test cycle time calculations

---

## Phase 5: Edge Cases and Error Handling

### Task 5.1: Validation Error Tests
**Priority:** MEDIUM | **Complexity:** Low | **Dependencies:** Phases 2-4

**Acceptance Criteria:**
- [ ] Test Pydantic validation errors return 422 with details
- [ ] Test required field missing errors
- [ ] Test type conversion errors
- [ ] Test range validation errors (negative quantities, etc.)

---

### Task 5.2: Constraint Violation Tests
**Priority:** MEDIUM | **Complexity:** Low | **Dependencies:** Phases 2-4

**Acceptance Criteria:**
- [ ] Test foreign key violations return appropriate errors
- [ ] Test unique constraint violations (duplicate entries)
- [ ] Test check constraint violations

---

### Task 5.3: Authorization Error Tests
**Priority:** HIGH | **Complexity:** Low | **Dependencies:** Phases 2-4

**Acceptance Criteria:**
- [ ] Test 401 for unauthenticated requests
- [ ] Test 403 for unauthorized role access
- [ ] Test client isolation (403 for wrong client)
- [ ] Test supervisor-only endpoints with operator user

---

### Task 5.4: Not Found Error Tests
**Priority:** LOW | **Complexity:** Low | **Dependencies:** Phases 2-4

**Acceptance Criteria:**
- [ ] Test 404 for non-existent resource IDs
- [ ] Test 404 for deleted resources
- [ ] Test 404 message includes resource type

---

## Dependency Graph

```
Phase 1 (Foundation)
├── Task 1.1: Real Database Fixtures
│   ├── Task 1.2: Authenticated Client Fixtures
│   └── Task 1.3: Test Data Seeding
│
├─────────────────────────────────────┐
│                                     │
Phase 2 (CRUD)                    Phase 3 (Routes)
├── Task 2.1: Workflow            ├── Task 3.1: Production
├── Task 2.2: Saved Filter        ├── Task 3.2: Quality
├── Task 2.3: Client Config       ├── Task 3.3: Attendance
├── Task 2.4: Employee            ├── Task 3.4: KPI
├── Task 2.5: Work Order          └── Task 3.5: Reports
└── Task 2.6: Hold
│                                     │
├─────────────────────────────────────┤
│                                     │
Phase 4 (Calculations)
├── Task 4.1: Alerts
├── Task 4.2: WIP Aging
├── Task 4.3: Performance
├── Task 4.4: Trend Analysis
└── Task 4.5: OTD
│
└─────────────────────────────────────┐
                                      │
                                Phase 5 (Edge Cases)
                                ├── Task 5.1: Validation Errors
                                ├── Task 5.2: Constraint Violations
                                ├── Task 5.3: Authorization Errors
                                └── Task 5.4: Not Found Errors
```

---

## Implementation Priority Order

### Week 1: Foundation (CRITICAL)
1. Task 1.1: Real Database Fixtures
2. Task 1.2: Authenticated Client Fixtures
3. Task 1.3: Test Data Seeding

### Week 2: High-Impact CRUD & Routes
4. Task 2.1: Workflow CRUD
5. Task 2.5: Work Order CRUD
6. Task 3.1: Production Routes
7. Task 4.1: Alerts Module

### Week 3: Remaining CRUD & Routes
8. Task 2.2-2.4: Saved Filter, Client Config, Employee
9. Task 2.6: Hold CRUD
10. Task 3.2-3.3: Quality, Attendance Routes
11. Task 4.2-4.3: WIP Aging, Performance

### Week 4: Calculations & Edge Cases
12. Task 3.4-3.5: KPI, Reports Routes
13. Task 4.4-4.5: Trend Analysis, OTD
14. Task 5.1-5.4: All Edge Case Tests

---

## Success Metrics

| Milestone | Target Coverage | Test Count |
|-----------|-----------------|------------|
| Phase 1 Complete | 45% | 3,000 |
| Phase 2 Complete | 60% | 3,200 |
| Phase 3 Complete | 70% | 3,350 |
| Phase 4 Complete | 80% | 3,450 |
| Phase 5 Complete | 85%+ | 3,500+ |

---

## Technical Notes

### Database Strategy
- Use `sqlite:///:memory:` for fast, isolated tests
- Use `session.rollback()` after each test for cleanup
- Leverage existing `regenerate_all_data.py` patterns for test data

### Authentication Strategy
- Create real JWT tokens in fixtures (not mocked)
- Use actual `create_access_token()` function
- Test with real user records in database

### Coverage Measurement
- Run `pytest --cov=backend --cov-report=html` for detailed reports
- Focus on branch coverage, not just line coverage
- Exclude test files and migrations from coverage

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | Claude | Initial plan created |
