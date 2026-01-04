# 🚀 Migration Deployment Checklist

## Pre-Deployment (1 hour before)

### 1. Environment Verification
- [ ] Verify database backup directory exists: `mkdir -p database/backups`
- [ ] Check database file permissions: `ls -lh database/kpi_platform.db`
- [ ] Verify SQLite version: `sqlite3 --version` (must be 3.0+)
- [ ] Check disk space: `df -h .` (need at least 500MB free)

### 2. Code Preparation
- [ ] Pull latest code from repository
- [ ] Verify migration scripts exist:
  - [ ] `002_phase2_schema_fix.sql`
  - [ ] `003_phase3_schema_fix.sql`
  - [ ] `004_phase4_schema_fix.sql`
- [ ] Verify Python scripts executable: `chmod +x run_migrations.py test_migrations.py`

### 3. Communication
- [ ] Notify users of maintenance window
- [ ] Schedule deployment time (recommend off-hours)
- [ ] Prepare rollback contact list

---

## Deployment (30-45 minutes)

### Step 1: Create Backup (5 min)
```bash
cd database/migrations
python3 run_migrations.py
```

**Expected Output:**
```
📦 Creating backup: database/backups/kpi_platform_pre_migration_YYYYMMDD_HHMMSS.db
   ✓ Backup created successfully
```

- [ ] Backup created successfully
- [ ] Verify backup size matches original

### Step 2: Run Migrations (15-20 min)
**Automatic (Recommended):**
```bash
python3 run_migrations.py
```

**Manual (if automatic fails):**
```bash
sqlite3 ../kpi_platform.db < 002_phase2_schema_fix.sql
sqlite3 ../kpi_platform.db < 003_phase3_schema_fix.sql
sqlite3 ../kpi_platform.db < 004_phase4_schema_fix.sql
```

- [ ] Migration 002 completed (Phase 2)
- [ ] Migration 003 completed (Phase 3)
- [ ] Migration 004 completed (Phase 4)
- [ ] No errors reported

### Step 3: Validate Schema (10 min)
```bash
python3 test_migrations.py
```

**Expected Output:**
```
✅ ALL TESTS PASSED - Migration successful!
```

- [ ] All table tests passed
- [ ] All column tests passed
- [ ] All index tests passed
- [ ] All view tests passed
- [ ] Data integrity tests passed

### Step 4: Smoke Tests (10 min)
Run these queries manually:

```sql
-- Test DOWNTIME_ENTRY
SELECT COUNT(*) as total,
       SUM(CASE WHEN is_resolved IS NOT NULL THEN 1 ELSE 0 END) as has_resolution
FROM DOWNTIME_ENTRY;

-- Test ATTENDANCE_ENTRY
SELECT COUNT(*) as total,
       SUM(CASE WHEN shift_type IN ('REGULAR','OVERTIME','WEEKEND') THEN 1 ELSE 0 END) as has_shift_type
FROM ATTENDANCE_ENTRY;

-- Test QUALITY_ENTRY
SELECT COUNT(*) as total,
       SUM(CASE WHEN approved_by IS NOT NULL THEN 1 ELSE 0 END) as has_approval
FROM QUALITY_ENTRY;
```

- [ ] DOWNTIME_ENTRY query successful
- [ ] ATTENDANCE_ENTRY query successful
- [ ] QUALITY_ENTRY query successful
- [ ] All record counts match expectations

---

## Post-Deployment (1 hour)

### Step 5: Application Testing
- [ ] Restart backend server
- [ ] Test Phase 2 endpoints (downtime, holds)
- [ ] Test Phase 3 endpoints (attendance, coverage)
- [ ] Test Phase 4 endpoints (quality, defects)
- [ ] Verify KPI calculations working

### Step 6: Documentation
- [ ] Update deployment log with timestamp
- [ ] Record any issues encountered
- [ ] Document configuration changes
- [ ] Update README if needed

### Step 7: Monitoring
- [ ] Monitor error logs for 24 hours
- [ ] Check database performance
- [ ] Verify user reports
- [ ] Confirm KPI calculations accurate

---

## Rollback Procedure (if needed)

### Signs You Need to Rollback:
- ❌ Migration script fails with errors
- ❌ Data integrity tests fail
- ❌ Application cannot connect to database
- ❌ Critical functionality broken

### Rollback Steps:
```bash
# 1. Stop application
systemctl stop kpi-backend  # or equivalent

# 2. Restore backup
cp database/backups/kpi_platform_pre_migration_YYYYMMDD_HHMMSS.db database/kpi_platform.db

# 3. Verify restoration
sqlite3 database/kpi_platform.db "SELECT COUNT(*) FROM DOWNTIME_ENTRY;"

# 4. Restart application
systemctl start kpi-backend
```

- [ ] Application stopped
- [ ] Backup restored
- [ ] Database verified working
- [ ] Application restarted
- [ ] Users notified

---

## Success Criteria

✅ **Migration Successful** if:
- All migrations completed without errors
- All validation tests pass
- Application connects to database
- KPI calculations work correctly
- No data loss
- Performance acceptable

❌ **Rollback Required** if:
- Any migration fails
- Validation tests fail
- Data corruption detected
- Application unable to start
- Critical errors in logs

---

## Contact Information

**Database Administrator:** ___________________
**Phone:** ___________________
**Email:** ___________________

**Backup Contact:** ___________________
**Phone:** ___________________

**On-Call Schedule:** ___________________

---

## Deployment Log

**Date:** ___________________
**Time Started:** ___________________
**Time Completed:** ___________________
**Deployed By:** ___________________
**Status:** [ ] Success  [ ] Rollback  [ ] Partial

**Notes:**
___________________________________________________________________
___________________________________________________________________
___________________________________________________________________

**Signatures:**
- Deployed By: ___________________ Date: ___________
- Verified By: ___________________ Date: ___________
- Approved By: ___________________ Date: ___________
