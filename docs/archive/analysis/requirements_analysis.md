# Manufacturing KPI Platform - Requirements Analysis

**Research Lead**: Researcher Agent
**Session ID**: swarm-1767238686161-ap0rkjkpz
**Date**: 2025-12-31
**Status**: Complete

---

## Executive Summary

This document provides a comprehensive analysis of all 10 KPIs required for the Manufacturing KPI Platform, synthesizing data from context summaries, metric definitions, and inventory assessments across 5 CSV files.

### Scale & Context
- **Current**: 15 clients, 800 employees
- **Peak**: 35 clients, 2,500 employees
- **2026 Target**: 50+ clients, 3,000+ employees
- **Architecture**: Multi-tenant with zero data duplication
- **Data Collection**: Manual entry + CSV upload (future: QR scanning)

---

## 10 KPI Modules - Detailed Analysis

### 1. WIP Aging (Phase 2)
**Priority**: Medium | **Complexity**: Medium | **Data Dependency**: Medium

**Business Purpose**:
Track how long jobs remain in work-in-process from start date until completion, excluding on-hold periods.

**Calculation Formula**:
```
IF status = 'ON_HOLD':
  WIP_Age = (Current_Date - Start_Date) - Total_Hold_Duration
ELSE IF status = 'ACTIVE':
  WIP_Age = Current_Date - Start_Date
ELSE IF status = 'COMPLETED':
  WIP_Age = Completion_Date - Start_Date - Total_Hold_Duration
```

**Data Requirements**:
- **Core Fields**: `work_order_id`, `actual_start_date`, `status`
- **Hold Tracking**: `hold_date`, `resume_date`, `hold_duration`
- **Filtering**: `style_model`, `part_number`, `client_id`

**Missing Data Inference Strategy**:
1. Use `planned_start_date` if `actual_start_date` missing
2. Use first production entry date if both dates missing
3. Calculate from `receipt_date + lead_time` if all else fails
4. Flag entries requiring manual review

**Dependencies**:
- `WORK_ORDER` table (core)
- `HOLD_ENTRY` table (for hold periods)
- `JOB` table (optional, for line-item granularity)

**Reporting**:
- Filters by style-model, part number, work order
- Daily/weekly/monthly aggregates
- Top 10/20 oldest jobs alert

---

### 2. On-Time Delivery (Phase 3)
**Priority**: High | **Complexity**: High | **Data Dependency**: High

**Business Purpose**:
Measure percentage of orders delivered by promised date, with strict 100% completion requirement.

**Calculation Formulas**:

**Standard OTD**:
```
OTD_% = (Orders_Delivered_On_Time / Total_Orders) × 100

WHERE:
  On_Time = actual_delivery_date <= planned_ship_date OR required_date
  Delivered = status = 'COMPLETED' AND shipped = TRUE
```

**TRUE-OTD** (100% complete requirement):
```
TRUE_OTD_% = (Complete_Orders_On_Time / Total_Complete_Orders) × 100

WHERE:
  Complete = quantity_completed = planned_quantity (no partial shipments)
  On_Time = same as above
```

**Data Requirements**:
- **Required**: `planned_ship_date` OR `required_date`
- **Critical**: `actual_delivery_date`, `status`, `quantity_completed`, `planned_quantity`
- **Validation**: Must be 100% complete (no partial shipments counted)

**Missing Data Inference Strategy**:
1. Use `required_date` if `planned_ship_date` missing
2. Calculate surrogate date: `planned_start_date + CEIL((quantity × ideal_cycle_time) / shift_hours)`
3. Use historical average lead time by `style_model` + `client_id`
4. Use industry standard lead time (configurable per client)
5. Flag as "No Promise Date - Cannot Calculate OTD"

**Dependencies**:
- `WORK_ORDER` table (dates, quantities)
- `JOB` table (line item tracking)
- `PRODUCTION_ENTRY` table (completion tracking)

**Reporting**:
- Daily/weekly/monthly OTD %
- Split by client, style-model
- Late orders with reasons

**Critical Notes**:
- Current practice: Promise dates often missing from work orders
- Paper logs updated daily at shift end
- Whiteboards currently track "guesstimates"

---

### 3. Production Efficiency (Phase 1 - MVP)
**Priority**: Critical | **Complexity**: High | **Data Dependency**: Medium

