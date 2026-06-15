import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { rectFrom, isInRange, buildTsv, useGridRangeCopy } from '../useGridRangeCopy'

const COLS = ['a', 'b', 'c', 'd']

describe('useGridRangeCopy pure helpers', () => {
  it('rectFrom normalizes any anchor/focus into a rectangle (col order aware)', () => {
    expect(rectFrom({ rowIndex: 4, colId: 'c' }, { rowIndex: 1, colId: 'a' }, COLS))
      .toEqual({ rowStart: 1, rowEnd: 4, colIds: ['a', 'b', 'c'] })
    expect(rectFrom({ rowIndex: 2, colId: 'b' }, { rowIndex: 2, colId: 'b' }, COLS))
      .toEqual({ rowStart: 2, rowEnd: 2, colIds: ['b'] })
  })

  it('isInRange is true only inside the rectangle', () => {
    const rect = { rowStart: 1, rowEnd: 3, colIds: ['b', 'c'] }
    expect(isInRange(2, 'b', rect)).toBe(true)
    expect(isInRange(0, 'b', rect)).toBe(false)
    expect(isInRange(2, 'a', rect)).toBe(false)
    expect(isInRange(2, 'b', null)).toBe(false)
  })

  it('buildTsv emits tab/newline separated values via the getter', () => {
    const rect = { rowStart: 0, rowEnd: 1, colIds: ['a', 'b'] }
    const getValue = (r: number, c: string) => `${r}${c}`
    expect(buildTsv(rect, getValue)).toBe('0a\t0b\n1a\t1b')
    const withBlank = (r: number, c: string) => (r === 1 && c === 'b' ? null : `${r}${c}`)
    expect(buildTsv(rect, withBlank)).toBe('0a\t0b\n1a\t')
  })
})

describe('useGridRangeCopy composable', () => {
  const colState = COLS.map((colId) => ({ colId }))
  const makeApi = () => ({
    getColumnState: () => colState,
    getDisplayedRowAtIndex: (i: number) => ({ i }),
    getValue: (colId: string, node: { i: number }) => `${node.i}:${colId}`,
    refreshCells: () => {},
  })

  it('shift+click extends the range and reports multi-cell', () => {
    const api = ref(makeApi())
    const rc = useGridRangeCopy({ gridApi: api as never, enabled: ref(true) })
    rc.onCellClicked({ rowIndex: 1, column: { getColId: () => 'a' } })
    rc.onCellClicked({ rowIndex: 3, column: { getColId: () => 'c' }, event: { shiftKey: true } as MouseEvent })
    expect(rc.isMultiCell.value).toBe(true)
    expect(rc.rect.value).toEqual({ rowStart: 1, rowEnd: 3, colIds: ['a', 'b', 'c'] })
  })

  it('does nothing when disabled', () => {
    const api = ref(makeApi())
    const rc = useGridRangeCopy({ gridApi: api as never, enabled: ref(false) })
    rc.onCellClicked({ rowIndex: 1, column: { getColId: () => 'a' } })
    expect(rc.rect.value).toBeNull()
    expect(rc.rangeCellClassRules['range-shim-selected']({ rowIndex: 1, column: { getColId: () => 'a' } })).toBe(false)
  })
})
