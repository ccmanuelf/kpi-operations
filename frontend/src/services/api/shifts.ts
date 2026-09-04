/**
 * Shift master-data API client.
 *
 * Reads are open to any authenticated user; create/update/delete require the
 * supervisory tier (backend/routes/shifts.py). Create and update return the
 * row alongside soft-validation `warnings` — overlapping shifts are permitted
 * but reported, and POST /shifts/check-overlap exists so a caller can raise
 * that warning BEFORE committing.
 */

import api from './client'

/** Times are `HH:MM:SS` on the wire (Python `datetime.time`). */
export interface Shift {
  shift_id: number
  client_id: string
  shift_name: string
  start_time: string
  end_time: string
  is_active: boolean
  created_at: string
}

export interface ShiftWithWarnings {
  data: Shift
  warnings: string[]
}

export interface OverlapInfo {
  shift_id: number
  shift_name: string
  start_time: string
  end_time: string
}

export interface OverlapCheckResponse {
  has_overlaps: boolean
  overlaps: OverlapInfo[]
}

/**
 * Scoped to the caller's authorized clients. Active-only unless
 * `includeInactive`, since DELETE is a soft delete.
 *
 * The trailing slash is required: the backend route is `/` under prefix
 * `/api/shifts`, and without it FastAPI 307s — axios drops Authorization on
 * the cross-origin redirect the Vite proxy produces, which 401s and logs the
 * user out. Same reason `reference.ts` spells it `/shifts/`.
 */
export const listShifts = (clientId?: string | number | null, includeInactive = false) => {
  const params: Record<string, unknown> = {}
  if (clientId) params.client_id = clientId
  // Without this the admin screen can deactivate a shift and never see it
  // again to reactivate it, even though PUT accepts is_active.
  if (includeInactive) params.include_inactive = true
  return api.get<Shift[]>('/shifts/', Object.keys(params).length ? { params } : undefined)
}

export const createShift = (data: {
  client_id: string
  shift_name: string
  start_time: string
  end_time: string
}) => api.post<ShiftWithWarnings>('/shifts/', data)

export const updateShift = (
  shiftId: number,
  data: {
    shift_name?: string
    start_time?: string
    end_time?: string
    is_active?: boolean
  },
) => api.put<ShiftWithWarnings>(`/shifts/${shiftId}`, data)

/** Soft delete — the backend deactivates rather than removing the row. */
export const deleteShift = (shiftId: number) => api.delete(`/shifts/${shiftId}`)

export const checkShiftOverlap = (data: {
  client_id: string
  start_time: string
  end_time: string
  exclude_shift_id?: number
}) => api.post<OverlapCheckResponse>('/shifts/check-overlap', data)
