import api from './client'

// Dashboard Preferences
export const getDashboardPreferences = () => api.get('/preferences/dashboard')

export const saveDashboardPreferences = (data: Record<string, unknown>) =>
  api.put('/preferences/dashboard', data)

export const updateDashboardPreferences = (data: Record<string, unknown>) =>
  api.patch('/preferences/dashboard', data)

export const getDashboardDefaults = (role: string) => api.get(`/preferences/defaults/${role}`)

export const resetDashboardPreferences = () => api.post('/preferences/reset')

// Saved Filters
export const getSavedFilters = (params?: Record<string, unknown>) =>
  api.get('/filters', { params })

export const createSavedFilter = (data: Record<string, unknown>) => api.post('/filters', data)

export const getSavedFilter = (filterId: string | number) => api.get(`/filters/${filterId}`)

export const updateSavedFilter = (filterId: string | number, data: Record<string, unknown>) =>
  api.put(`/filters/${filterId}`, data)

export const deleteSavedFilter = (filterId: string | number) => api.delete(`/filters/${filterId}`)

export const applyFilter = (filterId: string | number) => api.post(`/filters/${filterId}/apply`)

export const setDefaultFilter = (filterId: string | number) =>
  api.post(`/filters/${filterId}/set-default`)

export const duplicateFilter = (filterId: string | number, newName: string) =>
  api.post(`/filters/${filterId}/duplicate`, { new_name: newName })

export const getFilterHistory = () => api.get('/filters/history/recent')

export const clearFilterHistory = () => api.delete('/filters/history')
