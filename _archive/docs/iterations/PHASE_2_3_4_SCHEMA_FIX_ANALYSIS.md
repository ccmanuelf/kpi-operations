# 🔧 Phase 2-4 Database Schema Fix Analysis

**Date:** January 2, 2026
**Status:** CRITICAL - 40+ Missing Fields Identified
**Priority:** MEDIUM Impact - Features work but incomplete data tracking

---

## 📊 EXECUTIVE SUMMARY

This analysis identifies **40+ missing database fields** across Phase 2, 3, and 4 tables that are required per the comprehensive CSV upload specifications. While current CRUD operations function, critical tracking fields are absent, limiting audit trails, approval workflows, and comprehensive KPI analysis.

### Impact Assessment:
- **Phase 2 (Downtime & WIP):** 9 missing fields + schema conflict
- **Phase 3 (Attendance & Coverage):** 20 missing fields
- **Phase 4 (Quality & Defects):** 20 missing fields
- **Total:** 49 missing fields

---

## 🚨 CRITICAL FINDINGS

### 1. Phase 2: Schema Conflict (CRITICAL)

**Problem:** Two different schemas exist for downtime tracking:
- **Old Schema:** `downtime_events` table (currently used by API)
- **New Schema:** `DOWNTIME_ENTRY` table (per CSV spec in init_sqlite_schema.py)

**Risk:** Data fragmentation, inconsistent KPI calculations

