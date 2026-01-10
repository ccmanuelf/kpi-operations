# Test Data Scenarios and Sample Calculations

**Purpose:** Provide comprehensive test scenarios for validating KPI calculations with sample data, expected results, and edge cases.

**Date:** 2025-12-31
**Analyst:** ANALYST Agent (Hive Mind Swarm)

---

## Test Scenario Categories

1. **Perfect Data** - All required fields present, ideal conditions
2. **Missing Data (Inference Triggered)** - Missing optional fields, inference engine used
3. **Edge Cases** - Boundary conditions, zero values, extreme values
4. **Error Cases** - Invalid data, division by zero protection

---

## KPI #3: Production Efficiency Test Scenarios

### Formula
```
Efficiency = (units_produced × ideal_cycle_time) / (employees_assigned × run_time_hours) × 100
```

### Test Scenario 3.1: Perfect Data ✅

**Input Data:**
```json
{
  "product_id": 101,
  "ideal_cycle_time": 0.25,  // 15 minutes per unit
  "units_produced": 200,
  "employees_assigned": 5,
  "run_time_hours": 8.5
}
```

**Manual Calculation:**
```
Hours Produced = 200 units × 0.25 hrs/unit = 50 hours
Hours Available = 5 employees × 8.5 hours = 42.5 hours
Efficiency = (50 / 42.5) × 100 = 117.65%
```

**Expected Output:**
```json
{
  "efficiency_percentage": 117.65,
  "ideal_cycle_time_used": 0.25,
  "was_inferred": false
}
```

**Validation:**
- ✅ Efficiency > 100% is possible (team working faster than standard)
- ✅ Result capped at 150% (per implementation)
- ✅ Decimal precision: 0.01 (2 decimal places)

---

### Test Scenario 3.2: Missing Cycle Time (Inference - Historical Average) ✅

**Input Data:**
```json
{
  "product_id": 102,
  "ideal_cycle_time": null,  // Missing - triggers inference
  "units_produced": 150,
  "employees_assigned": 4,
  "run_time_hours": 7.0
}
```

**Historical Data (Last 10 entries for product 102):**
```
Entry 1: units=100, employees=3, runtime=7.5, efficiency=88.89% → inferred cycle_time=0.20
Entry 2: units=120, employees=4, runtime=8.0, efficiency=90.00% → inferred cycle_time=0.24
Entry 3: units=110, employees=3, runtime=8.5, efficiency=86.27% → inferred cycle_time=0.22
...
Average inferred cycle_time = 0.22 hours/unit
```

**Manual Calculation:**
```
Inferred Cycle Time = 0.22 hours/unit (historical average)
Hours Produced = 150 × 0.22 = 33 hours
Hours Available = 4 × 7.0 = 28 hours
Efficiency = (33 / 28) × 100 = 117.86%
```

**Expected Output:**
```json
{
  "efficiency_percentage": 117.86,
  "ideal_cycle_time_used": 0.22,
  "was_inferred": true
}
```

**Validation:**
- ✅ Inference engine used historical average
- ✅ `was_inferred` flag is true
- ✅ Calculation proceeds normally with inferred value

---

### Test Scenario 3.3: Missing Cycle Time (No History - Default Used) ✅

**Input Data:**
```json
{
  "product_id": 999,  // New product, no history
  "ideal_cycle_time": null,
  "units_produced": 80,
  "employees_assigned": 2,
  "run_time_hours": 9.0
}
```

**Historical Data:** None available for product 999

**Manual Calculation:**
```
Default Cycle Time = 0.25 hours/unit (15 minutes)
Hours Produced = 80 × 0.25 = 20 hours
Hours Available = 2 × 9.0 = 18 hours
Efficiency = (20 / 18) × 100 = 111.11%
```

**Expected Output:**
```json
{
  "efficiency_percentage": 111.11,
  "ideal_cycle_time_used": 0.25,
  "was_inferred": false  // Default is not considered "inferred"
}
```

**Validation:**
- ✅ Default value used when no history exists
- ✅ System can still calculate efficiency for new products
- ✅ `was_inferred` is false (default fallback, not historical inference)

---

### Test Scenario 3.4: Edge Case - Zero Employees (Division by Zero Protection) ✅

**Input Data:**
```json
{
  "product_id": 101,
  "ideal_cycle_time": 0.25,
  "units_produced": 100,
  "employees_assigned": 0,  // Invalid - zero employees
  "run_time_hours": 8.0
}
```

