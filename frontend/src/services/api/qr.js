import api from './client'

export const lookupQR = (data) => api.get('/qr/lookup', { params: { data } })

export const getWorkOrderQR = (workOrderId) => api.get(`/qr/work-order/${workOrderId}/image`, { responseType: 'blob' })

export const getProductQR = (productId) => api.get(`/qr/product/${productId}/image`, { responseType: 'blob' })

export const getJobQR = (jobId) => api.get(`/qr/job/${jobId}/image`, { responseType: 'blob' })

export const getEmployeeQR = (employeeId) => api.get(`/qr/employee/${employeeId}/image`, { responseType: 'blob' })

export const generateQR = (entityType, entityId) => api.post('/qr/generate', { entity_type: entityType, entity_id: entityId })

export const generateQRImage = (entityType, entityId) => api.post('/qr/generate/image', { entity_type: entityType, entity_id: entityId }, { responseType: 'blob' })