**Business Purpose**:
Estimate effective production time based on staffed line and production output. Target: 90%.

**Calculation Formula**:
```
Hours_Produced = Pieces_Produced × Standard_Time_Per_Piece
Hours_Available = (Assigned_Operators + Floating_Operators) × Shift_Hours - Downtime_Hours
Efficiency_% = (Hours_Produced / Hours_Available) × 100
```

**Data Requirements**:
- **Production**: `units_produced`, `employees_assigned`, `run_time_hours`
- **Critical**: `ideal_cycle_time` (standard time per piece)
- **Contextual**: `shift_hours_scheduled`, `downtime_total_minutes`
- **Floating Staff**: `employees_present`, `covered_by_floating_employee_id`

**Missing Data Inference Strategy**:
1. **ideal_cycle_time missing**: Use 30-day historical average by `style_model + client_id`
2. **employees_assigned missing**: Use scheduled line staffing from client configuration
3. **run_time_hours missing**: Use `shift_hours_scheduled - (downtime_total_minutes/60)`
4. **downtime missing**: Assume 0 (optimistic baseline, Phase 1 workaround)
5. **No historical data**: Use engineering estimates or industry benchmarks

**Dependencies**:
- `PRODUCTION_ENTRY` table (primary)
- `WORK_ORDER` table (`ideal_cycle_time`)
- `DOWNTIME_ENTRY` table (Phase 2+)
- `ATTENDANCE_ENTRY` table (Phase 3+, floating staff)

**Reporting**:
- Daily/shift aggregates by client
- 7-day rolling average
- Comparison to 90% target
- Alert if <80% efficiency

**Phase 1 Simplifications**:
- Assume 0 downtime (full shift hours available)
- No floating staff coverage (use `employees_assigned` only)
- Manual verification required until Phase 2/3 data integrated

**Critical Notes**:
- Numbers >100% indicate data quality issues
- Current calculations are "guesstimates"
- Automation will reveal true performance

---

### 4. Quality PPM (Phase 4)
**Priority**: Medium | **Complexity**: Low | **Data Dependency**: Low

**Business Purpose**:
Track defective units per million units produced at final inspection.

**Calculation Formula**:
```
PPM = (Total_Defects / Total_Units_Inspected) × 1,000,000

WHERE:
  Total_Defects = units_defective (from QUALITY_ENTRY)
  Total_Units_Inspected = units_inspected (from QUALITY_ENTRY)
```

**Data Requirements**:
- **Core**: `units_inspected`, `units_defective`
- **Context**: `operation_checked = 'FINAL_INSPECTION'`
- **Granularity**: Per shift, per client, per style-model

**Missing Data Inference Strategy**:
1. **No inspection data**: Assume 0 defects (optimistic, flag as "No QC Data")
2. **Sample inspection only**: Scale defects by sample % (`units_defective / sample_size_percent × 100`)
3. **Missing inspection method**: Assume 100% inspection
4. **Partial inspection**: Flag with confidence level
5. **No data**: Report as "Insufficient Quality Data"

**Dependencies**:
- `QUALITY_ENTRY` table (primary)
- `PRODUCTION_ENTRY` table (total production context)

**Reporting**:
- Daily/weekly/monthly PPM
- Trend analysis (improving or worsening)
- Comparison to industry benchmarks (e.g., <10,000 PPM good)

---

### 5. Quality DPMO (Phase 4)
**Priority**: Medium | **Complexity**: Medium | **Data Dependency**: Medium

**Business Purpose**:
Measure defects relative to number of opportunities for error, not just units.

**Calculation Formula**:
```
DPMO = (Total_Defects / (Units_Inspected × Opportunities_Per_Unit)) × 1,000,000

WHERE:
  Total_Defects = total_defects_count (from QUALITY_ENTRY)
  Opportunities_Per_Unit = from PART_OPPORTUNITIES table
  Units_Inspected = units_inspected (from QUALITY_ENTRY)
```

**Data Requirements**:
- **Core**: `total_defects_count`, `units_inspected`
- **Critical**: `opportunities_per_unit` (from `PART_OPPORTUNITIES` master table)
- **Linkage**: `part_number` must match between `JOB` and `PART_OPPORTUNITIES`

