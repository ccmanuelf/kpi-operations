import { describe, it, expect } from 'vitest'
import {
  useAgGridExcelBehaviors,
  DEFAULT_EXCEL_BEHAVIOR_FLAGS,
} from '../agGridExcelBehaviors'

describe('agGridExcelBehaviors', () => {
  it('emits the keyboard-nav grid option and an all-enabled registry by default', () => {
    const { gridOptions, registry } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    expect(typeof gridOptions.navigateToNextCell).toBe('function')
    expect(registry.length).toBeGreaterThanOrEqual(5)
    expect(registry.every((e) => e.enabled)).toBe(true)
    // every entry carries the metadata the docs need
    for (const e of registry) {
      expect(e.excelFeature).toBeTruthy()
      expect(e.communityMechanism).toBeTruthy()
      expect(e.enterpriseEquivalent).toBeTruthy()
    }
  })

  it('master:false removes every shim (empty fragment, registry all disabled)', () => {
    const { gridOptions, registry } = useAgGridExcelBehaviors({
      ...DEFAULT_EXCEL_BEHAVIOR_FLAGS,
      master: false,
    })
    expect(gridOptions.navigateToNextCell).toBeUndefined()
    expect(Object.keys(gridOptions)).toHaveLength(0)
    expect(registry.every((e) => !e.enabled)).toBe(true)
  })

  it('a single per-feature flag off disables only that behavior', () => {
    const { gridOptions, registry } = useAgGridExcelBehaviors({
      ...DEFAULT_EXCEL_BEHAVIOR_FLAGS,
      keyboardNav: false,
    })
    expect(gridOptions.navigateToNextCell).toBeUndefined()
    expect(registry.find((e) => e.key === 'excelPaste')?.enabled).toBe(true)
    expect(registry.find((e) => e.key === 'keyboardNav')?.enabled).toBe(false)
  })

  it('keyboard nav is Excel-style: Enter (13) moves down, Tab (9) keeps suggested', () => {
    const { gridOptions } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    const nav = gridOptions.navigateToNextCell as (_p: unknown) => unknown
    const suggested = { rowIndex: 5, column: 'X' }
    const prev = { rowIndex: 5, column: 'COL' }
    expect(nav({ key: 13, nextCellPosition: suggested, previousCellPosition: prev }))
      .toEqual({ rowIndex: 6, column: 'COL' })
    expect(nav({ key: 9, nextCellPosition: suggested, previousCellPosition: prev }))
      .toBe(suggested)
  })
})
