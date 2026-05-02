/**
 * Service-level tests for the SimPy V2 API client.
 *
 * Asserts the exact body shape we send to the backend so divergence
 * surfaces in CI rather than at runtime (the entry-interface audit
 * caught several silent 422 bugs by adding tests like this — see
 * `capacityPlanning.spec.ts` for the canonical pattern).
 *
 * Currently scoped to `runMonteCarlo` (the new endpoint shipped with
 * the SimPy V2 enhancements Deliverable 1). Other simulationV2 service
 * functions can be backfilled into this file as needed.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

import api from '../api/client'
import { runMonteCarlo } from '../api/simulationV2'

const mockApi = api as unknown as {
  post: ReturnType<typeof vi.fn>
  get: ReturnType<typeof vi.fn>
}

const validConfig = {
  operations: [],
  schedule: { shifts_enabled: 1, shift1_hours: 8, work_days: 5 },
  demands: [],
  mode: 'demand-driven' as const,
  horizon_days: 1,
}

beforeEach(() => {
  mockApi.post.mockReset()
  mockApi.post.mockResolvedValue({
    data: { success: true, n_replications: 3, aggregated_stats: {}, sample_run: null, validation_report: { errors: [], warnings: [], info: [] }, message: '' },
  })
})

describe('runMonteCarlo', () => {
  it('POSTs to /v2/simulation/run-monte-carlo with config + n_replications', async () => {
    await runMonteCarlo({ config: validConfig, n_replications: 10 })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/run-monte-carlo', {
      config: validConfig,
      n_replications: 10,
    })
  })

  it('includes base_seed when supplied', async () => {
    await runMonteCarlo({ config: validConfig, n_replications: 5, base_seed: 42 })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/run-monte-carlo', {
      config: validConfig,
      n_replications: 5,
      base_seed: 42,
    })
  })

  it('omits base_seed when null (independent RNG state)', async () => {
    await runMonteCarlo({ config: validConfig, n_replications: 7, base_seed: null })
    const body = mockApi.post.mock.calls[0][1] as Record<string, unknown>
    expect(body).not.toHaveProperty('base_seed')
  })

  it('omits base_seed when undefined (default)', async () => {
    await runMonteCarlo({ config: validConfig, n_replications: 7 })
    const body = mockApi.post.mock.calls[0][1] as Record<string, unknown>
    expect(body).not.toHaveProperty('base_seed')
  })

  it('returns the response data verbatim', async () => {
    const expected = {
      success: true,
      n_replications: 4,
      base_seed: 1,
      total_duration_seconds: 1.2,
      aggregated_stats: { daily_summary: { daily_throughput_pcs: { mean: 200, std: 5, ci_lo_95: 196, ci_hi_95: 204, n: 4 } } },
      sample_run: { daily_summary: { daily_throughput_pcs: 200 } },
      validation_report: { errors: [], warnings: [], info: [] },
      message: 'ok',
    }
    mockApi.post.mockResolvedValueOnce({ data: expected })
    const result = await runMonteCarlo({ config: validConfig, n_replications: 4, base_seed: 1 })
    expect(result).toEqual(expected)
  })

  it('forwards backend rejections as thrown errors', async () => {
    const err = new Error('422 Validation failed')
    mockApi.post.mockRejectedValueOnce(err)
    await expect(
      runMonteCarlo({ config: validConfig, n_replications: 2, base_seed: 0 }),
    ).rejects.toThrow('422 Validation failed')
  })
})