**Missing Data Inference Strategy**:
1. **opportunities_per_unit missing**: Default to 1 (same as PPM)
2. **No PART_OPPORTUNITIES record**: Use client-specific default (e.g., 10 for simple, 50 for complex)
3. **Multiple defects per unit**: Use `total_defects_count` (detailed tracking)
4. **Aggregate defects**: Use `units_defective` (simplified)
5. **No master data**: Flag as "DPMO unavailable - missing opportunities definition"

**Dependencies**:
- `QUALITY_ENTRY` table (defects)
- `PART_OPPORTUNITIES` table (master data)
- `JOB` table (part number linkage)

**Reporting**:
- Daily/weekly/monthly DPMO
- Compare to PPM (DPMO typically lower)
- Six Sigma correlation (3 sigma = 66,807 DPMO, 6 sigma = 3.4 DPMO)

---

### 6. Quality FPY & RTY (Phase 4)
**Priority**: Medium | **Complexity**: High | **Data Dependency**: High

**Business Purpose**:
Track first-pass yield and rolled throughput yield across all production stages.

**Calculation Formulas**:

**First Pass Yield (FPY)**:
```
FPY_% = (Units_Passed_First_Time / Total_Units_Processed) × 100

WHERE:
  Passed_First_Time = units_passed (no rework, no repair)
  Total_Units_Processed = units_inspected
```

**Rolled Throughput Yield (RTY)**:
```
RTY_% = FPY_Op1 × FPY_Op2 × ... × FPY_OpN

WHERE:
  Each FPY calculated per operation/stage
  RTY = Completed_Units / Total_Units_Started (across all ops)
```

**Data Requirements**:
- **FPY**: `units_passed`, `units_inspected`, `units_requiring_rework`, `units_requiring_repair`
- **RTY**: Multiple quality checks across operations (Cutting → Sewing → Assembly → QC → Packing)
- **Granularity**: Per operation, per shift, per client

**Missing Data Inference Strategy**:
1. **No rework/repair split**: Use `units_defective` (assume all failed FPY)
2. **No multi-stage tracking**: Use final inspection only (limited RTY)
3. **Partial operation data**: Calculate FPY for available ops, note gaps
4. **No quality data**: Default FPY = 100% (optimistic, flag as "No QC Data")
5. **Inconsistent staging**: Map operations to standard flow (Cutting → Sewing → Assembly → QC → Packing)

**Dependencies**:
- `QUALITY_ENTRY` table (multi-stage inspection)
- `DEFECT_DETAIL` table (rework vs repair distinction)
- `PRODUCTION_ENTRY` table (operation tracking)

**Reporting**:
- Daily FPY per operation
- Weekly RTY across all stages
- Identify bottleneck operations (lowest FPY)
- Rework volume tracking

**Critical Notes**:
- FPY fails if any rework/repair needed
- RTY multiplies FPY across stages (always ≤ lowest FPY)
- Target: >95% FPY, >90% RTY

---

### 7. Availability (Phase 2)
**Priority**: High | **Complexity**: Medium | **Data Dependency**: Medium

**Business Purpose**:
Track how much time the line/operation is actually running vs planned production time.

**Calculation Formula**:
```
Availability_% = (Uptime_Hours / (Uptime_Hours + Downtime_Hours)) × 100

Simplified:
Availability_% = ((Planned_Time - Downtime) / Planned_Time) × 100

WHERE:
  Planned_Time = shift_hours_scheduled (excludes breaks/lunch)
  Downtime = SUM(downtime_duration_minutes) / 60 (from DOWNTIME_ENTRY)
  Excludes: Scheduled breaks, lunch (not counted as downtime)
```

**Data Requirements**:
- **Core**: `shift_hours_scheduled`, `downtime_total_minutes`
- **Granularity**: Per line/cell, per shift, per client
- **Categories**: Equipment failure, material shortage, setup time, changeover, lack of orders, scheduled maintenance

**Missing Data Inference Strategy**:
1. **No downtime logged**: Assume 0 downtime (100% availability, optimistic)
2. **Partial downtime logs**: Use recorded data, flag as "Partial Data"
3. **Missing shift hours**: Use standard shift hours from client config
4. **Downtime duration missing**: Estimate from start/end times
5. **No downtime tracking**: Default to 95% (industry average, flag as estimate)

