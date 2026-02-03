/**
 * Production Line Simulation v2.0 - API Client
 *
 * Provides API methods for the ephemeral simulation tool.
 * All endpoints are under /api/v2/simulation
 */

import api from './client'

/**
 * Get simulation tool information and capabilities.
 * @returns {Promise<Object>} Tool info with version, capabilities, constraints
 */
export const getSimulationInfo = async () => {
  const response = await api.get('/v2/simulation/')
  return response.data
}

/**
 * Get JSON schema for simulation input configuration.
 * @returns {Promise<Object>} JSON schema
 */
export const getSimulationSchema = async () => {
  const response = await api.get('/v2/simulation/schema')
  return response.data
}

/**
 * Validate simulation configuration without running.
 * @param {Object} config - SimulationConfig object
 * @returns {Promise<Object>} ValidationReport with errors, warnings, info
 */
export const validateSimulationConfig = async (config) => {
  const response = await api.post('/v2/simulation/validate', { config })
  return response.data
}

/**
 * Run complete simulation and get results.
 * @param {Object} config - SimulationConfig object
 * @returns {Promise<Object>} SimulationResponse with results and validation
 */
export const runSimulation = async (config) => {
  const response = await api.post('/v2/simulation/run', { config })
  return response.data
}

/**
 * Build a SimulationConfig object from component state.
 * @param {Object} params - Configuration parameters
 * @returns {Object} SimulationConfig ready for API
 */
export const buildSimulationConfig = ({
  operations,
  schedule,
  demands,
  breakdowns = [],
  mode = 'demand-driven',
  totalDemand = null,
  horizonDays = 1
}) => {
  const config = {
    operations: operations.map(op => ({
      product: op.product,
      step: parseInt(op.step, 10),
      operation: op.operation,
      machine_tool: op.machine_tool,
      sam_min: parseFloat(op.sam_min),
      sequence: op.sequence || 'Assembly',
      grouping: op.grouping || '',
      operators: parseInt(op.operators, 10) || 1,
      variability: op.variability || 'triangular',
      rework_pct: parseFloat(op.rework_pct) || 0,
      grade_pct: parseFloat(op.grade_pct) || 85,
      fpd_pct: parseFloat(op.fpd_pct) || 15
    })),
    schedule: {
      shifts_enabled: parseInt(schedule.shifts_enabled, 10),
      shift1_hours: parseFloat(schedule.shift1_hours),
      shift2_hours: parseFloat(schedule.shift2_hours) || 0,
      shift3_hours: parseFloat(schedule.shift3_hours) || 0,
      work_days: parseInt(schedule.work_days, 10),
      ot_enabled: Boolean(schedule.ot_enabled),
      weekday_ot_hours: parseFloat(schedule.weekday_ot_hours) || 0,
      weekend_ot_days: parseInt(schedule.weekend_ot_days, 10) || 0,
      weekend_ot_hours: parseFloat(schedule.weekend_ot_hours) || 0
    },
    demands: demands.map(d => ({
      product: d.product,
      bundle_size: parseInt(d.bundle_size, 10) || 1,
      daily_demand: d.daily_demand ? parseFloat(d.daily_demand) : null,
      weekly_demand: d.weekly_demand ? parseFloat(d.weekly_demand) : null,
      mix_share_pct: d.mix_share_pct ? parseFloat(d.mix_share_pct) : null
    })),
    mode,
    horizon_days: parseInt(horizonDays, 10)
  }

  // Add breakdowns if any
  if (breakdowns && breakdowns.length > 0) {
    config.breakdowns = breakdowns
      .filter(b => b.machine_tool && b.breakdown_pct > 0)
      .map(b => ({
        machine_tool: b.machine_tool,
        breakdown_pct: parseFloat(b.breakdown_pct)
      }))
  }

  // Add total_demand for mix-driven mode
  if (mode === 'mix-driven' && totalDemand) {
    config.total_demand = parseFloat(totalDemand)
  }

  return config
}

/**
 * Default operation template for new rows
 */
export const getDefaultOperation = (product = '') => ({
  product,
  step: 1,
  operation: '',
  machine_tool: '',
  sam_min: 1.0,
  sequence: 'Assembly',
  grouping: '',
  operators: 1,
  variability: 'triangular',
  rework_pct: 0,
  grade_pct: 85,
  fpd_pct: 15
})

/**
 * Default schedule template
 */
export const getDefaultSchedule = () => ({
  shifts_enabled: 1,
  shift1_hours: 8,
  shift2_hours: 0,
  shift3_hours: 0,
  work_days: 5,
  ot_enabled: false,
  weekday_ot_hours: 0,
  weekend_ot_days: 0,
  weekend_ot_hours: 0
})

/**
 * Default demand template for new rows
 */
export const getDefaultDemand = (product = '') => ({
  product,
  bundle_size: 10,
  daily_demand: null,
  weekly_demand: null,
  mix_share_pct: null
})

/**
 * Default breakdown template
 */
export const getDefaultBreakdown = (machineTool = '') => ({
  machine_tool: machineTool,
  breakdown_pct: 0
})

/**
 * Sample T-Shirt manufacturing data for onboarding
 * Provides a realistic garment manufacturing scenario
 */
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
      variability: 'triangular',
      rework_pct: 1,
      grade_pct: 90,
      fpd_pct: 5
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
      variability: 'triangular',
      rework_pct: 2,
      grade_pct: 85,
      fpd_pct: 12
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
      variability: 'triangular',
      rework_pct: 1,
      grade_pct: 88,
      fpd_pct: 8
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
      variability: 'triangular',
      rework_pct: 2,
      grade_pct: 85,
      fpd_pct: 15
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
      variability: 'triangular',
      rework_pct: 1,
      grade_pct: 87,
      fpd_pct: 10
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
      variability: 'triangular',
      rework_pct: 1,
      grade_pct: 90,
      fpd_pct: 8
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
      variability: 'triangular',
      rework_pct: 1,
      grade_pct: 90,
      fpd_pct: 8
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
      variability: 'triangular',
      rework_pct: 0,
      grade_pct: 92,
      fpd_pct: 3
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
      variability: 'triangular',
      rework_pct: 0,
      grade_pct: 95,
      fpd_pct: 2
    }
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
    weekend_ot_hours: 0
  },
  demands: [
    {
      product: 'Basic T-Shirt',
      bundle_size: 12,
      daily_demand: 500,
      weekly_demand: null,
      mix_share_pct: null
    }
  ],
  breakdowns: [
    {
      machine_tool: 'Serger Machine',
      breakdown_pct: 3
    },
    {
      machine_tool: 'Single Needle',
      breakdown_pct: 2
    }
  ],
  mode: 'demand-driven',
  horizon_days: 5
})

/**
 * Check if this is the first visit to the simulation tool
 * Uses localStorage to track visits
 */
export const isFirstVisit = () => {
  const key = 'simulation_v2_visited'
  const visited = localStorage.getItem(key)
  return !visited
}

/**
 * Mark the simulation tool as visited
 */
export const markAsVisited = () => {
  const key = 'simulation_v2_visited'
  localStorage.setItem(key, 'true')
}

/**
 * Clear the visited flag (for testing or reset purposes)
 */
export const clearVisitedFlag = () => {
  const key = 'simulation_v2_visited'
  localStorage.removeItem(key)
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
  getDefaultBreakdown
}
