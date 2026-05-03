import api from './client'

export type SimulationMode = 'demand-driven' | 'mix-driven'
export type Variability = 'triangular' | 'normal' | 'uniform'

export interface OperationDraft {
  product: string
  step: number | string
  operation: string
  machine_tool: string
  sam_min: number | string
  sequence?: string
  grouping?: string
  operators?: number | string
  variability?: Variability
  rework_pct?: number | string
  grade_pct?: number | string
  fpd_pct?: number | string
}

export interface ScheduleDraft {
  shifts_enabled: number | string
  shift1_hours: number | string
  shift2_hours?: number | string
  shift3_hours?: number | string
  work_days: number | string
  ot_enabled?: boolean
  weekday_ot_hours?: number | string
  weekend_ot_days?: number | string
  weekend_ot_hours?: number | string
}

export interface DemandDraft {
  product: string
  bundle_size?: number | string
  daily_demand?: number | string | null
  weekly_demand?: number | string | null
  mix_share_pct?: number | string | null
}

export interface BreakdownDraft {
  machine_tool: string
  breakdown_pct: number | string
}

export interface BuildConfigParams {
  operations: OperationDraft[]
  schedule: ScheduleDraft
  demands: DemandDraft[]
  breakdowns?: BreakdownDraft[]
  mode?: SimulationMode
  totalDemand?: number | string | null
  horizonDays?: number | string
}

export interface SimulationConfig {
  operations: Record<string, unknown>[]
  schedule: Record<string, unknown>
  demands: Record<string, unknown>[]
  breakdowns?: Record<string, unknown>[]
  mode: SimulationMode
  horizon_days: number
  total_demand?: number
}

export const getSimulationInfo = async () => {
  const response = await api.get('/v2/simulation/')
  return response.data
}

export const getSimulationSchema = async () => {
  const response = await api.get('/v2/simulation/schema')
  return response.data
}

export const validateSimulationConfig = async (config: SimulationConfig) => {
  const response = await api.post('/v2/simulation/validate', { config })
  return response.data
}

export const runSimulation = async (config: SimulationConfig) => {
  const response = await api.post('/v2/simulation/run', { config })
  return response.data
}

// =============================================================================
// Monte Carlo
// =============================================================================

export interface MonteCarloStat {
  mean: number
  std: number
  ci_lo_95: number
  ci_hi_95: number
  n: number
}

export interface MonteCarloRunOptions {
  config: SimulationConfig
  n_replications: number
  base_seed?: number | null
}

// =============================================================================
// Pattern 4 — Planning horizon
// =============================================================================

export interface DailyPlan {
  day: number
  pieces_by_product: Record<string, number>
  total_pieces: number
  minutes_used: number
  daily_minutes_capacity: number
  load_pct: number
}

export interface PlanningHorizonOptions {
  config: SimulationConfig
  horizon_days?: number
  timeout_seconds?: number
}

/**
 * Pattern 4 (MiniZinc plans the week → SimPy executes each day): given
 * a config with weekly demand per product, distribute work across the
 * planning horizon to minimize the MAX daily utilization (smoothest
 * workload). Returns a per-day production schedule the planner can
 * hand to SimPy for stochastic execution-side validation.
 *
 * Best-effort behavior: when weekly demand exceeds horizon capacity,
 * `is_satisfied=false` plus a per-product shortfall message; the
 * `daily_plans` array still carries a capacity-bounded fallback.
 *
 * Backend: `POST /v2/simulation/plan-horizon`. Returns 503 if the
 * MiniZinc CLI is missing on the server.
 */
export const planHorizon = async ({
  config,
  horizon_days = 5,
  timeout_seconds = 30,
}: PlanningHorizonOptions) => {
  const body: Record<string, unknown> = { config, horizon_days, timeout_seconds }
  const response = await api.post('/v2/simulation/plan-horizon', body)
  return response.data
}

// =============================================================================
// Pattern 1 — Operator allocation optimization
// =============================================================================

export interface OperatorAllocationProposal {
  product: string
  step: number
  operation: string
  machine_tool: string
  sam_min: number
  grade_pct: number
  operators_before: number
  operators_after: number
  demand_pcs_per_day: number
  predicted_pcs_per_day: number
}

export interface OperatorAllocationOptions {
  config: SimulationConfig
  max_operators_per_op?: number
  total_operators_budget?: number | null
  timeout_seconds?: number
  validate_with_simulation?: boolean
}

// =============================================================================
// Pattern 2 — Bottleneck rebalancing
// =============================================================================

export interface RebalancingProposal {
  product: string
  step: number
  operation: string
  machine_tool: string
  sam_min: number
  grade_pct: number
  operators_before: number
  operators_after: number
  delta: number
  demand_pcs_per_day: number
  predicted_pcs_per_day: number
  slack_pcs: number
}