**Manual Calculation:**
```
Hours Produced = 100 × 0.25 = 25 hours
Hours Available = 0 × 8.0 = 0 hours  // Division by zero!
Efficiency = ??? → Protection needed
```

**Expected Output:**
```json
{
  "efficiency_percentage": 0.00,
  "ideal_cycle_time_used": 0.25,
  "was_inferred": false
}
```

**Validation:**
- ✅ No exception thrown
- ✅ Returns 0% efficiency (safe fallback)
- ✅ Code protection: `if employees_assigned == 0 or run_time_hours == 0: return 0`

---

### Test Scenario 3.5: Edge Case - Zero Runtime (Division by Zero Protection) ✅

**Input Data:**
```json
{
  "product_id": 101,
  "ideal_cycle_time": 0.25,
  "units_produced": 50,
  "employees_assigned": 3,
  "run_time_hours": 0.0  // Invalid - zero runtime
}
```

**Expected Output:**
```json
{
  "efficiency_percentage": 0.00,
  "ideal_cycle_time_used": 0.25,
  "was_inferred": false
}
```

**Validation:**
- ✅ No exception thrown
- ✅ Returns 0% efficiency
- ✅ Same protection as zero employees case

---

### Test Scenario 3.6: Edge Case - Efficiency Cap at 150% ✅

**Input Data:**
```json
{
  "product_id": 101,
  "ideal_cycle_time": 0.25,
  "units_produced": 500,  // Very high output
  "employees_assigned": 2,
  "run_time_hours": 4.0   // Short runtime
}
```

**Manual Calculation:**
```
Hours Produced = 500 × 0.25 = 125 hours
Hours Available = 2 × 4.0 = 8 hours
Efficiency = (125 / 8) × 100 = 1562.5%  // Unrealistic!
```

**Expected Output:**
```json
{
  "efficiency_percentage": 150.00,  // Capped
  "ideal_cycle_time_used": 0.25,
  "was_inferred": false
}
```

**Validation:**
- ✅ Cap prevents misleading values
- ✅ Code: `efficiency = min(efficiency, Decimal("150"))`
- ✅ Indicates data quality issue (investigate if >150% before cap)

---

## KPI #9: Performance Test Scenarios

### Formula
```
Performance = (ideal_cycle_time × units_produced) / run_time_hours × 100
```

### Test Scenario 9.1: Perfect Data ✅

**Input Data:**
```json
{
  "product_id": 201,
  "ideal_cycle_time": 0.20,  // 12 minutes per unit
  "units_produced": 300,
  "run_time_hours": 8.0
}
```

**Manual Calculation:**
```
Ideal Time = 300 units × 0.20 hrs/unit = 60 hours
Actual Runtime = 8.0 hours
Performance = (60 / 8.0) × 100 = 750%  // Wait, this seems wrong...
```

**CORRECTED Manual Calculation:**
```
Note: Performance formula should be interpreted as:
  "How much of the runtime was spent on actual value-added work?"

Ideal Time for 300 units = 300 × 0.20 = 60 hours (if we had infinite machines)
But we only have 8 hours runtime
So we need to think about this differently...

Actually, the SPECIFICATION formula means:
  Performance = (ideal_time × count) / run_time × 100

If ideal_time = 0.20 hrs/unit and we produced 300 units in 8 hours:
  Performance = (0.20 × 300) / 8.0 × 100 = 60 / 8 × 100 = 750%

This is IMPOSSIBLE. Let me re-read the specification...
```

**SPECIFICATION ANALYSIS:**

Looking at Metrics_Sheet1.csv:
```
"(Ideal Cycle Time * Total Count Processed)/ Run Time"
"Make sure to use Ideal Cycle Time and Run Time with the same units (seconds, minutes, hours)"
```

**INTERPRETATION:** The formula calculates how fast the line ran compared to designed speed:
- If Performance = 100%, line ran at exactly designed speed
- If Performance > 100%, line ran faster than designed speed
- If Performance < 100%, line ran slower than designed speed

**BUT:** The units must match! If ideal_cycle_time is in hours per unit, then:
- **Issue**: 300 units × 0.20 hrs/unit = 60 total hours needed
- **Issue**: This cannot be done in 8 hours runtime!

**CORRECTION NEEDED:** Ideal cycle time should be the time per unit ON THE LINE, not total hours.

Let's recalculate with correct interpretation:
```
If ideal_cycle_time = 0.02 hours/unit (1.2 minutes per unit - line speed)
Total ideal time = 300 × 0.02 = 6 hours
Actual runtime = 8 hours
Performance = (6 / 8) × 100 = 75%
```

