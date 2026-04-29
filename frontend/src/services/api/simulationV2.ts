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
  buildSimulationConfig,
  getDefaultOperation,
  getDefaultSchedule,
  getDefaultDemand,
  getDefaultBreakdown,
}
