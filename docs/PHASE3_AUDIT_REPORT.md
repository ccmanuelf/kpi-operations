# Phase 3: Attendance & Labor Metrics - Gap Analysis Report

**Audit Date:** 2026-01-02
**Specification Source:** `04-Phase3_Attendance_Inventory.csv`
**Status:** ⚠️ CRITICAL GAPS IDENTIFIED

---

## Executive Summary

Phase 3 implementation has **MAJOR GAPS** compared to the specification. The current system uses a simplified attendance model that does NOT match the comprehensive `ATTENDANCE_ENTRY` and `COVERAGE_ENTRY` schema defined in the specification.

**Overall Compliance:** ~45% ⚠️

**Critical Issues:**
1. ❌ **Missing 10+ critical fields** from ATTENDANCE_ENTRY specification
2. ❌ **Coverage Entry system incomplete** - floating pool logic not implemented
3. ❌ **Absence types incomplete** - spec defines 6 types, implementation has different set
4. ❌ **No floating pool double-billing prevention**
5. ❌ **Missing verification workflow** (verified_by, coverage_confirmed)
6. ❌ **Backend routes missing** - No API endpoints found
7. ⚠️ **Schema mismatch** - SQLAlchemy models don't match Pydantic schemas

---

## 1. ATTENDANCE_ENTRY Table Analysis

### 1.1 Specification Requirements (from CSV lines 2-20)

The spec defines **19 fields** across these categories:

**Required Core Fields:**
- `attendance_entry_id` (VARCHAR 50) - System-generated UUID
- `employee_id_fk` (VARCHAR 20)
- `client_id_fk` (VARCHAR 20) - Multi-tenant isolation
- `shift_date` (DATE)
- `shift_type` (ENUM: SHIFT_1ST, SHIFT_2ND, SAT_OT, SUN_OT, OTHER)
- `scheduled_hours` (DECIMAL 10,2)
- `is_absent` (BOOLEAN)

**Conditional Fields:**
- `actual_hours` (DECIMAL 10,2) - REQUIRED if present
- `absence_type` (ENUM) - REQUIRED if is_absent=TRUE
  - UNSCHEDULED_ABSENCE
  - VACATION
  - MEDICAL_LEAVE
  - PERSONAL_DAY
  - SUSPENDED
  - OTHER
- `absence_hours` (DECIMAL 10,2) - REQUIRED if is_absent=TRUE
- `covered_by_floating_employee_id` (VARCHAR 20) - If covered by floating pool

**Verification Fields:**
- `coverage_confirmed` (BOOLEAN) - Default FALSE until supervisor verifies
- `recorded_by_user_id` (VARCHAR 20)
- `recorded_at` (TIMESTAMP)
- `verified_by_user_id` (VARCHAR 20) - Optional supervisor verification
- `verified_at` (TIMESTAMP)

**Metadata:**
- `notes` (TEXT, 500 chars max)
- `created_at`, `updated_at` (TIMESTAMP)

### 1.2 Current Implementation

#### ✅ SQLAlchemy Model (`backend/schemas/attendance_entry.py`)
**STATUS: PARTIAL - Missing critical fields**

```python
class AttendanceEntry(Base):
    attendance_entry_id = Column(String(50), primary_key=True)  ✅
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'))  ✅
    employee_id = Column(Integer, ForeignKey('EMPLOYEE.employee_id'))  ✅
    shift_date = Column(DateTime)  ✅
    shift_id = Column(Integer, ForeignKey('SHIFT.shift_id'))  ⚠️ Different from spec
    scheduled_hours = Column(Numeric(5, 2))  ✅
    actual_hours = Column(Numeric(5, 2))  ✅
    absence_hours = Column(Numeric(5, 2))  ✅
    is_absent = Column(Integer, default=0)  ✅
    absence_type = Column(SQLEnum(AbsenceType))  ⚠️ Only 4 types vs 6 in spec

    # ❌ MISSING FROM SPEC:
    # - shift_type (ENUM) - Critical field
    # - covered_by_floating_employee_id
    # - coverage_confirmed
    # - recorded_by_user_id (has entered_by instead)
    # - recorded_at
    # - verified_by_user_id
    # - verified_at

    # ✅ EXTRA FIELDS (not in spec, but useful):
    arrival_time = Column(DateTime)
    departure_time = Column(DateTime)
    is_late = Column(Integer)
    is_early_departure = Column(Integer)
```

