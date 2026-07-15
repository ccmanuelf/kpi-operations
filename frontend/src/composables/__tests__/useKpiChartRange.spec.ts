import { describe, it, expect } from 'vitest'
import { computeKpiRange, KPI_RANGE_KEYS } from '../useKpiChartRange'

// Fixed "today" = Wednesday 2026-06-17 (ISO week Mon 2026-06-15 .. Sun 2026-06-21)
const TODAY = new Date(2026, 5, 17)

describe('computeKpiRange', () => {
  it('exposes exactly the four keys', () => {
    expect(KPI_RANGE_KEYS).toEqual(['thisWeek', 'lastWeek', 'lastMonth', 'last90Days'])
  })
  it('thisWeek = Monday of this week .. today', () => {
    expect(computeKpiRange('thisWeek', TODAY)).toEqual({ start: '2026-06-15', end: '2026-06-17' })
  })
  it('lastWeek = previous Mon..Sun', () => {
    expect(computeKpiRange('lastWeek', TODAY)).toEqual({ start: '2026-06-08', end: '2026-06-14' })
  })
  it('lastMonth = first..last day of previous month', () => {
    expect(computeKpiRange('lastMonth', TODAY)).toEqual({ start: '2026-05-01', end: '2026-05-31' })
  })
  it('last90Days = today-89 .. today', () => {
    expect(computeKpiRange('last90Days', TODAY)).toEqual({ start: '2026-03-20', end: '2026-06-17' })
  })
})
