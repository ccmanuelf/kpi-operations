# KPI Operations Domain Model

## Executive Summary

This document defines the domain boundaries, entity relationships, and ubiquitous language for the KPI Operations platform. It serves as the authoritative reference for domain semantics and business rules.

---

## Bounded Contexts

### 1. Production Context
**Purpose**: Track manufacturing output and efficiency metrics.

**Core Entities**:
- `ProductionEntry` - Records units produced per shift
- `Product` - Product definitions with ideal cycle times
- `Shift` - Shift definitions with scheduled hours

**Key Metrics**:
- Efficiency (KPI #3)
- Performance (KPI #9)
- Quality Rate

### 2. Quality Context
**Purpose**: Track quality inspections and defect metrics.

**Core Entities**:
- `QualityEntry` - Inspection records with defect data
- `DefectTypeCatalog` - Client-specific defect definitions
- `DefectDetail` - Individual defect instances

**Key Metrics**:
- PPM (Parts Per Million)
- DPMO (Defects Per Million Opportunities)
- FPY (First Pass Yield)
- RTY (Rolled Throughput Yield)

### 3. Work Order Context
**Purpose**: Manage work order lifecycle and workflow.

**Core Entities**:
- `WorkOrder` - Customer orders with status tracking
- `Job` - Line items within work orders
- `WorkflowTransitionLog` - Audit trail of status changes
- `HoldEntry` - Hold records with duration tracking

**Key Metrics**:
- WIP Aging
- On-Time Delivery (OTD)
- Cycle Time

### 4. Workforce Context
**Purpose**: Track employee assignments and attendance.

**Core Entities**:
- `Employee` - Staff directory
- `CoverageEntry` - Floating pool assignments
- `AttendanceEntry` - Daily attendance records

**Key Metrics**:
- Absenteeism Rate
- Coverage Utilization

---

## Production vs Quality Field Semantics

### CRITICAL: Understanding Defect Fields

The platform has **two sources of defect data** that serve different purposes:

#### ProductionEntry Defect Fields (Operator-Reported)
| Field | Description | Source |
|-------|-------------|--------|
| `defect_count` | Defects observed during production | Operator at workstation |
| `scrap_count` | Units scrapped during production | Operator at workstation |
| `rework_count` | Units requiring rework during production | Operator at workstation |

**Characteristics**:
- Real-time during production
- May include quick fixes that don't reach QC
- Represents production team's view of quality
- Used for production efficiency calculations

#### QualityEntry Defect Fields (Inspector-Verified)
| Field | Description | Source |
|-------|-------------|--------|
| `units_defective` | Units failing inspection | QC inspector |
| `total_defects_count` | Total defect instances found | QC inspector |
| `units_scrapped` | Units scrapped after inspection | QC inspector |
| `units_reworked` | Units sent to rework after inspection | QC inspector |

**Characteristics**:
- Formal inspection checkpoint
- Verified by QC personnel
- **Authoritative for quality KPIs**
- Used for PPM, DPMO, FPY, RTY calculations

### Reconciliation Rule

> **QualityEntry is the authoritative source for quality KPIs.**
>
> ProductionEntry defect counts may differ from QualityEntry because:
> 1. Some production defects are fixed in-line (never reach QC)
> 2. QC may find additional defects not visible during production
> 3. Different inspection criteria may apply

A reconciliation endpoint is available at `GET /api/reconciliation/production-quality` to compare these sources and identify discrepancies.

---

## WIP Aging and Hold Duration

### Business Rule: Hold Duration Exclusion

**Rule**: When calculating WIP aging, **all hold durations are excluded** from the aging calculation.

**Rationale**: Work orders on hold are not actively progressing. Including hold time would unfairly penalize orders for factors outside production control.

**Implementation**:
- `HoldEntry` records start/end times for each hold
- `calculate_wip_aging()` sums hold durations and subtracts from elapsed time
- All hold reasons receive equal treatment (no exceptions)

**Example**:
```
Work Order received: Jan 1
Work Order completed: Jan 10
Hold periods: Jan 3-5 (awaiting materials), Jan 7-8 (customer request)

Raw elapsed: 10 days
Hold duration: 2 + 1 = 3 days
WIP aging: 10 - 3 = 7 days
```

---

## QC Approval as Final Gate

### Business Rule: SHIPPED Requires QC Approval

**Rule**: A work order cannot transition to `SHIPPED` status unless `qc_approved = 1`.

**Workflow**:
1. Work order reaches `COMPLETED` status
2. QC inspection is performed
3. QC approves via `POST /api/work-orders/{id}/approve-qc`
4. Work order can now transition to `SHIPPED`

**Audit Trail**:
- QC approval creates a `WorkflowTransitionLog` entry with event type `QC_APPROVED`
- Captures: `qc_approved_by`, `qc_approved_date`, `notes`

---

## Defect Type Sharing

### Client-Specific vs Shared Defect Types

**Client-Specific Defect Types** (`DefectTypeCatalog`):
- Defined per client
- Custom codes and names
- Client isolation enforced

**Shared Defect Types** (`SharedDefectType`):
- System-default industry-standard defects
- Available to all clients
- Cannot be modified by clients

**Usage Priority**:
1. Client looks up in their `DefectTypeCatalog` first
2. If not found, check `SharedDefectType` table
3. Return "Unknown" if neither contains the code

---

## Part Opportunities (DPMO)

### Opportunities Per Unit Lookup

DPMO calculation requires knowing how many defect opportunities exist per unit.

**Lookup Order**:
1. `PART_OPPORTUNITIES` table (part-specific value)
2. Client configuration (`dpmo_opportunities_default`)
3. System default (10 opportunities per unit)

**Table**: `PART_OPPORTUNITIES`
| Field | Description |
|-------|-------------|
| `part_number` | Part number (unique per client) |
| `opportunities_per_unit` | Number of defect opportunities |
| `client_id_fk` | Client ID for isolation |

---

## Ubiquitous Language

| Term | Definition |
|------|------------|
| **Efficiency** | (units × cycle_time) / (employees × scheduled_hours) × 100 |
| **Performance** | (cycle_time × units) / run_time × 100 |
| **Quality Rate** | (good_units / total_units) × 100 |
| **OEE** | Availability × Performance × Quality |
| **PPM** | Parts Per Million = (defects / inspected) × 1,000,000 |
| **DPMO** | Defects Per Million Opportunities |
| **Sigma Level** | Quality level derived from DPMO (1-6) |
| **FPY** | First Pass Yield - units passing first time |
| **RTY** | Rolled Throughput Yield - product of FPYs across stages |
| **WIP** | Work In Progress |
| **Floating Pool** | Employees who can work across multiple clients |
| **Coverage Entry** | Record of floating pool employee assignment |
| **Hold** | Temporary pause in work order progress |
| **Inference** | Using historical data when explicit values are missing |
| **ESTIMATED Flag** | Indicates KPI used inferred values |

---

## Entity Relationships

```
CLIENT (1) ─────────< (*) WORK_ORDER
                         │
                         ├──< (*) JOB
                         │
                         ├──< (*) PRODUCTION_ENTRY
                         │
                         ├──< (*) QUALITY_ENTRY
                         │
                         └──< (*) HOLD_ENTRY

EMPLOYEE (1) ─────────< (*) EMPLOYEE_CLIENT_ASSIGNMENT >───────── (1) CLIENT

USER (1) ─────────────< (*) USER_CLIENT_ASSIGNMENT >───────────── (1) CLIENT

PRODUCT (1) ──────────< (*) PRODUCTION_ENTRY

SHIFT (1) ────────────< (*) PRODUCTION_ENTRY
```

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-01-XX | System | Initial domain model documentation |
