# Multi-Tenant Security Audit Checklist
**Date:** 2026-01-01

## Schema Violations

### ❌ CRITICAL: Tables Missing client_id

- [ ] **JOB Table** (`backend/schemas/job.py`)
  - Missing: `client_id` column with foreign key
  - Add after line 16: `client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)`
  - Impact: Work order line items leak across clients
  - No CRUD operations exist for JOB table

- [ ] **DEFECT_DETAIL Table** (`backend/schemas/defect_detail.py`)
  - Missing: `client_id` column with foreign key
  - Add after line 29: `client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)`
  - Impact: Quality defect details accessible across clients
  - No CRUD operations exist for DEFECT_DETAIL table

- [ ] **PART_OPPORTUNITIES Table** (`backend/schemas/part_opportunities.py`)
  - Missing: `client_id` column with foreign key
  - Add after line 15: `client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)`
  - Impact: Part definitions not client-specific
  - No CRUD operations exist for PART_OPPORTUNITIES table

- [ ] **EMPLOYEE Table** (`backend/schemas/employee.py`)
  - Uses weak `client_id_assigned = Column(Text)` without foreign key
  - Should use many-to-many relationship table
  - Create: `EMPLOYEE_CLIENT_ASSIGNMENT` table
  - Impact: No database-level constraint enforcement

---

## CRUD Operations Needed

### ❌ Missing CRUD Files

- [ ] **Create `backend/crud/job.py`**
  - Implement: `create_job(db, job, current_user)`
  - Implement: `get_job(db, job_id, current_user)`
  - Implement: `get_jobs(db, current_user, filters...)`
  - Implement: `update_job(db, job_id, job_update, current_user)`
  - Implement: `delete_job(db, job_id, current_user)`
  - All functions must use `verify_client_access()` and `build_client_filter_clause()`

- [ ] **Create `backend/crud/defect_detail.py`**
  - Implement: `create_defect_detail(db, defect, current_user)`
  - Implement: `get_defect_detail(db, defect_id, current_user)`
  - Implement: `get_defect_details(db, current_user, filters...)`
  - Implement: `update_defect_detail(db, defect_id, defect_update, current_user)`
  - Implement: `delete_defect_detail(db, defect_id, current_user)`
  - All functions must use client filtering

- [ ] **Create `backend/crud/part_opportunities.py`**
  - Implement CRUD operations with client filtering
  - Note: Reference data, may need different isolation strategy

---

## API Endpoints Needed

### ❌ Missing API Routes in `backend/main.py`

- [ ] **JOB Endpoints**
  - `POST /api/jobs` - Create job
  - `GET /api/jobs` - List jobs with filters
  - `GET /api/jobs/{job_id}` - Get job by ID
  - `PUT /api/jobs/{job_id}` - Update job
  - `DELETE /api/jobs/{job_id}` - Delete job (supervisor only)
  - All endpoints must pass `current_user: User = Depends(get_current_user)`

- [ ] **DEFECT_DETAIL Endpoints**
  - `POST /api/defects` - Create defect detail
  - `GET /api/defects` - List defect details
  - `GET /api/defects/{defect_id}` - Get defect by ID
  - `PUT /api/defects/{defect_id}` - Update defect
  - `DELETE /api/defects/{defect_id}` - Delete defect
  - All endpoints must pass `current_user`

- [ ] **PART_OPPORTUNITIES Endpoints**
  - `POST /api/part-opportunities` - Create part opportunity
  - `GET /api/part-opportunities` - List part opportunities
  - `GET /api/part-opportunities/{part_number}` - Get by part number
  - `PUT /api/part-opportunities/{part_number}` - Update
  - `DELETE /api/part-opportunities/{part_number}` - Delete
  - All endpoints must pass `current_user`

---

## Calculation Functions Security

### ❌ Functions Lacking Client Filtering

#### File: `backend/calculations/wip_aging.py`
- [ ] `calculate_wip_aging(db, product_id, as_of_date)` - Add `current_user` parameter
- [ ] `identify_chronic_holds(db, threshold_days)` - Add `current_user` parameter
- [ ] Apply `build_client_filter_clause()` to all queries