export interface RebalancingOptions {
  config: SimulationConfig
  min_operators_per_op?: number
  max_operators_per_op?: number
  total_delta_max?: number
  total_delta_min?: number
  timeout_seconds?: number
  validate_with_simulation?: boolean
}

/**
 * Pattern 2 (SimPy detects → MiniZinc solves): take an existing
 * operator allocation and reshuffle operators across stations to lift
 * the bottleneck. `total_delta_max=0` (default) preserves total head-
 * count; positive values permit growth.
 *
 * Backend: `POST /v2/simulation/rebalance-bottlenecks`. Returns 503 if
 * the MiniZinc CLI is missing on the server.
 */
export const rebalanceBottlenecks = async ({
  config,
  min_operators_per_op = 1,
  max_operators_per_op = 10,
  total_delta_max = 0,
  total_delta_min = -50,
  timeout_seconds = 15,
  validate_with_simulation = false,
}: RebalancingOptions) => {
  const body: Record<string, unknown> = {
    config,
    min_operators_per_op,
    max_operators_per_op,
    total_delta_max,
    total_delta_min,
    timeout_seconds,
    validate_with_simulation,
  }
  const response = await api.post('/v2/simulation/rebalance-bottlenecks', body)
  return response.data
}

// =============================================================================
// Pattern 3 — Product sequencing
// =============================================================================

export interface SetupTimeEntry {
  from_product: string
  to_product: string
  setup_minutes: number
}

export interface SequencedProduct {
  position: number
  product: string
  production_time_minutes: number
  start_time_minutes: number
  end_time_minutes: number
  setup_from_previous_minutes: number
}

export interface ProductSequencingOptions {
  config: SimulationConfig
  setup_times_minutes?: SetupTimeEntry[]
  timeout_seconds?: number
}

/**
 * Pattern 3 (MiniZinc orders → SimPy simulates): given a multi-product
 * config and a pairwise setup-time matrix, find the production order
 * that minimizes total wallclock makespan. Useful for campaign-mode
 * lines that produce one product at a time and pay a changeover cost
 * when switching between products.
 *
 * `setup_times_minutes` is a list of `{from_product, to_product,
 * setup_minutes}` triples. Missing pairs default to 0; entries
 * referencing products not in the config are tolerated (logged + ignored
 * server-side). Self-loops are also ignored.
 *
 * Backend: `POST /v2/simulation/sequence-products`. Returns 503 if the
 * MiniZinc CLI is missing on the server.
 */
export const sequenceProducts = async ({
  config,
  setup_times_minutes = [],
  timeout_seconds = 30,
}: ProductSequencingOptions) => {
  const body: Record<string, unknown> = {
    config,
    setup_times_minutes,
    timeout_seconds,
  }
  const response = await api.post('/v2/simulation/sequence-products', body)
  return response.data
}

/**
 * Pattern 1 (MiniZinc → SimPy validate): minimum-operator allocation
 * that meets each station's daily demand.
 *
 * Backend: `POST /v2/simulation/optimize-operators`. Returns 503 if the
 * MiniZinc CLI is missing on the server (development envs without it
 * stay functional for the rest of the simulation API).
 */
export const optimizeOperatorAllocation = async ({
  config,
  max_operators_per_op = 10,
  total_operators_budget = null,
  timeout_seconds = 15,
  validate_with_simulation = false,
}: OperatorAllocationOptions) => {
  const body: Record<string, unknown> = {
    config,
    max_operators_per_op,
    timeout_seconds,
    validate_with_simulation,
  }
  if (total_operators_budget !== null && total_operators_budget !== undefined) {
    body.total_operators_budget = total_operators_budget
  }
  const response = await api.post('/v2/simulation/optimize-operators', body)
  return response.data
}

/**
 * Run N replications of the simulation with mean ± 95% CI aggregation.
 *
 * Backend constrains `n_replications` to [2, 100]; 10–50 is the typical
 * range. `base_seed` is optional — if supplied, replication i uses
 * `base_seed + i`, making the entire run reproducible.
 *
 * Response shape: see backend `MonteCarloResponse`. The `aggregated_stats`
 * payload has top-level keys per output block (`daily_summary`,
 * `free_capacity`, `weekly_demand_capacity`, etc.). Numeric fields are
 * `MonteCarloStat`-shaped dicts; non-numeric fields pass through.
 * `sample_run` is a full `SimulationResults` from the first replication
 * (use it for `rebalancing_suggestions` / `assumption_log`, which are
 * not aggregated).
 */
