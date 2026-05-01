/**
 * Calculation Assumption Registry API client.
 *
 * Phase 2 endpoints (catalog, list/get/effective/history/dependencies, write
 * lifecycle) plus Phase 5 variance reporting.
 */

import api from './client'

// ----------------------------------------------------------- shared shapes

export type AssumptionStatus = 'proposed' | 'active' | 'retired'

export interface AssumptionResponse {
  assumption_id: number
  client_id: string
  assumption_name: string
  value: unknown
  rationale: string | null
  effective_date: string | null
  expiration_date: string | null
  status: AssumptionStatus
  proposed_by: string
  proposed_at: string
  approved_by: string | null
  approved_at: string | null
  retired_by: string | null
  retired_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface CatalogEntry {
  name: string
  description: string
  allowed_values: unknown[] | null
}

// ------------------------------------------------------------- Phase 5

export interface VarianceRow {
  assumption_id: number
  client_id: string
  assumption_name: string
  description: string | null
  value: unknown
  default_value: unknown
  deviates_from_default: boolean
  deviation_magnitude: number
  approved_by: string | null
  approved_at: string | null
  days_since_review: number | null
  is_stale: boolean
  rationale: string | null
}

export const getCatalog = () => api.get<CatalogEntry[]>('/api/assumptions/catalog')

export const getVarianceReport = (staleAfterDays = 365) =>
  api.get<VarianceRow[]>('/api/assumptions/variance', {
    params: { stale_after_days: staleAfterDays },
  })

export const listAssumptions = (params?: {
  client_id?: string
  assumption_name?: string
  status?: AssumptionStatus
  include_inactive?: boolean
}) => api.get<AssumptionResponse[]>('/api/assumptions', { params })
