import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../api/client'
import {
  listScenarios,
  getScenario,
  createScenario,
  updateScenario,
  deleteScenario,
  duplicateScenario,
  runScenario,
} from '../api/simulationScenarios'

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

const cfg = {
  operations: [],
  schedule: { shifts_enabled: 1, shift1_hours: 8, work_days: 5 },
  demands: [],
  mode: 'demand-driven' as const,
  horizon_days: 1,
}

beforeEach(() => {
  mockApi.get.mockReset().mockResolvedValue({ data: [] })
  mockApi.post.mockReset().mockResolvedValue({ data: { id: 1 } })
  mockApi.put.mockReset().mockResolvedValue({ data: { id: 1 } })
  mockApi.delete.mockReset().mockResolvedValue({ data: null })
})

describe('listScenarios', () => {
  it('GETs /v2/simulation/scenarios with no params by default', async () => {
    await listScenarios()
    expect(mockApi.get).toHaveBeenCalledWith('/v2/simulation/scenarios', { params: {} })
  })

  it('forwards include_inactive + client_id + skip + limit', async () => {
    await listScenarios({ include_inactive: true, client_id: 'ACME-MFG', skip: 10, limit: 50 })
    expect(mockApi.get).toHaveBeenCalledWith('/v2/simulation/scenarios', {
      params: { include_inactive: true, client_id: 'ACME-MFG', skip: 10, limit: 50 },
    })
  })

  it('returns the response data verbatim', async () => {
    const fixture = [{ id: 1, name: 'baseline', client_id: 'ACME-MFG', is_active: true }]
    mockApi.get.mockResolvedValueOnce({ data: fixture })
    const result = await listScenarios()
    expect(result).toBe(fixture)
  })
})

describe('getScenario', () => {
  it('GETs /v2/simulation/scenarios/:id', async () => {
    mockApi.get.mockResolvedValueOnce({ data: { id: 7, config_json: cfg } })
    await getScenario(7)
    expect(mockApi.get).toHaveBeenCalledWith('/v2/simulation/scenarios/7')
  })
})

describe('createScenario', () => {
  it('POSTs minimal payload (name + config_json only)', async () => {
    await createScenario({ name: 'baseline', config_json: cfg })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/scenarios', {
      name: 'baseline',
      config_json: cfg,
    })
  })

  it('forwards all optional fields when provided', async () => {
    await createScenario({
      name: 'optimized',
      description: 'Pattern 1 result',
      client_id: 'ACME-MFG',
      config_json: cfg,
      tags: ['baseline', 'optimized'],
    })
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/scenarios', {
      name: 'optimized',
      description: 'Pattern 1 result',
      client_id: 'ACME-MFG',
      config_json: cfg,
      tags: ['baseline', 'optimized'],
    })
  })

  it('omits optional fields when undefined (vs null)', async () => {
    await createScenario({ name: 'x', config_json: cfg })
    const body = mockApi.post.mock.calls[0][1] as Record<string, unknown>
    expect(body).not.toHaveProperty('description')
    expect(body).not.toHaveProperty('tags')
  })

  it('preserves explicit null client_id (admin global template)', async () => {
    await createScenario({ name: 'global', client_id: null, config_json: cfg })
    const body = mockApi.post.mock.calls[0][1] as Record<string, unknown>
    expect(body.client_id).toBeNull()
  })
})

describe('updateScenario', () => {
  it('PUTs partial payload', async () => {
    await updateScenario(3, { name: 'renamed', tags: ['v2'] })
    expect(mockApi.put).toHaveBeenCalledWith('/v2/simulation/scenarios/3', {
      name: 'renamed',
      tags: ['v2'],
    })
  })
})

describe('deleteScenario', () => {
  it('DELETEs /v2/simulation/scenarios/:id', async () => {
    await deleteScenario(9)
    expect(mockApi.delete).toHaveBeenCalledWith('/v2/simulation/scenarios/9')
  })
})

describe('duplicateScenario', () => {
  it('POSTs to /duplicate with no params by default', async () => {
    await duplicateScenario(5)
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/scenarios/5/duplicate', null, {
      params: {},
    })
  })

  it('forwards new_name when provided', async () => {
    await duplicateScenario(5, 'My Variant')
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/scenarios/5/duplicate', null, {
      params: { new_name: 'My Variant' },
    })
  })
})

describe('runScenario', () => {
  it('POSTs to /run', async () => {
    await runScenario(11)
    expect(mockApi.post).toHaveBeenCalledWith('/v2/simulation/scenarios/11/run')
  })

  it('returns the updated scenario with last_run_summary', async () => {
    const fixture = {
      id: 11,
      name: 'x',
      config_json: cfg,
      last_run_summary: { daily_throughput_pcs: 487 },
    }
    mockApi.post.mockResolvedValueOnce({ data: fixture })
    const result = await runScenario(11)
    expect(result.last_run_summary?.daily_throughput_pcs).toBe(487)
  })
})

describe('error propagation', () => {
  it('forwards backend rejection on create', async () => {
    mockApi.post.mockRejectedValueOnce(new Error('403 Forbidden'))
    await expect(createScenario({ name: 'x', config_json: cfg })).rejects.toThrow('403 Forbidden')
  })

  it('forwards backend rejection on run', async () => {
    mockApi.post.mockRejectedValueOnce(new Error('422 Validation failed'))
    await expect(runScenario(1)).rejects.toThrow('422 Validation failed')
  })
})