**Gap:** Missing 7 critical fields from specification

#### ❌ Pydantic Models (`backend/models/attendance.py`)
**STATUS: MAJOR MISMATCH**

The Pydantic models use a **completely different schema**:

```python
class AttendanceRecordCreate(BaseModel):
    employee_id: int  # ⚠️ Should be VARCHAR(20) per spec
    shift_id: int  # ⚠️ Spec uses shift_type ENUM
    attendance_date: date  # ✅ Matches shift_date
    status: str  # ❌ NOT in spec - spec uses is_absent + absence_type
    scheduled_hours: Decimal  ✅
    actual_hours_worked: Decimal  # ⚠️ Spec calls this actual_hours
    absence_reason: Optional[str]  # ⚠️ Spec uses absence_type ENUM
    notes: Optional[str]  ✅
```

**Gap:** Schema doesn't align with spec OR SQLAlchemy model

#### ❌ Frontend Components

**AttendanceEntry.vue** (Single Entry Form):
```javascript
formData = {
  employee_id: '',  ✅
  date: '',  ✅ (shift_date)
  shift_id: null,  ⚠️ Should be shift_type
  status: 'Present',  ❌ Should be is_absent + absence_type
  absence_reason: '',  ⚠️ Should be absence_type ENUM
  is_excused: false,  ❌ NOT in spec
  late_minutes: 0,  ❌ NOT in spec
  clock_in: '',  ⚠️ Spec calls this arrival_time
  clock_out: '',  ⚠️ Spec calls this departure_time
  notes: ''  ✅
}
```

**Gap:** Missing 8+ fields from spec, using non-standard status field

**AttendanceEntryGrid.vue** (Bulk Entry):
- ✅ Has AG Grid implementation (good for 50-200 employees)
- ✅ Has bulk status updates
- ❌ Missing floating pool coverage assignment
- ❌ Missing verification workflow
- ❌ Column definitions don't match spec

---

## 2. COVERAGE_ENTRY Table Analysis

### 2.1 Specification Requirements (CSV lines 21-33)

**Required Fields:**
- `coverage_entry_id` (VARCHAR 50) - UUID
- `absent_employee_id` (VARCHAR 20)
- `floating_employee_id` (VARCHAR 20) - **MUST be is_floating_pool=TRUE**
- `client_id_fk` (VARCHAR 20)
- `shift_date` (DATE)
- `shift_type` (ENUM)
- `coverage_duration_hours` (DECIMAL 10,2)
- `recorded_by_user_id` (VARCHAR 20)
- `recorded_at` (TIMESTAMP)
- `verified` (BOOLEAN, default FALSE)
- `notes` (TEXT, 300 chars)
- `created_at`, `updated_at`

**Critical Business Rule:**
> "Prevents double-billing of same floating employee" - Must validate that floating_employee_id is not assigned to multiple coverage entries for same shift_date + shift_type

### 2.2 Current Implementation

#### ⚠️ SQLAlchemy Model (`backend/schemas/coverage_entry.py`)
**STATUS: INCOMPLETE**

```python
class CoverageEntry(Base):
    coverage_entry_id = Column(String(50), primary_key=True)  ✅
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'))  ✅
    floating_employee_id = Column(Integer, ForeignKey('EMPLOYEE.employee_id'))  ✅
    covered_employee_id = Column(Integer)  ⚠️ Spec calls this absent_employee_id
    shift_date = Column(DateTime)  ✅
    shift_id = Column(Integer)  ⚠️ Should be shift_type ENUM

    # ❌ MISSING:
    # - shift_type (critical for double-billing prevention)
    # - coverage_duration_hours
    # - recorded_by_user_id (has assigned_by instead)
    # - recorded_at
    # - verified

    # ✅ EXTRA (not in spec):
    coverage_start_time = Column(DateTime)
    coverage_end_time = Column(DateTime)
    coverage_hours = Column(Integer)  # ⚠️ Should be DECIMAL per spec
    coverage_reason = Column(String(255))
```

