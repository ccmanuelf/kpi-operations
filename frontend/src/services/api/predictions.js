import api from './client'

/**
 * Get prediction for a single KPI with confidence intervals
 * @param {string} kpiType - Type of KPI (efficiency, performance, availability, oee, ppm, dpmo, fpy, rty, absenteeism, otd)
 * @param {Object} params - Query params: client_id, forecast_days (1-30), historical_days (7-90), method (auto|simple|double|linear)
 */
export const getPrediction = (kpiType, params) => api.get(`/predictions/${kpiType}`, { params })

/**
 * Get predictions for all KPIs in a single dashboard response
 * @param {Object} params - Query params: client_id, forecast_days (1-30), historical_days (7-90)
 */
export const getAllPredictions = (params) => api.get('/predictions/dashboard/all', { params })

/**
 * Get KPI benchmarks for all metrics
 */
export const getPredictionBenchmarks = () => api.get('/predictions/benchmarks')

/**
 * Get quick health assessment for a specific KPI
 * @param {string} kpiType - Type of KPI
 * @param {Object} params - Query params: client_id
 */
export const getKPIHealth = (kpiType, params) => api.get(`/predictions/health/${kpiType}`, { params })
