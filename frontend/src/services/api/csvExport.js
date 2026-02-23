import api from './client'

/**
 * CSV Export API functions
 *
 * Each function requests a CSV download from the backend export endpoints.
 * Returns an axios response with responseType: 'blob' for binary download.
 */

/**
 * Export production entries as CSV.
 * @param {Object} params - { client_id?, start_date?, end_date?, line_id? }
 */
export function exportProductionEntries(params = {}) {
  return api.get('/export/production-entries', { params, responseType: 'blob' })
}

/**
 * Export work orders as CSV.
 * @param {Object} params - { client_id?, start_date?, end_date? }
 */
export function exportWorkOrders(params = {}) {
  return api.get('/export/work-orders', { params, responseType: 'blob' })
}

/**
 * Export quality inspections as CSV.
 * @param {Object} params - { client_id?, start_date?, end_date? }
 */
export function exportQualityInspections(params = {}) {
  return api.get('/export/quality-inspections', { params, responseType: 'blob' })
}

/**
 * Export downtime events as CSV.
 * @param {Object} params - { client_id?, start_date?, end_date?, line_id? }
 */
export function exportDowntimeEvents(params = {}) {
  return api.get('/export/downtime-events', { params, responseType: 'blob' })
}

/**
 * Export attendance entries as CSV.
 * @param {Object} params - { client_id?, start_date?, end_date?, line_id? }
 */
export function exportAttendance(params = {}) {
  return api.get('/export/attendance', { params, responseType: 'blob' })
}

/**
 * Export employees as CSV.
 * @param {Object} params - { client_id? }
 */
export function exportEmployees(params = {}) {
  return api.get('/export/employees', { params, responseType: 'blob' })
}

/**
 * Export products as CSV.
 * @param {Object} params - { client_id? }
 */
export function exportProducts(params = {}) {
  return api.get('/export/products', { params, responseType: 'blob' })
}

/**
 * Export shifts as CSV.
 * @param {Object} params - { client_id? }
 */
export function exportShifts(params = {}) {
  return api.get('/export/shifts', { params, responseType: 'blob' })
}

/**
 * Export hold entries as CSV.
 * @param {Object} params - { client_id?, start_date?, end_date? }
 */
export function exportHolds(params = {}) {
  return api.get('/export/holds', { params, responseType: 'blob' })
}
