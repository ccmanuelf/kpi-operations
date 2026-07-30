/**
 * Unit tests for useKPIDashboardHelpers — status badge semantics.
 *
 * Regression coverage for e2e-sweep ISSUE-003's second defect: the KPI
 * Dashboard's WIP Aging card showed "Critical" even when there was no real
 * value to evaluate. getStatusText defaulted every non-success/non-warning
 * status — including 'gray' (kpiStore.kpiStatus's own "no value/target"
 * signal) — to "Critical". A missing/absent reading is not the same as a
 * confirmed-bad one; only a genuine 'error' status should read "Critical".
 */
import { describe, it, expect, vi } from 'vitest'
import type { KPISummary, StatusColor } from '@/stores/kpi'

const kpiStoreState = {
  kpiStatus:
    () =>
    (value: number | null | undefined, target: number | null | undefined, higherBetter = true): StatusColor => {
      if (!value || !target) return 'gray'
      const pct = (value / target) * 100
      if (higherBetter) {
        if (pct >= 95) return 'success'
        if (pct >= 80) return 'warning'
        return 'error'
      }
      if (pct <= 5) return 'success'
      if (pct <= 20) return 'warning'
      return 'error'
    },
}

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))
vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => ({ kpiStatus: kpiStoreState.kpiStatus() }),
}))

import { useKPIDashboardHelpers } from '../useKPIDashboardHelpers'

const makeKpi = (overrides: Partial<KPISummary>): KPISummary => ({
  key: 'wipAging',
  title: 'WIP Aging',
  value: null,
  target: 7,
  unit: 'days',
  higherBetter: false,
  icon: 'mdi-clock-alert',
  route: '/kpi/wip-aging',
  inference: { is_estimated: false, confidence_score: 1, details: {} },
  ...overrides,
})

describe('useKPIDashboardHelpers status semantics', () => {
  it('getStatusText renders "operationsHealth.critical" for a genuinely bad lower-is-better reading', () => {
    const { getStatusText } = useKPIDashboardHelpers()
    // WIP aging averaging 74.7 days against a 7-day target is real and bad.
    const kpi = makeKpi({ value: 74.7 })

    expect(getStatusText(kpi)).toBe('operationsHealth.critical')
  })

  it('getStatusText renders "common.na" (not Critical) when there is no value to evaluate', () => {
    const { getStatusText, getStatusColor } = useKPIDashboardHelpers()
    const kpi = makeKpi({ value: null })

    expect(getStatusColor(kpi)).toBe('gray')
    expect(getStatusText(kpi)).toBe('common.na')
  })

  it('formatValue renders the raw numeric reading, not a fabricated zero', () => {
    const { formatValue } = useKPIDashboardHelpers()

    expect(formatValue(74.7, 'days')).toBe('74.7days')
    expect(formatValue(null, 'days')).toBe('common.na')
  })
})
