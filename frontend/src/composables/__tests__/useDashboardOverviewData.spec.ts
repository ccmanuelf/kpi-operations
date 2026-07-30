/**
 * Behavioral regression test: useDashboardOverviewData must fetch through
 * the shared, authed `@/services/api` client — not raw `axios` (the
 * ISSUE-020 class; see services/api/__tests__/no-raw-axios-import.spec.ts
 * for the structural guard). A bare `axios.get(...)` call carries no
 * Authorization header, so every KPI on the home-page overview would
 * silently 401 in production.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('@/services/api', () => ({ default: apiMock }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))
// onMounted requires an active component instance outside a real render;
// no-op it so calling the composable directly (matching this repo's other
// use*Data composable specs) doesn't warn/throw.
vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue')>()
  return { ...actual, onMounted: vi.fn() }
})

import { useDashboardOverviewData } from '../useDashboardOverviewData'

describe('useDashboardOverviewData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.get.mockImplementation((url: string) => {
      const map: Record<string, unknown> = {
        '/kpi/efficiency/trend': { value: 88.2 },
        '/kpi/performance/trend': { value: 91.5 },
        '/kpi/wip-aging': { average_aging_days: 12.3 },
        '/kpi/otd': { otd_percentage: 94.1 },
        '/kpi/availability': { average_availability: 89.9 },
        '/attendance/kpi/absenteeism': { absenteeism_rate: 4.2 },
        '/quality/kpi/ppm': { ppm: 120 },
        '/quality/kpi/dpmo': { dpmo: 300 },
        '/quality/kpi/fpy-rty': { fpy: 97.5, rty: 96.1 },
      }
      return Promise.resolve({ data: map[url] })
    })
  })

  it('fetchKPIData calls the shared client with un-prefixed paths (not raw axios)', async () => {
    const { fetchKPIData, kpiData } = useDashboardOverviewData({})
    await fetchKPIData()

    expect(apiMock.get).toHaveBeenCalledWith('/kpi/efficiency/trend')
    expect(apiMock.get).toHaveBeenCalledWith('/kpi/wip-aging')
    expect(apiMock.get).toHaveBeenCalledWith('/attendance/kpi/absenteeism')
    // None of the calls carry a double /api/ prefix or bypass the client.
    for (const call of apiMock.get.mock.calls) {
      expect(String(call[0])).not.toMatch(/^\/api\//)
    }
    expect(kpiData.value.wipAging).toBe(12.3)
    expect(kpiData.value.absenteeism).toBe(4.2)
  })
})