**Dependencies**:
- `DOWNTIME_ENTRY` table (primary)
- `PRODUCTION_ENTRY` table (shift hours context)
- `CLIENT` table (standard shift hours)

**Reporting**:
- Daily availability % by client
- Downtime by reason (Pareto chart)
- Impact analysis (which downtimes hurt most)
- 4-week trend

**Critical Notes**:
- Scheduled breaks/lunch NOT counted as downtime
- 0.5 hrs downtime in Op1 may not impact entire line if other ops continue
- Calculate for entire production line/cell, not individual operations

**OEE Integration**:
Availability is 1 of 3 OEE components: `OEE = Availability × Performance × Quality`

---

### 8. Performance (Phase 1 - MVP)
**Priority**: Critical | **Complexity**: High | **Data Dependency**: Medium

**Business Purpose**:
Measure how fast material flows through the line vs designed/ideal speed.

**Calculation Formula**:
```
Performance_% = (Ideal_Cycle_Time × Total_Count_Processed) / Run_Time × 100

WHERE:
  Ideal_Cycle_Time = standard time per piece (hours)
  Total_Count_Processed = units_produced
  Run_Time = shift_hours - downtime_hours (in same units as ideal_cycle_time)
```

**Data Requirements**:
- **Core**: `ideal_cycle_time`, `units_produced`, `run_time_hours`
- **Context**: `shift_hours_scheduled`, `downtime_total_minutes`
- **Granularity**: Per work order, per shift, per client, per operation

**Missing Data Inference Strategy**:
1. **ideal_cycle_time missing**: Use 30-day historical average by `style_model + client_id`
2. **run_time_hours missing**: Calculate `shift_hours_scheduled - (downtime_total_minutes/60)`
3. **units_produced = 0**: Performance = 0% (no production)
4. **downtime missing**: Assume run_time = shift_hours (Phase 1 workaround)
5. **No historical data**: Use engineering standards or client-provided benchmarks

**Dependencies**:
- `PRODUCTION_ENTRY` table (primary)
- `WORK_ORDER` table (`ideal_cycle_time`)
- `DOWNTIME_ENTRY` table (Phase 2+)

**Reporting**:
- Daily/hourly performance by client
- Comparison to 90-100% target
- Slow periods identification
- Style-model performance comparison

**Phase 1 Simplifications**:
- Assume 0 downtime (run_time = shift_hours)
- Manual validation required
- Phase 2 integration with downtime for accurate calculation

**Critical Notes**:
- Performance >100% indicates faster than ideal (possible with process improvements)
- Varies by style-model and operation
- Must use consistent time units (all hours or all minutes)

**OEE Integration**:
Performance is 1 of 3 OEE components: `OEE = Availability × Performance × Quality`

---

### 9. Production Hours by Operation (Phase 4)
**Priority**: Low | **Complexity**: Low | **Data Dependency**: Low

**Business Purpose**:
Track production hours by operation/stage (Cutting, Sewing, Assembly, QC, Packing) for daily/weekly/monthly aggregates.

**Calculation Formula**:
```
Production_Hours = SUM(run_time_hours)
  GROUP BY operation_id, shift_date, client_id

WHERE:
  operation_id IN ('CUTTING', 'SEWING', 'ASSEMBLY', 'QC', 'PACKING')
  run_time_hours = from PRODUCTION_ENTRY
```

**Data Requirements**:
- **Core**: `operation_id`, `run_time_hours`, `shift_date`
- **Aggregation**: Daily/weekly/monthly totals by operation
- **Filtering**: By client, by shift type, by date range

**Missing Data Inference Strategy**:
1. **operation_id missing**: Aggregate at line level (no per-operation breakdown)
2. **run_time_hours missing**: Use shift_hours_scheduled
3. **No operation tracking**: Use client total (aspirational for future granularity)
4. **Partial data**: Report available operations only
5. **No data**: Flag as "No Production Hours Recorded"

**Dependencies**:
- `PRODUCTION_ENTRY` table (operation_id field, currently optional)
- `CLIENT` table (standard operations mapping)

**Reporting**:
- Daily hours by operation
- Weekly/monthly aggregates
- Operation utilization %
- Bottleneck identification (which ops running most/least)

**Critical Notes**:
- Currently optional (Phase 1 tracks at line level)
- Aspirational for future granularity
- Feeds into capacity planning

