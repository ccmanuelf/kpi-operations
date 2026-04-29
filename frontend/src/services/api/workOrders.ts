import api from './client'

export const getWorkOrders = (params?: Record<string, unknown>) =>
  api.get('/work-orders', { params })

export const getWorkOrder = (id: string | number) => api.get(`/work-orders/${id}`)

export const getWorkOrdersByStatus = (status: string, params?: Record<string, unknown>) =>
  api.get(`/work-orders/status/${status}`, { params })

export const getWorkOrdersByDateRange = (
  startDate: string,
  endDate: string,
  params?: Record<string, unknown>,
) =>
  api.get('/work-orders/date-range', {
    params: { start_date: startDate, end_date: endDate, ...params },
  })

export const createWorkOrder = (data: Record<string, unknown>) => api.post('/work-orders', data)

export const updateWorkOrder = (id: string | number, data: Record<string, unknown>) =>
  api.put(`/work-orders/${id}`, data)

export const deleteWorkOrder = (id: string | number) => api.delete(`/work-orders/${id}`)

export const updateWorkOrderStatus = (id: string | number, status: string) =>
  api.put(`/work-orders/${id}`, { status })

export const getWorkOrderProgress = (id: string | number) => api.get(`/work-orders/${id}/progress`)

export const getWorkOrderTimeline = (id: string | number) => api.get(`/work-orders/${id}/timeline`)

export const getClientWorkOrders = (clientId: string | number, params?: Record<string, unknown>) =>
  api.get(`/clients/${clientId}/work-orders`, { params })
