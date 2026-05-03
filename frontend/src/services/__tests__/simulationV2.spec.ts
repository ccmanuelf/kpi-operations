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
import {
  runMonteCarlo,
  optimizeOperatorAllocation,
  rebalanceBottlenecks,
  sequenceProducts,
  planHorizon,
} from '../api/simulationV2'

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

describe('optimizeOperatorAllocation (Pattern 1)', () => {
  it('POSTs to /v2/simulation/optimize-operators with defaults', async () => {
    await optimizeOperatorAllocation({ config: validConfig })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/optimize-operators', {
      config: validConfig,
      max_operators_per_op: 10,
      timeout_seconds: 15,
      validate_with_simulation: false,
    })
  })

  it('forwards explicit options', async () => {
    await optimizeOperatorAllocation({
      config: validConfig,
      max_operators_per_op: 5,
      total_operators_budget: 8,
      timeout_seconds: 30,
      validate_with_simulation: true,
    })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/optimize-operators', {
      config: validConfig,
      max_operators_per_op: 5,
      total_operators_budget: 8,
      timeout_seconds: 30,
      validate_with_simulation: true,
    })
  })

  it('omits total_operators_budget when null', async () => {
    await optimizeOperatorAllocation({
      config: validConfig,
      total_operators_budget: null,
    })
    const body = mockApi.post.mock.calls[0][1] as Record<string, unknown>
    expect(body).not.toHaveProperty('total_operators_budget')
  })

  it('returns the response data verbatim', async () => {
    const expected = {
      success: true,
      is_optimal: true,
      total_operators_before: 6,
      total_operators_after: 4,
      proposals: [],
      solver_message: 'ok',
    }
    mockApi.post.mockResolvedValueOnce({ data: expected })
    const result = await optimizeOperatorAllocation({ config: validConfig })
    expect(result).toEqual(expected)
  })

  it('forwards backend rejections', async () => {
    mockApi.post.mockRejectedValueOnce(new Error('503 Service Unavailable'))
    await expect(
      optimizeOperatorAllocation({ config: validConfig }),
    ).rejects.toThrow('503 Service Unavailable')
  })
})

describe('rebalanceBottlenecks (Pattern 2)', () => {
  it('POSTs to /v2/simulation/rebalance-bottlenecks with defaults', async () => {
    await rebalanceBottlenecks({ config: validConfig })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/rebalance-bottlenecks', {
      config: validConfig,
      min_operators_per_op: 1,
      max_operators_per_op: 10,
      total_delta_max: 0,
      total_delta_min: -50,
      timeout_seconds: 15,
      validate_with_simulation: false,
    })
  })

  it('forwards explicit options including growth budget', async () => {
    await rebalanceBottlenecks({
      config: validConfig,
      min_operators_per_op: 2,
      max_operators_per_op: 8,
      total_delta_max: 3,
      total_delta_min: -10,
      timeout_seconds: 30,
      validate_with_simulation: true,
    })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/rebalance-bottlenecks', {
      config: validConfig,
      min_operators_per_op: 2,
      max_operators_per_op: 8,
      total_delta_max: 3,
      total_delta_min: -10,
      timeout_seconds: 30,
      validate_with_simulation: true,
    })
  })

  it('returns the response data verbatim', async () => {
    const expected = {
      success: true,
      is_optimal: true,
      total_operators_before: 6,
      total_operators_after: 6,
      total_delta: 0,
      min_slack_pcs: 149,
      proposals: [],
      solver_message: 'Rebalanced 2 stations.',
    }
    mockApi.post.mockResolvedValueOnce({ data: expected })
    const result = await rebalanceBottlenecks({ config: validConfig })
    expect(result).toEqual(expected)
  })

  it('forwards backend rejections', async () => {
    mockApi.post.mockRejectedValueOnce(new Error('503 Service Unavailable'))
    await expect(
      rebalanceBottlenecks({ config: validConfig }),
    ).rejects.toThrow('503 Service Unavailable')
  })
})

describe('sequenceProducts (Pattern 3)', () => {
  it('POSTs to /v2/simulation/sequence-products with defaults', async () => {
    await sequenceProducts({ config: validConfig })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/sequence-products', {
      config: validConfig,
      setup_times_minutes: [],
      timeout_seconds: 30,
    })
  })

  it('forwards an explicit setup-time matrix', async () => {
    const setup = [
      { from_product: 'A', to_product: 'B', setup_minutes: 10 },
      { from_product: 'B', to_product: 'A', setup_minutes: 60 },
    ]
    await sequenceProducts({
      config: validConfig,
      setup_times_minutes: setup,
      timeout_seconds: 60,
    })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/sequence-products', {
      config: validConfig,
      setup_times_minutes: setup,
      timeout_seconds: 60,
    })
  })

  it('returns the response data verbatim', async () => {
    const expected = {
      success: true,
      is_optimal: true,
      is_satisfied: true,
      status: 'satisfied',
      makespan_minutes: 295,
      total_setup_minutes: 25,
      total_production_minutes: 270,
      sequence: [
        {
          position: 1,
          product: 'A',
          production_time_minutes: 120,
          start_time_minutes: 0,
          end_time_minutes: 120,
          setup_from_previous_minutes: 0,
        },
      ],
      solver_message: 'ok',
    }
    mockApi.post.mockResolvedValueOnce({ data: expected })
    const result = await sequenceProducts({ config: validConfig })
    expect(result).toEqual(expected)
  })

  it('forwards backend rejections', async () => {
    mockApi.post.mockRejectedValueOnce(new Error('503 Service Unavailable'))
    await expect(
      sequenceProducts({ config: validConfig }),
    ).rejects.toThrow('503 Service Unavailable')
  })
})

describe('planHorizon (Pattern 4)', () => {
  it('POSTs to /v2/simulation/plan-horizon with defaults', async () => {
    await planHorizon({ config: validConfig })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/plan-horizon', {
      config: validConfig,
      horizon_days: 5,
      timeout_seconds: 30,
    })
  })

  it('forwards explicit horizon_days', async () => {
    await planHorizon({ config: validConfig, horizon_days: 10, timeout_seconds: 60 })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/plan-horizon', {
      config: validConfig,
      horizon_days: 10,
      timeout_seconds: 60,
    })
  })

  it('returns the response data verbatim', async () => {
    const expected = {
      success: true,
      is_optimal: true,
      is_satisfied: true,
      status: 'satisfied',
      horizon_days: 5,
      products: ['A', 'B'],
      weekly_demand: { A: 500, B: 300 },
      daily_minutes_capacity: 480,
      max_load_pct: 67,
      daily_plans: [
        { day: 1, pieces_by_product: { A: 100, B: 60 }, total_pieces: 160, minutes_used: 320, daily_minutes_capacity: 480, load_pct: 66.67 },
      ],
      fulfillment_by_product: { A: 500, B: 300 },
      solver_message: 'Optimal plan found.',
    }
    mockApi.post.mockResolvedValueOnce({ data: expected })
    const result = await planHorizon({ config: validConfig })
    expect(result).toEqual(expected)
  })

  it('forwards backend rejections', async () => {
    mockApi.post.mockRejectedValueOnce(new Error('503 Service Unavailable'))
    await expect(
      planHorizon({ config: validConfig }),
    ).rejects.toThrow('503 Service Unavailable')
  })
})
