import api from './client'

export interface CapacityRequirementsPayload {
  target_units: number
  target_date: string
  cycle_time_hours?: number
  shift_hours?: number
  target_efficiency?: number
  absenteeism_rate?: number
  include_buffer?: boolean
}

export interface ProductionLineConfigParams {
  num_stations?: number
  workers_per_station?: number
  floating_pool_size?: number
  base_cycle_time?: number
}

export interface ProductionLineRunParams {
  duration_hours?: number
  arrival_rate_per_hour?: number
  max_units?: number
  random_seed?: number
}

export interface CompareScenariosParams {
  duration_hours?: number
  random_seed?: number
}

export const calculateCapacityRequirements = (data: CapacityRequirementsPayload) =>
  api.post('/simulation/capacity-requirements', data)

export const getProductionLineGuide = () => api.get('/simulation/production-line/guide')

export const getDefaultProductionLineConfig = (params?: ProductionLineConfigParams) =>
  api.get('/simulation/production-line/default', { params })

export const runProductionLineSimulation = (
  config: Record<string, unknown>,
  params?: ProductionLineRunParams,
) => api.post('/simulation/production-line/run', config, { params })

export const compareProductionScenarios = (
  baseConfig: Record<string, unknown>,
  scenarios: Record<string, unknown>[],
  params?: CompareScenariosParams,
) =>
  api.post(
    '/simulation/production-line/compare',
    { base_config: baseConfig, scenarios },
    { params },
  )

export const getFloatingPoolSimulationInsights = (params?: { target_date?: string }) =>
  api.get('/floating-pool/simulation/insights', { params })
