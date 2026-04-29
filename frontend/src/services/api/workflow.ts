import api from './client'

type Id = string | number
type Params = Record<string, unknown>

// Status Transitions
export const transitionWorkOrder = (workOrderId: Id, toStatus: string, notes: string | null = null) =>
  api.post(`/workflow/work-orders/${workOrderId}/transition`, {
    to_status: toStatus,
    notes,
  })

export const validateTransition = (workOrderId: Id, toStatus: string) =>
  api.post(`/workflow/work-orders/${workOrderId}/validate`, null, {
    params: { to_status: toStatus },
  })

export const getAllowedTransitions = (workOrderId: Id) =>
  api.get(`/workflow/work-orders/${workOrderId}/allowed-transitions`)

export const getTransitionHistory = (workOrderId: Id) =>
  api.get(`/workflow/work-orders/${workOrderId}/history`)

// Bulk Operations
export const bulkTransition = (
  workOrderIds: Id[],
  toStatus: string,
  clientId: Id,
  notes: string | null = null,
) =>
  api.post(
    '/workflow/bulk-transition',
    {
      work_order_ids: workOrderIds,
      to_status: toStatus,
      notes,
    },
    {
      params: { client_id: clientId },
    },
  )

// Workflow Configuration
export const getWorkflowConfig = (clientId: Id) => api.get(`/workflow/config/${clientId}`)

export const updateWorkflowConfig = (clientId: Id, config: Params) =>
  api.put(`/workflow/config/${clientId}`, config)

export const applyWorkflowTemplate = (clientId: Id, templateId: Id) =>
  api.post(`/workflow/config/${clientId}/apply-template`, null, {
    params: { template_id: templateId },
  })

export const getWorkflowTemplates = () => api.get('/workflow/templates')

// Elapsed Time Analytics
export const getWorkOrderElapsedTime = (workOrderId: Id) =>
  api.get(`/workflow/work-orders/${workOrderId}/elapsed-time`)

export const getWorkOrderTransitionTimes = (workOrderId: Id) =>
  api.get(`/workflow/work-orders/${workOrderId}/transition-times`)

export const getClientAverageTimes = (clientId: Id, params: Params = {}) =>
  api.get(`/workflow/analytics/${clientId}/average-times`, { params })

export const getClientStageDurations = (clientId: Id, params: Params = {}) =>
  api.get(`/workflow/analytics/${clientId}/stage-durations`, { params })

// Statistics & Reporting
export const getTransitionStatistics = (clientId: Id) =>
  api.get(`/workflow/statistics/${clientId}/transitions`)

export const getStatusDistribution = (clientId: Id) =>
  api.get(`/workflow/statistics/${clientId}/status-distribution`)

export const getClientTransitions = (clientId: Id, params: Params = {}) =>
  api.get(`/workflow/transitions/${clientId}`, { params })

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
  getClientTransitions,
}
