import api from './client'

export type KPIType =
  | 'efficiency'
  | 'performance'
  | 'availability'
  | 'oee'
  | 'ppm'
  | 'dpmo'
  | 'fpy'
  | 'rty'
  | 'absenteeism'
  | 'otd'

export interface PredictionParams {
  client_id?: string
  forecast_days?: number
  historical_days?: number
  method?: 'auto' | 'simple' | 'double' | 'linear'
}

export interface DashboardPredictionParams {
  client_id?: string
  forecast_days?: number
  historical_days?: number
}

export const getPrediction = (kpiType: KPIType, params?: PredictionParams) =>
  api.get(`/predictions/${kpiType}`, { params })

export const getAllPredictions = (params?: DashboardPredictionParams) =>
  api.get('/predictions/dashboard/all', { params })

export const getPredictionBenchmarks = () => api.get('/predictions/benchmarks')

export const getKPIHealth = (kpiType: KPIType, params?: { client_id?: string }) =>
  api.get(`/predictions/health/${kpiType}`, { params })
