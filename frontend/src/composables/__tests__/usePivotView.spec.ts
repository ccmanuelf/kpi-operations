import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockApiGet } = vi.hoisted(() => ({
  mockApiGet: vi.fn(),
}))

vi.mock('@/services/api/client', () => ({ default: { get: mockApiGet } }))
vi.mock('@/composables/useCSVExport', () => ({
  useCSVExport: () => ({ downloading: { value: false }, downloadCSVByPath: vi.fn() }),
}))

import { localISO, mergePivotRows, displayValue, usePivotView } from '@/composables/usePivotView'
import { PIVOT_VIEWS } from '@/composables/pivotPresets'

const q2 = PIVOT_VIEWS.find((v) => v.id === 'q2')!
const q3 = PIVOT_VIEWS.find((v) => v.id === 'q3')!

describe('localISO', () => {
  // Fixed Date built from LOCAL components (the `new Date(y, m, d, h, ...)`
  // constructor, not a UTC ISO string) -- localISO must read those same
  // local components back, so this is deterministic regardless of which
  // timezone the test runner itself is in. toISOString() would instead
  // convert to UTC first, which for a UTC-behind runner can roll an evening
  // local timestamp into the NEXT UTC calendar day.
  it('formats an evening local timestamp as the local calendar date, not a UTC-shifted one', () => {
    const evening = new Date(2026, 7, 6, 22, 30, 0) // 2026-08-06 22:30 local
    expect(localISO(evening)).toBe('2026-08-06')
  })

  it('zero-pads single-digit month and day', () => {
    const early = new Date(2026, 0, 5, 9, 0, 0) // 2026-01-05
    expect(localISO(early)).toBe('2026-01-05')
  })
})

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

  it('Q1 pin: when both datasets carry earned_hours for the same (bucket_start, group_key), the SECOND dataset wins (see the invariant comment on mergePivotRows)', () => {
    // Mirrors Q1's real shape: production is `primary`, labor is
    // `secondary` -- both emit earned_hours/excluded_entries, safe today
    // only because both are derived from the same mirrored formula.
    const production = [
      { bucket_start: '2026-03-01', group_key: null, earned_hours: 111, excluded_entries: 2 },
    ]
    const labor = [
      { bucket_start: '2026-03-01', group_key: null, earned_hours: 222, excluded_entries: 5 },
    ]
    const merged = mergePivotRows(production, labor)
    expect(merged).toHaveLength(1)
    expect(merged[0].earned_hours).toBe(222)
    expect(merged[0].excluded_entries).toBe(5)
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

  it('a grouping unsupported by one dataset falls back to time-only for that dataset alone -- rows interleave, not merge', async () => {
    // q3 = [quality, delivery]. delay_reason is in delivery's allow-list but
    // not quality's, so quality must be fetched without group_by (falls
    // back to time-only, group_key=null) while delivery gets group_by sent.
    mockApiGet.mockImplementation((path: string) => {
      if (path === '/pivot/quality') {
        return Promise.resolve({
          data: { rows: [{ bucket_start: '2026-03-01', group_key: null, inspected: 10 }], totals: {} },
        })
      }
      return Promise.resolve({
        data: {
          rows: [{ bucket_start: '2026-03-01', group_key: 'material_supplier_delay', delivered: 5 }],
          totals: {},
        },
      })
    })
    const view = usePivotView(q3)
    view.groupBy.value = 'delay_reason'
    await view.refresh()

    expect(mockApiGet).toHaveBeenCalledWith(
      '/pivot/quality',
      expect.objectContaining({ params: expect.not.objectContaining({ group_by: expect.anything() }) }),
    )
    expect(mockApiGet).toHaveBeenCalledWith(
      '/pivot/delivery',
      expect.objectContaining({ params: expect.objectContaining({ group_by: 'delay_reason' }) }),
    )

    // Both rows survive as distinct entries -- keyed on (bucket_start,
    // group_key), so the null-group quality row and the grouped delivery
    // row for the same bucket_start do NOT collapse into one.
    expect(view.rows.value).toHaveLength(2)
    const qualityRow = view.rows.value.find((r) => r.group_key === null)
    const deliveryRow = view.rows.value.find((r) => r.group_key === 'material_supplier_delay')
    expect(qualityRow).toMatchObject({ inspected: 10 })
    expect(deliveryRow).toMatchObject({ delivered: 5 })
  })

  it('a stale response cannot overwrite a newer selection (request-token guard)', async () => {
    // Two overlapping refresh() calls where the FIRST one resolves LAST --
    // e.g. the user changes the bucket twice in quick succession and the
    // earlier network request happens to complete after the later one.
    // Final state must reflect the SECOND call's data, never the first's.
    let resolveFirst!: (_v: unknown) => void
    let resolveSecond!: (_v: unknown) => void
    const firstResponse = new Promise((resolve) => { resolveFirst = resolve })
    const secondResponse = new Promise((resolve) => { resolveSecond = resolve })

    mockApiGet.mockImplementationOnce(() => firstResponse)
    const view = usePivotView(q2)
    const refresh1 = view.refresh()

    mockApiGet.mockImplementationOnce(() => secondResponse)
    const refresh2 = view.refresh()

    // Second call resolves FIRST.
    resolveSecond({
      data: { rows: [{ bucket_start: '2026-02-01', group_key: null, events: 2 }], totals: { events: 2 } },
    })
    await refresh2
    expect(view.rows.value).toEqual([{ bucket_start: '2026-02-01', group_key: null, events: 2 }])

    // First call resolves LAST -- must be discarded, not overwrite state.
    resolveFirst({
      data: { rows: [{ bucket_start: '2026-01-01', group_key: null, events: 1 }], totals: { events: 1 } },
    })
    await refresh1

    expect(view.rows.value).toEqual([{ bucket_start: '2026-02-01', group_key: null, events: 2 }])
    expect(view.totals.value).toEqual({ events: 2 })
    expect(view.loading.value).toBe(false)
  })
})