**This makes sense:** Line ran slower than ideal (took 8 hrs instead of 6 hrs)

**CRITICAL FINDING:**
⚠️ **The specification's "ideal_cycle_time" may be ambiguous!**
- In Efficiency KPI: ideal_cycle_time seems to mean "labor hours per unit"
- In Performance KPI: ideal_cycle_time should mean "machine cycle time per unit"

Let me check the actual implementation...

---

**IMPLEMENTATION REVIEW:**

Looking at `/backend/calculations/performance.py`:
```python
performance = (ideal_cycle_time * entry.units_produced) / Decimal(str(entry.run_time_hours)) * 100
```

And `/backend/calculations/efficiency.py` uses the SAME `ideal_cycle_time`!

**This is a POTENTIAL BUG** depending on interpretation:
- If `ideal_cycle_time` represents "total labor hours to produce one unit", then:
  - Efficiency calculation is CORRECT
  - Performance calculation is WRONG (should use line cycle time, not labor hours)

**RECOMMENDATION:** Clarify with stakeholder:
1. Is `ideal_cycle_time` the machine cycle time per unit? OR
2. Is `ideal_cycle_time` the labor hours per unit?

For now, assuming **machine cycle time** interpretation for Performance KPI:

**Corrected Test Scenario 9.1:**

**Input Data:**
```json
{
  "product_id": 201,
  "ideal_cycle_time": 0.0167,  // 1 minute per unit (machine speed)
  "units_produced": 300,
  "run_time_hours": 8.0
}
```

**Manual Calculation:**
```
Ideal Time = 300 units × 0.0167 hrs/unit = 5.01 hours
Actual Runtime = 8.0 hours
Performance = (5.01 / 8.0) × 100 = 62.63%
```

**Expected Output:**
```json
{
  "performance_percentage": 62.63,
  "ideal_cycle_time_used": 0.0167,
  "was_inferred": false
}
```

**Interpretation:** Line ran at 62.63% of ideal speed (took 8 hrs instead of ~5 hrs)

---

### Test Scenario 9.2: Missing Cycle Time (Inference Used) ✅

**Input Data:**
```json
{
  "product_id": 202,
  "ideal_cycle_time": null,
  "units_produced": 400,
  "run_time_hours": 9.0
}
```

**Inference:** Uses same `infer_ideal_cycle_time()` as Efficiency KPI

**Assumed Historical Average:** 0.02 hours/unit

**Manual Calculation:**
```
Inferred Cycle Time = 0.02 hours/unit
Ideal Time = 400 × 0.02 = 8 hours
Actual Runtime = 9.0 hours
Performance = (8 / 9) × 100 = 88.89%
```

**Expected Output:**
```json
{
  "performance_percentage": 88.89,
  "ideal_cycle_time_used": 0.02,
  "was_inferred": true
}
```

---

### Test Scenario 9.3: Edge Case - Zero Runtime ✅

**Input Data:**
```json
{
  "product_id": 201,
  "ideal_cycle_time": 0.02,
  "units_produced": 100,
  "run_time_hours": 0.0  // Invalid
}
```

**Expected Output:**
```json
{
  "performance_percentage": 0.00,
  "ideal_cycle_time_used": 0.02,
  "was_inferred": false
}
```

**Validation:**
- ✅ Division by zero protection
- ✅ Code: `if entry.run_time_hours == 0: return Decimal("0")`

---

### Test Scenario 9.4: Edge Case - Performance Cap at 150% ✅

**Input Data:**
```json
{
  "product_id": 201,
  "ideal_cycle_time": 0.02,
  "units_produced": 500,
  "run_time_hours": 4.0
}
```

**Manual Calculation:**
```
Ideal Time = 500 × 0.02 = 10 hours
Actual Runtime = 4.0 hours
Performance = (10 / 4) × 100 = 250%  // Impossible! Line can't run 2.5x faster
```

**Expected Output:**
```json
{
  "performance_percentage": 150.00,  // Capped
  "ideal_cycle_time_used": 0.02,
  "was_inferred": false
}
```

**Validation:**
- ✅ Cap prevents unrealistic values
- ✅ Indicates data error (check units_produced or runtime)

---

## Missing KPI Test Scenarios

### KPI #1: WIP Aging - NOT IMPLEMENTED ❌

**Test Scenario 1.1: Perfect Data (CANNOT TEST)**

