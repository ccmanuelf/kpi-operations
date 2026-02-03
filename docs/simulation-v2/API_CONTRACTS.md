# Production Line Simulation v2.0 - API Contracts

Quick reference for API endpoints and data structures.

---

## Endpoints

### GET `/api/v2/simulation/`

Returns tool info and capabilities.

**Response:**
```json
{
  "name": "Production Line Simulation Tool",
  "version": "2.0.0",
  "description": "Ephemeral capacity planning and line behavior simulation",
  "max_products": 5,
  "max_operations_per_product": 50
}
```

---

### POST `/api/v2/simulation/validate`

Validates configuration without running simulation.

**Request:**
```json
{
  "config": { /* SimulationConfig */ }
}
```

**Response:** `ValidationReport`

---

### POST `/api/v2/simulation/run`

Runs full simulation.

**Request:**
```json
{
  "config": { /* SimulationConfig */ }
}
```

**Response:**
```json
{
  "success": true,
  "results": { /* SimulationResults - 8 blocks */ },
  "validation_report": { /* ValidationReport */ },
  "message": "Simulation completed in 2.34 seconds"
}
```

---

## Input Schemas

### SimulationConfig

```typescript
interface SimulationConfig {
  operations: OperationInput[];        // Required, min 1
  schedule: ScheduleConfig;            // Required
  demands: DemandInput[];              // Required, min 1
  breakdowns?: BreakdownInput[];       // Optional
  mode: "demand-driven" | "mix-driven";
  total_demand?: number;               // Required if mix-driven
  horizon_days: number;                // Default: 1, range 1-7
}
```

### OperationInput

```typescript
interface OperationInput {
  product: string;                     // Required, min 1 char
  step: number;                        // Required, >= 1
  operation: string;                   // Required, min 1 char
  machine_tool: string;                // Required, min 1 char
  sam_min: number;                     // Required, > 0

  // Optional with defaults
  sequence?: string;                   // Default: "Assembly"
  grouping?: string;                   // Default: ""
  operators?: number;                  // Default: 1, range 1-20
  variability?: "deterministic" | "triangular";  // Default: "triangular"
  rework_pct?: number;                 // Default: 0, range 0-100
  grade_pct?: number;                  // Default: 85, range 0-100
  fpd_pct?: number;                    // Default: 15, range 0-100
}
```

### ScheduleConfig

```typescript
interface ScheduleConfig {
  shifts_enabled: number;              // Required, 1-3
  shift1_hours: number;                // Required, > 0, <= 12
  shift2_hours?: number;               // Default: 0
  shift3_hours?: number;               // Default: 0
  work_days: number;                   // Required, 1-7

  ot_enabled?: boolean;                // Default: false
  weekday_ot_hours?: number;           // Default: 0
  weekend_ot_days?: number;            // Default: 0, range 0-2
  weekend_ot_hours?: number;           // Default: 0
}
```

### DemandInput

```typescript
interface DemandInput {
  product: string;                     // Required, must match operations
  bundle_size?: number;                // Default: 1, range 1-100
  daily_demand?: number;               // Optional, >= 0
  weekly_demand?: number;              // Optional, >= 0
  mix_share_pct?: number;              // Optional, 0-100 (for mix-driven)
}
```

### BreakdownInput

```typescript
interface BreakdownInput {
  machine_tool: string;                // Must match operations machine_tool
  breakdown_pct: number;               // 0-100
}
```

---

## Output Schemas

### SimulationResults

```typescript
interface SimulationResults {
  weekly_demand_capacity: WeeklyDemandCapacityRow[];  // Block 1
  daily_summary: DailySummary;                         // Block 2
  station_performance: StationPerformanceRow[];        // Block 3
  free_capacity: FreeCapacityAnalysis;                 // Block 4
  bundle_metrics: BundleMetricsRow[];                  // Block 5
  per_product_summary: PerProductSummaryRow[];         // Block 6
  rebalancing_suggestions: RebalancingSuggestionRow[]; // Block 7
  assumption_log: AssumptionLog;                       // Block 8

  validation_report: ValidationReport;
  simulation_duration_seconds: number;
}
```

### Block 1: WeeklyDemandCapacityRow

```typescript
interface WeeklyDemandCapacityRow {
  product: string;
  weekly_demand_pcs: number;
  max_weekly_capacity_pcs: number;
  demand_coverage_pct: number;
  status: "OK" | "Tight" | "Shortfall";
}
```

### Block 2: DailySummary

```typescript
interface DailySummary {
  total_shifts_per_day: number;
  daily_planned_hours: number;
  daily_throughput_pcs: number;
  daily_demand_pcs: number;
  daily_coverage_pct: number;
  avg_cycle_time_min: number;
  avg_wip_pcs: number;
  bundles_processed_per_day: number;
  bundle_size_pcs: string;             // "10" or "mixed"
}
```

### Block 3: StationPerformanceRow

```typescript
interface StationPerformanceRow {
  product: string;
  step: number;
  operation: string;
  machine_tool: string;
  sequence: string;
  grouping: string;
  operators: number;
  total_pieces_processed: number;
  total_busy_time_min: number;
  avg_processing_time_min: number;
  util_pct: number;
  queue_wait_time_min: number;
  is_bottleneck: boolean;
  is_donor: boolean;
}
```

