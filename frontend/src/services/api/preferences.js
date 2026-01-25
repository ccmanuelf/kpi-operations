import api from './client'

// Dashboard Preferences
export const getDashboardPreferences = () => api.get('/preferences/dashboard')

export const saveDashboardPreferences = (data) => api.put('/preferences/dashboard', data)

export const updateDashboardPreferences = (data) => api.patch('/preferences/dashboard', data)

export const getDashboardDefaults = (role) => api.get(`/preferences/defaults/${role}`)

export const resetDashboardPreferences = () => api.post('/preferences/reset')

// Saved Filters
export const getSavedFilters = (params) => api.get('/filters', { params })

export const createSavedFilter = (data) => api.post('/filters', data)

export const getSavedFilter = (filterId) => api.get(`/filters/${filterId}`)

export const updateSavedFilter = (filterId, data) => api.put(`/filters/${filterId}`, data)

export const deleteSavedFilter = (filterId) => api.delete(`/filters/${filterId}`)

export const applyFilter = (filterId) => api.post(`/filters/${filterId}/apply`)

export const setDefaultFilter = (filterId) => api.post(`/filters/${filterId}/set-default`)

export const duplicateFilter = (filterId, newName) => api.post(`/filters/${filterId}/duplicate`, { new_name: newName })

export const getFilterHistory = () => api.get('/filters/history/recent')

export const clearFilterHistory = () => api.delete('/filters/history')
