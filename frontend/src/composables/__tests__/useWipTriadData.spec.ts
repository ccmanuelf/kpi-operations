import { describe, it, expect, vi, beforeEach } from 'vitest'

const { getWIPAgingMock } = vi.hoisted(() => ({ getWIPAgingMock: vi.fn() }))
vi.mock('@/services/api/kpi', () => ({ getWIPAging: getWIPAgingMock }))

import { useWipTriadData } from '@/composables/useWipTriadData'

describe('useWipTriadData', () => {
  beforeEach(() => getWIPAgingMock.mockReset())

  it('fetches getWIPAging directly (no kpi store involved) and surfaces the three distinct fields, using the real merged response shape', async () => {
    // Real shape getWIPAging() returns (frontend/src/services/api/kpi.ts):
    // it already merges /kpi/wip-aging + /kpi/wip-aging/top into one
    // object -- this composable does no additional merging of its own.
    getWIPAgingMock.mockResolvedValue({
      data: {
        average_days: 12.5,
        total_held: 20,
        total_units: 20,
        aging_15_30: 6,
        aging_over_30: 3,
        age_15_plus: 9,
        critical_count: 9,
        max_days: 67,
        total_hold_events: 5,
        top_aging: [{ age: 67 }],
      },
    })

    const { wipData, load } = useWipTriadData()
    await load()

    expect(wipData.value).toMatchObject({ average_days: 12.5, max_days: 67, age_15_plus: 9 })
    expect(getWIPAgingMock).toHaveBeenCalledTimes(1)
    const params = getWIPAgingMock.mock.calls[0][0] as Record<string, unknown>
    // No client_id (no store, no scoping) and a plain string date window --
    // never a store mutation.
    expect(params).not.toHaveProperty('client_id')
    expect(typeof params.start_date).toBe('string')
    expect(typeof params.end_date).toBe('string')
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
