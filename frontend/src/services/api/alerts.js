/**
 * Alerts API Module
 * Intelligent alerting system for proactive KPI management
 */
import api from './client'

/**
 * Get list of alerts with optional filters
 */
export const getAlerts = (params = {}) => {
  const searchParams = new URLSearchParams()
  if (params.client_id) searchParams.append('client_id', params.client_id)
  if (params.category) searchParams.append('category', params.category)
  if (params.severity) searchParams.append('severity', params.severity)
  if (params.status) searchParams.append('status', params.status)
  if (params.kpi_key) searchParams.append('kpi_key', params.kpi_key)
  if (params.days) searchParams.append('days', params.days)
  if (params.limit) searchParams.append('limit', params.limit)

  return api.get(`/alerts/?${searchParams.toString()}`)
}

/**
 * Get alert dashboard with summary and urgent alerts
 */
export const getAlertDashboard = (clientId = null) => {
  const params = clientId ? `?client_id=${clientId}` : ''
  return api.get(`/alerts/dashboard${params}`)
}

/**
 * Get quick alert summary
 */
export const getAlertSummary = (clientId = null) => {
  const params = clientId ? `?client_id=${clientId}` : ''
  return api.get(`/alerts/summary${params}`)
}

/**
 * Get specific alert by ID
 */
export const getAlert = (alertId) => api.get(`/alerts/${alertId}`)

/**
 * Create new alert manually
 */
export const createAlert = (alertData) => api.post('/alerts/', alertData)

/**
 * Acknowledge an alert
 */
export const acknowledgeAlert = (alertId, notes = null) =>
  api.post(`/alerts/${alertId}/acknowledge`, { notes })

/**
 * Resolve an alert
 */
export const resolveAlert = (alertId, resolutionNotes) =>
  api.post(`/alerts/${alertId}/resolve`, { resolution_notes: resolutionNotes })

/**
 * Dismiss an alert
 */
export const dismissAlert = (alertId) =>
  api.post(`/alerts/${alertId}/dismiss`)

/**
 * Run all alert checks and generate new alerts
 */
export const generateAlerts = (clientId = null) => {
  const params = clientId ? `?client_id=${clientId}` : ''
  return api.post(`/alerts/generate/check-all${params}`)
}

/**
 * Check OTD risk alerts
 */
export const checkOTDAlerts = (clientId = null) => {
  const params = clientId ? `?client_id=${clientId}` : ''
  return api.post(`/alerts/generate/otd-risk${params}`)
}

/**
 * Check quality alerts
 */
export const checkQualityAlerts = (clientId = null) => {
  const params = clientId ? `?client_id=${clientId}` : ''
  return api.post(`/alerts/generate/quality${params}`)
}

/**
 * Check capacity alerts
 */
export const checkCapacityAlerts = (params) => {
  const searchParams = new URLSearchParams()
  searchParams.append('load_percent', params.load_percent)
  if (params.predicted_idle_days) searchParams.append('predicted_idle_days', params.predicted_idle_days)
  if (params.overtime_hours_needed) searchParams.append('overtime_hours_needed', params.overtime_hours_needed)
  if (params.bottleneck_station) searchParams.append('bottleneck_station', params.bottleneck_station)
  if (params.client_id) searchParams.append('client_id', params.client_id)

  return api.post(`/alerts/generate/capacity?${searchParams.toString()}`)
}

/**
 * Get alert configurations
 */
export const getAlertConfigs = (clientId = null) => {
  const params = clientId ? `?client_id=${clientId}` : ''
  return api.get(`/alerts/config/${params}`)
}

/**
 * Create alert configuration
 */
export const createAlertConfig = (configData) =>
  api.post('/alerts/config/', configData)

/**
 * Get prediction accuracy history
 */
export const getPredictionAccuracy = (params = {}) => {
  const searchParams = new URLSearchParams()
  if (params.days) searchParams.append('days', params.days)
  if (params.category) searchParams.append('category', params.category)

  return api.get(`/alerts/history/accuracy?${searchParams.toString()}`)
}