**Related Metrics**:
- Feeds Production Efficiency calculation
- Feeds Availability calculation
- Feeds Performance calculation

---

### 10. Absenteeism Rate (Phase 3)
**Priority**: Medium | **Complexity**: Medium | **Data Dependency**: Medium

**Business Purpose**:
Track percentage of scheduled work time employees miss due to unscheduled absences.

**Calculation Formula**:
```
Absenteeism_% = (Total_Absence_Hours / Total_Scheduled_Hours) × 100

WHERE:
  Total_Absence_Hours = SUM(absence_hours WHERE absence_type = 'UNSCHEDULED_ABSENCE')
  Total_Scheduled_Hours = SUM(scheduled_hours FOR all_employees)

  Excludes: Vacation, medical leave (planned time off)
  Includes: Sick, no-show (unscheduled absences)
```

**Data Requirements**:
- **Core**: `scheduled_hours`, `actual_hours`, `is_absent`, `absence_type`
- **Filtering**: Unscheduled only (exclude planned time off)
- **Granularity**: Per line/cell, per shift, per client

**Missing Data Inference Strategy**:
1. **absence_hours missing**: Use `scheduled_hours - actual_hours`
2. **absence_type missing**: Assume 'UNSCHEDULED_ABSENCE' if is_absent = TRUE
3. **scheduled_hours missing**: Use standard shift hours from employee/client config
4. **actual_hours missing**: Infer from production logs (if employee recorded production, assume present)
5. **No attendance data**: Default to 5% (industry average, flag as estimate)

**Dependencies**:
- `ATTENDANCE_ENTRY` table (primary)
- `EMPLOYEE` table (scheduled hours, client assignment)
- `COVERAGE_ENTRY` table (floating staff coverage tracking)

**Reporting**:
- Daily/weekly/monthly absenteeism %
- By absence type (pie chart)
- Alert if >15% absenteeism
- Impact on production efficiency

**Critical Notes**:
- Excludes planned time off (vacation, medical leave)
- Floating staff coverage reduces effective absenteeism impact
- High absenteeism (>15%) requires investigation

**Related Metrics**:
- Impacts Production Efficiency (reduces hours available)
- Tracked alongside floating pool utilization

---

## OEE Calculation (Phase 2+)

**Overall Equipment Effectiveness** combines 3 KPIs:

```
OEE_% = Availability × Performance × Quality

WHERE:
  Availability = from KPI #7
  Performance = from KPI #8
  Quality = (units_produced - units_defective) / units_produced × 100
```

**World-Class OEE Targets**:
- 85%+ = World-class
- 60-85% = Good
- <60% = Needs improvement

**Dependencies**:
- Phase 2: Availability + Performance
- Phase 4: Quality integration

---

## Data Quality Assessment Summary

### Complete & Ready NOW
- Client/Employee master data
- Work order basic info (ID, quantity)
- Basic production counts (units produced)

### Needs Standardization
- Date formats (planned vs actual start dates)
- Ideal cycle time (often missing, requires historical averaging)
- Promise dates (planned_ship_date often absent)

### Needs New Collection
- Downtime tracking (reason, duration)
- Hold/resume workflow (approval required)
- Attendance records (daily entry)
- Quality inspection (defects, rework, repair)
- Floating pool assignments (daily updates)
- Part opportunities (engineering master data)

### Critical Gaps
1. **Missing Promise Dates**: 40-60% of work orders lack `planned_ship_date` or `required_date`
2. **No Ideal Cycle Time**: 30-50% missing, requires historical inference
3. **Paper Logs**: Current tracking on whiteboards/dry-erase boards (manual, error-prone)
4. **Inconsistent Data Collectors**: 1-5 per client, varying technical skills
5. **No Downtime Logs**: Phase 1 assumes 0 downtime (unrealistic)

---

## Implementation Priorities (Phased Approach)

### Phase 1: Core + Efficiency + Performance (Tasks 5-8)
**MVP Deliverable**: Automated production data entry with 2 KPIs

