/**
 * A delete that FAILS must not be reported as a success.
 *
 * productionDataStore's delete actions catch their own errors and return
 * `{success: false}` rather than throwing. All three grid composables awaited
 * them inside a try/catch, so the catch never ran and execution simply
 * continued: the row was removed from the grid, unsaved changes were cleared,
 * and a green "deleted successfully" snackbar was shown — for a record that is
 * still on the server and reappears on the next refresh.
 *
 * These tests fail against the pre-fix code for all three composables.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { computed, ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { withSetup } from '../../test/composable-test-utils'

const { store } = vi.hoisted(() => ({
  store: {
    productionEntries: [] as unknown[],
    downtimeEntries: [] as unknown[],
    holdEntries: [] as unknown[],
    workOrders: [] as unknown[],
    products: [] as unknown[],
    shifts: [] as unknown[],
    productionLines: [] as unknown[],
    fetchReferenceData: vi.fn().mockResolvedValue(undefined),
    fetchProductionEntries: vi.fn().mockResolvedValue(undefined),
    fetchDowntimeEntries: vi.fn().mockResolvedValue(undefined),
    fetchHoldEntries: vi.fn().mockResolvedValue(undefined),
    deleteProductionEntry: vi.fn(),
    deleteDowntimeEntry: vi.fn(),
    deleteHoldEntry: vi.fn(),
  },
}))

// Partial mock: useHoldGridForms reaches services/api/structuredErrors, which
// imports @/i18n and needs the real createI18n. Replacing vue-i18n wholesale
// breaks the module graph, not just the translation.
vi.mock('vue-i18n', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (k: string) => k, locale: { value: 'en' } }),
}))
vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ user: { client_id_assigned: 'CLIENT1' }, token: null }),
}))
vi.mock('@/stores/kpi', () => ({ useKPIStore: () => ({ selectedClient: null }) }))
vi.mock('@/stores/productionDataStore', () => ({ useProductionDataStore: () => store }))

import useProductionGridData from '../useProductionGridData'
import useDowntimeGridData from '../useDowntimeGridData'
import { useHoldGridForms } from '../useHoldGridForms'

/** An AG Grid stub that records whether the row was removed from the grid. */
const gridStub = () => {
  const removed: unknown[] = []
  return {
    removed,
    // the composables read gridRef.value?.gridApi, not .api
    gridApi: {
      applyTransaction: (tx: { remove?: unknown[] }) => {
        if (tx.remove) removed.push(...tx.remove)
      },
      refreshCells: vi.fn(),
      getRowNode: vi.fn(),
    },
  }
}

const FAILURE = { success: false, error: 'Cannot delete: still referenced' }

describe('a failed delete is never reported as a success', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // These flows gate on window.confirm before touching the store.
    vi.stubGlobal('confirm', () => true)
    Object.values(store).forEach((v) => {
      if (typeof v === 'function' && 'mockClear' in v) (v as { mockClear: () => void }).mockClear()
    })
  })

  it('production: keeps the row, and the snackbar is an error', async () => {
    store.deleteProductionEntry.mockResolvedValue(FAILURE)
    const grid = gridStub()
    const api = withSetup(() => useProductionGridData())
    api.gridRef.value = grid as never

    await api.deleteEntry({ entry_id: 'PE-1' } as never)

    expect(grid.removed, 'the row must stay in the grid').toEqual([])
    expect(api.snackbar.value.color, 'the snackbar must be an error').toBe('error')
  })

  it('downtime: keeps the row, and the snackbar is an error', async () => {
    store.deleteDowntimeEntry.mockResolvedValue(FAILURE)
    const grid = gridStub()
    const api = withSetup(() => useDowntimeGridData())
    api.gridRef.value = grid as never

    await api.deleteEntry({ downtime_entry_id: 'DT-1' } as never)

    expect(grid.removed, 'the row must stay in the grid').toEqual([])
    expect(api.snackbar.value.color, 'the snackbar must be an error').toBe('error')
  })

  it('production: a SUCCESSFUL delete still removes the row and says so', async () => {
    store.deleteProductionEntry.mockResolvedValue({ success: true })
    const grid = gridStub()
    const api = withSetup(() => useProductionGridData())
    api.gridRef.value = grid as never

    await api.deleteEntry({ entry_id: 'PE-2' } as never)

    expect(grid.removed).toHaveLength(1)
    expect(api.snackbar.value.color).toBe('success')
  })

  it('holds: keeps the row, and the snackbar is an error', async () => {
    // This composable takes its store as an injected dependency rather than
    // reading the pinia store, so it is built directly.
    const grid = gridStub()
    const showSnackbar = vi.fn()
    const api = withSetup(() =>
      useHoldGridForms({
        gridRef: ref(grid) as never,
        unsavedChanges: ref(new Set<string | number>()),
        saving: ref(false),
        workOrders: computed(() => []),
        kpiStore: {
          deleteHoldEntry: vi.fn().mockResolvedValue(FAILURE),
          createHoldEntry: vi.fn(),
          updateHoldEntry: vi.fn(),
          fetchHoldEntries: vi.fn().mockResolvedValue(undefined),
        },
        applyFilters: vi.fn(),
        showSnackbar,
      }),
    )

    await api.deleteEntry({ id: 'H-1' } as never)

    expect(grid.removed, 'the row must stay in the grid').toEqual([])
    const [, color] = showSnackbar.mock.calls.at(-1) ?? []
    expect(color, 'the snackbar must be an error').toBe('error')
  })

  it('surfaces the reason the backend gave, not a generic message', async () => {
    store.deleteProductionEntry.mockResolvedValue(FAILURE)
    const grid = gridStub()
    const api = withSetup(() => useProductionGridData())
    api.gridRef.value = grid as never

    await api.deleteEntry({ entry_id: 'PE-3' } as never)

    expect(api.snackbar.value.message).toContain('Cannot delete: still referenced')
  })
})
