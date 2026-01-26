import api from './client'

/**
 * My Shift API Service
 * Provides personalized shift data for line operators
 */

/**
 * Get complete shift summary for current operator
 * @param {Object} params - Query parameters
 * @param {string} params.shift_date - Date for shift summary (YYYY-MM-DD)
 * @param {number} params.shift_number - Shift number (1-3)
 * @param {string} params.operator_id - Operator employee ID
 */
export const getMyShiftSummary = (params) =>
  api.get('/my-shift/summary', { params })

/**
 * Get just statistics for the shift (lightweight)
 * @param {Object} params - Query parameters
 */
export const getMyShiftStats = (params) =>
  api.get('/my-shift/stats', { params })

/**
 * Get recent activity entries for the shift
 * @param {Object} params - Query parameters
 * @param {string} params.shift_date - Date for activity
 * @param {number} params.shift_number - Shift number (1-3)
 * @param {number} params.limit - Maximum entries to return
 */
export const getMyShiftActivity = (params) =>
  api.get('/my-shift/activity', { params })
