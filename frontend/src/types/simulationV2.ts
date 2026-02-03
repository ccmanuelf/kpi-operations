/**
 * Type definitions for Simulation v2.0
 *
 * These types mirror the backend Pydantic models for simulation configuration
 * and output blocks.
 */

// ============================================================================
// Input Types
// ============================================================================

export type VariabilityType = 'triangular' | 'deterministic'
export type DemandMode = 'demand-driven' | 'mix-driven'

export interface OperationInput {
  product: string
  step: number
  operation: string
  machine_tool: string
  sam_min: number
  sequence?: string
  grouping?: string
  operators?: number
  variability?: VariabilityType
  rework_pct?: number
  grade_pct?: number
  fpd_pct?: number
  _id?: string // Internal ID for AG Grid
}

export interface ScheduleConfig {
  shifts_enabled: number
  shift1_hours: number
  shift2_hours: number
  shift3_hours: number
  work_days: number
  ot_enabled: boolean
  weekday_ot_hours?: number
  weekend_ot_days?: number
  weekend_ot_hours?: number
}

export interface DemandInput {
  product: string
  bundle_size: number
  daily_demand?: number | null
  weekly_demand?: number | null
  mix_share_pct?: number | null
  _id?: string // Internal ID for AG Grid
}

export interface BreakdownInput {
  machine_tool: string
  breakdown_pct: number
  _id?: string // Internal ID for AG Grid
}

export interface SimulationConfig {
  operations: OperationInput[]
  schedule: ScheduleConfig
  demands: DemandInput[]
  breakdowns?: BreakdownInput[]
  mode: DemandMode
  total_demand?: number | null
  horizon_days?: number
}

// ============================================================================
// Validation Types
// ============================================================================

export type ValidationSeverity = 'error' | 'warning' | 'info'

export interface ValidationIssue {
  severity: ValidationSeverity
  category: string
  message: string
  field?: string
  product?: string
  recommendation?: string
}

export interface ValidationReport {
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
  info: ValidationIssue[]
  products_count: number
  operations_count: number
  machine_tools_count: number
  is_valid: boolean
  can_proceed: boolean
}

// ============================================================================
// Output Types (8 Blocks)
// ============================================================================

// Block 1: Weekly Demand vs Capacity
export interface WeeklyDemandCapacity {
  product: string
  weekly_demand_pcs: number
  max_weekly_capacity_pcs: number
  demand_coverage_pct: number
  status: 'OK' | 'Tight' | 'Shortfall'
}

// Block 2: Daily Summary
export interface DailySummary {
  daily_throughput_pcs: number
  daily_demand_pcs: number
  daily_coverage_pct: number
  total_shifts_per_day: number
  daily_planned_hours: number
  bundles_processed_per_day: number
  bundle_size_pcs: number
  avg_cycle_time_min: number
  avg_wip_pcs: number
}

// Block 3: Per Product Summary
export interface PerProductSummary {
  product: string
  bundle_size_pcs: number
  mix_share_pct: number
  daily_demand_pcs: number
  daily_throughput_pcs: number
  daily_coverage_pct: number
  weekly_demand_pcs: number
  weekly_throughput_pcs: number
}

// Block 4: Station Performance
export interface StationPerformance {
  product: string
  step: number
  operation: string
  machine_tool: string
  operators: number
  util_pct: number
  queue_wait_time_min: number
  is_bottleneck: boolean
  is_donor: boolean
}

// Block 5: Rebalancing Suggestions
export interface RebalancingSuggestion {
  product: string
  step: number
  operation: string
  machine_tool: string
  operators_before: number
  operators_after: number
  util_before_pct: number
  util_after_pct: number
  role: 'Bottleneck' | 'Donor'
  comment: string
}

// Block 6: Free Capacity
export interface FreeCapacity {
  daily_max_capacity_pcs: number
  demand_usage_pct: number
  free_line_hours_per_day: number
  equivalent_free_operators_full_shift: number
}

// Block 7: Bundle Metrics
export interface BundleMetrics {
  product: string
  bundle_size_pcs: number
  bundles_arriving_per_day: number
  avg_bundles_in_system: number
  max_bundles_in_system: number
  avg_bundle_cycle_time_min: number
}

// Block 8: Assumption Log
export interface AssumptionLog {
  simulation_engine_version: string
  configuration_mode: string
  timestamp: string
  formula_implementations: Record<string, string>
  limitations_and_caveats: string[]
}

// Combined Output Blocks
export interface SimulationOutputBlocks {
  weekly_demand_capacity: WeeklyDemandCapacity[]
  daily_summary: DailySummary
  per_product_summary: PerProductSummary[]
  station_performance: StationPerformance[]
  rebalancing_suggestions: RebalancingSuggestion[]
  free_capacity: FreeCapacity
  bundle_metrics: BundleMetrics[]
  assumption_log: AssumptionLog
}

// API Response
export interface SimulationResponse {
  success: boolean
  message: string
  results: SimulationOutputBlocks
  simulation_duration_seconds: number
}

// Simulation Info
export interface SimulationInfo {
  version: string
  supported_modes: string[]
  limits: {
    max_products: number
    max_operations_per_product: number
    max_total_operations: number
    max_horizon_days: number
  }
  defaults: {
    schedule: {
      shifts_enabled: number
      shift1_hours: number
      work_days: number
    }
    operation: {
      operators: number
      variability: VariabilityType
      grade_pct: number
      fpd_pct: number
      rework_pct: number
    }
    demand: {
      bundle_size: number
      horizon_days: number
    }
  }
}
