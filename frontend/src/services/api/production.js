import api from './client'

export const createProductionEntry = (data) => api.post('/production', data)

export const getProductionEntries = (params) => api.get('/production', { params })

export const getProductionEntry = (id) => api.get(`/production/${id}`)

export const updateProductionEntry = (id, data) => api.put(`/production/${id}`, data)

export const deleteProductionEntry = (id) => api.delete(`/production/${id}`)

export const uploadCSV = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/production/upload/csv', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

export const batchImportProduction = (entries) => api.post('/production/batch-import', { entries })
