import api from './client'

export interface PlanVsActualParams {
  client_id?: string | number
  start_date?: string
  end_date?: string
  line_id?: string
  status?: string
}

export function getPlanVsActual(params: PlanVsActualParams = {}) {
  return api.get('/plan-vs-actual', { params })
}

export function getPlanVsActualSummary(params: { client_id?: string | number } = {}) {
  return api.get('/plan-vs-actual/summary', { params })
}
