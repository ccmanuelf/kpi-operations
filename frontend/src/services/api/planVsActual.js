import api from './client'

/**
 * Plan vs Actual API service
 * Fetches plan-vs-actual comparison data for capacity orders
 */

/**
 * Get plan vs actual detail entries with optional filters
 * @param {Object} params - Query parameters
 * @param {number} params.client_id - Client ID (required)
 * @param {string} [params.start_date] - Filter by start date (YYYY-MM-DD)
 * @param {string} [params.end_date] - Filter by end date (YYYY-MM-DD)
 * @param {string} [params.line_id] - Filter by production line
 * @param {string} [params.status] - Filter by order status
 * @returns {Promise} Axios response with array of plan vs actual entries
 */
export function getPlanVsActual(params = {}) {
  return api.get('/api/plan-vs-actual', { params })
}

/**
 * Get aggregate plan vs actual summary for a client
 * @param {Object} params - Query parameters
 * @param {number} params.client_id - Client ID (required)
 * @returns {Promise} Axios response with summary object
 */
export function getPlanVsActualSummary(params = {}) {
  return api.get('/api/plan-vs-actual/summary', { params })
}
