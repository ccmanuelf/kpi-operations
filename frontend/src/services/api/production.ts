import api from './client'

export const createProductionEntry = (data: Record<string, unknown>) => api.post('/production', data)

export const getProductionEntries = (params?: Record<string, unknown>) =>
  api.get('/production', { params })

export const getProductionEntry = (id: string | number) => api.get(`/production/${id}`)

export const updateProductionEntry = (id: string | number, data: Record<string, unknown>) =>
  api.put(`/production/${id}`, data)

export const deleteProductionEntry = (id: string | number) => api.delete(`/production/${id}`)

export const uploadCSV = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/production/upload/csv', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export const batchImportProduction = (entries: Record<string, unknown>[]) =>
  api.post('/production/batch-import', { entries })
