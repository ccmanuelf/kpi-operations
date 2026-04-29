import api from './client'

type Id = string | number
type Payload = Record<string, unknown>

// Clients CRUD
export const getClients = () => api.get('/clients')
export const getClient = (clientId: Id) => api.get(`/clients/${clientId}`)
export const createClient = (data: Payload) => api.post('/clients', data)
export const updateClient = (clientId: Id, data: Payload) =>
  api.put(`/clients/${clientId}`, data)
export const deleteClient = (clientId: Id) => api.delete(`/clients/${clientId}`)

// Users CRUD (Admin)
export const getUsers = () => api.get('/users')
export const getUser = (userId: Id) => api.get(`/users/${userId}`)
export const createUser = (data: Payload) => api.post('/users', data)
export const updateUser = (userId: Id, data: Payload) => api.put(`/users/${userId}`, data)
export const deleteUser = (userId: Id) => api.delete(`/users/${userId}`)

// KPI Thresholds
export const getKPIThresholds = (clientId: Id | null = null) => {
  const params = clientId ? { client_id: clientId } : {}
  return api.get('/kpi-thresholds', { params })
}

export const updateKPIThresholds = (data: Payload) => api.put('/kpi-thresholds', data)

export const deleteClientThreshold = (clientId: Id, kpiKey: string) =>
  api.delete(`/kpi-thresholds/${clientId}/${kpiKey}`)

// Defect Type Catalog (Client-specific)
export const getDefectTypes = (clientId?: Id) => {
  if (clientId) {
    return api.get(`/defect-types/client/${clientId}`)
  }
  return api.get('/defect-types/client/default').catch(() => ({ data: [] }))
}

export const getDefectTypesByClient = (
  clientId: Id,
  includeInactive = false,
  includeGlobal = true,
) => {
  return api.get(`/defect-types/client/${clientId}`, {
    params: {
      include_inactive: includeInactive,
      include_global: includeGlobal,
    },
  })
}

export const getGlobalDefectTypes = (includeInactive = false) => {
  return api.get('/defect-types/global', {
    params: { include_inactive: includeInactive },
  })
}

export const createDefectType = (data: Payload) => api.post('/defect-types', data)

export const updateDefectType = (defectTypeId: Id, data: Payload) =>
  api.put(`/defect-types/${defectTypeId}`, data)

export const deleteDefectType = (defectTypeId: Id) => api.delete(`/defect-types/${defectTypeId}`)

export const uploadDefectTypes = (clientId: Id, file: File, replaceExisting = false) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('replace_existing', String(replaceExisting))
  return api.post(`/defect-types/upload/${clientId}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getDefectTypeTemplate = () => api.get('/defect-types/template/download')
