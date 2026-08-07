import { describe, it, expect, vi, beforeEach } from 'vitest'

const { getWIPAgingMock } = vi.hoisted(() => ({ getWIPAgingMock: vi.fn() }))
vi.mock('@/services/api/kpi', () => ({ getWIPAging: getWIPAgingMock }))

import { useWipTriadData } from '@/composables/useWipTriadData'

describe('useWipTriadData', () => {
  beforeEach(() => getWIPAgingMock.mockReset())

  it('fetches getWIPAging directly (no kpi store involved), with NO date window, and surfaces the three distinct fields using the real as-of-now snapshot response shape', async () => {
    // Real shape getWIPAging() returns with no params (frontend/src/services/api/kpi.ts):
    // an as-of-now snapshot -- these headline cards are not a windowed
    // series (live-VM finding: windowing this endpoint excludes holds
    // whose hold_date falls outside the range, i.e. the oldest/worst
    // holds are exactly what a trailing window drops).
    getWIPAgingMock.mockResolvedValue({
      data: {
        average_days: 64.5,
        total_held: 4,
        total_units: 4,
        aging_15_30: 0,
        aging_over_30: 4,
        age_15_plus: 4,
        critical_count: 4,
        max_days: 70,
        total_hold_events: 4,
        top_aging: [{ age: 70 }],
      },
    })

    const { wipData, load } = useWipTriadData()
    await load()

    expect(wipData.value).toMatchObject({ average_days: 64.5, max_days: 70, age_15_plus: 4 })
    expect(getWIPAgingMock).toHaveBeenCalledTimes(1)
    // No arguments at all -- not just "no client_id" but no date window
    // either, so the backend returns its unfiltered as-of-now snapshot.
    expect(getWIPAgingMock).toHaveBeenCalledWith()
  })

  it('surfaces a null average_days (honest no-data) rather than a fabricated 0', async () => {
    getWIPAgingMock.mockResolvedValue({
      data: { average_days: null, total_held: 0, max_days: 0, age_15_plus: 0, top_aging: [] },
    })
    const { wipData, load } = useWipTriadData()
    await load()
    expect(wipData.value?.average_days).toBeNull()
  })

  it('sets loading true during the fetch and false once settled', async () => {
    let resolveLoad!: (_v: unknown) => void
    getWIPAgingMock.mockReturnValue(new Promise((resolve) => { resolveLoad = resolve }))
    const { loading, load } = useWipTriadData()
    const p = load()
    expect(loading.value).toBe(true)
    resolveLoad({ data: { average_days: 1, max_days: 1, age_15_plus: 1 } })
    await p
    expect(loading.value).toBe(false)
  })
})
