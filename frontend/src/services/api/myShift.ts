import api from './client'

export interface MyShiftParams {
  shift_date: string
  shift_number: 1 | 2 | 3
  operator_id?: string
}

export interface MyShiftActivityParams extends Omit<MyShiftParams, 'operator_id'> {
  limit?: number
}

export const getMyShiftSummary = (params: MyShiftParams) =>
  api.get('/my-shift/summary', { params })

export const getMyShiftStats = (params: MyShiftParams) => api.get('/my-shift/stats', { params })

export const getMyShiftActivity = (params: MyShiftActivityParams) =>
  api.get('/my-shift/activity', { params })
