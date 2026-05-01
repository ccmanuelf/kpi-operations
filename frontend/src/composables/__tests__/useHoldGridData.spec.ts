/**
 * Unit tests for useHoldGridData composable.
 * Covers column definitions (alignment to backend WIPHoldResponse schema),
 * HOLD_REASON_CODES catalog, filters (date/status/reason), aggregate
 * counts (active/resumed/pending), avgDaysOnHold calculation.
 *
 * Migrated from the legacy form-only spec at
 * frontend/src/components/__tests__/HoldResumeEntry.spec.ts (deleted in
 * the same change that re-routed /data-entry/hold-resume to the AG Grid
 * surface).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { storeState } = vi.hoisted(() => ({
  storeState: {
    holdEntries: [] as unknown[],
    workOrders: [] as unknown[],
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/stores/productionDataStore', () => ({
  useProductionDataStore: () => ({
    holdEntries: storeState.holdEntries,
    workOrders: storeState.workOrders,
  }),
}))

import {
  useHoldGridData,
  HOLD_REASON_CODES,
  type HoldEntry,
} from '../useHoldGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: unknown[] } | (() => { values?: unknown[] })
  valueGetter?: (params: { data: HoldEntry }) => unknown
  cellClass?: string | ((params: { data: HoldEntry; value?: unknown }) => string)
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

describe('useHoldGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeState.holdEntries = []
    storeState.workOrders = []
    vi.clearAllMocks()
  })

  describe('HOLD_REASON_CODES catalog', () => {
    it('contains canonical backend catalog codes', () => {
      expect(HOLD_REASON_CODES).toContain('QUALITY_ISSUE')
      expect(HOLD_REASON_CODES).toContain('MATERIAL_INSPECTION')
      expect(HOLD_REASON_CODES).toContain('ENGINEERING_REVIEW')
      expect(HOLD_REASON_CODES).toContain('CUSTOMER_REQUEST')
      expect(HOLD_REASON_CODES).toContain('MISSING_SPECIFICATION')
      expect(HOLD_REASON_CODES).toContain('EQUIPMENT_UNAVAILABLE')
      expect(HOLD_REASON_CODES).toContain('CAPACITY_CONSTRAINT')
      expect(HOLD_REASON_CODES).toContain('OTHER')
    })

    it('has exactly 8 catalog codes', () => {
      expect(HOLD_REASON_CODES).toHaveLength(8)
    })

    it('does NOT contain legacy UI labels', () => {
      expect(HOLD_REASON_CODES).not.toContain('Quality Issue')
      expect(HOLD_REASON_CODES).not.toContain('Material Defect')
      expect(HOLD_REASON_CODES).not.toContain('Process Non-Conformance')
    })
  })

  describe('column definitions match backend schema', () => {
    it('exposes hold_date column (not legacy placed_on_hold_date)', () => {
      const { columnDefs } = useHoldGridData()
      expect(findCol(columnDefs.value, 'hold_date')).toBeDefined()
      expect(findCol(columnDefs.value, 'placed_on_hold_date')).toBeUndefined()
    })

    it('exposes expected_resolution_date column (not legacy expected_resume_date)', () => {
      const { columnDefs } = useHoldGridData()
      expect(findCol(columnDefs.value, 'expected_resolution_date')).toBeDefined()
      expect(findCol(columnDefs.value, 'expected_resume_date')).toBeUndefined()
    })

    it('exposes resume_date column (not legacy actual_resume_date)', () => {
      const { columnDefs } = useHoldGridData()
      expect(findCol(columnDefs.value, 'resume_date')).toBeDefined()
      expect(findCol(columnDefs.value, 'actual_resume_date')).toBeUndefined()
    })

    it('exposes resumed_by column (not legacy resumed_by_user_id)', () => {
      const { columnDefs } = useHoldGridData()
      expect(findCol(columnDefs.value, 'resumed_by')).toBeDefined()
      expect(findCol(columnDefs.value, 'resumed_by_user_id')).toBeUndefined()
    })

    it('exposes hold_initiated_by column', () => {
      const { columnDefs } = useHoldGridData()
      expect(findCol(columnDefs.value, 'hold_initiated_by')).toBeDefined()
    })

    it('exposes hold_approved_by column', () => {
      const { columnDefs } = useHoldGridData()
      expect(findCol(columnDefs.value, 'hold_approved_by')).toBeDefined()
    })

    it('does NOT expose hold_approved_at (vestigial timestamp not in backend)', () => {
      const { columnDefs } = useHoldGridData()
      expect(findCol(columnDefs.value, 'hold_approved_at')).toBeUndefined()
    })

    it('does NOT expose resume_approved_at (vestigial timestamp not in backend)', () => {
      const { columnDefs } = useHoldGridData()
      expect(findCol(columnDefs.value, 'resume_approved_at')).toBeUndefined()
    })

    it('exposes hold_reason column with select editor over catalog codes', () => {
      const { columnDefs } = useHoldGridData()
      const col = findCol(columnDefs.value, 'hold_reason')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      const params = col.cellEditorParams as { values?: unknown[] } | undefined
      expect(params?.values).toEqual(HOLD_REASON_CODES)
    })

    it('exposes hold_reason_description column with large text editor', () => {
      const { columnDefs } = useHoldGridData()
      const col = findCol(columnDefs.value, 'hold_reason_description')!
      expect(col.cellEditor).toBe('agLargeTextCellEditor')
    })

    it('exposes hold_status column (read-only, server-controlled)', () => {
      const { columnDefs } = useHoldGridData()
      const col = findCol(columnDefs.value, 'hold_status')!
      expect(col.editable).toBe(false)
    })

    it('exposes notes column with large text editor', () => {
      const { columnDefs } = useHoldGridData()
      const col = findCol(columnDefs.value, 'notes')!
      expect(col.cellEditor).toBe('agLargeTextCellEditor')
    })
  })

  describe('days_on_hold column valueGetter', () => {
    it('returns 0 when hold_date is missing', () => {
      const { columnDefs } = useHoldGridData()
      const col = findCol(columnDefs.value, 'days_on_hold')!
      expect(col.valueGetter!({ data: {} })).toBe(0)
    })

    it('computes days from hold_date to today when not resumed', () => {
      const { columnDefs } = useHoldGridData()
      const col = findCol(columnDefs.value, 'days_on_hold')!
      const fiveDaysAgo = new Date()
      fiveDaysAgo.setDate(fiveDaysAgo.getDate() - 5)
      const days = col.valueGetter!({
        data: { hold_date: fiveDaysAgo.toISOString().slice(0, 10) },
      }) as number
      expect(days).toBeGreaterThanOrEqual(4)
      expect(days).toBeLessThanOrEqual(6)
    })

    it('computes days from hold_date to resume_date when resumed', () => {
      const { columnDefs } = useHoldGridData()
      const col = findCol(columnDefs.value, 'days_on_hold')!
      const days = col.valueGetter!({
        data: {
          hold_date: '2026-01-01',
          resume_date: '2026-01-08',
        },
      }) as number
      expect(days).toBe(7)
    })
  })

  describe('aggregate counts', () => {
    it('activeCount sums entries with hold_status ON_HOLD', () => {
      storeState.holdEntries = [
        { hold_status: 'ON_HOLD' },
        { hold_status: 'ON_HOLD' },
        { hold_status: 'RESUMED' },
      ]
      const { activeCount } = useHoldGridData()
      expect(activeCount.value).toBe(2)
    })

    it('resumedCount sums entries with hold_status RESUMED or with resume_date', () => {
      storeState.holdEntries = [
        { hold_status: 'RESUMED' },
        { hold_status: 'ON_HOLD', resume_date: '2026-04-30' },
        { hold_status: 'ON_HOLD' },
      ]
      const { resumedCount } = useHoldGridData()
      expect(resumedCount.value).toBe(2)
    })

    it('pendingHoldApprovalsCount sums PENDING_HOLD_APPROVAL entries', () => {
      storeState.holdEntries = [
        { hold_status: 'PENDING_HOLD_APPROVAL' },
        { hold_status: 'PENDING_HOLD_APPROVAL' },
        { hold_status: 'ON_HOLD' },
      ]
      const { pendingHoldApprovalsCount } = useHoldGridData()
      expect(pendingHoldApprovalsCount.value).toBe(2)
    })

    it('pendingResumeApprovalsCount sums PENDING_RESUME_APPROVAL entries', () => {
      storeState.holdEntries = [
        { hold_status: 'PENDING_RESUME_APPROVAL' },
        { hold_status: 'ON_HOLD' },
      ]
      const { pendingResumeApprovalsCount } = useHoldGridData()
      expect(pendingResumeApprovalsCount.value).toBe(1)
    })

    it('pendingApprovalsCount sums hold + resume pending approvals', () => {
      storeState.holdEntries = [
        { hold_status: 'PENDING_HOLD_APPROVAL' },
        { hold_status: 'PENDING_RESUME_APPROVAL' },
        { hold_status: 'PENDING_RESUME_APPROVAL' },
        { hold_status: 'ON_HOLD' },
      ]
      const { pendingApprovalsCount } = useHoldGridData()
      expect(pendingApprovalsCount.value).toBe(3)
    })
  })

  describe('avgDaysOnHold', () => {
    it('returns 0 when no entries', () => {
      const { avgDaysOnHold } = useHoldGridData()
      expect(avgDaysOnHold.value).toBe(0)
    })

    it('averages days across filtered entries', () => {
      storeState.holdEntries = [
        { hold_date: '2026-01-01', resume_date: '2026-01-04' }, // 3 days
        { hold_date: '2026-01-01', resume_date: '2026-01-11' }, // 10 days
      ]
      const { avgDaysOnHold, applyFilters } = useHoldGridData()
      applyFilters()
      expect(avgDaysOnHold.value).toBe(6.5)
    })
  })

  describe('applyFilters', () => {
    it('filters by reason', () => {
      storeState.holdEntries = [
        { hold_reason: 'QUALITY_ISSUE', hold_date: '2026-01-01' },
        { hold_reason: 'OTHER', hold_date: '2026-01-02' },
      ]
      const { reasonFilter, filteredEntries, applyFilters } = useHoldGridData()
      reasonFilter.value = 'QUALITY_ISSUE'
      applyFilters()
      expect(filteredEntries.value).toHaveLength(1)
    })

    it('filters by hold_date (not legacy placed_on_hold_date)', () => {
      storeState.holdEntries = [
        { hold_date: '2026-04-30T00:00:00' },
        { hold_date: '2026-04-29T00:00:00' },
      ]
      const { dateFilter, filteredEntries, applyFilters } = useHoldGridData()
      dateFilter.value = '2026-04-30'
      applyFilters()
      expect(filteredEntries.value).toHaveLength(1)
    })

    it('filters ON_HOLD by status', () => {
      storeState.holdEntries = [
        { hold_status: 'ON_HOLD', hold_date: '2026-01-01' },
        { hold_status: 'RESUMED', hold_date: '2026-01-02' },
      ]
      const { statusFilter, filteredEntries, applyFilters } = useHoldGridData()
      statusFilter.value = 'ON_HOLD'
      applyFilters()
      expect(filteredEntries.value).toHaveLength(1)
    })
  })

  describe('initial state', () => {
    it('initialises unsavedChanges as empty Set', () => {
      const { unsavedChanges } = useHoldGridData()
      expect(unsavedChanges.value.size).toBe(0)
    })

    it('initialises hasUnsavedChanges to false', () => {
      const { hasUnsavedChanges } = useHoldGridData()
      expect(hasUnsavedChanges.value).toBe(false)
    })

    it('exposes holdReasons === HOLD_REASON_CODES', () => {
      const { holdReasons } = useHoldGridData()
      expect(holdReasons).toBe(HOLD_REASON_CODES)
    })
  })
})
