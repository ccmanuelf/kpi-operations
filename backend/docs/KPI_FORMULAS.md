# KPI Formulas Reference

## Executive Summary

This document provides the authoritative reference for all KPI calculations in the KPI Operations platform. Each formula includes:
- Mathematical formula
- Input requirements
- Edge cases
- Inference chains (when applicable)

---

## Production KPIs

### KPI #3: Efficiency

**Formula**:
```
Efficiency (%) = (units_produced × ideal_cycle_time) / (employees_assigned × scheduled_hours) × 100
```

**Inputs**:
| Parameter | Type | Source | Required |
|-----------|------|--------|----------|
| `units_produced` | int | ProductionEntry | Yes |
| `ideal_cycle_time` | Decimal (hours/unit) | Product.ideal_cycle_time | Inferred if missing |
| `employees_assigned` | int | ProductionEntry | Inferred if missing |
| `scheduled_hours` | Decimal | Shift.start_time/end_time | Default: 8.0 |

**Inference Chain for ideal_cycle_time**:
1. `Product.ideal_cycle_time` (authoritative)
2. Historical average from same product's production entries
3. Client default (`ClientConfig.default_cycle_time_hours`)
4. System default: 0.25 hours (15 minutes)

**Inference Chain for employees_assigned**:
1. `ProductionEntry.employees_assigned` (authoritative)
2. `CoverageEntry.employees_present` for shift
3. Historical average for product/shift
4. System default: 1

**Edge Cases**:
- `employees_assigned = 0`: Returns 0%
- `scheduled_hours = 0`: Returns 0%
- Cap at 150% (reasonable max)

**ESTIMATED Flag**: Set when any input was inferred

---

### KPI #9: Performance

**Formula**:
```
Performance (%) = (ideal_cycle_time × units_produced) / run_time_hours × 100
```

**Inputs**:
| Parameter | Type | Source | Required |
|-----------|------|--------|----------|
| `units_produced` | int | ProductionEntry | Yes |
| `ideal_cycle_time` | Decimal (hours/unit) | Product.ideal_cycle_time | Inferred |
| `run_time_hours` | Decimal | ProductionEntry | Yes |

**Edge Cases**:
- `run_time_hours = 0`: Returns 0%
- Cap at 150%

---

### Quality Rate

**Formula**:
```
Quality Rate (%) = ((units_produced - defects - scrap) / units_produced) × 100
```

**Inputs**:
| Parameter | Type | Source | Required |
|-----------|------|--------|----------|
| `units_produced` | int | ProductionEntry | Yes |
| `defect_count` | int | ProductionEntry | Default: 0 |
| `scrap_count` | int | ProductionEntry | Default: 0 |

**Edge Cases**:
- `units_produced = 0`: Returns 0%
- Negative result: Returns 0% (should never happen)

---

### OEE (Overall Equipment Effectiveness)

**Formula**:
```
OEE (%) = Availability × Performance × Quality
```

Where all factors are expressed as decimals (e.g., 85% = 0.85)

**Note**: Current implementation assumes 100% availability. Full availability tracking requires downtime integration.

---

## Quality KPIs

### PPM (Parts Per Million)

**Formula**:
```
PPM = (total_defective_units / total_units_inspected) × 1,000,000
```

**Inputs**:
| Parameter | Type | Source | Required |
|-----------|------|--------|----------|
| `total_units_inspected` | int | Sum of QualityEntry.units_inspected | Yes |
| `total_defective_units` | int | Sum of QualityEntry.units_defective | Yes |

**Edge Cases**:
- `total_units_inspected = 0`: Returns 0

**Interpretation**:
| PPM Range | Quality Level |
|-----------|---------------|
| < 100 | Excellent |
| 100-500 | Good |
| 500-2000 | Average |
| > 2000 | Needs improvement |

---

### DPMO (Defects Per Million Opportunities)

**Formula**:
```
DPMO = (total_defects / (total_units × opportunities_per_unit)) × 1,000,000
```

