import api from './client'

/**
 * Get simulation capabilities overview
 */
export const getSimulationOverview = () => api.get('/simulation/')

/**
 * Calculate capacity requirements for production target
 * @param {Object} data - { target_units, target_date, cycle_time_hours, shift_hours, target_efficiency, absenteeism_rate, include_buffer }
 */
export const calculateCapacityRequirements = (data) => api.post('/simulation/capacity-requirements', data)

/**
 * Calculate production capacity given staffing levels
 * @param {Object} data - { employees, shift_hours, cycle_time_hours, efficiency_percent }
 */
export const calculateProductionCapacity = (data) => api.post('/simulation/production-capacity', data)

/**
 * Run staffing simulation with multiple scenarios
 * @param {Object} data - { base_employees, scenarios, shift_hours, cycle_time_hours, base_efficiency, efficiency_scaling }
 */
export const runStaffingSimulation = (data) => api.post('/simulation/staffing', data)

/**
 * Run efficiency simulation with multiple scenarios
 * @param {Object} data - { employees, efficiency_scenarios, shift_hours, cycle_time_hours, base_efficiency }
 */
export const runEfficiencySimulation = (data) => api.post('/simulation/efficiency', data)

/**
 * Simulate shift coverage with regular and floating pool employees
 * @param {Object} data - { shift_id, shift_name, regular_employees, floating_pool_available, required_employees, target_date }
 */
export const simulateShiftCoverage = (data) => api.post('/simulation/shift-coverage', data)

/**
 * Simulate coverage across multiple shifts with floating pool allocation
 * @param {Object} data - { shifts: [], floating_pool_total }
 */
export const simulateMultiShiftCoverage = (data) => api.post('/simulation/multi-shift-coverage', data)

/**
 * Optimize floating pool employee allocation across shifts
 * @param {Object} data - { available_pool_employees, shift_requirements, optimization_goal, target_date }
 */
export const optimizeFloatingPool = (data) => api.post('/simulation/floating-pool-optimization', data)

/**
 * Run comprehensive capacity simulation
 * @param {Object} data - { target_units, current_employees, shift_hours, cycle_time_hours, efficiency, staffing_scenarios, efficiency_scenarios }
 */
export const runComprehensiveSimulation = (data) => api.post('/simulation/comprehensive', data)

/**
 * Quick capacity calculation via query parameters
 * @param {Object} params - { employees, target_units, shift_hours, cycle_time_hours, efficiency }
 */
export const quickCapacityCheck = (params) => api.get('/simulation/quick/capacity', { params })

/**
 * Quick staffing requirement calculation via query parameters
 * @param {Object} params - { target_units, shift_hours, cycle_time_hours, efficiency }
 */
export const quickStaffingCheck = (params) => api.get('/simulation/quick/staffing', { params })

// =============================================================================
// SimPy Production Line Simulation
// =============================================================================

/**
 * Get production line simulation guide
 */
export const getProductionLineGuide = () => api.get('/simulation/production-line/guide')

/**
 * Get default production line configuration
 * @param {Object} params - { num_stations, workers_per_station, floating_pool_size, base_cycle_time }
 */
export const getDefaultProductionLineConfig = (params) => api.get('/simulation/production-line/default', { params })

/**
 * Run production line simulation
 * @param {Object} config - Production line configuration
 * @param {Object} params - { duration_hours, arrival_rate_per_hour, max_units, random_seed }
 */
export const runProductionLineSimulation = (config, params) => api.post('/simulation/production-line/run', config, { params })

/**
 * Compare production scenarios
 * @param {Object} data - { base_config, scenarios }
 * @param {Object} params - { duration_hours, random_seed }
 */
export const compareProductionScenarios = (baseConfig, scenarios, params) =>
  api.post('/simulation/production-line/compare', { base_config: baseConfig, scenarios }, { params })

/**
 * Analyze production bottlenecks
 * @param {Object} config - Production line configuration
 * @param {Object} params - { duration_hours, random_seed }
 */
export const analyzeProductionBottlenecks = (config, params) =>
  api.post('/simulation/production-line/bottlenecks', config, { params })

/**
 * Analyze floating pool impact on production
 * @param {Object} config - Production line configuration
 * @param {Object} params - { pool_sizes, duration_hours, random_seed }
 */
export const analyzeFloatingPoolImpact = (config, params) =>
  api.post('/simulation/production-line/floating-pool-impact', config, { params })

// =============================================================================
// Floating Pool Simulation Integration
// =============================================================================

/**
 * Get simulation-based insights for floating pool optimization
 * @param {Object} params - { target_date }
 */
export const getFloatingPoolSimulationInsights = (params) =>
  api.get('/floating-pool/simulation/insights', { params })

/**
 * Optimize floating pool allocation across shifts
 * @param {Object} data - { shift_requirements, optimization_goal, target_date }
 */
export const optimizeFloatingPoolAllocation = (data) =>
  api.post('/floating-pool/simulation/optimize-allocation', data.shift_requirements, {
    params: {
      optimization_goal: data.optimization_goal,
      target_date: data.target_date
    }
  })

/**
 * Simulate coverage for a specific shift
 * @param {Object} data - { shift_id, shift_name, regular_employees, floating_pool_available, required_employees, target_date }
 */
export const simulateShiftCoverageWithPool = (data) =>
  api.post('/floating-pool/simulation/shift-coverage', null, { params: data })
