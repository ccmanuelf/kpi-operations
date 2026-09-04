/**
 * Data layer for the per-client hold status/reason catalog admin screen.
 *
 * Kept free of `useI18n` and of component internals so it can be unit tested
 * directly — the view and the grid layer own all user-facing copy.
 *
 * The catalogs are load-bearing, not cosmetic: `routes/holds.py` rejects any
 * status or reason absent from (or deactivated in) the calling client's
 * catalog, so a tenant whose catalog was never seeded cannot record a hold at
 * all. `catalogIsEmpty` exists to drive the empty state that offers
 * `seedDefaults` as the only way out of that dead end.
 */
import { ref, computed, type Ref } from 'vue'
import api from '@/services/api'
import {
  listHoldStatuses,
  listHoldReasons,
  deleteHoldStatus,
  deleteHoldReason,
  seedHoldCatalogDefaults,
  type HoldStatusCatalogEntry,
  type HoldReasonCatalogEntry,
  type SeedDefaultsResult,
} from '@/services/api/holdCatalogs'

export interface ClientOption {
  client_id: string | number
  client_name: string
  [key: string]: unknown
}

/** A catalog row as the grid holds it — server fields plus local edit flags. */
export interface HoldCatalogRow {
  catalog_id?: number
  client_id?: string
  /** Present on status rows only. */
  status_code?: string
  /** Present on reason rows only. */
  reason_code?: string
  display_name?: string
  is_default?: boolean
  is_active?: boolean
  sort_order?: number
  created_at?: string
  _isNew?: boolean
  _isSaving?: boolean
}

export type CatalogKind = 'status' | 'reason'

export function useHoldCatalogAdmin() {
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const statuses = ref<HoldCatalogRow[]>([])
  const reasons = ref<HoldCatalogRow[]>([])
  const loading = ref(false)
  /** False until the first successful load, so the empty state cannot flash. */
  const loaded = ref(false)

  const selectedClientInfo = computed<ClientOption | null>(
    () => clients.value.find((c) => c.client_id === selectedClient.value) ?? null,
  )

  /**
   * True only when a load SUCCEEDED and returned nothing. A failed read is not
   * evidence of an empty catalog, and offering "seed defaults" there would be
   * a lie about why the screen is blank.
   */
  const catalogIsEmpty = computed(
    () => loaded.value && statuses.value.length === 0 && reasons.value.length === 0,
  )

  /**
   * Drafts for the CURRENTLY selected client only. createEntry stamps a row
   * with whatever client is selected at save time, so a draft carried across a
   * client switch would be filed under the wrong tenant.
   */
  const pendingDrafts = (list: Ref<HoldCatalogRow[]>): HoldCatalogRow[] => {
    const current = selectedClient.value === null ? null : String(selectedClient.value)
    return list.value.filter((r) => r._isNew && r.client_id === current)
  }

  const loadClients = async (): Promise<void> => {
    const res = await api.getClients()
    clients.value = (res.data as ClientOption[]) || []
  }

  const loadCatalogs = async (): Promise<void> => {
    if (!selectedClient.value) {
      statuses.value = []
      reasons.value = []
      loaded.value = false
      return
    }
    loading.value = true
    try {
      const [statusRes, reasonRes] = await Promise.all([
        listHoldStatuses(selectedClient.value),
        listHoldReasons(selectedClient.value),
      ])
      // Preserve rows the user is still typing into. Every write reloads the
      // list, so replacing it wholesale would silently discard any OTHER
      // unsaved draft rows they had added.
      statuses.value = [...pendingDrafts(statuses), ...((statusRes.data as HoldCatalogRow[]) ?? [])]
      reasons.value = [...pendingDrafts(reasons), ...((reasonRes.data as HoldCatalogRow[]) ?? [])]
      loaded.value = true
    } catch (error) {
      statuses.value = []
      reasons.value = []
      loaded.value = false
      throw error
    } finally {
      loading.value = false
    }
  }

  const seedDefaults = async (): Promise<SeedDefaultsResult | null> => {
    if (!selectedClient.value) return null
    const { data } = await seedHoldCatalogDefaults(selectedClient.value)
    await loadCatalogs()
    return data
  }

  const deleteEntry = async (kind: CatalogKind, catalogId: number): Promise<void> => {
    if (kind === 'status') {
      await deleteHoldStatus(catalogId)
    } else {
      await deleteHoldReason(catalogId)
    }
    await loadCatalogs()
  }

  return {
    clients,
    selectedClient,
    statuses,
    reasons,
    loading,
    loaded,
    selectedClientInfo,
    catalogIsEmpty,
    loadClients,
    loadCatalogs,
    seedDefaults,
    deleteEntry,
  }
}

export type { HoldStatusCatalogEntry, HoldReasonCatalogEntry }