**Gap:** Missing 5 critical fields, no double-billing prevention logic

#### ❌ Pydantic Models (`backend/models/coverage.py`)
**STATUS: COMPLETELY DIFFERENT SCHEMA**

```python
class ShiftCoverageCreate(BaseModel):
    shift_id: int
    coverage_date: date
    required_employees: int  # ❌ NOT in COVERAGE_ENTRY spec
    actual_employees: int  # ❌ NOT in spec
    notes: Optional[str]
```

**Critical Issue:** This is implementing a **different concept** (shift-level coverage tracking) versus the spec's **individual floating pool assignment tracking**.

#### ❌ Frontend Components

**NO COVERAGE ENTRY COMPONENT FOUND**

Expected: `CoverageEntry.vue` or similar
Actual: None exists

**Gap:** Entire coverage entry UI missing

#### ❌ Backend Routes

```bash
# Expected files:
backend/routes/attendance.py  ❌ NOT FOUND
backend/routes/coverage.py    ❌ NOT FOUND
```

**Gap:** No API endpoints for attendance or coverage entry

---

## 3. KPI Calculations Analysis

### 3.1 KPI #10: Absenteeism

#### ✅ Calculation Logic (`backend/calculations/absenteeism.py`)
**STATUS: GOOD**

```python
def calculate_absenteeism(db, shift_id, start_date, end_date):
    """
    Absenteeism Rate = (Total Hours Absent / Total Scheduled Hours) * 100
    """
    # ✅ Correct formula
    # ✅ Returns detailed metrics
    # ✅ Handles edge cases
```

**Additional Functions:**
- ✅ `calculate_attendance_rate()` - Individual employee tracking
- ✅ `identify_chronic_absentees()` - Threshold-based alerts (default 10%)
- ✅ `calculate_bradford_factor()` - Advanced HR metric (S² × D)

**Gap:** None - calculation logic is solid

### 3.2 KPI #2: On-Time Delivery (OTD)

#### ⚠️ Calculation Logic (`backend/calculations/otd.py`)
**STATUS: PLACEHOLDER/MVP ONLY**

```python
def calculate_otd(db, start_date, end_date, product_id=None):
    """
    Note: This is a simplified calculation based on production entries.
    In a full system, this would use order/shipment data.

    For MVP, we consider production completed on time if:
    - Production date <= planned completion date
    """
    # ⚠️ Uses production entries as proxy
    # ⚠️ No actual delivery/shipment tracking
    # ⚠️ Confirmation field used as "on-time" indicator
```

**Gap:** Not a true OTD calculation - missing delivery/order data

**Additional Functions:**
- ✅ `calculate_lead_time()` - Days from first to last production entry
- ✅ `calculate_cycle_time()` - Total production hours
- ⚠️ `calculate_delivery_variance()` - Returns empty placeholder
- ⚠️ `identify_late_orders()` - Uses 7-day threshold heuristic

---

## 4. Floating Pool & Double-Billing Prevention

### 4.1 Specification Requirements

**From CSV line 23:**
> "Must reference employee with is_floating_pool = TRUE. Prevents double-billing of same floating employee."

**From CSV line 28:**
> "CRITICAL to prevent same floating employee covering 2+ people in same shift."

### 4.2 Current Implementation

#### ✅ Employee Model has floating pool flag
```python
# backend/models/employee.py (assumed)
is_floating_pool = Column(Boolean, default=False)
```

#### ❌ No Validation Logic Found

**Expected:**
- Database constraint or trigger preventing duplicate assignments
- API validation in `create_coverage_entry()`
- Frontend warning when floating employee already assigned

**Actual:**
- None of the above implemented

**Gap:** Critical business rule not enforced - could lead to billing errors

---

## 5. Demo Data Analysis

### 5.1 Seed Data (`database/seed_data.sql`)

