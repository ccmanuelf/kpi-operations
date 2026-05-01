/**
 * Inspector API client — Phase 4 dual-view UI.
 *
 * Wraps GET /api/metrics/results and GET /api/metrics/results/{id}.
 */

import api from './client'

export interface MetricResultBrief {
  result_id: number
  client_id: string
  metric_name: string
  period_start: string
  period_end: string
  standard_value: unknown
  site_adjusted_value: unknown
  delta: number | null
  delta_pct: number | null
  has_assumptions: boolean
  calculated_at: string
}

export interface AssumptionInLineage {
  name: string
  value: unknown
  description: string | null
  rationale: string | null
  approved_by: string | null
  approved_at: string | null
  assumption_id: number | null
}

export interface MetricLineage {
  result_id: number
  client_id: string
  metric_name: string
  metric_display_name: string
  formula: string
  description: string
  period_start: string
  period_end: string
  standard_value: unknown
  site_adjusted_value: unknown
  delta: number | null
  delta_pct: number | null
  inputs: Record<string, unknown>
  inputs_help: Record<string, string>
  assumptions_applied: AssumptionInLineage[]
  calculated_at: string
  calculated_by: string | null
}

export interface ListMetricResultsParams {
  client_id?: string
  metric_name?: string
  period_start?: string
  period_end?: string
  limit?: number
}

export const listMetricResults = (params?: ListMetricResultsParams) =>
  api.get<MetricResultBrief[]>('/api/metrics/results', { params })

export const getMetricLineage = (resultId: number) =>
  api.get<MetricLineage>(`/api/metrics/results/${resultId}`)
