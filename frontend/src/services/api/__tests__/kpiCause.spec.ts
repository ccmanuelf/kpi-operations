import { describe, it, expect, vi, beforeEach } from 'vitest'

const get = vi.fn()
vi.mock('../client', () => ({ default: { get: (...a: unknown[]) => get(...a) } }))

import { fetchKpiCause, fetchKpiCauses } from '../kpi'

describe('fetchKpiCause / fetchKpiCauses', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls the cause endpoint and returns the payload when a factor exists', async () => {
    get.mockResolvedValue({ data: { date: '2026-06-10', kind: 'downtime', factor: 'Changeover', value: 60, unit: 'min', share: 0.5 } })
    const res = await fetchKpiCause('availability', '2026-06-10', 'C1')
    expect(get).toHaveBeenCalledWith('/kpi/availability/cause', { params: { date: '2026-06-10', client_id: 'C1' } })
    expect(res?.factor).toBe('Changeover')
  })

  it('returns null when the response has no factor', async () => {
    get.mockResolvedValue({ data: { date: '2026-06-10', factor: null } })
    expect(await fetchKpiCause('efficiency', '2026-06-10')).toBeNull()
  })

  it('returns null on error', async () => {
    get.mockRejectedValue(new Error('boom'))
    expect(await fetchKpiCause('availability', '2026-06-10')).toBeNull()
  })

  it('batches multiple dates into a date-keyed map, dropping nulls', async () => {
    get
      .mockResolvedValueOnce({ data: { date: '2026-06-10', factor: 'Burr', kind: 'defect', value: 3, unit: 'count', share: 1 } })
      .mockResolvedValueOnce({ data: { date: '2026-06-11', factor: null } })
    const map = await fetchKpiCauses('quality', ['2026-06-10', '2026-06-11'], 'C1')
    expect(Object.keys(map)).toEqual(['2026-06-10'])
    expect(map['2026-06-10'].factor).toBe('Burr')
  })
})
