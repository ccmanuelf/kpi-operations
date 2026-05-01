/**
 * Unit tests for useQualityGridData composable.
 * Covers calculation logic (FPY, PPM, units_passed), aggregate stats,
 * initial state, and column definition shape against the canonical
 * backend Pydantic schema (backend/schemas/quality.py).
 *
 * Migrated from the legacy form-only spec at
 * frontend/src/components/__tests__/QualityEntry.spec.ts (deleted in
 * the same change that re-routed /data-entry/quality to the AG Grid
 * surface).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getQualityEntries: vi.fn().mockResolvedValue({ data: [] }),
    createQualityEntry: vi.fn().mockResolvedValue({ data: {} }),
    updateQualityEntry: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ user: { client_id_assigned: 'CLIENT1' } }),
}))

vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => ({ selectedClient: null }),
}))

import useQualityGridData, { type QualityRow } from '../useQualityGridData'

interface ColumnDef {
  field: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: string[]; min?: number; precision?: number }
  cellEditorPopup?: boolean
  valueGetter?: (params: { data: Partial<QualityRow> }) => string | number
}

const findCol = (cols: unknown[], field: string): ColumnDef | undefined =>
  (cols as ColumnDef[]).find((c) => c.field === field)

describe('useQualityGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('FPY column valueGetter', () => {
    it('returns 0 when units_inspected is 0', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'fpy')!
      expect(col.valueGetter!({ data: { units_inspected: 0, units_defective: 5 } })).toBe(0)
    })

    it('returns 100.00 with no defects', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'fpy')!
      expect(col.valueGetter!({ data: { units_inspected: 100, units_defective: 0 } })).toBe('100.00')
    })

    it('calculates correct FPY percentage', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'fpy')!
      expect(col.valueGetter!({ data: { units_inspected: 100, units_defective: 5 } })).toBe('95.00')
    })

    it('handles decimal results', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'fpy')!
      expect(col.valueGetter!({ data: { units_inspected: 100, units_defective: 3 } })).toBe('97.00')
    })
  })

  describe('PPM column valueGetter', () => {
    it('returns 0 when units_inspected is 0', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'ppm')!
      expect(col.valueGetter!({ data: { units_inspected: 0, units_defective: 5 } })).toBe(0)
    })

    it('returns 0 with no defects', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'ppm')!
      expect(col.valueGetter!({ data: { units_inspected: 1000, units_defective: 0 } })).toBe(0)
    })

    it('calculates correct PPM', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'ppm')!
      expect(col.valueGetter!({ data: { units_inspected: 1000, units_defective: 5 } })).toBe(5000)
    })

    it('rounds PPM to integer', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'ppm')!
      expect(col.valueGetter!({ data: { units_inspected: 300, units_defective: 1 } })).toBe(3333)
    })
  })

  describe('units_passed column valueGetter', () => {
    it('computes inspected minus defective', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'units_passed')!
      expect(col.valueGetter!({ data: { units_inspected: 100, units_defective: 10 } })).toBe(90)
    })

    it('returns inspected when no defects', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'units_passed')!
      expect(col.valueGetter!({ data: { units_inspected: 100, units_defective: 0 } })).toBe(100)
    })

    it('handles undefined values', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'units_passed')!
      expect(col.valueGetter!({ data: {} })).toBe(0)
    })

    it('clamps negative result to 0', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'units_passed')!
      expect(col.valueGetter!({ data: { units_inspected: 5, units_defective: 10 } })).toBe(0)
    })
  })

  describe('aggregated stats', () => {
    it('totalInspected sums units_inspected across rows', () => {
      const { qualityData, totalInspected } = useQualityGridData()
      qualityData.value = [
        { units_inspected: 100 } as QualityRow,
        { units_inspected: 50 } as QualityRow,
        { units_inspected: 25 } as QualityRow,
      ]
      expect(totalInspected.value).toBe(175)
    })

    it('totalDefects sums units_defective across rows', () => {
      const { qualityData, totalDefects } = useQualityGridData()
      qualityData.value = [
        { units_defective: 5 } as QualityRow,
        { units_defective: 10 } as QualityRow,
      ]
      expect(totalDefects.value).toBe(15)
    })

    it('avgFPY returns 0 when no inspections', () => {
      const { avgFPY } = useQualityGridData()
      expect(avgFPY.value).toBe(0)
    })

    it('avgFPY computes correct percentage', () => {
      const { qualityData, avgFPY } = useQualityGridData()
      qualityData.value = [{ units_inspected: 100, units_defective: 5 } as QualityRow]
      expect(avgFPY.value).toBe(95)
    })

    it('avgPPM returns 0 when no inspections', () => {
      const { avgPPM } = useQualityGridData()
      expect(avgPPM.value).toBe(0)
    })

    it('avgPPM computes correct PPM', () => {
      const { qualityData, avgPPM } = useQualityGridData()
      qualityData.value = [{ units_inspected: 1000, units_defective: 5 } as QualityRow]
      expect(avgPPM.value).toBe(5000)
    })
  })

  describe('initial state', () => {
    it('initialises with empty quality data', () => {
      const { qualityData } = useQualityGridData()
      expect(qualityData.value).toEqual([])
    })

    it('initialises hasChanges to false', () => {
      const { hasChanges } = useQualityGridData()
      expect(hasChanges.value).toBe(false)
    })

    it('initialises changedRowsCount to 0', () => {
      const { changedRowsCount } = useQualityGridData()
      expect(changedRowsCount.value).toBe(0)
    })
  })

  describe('column definitions match backend schema', () => {
    it('exposes shift_date column with date editor', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'shift_date')!
      expect(col.cellEditor).toBe('agDateStringCellEditor')
      expect(col.editable).toBe(true)
    })

    it('exposes units_inspected column with numeric editor and min:1', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'units_inspected')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 1, precision: 0 })
    })

    it('exposes units_defective column with numeric editor', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'units_defective')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
    })

    it('exposes total_defects_count column', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'total_defects_count')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
    })

    it('exposes inspection_stage column with select editor', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'inspection_stage')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual(['Incoming', 'In-Process', 'Final'])
    })

    it('exposes notes column with large text editor', () => {
      const { columnDefs } = useQualityGridData()
      const col = findCol(columnDefs.value, 'notes')!
      expect(col.cellEditor).toBe('agLargeTextCellEditor')
      expect(col.cellEditorPopup).toBe(true)
    })

    it('does NOT expose product_id (not in backend QualityEntry)', () => {
      const { columnDefs } = useQualityGridData()
      expect(findCol(columnDefs.value, 'product_id')).toBeUndefined()
    })

    it('does NOT expose severity (vestigial UI-only)', () => {
      const { columnDefs } = useQualityGridData()
      expect(findCol(columnDefs.value, 'severity')).toBeUndefined()
    })

    it('does NOT expose disposition (vestigial UI-only)', () => {
      const { columnDefs } = useQualityGridData()
      expect(findCol(columnDefs.value, 'disposition')).toBeUndefined()
    })

    it('does NOT expose defect_type_id (separate defect_details table)', () => {
      const { columnDefs } = useQualityGridData()
      expect(findCol(columnDefs.value, 'defect_type_id')).toBeUndefined()
    })
  })
})
