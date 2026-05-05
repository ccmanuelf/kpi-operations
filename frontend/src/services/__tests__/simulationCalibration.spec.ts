import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
  },
}))

import api from '../api/client'
import { calibrateFromHistory } from '../api/simulationCalibration'

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
}

const fixture = {
  client_id: 'ACME-MFG',
  period: { start: '2026-04-01', end: '2026-04-30', days: 30 },
  config: {
    operations: [],
    schedule: { shifts_enabled: 1, shift1_hours: 8, work_days: 5 },
    demands: [],
    mode: 'demand-driven',
    horizon_days: 7,
  },
  sources: {
    schedule: {
      source: 'SHIFT',
      sample_size: 22,
      period: '2026-04-01 to 2026-04-30',
      confidence: 'high',
    },
  },
  warnings: [],
}

beforeEach(() => {
  mockApi.get.mockReset().mockResolvedValue({ data: fixture })
})

describe('calibrateFromHistory', () => {
  it('GETs /v2/simulation/calibration with just client_id', async () => {
    await calibrateFromHistory({ client_id: 'ACME-MFG' })
    expect(mockApi.get).toHaveBeenCalledWith('/v2/simulation/calibration', {
      params: { client_id: 'ACME-MFG' },
    })
  })

  it('forwards period_start + period_end when provided', async () => {
    await calibrateFromHistory({
      client_id: 'ACME-MFG',
      period_start: '2026-04-01',
      period_end: '2026-04-30',
    })
    expect(mockApi.get).toHaveBeenCalledWith('/v2/simulation/calibration', {
      params: {
        client_id: 'ACME-MFG',
        period_start: '2026-04-01',
        period_end: '2026-04-30',
      },
    })
  })

  it('omits empty period_start / period_end strings', async () => {
    await calibrateFromHistory({
      client_id: 'ACME-MFG',
      period_start: '',
      period_end: '',
    })
    expect(mockApi.get).toHaveBeenCalledWith('/v2/simulation/calibration', {
      params: { client_id: 'ACME-MFG' },
    })
  })

  it('returns the response data verbatim', async () => {
    const result = await calibrateFromHistory({ client_id: 'ACME-MFG' })
    expect(result).toEqual(fixture)
    expect(result.config.horizon_days).toBe(7)
    expect(result.sources.schedule.confidence).toBe('high')
  })

  it('propagates errors from the API client', async () => {
    mockApi.get.mockRejectedValueOnce({ response: { status: 403, data: { detail: 'forbidden' } } })
    await expect(calibrateFromHistory({ client_id: 'TEXTILE-PRO' })).rejects.toMatchObject({
      response: { status: 403 },
    })
  })
})
