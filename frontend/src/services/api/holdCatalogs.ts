/**
 * Per-client hold status/reason catalog API client.
 *
 * These catalogs gate hold creation: `routes/holds.py` rejects any status or
 * reason that is not ACTIVE in the calling client's catalog. A client whose
 * catalog was never seeded therefore cannot record a hold at all, which is
 * why `seedDefaults` is part of this surface and not just a fixture concern.
 *
 * Reads are open to any authenticated user; every write requires the
 * supervisory tier (admin/poweruser/leader/supervisor) — see
 * `backend/routes/hold_catalogs.py`.
 */

import api from './client'

export interface HoldStatusCatalogEntry {
  catalog_id: number
  client_id: string
  status_code: string
  display_name: string
  is_default: boolean
  is_active: boolean
  sort_order: number
  created_at: string
}

export interface HoldReasonCatalogEntry {
  catalog_id: number
  client_id: string
  reason_code: string
  display_name: string
  is_default: boolean
  is_active: boolean
  sort_order: number
  created_at: string
}

/** Fields the API accepts on update. `*_code` is immutable once created. */
export interface CatalogUpdate {
  display_name?: string
  is_active?: boolean
  sort_order?: number
}

export interface SeedDefaultsResult {
  statuses_created: number
  reasons_created: number
  skipped: number
}

// ------------------------------------------------------------- statuses

export const listHoldStatuses = (clientId: string | number) =>
  api.get<HoldStatusCatalogEntry[]>('/hold-catalogs/statuses', {
    params: { client_id: clientId },
  })

export const createHoldStatus = (data: {
  client_id: string
  status_code: string
  display_name: string
  sort_order?: number
}) => api.post<HoldStatusCatalogEntry>('/hold-catalogs/statuses', data)

export const updateHoldStatus = (catalogId: number, data: CatalogUpdate) =>
  api.put<HoldStatusCatalogEntry>(`/hold-catalogs/statuses/${catalogId}`, data)

export const deleteHoldStatus = (catalogId: number) =>
  api.delete(`/hold-catalogs/statuses/${catalogId}`)

// -------------------------------------------------------------- reasons

export const listHoldReasons = (clientId: string | number) =>
  api.get<HoldReasonCatalogEntry[]>('/hold-catalogs/reasons', {
    params: { client_id: clientId },
  })

export const createHoldReason = (data: {
  client_id: string
  reason_code: string
  display_name: string
  sort_order?: number
}) => api.post<HoldReasonCatalogEntry>('/hold-catalogs/reasons', data)

export const updateHoldReason = (catalogId: number, data: CatalogUpdate) =>
  api.put<HoldReasonCatalogEntry>(`/hold-catalogs/reasons/${catalogId}`, data)

export const deleteHoldReason = (catalogId: number) =>
  api.delete(`/hold-catalogs/reasons/${catalogId}`)

// -------------------------------------------------------- seed defaults

/**
 * Idempotently install the built-in status/reason sets for a client.
 *
 * This is the only way to bootstrap a tenant whose catalog is empty, and
 * without it the Hold/Resume entry screen is silently dead for that tenant.
 */
export const seedHoldCatalogDefaults = (clientId: string | number) =>
  api.post<SeedDefaultsResult>('/hold-catalogs/seed-defaults', null, {
    params: { client_id: clientId },
  })
