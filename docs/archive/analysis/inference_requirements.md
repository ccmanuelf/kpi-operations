# Inference Requirements - 5-Level Fallback Strategies for Missing Data

**Research Lead**: Researcher Agent
**Session ID**: swarm-1767238686161-ap0rkjkpz
**Date**: 2025-12-31

---

## Purpose

Manufacturing data is often incomplete, inconsistent, or missing entirely. This document defines **5-level fallback strategies** for each critical field to ensure KPI calculations can proceed gracefully without blocking on missing data.

**Design Philosophy**:
1. **Primary**: Use actual recorded data (highest confidence)
2. **Fallback**: Use alternative field (high confidence)
3. **Calculated**: Derive from other fields (medium confidence)
4. **Historical**: Use 30-day average (medium-low confidence)
5. **Default/Flag**: Use industry standard OR flag as "Insufficient Data" (low confidence)

**Critical**: ALWAYS track which inference level was used for transparency and data quality reporting.

---

## Table of Contents

1. [Core Fields Inference](#core-fields-inference)
2. [Production Data Inference](#production-data-inference)
3. [Downtime & Hold Inference](#downtime--hold-inference)
4. [Attendance Inference](#attendance-inference)
5. [Quality Data Inference](#quality-data-inference)
6. [Confidence Level Tracking](#confidence-level-tracking)
7. [Implementation Guidelines](#implementation-guidelines)

---

## Core Fields Inference

### 1. `actual_start_date` (WORK_ORDER)
**Used By**: WIP Aging (#1), OTD (#2)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `actual_start_date` | Direct field | **HIGH** | Recorded actual start |
| 2 | `planned_start_date` | Fallback field | **MEDIUM-HIGH** | Planned start (if actual missing) |
| 3 | First `PRODUCTION_ENTRY.shift_date` | Calculated | **MEDIUM** | First production entry date for this WO |
| 4 | `receipt_date + lead_time` | Calculated | **MEDIUM-LOW** | Receipt date + client-specific lead time (e.g., 5 days) |
| 5 | `acknowledged_date + 2 days` | Default estimate | **LOW** | Standard 2-day planning cycle |

**Fallback SQL**:
```sql
COALESCE(
  actual_start_date,
  planned_start_date,
  (SELECT MIN(shift_date) FROM PRODUCTION_ENTRY WHERE work_order_id_fk = work_order_id),
  DATE_ADD(receipt_date, INTERVAL 5 DAY),
  DATE_ADD(acknowledged_date, INTERVAL 2 DAY)
)
```

**Flag If**:
- All 5 levels return NULL → Flag as "NO_START_DATE"
- Level 3+ used → Store `inference_level = 3` and `inference_method = 'first_production_entry'`

---

### 2. `planned_ship_date` OR `required_date` (WORK_ORDER)
**Used By**: On-Time Delivery (#2)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `planned_ship_date` | Direct field | **HIGH** | Promise date from production schedule |
| 2 | `required_date` | Fallback field | **HIGH** | Customer PO required date |
| 3 | `planned_start_date + CEIL((quantity × ideal_cycle_time) / shift_hours)` | Calculated surrogate | **MEDIUM** | Calculated delivery date based on production capacity |
| 4 | `actual_start_date + historical_avg_lead_time(style_model, client_id)` | Historical average | **MEDIUM-LOW** | 30-day avg lead time by style-model + client |
| 5 | `actual_start_date + 14 days` | Default industry standard | **LOW** | Standard 2-week lead time |

**Fallback SQL**:
```sql
COALESCE(
  planned_ship_date,
  required_date,
  DATE_ADD(planned_start_date, INTERVAL CEIL((planned_quantity * ideal_cycle_time) / 9) DAY),
  DATE_ADD(actual_start_date, INTERVAL (SELECT AVG(DATEDIFF(planned_ship_date, actual_start_date)) FROM WORK_ORDER WHERE style_model = style_model AND client_id_fk = client_id_fk AND planned_ship_date IS NOT NULL AND DATE_SUB(CURDATE(), INTERVAL 30 DAY) <= actual_start_date) DAY),
  DATE_ADD(actual_start_date, INTERVAL 14 DAY)
)
```

**Flag If**:
- All 5 levels return NULL → Flag as "NO_PROMISE_DATE - CANNOT_CALCULATE_OTD"
- Level 3+ used → Store `inference_level` and `inference_method`

**Critical Note**: Current practice shows 40-60% of work orders missing promise dates. System MUST handle this gracefully.

---

### 3. `ideal_cycle_time` (WORK_ORDER)
**Used By**: Efficiency (#3), Performance (#8), OTD (#2)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `ideal_cycle_time` | Direct field | **HIGH** | Engineering-provided standard time |
| 2 | Engineering master table | Reference data | **HIGH** | Centralized standard times by part/style |
| 3 | Historical average (30 days) | `AVG(units_produced / run_time_hours)` by `style_model + client_id` | **MEDIUM** | Actual performance-based average |
| 4 | Client-specific default | Client configuration | **MEDIUM-LOW** | Client-provided general standard (e.g., 0.25 hrs for boots) |
| 5 | Flag as "NO_STANDARD_TIME" | Efficiency/Performance = NULL | **NONE** | Cannot calculate without cycle time |

**Fallback SQL**:
```sql
COALESCE(
  ideal_cycle_time,
  (SELECT standard_time FROM ENGINEERING_STANDARDS WHERE part_number = part_number),
  (SELECT AVG(units_produced / NULLIF(run_time_hours, 0)) FROM PRODUCTION_ENTRY WHERE work_order_id_fk IN (SELECT work_order_id FROM WORK_ORDER WHERE style_model = style_model AND client_id_fk = client_id_fk) AND shift_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)),
  (SELECT default_cycle_time FROM CLIENT WHERE client_id = client_id_fk),
  NULL
)
```

**Flag If**:
- Level 5 (NULL) → Flag as "NO_STANDARD_TIME - EFFICIENCY_UNAVAILABLE"
- Level 3+ used → Store `inference_level` and `inference_method`

**Critical Note**: 30-50% missing. Historical averaging from actual production is most practical fallback.

---

## Production Data Inference

### 4. `run_time_hours` (PRODUCTION_ENTRY)
**Used By**: Efficiency (#3), Performance (#8)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `run_time_hours` | Direct field | **HIGH** | Manually recorded actual run time |
| 2 | `shift_hours_scheduled - (downtime_total_minutes / 60)` | Calculated | **HIGH** | Shift hours minus logged downtime |
| 3 | `shift_hours_scheduled` | Fallback (assumes 0 downtime) | **MEDIUM** | Phase 1 workaround |
| 4 | Standard shift hours | From CLIENT config or shift_type mapping | **MEDIUM-LOW** | 9 hrs for SHIFT_1ST, 9 hrs for SHIFT_2ND, 8 hrs for SAT_OT |
| 5 | 9 hours | Default assumption | **LOW** | Standard shift assumption |

**Fallback SQL**:
```sql
COALESCE(
  run_time_hours,
  shift_hours_scheduled - (COALESCE(downtime_total_minutes, 0) / 60),
  shift_hours_scheduled,
  CASE shift_type
    WHEN 'SHIFT_1ST' THEN 9
    WHEN 'SHIFT_2ND' THEN 9
    WHEN 'SAT_OT' THEN 8
    WHEN 'SUN_OT' THEN 8
    ELSE 9
  END,
  9
)
```

**Flag If**:
- Level 3+ used → Store `inference_level` and `inference_method`
- Phase 1: Default to Level 3 (assume 0 downtime)

---

### 5. `employees_assigned` (PRODUCTION_ENTRY)
**Used By**: Efficiency (#3)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `employees_assigned` | Direct field | **HIGH** | Manually recorded staffing |
| 2 | `COUNT(employee_id) FROM ATTENDANCE_ENTRY WHERE is_absent = FALSE` | Calculated from attendance | **HIGH** | Count present employees (Phase 3+) |
| 3 | Client standard staffing | Client configuration | **MEDIUM** | Expected line staffing level |
| 4 | Historical average | 30-day avg staffing by client | **MEDIUM-LOW** | Past staffing patterns |
| 5 | 10 employees | Default assumption | **LOW** | Typical line staffing |

**Fallback SQL**:
```sql
COALESCE(
  employees_assigned,
  (SELECT COUNT(*) FROM ATTENDANCE_ENTRY WHERE client_id_fk = client_id_fk AND shift_date = shift_date AND shift_type = shift_type AND is_absent = FALSE),
  (SELECT standard_line_staffing FROM CLIENT WHERE client_id = client_id_fk),
  (SELECT AVG(employees_assigned) FROM PRODUCTION_ENTRY WHERE client_id_fk = client_id_fk AND shift_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)),
  10
)
```

**Flag If**:
- Level 3+ used → Store `inference_level` and `inference_method`

**Phase Integration**:
- Phase 1: Use Level 1 or Level 3 (no attendance data yet)
- Phase 3+: Use Level 2 (calculate from ATTENDANCE_ENTRY)

---

### 6. `downtime_total_minutes` (PRODUCTION_ENTRY)
**Used By**: Efficiency (#3), Performance (#8), Availability (#7)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `downtime_total_minutes` | Direct field (manually entered summary) | **HIGH** | Data collector summarized downtime |
| 2 | `SUM(downtime_duration_minutes) FROM DOWNTIME_ENTRY` | Calculated from detailed logs | **HIGH** | Sum of all downtime entries for this WO/shift |
| 3 | `shift_hours_scheduled - run_time_hours` | Calculated difference | **MEDIUM** | Infer downtime from missing run time |
| 4 | 0 minutes | Phase 1 assumption | **MEDIUM-LOW** | Assume no downtime (Phase 1 workaround) |
| 5 | 30 minutes | Default 5% downtime | **LOW** | Industry avg ~5% unplanned downtime |

**Fallback SQL**:
```sql
COALESCE(
  downtime_total_minutes,
  (SELECT SUM(downtime_duration_minutes) FROM DOWNTIME_ENTRY WHERE work_order_id_fk = work_order_id_fk AND shift_date = shift_date AND shift_type = shift_type),
  (shift_hours_scheduled - COALESCE(run_time_hours, shift_hours_scheduled)) * 60,
  0,
  30
)
```

**Flag If**:
- Level 4 used (Phase 1) → Flag as "ASSUMED_ZERO_DOWNTIME - PHASE1_WORKAROUND"
- Level 5 used → Flag as "DEFAULT_DOWNTIME_ASSUMPTION"

**Phase Integration**:
- Phase 1: Default to Level 4 (0 downtime)
- Phase 2+: Use Levels 1-3 (actual downtime tracking)

---

## Downtime & Hold Inference

### 7. `hold_duration_hours` (HOLD_ENTRY)
**Used By**: WIP Aging (#1)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `total_hold_duration_hours` | Direct field (auto-calculated) | **HIGH** | System calculated from hold_date and resume_date |
| 2 | `TIMESTAMPDIFF(HOUR, hold_date, resume_date)` | Calculated from dates | **HIGH** | Manual calculation if total field missing |
| 3 | `DATEDIFF(resume_date, hold_date) * 24` | Day-level calculation | **MEDIUM** | If times missing, use dates only |
| 4 | `CURDATE() - hold_date` | Ongoing hold | **MEDIUM** | If not resumed, calculate ongoing duration |
| 5 | Flag as "HOLD_DURATION_UNKNOWN" | WIP aging includes full hold period | **LOW** | Cannot exclude hold time from aging |

**Fallback SQL**:
```sql
CASE
  WHEN hold_status = 'RESUMED' THEN
    COALESCE(
      total_hold_duration_hours,
      TIMESTAMPDIFF(HOUR, CONCAT(hold_date, ' ', COALESCE(hold_time, '00:00:00')), CONCAT(resume_date, ' ', COALESCE(resume_time, '00:00:00'))),
      DATEDIFF(resume_date, hold_date) * 24,
      NULL
    )
  WHEN hold_status = 'ON_HOLD' THEN
    COALESCE(
      TIMESTAMPDIFF(HOUR, CONCAT(hold_date, ' ', COALESCE(hold_time, '00:00:00')), NOW()),
      DATEDIFF(CURDATE(), hold_date) * 24,
      NULL
    )
  ELSE NULL
END
```

**Flag If**:
- Level 5 (NULL) → Flag as "HOLD_DURATION_UNKNOWN - AGING_INACCURATE"

---

### 8. `downtime_reason` (DOWNTIME_ENTRY)
**Used By**: Availability (#7), Analysis

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `downtime_reason` | Direct field (dropdown selection) | **HIGH** | Supervisor selected reason |
| 2 | `downtime_reason_detail` text analysis | NLP/keyword matching | **MEDIUM** | Extract reason from detail field |
| 3 | Historical pattern | Most common reason for this client/shift | **MEDIUM-LOW** | Pattern-based guess |
| 4 | 'OTHER' | Default category | **LOW** | Unknown reason |
| 5 | Flag as "REASON_UNKNOWN" | Count as downtime, unknown category | **NONE** | Cannot categorize |

**Fallback Logic** (pseudo-code):
```python
if downtime_reason:
    return downtime_reason  # Level 1
elif downtime_reason_detail:
    # Level 2: Keyword matching
    if "machine" in detail.lower() or "equipment" in detail.lower():
        return "EQUIPMENT_FAILURE"
    elif "material" in detail.lower() or "shortage" in detail.lower():
        return "MATERIAL_SHORTAGE"
    elif "setup" in detail.lower() or "changeover" in detail.lower():
        return "CHANGEOVER_SETUP"
    # ... more patterns
else:
    # Level 3: Historical
    return most_common_reason_for_client(client_id, last_30_days)

# Level 4: Default
return "OTHER"
```

**Flag If**:
- Level 2+ used → Store `inference_level` and `inference_method`

---

## Attendance Inference

### 9. `scheduled_hours` (ATTENDANCE_ENTRY)
**Used By**: Absenteeism (#10)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `scheduled_hours` | Direct field | **HIGH** | Manually recorded scheduled hours |
| 2 | `shift_hours_scheduled` from PRODUCTION_ENTRY | Fallback field | **HIGH** | Shift hours for this date/shift |
| 3 | Standard shift hours | From shift_type mapping | **MEDIUM** | 9 hrs SHIFT_1ST, 9 hrs SHIFT_2ND, 8 hrs SAT_OT, 8 hrs SUN_OT |
| 4 | Employee contract hours | From EMPLOYEE table (if custom) | **MEDIUM-LOW** | Employee-specific scheduled hours |
| 5 | 9 hours | Default assumption | **LOW** | Standard shift |

**Fallback SQL**:
```sql
COALESCE(
  scheduled_hours,
  (SELECT shift_hours_scheduled FROM PRODUCTION_ENTRY WHERE client_id_fk = client_id_fk AND shift_date = shift_date AND shift_type = shift_type LIMIT 1),
  CASE shift_type
    WHEN 'SHIFT_1ST' THEN 9
    WHEN 'SHIFT_2ND' THEN 9
    WHEN 'SAT_OT' THEN 8
    WHEN 'SUN_OT' THEN 8
    ELSE 9
  END,
  (SELECT contract_hours_per_shift FROM EMPLOYEE WHERE employee_id = employee_id_fk),
  9
)
```

**Flag If**:
- Level 3+ used → Store `inference_level` and `inference_method`

---

### 10. `absence_hours` (ATTENDANCE_ENTRY)
**Used By**: Absenteeism (#10)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `absence_hours` | Direct field | **HIGH** | Manually recorded absence hours |
| 2 | `scheduled_hours - actual_hours` | Calculated difference | **HIGH** | Infer absence from missing hours |
| 3 | `scheduled_hours` (if is_absent = TRUE) | Assume full shift absence | **MEDIUM** | Full day absence |
| 4 | Production log inference | If no production entries, assume absent | **MEDIUM-LOW** | Indirect absence detection |
| 5 | 0 hours | Default (assume present) | **LOW** | Optimistic assumption |

**Fallback SQL**:
```sql
CASE
  WHEN is_absent = TRUE THEN
    COALESCE(
      absence_hours,
      scheduled_hours - COALESCE(actual_hours, 0),
      scheduled_hours,
      9
    )
  ELSE 0
END
```

**Flag If**:
- Level 3+ used → Store `inference_level` and `inference_method`
- If employee has production entries but marked absent → Data quality issue

---

## Quality Data Inference

### 11. `opportunities_per_unit` (PART_OPPORTUNITIES)
**Used By**: DPMO (#5)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | `opportunities_per_unit` | Direct field from PART_OPPORTUNITIES | **HIGH** | Engineering-defined opportunities |
| 2 | Client-specific default | From CLIENT config by product type | **MEDIUM** | Simple=10, Medium=25, Complex=50 |
| 3 | Historical average | Avg opportunities by similar parts | **MEDIUM-LOW** | Pattern-based estimate |
| 4 | 1 opportunity | Default (DPMO = PPM) | **LOW** | Simplest assumption |
| 5 | Flag as "NO_OPPORTUNITIES - DPMO_UNAVAILABLE" | DPMO = NULL | **NONE** | Cannot calculate |

**Fallback SQL**:
```sql
COALESCE(
  (SELECT opportunities_per_unit FROM PART_OPPORTUNITIES WHERE part_number = part_number),
  (SELECT default_opportunities FROM CLIENT WHERE client_id = client_id_fk),
  (SELECT AVG(opportunities_per_unit) FROM PART_OPPORTUNITIES WHERE part_number LIKE CONCAT(SUBSTRING(part_number, 1, 4), '%')),
  1,
  NULL
)
```

**Flag If**:
- Level 4 used → Flag as "USING_DEFAULT_OPPORTUNITIES - DPMO_EQUALS_PPM"
- Level 5 (NULL) → Flag as "NO_OPPORTUNITIES - DPMO_UNAVAILABLE"

---

### 12. `units_requiring_rework` vs `units_requiring_repair` (QUALITY_ENTRY)
**Used By**: FPY (#6), RTY (#7)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|--------|--------|------------|-------|
| 1 | Both fields populated | Direct fields | **HIGH** | Detailed tracking |
| 2 | `units_defective` only | Assume all defects require rework OR repair | **MEDIUM** | Simplified tracking (all fail FPY) |
| 3 | DEFECT_DETAIL analysis | Count rework vs repair from detailed records | **MEDIUM** | Infer from defect details |
| 4 | Historical split | 60% rework, 40% repair (client-specific pattern) | **MEDIUM-LOW** | Pattern-based allocation |
| 5 | All defects = rework | Assume worst case (all return to previous op) | **LOW** | Conservative estimate |

**Fallback Logic** (pseudo-code):
```python
if units_requiring_rework is not None and units_requiring_repair is not None:
    return (units_requiring_rework, units_requiring_repair)  # Level 1

elif units_defective:
    # Level 2
    return (units_defective, 0)  # Assume all rework

elif defect_detail_records:
    # Level 3
    rework = COUNT(is_rework_required = TRUE)
    repair = COUNT(is_repair_in_current_op = TRUE)
    return (rework, repair)

else:
    # Level 4: Historical split
    rework_pct = historical_rework_percentage(client_id, part_number)
    rework = units_defective * rework_pct
    repair = units_defective * (1 - rework_pct)
    return (rework, repair)
```

**Flag If**:
- Level 2+ used → Store `inference_level` and `inference_method`

---

### 13. `total_defects_count` (QUALITY_ENTRY)
**Used By**: DPMO (#5)

**5-Level Strategy**:

| Level | Source | Method | Confidence | Notes |
|-------|------|--------|------------|-------|
| 1 | `total_defects_count` | Direct field | **HIGH** | Manually recorded total defects |
| 2 | `COUNT(defect_detail_id)` | Calculated from DEFECT_DETAIL | **HIGH** | Count individual defect records |
| 3 | `units_defective` | Assume 1 defect per defective unit | **MEDIUM** | Simplified (total_defects = units_defective) |
| 4 | `units_defective × 1.5` | Historical average multiplier | **MEDIUM-LOW** | Some units have multiple defects |
| 5 | `units_defective` | Default (same as Level 3) | **LOW** | Conservative estimate |

**Fallback SQL**:
```sql
COALESCE(
  total_defects_count,
  (SELECT COUNT(*) FROM DEFECT_DETAIL WHERE quality_entry_id_fk = quality_entry_id),
  units_defective,
  units_defective * 1.5,
  units_defective
)
```

**Flag If**:
- Level 3+ used → Store `inference_level` and `inference_method`
- DPMO accuracy degrades if multiple defects per unit common

---

## Confidence Level Tracking

### Metadata Fields for Inference Tracking

**Add to ALL entity tables**:

| Field | Type | Purpose |
|-------|------|---------|
| `inference_used` | BOOLEAN | TRUE if ANY field used inference (not all primary data) |
| `inference_level_max` | INT | Highest inference level used (1-5, 1=best, 5=worst) |
| `inference_fields` | JSON | Array of fields that used inference |
| `inference_methods` | JSON | Map of field → inference method used |

**Example**:
```json
{
  "inference_used": true,
  "inference_level_max": 3,
  "inference_fields": ["ideal_cycle_time", "run_time_hours"],
  "inference_methods": {
    "ideal_cycle_time": "30-day historical average by style_model",
    "run_time_hours": "shift_hours_scheduled (assumed 0 downtime)"
  }
}
```

**Data Quality Dashboard**:
- % records using inference (by KPI)
- Distribution of inference levels (how many Level 1, 2, 3, 4, 5?)
- Most common inferred fields
- Confidence score trends (improving or worsening?)

---

### Confidence Scoring System

**Composite Confidence Score** (per KPI calculation):

```
Confidence_Score = AVERAGE(field_confidence_scores)

WHERE:
  field_confidence_score = CASE inference_level
    WHEN 1 THEN 1.0  (100% confidence)
    WHEN 2 THEN 0.9  (90% confidence)
    WHEN 3 THEN 0.7  (70% confidence)
    WHEN 4 THEN 0.5  (50% confidence)
    WHEN 5 THEN 0.3  (30% confidence)
  END
```

**Example**: Production Efficiency Calculation
- `units_produced`: Level 1 (1.0)
- `ideal_cycle_time`: Level 3 (0.7) - historical average
- `employees_assigned`: Level 1 (1.0)
- `run_time_hours`: Level 3 (0.7) - assumed 0 downtime

**Efficiency Confidence** = (1.0 + 0.7 + 1.0 + 0.7) / 4 = **0.85 (85% confidence)**

**Reporting**:
- Display confidence % next to KPI values
- Flag KPIs with <70% confidence for manual review
- Track confidence trends (improving = better data quality)

---

## Implementation Guidelines

### 1. Inference Engine Architecture

**Centralized Inference Service**:
```python
class InferenceEngine:
    def infer_field(self, field_name, primary_value, context_data):
        """
        Apply 5-level fallback strategy

        Args:
            field_name: Name of field to infer
            primary_value: Primary field value (may be None)
            context_data: Dict of related data for calculations

        Returns:
            (inferred_value, inference_level, inference_method)
        """
        strategies = self.get_strategies(field_name)

        for level, strategy in enumerate(strategies, start=1):
            value = strategy.execute(primary_value, context_data)
            if value is not None:
                return (value, level, strategy.method_name)

        return (None, 5, 'NO_INFERENCE_AVAILABLE')
```

**Usage in KPI Calculation**:
```python
# Efficiency calculation
inference_engine = InferenceEngine()

units_produced, inf_level_1, inf_method_1 = inference_engine.infer_field(
    'units_produced',
    production_entry.units_produced,
    {'work_order': work_order, 'shift_date': shift_date}
)

ideal_cycle_time, inf_level_2, inf_method_2 = inference_engine.infer_field(
    'ideal_cycle_time',
    work_order.ideal_cycle_time,
    {'style_model': work_order.style_model, 'client_id': work_order.client_id_fk}
)

# Track inference metadata
efficiency_metadata = {
    'inference_used': inf_level_1 > 1 or inf_level_2 > 1,
    'inference_level_max': max(inf_level_1, inf_level_2),
    'inference_fields': [f for f in ['units_produced', 'ideal_cycle_time'] if level > 1],
    'inference_methods': {
        'units_produced': inf_method_1,
        'ideal_cycle_time': inf_method_2
    },
    'confidence_score': calculate_confidence([inf_level_1, inf_level_2])
}
```

---

### 2. Historical Averaging Queries

**30-Day Historical Average Template**:
```sql
-- ideal_cycle_time historical average
SELECT
    AVG(units_produced / NULLIF(run_time_hours, 0)) AS avg_cycle_time
FROM PRODUCTION_ENTRY pe
JOIN WORK_ORDER wo ON pe.work_order_id_fk = wo.work_order_id
WHERE
    wo.style_model = :target_style_model
    AND wo.client_id_fk = :target_client_id
    AND pe.shift_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    AND pe.units_produced > 0
    AND pe.run_time_hours > 0
```

**Lead Time Historical Average**:
```sql
-- OTD lead time historical average
SELECT
    AVG(DATEDIFF(planned_ship_date, actual_start_date)) AS avg_lead_time_days
FROM WORK_ORDER
WHERE
    style_model = :target_style_model
    AND client_id_fk = :target_client_id
    AND planned_ship_date IS NOT NULL
    AND actual_start_date IS NOT NULL
    AND DATE_SUB(CURDATE(), INTERVAL 30 DAY) <= actual_start_date
```

---

### 3. Validation Rules

**Pre-Calculation Validation**:
- Check for NULL primary fields
- Trigger inference if NULL
- Log inference usage for audit

**Post-Calculation Validation**:
- Flag unrealistic values (e.g., Efficiency > 150%, PPM > 1,000,000)
- Alert on low confidence (<70%)
- Recommend data quality improvements

**Data Quality Alerts**:
- ">50% of Efficiency calculations using Level 3+ inference"
- "ideal_cycle_time missing for 40% of work orders - update engineering standards"
- "promise_date missing for 60% of work orders - improve planning process"

---

### 4. User Interface Guidelines

**Display Inference Indicators**:
- ✓ Green checkmark = 100% actual data (Level 1)
- ⚠️ Yellow warning = Inferred data (Level 2-3)
- ⛔ Red flag = Low confidence (Level 4-5)

**Tooltip on Hover**:
```
Efficiency: 87.5% ⚠️
Confidence: 85%

Inferred Fields:
- ideal_cycle_time: 30-day historical average (0.25 hrs)
- run_time_hours: assumed 0 downtime (9 hrs)

Click to see detailed calculation
```

**Admin Dashboard**:
- Data Quality Score (% of records with Level 1 data)
- Inference Usage Report (which fields inferred most often)
- Improvement Recommendations (prioritize collecting missing data)

---

## Summary Table - All Inference Strategies

| Field | Primary | Fallback 2 | Fallback 3 | Fallback 4 | Fallback 5 | Flag If Level 5 |
|-------|---------|------------|------------|------------|------------|-----------------|
| actual_start_date | actual_start_date | planned_start_date | First production entry date | receipt_date + lead_time | acknowledged_date + 2 days | NO_START_DATE |
| planned_ship_date | planned_ship_date | required_date | planned_start_date + calc | Historical avg lead time | actual_start_date + 14 days | NO_PROMISE_DATE |
| ideal_cycle_time | ideal_cycle_time | Engineering master | 30-day historical avg | Client default | NULL | NO_STANDARD_TIME |
| run_time_hours | run_time_hours | shift_hrs - downtime | shift_hours_scheduled | Standard shift hrs by type | 9 hrs | - |
| employees_assigned | employees_assigned | COUNT(attendance present) | Client standard staffing | 30-day avg staffing | 10 | - |
| downtime_total_minutes | downtime_total_minutes | SUM(downtime entries) | shift_hrs - run_time | 0 (Phase 1) | 30 min (5%) | ASSUMED_ZERO_DOWNTIME |
| hold_duration_hours | total_hold_duration_hours | TIMESTAMPDIFF(dates) | DATEDIFF * 24 | Ongoing hold (CURDATE - hold_date) | NULL | HOLD_DURATION_UNKNOWN |
| scheduled_hours | scheduled_hours | shift_hours_scheduled | Standard shift hrs by type | Employee contract hours | 9 hrs | - |
| absence_hours | absence_hours | scheduled_hrs - actual_hrs | scheduled_hours (if absent) | 9 hrs | 0 hrs | - |
| opportunities_per_unit | opportunities_per_unit | Client default | Historical avg by pattern | 1 | NULL | NO_OPPORTUNITIES |
| units_requiring_rework | units_requiring_rework | units_defective (all) | DEFECT_DETAIL count | Historical split (60/40) | units_defective (all rework) | - |
| total_defects_count | total_defects_count | COUNT(DEFECT_DETAIL) | units_defective | units_defective × 1.5 | units_defective | - |

---

## Next Steps for Development

1. **Implement InferenceEngine class** (centralized service)
2. **Create inference metadata tracking** (JSON fields in tables)
3. **Build historical averaging queries** (30-day lookback)
4. **Design data quality dashboard** (confidence scores, inference usage)
5. **Add UI indicators** (green/yellow/red confidence levels)
6. **Test with real data** (validate inference accuracy)
7. **Iterate on thresholds** (adjust confidence scoring based on actual performance)

---

**Complete Inference Requirements**: Ready for implementation in KPI calculation engines.