### Block 4: FreeCapacityAnalysis

```typescript
interface FreeCapacityAnalysis {
  daily_demand_pcs: number;
  daily_max_capacity_pcs: number;
  demand_usage_pct: number;
  free_line_hours_per_day: number;
  free_operator_hours_at_bottleneck_per_day: number;
  equivalent_free_operators_full_shift: number;
}
```

### Block 5: BundleMetricsRow

```typescript
interface BundleMetricsRow {
  product: string;
  bundle_size_pcs: number;
  bundles_arriving_per_day: number;
  avg_bundles_in_system: number | null;
  max_bundles_in_system: number | null;
  avg_bundle_cycle_time_min: number | null;
}
```

### Block 6: PerProductSummaryRow

```typescript
interface PerProductSummaryRow {
  product: string;
  bundle_size_pcs: number;
  mix_share_pct: number | null;
  daily_demand_pcs: number;
  daily_throughput_pcs: number;
  daily_coverage_pct: number;
  weekly_demand_pcs: number;
  weekly_throughput_pcs: number;
  weekly_coverage_pct: number;
}
```

### Block 7: RebalancingSuggestionRow

```typescript
interface RebalancingSuggestionRow {
  product: string;                     // "ALL" for cross-product
  step: number;
  operation: string;
  machine_tool: string;
  grouping: string;
  operators_before: number;
  operators_after: number;
  util_before_pct: number;
  util_after_pct: number;
  role: "Bottleneck" | "Donor";
  comment: string;
}
```

### Block 8: AssumptionLog

```typescript
interface AssumptionLog {
  timestamp: string;                   // ISO 8601
  simulation_engine_version: string;
  configuration_mode: string;
  schedule: Record<string, any>;
  products: Array<Record<string, any>>;
  operations_defaults_applied: Array<{
    product: string;
    step: number;
    operation: string;
    defaults: string[];
  }>;
  breakdowns_configuration: {
    enabled: boolean;
    message: string;
  };
  formula_implementations: Record<string, string>;
  limitations_and_caveats: string[];
}
```

### ValidationReport

```typescript
interface ValidationReport {
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  info: ValidationIssue[];

  products_count: number;
  operations_count: number;
  machine_tools_count: number;

  is_valid: boolean;
  can_proceed: boolean;
}

interface ValidationIssue {
  severity: "error" | "warning" | "info";
  category: string;
  message: string;
  field?: string;
  product?: string;
  recommendation?: string;
}
```

---

## CSV Import Formats

### Operations CSV

```csv
Product,Step,Operation,Machine_Tool,SAM_min,Sequence,Grouping,Operators,Variability,Rework_pct,Grade_pct,FPD_pct
HV_TSHIRT,1,Cut fabric panels,Cutting table,2.30,Cutting,CUTTING,1,triangular,0,85,15
HV_TSHIRT,2,Join shoulder seams,4-thread overlock,0.85,Assembly,PREP,1,triangular,2,85,15
```

**Required columns:** Product, Step, Operation, Machine_Tool, SAM_min
**Optional columns:** Sequence, Grouping, Operators, Variability, Rework_pct, Grade_pct, FPD_pct

### Demand CSV

```csv
Product,Bundle_Size,Daily_Demand,Weekly_Demand,Mix_Share_pct
HV_TSHIRT,10,500,2500,
POLO_SHIRT,10,360,1800,
```

**Required columns:** Product
**Optional columns:** Bundle_Size, Daily_Demand, Weekly_Demand, Mix_Share_pct

### Breakdowns CSV

```csv
Machine_Tool,Breakdown_pct
4-thread overlock,2.5
Single needle,1.0
```

**Required columns:** Machine_Tool
**Optional columns:** Breakdown_pct (defaults to 0)

---

## Processing Time Formula

```
Actual_Time = SAM × (1 + Variability_Factor + FPD_pct/100 + (100-Grade_pct)/100)
```

Where:
- **Variability_Factor**: 0 for deterministic, random(-0.10, +0.10) for triangular
- **FPD_pct**: Fatigue and personal delay percentage
- **Grade_pct**: Operator skill level (100 = fully trained)

**Example:**
- SAM = 1.0 min
- Grade_pct = 85%
- FPD_pct = 15%
- Variability = +5% (random draw)

```
Actual = 1.0 × (1 + 0.05 + 0.15 + 0.15) = 1.35 min
```

---

## Bundle Transition Times

| Bundle Size | Transition Time |
|-------------|-----------------|
| ≤ 5 pieces | 1 second |
| > 5 pieces | 5 seconds |

Applied at entry and exit of each station.

---

## Bottleneck Detection Thresholds

| Utilization % | Classification |
|---------------|----------------|
| ≥ 95% | Bottleneck |
| ≤ 70% (with operators > 1) | Potential Donor |
| 70% - 95% | Normal |

---

## Status Determination (Block 1)

| Coverage % | Status |
|------------|--------|
| ≥ 110% | OK (surplus capacity) |
| 90% - 110% | Tight |
| < 90% | Shortfall |
