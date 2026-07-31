/**
 * Unit tests for the Inspector (dual-view) metric results API client.
 *
 * Same double-`/api/`-prefix bug class as ISSUE-019 (calculationAssumptions.ts):
 * a literal leading `/api/` on top of the shared client's `/api/v1` baseURL
 * double-prefixed every request and 404ed.
 */
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
import { listMetricResults, getMetricLineage } from '../api/metricResults'

describe('Metric Results API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('listMetricResults calls GET /metrics/results (not double-prefixed)', async () => {
    api.get.mockResolvedValue({ data: [] })

    await listMetricResults({ client_id: 'ACME' })

    expect(api.get).toHaveBeenCalledWith('/metrics/results', { params: { client_id: 'ACME' } })
  })

  it('getMetricLineage calls GET /metrics/results/:id (not double-prefixed)', async () => {
    api.get.mockResolvedValue({ data: {} })

    await getMetricLineage(42)

    expect(api.get).toHaveBeenCalledWith('/metrics/results/42')
  })
})