#### File: `backend/calculations/absenteeism.py`
- [ ] `calculate_absenteeism(db, shift_id, start_date, end_date)` - Add `current_user` parameter
- [ ] `calculate_bradford_factor(db, employee_id, start_date, end_date)` - Add `current_user` parameter
- [ ] Apply client filtering to queries

#### File: `backend/calculations/otd.py`
- [ ] `calculate_otd(db, start_date, end_date, product_id)` - Add `current_user` parameter
- [ ] `identify_late_orders(db, as_of_date)` - Add `current_user` parameter
- [ ] Apply client filtering to queries

#### File: `backend/calculations/ppm.py`
- [ ] `calculate_ppm(db, product_id, shift_id, start_date, end_date)` - Add `current_user` parameter
- [ ] `identify_top_defects(db, product_id, start_date, end_date, limit)` - Add `current_user` parameter
- [ ] Apply client filtering to queries

#### File: `backend/calculations/dpmo.py`
- [ ] `calculate_dpmo(db, product_id, shift_id, start_date, end_date, opportunities)` - Add `current_user` parameter
- [ ] Apply client filtering to queries

#### File: `backend/calculations/fpy_rty.py`
- [ ] `calculate_fpy(db, product_id, start_date, end_date)` - Add `current_user` parameter
- [ ] `calculate_rty(db, product_id, start_date, end_date)` - Add `current_user` parameter
- [ ] `calculate_quality_score(db, product_id, start_date, end_date)` - Add `current_user` parameter
- [ ] Apply client filtering to queries

#### File: `backend/calculations/availability.py`
- [ ] Review: `calculate_availability(db, product_id, shift_id, production_date)` - Check if client filtering needed

#### File: `backend/calculations/efficiency.py`
- [ ] Review: `calculate_efficiency(db, entry, product)` - Check if client filtering needed

#### File: `backend/calculations/performance.py`
- [ ] Review: `calculate_performance(db, entry, product)` - Check if client filtering needed

---

## API Endpoint Updates Required

### Files: `backend/main.py`

Update these endpoints to pass `current_user` to calculation functions:

- [ ] Line 708: `get_chronic_holds()` - Pass `current_user` to `identify_chronic_holds()`
- [ ] Line 793: `calculate_absenteeism_kpi()` - Pass `current_user` to `calculate_absenteeism()`
- [ ] Line 820: `get_bradford_factor()` - Pass `current_user` to `calculate_bradford_factor()`
- [ ] Line 879: `calculate_otd_kpi()` - Pass `current_user` to `calculate_otd()`
- [ ] Line 899: `get_late_orders()` - Pass `current_user` to `identify_late_orders()`
- [ ] Line 986: `calculate_ppm_kpi()` - Pass `current_user` to `calculate_ppm()`
- [ ] Line 1013: `calculate_dpmo_kpi()` - Pass `current_user` to `calculate_dpmo()`
- [ ] Line 1040: `calculate_fpy_rty_kpi()` - Pass `current_user` to `calculate_fpy()` and `calculate_rty()`
- [ ] Line 1065: `get_quality_score()` - Pass `current_user` to `calculate_quality_score()`
- [ ] Line 1078: `get_top_defects()` - Pass `current_user` to `identify_top_defects()`

---

## Database Migration Tasks

- [ ] **Create Alembic Migration: Add client_id to JOB**
  ```bash
  alembic revision --autogenerate -m "Add client_id to JOB table"
  ```

- [ ] **Create Alembic Migration: Add client_id to DEFECT_DETAIL**
  ```bash
  alembic revision --autogenerate -m "Add client_id to DEFECT_DETAIL table"
  ```

- [ ] **Create Alembic Migration: Add client_id to PART_OPPORTUNITIES**
  ```bash
  alembic revision --autogenerate -m "Add client_id to PART_OPPORTUNITIES table"
  ```

- [ ] **Create Alembic Migration: Refactor EMPLOYEE client assignment**
  ```bash
  alembic revision --autogenerate -m "Create EMPLOYEE_CLIENT_ASSIGNMENT table"
  ```

