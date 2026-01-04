# Database Migrations - Phase 2-4 Schema Fixes

This directory contains SQL migration scripts to add 40+ missing fields across Phase 2, 3, and 4 tables.

## 📋 Migration Overview

| Migration | Description | Fields Added | Impact |
|-----------|-------------|--------------|--------|
| `002_phase2_schema_fix.sql` | Downtime & WIP schema fixes | 9 fields | Schema consolidation + approval workflow |
| `003_phase3_schema_fix.sql` | Attendance & Coverage schema fixes | 14 fields | Floating pool + verification workflow |
| `004_phase4_schema_fix.sql` | Quality & Defects schema fixes | 17 fields | Disposition tracking + approval workflow |
| **Total** | | **40 fields** | Production-ready schema |

## 🚀 Quick Start

### Option 1: Automated Migration Runner (Recommended)

```bash
# Navigate to database directory
cd database/migrations

# Make script executable
chmod +x run_migrations.py

# Run all migrations (creates backup automatically)
python3 run_migrations.py
```

### Option 2: Manual Migration

```bash
# Create backup first!
cp database/kpi_platform.db database/backups/kpi_platform_backup_$(date +%Y%m%d_%H%M%S).db

# Run migrations in order
sqlite3 database/kpi_platform.db < database/migrations/002_phase2_schema_fix.sql
sqlite3 database/kpi_platform.db < database/migrations/003_phase3_schema_fix.sql
sqlite3 database/kpi_platform.db < database/migrations/004_phase4_schema_fix.sql
```

## 📊 Migration Details

### Migration 002: Phase 2 Schema Fix

**Tables Modified:**
- `DOWNTIME_ENTRY` - 6 new fields
- `HOLD_ENTRY` - 3 new fields

**Key Changes:**
- Adds resolution tracking (`is_resolved`, `resolution_notes`)
- Adds WIP impact calculation (`impact_on_wip_hours`)
- Adds approval workflow (`hold_approved_at`, `resume_approved_at`)
- Creates views for active downtime and holds
- Migrates data from old `downtime_events` table (if exists)

**Estimated Time:** 10-15 minutes

### Migration 003: Phase 3 Schema Fix

**Tables Modified:**
- `ATTENDANCE_ENTRY` - 9 new fields
- `SHIFT_COVERAGE` - 5 new fields

**Key Changes:**
- Adds shift type classification (`shift_type` ENUM)
- Adds floating pool coverage tracking
- Adds supervisor verification workflow
- Adds excused/unexcused absence tracking
- Creates absenteeism summary views

**Estimated Time:** 8-12 minutes

### Migration 004: Phase 4 Schema Fix

**Tables Modified:**
- `QUALITY_ENTRY` - 12 new fields
- `DEFECT_DETAIL` - 5 new fields

**Key Changes:**
- Adds sampling details (`sample_size_percent`, `inspection_level`)
- Adds disposition tracking (`units_requiring_repair`, `units_requiring_rework`)
- Adds approval workflow (`approved_by`, `approved_at`)
- Adds defect traceability (`unit_serial_or_id`, `root_cause`)
- Creates PPM, DPMO, FPY views

**Estimated Time:** 10-15 minutes

## ✅ Validation

After running migrations, verify schema changes:

```sql
-- Check DOWNTIME_ENTRY new fields
PRAGMA table_info(DOWNTIME_ENTRY);

-- Check ATTENDANCE_ENTRY new fields
PRAGMA table_info(ATTENDANCE_ENTRY);

-- Check QUALITY_ENTRY new fields
PRAGMA table_info(QUALITY_ENTRY);

-- Verify data integrity
SELECT COUNT(*) FROM DOWNTIME_ENTRY WHERE is_resolved IS NOT NULL;
SELECT COUNT(*) FROM ATTENDANCE_ENTRY WHERE shift_type IS NOT NULL;
SELECT COUNT(*) FROM QUALITY_ENTRY WHERE shift_type IS NOT NULL;
```

## 🔄 Rollback Instructions

If migration fails or needs to be reverted:

```bash
# Restore from backup
cp database/backups/kpi_platform_pre_migration_YYYYMMDD_HHMMSS.db database/kpi_platform.db

# Or use SQLite rollback (if within transaction)
# Each migration file uses BEGIN TRANSACTION / COMMIT
# Simply don't COMMIT if errors occur
```

## 📝 Post-Migration Tasks

After successful migration:

### 1. Update Pydantic Models (Backend)

**Files to update:**
- `/backend/models/downtime.py` - Add 6 fields
- `/backend/models/hold.py` - Add 3 fields
- `/backend/models/attendance.py` - Add 9 fields
- `/backend/models/coverage.py` - Add 5 fields
- `/backend/models/quality.py` - Add 12 fields
- `/backend/models/defect_detail.py` - Add 5 fields