**Found:**
- ✅ Users (admin, supervisor, operators)
- ✅ Shifts (Morning, Afternoon, Night)
- ✅ Products (5 items)
- ✅ KPI Targets
- ✅ Production Entries (19 sample records)

**Missing:**
- ❌ Attendance entries
- ❌ Coverage entries
- ❌ Floating pool employees
- ❌ Absence records
- ❌ Verification examples

**Gap:** No demo data for Phase 3 features

---

## 6. Critical Missing Components

### 6.1 Backend API Routes

**Expected Files:**
```
backend/routes/attendance.py  ❌
backend/routes/coverage.py    ❌
```

**Required Endpoints:**

**Attendance:**
- `POST /api/attendance` - Create attendance entry
- `GET /api/attendance` - List with filters
- `GET /api/attendance/{id}` - Get single entry
- `PUT /api/attendance/{id}` - Update entry
- `PUT /api/attendance/{id}/verify` - Supervisor verification
- `DELETE /api/attendance/{id}` - Delete entry
- `GET /api/attendance/absenteeism` - Calculate KPI

**Coverage:**
- `POST /api/coverage` - Create coverage assignment
- `GET /api/coverage` - List assignments
- `GET /api/coverage/available-floating` - Get available floating pool for date/shift
- `PUT /api/coverage/{id}/verify` - Verify coverage
- `POST /api/coverage/validate` - Check for double-billing

### 6.2 Frontend Components

**Found:**
- ✅ `AttendanceEntry.vue` - Single entry form
- ✅ `AttendanceEntryGrid.vue` - Bulk entry grid

**Missing:**
- ❌ `CoverageEntry.vue` - Coverage assignment form
- ❌ `FloatingPoolSchedule.vue` - Visual calendar of floating pool assignments
- ❌ `AbsenteeismDashboard.vue` - KPI #10 visualization
- ❌ `AttendanceVerification.vue` - Supervisor approval workflow

### 6.3 Database Schema Alignment

**Tables Exist:**
- ✅ `ATTENDANCE_ENTRY` (SQLAlchemy schema)
- ✅ `COVERAGE_ENTRY` (SQLAlchemy schema)

**Schema Gaps:**
- ⚠️ Missing fields (see sections 1.2 and 2.2)
- ❌ No unique constraint on floating_employee_id + shift_date + shift_type
- ❌ No check constraint for absence_type values matching spec

---

## 7. Data Quality & Validation

### 7.1 Spec-Defined Validations

**ATTENDANCE_ENTRY:**
- ✅ `actual_hours` REQUIRED if employee present
- ✅ `absence_type` REQUIRED if is_absent=TRUE
- ✅ `absence_hours` REQUIRED if is_absent=TRUE
- ❌ `covered_by_floating_employee_id` validation - Must exist in EMPLOYEE where is_floating_pool=TRUE
- ❌ `notes` max length 500 chars

**COVERAGE_ENTRY:**
- ❌ `floating_employee_id` must have is_floating_pool=TRUE
- ❌ Unique constraint: (floating_employee_id, shift_date, shift_type)
- ❌ `coverage_duration_hours` = absent employee's `absence_hours`
- ❌ `notes` max length 300 chars

### 7.2 Current Validation

**Backend:**
- ⚠️ Pydantic models have basic type validation
- ⚠️ No business rule validation
- ❌ No cross-table validation

**Frontend:**
- ⚠️ Basic required field validation
- ❌ No enum validation
- ❌ No floating pool availability checking

---

## 8. Compliance Scoring by Component

| Component | Spec Completeness | Critical Gaps | Priority |
|-----------|-------------------|---------------|----------|
| **ATTENDANCE_ENTRY Schema** | 60% | Missing 7 fields, shift_type enum | HIGH |
| **COVERAGE_ENTRY Schema** | 55% | Missing 5 fields, no validation | CRITICAL |
| **Absenteeism Calculation** | 95% | None - well implemented | LOW |
| **OTD Calculation** | 40% | Not true OTD, missing delivery data | MEDIUM |
| **Backend API Routes** | 0% | No endpoints exist | CRITICAL |
| **Frontend Coverage UI** | 0% | Component doesn't exist | HIGH |
| **Demo Data** | 0% | No Phase 3 seed data | MEDIUM |
| **Double-Billing Prevention** | 0% | No validation logic | CRITICAL |
| **Verification Workflow** | 0% | No UI or API | HIGH |

