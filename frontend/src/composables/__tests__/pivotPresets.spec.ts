import { describe, it, expect } from 'vitest'
import { PIVOT_VIEWS, DATASET_GROUPINGS } from '@/composables/pivotPresets'

describe('PIVOT_VIEWS structural invariants', () => {
  it('declares exactly q1..q5 in order', () => {
    expect(PIVOT_VIEWS.map((v) => v.id)).toEqual(['q1', 'q2', 'q3', 'q4', 'q5'])
  })
  it('every view has >=1 dataset, >=1 grouping incl. time-only, >=2 columns', () => {
    for (const v of PIVOT_VIEWS) {
      expect(v.datasets.length).toBeGreaterThanOrEqual(1)
      expect(v.groupings.some((g) => g.value === null)).toBe(true)
      expect(v.columns.length).toBeGreaterThanOrEqual(2)
    }
  })
  it('q3 delay_reason grouping exposes late counts, never a per-reason OTD% (spec §6)', () => {
    const q3 = PIVOT_VIEWS.find((v) => v.id === 'q3')!
    expect(q3.groupings.map((g) => g.value)).toContain('delay_reason')
    expect(q3.columns.some((c) => c.key === 'justified_late')).toBe(true)
  })
  it('every preset grouping valid for at least one of its view\'s datasets', () => {
    for (const view of PIVOT_VIEWS) {
      for (const grouping of view.groupings) {
        if (grouping.value === null) {
          // time-only is always valid
          continue
        }
        const valid = view.datasets.some((ds) =>
          (DATASET_GROUPINGS[ds] ?? []).includes(grouping.value),
        )
        expect(valid).toBe(true)
      }
    }
  })
})
