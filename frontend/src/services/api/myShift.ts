import api from './client'

// Params mirror the real backend contract (backend/routes/my_shift.py):
// shift_date (defaults server-side to today), shift_id (SHIFT.shift_id FK,
// optional), operator_id (accepted for forward-compatibility, currently
// advisory only server-side — see the route's docstring).
export interface MyShiftParams {
  shift_date?: string
  shift_id?: number
  operator_id?: string
}

export interface MyShiftActivityParams extends MyShiftParams {
  limit?: number
}

export const getMyShiftSummary = (params: MyShiftParams = {}) =>
  api.get('/my-shift/summary', { params })

export const getMyShiftStats = (params: MyShiftParams = {}) => api.get('/my-shift/stats', { params })

export const getMyShiftActivity = (params: MyShiftActivityParams = {}) =>
  api.get('/my-shift/activity', { params })
