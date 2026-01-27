import api from './client'

/**
 * Workflow API Service
 * Phase 10: Flexible Workflow Foundation
 * Provides endpoints for status transitions, history, and configuration
 */

// ============================================
// Status Transitions
// ============================================

/**
 * Transition a work order to a new status
 * @param {string} workOrderId - Work order ID
 * @param {string} toStatus - Target status
 * @param {string} notes - Optional transition notes
 */
export const transitionWorkOrder = (workOrderId, toStatus, notes = null) =>
  api.post(`/api/workflow/work-orders/${workOrderId}/transition`, {
    to_status: toStatus,
    notes
  })

/**
 * Validate if a transition is allowed
 * @param {string} workOrderId - Work order ID
 * @param {string} toStatus - Target status to validate
 */
export const validateTransition = (workOrderId, toStatus) =>
  api.post(`/api/workflow/work-orders/${workOrderId}/validate`, null, {
    params: { to_status: toStatus }
  })

/**
 * Get allowed transitions for a work order
 * @param {string} workOrderId - Work order ID
 */
export const getAllowedTransitions = (workOrderId) =>
  api.get(`/api/workflow/work-orders/${workOrderId}/allowed-transitions`)

/**
 * Get transition history for a work order
 * @param {string} workOrderId - Work order ID
 */
export const getTransitionHistory = (workOrderId) =>
  api.get(`/api/workflow/work-orders/${workOrderId}/history`)

// ============================================
// Bulk Operations
// ============================================

/**
 * Bulk transition multiple work orders
 * @param {string[]} workOrderIds - Array of work order IDs
 * @param {string} toStatus - Target status
 * @param {string} clientId - Client ID
 * @param {string} notes - Optional notes
 */
export const bulkTransition = (workOrderIds, toStatus, clientId, notes = null) =>
  api.post('/api/workflow/bulk-transition', {
    work_order_ids: workOrderIds,
    to_status: toStatus,
    notes
  }, {
    params: { client_id: clientId }
  })

// ============================================
// Workflow Configuration
// ============================================

/**
 * Get workflow configuration for a client
 * @param {string} clientId - Client ID
 */
export const getWorkflowConfig = (clientId) =>
  api.get(`/api/workflow/config/${clientId}`)

/**
 * Update workflow configuration for a client
 * @param {string} clientId - Client ID
 * @param {object} config - Configuration updates
 */
export const updateWorkflowConfig = (clientId, config) =>
  api.put(`/api/workflow/config/${clientId}`, config)

/**
 * Apply a workflow template to a client
 * @param {string} clientId - Client ID
 * @param {string} templateId - Template ID to apply
 */
export const applyWorkflowTemplate = (clientId, templateId) =>
  api.post(`/api/workflow/config/${clientId}/apply-template`, null, {
    params: { template_id: templateId }
  })

/**
 * List available workflow templates
 */
export const getWorkflowTemplates = () =>
  api.get('/api/workflow/templates')

// ============================================
// Elapsed Time Analytics
// ============================================

/**
 * Get elapsed time metrics for a work order
 * @param {string} workOrderId - Work order ID
 */
export const getWorkOrderElapsedTime = (workOrderId) =>
  api.get(`/api/workflow/work-orders/${workOrderId}/elapsed-time`)

/**
 * Get transition times for a work order
 * @param {string} workOrderId - Work order ID
 */
export const getWorkOrderTransitionTimes = (workOrderId) =>
  api.get(`/api/workflow/work-orders/${workOrderId}/transition-times`)

/**
 * Get average elapsed times for a client
 * @param {string} clientId - Client ID
 * @param {object} params - Optional filters (status, start_date, end_date)
 */
export const getClientAverageTimes = (clientId, params = {}) =>
  api.get(`/api/workflow/analytics/${clientId}/average-times`, { params })

/**
 * Get stage duration summary for a client
 * @param {string} clientId - Client ID
 * @param {object} params - Optional filters (start_date, end_date)
 */
export const getClientStageDurations = (clientId, params = {}) =>
  api.get(`/api/workflow/analytics/${clientId}/stage-durations`, { params })

// ============================================
// Statistics & Reporting
// ============================================

/**
 * Get transition statistics for a client
 * @param {string} clientId - Client ID
 */
export const getTransitionStatistics = (clientId) =>
  api.get(`/api/workflow/statistics/${clientId}/transitions`)

/**
 * Get status distribution for a client
 * @param {string} clientId - Client ID
 */
export const getStatusDistribution = (clientId) =>
  api.get(`/api/workflow/statistics/${clientId}/status-distribution`)

/**
 * Get all transitions for a client
 * @param {string} clientId - Client ID
 * @param {object} params - Query params (skip, limit, from_status, to_status, trigger_source)
 */
export const getClientTransitions = (clientId, params = {}) =>
  api.get(`/api/workflow/transitions/${clientId}`, { params })

// Export all functions as default object for backward compatibility
export default {
  transitionWorkOrder,
  validateTransition,
  getAllowedTransitions,
  getTransitionHistory,
  bulkTransition,
  getWorkflowConfig,
  updateWorkflowConfig,
  applyWorkflowTemplate,
  getWorkflowTemplates,
  getWorkOrderElapsedTime,
  getWorkOrderTransitionTimes,
  getClientAverageTimes,
  getClientStageDurations,
  getTransitionStatistics,
  getStatusDistribution,
  getClientTransitions
}