**Theoretical Input Data:**
```json
{
  "job_id": "WO-12345",
  "start_date": "2025-12-01",
  "current_date": "2025-12-31",
  "hold_duration_hours": 72,  // 3 days on hold
  "status": "in-progress"
}
```

**Theoretical Calculation:**
```
Total Elapsed = 2025-12-31 - 2025-12-01 = 30 days
Hold Duration = 72 hours = 3 days
WIP Aging = 30 days - 3 days = 27 days
```

**Status:** ❌ Cannot validate - not implemented

---

### KPI #2: On-Time Delivery - NOT IMPLEMENTED ❌

**Test Scenario 2.1: Perfect Data (CANNOT TEST)**

**Theoretical Input Data:**
```json
{
  "orders": [
    {"promised_date": "2025-12-15", "actual_delivery": "2025-12-14", "on_time": true},
    {"promised_date": "2025-12-20", "actual_delivery": "2025-12-22", "on_time": false},
    {"promised_date": "2025-12-25", "actual_delivery": "2025-12-24", "on_time": true}
  ]
}
```

**Theoretical Calculation:**
```
Total Orders = 3
On-Time Orders = 2
OTD = (2 / 3) × 100 = 66.67%
```

**Status:** ❌ Cannot validate - not implemented

---

### KPI #4: Quality PPM - NOT IMPLEMENTED (BUT DATA EXISTS!) ❌

**Test Scenario 4.1: Perfect Data (COULD IMPLEMENT EASILY)**

**Available Input Data:**
```json
{
  "entry_id": 1001,
  "defect_count": 15,
  "units_produced": 10000
}
```

**Manual Calculation:**
```
PPM = (defects / total_units) × 1,000,000
PPM = (15 / 10,000) × 1,000,000 = 1,500 PPM
```

**Expected Output (If Implemented):**
```json
{
  "ppm": 1500.00
}
```

**Status:** ❌ Not implemented (QUICK WIN - data exists, formula is trivial)

---

### KPI #5: Quality DPMO - NOT IMPLEMENTED ❌

**Test Scenario 5.1: Perfect Data (CANNOT TEST - Missing opportunities_per_unit)**

**Theoretical Input Data:**
```json
{
  "defect_count": 20,
  "units_produced": 5000,
  "opportunities_per_unit": 8  // 8 ways a unit can fail
}
```

**Theoretical Calculation:**
```
Total Opportunities = 5000 units × 8 opps/unit = 40,000 opportunities
DPMO = (20 / 40,000) × 1,000,000 = 500 DPMO
```

**Status:** ❌ Cannot validate - not implemented

---

### KPI #6: Quality FPY - NOT IMPLEMENTED ❌

**Test Scenario 6.1: Perfect Data (CANNOT TEST)**

**Theoretical Input Data:**
```json
{
  "units_inspected": 1000,
  "units_passed_first_time": 920,
  "units_reworked": 60,
  "units_scrapped": 20
}
```

**Theoretical Calculation:**
```
FPY = (passed_first_time / inspected) × 100
FPY = (920 / 1000) × 100 = 92.00%
```

**Status:** ❌ Cannot validate - not implemented

---

### KPI #7: Quality RTY - NOT IMPLEMENTED ❌

**Test Scenario 7.1: Perfect Data (CANNOT TEST)**

**Theoretical Input Data:**
```json
{
  "units_started": 1000,
  "units_completed_defect_free": 850
}
```

**Theoretical Calculation:**
```
RTY = (completed_defect_free / started) × 100
RTY = (850 / 1000) × 100 = 85.00%
```

**Status:** ❌ Cannot validate - not implemented

---

### KPI #8: Availability - NOT IMPLEMENTED ❌

**Test Scenario 8.1: Perfect Data (CANNOT TEST)**

**Theoretical Input Data:**
```json
{
  "planned_production_time": 480,  // 8 hours = 480 minutes
  "downtime_minutes": 45,
  "downtime_reasons": [
    {"reason": "Equipment failure", "minutes": 25},
    {"reason": "Material shortage", "minutes": 20}
  ]
}
```

**Theoretical Calculation:**
```
Uptime = 480 - 45 = 435 minutes
Availability = 1 - (downtime / planned_time)
Availability = 1 - (45 / 480) = 1 - 0.09375 = 0.90625 = 90.63%
```

**Status:** ❌ Cannot validate - not implemented

---

### KPI #10: Absenteeism - NOT IMPLEMENTED ❌

**Test Scenario 10.1: Perfect Data (CANNOT TEST)**

