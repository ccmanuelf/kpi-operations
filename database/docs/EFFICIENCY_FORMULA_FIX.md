# Efficiency Formula Correction

## Issue Identified
The efficiency calculation was incorrectly using `run_time_hours` (actual machine runtime) instead of `scheduled_hours` (planned shift time) in the denominator.

## Problem

**Incorrect Formula (Before Fix):**
```sql
efficiency = (units_produced × ideal_cycle_time) / (employees_assigned × run_time_hours)
```

**Issue:** This formula measures machine productivity during actual operation, not workforce efficiency during scheduled time.

## Solution

**Correct Formula (After Fix):**
```sql
efficiency = (units_produced × ideal_cycle_time) / (employees_assigned × scheduled_hours)
```

**Key Change:** Now uses scheduled shift hours calculated from `shift.start_time` and `shift.end_time`.

## Technical Changes

### 1. SQL Stored Procedure (`schema.sql`)

**File:** `/database/schema.sql`
**Procedure:** `sp_calculate_efficiency`

#### Changes Made:
- Added variables for shift times:
  - `v_shift_start TIME`
  - `v_shift_end TIME`
  - `v_shift_hours DECIMAL(8,2)` (replaces `v_runtime`)

- Modified JOIN to include shift table:
  ```sql
  JOIN shift s ON pe.shift_id = s.shift_id
  ```

- Added shift hours calculation:
  ```sql
  -- Calculate SCHEDULED shift hours from start/end times
  IF v_shift_end >= v_shift_start THEN
    SET v_shift_hours = TIME_TO_SEC(TIMEDIFF(v_shift_end, v_shift_start)) / 3600;
  ELSE
    -- Handle overnight shifts
    SET v_shift_hours = (TIME_TO_SEC(TIMEDIFF(v_shift_end, v_shift_start)) + 86400) / 3600;
  END IF;
  ```

- Updated formula to use `v_shift_hours` instead of `v_runtime`

### 2. Python Backend Module

**File:** `/backend/calculations/efficiency.py`

Created new Python module with:

#### Key Functions:

1. **`calculate_shift_hours(shift_start, shift_end)`**
   - Calculates scheduled hours from shift times
   - Handles overnight shifts correctly
   - Returns duration in hours (e.g., 8.0 for 8-hour shift)

2. **`calculate_efficiency(units, cycle_time, employees, shift_hours)`**
   - Pure calculation function
   - Uses SCHEDULED hours (not runtime)
   - Returns percentage by default
   - Includes validation

3. **`calculate_efficiency_from_db(db, entry_id)`**
   - Database integration
   - Fetches data from ProductionEntry, Product, and Shift tables
   - Calculates shift hours from shift definition
   - Returns efficiency percentage

4. **`update_efficiency_in_db(db, entry_id)`**
   - Updates production_entry.efficiency_percentage
   - Commits changes to database

## Formula Explanation

### Efficiency vs Performance

**Efficiency (KPI #3):** Measures workforce utilization during SCHEDULED time
```
Efficiency = (Units × Cycle Time) / (Employees × SCHEDULED Hours) × 100
```

**Performance (KPI #9):** Measures machine speed during ACTUAL runtime
```
Performance = (Units × Cycle Time) / RUNTIME Hours × 100
```

### Why This Matters

**Scenario:** 8-hour shift, 5 employees, 1000 units, 0.01 hr/unit cycle time

**Option 1: 6 hours runtime (machine stopped 2 hours)**
- Efficiency = (1000 × 0.01) / (5 × 8) = 25% ✅ (uses scheduled 8 hours)
- Performance = (1000 × 0.01) / 6 = 166.7% (machine ran fast when operating)

**Option 2: 8 hours runtime (no downtime)**
- Efficiency = (1000 × 0.01) / (5 × 8) = 25% ✅ (same efficiency)
- Performance = (1000 × 0.01) / 8 = 125% (slower but no downtime)

The old formula would have shown:
- Option 1: 16.7% efficiency (WRONG - penalized for downtime twice)
- Option 2: 12.5% efficiency (WRONG - different value for same workforce utilization)

## Testing

### SQL Testing
```sql
-- Insert test shift
INSERT INTO shift (shift_name, start_time, end_time)
VALUES ('Day Shift', '07:00:00', '15:00:00');

-- Insert test production entry
INSERT INTO production_entry (
  product_id, shift_id, production_date,
  units_produced, run_time_hours, employees_assigned
) VALUES (1, 1, '2024-01-15', 1000, 6.0, 5);

-- Check efficiency (should be based on 8 scheduled hours, not 6 runtime)
SELECT efficiency_percentage FROM production_entry WHERE entry_id = LAST_INSERT_ID();
-- Expected: 25.0 (using 8 scheduled hours)
-- Old formula would give: 33.3 (using 6 runtime hours)
```

### Python Testing
```python
from backend.calculations.efficiency import calculate_efficiency, calculate_shift_hours

# Test shift hours calculation
assert calculate_shift_hours("07:00:00", "15:00:00") == 8.0
assert calculate_shift_hours("22:00:00", "06:00:00") == 8.0  # Overnight

# Test efficiency calculation
efficiency = calculate_efficiency(
    units_produced=1000,
    ideal_cycle_time=0.01,
    employees_assigned=5,
    shift_hours=8.0  # SCHEDULED, not runtime
)
assert efficiency == 25.0  # 25% efficiency
```

## Files Modified

1. **`schema.sql`** - Updated `sp_calculate_efficiency` stored procedure
2. **`backend/calculations/__init__.py`** - Created module init
3. **`backend/calculations/efficiency.py`** - Created efficiency calculation module
4. **`backend/calculations/performance.py`** - Created performance calculation module (for reference)

## Migration Steps

To apply this fix to an existing database:

1. **Drop and recreate the stored procedure:**
   ```sql
   DROP PROCEDURE IF EXISTS sp_calculate_efficiency;
   -- Then run the updated CREATE PROCEDURE from schema.sql
   ```

2. **Recalculate existing efficiency values:**
   ```sql
   -- Recalculate all production entries
   UPDATE production_entry
   SET efficiency_percentage = NULL;  -- Clear old values

   -- Trigger will recalculate automatically, or manually call:
   CALL sp_calculate_efficiency(entry_id);
   ```

## Impact

- **Accuracy:** Efficiency now correctly measures workforce utilization during scheduled time
- **Consistency:** Same efficiency value regardless of actual runtime (downtime doesn't affect efficiency)
- **Alignment:** Matches CSV requirement specification
- **Separation:** Clear distinction between Efficiency (workforce) and Performance (machine speed)

## References

- CSV Requirement: "Use scheduled_hours from shift, not actual run_time"
- Audit Report: Identified formula error in denominator
- Industry Standard: Efficiency measures planned vs actual labor utilization
