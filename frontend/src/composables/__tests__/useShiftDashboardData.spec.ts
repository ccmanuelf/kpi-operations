/**
 * Unit tests for useShiftDashboardData — e2e-sweep ISSUE-007.
 *
 * Verifies the MyShift dashboard's data-fetching composable:
 *  - never falls back to fabricated records (no `fallbackData()` exists
 *    anymore; a failed/errored fetch must leave the screen in the real,
 *    honest empty state instead of inventing WO-2024-* work orders).
 *  - wires to the real backend endpoint (api.getMyShiftSummary ->
 *    GET /my-shift/summary) and maps its response verbatim.
 *  - hasAssignments reflects whether there is any real assigned work order.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getMyShiftSummary: vi.fn(),
  },
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: { value: 'en' } }),
}))

import { useShiftDashboardData } from '../useShiftDashboardData'

// Every string any mock/fabricated record used, so a future regression that
// reintroduces a fallback (even under a different shape) gets caught here.
const FORBIDDEN_MOCK_STRINGS = [
  'WO-2024-001',
  'WO-2024-002',
  'WO-2024-003',
  'Widget A',
  'Widget B',
  'Component X',
]

function assertNoFabricatedRecords(...haystacks: unknown[]): void {
  const serialized = JSON.stringify(haystacks)
  for (const forbidden of FORBIDDEN_MOCK_STRINGS) {
    expect(serialized).not.toContain(forbidden)
  }
  // Structural check independent of the specific literal strings above:
  // no work order in the resulting state may match the WO-2024-* pattern.
  expect(serialized).not.toMatch(/WO-2024-\d+/)
}

describe('useShiftDashboardData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('unassigned user (e.g. verify_bot — no line/shift mapping)', () => {
    it('renders the real empty state, never a fabricated fallback, when the API returns nothing', async () => {
      mockApi.getMyShiftSummary.mockResolvedValueOnce({
        data: {
          date: '2026-07-30',
          shift_id: null,
          operator_id: null,
          stats: {
            units_produced: 0,
            efficiency: 0,
            downtime_incidents: 0,
            downtime_minutes: 0,
            quality_checks: 0,
            defect_count: 0,
          },
          assigned_work_orders: [],
          recent_activity: [],
          data_completeness: {},
        },
      })

      const { assignedWorkOrders, recentActivity, myStats, hasAssignments, fetchMyShiftData } =
        useShiftDashboardData()

      await fetchMyShiftData()

      expect(assignedWorkOrders.value).toEqual([])
      expect(recentActivity.value).toEqual([])
      expect(myStats.value).toEqual({
        unitsProduced: 0,
        efficiency: 0,
        downtimeIncidents: 0,
        qualityChecks: 0,
      })
      expect(hasAssignments.value).toBe(false)
      assertNoFabricatedRecords(assignedWorkOrders.value, recentActivity.value, myStats.value)
    })

    it('renders the real empty state — never the mock fallback — when the API call fails', async () => {
      mockApi.getMyShiftSummary.mockRejectedValueOnce(new Error('network error'))

      const { assignedWorkOrders, recentActivity, myStats, hasAssignments, fetchMyShiftData } =
        useShiftDashboardData()

      await fetchMyShiftData()

      expect(assignedWorkOrders.value).toEqual([])
      expect(recentActivity.value).toEqual([])
      expect(myStats.value).toEqual({
        unitsProduced: 0,
        efficiency: 0,
        downtimeIncidents: 0,
        qualityChecks: 0,
      })
      expect(hasAssignments.value).toBe(false)
      assertNoFabricatedRecords(assignedWorkOrders.value, recentActivity.value, myStats.value)
    })
  })

  describe('assigned user (mocked real backend data)', () => {
    it('renders the real assigned work orders, stats, and activity returned by the API', async () => {
      mockApi.getMyShiftSummary.mockResolvedValueOnce({
        data: {
          date: '2026-07-30',
          shift_id: 1,
          operator_id: 'OP-42',
          stats: {
            units_produced: 240,
            efficiency: 92.5,
            downtime_incidents: 1,
            downtime_minutes: 20,
            quality_checks: 3,
            defect_count: 2,
          },
          assigned_work_orders: [
            {
              id: 1,
              work_order_id: 'WO-DEMO-042',
              product_name: 'Real Product',
              target_qty: 400,
              produced: 240,
              progress_percent: 60,
            },
          ],
          recent_activity: [
            {
              id: 'prod-501',
              type: 'production',
              description: 'Logged 80 units for WO-DEMO-042',
              timestamp: '2026-07-30T08:00:00Z',
            },
          ],
          data_completeness: {},
        },
      })

      const { assignedWorkOrders, recentActivity, myStats, hasAssignments, fetchMyShiftData } =
        useShiftDashboardData()

      await fetchMyShiftData()

      expect(assignedWorkOrders.value).toEqual([
        {
          id: 1,
          work_order_id: 'WO-DEMO-042',
          product_name: 'Real Product',
          target_qty: 400,
          produced: 240,
          progress_percent: 60,
        },
      ])
      expect(recentActivity.value).toEqual([
        {
          id: 'prod-501',
          type: 'production',
          description: 'Logged 80 units for WO-DEMO-042',
          timestamp: '2026-07-30T08:00:00Z',
        },
      ])
      expect(myStats.value).toEqual({
        unitsProduced: 240,
        efficiency: 92.5,
        downtimeIncidents: 1,
        qualityChecks: 3,
      })
      expect(hasAssignments.value).toBe(true)
      expect(mockApi.getMyShiftSummary).toHaveBeenCalledWith(
        expect.objectContaining({ shift_date: expect.any(String) }),
      )
    })
  })
})
