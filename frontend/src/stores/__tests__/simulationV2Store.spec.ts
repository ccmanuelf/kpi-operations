/**
 * Store-level tests for the SimPy V2 simulation store, focused on the
 * Monte Carlo deliverable wiring.
 *
 * Verifies that flipping `monteCarloEnabled` and calling
 * `runMonteCarloAction()` issues the expected service call AND
 * populates `monteCarloAggregatedStats` + `results` from the response.
 * This complements the service-level spec — service spec covers the
 * request body, this covers the store's response handling.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/services/api/simulationV2', () => {
  const sample = {
    daily_summary: { daily_throughput_pcs: 200 },
  }
  const mcResponseSuccess = {
    success: true,
    n_replications: 10,
    base_seed: 7,
    total_duration_seconds: 1.5,
    aggregated_stats: {
      daily_summary: {
        daily_throughput_pcs: { mean: 200, std: 5, ci_lo_95: 196, ci_hi_95: 204, n: 10 },
      },
    },
    sample_run: sample,
    validation_report: { errors: [], warnings: [], info: [], is_valid: true },
    message: 'ok',
  }
  return {
    getSimulationInfo: vi.fn(),
    validateSimulationConfig: vi.fn(),
    runSimulation: vi.fn(),
    runMonteCarlo: vi.fn().mockResolvedValue(mcResponseSuccess),
    buildSimulationConfig: vi.fn().mockReturnValue({
      operations: [],
      schedule: {},
      demands: [],
      mode: 'demand-driven',
      horizon_days: 1,
    }),
    getDefaultOperation: vi.fn(),
    getDefaultSchedule: vi.fn().mockReturnValue({
      shifts_enabled: 1,
      shift1_hours: 8,
      shift2_hours: 0,
      shift3_hours: 0,
      work_days: 5,
      ot_enabled: false,
    }),
    getDefaultDemand: vi.fn(),
    getDefaultBreakdown: vi.fn(),
    getSampleTShirtData: vi.fn(),
    isFirstVisit: vi.fn().mockReturnValue(false),
    markAsVisited: vi.fn(),
    clearVisitedFlag: vi.fn(),
  }
})

import { useSimulationV2Store } from '../simulationV2Store'
import { runMonteCarlo } from '@/services/api/simulationV2'

const mockRunMonteCarlo = runMonteCarlo as unknown as ReturnType<typeof vi.fn>

beforeEach(() => {
  setActivePinia(createPinia())
  mockRunMonteCarlo.mockClear()
})

describe('Monte Carlo state defaults', () => {
  it('starts with MC disabled, 10 replications, no base seed', () => {
    const s = useSimulationV2Store()
    expect(s.monteCarloEnabled).toBe(false)
    expect(s.monteCarloReplications).toBe(10)
    expect(s.monteCarloBaseSeed).toBeNull()
    expect(s.monteCarloAggregatedStats).toBeNull()
    expect(s.monteCarloDurationSeconds).toBeNull()
  })
})

describe('runMonteCarloAction', () => {
  it('calls runMonteCarlo with current state values', async () => {
    const s = useSimulationV2Store()
    s.monteCarloEnabled = true
    s.monteCarloReplications = 25
    s.monteCarloBaseSeed = 99

    await s.runMonteCarloAction()

    expect(mockRunMonteCarlo).toHaveBeenCalledTimes(1)
    const args = mockRunMonteCarlo.mock.calls[0][0] as Record<string, unknown>
    expect(args.n_replications).toBe(25)
    expect(args.base_seed).toBe(99)
    expect(args.config).toEqual({
      operations: [],
      schedule: {},
      demands: [],
      mode: 'demand-driven',
      horizon_days: 1,
    })
  })

  it('populates aggregated stats and sample_run on success', async () => {
    const s = useSimulationV2Store()
    s.monteCarloEnabled = true

    await s.runMonteCarloAction()

    expect(s.monteCarloAggregatedStats).not.toBeNull()
    expect(s.monteCarloDurationSeconds).toBe(1.5)
    expect(s.results).toEqual({ daily_summary: { daily_throughput_pcs: 200 } })
    expect(s.showResultsDialog).toBe(true)
    expect(s.simulationMessage).toBe('ok')
  })

  it('clears MC state when called (each run is fresh)', async () => {
    const s = useSimulationV2Store()
    s.monteCarloAggregatedStats = { stale: true } as Record<string, unknown>
    s.monteCarloDurationSeconds = 99

    await s.runMonteCarloAction()

    // Stale stats replaced by current run's stats; not retained.
    expect(s.monteCarloAggregatedStats).toEqual({
      daily_summary: {
        daily_throughput_pcs: { mean: 200, std: 5, ci_lo_95: 196, ci_hi_95: 204, n: 10 },
      },
    })
    expect(s.monteCarloDurationSeconds).toBe(1.5)
  })

  it('routes through validation panel on validation failure', async () => {
    mockRunMonteCarlo.mockResolvedValueOnce({
      success: false,
      validation_report: {
        errors: [{ message: 'bad' }],
        warnings: [],
        info: [],
        is_valid: false,
      },
      message: 'Validation failed',
    })

    const s = useSimulationV2Store()
    await s.runMonteCarloAction()

    expect(s.results).toBeNull()
    expect(s.showResultsDialog).toBe(false)
    expect(s.showValidationPanel).toBe(true)
    expect(s.simulationMessage).toBe('Validation failed')
  })

  it('toggles isRunning around the call', async () => {
    const s = useSimulationV2Store()
    expect(s.isRunning).toBe(false)
    const promise = s.runMonteCarloAction()
    expect(s.isRunning).toBe(true)
    await promise
    expect(s.isRunning).toBe(false)
  })

  it('reset() clears MC state', async () => {
    const s = useSimulationV2Store()
    await s.runMonteCarloAction()
    expect(s.monteCarloAggregatedStats).not.toBeNull()
    s.reset()
    expect(s.monteCarloAggregatedStats).toBeNull()
    expect(s.monteCarloDurationSeconds).toBeNull()
  })
})
