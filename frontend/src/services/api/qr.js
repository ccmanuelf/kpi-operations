import api from './client'

export const lookupQR = (data) => api.get('/qr/lookup', { params: { data } })

export const generateQRImage = (entityType, entityId) => api.post('/qr/generate/image', { entity_type: entityType, entity_id: entityId }, { responseType: 'blob' })