**Theoretical Input Data:**
```json
{
  "employees": [
    {"employee_id": 1, "scheduled_hours": 40, "absence_hours": 8},
    {"employee_id": 2, "scheduled_hours": 40, "absence_hours": 0},
    {"employee_id": 3, "scheduled_hours": 40, "absence_hours": 16}
  ]
}
```

**Theoretical Calculation:**
```
Total Scheduled = 40 + 40 + 40 = 120 hours
Total Absence = 8 + 0 + 16 = 24 hours
Absenteeism = (24 / 120) × 100 = 20.00%
```

**Status:** ❌ Cannot validate - not implemented

---

## Critical Finding: ideal_cycle_time Ambiguity ⚠️

### ISSUE IDENTIFIED

The `ideal_cycle_time` field is used in BOTH:
1. **Efficiency KPI** (labor hours per unit)
2. **Performance KPI** (machine cycle time per unit)

These are **DIFFERENT** concepts:
- **Labor hours per unit** = Total human hours needed to produce one unit
  - Example: 0.25 hrs (15 minutes of combined labor from all workers)
- **Machine cycle time** = How fast the line can process one unit
  - Example: 0.0167 hrs (1 minute per unit throughput)

### CURRENT IMPLEMENTATION PROBLEM

Both KPIs use the same `ideal_cycle_time` value from the `product` table, which creates ambiguity:
- If `ideal_cycle_time = 0.25` hours (labor hours per unit):
  - ✅ Efficiency calculation is CORRECT
  - ❌ Performance calculation will show impossibly high values (>100% always)

- If `ideal_cycle_time = 0.0167` hours (machine cycle time):
  - ❌ Efficiency calculation will show impossibly low values (<10%)
  - ✅ Performance calculation is CORRECT

### RECOMMENDATION

**Option 1: Separate Fields (Recommended)**
```sql
ALTER TABLE product
  ADD COLUMN labor_hours_per_unit DECIMAL(8,4) COMMENT 'For Efficiency KPI',
  ADD COLUMN machine_cycle_time DECIMAL(8,4) COMMENT 'For Performance KPI';
```

**Option 2: Clarify Single Field Usage**
- Document that `ideal_cycle_time` represents ONLY machine cycle time
- Update Efficiency KPI to use a different calculation approach
- Use industry-standard approach: Efficiency based on OEE components

**Option 3: Use Run Rate**
```sql
-- Add target run rate (units per hour)
ALTER TABLE product
  ADD COLUMN target_run_rate INT UNSIGNED COMMENT 'Units per hour at 100% performance';
```

Then:
- Efficiency = labor utilization metric
- Performance = (actual_run_rate / target_run_rate) × 100

---

## Summary of Testable vs. Non-Testable KPIs

### ✅ Testable KPIs (2/10)

| KPI | Test Scenarios | Coverage |
|-----|----------------|----------|
| #3 Efficiency | 6 scenarios | Perfect data, inference (historical), inference (default), zero employees, zero runtime, cap at 150% |
| #9 Performance | 4 scenarios | Perfect data, inference, zero runtime, cap at 150% |

### ❌ Non-Testable KPIs (8/10)

| KPI | Reason |
|-----|--------|
| #1 WIP Aging | No implementation, no data tables |
| #2 On-Time Delivery | No implementation, no data tables |
| #4 Quality PPM | No implementation (but data exists - QUICK WIN!) |
| #5 Quality DPMO | No implementation, missing opportunities_per_unit |
| #6 Quality FPY | No implementation, missing rework/repair tracking |
| #7 Quality RTY | No implementation, missing process step tracking |
| #8 Availability | No implementation, missing downtime tracking |
| #10 Absenteeism | No implementation, missing attendance tracking |

---

## Next Steps for Testing

### Immediate Testing (Can Do Now)

1. ✅ **Test KPI #3 (Efficiency)** with all 6 scenarios
2. ✅ **Test KPI #9 (Performance)** with all 4 scenarios
3. ✅ **Document ideal_cycle_time ambiguity** and get stakeholder clarification

### Future Testing (After Implementation)

1. ❌ Implement KPI #4 (PPM) → Test with real production data
2. ❌ Implement remaining KPIs → Create test scenarios as they're built
3. ❌ Integration testing with frontend dashboard
4. ❌ Load testing with large datasets (>10,000 production entries)

---

**Report Generated:** 2025-12-31 by ANALYST Agent
**Companion Document:** validation_report.md
