# Data Field Mapping - Complete Field → KPI → Calculation Reference

**Research Lead**: Researcher Agent
**Session ID**: swarm-1767238686161-ap0rkjkpz
**Date**: 2025-12-31

---

## Purpose

This document provides a comprehensive mapping of all database fields to their respective KPIs and calculations. Use this as a reference when implementing KPI calculation engines.

---

## Table of Contents

1. [Core Entities](#core-entities)
2. [Production Data](#production-data)
3. [Downtime & Holds](#downtime--holds)
4. [Attendance & Coverage](#attendance--coverage)
5. [Quality Tracking](#quality-tracking)
6. [KPI Cross-Reference Matrix](#kpi-cross-reference-matrix)

---

## Core Entities

### CLIENT Table
**Purpose**: Multi-tenant client/business unit configuration

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| client_id | VARCHAR(20) | YES | ALL | Data isolation, filtering |
| client_name | VARCHAR(100) | YES | Reports | Display name |
| client_contact | VARCHAR(100) | NO | - | Communication |
| client_email | VARCHAR(100) | NO | - | Report delivery |
| client_phone | VARCHAR(20) | NO | - | Escalation |
| location | VARCHAR(100) | NO | Reports | Context |
| supervisor_id | VARCHAR(20) | NO | Hold approval | Escalation chain |
| planner_id | VARCHAR(20) | NO | OTD | Promise date validation |
| engineering_id | VARCHAR(20) | NO | Quality | Spec changes |
| client_type | ENUM | NO | Billing | Piece rate vs hourly |
| timezone | VARCHAR(10) | NO | Reports | Timestamp conversion |
| is_active | BOOLEAN | YES | ALL | Filter inactive clients |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |

---

### WORK_ORDER Table
**Purpose**: Job tracking, dates, quantities, style-model, part number

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| work_order_id | VARCHAR(50) | YES | ALL | Primary key, tracking |
| client_id_fk | VARCHAR(20) | YES | ALL | Data isolation |
| style_model | VARCHAR(100) | NO | Efficiency, Performance | Grouping, filtering |
| planned_quantity | INT | YES | OTD | Completion % |
| planned_start_date | DATE | NO | WIP Aging, OTD | Fallback for actual_start_date |
| actual_start_date | DATE | NO | WIP Aging | **Start of aging clock** |
| planned_ship_date | DATE | CONDITIONAL | **OTD** | **Promise date (primary)** |
| required_date | DATE | NO | **OTD** | **Promise date (fallback)** |
| ideal_cycle_time | DECIMAL | CONDITIONAL | **Efficiency, Performance, OTD** | **Standard time per unit** |
| status | ENUM | YES | **WIP Aging** | **ON_HOLD pauses aging** |
| receipt_date | DATE | NO | OTD | Lead time analysis |
| acknowledged_date | DATE | NO | OTD | Planning cycle time |
| priority_level | ENUM | NO | Reports | Sorting, escalation |
| po_number | VARCHAR(50) | NO | Traceability | Customer reference |
| notes | TEXT | NO | Context | Special requirements |
| created_by | VARCHAR(20) | NO | Audit | Record creator |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |

**Critical Fields for KPI Calculations**:
- `actual_start_date`: WIP aging start
- `planned_ship_date` OR `required_date`: OTD promise date
- `ideal_cycle_time`: Efficiency & Performance standard
- `status`: Hold tracking for WIP aging

---

### JOB Table
**Purpose**: Line items within work orders (granular tracking)

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| job_id | VARCHAR(50) | YES | ALL | Line item tracking |
| work_order_id_fk | VARCHAR(50) | YES | ALL | Parent work order |
| job_number | VARCHAR(50) | NO | Traceability | Customer reference |
| part_number | VARCHAR(50) | YES | **DPMO** | **Link to PART_OPPORTUNITIES** |
| quantity_ordered | INT | YES | OTD | Job size |
| quantity_completed | INT | NO | OTD, FPY, RTY | Completion tracking |
| quantity_scrapped | INT | NO | Quality | Scrap rate |
| priority_level | ENUM | NO | Reports | Sorting |
| notes | TEXT | NO | Context | Special requirements |

**Critical Fields for KPI Calculations**:
- `part_number`: Links to PART_OPPORTUNITIES for DPMO
- `quantity_completed`: OTD 100% completion requirement
- `quantity_scrapped`: Quality analysis

---

### EMPLOYEE Table
**Purpose**: Staff directory (3000+ employees), floating pool tracking

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| employee_id | VARCHAR(20) | YES | ALL | Primary key |
| employee_name | VARCHAR(100) | YES | Reports | Display name |
| department | VARCHAR(50) | NO | Reports | Filtering |
| is_floating_pool | BOOLEAN | YES | **Efficiency, Absenteeism** | **Coverage tracking** |
| is_support_billed | BOOLEAN | YES | Billing | Non-operational hours |
| is_support_included | BOOLEAN | YES | Billing | Shared resource |
| client_id_assigned | VARCHAR(20) | NO | Efficiency | Primary assignment |
| hourly_rate | DECIMAL(10,2) | NO | Cost | Billing/cost tracking |
| is_active | BOOLEAN | YES | ALL | Filter inactive |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |

**Critical Fields for KPI Calculations**:
- `is_floating_pool`: Identifies shared resources for coverage
- `client_id_assigned`: Links to primary work center

---

### FLOATING_POOL Table
**Purpose**: Track availability changes for floating staff

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| floating_pool_id | VARCHAR(50) | YES | Efficiency | Assignment tracking |
| employee_id_fk | VARCHAR(20) | YES | Efficiency, Absenteeism | Link to EMPLOYEE |
| status | ENUM | YES | **Efficiency** | **AVAILABLE vs ASSIGNED** |
| assigned_to_client | VARCHAR(20) | NO | **Efficiency** | **Current assignment** |
| assigned_by_user_id | VARCHAR(20) | NO | Audit | Assignment authority |
| last_updated_at | TIMESTAMP | YES | Audit | Staleness check |
| notes | TEXT | NO | Context | Assignment reason |

**Critical Fields for KPI Calculations**:
- `status`: Current availability
- `assigned_to_client`: Where floating employee is working

---

### USER Table
**Purpose**: System accounts & authentication

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| user_id | VARCHAR(20) | YES | Audit | Primary key |
| username | VARCHAR(50) | YES | Audit | Login |
| full_name | VARCHAR(100) | YES | Reports | Display name |
| email | VARCHAR(100) | NO | Reports | Email delivery |
| role | ENUM | YES | Permissions | OPERATOR, LEADER, POWERUSER, ADMIN |
| client_id_assigned | VARCHAR(20) | NO | Permissions | Data access |
| is_active | BOOLEAN | YES | ALL | Filter inactive |
| last_login | TIMESTAMP | NO | Audit | Activity tracking |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |

---

### PART_OPPORTUNITIES Table
**Purpose**: Defect opportunities per unit for DPMO calculation

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| part_number | VARCHAR(50) | YES | **DPMO** | **Primary key, links to JOB** |
| opportunities_per_unit | INT | YES | **DPMO** | **Defect opportunities** |
| description | VARCHAR(200) | NO | Quality | Opportunity breakdown |
| updated_by | VARCHAR(20) | NO | Audit | Engineering/Quality |
| updated_at | TIMESTAMP | YES | Audit | Spec change tracking |

**Critical Fields for KPI Calculations**:
- `opportunities_per_unit`: DPMO denominator

**DPMO Formula**:
```
DPMO = (Total_Defects / (Units_Inspected × opportunities_per_unit)) × 1,000,000
```

---

## Production Data

### PRODUCTION_ENTRY Table
**Purpose**: Units produced, defects, run time, operation/stage

**KPIs Using This Table**: Efficiency (#3), Performance (#8), Production Hours (#9), Quality (context)

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| production_entry_id | VARCHAR(50) | YES | ALL | Primary key |
| work_order_id_fk | VARCHAR(50) | YES | ALL | Link to WORK_ORDER |
| job_id_fk | VARCHAR(50) | NO | ALL | Line item tracking |
| client_id_fk | VARCHAR(20) | YES | ALL | Data isolation |
| shift_date | DATE | YES | **ALL** | **Daily aggregation** |
| shift_type | ENUM | YES | Reports | SHIFT_1ST, SHIFT_2ND, SAT_OT, SUN_OT, OTHER |
| operation_id | VARCHAR(50) | NO | **Production Hours (#9)** | **Per-operation tracking** |
| units_produced | INT | YES | **Efficiency, Performance, Quality** | **Total output** |
| units_defective | INT | YES | Quality | Defects for PPM/DPMO/FPY/RTY |
| run_time_hours | DECIMAL(10,2) | YES | **Efficiency, Performance** | **Actual production time** |
| employees_assigned | INT | YES | **Efficiency** | **Staffing level** |
| employees_present | INT | NO | Absenteeism | Actual attendance |
| data_collector_id | VARCHAR(20) | YES | Audit | Data source |
| entry_method | ENUM | NO | Audit | MANUAL_ENTRY, CSV_UPLOAD, QR_SCAN, API |
| timestamp | TIMESTAMP | NO | Analysis | Hourly tracking |
| verified_by | VARCHAR(20) | NO | Audit | Supervisor approval |
| verified_at | TIMESTAMP | NO | Audit | Approval timestamp |
| notes | TEXT | NO | Context | Special conditions |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |
| shift_hours_scheduled | DECIMAL(10,2) | NO | Efficiency, Performance | Standard shift hours |
| downtime_total_minutes | INT | NO | Efficiency, Performance, Availability | Downtime summary |
| efficiency_target | DECIMAL(5,2) | NO | Efficiency | Comparison target (90%) |
| performance_target | DECIMAL(5,2) | NO | Performance | Comparison target (90%) |

**Critical Fields for KPI Calculations**:

**Efficiency (#3)**:
```
Hours_Produced = units_produced × ideal_cycle_time (from WORK_ORDER)
Hours_Available = employees_assigned × shift_hours_scheduled - (downtime_total_minutes/60)
Efficiency_% = (Hours_Produced / Hours_Available) × 100
```

**Performance (#8)**:
```
Performance_% = (ideal_cycle_time × units_produced) / run_time_hours × 100
```

**Production Hours (#9)**:
```
Production_Hours = SUM(run_time_hours) GROUP BY operation_id, shift_date, client_id
```

---

## Downtime & Holds

### DOWNTIME_ENTRY Table
**Purpose**: Equipment failure, material shortage, setup time tracking

**KPIs Using This Table**: Availability (#7), Efficiency (#3), Performance (#8)

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| downtime_entry_id | VARCHAR(50) | YES | ALL | Primary key |
| work_order_id_fk | VARCHAR(50) | YES | ALL | Affected job |
| client_id_fk | VARCHAR(20) | YES | ALL | Data isolation |
| shift_date | DATE | YES | **Availability** | **Daily aggregation** |
| shift_type | ENUM | YES | Reports | Shift identification |
| downtime_reason | ENUM | YES | **Availability** | **Categorization** |
| downtime_reason_detail | TEXT | NO | Analysis | Detailed explanation |
| downtime_duration_minutes | INT | YES | **Availability, Efficiency, Performance** | **Downtime amount** |
| downtime_start_time | TIME | NO | Analysis | Hourly tracking |
| responsible_person_id | VARCHAR(20) | NO | Escalation | Accountability |
| reported_by_user_id | VARCHAR(20) | YES | Audit | Data collector |
| reported_at | TIMESTAMP | YES | Audit | Log timestamp |
| is_resolved | BOOLEAN | NO | Escalation | Ongoing flag |
| resolution_notes | TEXT | NO | Analysis | How resolved |
| impact_on_wip_hours | DECIMAL(10,2) | NO | Analysis | WIP impact |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |

**Critical Fields for KPI Calculations**:

**Availability (#7)**:
```
Availability_% = ((Planned_Time - SUM(downtime_duration_minutes)/60) / Planned_Time) × 100

WHERE:
  Planned_Time = shift_hours_scheduled
  Downtime reasons: EQUIPMENT_FAILURE, MATERIAL_SHORTAGE, CHANGEOVER_SETUP,
                   LACK_OF_ORDERS, MAINTENANCE_SCHEDULED, QC_HOLD,
                   MISSING_SPECIFICATION, OTHER
```

**Efficiency & Performance Impact**:
- Downtime reduces Hours_Available
- Downtime reduces Run_Time

---

### HOLD_ENTRY Table
**Purpose**: WIP on hold tracking & resume workflow

**KPIs Using This Table**: WIP Aging (#1)

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| hold_entry_id | VARCHAR(50) | YES | WIP Aging | Primary key |
| work_order_id_fk | VARCHAR(50) | YES | **WIP Aging** | **Affected job** |
| job_id_fk | VARCHAR(50) | NO | WIP Aging | Line item (optional) |
| client_id_fk | VARCHAR(20) | YES | ALL | Data isolation |
| hold_status | ENUM | YES | **WIP Aging** | **ON_HOLD, RESUMED, CANCELLED** |
| hold_date | DATE | YES | **WIP Aging** | **Hold start** |
| hold_time | TIME | NO | Analysis | Hourly tracking |
| hold_reason | ENUM | YES | Analysis | Categorization |
| hold_reason_detail | TEXT | YES | Analysis | Detailed explanation |
| hold_approved_by_user_id | VARCHAR(20) | YES | Audit | Approval authority |
| hold_approved_at | TIMESTAMP | YES | Audit | Approval timestamp |
| resume_date | DATE | NO | **WIP Aging** | **Hold end** |
| resume_time | TIME | NO | Analysis | Hourly tracking |
| resume_approved_by_user_id | VARCHAR(20) | NO | Audit | Resume authority |
| resume_approved_at | TIMESTAMP | NO | Audit | Resume timestamp |
| total_hold_duration_hours | DECIMAL(10,2) | NO | **WIP Aging** | **Duration to subtract** |
| hold_notes | TEXT | NO | Context | Additional info |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |

**Critical Fields for KPI Calculations**:

**WIP Aging (#1)**:
```
IF hold_status = 'ON_HOLD':
  WIP_Age = (Current_Date - actual_start_date) - SUM(total_hold_duration_hours)/24
ELSE IF hold_status = 'RESUMED':
  WIP_Age = (Current_Date - actual_start_date) - SUM(total_hold_duration_hours WHERE hold_status = 'RESUMED')/24
ELSE:
  WIP_Age = Current_Date - actual_start_date

Hold reasons: MATERIAL_INSPECTION, QUALITY_ISSUE, ENGINEERING_REVIEW,
              CUSTOMER_REQUEST, MISSING_SPECIFICATION, EQUIPMENT_UNAVAILABLE,
              CAPACITY_CONSTRAINT, OTHER
```

---

## Attendance & Coverage

### ATTENDANCE_ENTRY Table
**Purpose**: Scheduled vs actual hours, absence types

**KPIs Using This Table**: Absenteeism (#10), Efficiency (#3)

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| attendance_entry_id | VARCHAR(50) | YES | ALL | Primary key |
| employee_id_fk | VARCHAR(20) | YES | **Absenteeism** | **Employee tracking** |
| client_id_fk | VARCHAR(20) | YES | ALL | Data isolation |
| shift_date | DATE | YES | **Absenteeism** | **Daily aggregation** |
| shift_type | ENUM | YES | Reports | Shift identification |
| scheduled_hours | DECIMAL(10,2) | YES | **Absenteeism** | **Denominator** |
| actual_hours | DECIMAL(10,2) | NO | Efficiency | Hours worked |
| is_absent | BOOLEAN | YES | **Absenteeism** | **Absence flag** |
| absence_type | ENUM | CONDITIONAL | **Absenteeism** | **UNSCHEDULED_ABSENCE only** |
| absence_hours | DECIMAL(10,2) | CONDITIONAL | **Absenteeism** | **Numerator** |
| covered_by_floating_employee_id | VARCHAR(20) | NO | **Efficiency** | **Coverage tracking** |
| coverage_confirmed | BOOLEAN | NO | Audit | Verification flag |
| recorded_by_user_id | VARCHAR(20) | YES | Audit | Data collector |
| recorded_at | TIMESTAMP | YES | Audit | Log timestamp |
| verified_by_user_id | VARCHAR(20) | NO | Audit | Supervisor approval |
| verified_at | TIMESTAMP | NO | Audit | Approval timestamp |
| notes | TEXT | NO | Context | Additional info |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |

**Critical Fields for KPI Calculations**:

**Absenteeism (#10)**:
```
Absenteeism_% = (Total_Absence_Hours / Total_Scheduled_Hours) × 100

WHERE:
  Total_Absence_Hours = SUM(absence_hours WHERE absence_type = 'UNSCHEDULED_ABSENCE')
  Total_Scheduled_Hours = SUM(scheduled_hours)

  Excludes: VACATION, MEDICAL_LEAVE (planned)
  Includes: UNSCHEDULED_ABSENCE, sick, no-show
```

**Efficiency Impact**:
- Absence reduces effective employees_assigned
- Floating coverage mitigates impact

---

### COVERAGE_ENTRY Table
**Purpose**: Floating pool employee providing coverage (prevent double-billing)

**KPIs Using This Table**: Efficiency (#3), Absenteeism (#10)

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| coverage_entry_id | VARCHAR(50) | YES | ALL | Primary key |
| absent_employee_id | VARCHAR(20) | YES | Efficiency | Original position |
| floating_employee_id | VARCHAR(20) | YES | **Efficiency** | **Coverage provider** |
| client_id_fk | VARCHAR(20) | YES | ALL | Data isolation |
| shift_date | DATE | YES | **Efficiency** | **Daily tracking** |
| shift_type | ENUM | YES | Reports | Shift identification |
| coverage_duration_hours | DECIMAL(10,2) | YES | **Efficiency** | **Coverage amount** |
| recorded_by_user_id | VARCHAR(20) | YES | Audit | Supervisor |
| recorded_at | TIMESTAMP | YES | Audit | Log timestamp |
| verified | BOOLEAN | NO | Audit | Confirmation flag |
| notes | TEXT | NO | Context | Additional info |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |

**Critical Fields for KPI Calculations**:

**Efficiency (#3)** - Floating Staff Integration:
```
Hours_Available = (employees_assigned - COUNT(absent) + COUNT(floating_coverage)) × shift_hours_scheduled - downtime

WHERE:
  absent = is_absent = TRUE AND covered_by_floating_employee_id IS NULL
  floating_coverage = covered_by_floating_employee_id IS NOT NULL
```

**Double-Billing Prevention**:
- Same `floating_employee_id` cannot have 2+ COVERAGE_ENTRY records for same `shift_date + shift_type`

---

## Quality Tracking

### QUALITY_ENTRY Table
**Purpose**: Defects, repair/rework tracking, quality checks

**KPIs Using This Table**: PPM (#4), DPMO (#5), FPY (#6), RTY (#7)

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| quality_entry_id | VARCHAR(50) | YES | ALL | Primary key |
| work_order_id_fk | VARCHAR(50) | YES | ALL | Link to WORK_ORDER |
| job_id_fk | VARCHAR(50) | NO | ALL | Line item (optional) |
| client_id_fk | VARCHAR(20) | YES | ALL | Data isolation |
| shift_date | DATE | YES | **ALL Quality KPIs** | **Daily aggregation** |
| shift_type | ENUM | YES | Reports | Shift identification |
| operation_checked | VARCHAR(50) | YES | **FPY, RTY** | **Stage identification** |
| units_inspected | INT | YES | **PPM, DPMO, FPY, RTY** | **Denominator** |
| units_passed | INT | YES | **FPY, RTY** | **No defects, no rework** |
| units_defective | INT | YES | **PPM** | **Total defects** |
| units_requiring_rework | INT | NO | **FPY, RTY** | **Return to previous op** |
| units_requiring_repair | INT | NO | **FPY, RTY** | **Repair in current op** |
| defect_categories | TEXT | NO | Analysis | Categorized defects |
| total_defects_count | INT | YES | **DPMO** | **Individual defects (>= units_defective)** |
| qc_inspector_id | VARCHAR(20) | YES | Audit | Inspector |
| recorded_by_user_id | VARCHAR(20) | YES | Audit | Data collector |
| recorded_at | TIMESTAMP | YES | Audit | Log timestamp |
| inspection_method | ENUM | NO | Analysis | VISUAL, MEASUREMENT, FUNCTIONAL_TEST, SAMPLE_CHECK, 100_PERCENT_INSPECTION |
| sample_size_percent | DECIMAL(5,2) | NO | Analysis | Sample % if SAMPLE_CHECK |
| notes | TEXT | NO | Context | Additional info |
| verified_by_user_id | VARCHAR(20) | NO | Audit | Supervisor approval |
| verified_at | TIMESTAMP | NO | Audit | Approval timestamp |
| created_at | TIMESTAMP | YES | Audit | Record creation |
| updated_at | TIMESTAMP | YES | Audit | Record modification |

**Critical Fields for KPI Calculations**:

**PPM (#4)**:
```
PPM = (units_defective / units_inspected) × 1,000,000
```

**DPMO (#5)**:
```
DPMO = (total_defects_count / (units_inspected × opportunities_per_unit)) × 1,000,000

WHERE:
  opportunities_per_unit = from PART_OPPORTUNITIES table (linked by part_number)
```

**FPY (#6)**:
```
FPY_% = (units_passed / units_inspected) × 100

WHERE:
  units_passed = no rework, no repair
```

**RTY (#7)**:
```
RTY_% = FPY_Op1 × FPY_Op2 × ... × FPY_OpN

OR simplified:

RTY_% = (Completed_Units / Total_Units_Started) × 100
```

---

### DEFECT_DETAIL Table
**Purpose**: Granular defect tracking (individual defects)

**KPIs Using This Table**: DPMO (#5), FPY (#6), RTY (#7), Quality Analysis

| Field | Type | Required | KPI Usage | Calculation Role |
|-------|------|----------|-----------|------------------|
| defect_detail_id | VARCHAR(50) | YES | ALL | Primary key |
| quality_entry_id_fk | VARCHAR(50) | YES | ALL | Link to QUALITY_ENTRY |
| defect_type | ENUM | YES | **Analysis** | **STITCHING, COLOR_MISMATCH, SIZING, MATERIAL_DEFECT, ASSEMBLY, FINISHING, PACKAGING, OTHER** |
| defect_description | TEXT | YES | Analysis | Detailed description |
| unit_serial_or_id | VARCHAR(50) | NO | Traceability | Individual unit tracking |
| is_rework_required | BOOLEAN | YES | **FPY, RTY** | **Return to previous op** |
| is_repair_in_current_op | BOOLEAN | YES | **FPY, RTY** | **Repair here** |
| is_scrapped | BOOLEAN | NO | Quality | Scrap rate |
| root_cause | ENUM | NO | Analysis | OPERATOR_ERROR, MATERIAL_ISSUE, EQUIPMENT_ISSUE, PROCESS_ISSUE, DESIGN_ISSUE, UNKNOWN |
| created_at | TIMESTAMP | YES | Audit | Record creation |

**Critical Fields for KPI Calculations**:

**DPMO (#5)** - Detailed Defects:
```
total_defects_count = COUNT(defect_detail_id) WHERE quality_entry_id_fk = quality_entry_id
```

**FPY/RTY (#6, #7)** - Rework vs Repair:
```
units_passed = units_inspected - COUNT(DISTINCT unit_serial_or_id WHERE is_rework_required = TRUE OR is_repair_in_current_op = TRUE)
```

---

## KPI Cross-Reference Matrix

### Quick Lookup: Which Tables Feed Which KPIs

| KPI | Primary Tables | Secondary Tables | Critical Fields |
|-----|----------------|------------------|-----------------|
| **#1 WIP Aging** | WORK_ORDER, HOLD_ENTRY | JOB | actual_start_date, hold_date, resume_date, status |
| **#2 On-Time Delivery** | WORK_ORDER, JOB | PRODUCTION_ENTRY | planned_ship_date, required_date, quantity_completed, planned_quantity |
| **#3 Efficiency** | PRODUCTION_ENTRY, WORK_ORDER | DOWNTIME_ENTRY, ATTENDANCE_ENTRY, COVERAGE_ENTRY | units_produced, ideal_cycle_time, employees_assigned, run_time_hours |
| **#4 PPM** | QUALITY_ENTRY, PRODUCTION_ENTRY | - | units_defective, units_inspected |
| **#5 DPMO** | QUALITY_ENTRY, PART_OPPORTUNITIES | DEFECT_DETAIL | total_defects_count, units_inspected, opportunities_per_unit |
| **#6 FPY** | QUALITY_ENTRY | DEFECT_DETAIL | units_passed, units_inspected, units_requiring_rework, units_requiring_repair |
| **#7 RTY** | QUALITY_ENTRY (multi-stage) | DEFECT_DETAIL | units_passed per operation, operation_checked |
| **#8 Availability** | DOWNTIME_ENTRY, PRODUCTION_ENTRY | - | downtime_duration_minutes, shift_hours_scheduled |
| **#9 Performance** | PRODUCTION_ENTRY, WORK_ORDER | DOWNTIME_ENTRY | ideal_cycle_time, units_produced, run_time_hours |
| **#10 Production Hours** | PRODUCTION_ENTRY | - | run_time_hours, operation_id, shift_date |
| **#11 Absenteeism** | ATTENDANCE_ENTRY | COVERAGE_ENTRY | scheduled_hours, absence_hours, is_absent, absence_type |
| **OEE** | Combines #8 Availability, #9 Performance, Quality from #4-7 | - | OEE = Availability × Performance × Quality |

---

## Data Flow Diagrams

### Production Efficiency (#3) Data Flow

```
WORK_ORDER
  └── ideal_cycle_time ──┐
                         │
PRODUCTION_ENTRY         ├──> Efficiency Calculation
  ├── units_produced ────┤
  ├── employees_assigned ┤
  └── run_time_hours ────┤
                         │
DOWNTIME_ENTRY           │
  └── downtime_duration_minutes ──> (reduces Hours_Available)
                         │
ATTENDANCE_ENTRY         │
  └── is_absent ─────────┤
                         │
COVERAGE_ENTRY           │
  └── floating_employee_id ──> (restores Hours_Available)
```

**Formula**:
```
Hours_Produced = units_produced × ideal_cycle_time
Hours_Available = (employees_assigned - absent + floating) × shift_hours - downtime
Efficiency_% = (Hours_Produced / Hours_Available) × 100
```

---

### On-Time Delivery (#2) Data Flow

```
WORK_ORDER
  ├── planned_ship_date ──┐
  ├── required_date ──────┤
  ├── planned_quantity ───┤
  ├── planned_start_date ─┤
  └── ideal_cycle_time ───┤
                          │
JOB                       ├──> OTD Calculation
  └── quantity_completed ─┤
                          │
PRODUCTION_ENTRY          │
  └── shift_date ─────────┘ (actual delivery date)
```

**Formula**:
```
OTD_% = (Orders_On_Time / Total_Orders) × 100

WHERE:
  On_Time = actual_delivery_date <= (planned_ship_date OR required_date OR surrogate_date)
  Surrogate_Date = planned_start_date + CEIL((quantity × ideal_cycle_time) / shift_hours)
```

---

### Quality DPMO (#5) Data Flow

```
PART_OPPORTUNITIES
  └── opportunities_per_unit ──┐
                               │
JOB                            │
  └── part_number ─────────────┤
                               │
QUALITY_ENTRY                  ├──> DPMO Calculation
  ├── total_defects_count ─────┤
  └── units_inspected ─────────┤
                               │
DEFECT_DETAIL (optional)       │
  └── COUNT(defect_detail_id) ─┘ (detailed tracking)
```

**Formula**:
```
DPMO = (total_defects_count / (units_inspected × opportunities_per_unit)) × 1,000,000
```

---

### WIP Aging (#1) Data Flow

```
WORK_ORDER
  ├── actual_start_date ──┐
  ├── status ─────────────┤
  └── work_order_id ──────┤
                          │
HOLD_ENTRY                ├──> WIP Aging Calculation
  ├── hold_date ──────────┤
  ├── resume_date ────────┤
  ├── hold_status ────────┤
  └── total_hold_duration_hours ─┘
```

**Formula**:
```
IF status = 'ON_HOLD':
  WIP_Age = (Current_Date - actual_start_date) - SUM(total_hold_duration_hours)/24
ELSE IF status = 'ACTIVE':
  WIP_Age = Current_Date - actual_start_date
ELSE IF status = 'COMPLETED':
  WIP_Age = Completion_Date - actual_start_date - SUM(total_hold_duration_hours)/24
```

---

## Implementation Notes for Developers

### 1. Field Validation Rules

**Required Fields** (cannot be NULL):
- All `_id` primary keys
- All `client_id_fk` foreign keys (multi-tenant security)
- All `shift_date` fields (temporal tracking)
- All quantity/count fields (production/quality data)

**Conditional Required**:
- `planned_ship_date` OR `required_date` (OTD needs promise date)
- `ideal_cycle_time` (Efficiency/Performance need standard time)
- `absence_hours` IF `is_absent = TRUE`
- `resume_date` IF `hold_status = 'RESUMED'`

**Timestamp Auto-Generation**:
- `created_at` = NOW() on INSERT
- `updated_at` = NOW() on UPDATE

---

### 2. Data Integrity Constraints

**Foreign Keys**:
- All `*_fk` fields must reference existing records
- Cascade deletes NOT allowed (use `is_active = FALSE`)
- Orphan prevention (cannot delete parent with children)

**Uniqueness**:
- `work_order_id` UNIQUE per client
- `employee_id` UNIQUE globally
- `user_id` UNIQUE globally
- `username` UNIQUE globally

**Check Constraints**:
- `planned_quantity > 0`
- `units_produced >= 0`
- `units_defective <= units_inspected`
- `units_passed <= units_inspected`
- `downtime_duration_minutes >= 0`
- `absence_hours >= 0`
- `efficiency_% >= 0` (but >100% indicates data quality issue)

---

### 3. Indexing Strategy

**Primary Indexes** (for performance at scale):
- `client_id_fk` (multi-tenant isolation)
- `shift_date` (temporal queries)
- `work_order_id_fk` (job tracking)
- `employee_id_fk` (attendance/coverage)
- `part_number` (quality tracking)

**Composite Indexes**:
- `(client_id, shift_date)` - daily reports
- `(work_order_id, shift_date)` - job progress
- `(client_id, shift_date, shift_type)` - shift-level aggregation
- `(employee_id, shift_date)` - attendance tracking
- `(floating_employee_id, shift_date, shift_type)` - double-billing prevention

---

### 4. Missing Data Handling

**5-Level Inference Strategy** (see `/docs/inference_requirements.md`):
1. Primary field (e.g., `planned_ship_date`)
2. Fallback field (e.g., `required_date`)
3. Calculated surrogate (e.g., `planned_start_date + lead_time`)
4. Historical average (e.g., 30-day avg `ideal_cycle_time` by `style_model`)
5. Default/flag (e.g., industry standard or "Insufficient Data")

**Flagging Strategy**:
- Store inferred values with metadata flag
- Track confidence level (high/medium/low)
- Report data quality metrics (% complete, % inferred, % missing)

---

## Next Steps

1. **Review inference requirements** (`/docs/inference_requirements.md`)
2. **Study test scenarios** (`/docs/test_scenarios.md`)
3. **Begin database schema design** (SQLite for dev, MariaDB for prod)
4. **Implement KPI calculation engines** (refer to formulas above)
5. **Create validation rules** (enforce data integrity)

---

**Complete Data Field Mapping**: Ready for development team handoff.
