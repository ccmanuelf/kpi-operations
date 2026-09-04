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
// Trailing slash matches the backend's APIRouter("/") definition (same
// rationale as production-lines below): without it, FastAPI 307-redirects,
// and behind a reverse proxy that doesn't forward X-Forwarded-Proto trust,
// the redirect's Location header can downgrade https->http, which the
// browser blocks as mixed content (ISSUE-012 — this was the captured
// casualty: "Failed to load quality entries").
export const createQualityEntry = (data: Payload) => api.post('/quality/', data)
export const getQualityEntries = (params?: Params) => api.get('/quality/', { params })
export const updateQualityEntry = (id: Id, data: Payload) => api.put(`/quality/${id}`, data)
export const deleteQualityEntry = (id: Id) => api.delete(`/quality/${id}`)

// Hold/Resume
// Resume workflow uses approval endpoints (request-resume, approve-resume) called
// directly from useHoldGridForms._approvalRequest, not a single /resume URL.
export const createHoldEntry = (data: Payload) => api.post('/holds', data)
export const updateHoldEntry = (id: Id, data: Payload) => api.put(`/holds/${id}`, data)
export const deleteHoldEntry = (id: Id) => api.delete(`/holds/${id}`)
export const getHoldEntries = (params?: Params) => api.get('/holds', { params })

/**
 * The client's ACTIVE hold reasons.
 *
 * Hold creation is gated on this server-side: routes/holds.py rejects any
 * reason not active in the client's catalog with 422 "Reason X not found in
 * client catalog". The grid used to offer a hardcoded list instead, which
 * both omitted real catalog entries and could offer ones a given tenant had
 * disabled.
 */
export const getHoldReasonCatalog = (clientId: string | number) =>
  api.get('/hold-catalogs/reasons', { params: { client_id: clientId } })
export const getActiveHolds = (params?: Params) => api.get('/holds/active', { params })