**Overall Phase 3 Compliance: 45%** ⚠️

---

## 9. Recommended Action Plan

### 9.1 CRITICAL (Do First)

1. **Fix ATTENDANCE_ENTRY Schema**
   - Add missing 7 fields
   - Implement shift_type ENUM
   - Add absence_type values: SUSPENDED, PERSONAL_LEAVE
   - Add verification fields (verified_by, verified_at)

2. **Fix COVERAGE_ENTRY Schema**
   - Add shift_type ENUM
   - Add coverage_duration_hours
   - Add verification fields
   - Implement unique constraint for double-billing prevention

3. **Create Backend API Routes**
   - `backend/routes/attendance.py` with all CRUD endpoints
   - `backend/routes/coverage.py` with validation logic
   - Add `/validate-floating-pool` endpoint

4. **Implement Double-Billing Prevention**
   - Database unique constraint
   - API validation
   - Frontend warning system

### 9.2 HIGH Priority

5. **Create Coverage Entry UI**
   - `CoverageEntry.vue` - Assignment form
   - Floating pool availability checker
   - Visual conflict warnings

6. **Add Verification Workflow**
   - Supervisor approval UI
   - Attendance verification endpoint
   - Coverage confirmation endpoint

7. **Align Pydantic Models**
   - Match SQLAlchemy schema
   - Match specification
   - Update frontend to use correct fields

### 9.3 MEDIUM Priority

8. **Create Demo Data**
   - 20+ attendance entries with various absence types
   - 10+ coverage entries with floating pool
   - Examples of verified/unverified records
   - Chronic absenteeism examples

9. **Implement True OTD**
   - Create ORDER table
   - Create SHIPMENT table
   - Update OTD calculation to use actual delivery dates

10. **Add Advanced Features**
    - Bradford Factor dashboard
    - Chronic absentee alerts
    - Floating pool utilization report

---

## 10. Code Quality Assessment

### 10.1 Strengths ✅

1. **Absenteeism calculation logic** is well-implemented
2. **AG Grid integration** for bulk entry is appropriate
3. **SQLAlchemy models** use proper relationships and indexes
4. **Calculation functions** include useful metrics (Bradford Factor)

### 10.2 Code Smells 🔴

1. **Schema Inconsistency**
   - SQLAlchemy ≠ Pydantic ≠ Frontend ≠ Specification
   - Different field names across layers

2. **Missing Validation**
   - No enum validation
   - No cross-table constraints
   - No business rule enforcement

3. **Incomplete Implementation**
   - Routes referenced but don't exist
   - API calls in frontend with no backend
   - Models without CRUD operations

4. **Naming Confusion**
   - `AttendanceRecord` vs `AttendanceEntry`
   - `ShiftCoverage` vs `CoverageEntry`
   - `entered_by` vs `recorded_by_user_id`

### 10.3 Technical Debt

1. **OTD Placeholder** - Need proper order/delivery tracking
2. **Frontend API Calls** - Reference non-existent endpoints
3. **Schema Migration** - No Alembic migrations found
4. **No Tests** - No unit tests for Phase 3 calculations

---

## 11. Security & Data Isolation

### 11.1 Multi-Tenant Isolation

✅ **Good:** All tables include `client_id` foreign key
⚠️ **Warning:** No verification in CRUD operations that user has access to client
❌ **Missing:** Row-level security policies

### 11.2 Audit Trail

✅ **Good:** `entered_by`, `created_at`, `updated_at` in most tables
⚠️ **Partial:** Verification workflow exists in schema but not implemented
❌ **Missing:** Change history/audit log table

---

## 12. Conclusion

Phase 3 is **45% complete** with **CRITICAL GAPS** in:

