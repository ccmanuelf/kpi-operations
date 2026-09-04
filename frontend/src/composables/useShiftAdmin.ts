/**
 * Data layer for the shift master-data admin screen.
 *
 * Distinct from `useShiftForms.ts`, which only reads shifts to populate a
 * production-entry dropdown. This one owns the SHIFT table itself.
 *
 * Every write invalidates the cached shift reference data. `reference.ts`
 * serves `/shifts/` from a 30-minute TTL cache that feeds the shift dropdown
 * on every data-entry grid, so without this a shift added here would not
 * appear where operators need it until the cache aged out.
 */
import { ref, computed } from 'vue'
import api from '@/services/api'
import { invalidateReferenceType } from '@/services/api/reference'
import { listShifts, deleteShift, type Shift } from '@/services/api/shifts'

export interface ClientOption {
  client_id: string | number
  client_name: string
  [key: string]: unknown
}

/** A shift as the grid holds it — server fields plus local edit flags. */
export interface ShiftRow extends Partial<Shift> {
  _isNew?: boolean
  _isSaving?: boolean
}

export function useShiftAdmin() {
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const shifts = ref<ShiftRow[]>([])
  const loading = ref(false)
  const loaded = ref(false)

  const selectedClientInfo = computed<ClientOption | null>(
    () => clients.value.find((c) => c.client_id === selectedClient.value) ?? null,
  )

  /**
   * True only after a SUCCESSFUL read that came back empty. This is the state
   * the onboarding checklist's first step ("configure shifts") reports on, so
   * it must not be reached by way of a failed request.
   */
  const noShiftsConfigured = computed(() => loaded.value && shifts.value.length === 0)

  const loadClients = async (): Promise<void> => {
    const res = await api.getClients()
    clients.value = (res.data as ClientOption[]) || []
  }

  const loadShifts = async (): Promise<void> => {
    loading.value = true
    try {
      const { data } = await listShifts(selectedClient.value)
      // Preserve rows the user is still typing into — every write reloads the
      // list, and replacing it wholesale would discard other unsaved drafts.
      const drafts = shifts.value.filter((r) => r._isNew)
      shifts.value = [...drafts, ...((data as ShiftRow[]) ?? [])]
      loaded.value = true
    } catch (error) {
      shifts.value = []
      loaded.value = false
      throw error
    } finally {
      loading.value = false
    }
  }

  /** Soft delete server-side; the row leaves the list because reads are active-only. */
  const removeShift = async (shiftId: number): Promise<void> => {
    await deleteShift(shiftId)
    invalidateReferenceType('shifts')
    await loadShifts()
  }

  return {
    clients,
    selectedClient,
    shifts,
    loading,
    loaded,
    selectedClientInfo,
    noShiftsConfigured,
    loadClients,
    loadShifts,
    removeShift,
  }
}