export const runMonteCarlo = async ({
  config,
  n_replications,
  base_seed = null,
}: MonteCarloRunOptions) => {
  const body: Record<string, unknown> = { config, n_replications }
  if (base_seed !== null && base_seed !== undefined) {
    body.base_seed = base_seed
  }
  const response = await api.post('/v2/simulation/run-monte-carlo', body)
  return response.data
}

export const buildSimulationConfig = ({
  operations,
  schedule,
  demands,
  breakdowns = [],
  mode = 'demand-driven',
  totalDemand = null,
  horizonDays = 1,
}: BuildConfigParams): SimulationConfig => {
  const config: SimulationConfig = {
    operations: operations.map((op) => ({
      product: op.product,
      step: parseInt(String(op.step), 10),
      operation: op.operation,
      machine_tool: op.machine_tool,
      sam_min: parseFloat(String(op.sam_min)),
      sequence: op.sequence || 'Assembly',
      grouping: op.grouping || '',
      operators: parseInt(String(op.operators ?? 1), 10) || 1,
      variability: op.variability || 'triangular',
      rework_pct: parseFloat(String(op.rework_pct ?? 0)) || 0,
      grade_pct: parseFloat(String(op.grade_pct ?? 85)) || 85,
      fpd_pct: parseFloat(String(op.fpd_pct ?? 15)) || 15,
    })),
    schedule: {
      shifts_enabled: parseInt(String(schedule.shifts_enabled), 10),
      shift1_hours: parseFloat(String(schedule.shift1_hours)),
      shift2_hours: parseFloat(String(schedule.shift2_hours ?? 0)) || 0,
      shift3_hours: parseFloat(String(schedule.shift3_hours ?? 0)) || 0,
      work_days: parseInt(String(schedule.work_days), 10),
      ot_enabled: Boolean(schedule.ot_enabled),
      weekday_ot_hours: parseFloat(String(schedule.weekday_ot_hours ?? 0)) || 0,
      weekend_ot_days: parseInt(String(schedule.weekend_ot_days ?? 0), 10) || 0,
      weekend_ot_hours: parseFloat(String(schedule.weekend_ot_hours ?? 0)) || 0,
    },
    demands: demands.map((d) => ({
      product: d.product,
      bundle_size: parseInt(String(d.bundle_size ?? 1), 10) || 1,
      daily_demand: d.daily_demand != null ? parseFloat(String(d.daily_demand)) : null,
      weekly_demand: d.weekly_demand != null ? parseFloat(String(d.weekly_demand)) : null,
      mix_share_pct: d.mix_share_pct != null ? parseFloat(String(d.mix_share_pct)) : null,
    })),
    mode,
    horizon_days: parseInt(String(horizonDays), 10),
  }

  if (breakdowns && breakdowns.length > 0) {
    config.breakdowns = breakdowns
      .filter((b) => b.machine_tool && Number(b.breakdown_pct) > 0)
      .map((b) => ({
        machine_tool: b.machine_tool,
        breakdown_pct: parseFloat(String(b.breakdown_pct)),
      }))
  }

  if (mode === 'mix-driven' && totalDemand != null) {
    config.total_demand = parseFloat(String(totalDemand))
  }

  return config
}

export const getDefaultOperation = (product = '') => ({
  product,
  step: 1,
  operation: '',
  machine_tool: '',
  sam_min: 1.0,
  sequence: 'Assembly',
  grouping: '',
  operators: 1,
  variability: 'triangular' as Variability,
  rework_pct: 0,
  grade_pct: 85,
  fpd_pct: 15,
})

export const getDefaultSchedule = () => ({
  shifts_enabled: 1,
  shift1_hours: 8,
  shift2_hours: 0,
  shift3_hours: 0,
  work_days: 5,
  ot_enabled: false,
  weekday_ot_hours: 0,
  weekend_ot_days: 0,
  weekend_ot_hours: 0,
})

export const getDefaultDemand = (product = '') => ({
  product,
  bundle_size: 10,
  daily_demand: null as number | null,
  weekly_demand: null as number | null,
  mix_share_pct: null as number | null,
})

export const getDefaultBreakdown = (machineTool = '') => ({
  machine_tool: machineTool,
  breakdown_pct: 0,
})

