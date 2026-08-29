/**
 * A fetch that FAILS must not leave the grid silently empty.
 *
 * productionDataStore's fetch actions catch their own errors and resolve with
 * `{success: false}`, leaving the previous array in place — empty on a cold
 * mount. All ten call sites discarded that result, so a failed first load
 * rendered "no rows": indistinguishable from a dataset that is genuinely empty.
 *
 * Initial load and refresh are deliberately different. A failed refresh follows
 * a save that DID happen and leaves real rows on screen, so it gets a transient
 * snackbar, not a banner that would outlive its usefulness.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { withSetup } from '../../test/composable-test-utils'
import { useGridLoadState } from '../useGridLoadState'

const { store } = vi.hoisted(() => ({
  store: {
    productionEntries: [] as unknown[],
    workOrders: [] as unknown[],
    products: [] as unknown[],
    shifts: [] as unknown[],
    productionLines: [] as unknown[],
    fetchReferenceData: vi.fn(),
    fetchProductionEntries: vi.fn(),
    deleteProductionEntry: vi.fn(),
  },
}))

vi.mock('vue-i18n', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (k: string) => k, locale: { value: 'en' } }),
}))
vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ user: { client_id_assigned: 'C1' }, token: null }),
}))
vi.mock('@/stores/kpi', () => ({ useKPIStore: () => ({ selectedClient: null }) }))
vi.mock('@/stores/productionDataStore', () => ({ useProductionDataStore: () => store }))

import useProductionGridData from '../useProductionGridData'

const ok = () => Promise.resolve({ success: true })
const fail = (error?: string) => () => Promise.resolve({ success: false, error })

describe('useGridLoadState', () => {
  it('is clean when every step succeeds', async () => {
    const s = useGridLoadState()
    expect(await s.load(ok, ok)).toBe(true)
    expect(s.loadError.value).toBeNull()
  })

  it('records the backend reason from the first failing step', async () => {
    const s = useGridLoadState()
    expect(await s.load(ok, fail('Network error'))).toBe(false)
    expect(s.loadError.value).toBe('Network error')
  })

  it('stops at the first failure rather than running the rest', async () => {
    const s = useGridLoadState()
    const later = vi.fn(ok)
    await s.load(fail('boom'), later)
    expect(later).not.toHaveBeenCalled()
  })

  it('distinguishes "failed with no message" from "healthy"', async () => {
    // The critical distinction: '' is falsy but is NOT null, so the banner
    // still renders. Treating them alike would silently hide the failure.
    const s = useGridLoadState()
    await s.load(fail(undefined))
    expect(s.loadError.value).toBe('')
    expect(s.loadError.value).not.toBeNull()
  })

  it('catches a step that genuinely throws', async () => {
    const s = useGridLoadState()
    expect(await s.load(() => Promise.reject(new Error('exploded')))).toBe(false)
    expect(s.loadError.value).toBe('exploded')
  })

  it('clears a previous error when a retry succeeds', async () => {
    const s = useGridLoadState()
    const step = vi.fn().mockResolvedValueOnce({ success: false, error: 'x' }).mockResolvedValueOnce({ success: true })
    await s.load(step)
    expect(s.loadError.value).toBe('x')
    expect(await s.retry()).toBe(true)
    expect(s.loadError.value).toBeNull()
    expect(step).toHaveBeenCalledTimes(2)
  })
})

describe('the grid surfaces a failed initial load', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    store.fetchReferenceData.mockReset()
    store.fetchProductionEntries.mockReset()
  })

  it('sets loadError when the entries fetch fails on mount', async () => {
    store.fetchReferenceData.mockResolvedValue({ success: true })
    store.fetchProductionEntries.mockResolvedValue({ success: false, error: 'Failed to fetch entries' })

    const api = withSetup(() => useProductionGridData())
    await new Promise((r) => setTimeout(r, 0))

    expect(api.loadError.value).toBe('Failed to fetch entries')
  })

  it('stays clean when the load succeeds', async () => {
    store.fetchReferenceData.mockResolvedValue({ success: true })
    store.fetchProductionEntries.mockResolvedValue({ success: true })

    const api = withSetup(() => useProductionGridData())
    await new Promise((r) => setTimeout(r, 0))

    expect(api.loadError.value).toBeNull()
  })

  it('retry re-runs the same steps', async () => {
    store.fetchReferenceData.mockResolvedValue({ success: true })
    store.fetchProductionEntries.mockResolvedValue({ success: false, error: 'down' })

    const api = withSetup(() => useProductionGridData())
    await new Promise((r) => setTimeout(r, 0))
    expect(api.loadError.value).toBe('down')

    store.fetchProductionEntries.mockResolvedValue({ success: true })
    await api.retryLoad()

    expect(api.loadError.value).toBeNull()
  })
})
