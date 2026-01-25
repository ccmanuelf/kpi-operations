import api from './client'

// Clients CRUD
export const getClients = () => api.get('/clients')

export const getClient = (clientId) => api.get(`/clients/${clientId}`)

export const createClient = (data) => api.post('/clients', data)

export const updateClient = (clientId, data) => api.put(`/clients/${clientId}`, data)

export const deleteClient = (clientId) => api.delete(`/clients/${clientId}`)

// Users CRUD (Admin)
export const getUsers = () => api.get('/users')

export const getUser = (userId) => api.get(`/users/${userId}`)

export const createUser = (data) => api.post('/users', data)

export const updateUser = (userId, data) => api.put(`/users/${userId}`, data)

export const deleteUser = (userId) => api.delete(`/users/${userId}`)

// KPI Thresholds
export const getKPIThresholds = (clientId = null) => {
  const params = clientId ? { client_id: clientId } : {}
  return api.get('/kpi-thresholds', { params })
}

export const updateKPIThresholds = (data) => api.put('/kpi-thresholds', data)

export const deleteClientThreshold = (clientId, kpiKey) => api.delete(`/kpi-thresholds/${clientId}/${kpiKey}`)

// Defect Type Catalog (Client-specific)
export const getDefectTypes = (clientId) => {
  // If clientId provided, get client-specific defect types
  if (clientId) {
    return api.get(`/defect-types/client/${clientId}`)
  }
  // Fallback: try to get from user's assigned client or return empty
  return api.get('/defect-types/client/default').catch(() => ({ data: [] }))
}

export const getDefectTypesByClient = (clientId, includeInactive = false, includeGlobal = true) => {
  return api.get(`/defect-types/client/${clientId}`, {
    params: {
      include_inactive: includeInactive,
      include_global: includeGlobal
    }
  })
}

export const getGlobalDefectTypes = (includeInactive = false) => {
  return api.get('/defect-types/global', {
    params: { include_inactive: includeInactive }
  })
}

export const createDefectType = (data) => api.post('/defect-types', data)

export const updateDefectType = (defectTypeId, data) => api.put(`/defect-types/${defectTypeId}`, data)

export const deleteDefectType = (defectTypeId) => api.delete(`/defect-types/${defectTypeId}`)

export const uploadDefectTypes = (clientId, file, replaceExisting = false) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('replace_existing', replaceExisting)
  return api.post(`/defect-types/upload/${clientId}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const getDefectTypeTemplate = () => api.get('/defect-types/template/download')