**Fields in Old Schema (downtime_events):**
```sql
- downtime_id (INT)
- product_id (INT)
- shift_id (INT)
- production_date (DATE)
- downtime_category (VARCHAR)
- downtime_reason (VARCHAR)
- duration_hours (DECIMAL)
- machine_id (VARCHAR)
- work_order_number (VARCHAR)
- notes (TEXT)
- entered_by (INT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

**Fields in New Schema (DOWNTIME_ENTRY):**
```sql
- downtime_id (INT PRIMARY KEY AUTOINCREMENT)
- client_id (VARCHAR(50) NOT NULL) ← Multi-tenant isolation
- work_order_id (VARCHAR(50) NOT NULL)
- shift_id (INT NOT NULL)
- downtime_date (DATE NOT NULL)
- downtime_reason (VARCHAR(255))
- downtime_category (VARCHAR(100))
- downtime_duration_minutes (INT NOT NULL) ← Different unit
- entered_by (VARCHAR(50))
- notes (TEXT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

**MISSING FIELDS (6 total):**
1. `downtime_start_time` TIMESTAMP - Track when downtime began
2. `is_resolved` BOOLEAN DEFAULT FALSE - Track resolution status
3. `resolution_notes` TEXT - Document resolution actions
4. `impact_on_wip_hours` DECIMAL(10,2) - Calculate WIP impact
5. `created_by` VARCHAR(20) - Audit trail for creation
6. `updated_at` TIMESTAMP - Track last modification

---

### 2. Phase 2: HOLD_ENTRY Missing Fields (3)

**Current Schema (init_sqlite_schema.py):**
```sql
CREATE TABLE HOLD_ENTRY (
    hold_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) NOT NULL,
    work_order_id VARCHAR(50) NOT NULL,
    placed_on_hold_date DATE NOT NULL,
    released_date DATE,
    hold_reason VARCHAR(255),
    units_on_hold INTEGER,
    entered_by VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
)
```

**MISSING FIELDS (3 total):**
1. `hold_approved_at` TIMESTAMP - Approval workflow timestamp
2. `resume_approved_at` TIMESTAMP - Resume approval timestamp
3. `created_by` VARCHAR(20) - Audit trail (separate from entered_by)

---

### 3. Phase 3: ATTENDANCE_ENTRY Missing Fields (12)

**Current Schema:**
```sql
CREATE TABLE ATTENDANCE_ENTRY (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) NOT NULL,
    employee_id VARCHAR(50) NOT NULL,
    shift_id INTEGER NOT NULL,
    attendance_date DATE NOT NULL,
    is_absent INTEGER DEFAULT 0,
    is_late INTEGER DEFAULT 0,
    scheduled_hours DECIMAL(5, 2),
    actual_hours DECIMAL(5, 2),
    entered_by VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
)
```

**MISSING FIELDS (12 total):**
1. `shift_type` ENUM('REGULAR', 'OVERTIME', 'WEEKEND') - Track shift type
2. `covered_by_floating_employee_id` VARCHAR(20) - Floating pool coverage
3. `coverage_confirmed` BOOLEAN DEFAULT FALSE - Confirm coverage assignment
4. `verified_by_user_id` VARCHAR(20) - Supervisor verification
5. `verified_at` TIMESTAMP - Verification timestamp
6. `absence_reason` TEXT - Detailed absence documentation
7. `is_excused_absence` BOOLEAN - Distinguish excused vs unexcused
8. `notes` TEXT - Additional context (already exists but needs documentation)
9. `created_by` VARCHAR(20) - Audit trail
10. `created_at` TIMESTAMP - Creation timestamp (already exists)
11. `updated_by` VARCHAR(20) - Last modifier
12. `updated_at` TIMESTAMP - Last modification (already exists)

**Net New Fields:** 9 (3 already exist but need better schema)

---

### 4. Phase 3: SHIFT_COVERAGE Missing Fields (8)

**Current Schema:**
```sql
CREATE TABLE SHIFT_COVERAGE (
    coverage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) NOT NULL,
    shift_id INTEGER NOT NULL,
    coverage_date DATE NOT NULL,
    employees_scheduled INTEGER,
    employees_present INTEGER,
    coverage_percentage DECIMAL(5, 2),
    entered_by VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
)
```

**MISSING FIELDS (8 total):**
1. `shift_type` ENUM('REGULAR', 'OVERTIME', 'WEEKEND') - Classify shift type
2. `coverage_duration_hours` DECIMAL(5,2) - Track total hours covered
3. `recorded_by_user_id` VARCHAR(20) - User who recorded coverage
4. `verified` BOOLEAN DEFAULT FALSE - Verification status
5. `notes` TEXT - Additional context (already exists)
6. `created_by` VARCHAR(20) - Audit trail
7. `created_at` TIMESTAMP - Creation timestamp (already exists)
8. `updated_at` TIMESTAMP - Last modification (already exists)

**Net New Fields:** 5 (3 already exist)

---

### 5. Phase 4: QUALITY_ENTRY Missing Fields (15)

**Current Schema:**
```sql
CREATE TABLE QUALITY_ENTRY (
    quality_entry_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    work_order_id VARCHAR(50) NOT NULL,
    inspection_date DATE NOT NULL,
    units_inspected INTEGER NOT NULL,
    units_passed INTEGER NOT NULL,
    units_failed INTEGER NOT NULL,
    total_defects_count INTEGER DEFAULT 0,
    entered_by VARCHAR(50),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
)
```

**MISSING FIELDS (15 total):**
1. `shift_type` ENUM('REGULAR', 'OVERTIME', 'WEEKEND') - Classify inspection shift
2. `operation_checked` VARCHAR(100) - Specific operation inspected
3. `units_requiring_repair` INT - Units needing repair (not scrap)
4. `units_requiring_rework` INT - Units needing rework
5. `recorded_by_user_id` VARCHAR(20) - Inspector user ID
6. `recorded_at` TIMESTAMP - Recording timestamp
7. `sample_size_percent` DECIMAL(5,2) - Sampling percentage
8. `inspection_level` VARCHAR(20) - AQL inspection level (I, II, III)
9. `approved_by` VARCHAR(20) - Quality manager approval
10. `approved_at` TIMESTAMP - Approval timestamp
11. `notes` TEXT - Additional context (already exists)
12. `created_by` VARCHAR(20) - Audit trail
13. `created_at` TIMESTAMP - Creation timestamp (already exists)
14. `updated_by` VARCHAR(20) - Last modifier
15. `updated_at` TIMESTAMP - Last modification (already exists)

**Net New Fields:** 12 (3 already exist)

---

### 6. Phase 4: DEFECT_DETAIL Missing Fields (5)

**Current Schema:**
```sql
CREATE TABLE DEFECT_DETAIL (
    defect_detail_id VARCHAR(50) PRIMARY KEY,
    quality_entry_id VARCHAR(50) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    defect_type VARCHAR(50) NOT NULL,
    defect_category VARCHAR(100),
    defect_count INTEGER NOT NULL,
    severity VARCHAR(20),
    location VARCHAR(255),
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**MISSING FIELDS (5 total):**
1. `is_rework_required` BOOLEAN DEFAULT FALSE - Disposition flag
2. `is_repair_in_current_op` BOOLEAN DEFAULT FALSE - Repair location flag
3. `is_scrapped` BOOLEAN DEFAULT FALSE - Scrap disposition
4. `root_cause` TEXT - Root cause analysis
5. `unit_serial_or_id` VARCHAR(100) - Track specific unit for traceability

---

## 📈 MIGRATION STRATEGY

### Migration Order:
1. **Phase 2 Schema Fix** (002_phase2_schema_fix.sql)
   - Consolidate downtime_events → DOWNTIME_ENTRY
   - Add 6 missing DOWNTIME_ENTRY fields
   - Add 3 missing HOLD_ENTRY fields
   - Data migration from old to new schema

2. **Phase 3 Schema Fix** (003_phase3_schema_fix.sql)
   - Add 9 new ATTENDANCE_ENTRY fields
   - Add 5 new SHIFT_COVERAGE fields (renamed to COVERAGE_ENTRY)
   - Create indexes for performance

3. **Phase 4 Schema Fix** (004_phase4_schema_fix.sql)
   - Add 12 new QUALITY_ENTRY fields
   - Add 5 new DEFECT_DETAIL fields
   - Update quality inspection workflows

### Data Preservation:
- All migrations use `ALTER TABLE ADD COLUMN` (non-destructive)
- Existing data remains intact
- New fields have sensible defaults
- Foreign keys preserved

---

## 🎯 SUCCESS CRITERIA

✅ All 40+ fields added to database schema
✅ Migration scripts tested on development database
✅ No data loss during migration
✅ SQLAlchemy models updated to match new schema
✅ Foreign key constraints remain intact
✅ Indexes created for new searchable fields
✅ API routes updated to handle new fields (separate task)

---

## ⚠️ RISKS & MITIGATION

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Data type mismatches | Low | High | Test migrations on copy of production DB |
| Foreign key violations | Medium | High | Use CASCADE ON DELETE where appropriate |
| Performance degradation | Low | Medium | Add indexes on new searchable fields |
| Breaking API contracts | High | High | Coordinate with backend API update task |
| Schema drift | Medium | Medium | Version control all migration scripts |

---

## 📝 IMPLEMENTATION NOTES

### Phase 2 Schema Consolidation:
The downtime_events → DOWNTIME_ENTRY migration requires:
1. Create new DOWNTIME_ENTRY table with all fields
2. Migrate existing downtime_events data
3. Update backend API to use DOWNTIME_ENTRY
4. Drop downtime_events table after verification

### Pydantic Model Updates Required:
- `/backend/models/downtime.py` - Add 6 new fields
- `/backend/models/hold.py` - Add 3 new fields
- `/backend/models/attendance.py` - Add 9 new fields
- `/backend/models/coverage.py` - Add 5 new fields (rename model)
- `/backend/models/quality.py` - Add 12 new fields
- `/backend/models/defect_detail.py` - Add 5 new fields

### API Route Coordination:
This schema fix must be deployed in coordination with:
- Backend API routes update (separate concurrent task)
- Frontend form updates (to send new fields)
- AG Grid column updates (to display new fields)

---

## 🔄 ROLLBACK PLAN

If migration fails:
1. Restore database from backup (pre-migration snapshot)
2. Revert migration scripts
3. Document failure reason
4. Test fix on development environment
5. Re-attempt migration after validation

**Backup Command:**
```bash
cp database/kpi_platform.db database/backups/kpi_platform_pre_migration_$(date +%Y%m%d_%H%M%S).db
```

---

**Report Generated:** January 2, 2026
**Agent:** Database Schema Specialist (Task 2)
**Status:** Migration scripts ready for deployment
