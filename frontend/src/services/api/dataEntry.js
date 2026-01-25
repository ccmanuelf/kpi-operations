import api from './client'

// Downtime
export const createDowntimeEntry = (data) => api.post('/downtime', data)

export const getDowntimeEntries = (params) => api.get('/downtime', { params })

export const updateDowntimeEntry = (id, data) => api.put(`/downtime/${id}`, data)

export const deleteDowntimeEntry = (id) => api.delete(`/downtime/${id}`)

// Attendance
export const createAttendanceEntry = (data) => api.post('/attendance', data)

export const getAttendanceEntries = (params) => api.get('/attendance', { params })

export const updateAttendanceEntry = (id, data) => api.put(`/attendance/${id}`, data)

export const deleteAttendanceEntry = (id) => api.delete(`/attendance/${id}`)

// Quality
export const createQualityEntry = (data) => api.post('/quality', data)

export const getQualityEntries = (params) => api.get('/quality', { params })

export const updateQualityEntry = (id, data) => api.put(`/quality/${id}`, data)

export const deleteQualityEntry = (id) => api.delete(`/quality/${id}`)

// Hold/Resume
export const createHoldEntry = (data) => api.post('/holds', data)

export const updateHoldEntry = (id, data) => api.put(`/holds/${id}`, data)

export const deleteHoldEntry = (id) => api.delete(`/holds/${id}`)

export const resumeHold = (id, data) => api.post(`/holds/${id}/resume`, data)

export const getHoldEntries = (params) => api.get('/holds', { params })

export const getActiveHolds = (params) => api.get('/holds/active', { params })
