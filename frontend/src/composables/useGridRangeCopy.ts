// Flag-gated multi-cell range selection + TSV copy for AG Grid Community
// (range selection is Enterprise-only). Built on public AG APIs + events; no
// DOM mouse tracking. Owned by agGridExcelBehaviors via the `rangeCopy` flag.
// Enterprise: native cell selection / range copy — disable this when present.
// See docs/frontend/ag-grid-excel-behaviors.md.
import { ref, computed, type Ref } from 'vue'

export interface CellPos {
  rowIndex: number
  colId: string
}
export interface RangeRect {
  rowStart: number
  rowEnd: number
  colIds: string[]
}

export function rectFrom(anchor: CellPos, focus: CellPos, colOrder: string[]): RangeRect {
  const rowStart = Math.min(anchor.rowIndex, focus.rowIndex)
  const rowEnd = Math.max(anchor.rowIndex, focus.rowIndex)
  const ai = colOrder.indexOf(anchor.colId)
  const fi = colOrder.indexOf(focus.colId)
  const lo = Math.max(0, Math.min(ai, fi))
  const hi = Math.max(ai, fi)
  return { rowStart, rowEnd, colIds: colOrder.slice(lo, hi + 1) }
}

export function isInRange(rowIndex: number, colId: string, rect: RangeRect | null): boolean {
  if (!rect) return false
  return rowIndex >= rect.rowStart && rowIndex <= rect.rowEnd && rect.colIds.includes(colId)
}

export function buildTsv(
  rect: RangeRect,
  getValue: (_rowIndex: number, _colId: string) => unknown,
): string {
  const rows: string[] = []
  for (let r = rect.rowStart; r <= rect.rowEnd; r++) {
    rows.push(
      rect.colIds
        .map((c) => {
          const v = getValue(r, c)
          return v == null ? '' : String(v)
        })
        .join('\t'),
    )
  }
  return rows.join('\n')
}

interface GridApiLike {
  getColumnState?: () => { colId: string }[]
  getDisplayedRowAtIndex?: (_i: number) => unknown
  getCellValue?: (_p: { rowNode: unknown; colKey: string; useFormatter?: boolean }) => unknown
  refreshCells?: (_p?: { force?: boolean }) => void
}
interface ClickedCell {
  rowIndex: number
  column: { getColId: () => string }
  event?: MouseEvent
}

export function useGridRangeCopy(opts: { gridApi: Ref<GridApiLike | null>; enabled: Ref<boolean> }) {
  const anchor = ref<CellPos | null>(null)
  const focus = ref<CellPos | null>(null)

  const colOrder = (): string[] =>
    (opts.gridApi.value?.getColumnState?.() ?? []).map((c) => c.colId)

  const rect = computed<RangeRect | null>(() =>
    anchor.value && focus.value ? rectFrom(anchor.value, focus.value, colOrder()) : null,
  )
  const isMultiCell = computed(() => {
    const r = rect.value
    return !!r && (r.rowStart !== r.rowEnd || r.colIds.length > 1)
  })

  const refresh = (): void => opts.gridApi.value?.refreshCells?.({ force: true })

  const rangeCellClassRules = {
    'range-shim-selected': (p: { rowIndex: number; column: { getColId: () => string } }) =>
      opts.enabled.value && isInRange(p.rowIndex, p.column.getColId(), rect.value),
  }

  const onCellClicked = (e: ClickedCell): void => {
    if (!opts.enabled.value) return
    const pos = { rowIndex: e.rowIndex, colId: e.column.getColId() }
    if (e.event?.shiftKey && anchor.value) {
      focus.value = pos
    } else {
      anchor.value = pos
      focus.value = pos
    }
    refresh()
  }

  const getValue = (rowIndex: number, colId: string): unknown => {
    const api = opts.gridApi.value
    const node = api?.getDisplayedRowAtIndex?.(rowIndex)
    // AG Grid 35 renamed getValue -> getCellValue; useFormatter copies the
    // displayed value (Excel-copy parity).
    return node ? api?.getCellValue?.({ rowNode: node, colKey: colId, useFormatter: true }) : undefined
  }

  const copyRange = async (): Promise<boolean> => {
    if (!opts.enabled.value || !isMultiCell.value || !rect.value) return false
    await navigator.clipboard.writeText(buildTsv(rect.value, getValue))
    return true
  }

  const extend = (dRow: number, dCol: number): void => {
    if (!focus.value) return
    const order = colOrder()
    const ci = order.indexOf(focus.value.colId)
    const nextCi = Math.max(0, Math.min(order.length - 1, ci + dCol))
    focus.value = {
      rowIndex: Math.max(0, focus.value.rowIndex + dRow),
      colId: order[nextCi] ?? focus.value.colId,
    }
    refresh()
  }

  const ARROWS: Record<string, [number, number]> = {
    ArrowUp: [-1, 0],
    ArrowDown: [1, 0],
    ArrowLeft: [0, -1],
    ArrowRight: [0, 1],
  }

  const onKeyDown = (e: KeyboardEvent): void => {
    if (!opts.enabled.value) return
    if (e.shiftKey && e.key in ARROWS) {
      if (!anchor.value) return
      e.preventDefault()
      const [dr, dc] = ARROWS[e.key]
      extend(dr, dc)
    } else if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C') && isMultiCell.value) {
      e.preventDefault()
      void copyRange()
    }
  }

  const clear = (): void => {
    anchor.value = null
    focus.value = null
    refresh()
  }

  return { rect, isMultiCell, rangeCellClassRules, onCellClicked, onKeyDown, copyRange, clear }
}