- [ ] **Data Migration: Populate client_id for existing records**
  - JOB: Inherit from WORK_ORDER.client_id
  - DEFECT_DETAIL: Inherit from QUALITY_ENTRY.client_id
  - PART_OPPORTUNITIES: Assign to appropriate clients
  - EMPLOYEE: Migrate from client_id_assigned text field

---

## Testing Tasks

- [ ] **Run Security Validation Script**
  ```bash
  python database/tests/validate_multi_tenant_sqlite.py
  ```

- [ ] **Test: Client A cannot see Client B's data**
  - Create records for both clients
  - Verify OPERATOR role filtering
  - Verify cross-client access denied

- [ ] **Test: ADMIN can see all clients**
  - Create records for multiple clients
  - Verify ADMIN sees all records
  - Verify POWERUSER sees all records

- [ ] **Test: LEADER with multi-client access**
  - Assign LEADER to "CLIENT-A,CLIENT-B"
  - Verify sees both clients' data
  - Verify cannot see CLIENT-C

- [ ] **Test: JOB table isolation (after fix)**
  - Create jobs for different clients
  - Verify isolation in CRUD operations

- [ ] **Test: DEFECT_DETAIL isolation (after fix)**
  - Create defects for different clients
  - Verify isolation in CRUD operations

- [ ] **Test: Calculation functions respect client isolation**
  - Run KPI calculations for Client A
  - Verify results only include Client A's data

---

## Documentation Tasks

- [ ] **Document: Why PRODUCT table has no client_id**
  - Add comment in schema file
  - Explain shared reference data strategy

- [ ] **Document: Why SHIFT table has no client_id**
  - Add comment in schema file
  - Explain shared shift definitions

- [ ] **Document: FLOATING_POOL design decision**
  - Clarify if intentionally shared or needs client_id
  - Add comments explaining resource sharing

- [ ] **Update: API documentation**
  - Document client isolation behavior
  - Explain role-based access control
  - Document multi-client leader access

---

## Code Review Checklist

### Before Merging to Production:

- [ ] All schema changes deployed via Alembic migrations
- [ ] All CRUD operations test client filtering
- [ ] All API endpoints pass current_user
- [ ] All calculation functions apply client filtering
- [ ] Security validation tests pass 100%
- [ ] No database queries bypass client_id filtering
- [ ] Foreign key constraints enforced in database
- [ ] Integration tests verify cross-client isolation

---

## Performance Considerations

- [ ] **Index Review: client_id columns**
  - Verify all client_id columns have indexes
  - Add composite indexes where needed (e.g., client_id + date)

- [ ] **Query Performance: Large multi-tenant datasets**
  - Test queries with 50+ clients
  - Verify query plans use client_id indexes
  - Consider partitioning by client_id if needed

- [ ] **Caching Strategy: Client-specific data**
  - Ensure cache keys include client_id
  - Prevent cache poisoning across clients

---

## Security Best Practices

- [ ] **Principle of Least Privilege**
  - OPERATOR: Only assigned clients
  - LEADER: Multiple clients (explicit assignment)
  - POWERUSER: All clients (read-only in most cases)
  - ADMIN: All clients (full access)

- [ ] **Defense in Depth**
  - Database-level: Foreign key constraints
  - Application-level: Middleware authorization
  - API-level: current_user required on all endpoints
  - Query-level: Client filtering in WHERE clauses

- [ ] **Audit Logging**
  - Log all cross-client access attempts
  - Log authorization failures
  - Track client_id in all transaction logs

---

## Sign-Off

- [ ] Schema changes reviewed and approved
- [ ] CRUD operations tested and verified
- [ ] API endpoints tested with different roles
- [ ] Security validation tests pass
- [ ] Documentation complete
- [ ] Performance benchmarks acceptable
- [ ] Ready for production deployment

**Approval Required From:**
- [ ] Database Administrator
- [ ] Security Team
- [ ] QA Team
- [ ] Product Owner

---

**Status:** ❌ NOT READY FOR PRODUCTION

**Blocking Issues Count:** 13 critical items

**Target Completion Date:** _____________

**Actual Completion Date:** _____________
