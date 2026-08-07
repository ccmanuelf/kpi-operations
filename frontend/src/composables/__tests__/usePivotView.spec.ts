import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockApiGet } = vi.hoisted(() => ({
  mockApiGet: vi.fn(),
}))

vi.mock('@/services/api/client', () => ({ default: { get: mockApiGet } }))
vi.mock('@/composables/useCSVExport', () => ({
  useCSVExport: () => ({ downloading: { value: false }, downloadCSVByPath: vi.fn() }),
}))

import { mergePivotRows, displayValue, usePivotView } from '@/composables/usePivotView'
import { PIVOT_VIEWS } from '@/composables/pivotPresets'

const q2 = PIVOT_VIEWS.find((v) => v.id === 'q2')!
const q3 = PIVOT_VIEWS.find((v) => v.id === 'q3')!

// localISO itself now lives in, and is tested by,
// frontend/src/utils/__tests__/localeDate.spec.ts -- usePivotView just
// imports it from there (review round MINOR 8).

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

  it('a grouping unsupported by one dataset SKIPS that dataset entirely (Q3 + delay_reason fetches ONLY delivery)', async () => {
    // q3 = [quality, delivery]. delay_reason is in delivery's allow-list but
    // not quality's -- every one of quality's columns is hidden under
    // delay_reason anyway (pivotPresets.ts hideForGroupings), so a
    // time-only fallback row would just be an all-blank noise row. quality
    // must not be fetched at all; delivery gets group_by sent normally.
    mockApiGet.mockImplementation((path: string) => {
      if (path === '/pivot/delivery') {
        return Promise.resolve({
          data: {
            rows: [{ bucket_start: '2026-03-01', group_key: 'material_supplier_delay', delivered: 5 }],
            totals: {},
          },
        })
      }
      // Any other path (e.g. '/pivot/quality') would mean the skip logic
      // failed to skip it -- caught below via toHaveBeenCalledTimes(1) /
      // toHaveBeenCalledWith, not by rejecting here (a harness quirk fires
      // one further call to this same mock during test teardown, after
      // refresh() has already settled and been asserted on -- rejecting
      // unconditionally turns that into an unrelated unhandled-rejection
      // failure instead of a clean, accurate assertion mismatch).
      return Promise.resolve({ data: { rows: [], totals: {} } })
    })
    const view = usePivotView(q3)
    view.groupBy.value = 'delay_reason'
    await view.refresh()

    expect(mockApiGet).toHaveBeenCalledTimes(1)
    expect(mockApiGet).toHaveBeenCalledWith(
      '/pivot/delivery',
      expect.objectContaining({ params: expect.objectContaining({ group_by: 'delay_reason' }) }),
    )

    // No null-group quality row -- only delivery's grouped row.
    expect(view.rows.value).toHaveLength(1)
    expect(view.rows.value.find((r) => r.group_key === null)).toBeUndefined()
    expect(view.rows.value[0]).toMatchObject({ group_key: 'material_supplier_delay', delivered: 5 })
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
