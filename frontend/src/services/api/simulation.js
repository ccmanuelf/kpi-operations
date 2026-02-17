import api from './client'

// =============================================================================
// SimPy Production Line Simulation
// =============================================================================

/**
 * Calculate capacity requirements for production target
 * @param {Object} data - { target_units, target_date, cycle_time_hours, shift_hours, target_efficiency, absenteeism_rate, include_buffer }
 */
export const calculateCapacityRequirements = (data) => api.post('/simulation/capacity-requirements', data)

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

// =============================================================================
// Floating Pool Simulation Integration
// =============================================================================

/**
 * Get simulation-based insights for floating pool optimization
 * @param {Object} params - { target_date }
 */
export const getFloatingPoolSimulationInsights = (params) =>
  api.get('/floating-pool/simulation/insights', { params })
