/**
 * Unit tests for the Calculation Assumption Registry API client.
 *
 * Regression coverage for the e2e-sweep ISSUE-019 root cause: every
 * exported call had a redundant literal `/api/` prefix layered on top of
 * the shared client's `/api/v1` baseURL, double-prefixing every request
 * (e.g. `/api/v1/api/assumptions/variance`) and 404ing.
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
import { getCatalog, getVarianceReport, listAssumptions } from '../api/calculationAssumptions'

describe('Calculation Assumptions API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getVarianceReport calls GET /assumptions/variance (not double-prefixed)', async () => {
    const mockRows = [{ assumption_id: 1, client_id: 'ACME', assumption_name: 'x' }]
    api.get.mockResolvedValue({ data: mockRows })

    const result = await getVarianceReport(180)

    expect(api.get).toHaveBeenCalledWith('/assumptions/variance', {
      params: { stale_after_days: 180 },
    })
    expect(result.data).toEqual(mockRows)
  })

  it('getCatalog calls GET /assumptions/catalog (not double-prefixed)', async () => {
    api.get.mockResolvedValue({ data: [] })

    await getCatalog()

    expect(api.get).toHaveBeenCalledWith('/assumptions/catalog')
  })

  it('listAssumptions calls GET /assumptions (not double-prefixed)', async () => {
    api.get.mockResolvedValue({ data: [] })

    await listAssumptions({ client_id: 'ACME' })

    expect(api.get).toHaveBeenCalledWith('/assumptions', { params: { client_id: 'ACME' } })
  })
})