export const getSampleTShirtData = () => ({
  operations: [
    {
      product: 'Basic T-Shirt',
      step: 1,
      operation: 'Cut Fabric Panels',
      machine_tool: 'Cutting Table',
      sam_min: 0.8,
      sequence: 'Cutting',
      grouping: 'Preparation',
      operators: 2,
      variability: 'triangular' as Variability,
      rework_pct: 1,
      grade_pct: 90,
      fpd_pct: 5,
    },
    {
      product: 'Basic T-Shirt',
      step: 2,
      operation: 'Attach Collar',
      machine_tool: 'Serger Machine',
      sam_min: 1.2,
      sequence: 'Assembly',
      grouping: 'Collar',
      operators: 1,
      variability: 'triangular' as Variability,
      rework_pct: 2,
      grade_pct: 85,
      fpd_pct: 12,
    },
    {
      product: 'Basic T-Shirt',
      step: 3,
      operation: 'Join Shoulder Seams',
      machine_tool: 'Serger Machine',
      sam_min: 0.9,
      sequence: 'Assembly',
      grouping: 'Body',
      operators: 1,
      variability: 'triangular' as Variability,
      rework_pct: 1,
      grade_pct: 88,
      fpd_pct: 8,
    },
    {
      product: 'Basic T-Shirt',
      step: 4,
      operation: 'Attach Sleeves',
      machine_tool: 'Serger Machine',
      sam_min: 1.5,
      sequence: 'Assembly',
      grouping: 'Sleeves',
      operators: 1,
      variability: 'triangular' as Variability,
      rework_pct: 2,
      grade_pct: 85,
      fpd_pct: 15,
    },
    {
      product: 'Basic T-Shirt',
      step: 5,
      operation: 'Close Side Seams',
      machine_tool: 'Serger Machine',
      sam_min: 1.1,
      sequence: 'Assembly',
      grouping: 'Body',
      operators: 1,
      variability: 'triangular' as Variability,
      rework_pct: 1,
      grade_pct: 87,
      fpd_pct: 10,
    },
    {
      product: 'Basic T-Shirt',
      step: 6,
      operation: 'Hem Bottom',
      machine_tool: 'Flatlock Machine',
      sam_min: 0.7,
      sequence: 'Finishing',
      grouping: 'Hemming',
      operators: 1,
      variability: 'triangular' as Variability,
      rework_pct: 1,
      grade_pct: 90,
      fpd_pct: 8,
    },
    {
      product: 'Basic T-Shirt',
      step: 7,
      operation: 'Hem Sleeves',
      machine_tool: 'Flatlock Machine',
      sam_min: 0.6,
      sequence: 'Finishing',
      grouping: 'Hemming',
      operators: 1,
      variability: 'triangular' as Variability,
      rework_pct: 1,
      grade_pct: 90,
      fpd_pct: 8,
    },
    {
      product: 'Basic T-Shirt',
      step: 8,
      operation: 'Insert Label',
      machine_tool: 'Single Needle',
      sam_min: 0.5,
      sequence: 'Finishing',
      grouping: 'Labeling',
      operators: 1,
      variability: 'triangular' as Variability,
      rework_pct: 0,
      grade_pct: 92,
      fpd_pct: 3,
    },
    {
      product: 'Basic T-Shirt',
      step: 9,
      operation: 'Final QC & Fold',
      machine_tool: 'QC Station',
      sam_min: 0.8,
      sequence: 'QC',
      grouping: 'Quality',
      operators: 1,
      variability: 'triangular' as Variability,
      rework_pct: 0,
      grade_pct: 95,
      fpd_pct: 2,
    },
  ],
  schedule: {
    shifts_enabled: 1,
    shift1_hours: 8,
    shift2_hours: 0,
    shift3_hours: 0,
    work_days: 5,
    ot_enabled: false,
    weekday_ot_hours: 0,
    weekend_ot_days: 0,
    weekend_ot_hours: 0,
  },
  demands: [
    {
      product: 'Basic T-Shirt',
      bundle_size: 12,
      daily_demand: 500,
      weekly_demand: null as number | null,
      mix_share_pct: null as number | null,
    },
  ],
  breakdowns: [
    { machine_tool: 'Serger Machine', breakdown_pct: 3 },
    { machine_tool: 'Single Needle', breakdown_pct: 2 },
  ],
  mode: 'demand-driven' as SimulationMode,
  horizon_days: 5,
})

const VISIT_KEY = 'simulation_v2_visited'

export const isFirstVisit = (): boolean => !localStorage.getItem(VISIT_KEY)

export const markAsVisited = (): void => {
  localStorage.setItem(VISIT_KEY, 'true')
}

export const clearVisitedFlag = (): void => {
  localStorage.removeItem(VISIT_KEY)
}

export default {
  getSimulationInfo,
  getSimulationSchema,
  validateSimulationConfig,
  runSimulation,
  runMonteCarlo,
  optimizeOperatorAllocation,
  rebalanceBottlenecks,
  sequenceProducts,
  planHorizon,
  buildSimulationConfig,
  getDefaultOperation,
  getDefaultSchedule,
  getDefaultDemand,
  getDefaultBreakdown,
}
