import api from './client'

/**
 * Work Order API Service
 * Provides CRUD and enhanced endpoints for work order management
 */

// List work orders with filters
export const getWorkOrders = (params) => api.get('/work-orders', { params })

// Get single work order by ID
export const getWorkOrder = (id) => api.get(`/work-orders/${id}`)

// Get work orders by status
export const getWorkOrdersByStatus = (status, params) =>
  api.get(`/work-orders/status/${status}`, { params })

// Get work orders by date range
export const getWorkOrdersByDateRange = (startDate, endDate, params) =>
  api.get('/work-orders/date-range', {
    params: { start_date: startDate, end_date: endDate, ...params }
  })

// Create new work order
export const createWorkOrder = (data) => api.post('/work-orders', data)

// Update work order
export const updateWorkOrder = (id, data) => api.put(`/work-orders/${id}`, data)

// Delete work order (supervisor only)
export const deleteWorkOrder = (id) => api.delete(`/work-orders/${id}`)

// Update work order status only
export const updateWorkOrderStatus = (id, status) =>
  api.put(`/work-orders/${id}`, { status })

// Get work order progress with production entries
export const getWorkOrderProgress = (id) => api.get(`/work-orders/${id}/progress`)

// Get work order activity timeline
export const getWorkOrderTimeline = (id) => api.get(`/work-orders/${id}/timeline`)

// Get work orders for a specific client
export const getClientWorkOrders = (clientId, params) =>
  api.get(`/clients/${clientId}/work-orders`, { params })