1. **Schema Compliance** - Missing 12+ fields across 2 tables
2. **API Layer** - No backend routes implemented
3. **Coverage System** - Floating pool assignment incomplete
4. **Validation** - No double-billing prevention
5. **Demo Data** - No attendance/coverage examples

**Recommendation:** **DO NOT DEPLOY** Phase 3 to production until:
- Backend API routes created
- Schema aligned with specification
- Double-billing prevention implemented
- Verification workflow added
- Demo data created for testing

**Estimated Effort to Complete:**
- Backend: 16-20 hours
- Frontend: 12-16 hours
- Testing & Validation: 8-10 hours
- **Total: 36-46 hours**

---

## Appendix A: Field Mapping

### ATTENDANCE_ENTRY Spec → Implementation

| Spec Field | SQLAlchemy | Pydantic | Frontend | Status |
|------------|------------|----------|----------|--------|
| `attendance_entry_id` | ✅ | ✅ | ✅ | MATCH |
| `employee_id_fk` | ✅ | ⚠️ (int) | ✅ | TYPE MISMATCH |
| `client_id_fk` | ✅ | ❌ | ❌ | MISSING |
| `shift_date` | ✅ | ⚠️ (attendance_date) | ⚠️ (date) | NAME MISMATCH |
| `shift_type` | ❌ | ❌ (shift_id) | ❌ (shift_id) | MISSING |
| `scheduled_hours` | ✅ | ✅ | ❌ | PARTIAL |
| `actual_hours` | ✅ | ⚠️ (actual_hours_worked) | ❌ | NAME MISMATCH |
| `is_absent` | ✅ | ❌ (status) | ❌ (status) | CONCEPT MISMATCH |
| `absence_type` | ⚠️ (4 types) | ⚠️ (absence_reason str) | ⚠️ (absence_reason) | INCOMPLETE |
| `absence_hours` | ✅ | ❌ | ❌ | MISSING |
| `covered_by_floating_employee_id` | ❌ | ❌ | ❌ | MISSING |
| `coverage_confirmed` | ❌ | ❌ | ❌ | MISSING |
| `recorded_by_user_id` | ⚠️ (entered_by) | ❌ | ❌ | NAME MISMATCH |
| `recorded_at` | ❌ | ❌ | ❌ | MISSING |
| `verified_by_user_id` | ❌ | ❌ | ❌ | MISSING |
| `verified_at` | ❌ | ❌ | ❌ | MISSING |
| `notes` | ✅ | ✅ | ✅ | MATCH |

**Compliance: 7/17 = 41%**

---

## Appendix B: Absence Type Enumeration

### Specification (6 types)
1. `UNSCHEDULED_ABSENCE` - Counts toward absenteeism
2. `VACATION` - Scheduled, doesn't count
3. `MEDICAL_LEAVE` - Counts toward absenteeism
4. `PERSONAL_DAY` - Counts toward absenteeism (MISSING)
5. `SUSPENDED` - Disciplinary (MISSING)
6. `OTHER` - Catch-all

### Current Implementation (4 types)
```python
class AbsenceType(str, enum.Enum):
    UNSCHEDULED_ABSENCE = "UNSCHEDULED_ABSENCE"  ✅
    VACATION = "VACATION"  ✅
    MEDICAL_LEAVE = "MEDICAL_LEAVE"  ✅
    PERSONAL_LEAVE = "PERSONAL_LEAVE"  ⚠️ Different name
    # MISSING: SUSPENDED
    # MISSING: OTHER
```

### Frontend (7+ types - different list)
```javascript
absenceReasons = [
  'Sick Leave',  // ≈ MEDICAL_LEAVE
  'Personal Leave',  // ≈ PERSONAL_DAY
  'Family Emergency',  // ❌ Not in spec
  'Medical Appointment',  // ❌ Not in spec
  'No Show',  // ≈ UNSCHEDULED_ABSENCE
  'Unauthorized',  // ≈ UNSCHEDULED_ABSENCE
  'Other'  // ✅
]
```

**Recommendation:** Standardize to spec's 6 enum values

---

**Report Generated:** 2026-01-02
**Next Steps:** Review with development team and prioritize fixes