**Inputs**:
| Parameter | Type | Source | Required |
|-----------|------|--------|----------|
| `total_defects` | int | Sum of QualityEntry.total_defects_count | Yes |
| `total_units` | int | Sum of QualityEntry.units_inspected | Yes |
| `opportunities_per_unit` | int | PART_OPPORTUNITIES or default | Lookup |

**Opportunities Lookup Chain**:
1. `PART_OPPORTUNITIES` table (part-specific)
2. `ClientConfig.dpmo_opportunities_default`
3. System default: 10

**Sigma Level Conversion**:
| DPMO | Sigma Level | Yield |
|------|-------------|-------|
| 3.4 | 6σ | 99.99966% |
| 233 | 5σ | 99.977% |
| 6,210 | 4σ | 99.379% |
| 66,807 | 3σ | 93.32% |
| 308,537 | 2σ | 69.15% |
| 690,000 | 1σ | 31.0% |

---

### FPY (First Pass Yield)

**Formula**:
```
FPY (%) = (units_passed_first_time / total_units_inspected) × 100
```

**CRITICAL**: `units_passed_first_time` excludes both rework AND repair.

**Inputs**:
| Parameter | Type | Source | Required |
|-----------|------|--------|----------|
| `units_passed` | int | QualityEntry.units_passed | Yes |
| `units_inspected` | int | QualityEntry.units_inspected | Yes |

**Edge Cases**:
- `units_inspected = 0`: Returns 0%

---

### RTY (Rolled Throughput Yield)

**Formula**:
```
RTY (%) = FPY_step1 × FPY_step2 × ... × FPY_stepN
```

Where each FPY is expressed as a decimal (e.g., 95% = 0.95)

**Default Process Steps**:
1. Incoming
2. In-Process
3. Final

**Example**:
```
Incoming FPY: 98%
In-Process FPY: 95%
Final FPY: 99%

RTY = 0.98 × 0.95 × 0.99 = 0.9217 = 92.17%
```

**Interpretation**:
```
RTY < 85%: Process has significant hidden factory (rework)
RTY 85-95%: Typical manufacturing
RTY > 95%: Lean/efficient process
```

---

## Work Order KPIs

### WIP Aging

**Formula**:
```
WIP Aging (days) = (current_date - received_date) - total_hold_duration
```

**Hold Duration Calculation**:
```
For each HoldEntry:
  hold_duration = hold_end_date - hold_start_date

total_hold_duration = SUM(hold_duration)
```

**CRITICAL**: All hold reasons are treated equally and excluded from aging.

---

### Job Yield

**Formula**:
```
Job Yield (%) = ((completed_quantity - quantity_scrapped) / completed_quantity) × 100
```

**Inputs**:
| Parameter | Type | Source | Required |
|-----------|------|--------|----------|
| `completed_quantity` | int | Job.completed_quantity | Yes |
| `quantity_scrapped` | int | Job.quantity_scrapped | Default: 0 |

---

### Recovery Rate

**Formula**:
```
Recovery Rate (%) = (rework + repair) / (rework + repair + scrap) × 100
```

Measures ability to recover units that initially failed.

---

## Implementation Notes

### Pure vs Database-Dependent Functions

The codebase contains two types of calculation functions:

**Pure Functions** (Phase 1.2):
- Suffix: `_pure` (e.g., `calculate_efficiency_pure`)
- No database access
- Unit testable without mocks
- Accept raw values as parameters

**Orchestrated Functions**:
- Use ProductionKPIService, QualityKPIService
- Handle data fetching and inference
- Call pure functions internally

### Service Layer Pattern

```python
# Route → Service → Pure Calculation

@router.get("/efficiency")
def get_efficiency(db: Session, entry_id: str):
    service = ProductionKPIService(db)
    result = service.calculate_efficiency_only(entry)
    return result

# ProductionKPIService._calculate_efficiency() internally calls:
# calculate_efficiency_pure(units, cycle_time, employees, hours)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Phase 5 | Initial KPI formulas documentation |
