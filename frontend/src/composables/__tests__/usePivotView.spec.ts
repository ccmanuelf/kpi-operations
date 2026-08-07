import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockApiGet } = vi.hoisted(() => ({
  mockApiGet: vi.fn(),
}))

vi.mock('@/services/api/client', () => ({ default: { get: mockApiGet } }))
vi.mock('@/composables/useCSVExport', () => ({
  useCSVExport: () => ({ downloading: { value: false }, downloadCSVByPath: vi.fn() }),
}))

import api from '@/services/api/client'
import { mergePivotRows, displayValue, usePivotView } from '@/composables/usePivotView'
import { PIVOT_VIEWS } from '@/composables/pivotPresets'

const q2 = PIVOT_VIEWS.find((v) => v.id === 'q2')!

describe('mergePivotRows', () => {
  it('joins on (bucket_start, group_key) and unions measures', () => {
    const a = [{ bucket_start: '2026-03-01', group_key: null, units: 300, run_hours: 20 }]
    const b = [{ bucket_start: '2026-03-01', group_key: null, actual: 40, billed: 30 }]
    const merged = mergePivotRows(a, b)
    expect(merged).toHaveLength(1)
    expect(merged[0]).toMatchObject({ units: 300, run_hours: 20, actual: 40, billed: 30 })
  })

  it('keeps unmatched rows from both sides', () => {
    const a = [{ bucket_start: '2026-03-01', group_key: null, units: 1 }]
    const b = [{ bucket_start: '2026-04-01', group_key: null, actual: 2 }]
    expect(mergePivotRows(a, b)).toHaveLength(2)
  })
})

describe('displayValue', () => {
  const pct = { key: 'otd_gross_pct', headerKey: 'x', kind: 'percent' as const }
  it('renders em dash for null AND for absent key (spec §5 asymmetry)', () => {
    expect(displayValue({ otd_gross_pct: null }, pct)).toBe('—')
    expect(displayValue({}, pct)).toBe('—')
  })
  it('formats percent with 2 decimals and number with 2 decimals', () => {
    expect(displayValue({ otd_gross_pct: 58.82 }, pct)).toBe('58.82%')
    expect(displayValue({ h: 8.9 }, { key: 'h', headerKey: 'x', kind: 'number' })).toBe('8.90')
    expect(displayValue({ n: 4 }, { key: 'n', headerKey: 'x', kind: 'count' })).toBe('4')
  })
})

describe('usePivotView', () => {
  beforeEach(() => mockApiGet.mockReset())

  it('fetches every dataset of the preset with current selection', async () => {
    mockApiGet.mockResolvedValue({ data: { rows: [], totals: {} } })
    const view = usePivotView(q2)
    view.bucket.value = 'month'
    await view.refresh()
    expect(mockApiGet).toHaveBeenCalledWith('/pivot/downtime', {
      params: expect.objectContaining({ bucket: 'month' }),
    })
  })

  it('surfaces API failure as error, not a throw', async () => {
    const err = new Error() as unknown as { response?: { data?: { detail?: unknown } } }
    err.response = { data: { detail: 'boom' } }
    mockApiGet.mockRejectedValueOnce(err)
    const view = usePivotView(q2)
    await view.refresh()
    expect(view.error.value).toContain('boom')
    expect(view.loading.value).toBe(false)
  })
})
