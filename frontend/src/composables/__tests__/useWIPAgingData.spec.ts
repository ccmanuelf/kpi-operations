/**
 * Unit tests for useWIPAgingData composable.
 *
 * Covers the WIP Aging KPI detail page's logic surface — the view itself
 * (`views/kpi/WIPAging.vue`) is a thin presentation layer; testing this
 * composable lifts both files from 0% line coverage. Asserts:
 *   - reactive state defaults
 *   - INVERTED threshold-based color tokens (statusColor, getAgeColor) where
 *     lower aging (in days) is healthier
 *   - formatters (formatValue, formatDate)
 *   - i18n-resolved table headers (agingHeaders, historyHeaders)
 *   - async actions (loadHoldHistory, refreshData success + error,
 *     onClientChange/onDateChange side effects, initialize)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

const { mockApi, kpiStoreState } = vi.hoisted(() => ({
  mockApi: {
    getClients: vi.fn(),
    getHoldEntries: vi.fn(),
  },
  kpiStoreState: {
    wipAging: null as Record<string, unknown> | null,
    fetchWIPAging: vi.fn(),
    setClient: vi.fn(),
    setDateRange: vi.fn(),
  },
}))

vi.mock('@/services/api', () => ({ default: mockApi }))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (k: string) => k }),
}))
vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => kpiStoreState,
}))

import useWIPAgingData from '../useWIPAgingData'

describe('useWIPAgingData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockApi.getClients.mockReset().mockResolvedValue({ data: [] })
    mockApi.getHoldEntries.mockReset().mockResolvedValue({ data: [] })
    kpiStoreState.wipAging = null
    kpiStoreState.fetchWIPAging.mockReset().mockResolvedValue(undefined)
    kpiStoreState.setClient.mockReset()
    kpiStoreState.setDateRange.mockReset()
  })

  describe('initial state', () => {
    it('has loading=false and empty collections', () => {
      const c = useWIPAgingData()
      expect(c.loading.value).toBe(false)
      expect(c.clients.value).toEqual([])
      expect(c.holdHistory.value).toEqual([])
      expect(c.selectedClient.value).toBeNull()
      expect(c.tableSearch.value).toBe('')
    })

    it('initializes startDate to 30 days ago and endDate to today', () => {
      const c = useWIPAgingData()
      expect(c.startDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(c.endDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      const start = new Date(c.startDate.value)
      const end = new Date(c.endDate.value)
      const days = Math.round((end.getTime() - start.getTime()) / 86_400_000)
      expect(days).toBe(30)
    })
  })

  describe('threshold colors (INVERTED — lower days = better)', () => {
    it.each([
      [0, 'success'],
      [3, 'success'],
      [7, 'success'],
      [10, 'amber-darken-3'],
      [14, 'amber-darken-3'],
      [20, 'error'],
      [60, 'error'],
    ])('getAgeColor(%d) returns %s', (val, expected) => {
      const c = useWIPAgingData()
      expect(c.getAgeColor(val)).toBe(expected)
    })
  })

  describe('statusColor (computed) reflects average_days (INVERTED)', () => {
    it.each([
      [3, 'success'],
      [7, 'success'],
      [10, 'amber-darken-3'],
      [14, 'amber-darken-3'],
      [20, 'error'],
    ])('average_days=%d → %s', (avg, expected) => {
      kpiStoreState.wipAging = { average_days: avg }
      const c = useWIPAgingData()
      expect(c.statusColor.value).toBe(expected)
    })

    it('null wipAging → success (treats as 0, inverted threshold)', () => {
      // Inverted threshold: 0 days = healthiest case.
      kpiStoreState.wipAging = null
      const c = useWIPAgingData()
      expect(c.statusColor.value).toBe('success')
    })
  })

  describe('formatters', () => {
    it('formatValue returns 1-decimal string for finite numbers', () => {
      const c = useWIPAgingData()
      expect(c.formatValue(7)).toBe('7.0')
      expect(c.formatValue(7.456)).toBe('7.5')
    })

    it('formatValue returns the i18n n/a key when value is null/undefined', () => {
      const c = useWIPAgingData()
      expect(c.formatValue(null)).toBe('common.na')
      expect(c.formatValue(undefined)).toBe('common.na')
    })

    it('formatDate formats valid date strings (MMM dd, yyyy)', () => {
      const c = useWIPAgingData()
      const out = c.formatDate('2026-05-07T12:00:00')
      expect(out).toBe('May 07, 2026')
    })

    it('formatDate returns the input when parsing fails', () => {
      const c = useWIPAgingData()
      expect(c.formatDate('not-a-date')).toBe('not-a-date')
    })
  })

  describe('table headers (i18n-resolved)', () => {
    it('agingHeaders has work_order, product, age, quantity', () => {
      const c = useWIPAgingData()
      expect(c.agingHeaders.value.map((h) => h.key)).toEqual([
        'work_order',
        'product',
        'age',
        'quantity',
      ])
    })

    it('historyHeaders has hold_date, work_order_id, category, reason, status', () => {
      const c = useWIPAgingData()
      expect(c.historyHeaders.value.map((h) => h.key)).toEqual([
        'hold_date',
        'work_order_id',
        'hold_reason_category',
        'hold_reason_description',
        'hold_status',
      ])
    })
  })

  describe('refreshData', () => {
    it('calls store.fetchWIPAging + api.getHoldEntries and toggles loading', async () => {
      const c = useWIPAgingData()
      const promise = c.refreshData()
      expect(c.loading.value).toBe(true)
      await promise
      expect(kpiStoreState.fetchWIPAging).toHaveBeenCalled()
      expect(mockApi.getHoldEntries).toHaveBeenCalled()
      expect(c.loading.value).toBe(false)
    })

    it('passes start_date/end_date and threads selectedClient when set', async () => {
      const c = useWIPAgingData()
      c.selectedClient.value = 'ACME-MFG'
      c.startDate.value = '2026-01-01'
      c.endDate.value = '2026-02-01'
      await c.refreshData()
      expect(mockApi.getHoldEntries).toHaveBeenCalledWith({
        start_date: '2026-01-01',
        end_date: '2026-02-01',
        client_id: 'ACME-MFG',
      })
    })

    it('omits client_id when no client selected', async () => {
      const c = useWIPAgingData()
      await c.refreshData()
      const call = mockApi.getHoldEntries.mock.calls[0][0]
      expect(call).not.toHaveProperty('client_id')
    })

    it('populates holdHistory from response', async () => {
      mockApi.getHoldEntries.mockResolvedValueOnce({
        data: [{ hold_date: '2026-05-07', hold_status: 'ON_HOLD' }],
      })
      const c = useWIPAgingData()
      await c.refreshData()
      expect(c.holdHistory.value).toEqual([
        { hold_date: '2026-05-07', hold_status: 'ON_HOLD' },
      ])
    })

    it('clears holdHistory when getHoldEntries throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getHoldEntries.mockRejectedValueOnce(new Error('boom'))
      const c = useWIPAgingData()
      await c.refreshData()
      expect(c.holdHistory.value).toEqual([])
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })

    it('clears loading even when fetchWIPAging throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      kpiStoreState.fetchWIPAging.mockRejectedValueOnce(new Error('boom'))
      const c = useWIPAgingData()
      await c.refreshData()
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })

  describe('onClientChange / onDateChange', () => {
    it('onClientChange updates store and refreshes data', async () => {
      const c = useWIPAgingData()
      c.selectedClient.value = 'ACME-MFG'
      c.onClientChange()
      await flushPromises()
      expect(kpiStoreState.setClient).toHaveBeenCalledWith('ACME-MFG')
      expect(kpiStoreState.fetchWIPAging).toHaveBeenCalled()
    })

    it('onDateChange updates store with current dates and refreshes data', async () => {
      const c = useWIPAgingData()
      c.startDate.value = '2026-01-01'
      c.endDate.value = '2026-02-01'
      c.onDateChange()
      await flushPromises()
      expect(kpiStoreState.setDateRange).toHaveBeenCalledWith('2026-01-01', '2026-02-01')
      expect(kpiStoreState.fetchWIPAging).toHaveBeenCalled()
    })
  })

  describe('initialize', () => {
    it('loads clients, sets date range on store, and refreshes', async () => {
      mockApi.getClients.mockResolvedValueOnce({ data: [{ client_id: 'C1' }] })
      const c = useWIPAgingData()
      await c.initialize()
      expect(c.clients.value).toEqual([{ client_id: 'C1' }])
      expect(kpiStoreState.setDateRange).toHaveBeenCalled()
      expect(kpiStoreState.fetchWIPAging).toHaveBeenCalled()
      expect(c.loading.value).toBe(false)
    })

    it('still clears loading on getClients failure', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getClients.mockRejectedValueOnce(new Error('500'))
      const c = useWIPAgingData()
      await c.initialize()
      expect(c.clients.value).toEqual([])
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })
})
