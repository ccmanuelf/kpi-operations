import { describe, it, expect } from 'vitest'
import {
  emptyAllocationRow,
  addAllocationRow,
  removeAllocationRow,
  allocatedTotal,
  hasDuplicateCategories,
  hasInvalidHours,
  exceedsActualHours,
  validateAllocations,
  allocationSummary,
  toAllocationItems,
  allocationRowsFromItems,
  type AllocationRow,
} from '../useAllocationEditor'

describe('row add/remove', () => {
  it('addAllocationRow appends a blank row without mutating the input', () => {
    const rows: AllocationRow[] = [{ category: 'training', hours: 1 }]
    const next = addAllocationRow(rows)
    expect(next).toHaveLength(2)
    expect(next[1]).toEqual(emptyAllocationRow())
    expect(rows).toHaveLength(1)
  })

  it('removeAllocationRow drops the row at the given index', () => {
    const rows: AllocationRow[] = [
      { category: 'training', hours: 1 },
      { category: 'meeting', hours: 2 },
    ]
    const next = removeAllocationRow(rows, 0)
    expect(next).toEqual([{ category: 'meeting', hours: 2 }])
  })
})

describe('allocatedTotal', () => {
  it('sums only complete rows (category + positive hours)', () => {
    const rows: AllocationRow[] = [
      { category: 'billed_production', hours: 5 },
      { category: 'training', hours: 1 },
      { category: null, hours: 3 },
      { category: 'meeting', hours: null },
    ]
    expect(allocatedTotal(rows)).toBe(6)
  })

  it('returns 0 for an empty list', () => {
    expect(allocatedTotal([])).toBe(0)
  })
})

describe('duplicate-category detection (mirrors backend validate_allocations)', () => {
  it('blocked: same category twice', () => {
    const rows: AllocationRow[] = [
      { category: 'training', hours: 1 },
      { category: 'training', hours: 2 },
    ]
    expect(hasDuplicateCategories(rows)).toBe(true)
  })

  it('allowed: distinct categories', () => {
    const rows: AllocationRow[] = [
      { category: 'training', hours: 1 },
      { category: 'meeting', hours: 2 },
    ]
    expect(hasDuplicateCategories(rows)).toBe(false)
  })

  it('blank category rows never count as duplicates of each other', () => {
    const rows: AllocationRow[] = [
      { category: null, hours: null },
      { category: null, hours: null },
    ]
    expect(hasDuplicateCategories(rows)).toBe(false)
  })
})

describe('invalid-hours detection (mirrors backend hours <= 0 rejection)', () => {
  it('flags a chosen category with zero hours', () => {
    expect(hasInvalidHours([{ category: 'training', hours: 0 }])).toBe(true)
  })

  it('flags a chosen category with negative hours', () => {
    expect(hasInvalidHours([{ category: 'training', hours: -1 }])).toBe(true)
  })

  it('flags a chosen category with null hours', () => {
    expect(hasInvalidHours([{ category: 'training', hours: null }])).toBe(true)
  })

  it('does not flag a fully-blank trailing row', () => {
    expect(hasInvalidHours([{ category: null, hours: null }])).toBe(false)
  })

  it('does not flag a complete row', () => {
    expect(hasInvalidHours([{ category: 'training', hours: 1 }])).toBe(false)
  })
})

describe('over-sum detection (mirrors backend total > actual_hours rejection)', () => {
  it('blocked: allocated total exceeds actual_hours', () => {
    const rows: AllocationRow[] = [{ category: 'billed_production', hours: 9 }]
    expect(exceedsActualHours(rows, 8)).toBe(true)
  })

  it('allowed: allocated total under actual_hours (unallocated remainder OK)', () => {
    const rows: AllocationRow[] = [{ category: 'billed_production', hours: 5 }]
    expect(exceedsActualHours(rows, 8)).toBe(false)
  })

  it('allowed: allocated total exactly equals actual_hours', () => {
    const rows: AllocationRow[] = [{ category: 'billed_production', hours: 8 }]
    expect(exceedsActualHours(rows, 8)).toBe(false)
  })

  it('treats missing actual_hours as 0', () => {
    const rows: AllocationRow[] = [{ category: 'billed_production', hours: 1 }]
    expect(exceedsActualHours(rows, null)).toBe(true)
    expect(exceedsActualHours(rows, undefined)).toBe(true)
  })
})