**KPIs**:
- Production Efficiency (#3)
- Performance (#8)

**Simplifications**:
- Assume 0 downtime
- No floating staff coverage
- Manual validation required

**Tables**:
- CLIENT, EMPLOYEE, USER, WORK_ORDER, JOB, PRODUCTION_ENTRY, PART_OPPORTUNITIES

**Success Criteria**:
- Data entry grid functional (manual + CSV upload)
- Efficiency & Performance calculating correctly
- Daily PDF/Excel reports generating
- Multi-tenant data isolation working

---

### Phase 2: Downtime + Availability + WIP Aging (Tasks 9-11)
**Deliverable**: Downtime tracking + OEE foundation

**KPIs**:
- Availability (#7)
- WIP Aging (#1)
- OEE calculation (Availability × Performance)

**New Tables**:
- DOWNTIME_ENTRY
- HOLD_ENTRY

**Success Criteria**:
- Downtime reasons standardized
- Hold/resume approval workflow working
- WIP aging excluding hold periods
- OEE dashboard with breakdown

---

### Phase 3: Attendance + On-Time Delivery (Tasks 12-14)
**Deliverable**: Workforce tracking + delivery performance

**KPIs**:
- On-Time Delivery (#2)
- Absenteeism (#10)

**New Tables**:
- ATTENDANCE_ENTRY
- COVERAGE_ENTRY
- FLOATING_POOL

**Success Criteria**:
- Floating staff double-billing prevention
- OTD with 100% completion requirement
- Absenteeism impact on efficiency visible
- 4-week trend analysis functional

---

### Phase 4: Quality Metrics (Tasks 15-17)
**Deliverable**: Complete quality tracking

**KPIs**:
- Quality PPM (#4)
- Quality DPMO (#5)
- Quality FPY & RTY (#6)
- Production Hours by Operation (#9)

**New Tables**:
- QUALITY_ENTRY
- DEFECT_DETAIL

**Success Criteria**:
- All 4 quality KPIs calculating
- Defect categorization working
- Rework vs repair distinction
- Per-operation tracking (aspirational)

**ALL 10 KPIs LIVE**

---

## Technology Stack Requirements

### Frontend
- Vue 3 + Vuetify 3 + Tailwind CSS
- Responsive, tablet-optimized for production floor
- Excel-like grid for copy/paste support
- Real-time validation feedback

### Backend
- FastAPI (Python)
- Data validation engine
- Business logic layer
- KPI calculation engine
- CSV parsing & bulk upload

### Database
- SQLite (local development)
- MariaDB (production, InMotion hosting)
- Multi-tenant schema design
- Proper indexing for 50+ clients, 3000+ employees

### Deployment
- Local development environment initially
- Web-based tablet interface
- Future: QR code scanning integration
- Future: API integrations with existing systems

---

## Critical Success Factors

1. **Zero Data Duplication**: Single source of truth for shared data
2. **Multi-Tenant Security**: Data isolation per client/business unit
3. **Scalability**: Handle 50+ clients, 3000+ employees, thousands of daily transactions
4. **Data Validation**: Enforce mandatory fields, reject invalid entries
5. **Audit Trails**: Track who changed what data and when
6. **Responsive UI**: Tablet-optimized for production floor use
7. **Timestamp Everything**: Enable precise analysis and troubleshooting
8. **Graceful Degradation**: Handle missing data with 5-level inference strategies

---

## Risk Mitigation Strategies

| Risk | Mitigation |
|------|-----------|
| Data quality poor | Start data collection NOW, before development |
| Floating staff tracking missing | Implement manual log NOW, system imports later |
| Missing ideal_cycle_time | Use inference as fallback, collect real data in parallel |
| Database connectivity issues | Test connectivity Week 4 before Phase 1 starts |
| Developers slow | Provide sample data & clear specs to accelerate |
| Upper management pressure | Show Friday demos - visible progress builds confidence |
| Promise dates often missing | 5-level inference strategy + manual flagging |
| Paper logs error-prone | Real-time tablet entry + validation |

---

## Next Steps for Development Team

1. **Review this requirements analysis** (understand all 10 KPIs)
2. **Read data field mapping** (see `/docs/data_field_mapping.md`)
3. **Study inference requirements** (see `/docs/inference_requirements.md`)
4. **Review test scenarios** (see `/docs/test_scenarios.md`)
5. **Begin Phase 1 implementation** (Database schema + Production Entry module)

---

**Research Complete**: All findings stored in swarm collective memory for coder and analyst agents.
