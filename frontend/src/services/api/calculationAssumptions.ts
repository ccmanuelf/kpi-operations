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

// Paths are relative to the `api` client's baseURL (/api/v1, rewritten to
// /api server-side) — a literal leading `/api/` here double-prefixes the
// request (e.g. /api/v1/api/assumptions/variance), which 404s.
export const getCatalog = () => api.get<CatalogEntry[]>('/assumptions/catalog')

export const getVarianceReport = (staleAfterDays = 365) =>
  api.get<VarianceRow[]>('/assumptions/variance', {
    params: { stale_after_days: staleAfterDays },
  })

export const listAssumptions = (params?: {
  client_id?: string
  assumption_name?: string
  status?: AssumptionStatus
  include_inactive?: boolean
}) => api.get<AssumptionResponse[]>('/assumptions', { params })

// ------------------------------------------------- the write lifecycle
//
// None of the below had a client function, so the entire propose -> approve
// -> retire workflow -- and the append-only change log behind it -- was
// unreachable from the product. The site-adjusted half of the dual view is
// driven by approved assumptions, so the only way to get one was direct DB
// access.
//
// AUTH IS NARROWER THAN THE ROUTE SUGGESTS. Each write passes a FastAPI
// dependency AND a second, tighter check inside AssumptionService, and only
// the second one is the real answer:
//
//   propose   route: supervisory   service: admin | poweruser
//   edit      route: supervisory   service: the original proposer, or admin
//   approve   route: planner       service: ADMIN ONLY
//   retire    route: planner       service: ADMIN ONLY
//
// Gating a button on the route's tier would therefore offer approve to a
// poweruser and 403 them. Gate on admin.

export interface AssumptionChangeRow {
  change_id: number
  assumption_id: number
  changed_by: string
  changed_at: string
  previous_value: unknown | null
  new_value: unknown | null
  previous_status: string | null
  new_status: string | null
  change_reason: string | null
  trigger_source: string | null
}

export interface ProposalPayload {
  client_id: string
  assumption_name: string
  value: unknown
  rationale?: string | null
  effective_date?: string | null
  expiration_date?: string | null
}

export interface ProposalPatch {
  value?: unknown
  rationale?: string | null
  effective_date?: string | null
  expiration_date?: string | null
  change_reason?: string | null
}

export const getAssumption = (assumptionId: number) =>
  api.get<AssumptionResponse>(`/assumptions/${assumptionId}`)

/** The append-only governance trail: who changed what, when, and why. */
export const getAssumptionHistory = (assumptionId: number) =>
  api.get<AssumptionChangeRow[]>(`/assumptions/${assumptionId}/history`)

export const getEffectiveSet = (clientId: string, asOf?: string) =>
  api.get('/assumptions/effective', {
    params: asOf ? { client_id: clientId, as_of: asOf } : { client_id: clientId },
  })

export const proposeAssumption = (data: ProposalPayload) =>
  api.post<AssumptionResponse>('/assumptions', data)

/** Only while PROPOSED -- the API answers 409 once a record is active. */
export const updateProposal = (assumptionId: number, data: ProposalPatch) =>
  api.patch<AssumptionResponse>(`/assumptions/${assumptionId}`, data)

export const approveAssumption = (assumptionId: number, changeReason?: string | null) =>
  api.post<AssumptionResponse>(`/assumptions/${assumptionId}/approve`, {
    change_reason: changeReason ?? null,
  })

export const retireAssumption = (assumptionId: number, changeReason?: string | null) =>
  api.post<AssumptionResponse>(`/assumptions/${assumptionId}/retire`, {
    change_reason: changeReason ?? null,
  })
