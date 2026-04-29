import api from './client'

type Id = string | number
type Payload = Record<string, unknown>
type Params = Record<string, unknown>

// Downtime
export const createDowntimeEntry = (data: Payload) => api.post('/downtime', data)
export const getDowntimeEntries = (params?: Params) => api.get('/downtime', { params })
export const updateDowntimeEntry = (id: Id, data: Payload) => api.put(`/downtime/${id}`, data)
export const deleteDowntimeEntry = (id: Id) => api.delete(`/downtime/${id}`)

// Attendance
export const createAttendanceEntry = (data: Payload) => api.post('/attendance', data)
export const getAttendanceEntries = (params?: Params) => api.get('/attendance', { params })
export const updateAttendanceEntry = (id: Id, data: Payload) => api.put(`/attendance/${id}`, data)
export const deleteAttendanceEntry = (id: Id) => api.delete(`/attendance/${id}`)

export const bulkCreateAttendance = (records: Payload[]) => api.post('/attendance/bulk', records)

export const markAllPresent = (params?: Params) =>
  api.post('/attendance/mark-all-present', null, { params })

// Quality
export const createQualityEntry = (data: Payload) => api.post('/quality', data)
export const getQualityEntries = (params?: Params) => api.get('/quality', { params })
export const updateQualityEntry = (id: Id, data: Payload) => api.put(`/quality/${id}`, data)
export const deleteQualityEntry = (id: Id) => api.delete(`/quality/${id}`)

// Hold/Resume
export const createHoldEntry = (data: Payload) => api.post('/holds', data)
export const updateHoldEntry = (id: Id, data: Payload) => api.put(`/holds/${id}`, data)
export const deleteHoldEntry = (id: Id) => api.delete(`/holds/${id}`)
export const resumeHold = (id: Id, data: Payload) => api.post(`/holds/${id}/resume`, data)
export const getHoldEntries = (params?: Params) => api.get('/holds', { params })
export const getActiveHolds = (params?: Params) => api.get('/holds/active', { params })
