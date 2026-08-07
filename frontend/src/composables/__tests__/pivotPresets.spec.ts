import { describe, it, expect } from 'vitest'
import { BUCKET_LABEL_KEYS, VALID_BUCKETS, PIVOT_VIEWS, DATASET_GROUPINGS, groupLabel, visibleColumns } from '@/composables/pivotPresets'

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
  it('q3 otd_gross_pct/otd_net_pct declare the delay_reason exclusion', () => {
    const q3 = PIVOT_VIEWS.find((v) => v.id === 'q3')!
    const gross = q3.columns.find((c) => c.key === 'otd_gross_pct')!
    const net = q3.columns.find((c) => c.key === 'otd_net_pct')!
    expect(gross.hideForGroupings).toEqual(['delay_reason'])
    expect(net.hideForGroupings).toEqual(['delay_reason'])
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

describe('BUCKET_LABEL_KEYS', () => {
  it('covers exactly VALID_BUCKETS, each with a literal pivot.buckets.* key', () => {
    expect(Object.keys(BUCKET_LABEL_KEYS).sort()).toEqual([...VALID_BUCKETS].sort())
    for (const bucket of VALID_BUCKETS) {
      expect(BUCKET_LABEL_KEYS[bucket]).toBe(`pivot.buckets.${bucket}`)
    }
  })
})

describe('visibleColumns', () => {
  const q3 = PIVOT_VIEWS.find((v) => v.id === 'q3')!

  it('drops otd_gross_pct/otd_net_pct when grouped by delay_reason', () => {
    const cols = visibleColumns(q3, 'delay_reason').map((c) => c.key)
    expect(cols).not.toContain('otd_gross_pct')
    expect(cols).not.toContain('otd_net_pct')
    // Everything else in q3 stays -- only the two OTD% columns are hidden.
    expect(cols).toContain('justified_late')
    expect(cols).toContain('delivered')
  })

  it('keeps otd_gross_pct/otd_net_pct for other groupings, incl. time-only (null)', () => {
    expect(visibleColumns(q3, null).map((c) => c.key)).toEqual(q3.columns.map((c) => c.key))
    expect(visibleColumns(q3, 'client').map((c) => c.key)).toEqual(q3.columns.map((c) => c.key))
    expect(visibleColumns(q3, 'style').map((c) => c.key)).toEqual(q3.columns.map((c) => c.key))
  })

  it('is a no-op for presets with no hideForGroupings columns', () => {
    const q1 = PIVOT_VIEWS.find((v) => v.id === 'q1')!
    expect(visibleColumns(q1, 'client').map((c) => c.key)).toEqual(q1.columns.map((c) => c.key))
  })
})

describe('groupLabel', () => {
  const t = (key: string) => `[${key}]`

  it('renders an em dash for null/undefined', () => {
    expect(groupLabel(null, t)).toBe('—')
    expect(groupLabel(undefined, t)).toBe('—')
  })

  it('localizes all four backend sentinels', () => {
    expect(groupLabel('none', t)).toBe('[pivot.sentinels.none]')
    expect(groupLabel('uncategorized', t)).toBe('[pivot.sentinels.uncategorized]')
    expect(groupLabel('unknown', t)).toBe('[pivot.sentinels.unknown]')
    expect(groupLabel('unclassified', t)).toBe('[pivot.sentinels.unclassified]')
  })

  it('renders non-sentinel values as-is when groupBy is not delay_reason', () => {
    expect(groupLabel('material_supplier_delay', t)).toBe('material_supplier_delay')
    expect(groupLabel('ACME Corp', t)).toBe('ACME Corp')
    expect(groupLabel('ACME Corp', t, 'client')).toBe('ACME Corp')
  })

  it('localizes all six delay-reason codes when grouped by delay_reason (F2)', () => {
    expect(groupLabel('customer_request', t, 'delay_reason')).toBe('[delay.reasons.customerRequest]')
    expect(groupLabel('customer_change_order', t, 'delay_reason')).toBe(
      '[delay.reasons.customerChangeOrder]',
    )
    expect(groupLabel('material_supplier_delay', t, 'delay_reason')).toBe(
      '[delay.reasons.materialSupplierDelay]',
    )
    expect(groupLabel('force_majeure', t, 'delay_reason')).toBe('[delay.reasons.forceMajeure]')
    expect(groupLabel('upstream_hold', t, 'delay_reason')).toBe('[delay.reasons.upstreamHold]')
    expect(groupLabel('other', t, 'delay_reason')).toBe('[delay.reasons.other]')
  })

  it('still localizes the "none" sentinel when grouped by delay_reason (on-time orders)', () => {
    expect(groupLabel('none', t, 'delay_reason')).toBe('[pivot.sentinels.none]')
  })

  it('passes through an unknown value as-is even when grouped by delay_reason', () => {
    expect(groupLabel('some_future_reason', t, 'delay_reason')).toBe('some_future_reason')
  })
})