describe('validateAllocations truth table', () => {
  it('valid: distinct categories, positive hours, within actual_hours', () => {
    const rows: AllocationRow[] = [
      { category: 'billed_production', hours: 5 },
      { category: 'training', hours: 1 },
    ]
    expect(validateAllocations(rows, 8)).toEqual({
      valid: true,
      duplicateCategory: false,
      invalidHours: false,
      exceedsActual: false,
    })
  })

  it('invalid: duplicate category blocks save', () => {
    const rows: AllocationRow[] = [
      { category: 'training', hours: 1 },
      { category: 'training', hours: 2 },
    ]
    const result = validateAllocations(rows, 8)
    expect(result.valid).toBe(false)
    expect(result.duplicateCategory).toBe(true)
  })

  it('invalid: over-sum blocks save', () => {
    const rows: AllocationRow[] = [{ category: 'billed_production', hours: 10 }]
    const result = validateAllocations(rows, 8)
    expect(result.valid).toBe(false)
    expect(result.exceedsActual).toBe(true)
  })

  it('invalid: zero-hours row blocks save', () => {
    const rows: AllocationRow[] = [{ category: 'training', hours: 0 }]
    const result = validateAllocations(rows, 8)
    expect(result.valid).toBe(false)
    expect(result.invalidHours).toBe(true)
  })

  it('valid: empty rows list', () => {
    expect(validateAllocations([], 8).valid).toBe(true)
  })
})

describe('allocationSummary', () => {
  it('returns allocated and actual for the {allocated}/{actual}h template', () => {
    const rows: AllocationRow[] = [
      { category: 'billed_production', hours: 5 },
      { category: 'training', hours: 1 },
    ]
    expect(allocationSummary(rows, 8)).toEqual({ allocated: 6, actual: 8 })
  })

  it('defaults actual to 0 when missing', () => {
    expect(allocationSummary([], undefined)).toEqual({ allocated: 0, actual: 0 })
  })
})

describe('toAllocationItems / allocationRowsFromItems round trip', () => {
  it('toAllocationItems drops incomplete rows and strips row-editor shape', () => {
    const rows: AllocationRow[] = [
      { category: 'billed_production', hours: 5 },
      { category: null, hours: null },
      { category: 'meeting', hours: 0 },
    ]
    expect(toAllocationItems(rows)).toEqual([{ category: 'billed_production', hours: 5 }])
  })

  it('allocationRowsFromItems seeds one blank row when there is nothing saved', () => {
    expect(allocationRowsFromItems(undefined)).toEqual([emptyAllocationRow()])
    expect(allocationRowsFromItems(null)).toEqual([emptyAllocationRow()])
    expect(allocationRowsFromItems([])).toEqual([emptyAllocationRow()])
  })

  it('allocationRowsFromItems maps saved items back to editable rows', () => {
    expect(allocationRowsFromItems([{ category: 'training', hours: 2 }])).toEqual([
      { category: 'training', hours: 2 },
    ])
  })

  it('round-trips through toAllocationItems -> allocationRowsFromItems', () => {
    const rows: AllocationRow[] = [{ category: 'billed_production', hours: 5 }]
    const items = toAllocationItems(rows)
    expect(allocationRowsFromItems(items)).toEqual(rows)
  })
})

describe('toAllocationItems rounds hours to 2 decimal places', () => {
  // The hours <input type="number"> has no browser-enforced precision, but storage
  // is Numeric(5,2) and the backend schema rejects >2dp payloads (decimal_places=2).
  // Rounding here on submit avoids a preventable 422 for imprecise typed/pasted input.
  it('rounds a 3dp value down', () => {
    expect(toAllocationItems([{ category: 'training', hours: 0.336 }])).toEqual([
      { category: 'training', hours: 0.34 },
    ])
  })

  it('rounds a 3dp value up', () => {
    expect(toAllocationItems([{ category: 'training', hours: 0.328 }])).toEqual([
      { category: 'training', hours: 0.33 },
    ])
  })

  it('leaves an already-2dp value unchanged', () => {
    expect(toAllocationItems([{ category: 'training', hours: 1.25 }])).toEqual([
      { category: 'training', hours: 1.25 },
    ])
  })

  it('leaves an integer value unchanged', () => {
    expect(toAllocationItems([{ category: 'training', hours: 3 }])).toEqual([
      { category: 'training', hours: 3 },
    ])
  })
})