### 2. Update API Routes

**Files to update:**
- `/backend/routes/downtime.py` - Handle new fields
- `/backend/routes/hold.py` - Handle approval workflow
- `/backend/routes/attendance.py` - Handle verification workflow
- `/backend/routes/quality.py` - Handle disposition tracking

### 3. Update Frontend Components

**Files to update:**
- `/frontend/src/components/DowntimeEntryGrid.vue` - Add resolution columns
- `/frontend/src/components/HoldEntryGrid.vue` - Add approval columns
- `/frontend/src/components/AttendanceEntryGrid.vue` - Add verification columns
- `/frontend/src/components/QualityEntryGrid.vue` - Add disposition columns

### 4. Test KPI Calculations

Verify that KPI calculations still work correctly with new schema:
- Availability (uses `is_resolved` flag)
- Absenteeism (uses `is_excused_absence` flag)
- PPM/DPMO (uses disposition flags)
- FPY (uses `units_requiring_rework`)

## 🚨 Important Notes

1. **Backup Required:** Always create a backup before running migrations
2. **Downtime:** Migrations should be run during maintenance window
3. **Foreign Keys:** All migrations preserve existing foreign key constraints
4. **Data Integrity:** Existing data is preserved; new fields have sensible defaults
5. **Indexes:** Performance indexes are automatically created
6. **Views:** Reporting views are created for common queries

## 📚 Schema Reference

### Phase 2 New Fields

**DOWNTIME_ENTRY:**
```sql
downtime_start_time TIMESTAMP        -- When downtime began
is_resolved BOOLEAN                  -- Resolution status
resolution_notes TEXT                -- Resolution documentation
impact_on_wip_hours DECIMAL(10,2)   -- WIP impact calculation
created_by VARCHAR(20)               -- Audit trail
```

**HOLD_ENTRY:**
```sql
hold_approved_at TIMESTAMP           -- Hold approval timestamp
resume_approved_at TIMESTAMP         -- Resume approval timestamp
created_by VARCHAR(20)               -- Audit trail
```

### Phase 3 New Fields

**ATTENDANCE_ENTRY:**
```sql
shift_type VARCHAR(20)                      -- REGULAR, OVERTIME, WEEKEND
covered_by_floating_employee_id VARCHAR(20) -- Floating pool assignment
coverage_confirmed BOOLEAN                  -- Coverage verification
verified_by_user_id VARCHAR(20)             -- Supervisor verification
verified_at TIMESTAMP                       -- Verification timestamp
is_excused_absence BOOLEAN                  -- Excused vs unexcused
created_by VARCHAR(20)                      -- Audit trail
updated_by VARCHAR(20)                      -- Last modifier
```

**SHIFT_COVERAGE:**
```sql
shift_type VARCHAR(20)              -- REGULAR, OVERTIME, WEEKEND
coverage_duration_hours DECIMAL(5,2) -- Total hours covered
recorded_by_user_id VARCHAR(20)     -- Recorder
verified BOOLEAN                    -- Verification status
created_by VARCHAR(20)              -- Audit trail
updated_by VARCHAR(20)              -- Last modifier
```

### Phase 4 New Fields

**QUALITY_ENTRY:**
```sql
shift_type VARCHAR(20)              -- REGULAR, OVERTIME, WEEKEND
operation_checked VARCHAR(100)      -- Operation inspected
units_requiring_repair INT          -- Repair disposition
units_requiring_rework INT          -- Rework disposition
recorded_by_user_id VARCHAR(20)     -- Inspector
recorded_at TIMESTAMP               -- Recording timestamp
sample_size_percent DECIMAL(5,2)    -- Sampling percentage
inspection_level VARCHAR(20)        -- AQL level (I, II, III)
approved_by VARCHAR(20)             -- Quality manager
approved_at TIMESTAMP               -- Approval timestamp
created_by VARCHAR(20)              -- Audit trail
updated_by VARCHAR(20)              -- Last modifier
```

**DEFECT_DETAIL:**
```sql
is_rework_required BOOLEAN          -- Rework flag
is_repair_in_current_op BOOLEAN     -- Repair location
is_scrapped BOOLEAN                 -- Scrap flag
root_cause TEXT                     -- Root cause analysis
unit_serial_or_id VARCHAR(100)      -- Unit traceability
```

## 🎯 Success Criteria

✅ All 40+ fields added to database
✅ No data loss during migration
✅ All foreign keys intact
✅ Indexes created for performance
✅ Views created for reporting
✅ Validation queries pass
✅ Backup created successfully

## 📞 Support

For issues or questions:
1. Check validation queries
2. Review migration logs
3. Restore from backup if needed
4. Contact database administrator

---

**Last Updated:** January 2, 2026
**Migration Version:** 1.0.0
