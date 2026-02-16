/**
 * Unit tests for Composables
 * Tests: useResponsive, useKeyboardShortcuts, useUnsavedChanges,
 *        useMobileGrid, useDashboardWidgets, useQRScanner
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'

// ---------- Mock setup for vue-router (useUnsavedChanges needs it) ----------
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn()
  }),
  onBeforeRouteLeave: vi.fn()
}))

// ---------- Mock axios (useDashboardWidgets needs it) ----------
const mockAxiosGet = vi.fn()
vi.mock('axios', () => ({
  default: {
    get: (...args) => mockAxiosGet(...args)
  }
}))

// ---------- Mock @/services/api (useQRScanner needs it) ----------
const mockLookupQR = vi.fn()
const mockGenerateQRImage = vi.fn()
vi.mock('@/services/api', () => ({
  default: {
    lookupQR: (...args) => mockLookupQR(...args),
    generateQRImage: (...args) => mockGenerateQRImage(...args)
  }
}))

// ============================================================
// useResponsive
// ============================================================
describe('useResponsive', () => {
  let useResponsive

  beforeEach(async () => {
    vi.clearAllMocks()
    const mod = await import('../useResponsive.js')
    useResponsive = mod.useResponsive
  })

  it('detects mobile breakpoint when width < 768', () => {
    Object.defineProperty(window, 'innerWidth', { value: 400, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { isMobile, isTablet, isDesktop, updateBreakpoints } = useResponsive()
    updateBreakpoints()

    expect(isMobile.value).toBe(true)
    expect(isTablet.value).toBe(false)
    expect(isDesktop.value).toBe(false)
  })

  it('detects tablet breakpoint when 768 <= width < 1024', () => {
    Object.defineProperty(window, 'innerWidth', { value: 800, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 600, writable: true, configurable: true })

    const { isMobile, isTablet, isDesktop, updateBreakpoints } = useResponsive()
    updateBreakpoints()

    expect(isMobile.value).toBe(false)
    expect(isTablet.value).toBe(true)
    expect(isDesktop.value).toBe(false) // 800 < 1024 (TABLET threshold)
  })

  it('detects desktop breakpoint when width >= 1024', () => {
    Object.defineProperty(window, 'innerWidth', { value: 1200, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { isMobile, isTablet, isDesktop, updateBreakpoints } = useResponsive()
    updateBreakpoints()

    expect(isMobile.value).toBe(false)
    expect(isTablet.value).toBe(false)
    expect(isDesktop.value).toBe(true)
  })

  it('returns correct breakpoint name via getCurrentBreakpoint', () => {
    Object.defineProperty(window, 'innerWidth', { value: 400, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { getCurrentBreakpoint, updateBreakpoints } = useResponsive()
    updateBreakpoints()

    expect(getCurrentBreakpoint()).toBe('mobile')
  })

  it('returns responsive grid height based on breakpoint', () => {
    Object.defineProperty(window, 'innerWidth', { value: 400, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { getGridHeight, updateBreakpoints } = useResponsive()
    updateBreakpoints()

    expect(getGridHeight()).toBe('400px')
  })

  it('adjusts column width for mobile', () => {
    Object.defineProperty(window, 'innerWidth', { value: 400, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { getColumnWidth, updateBreakpoints } = useResponsive()
    updateBreakpoints()

    // 150 * 0.7 = 105
    expect(getColumnWidth(150)).toBe(105)
  })

  it('returns desktop column width when on desktop', () => {
    Object.defineProperty(window, 'innerWidth', { value: 1200, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { getColumnWidth, updateBreakpoints } = useResponsive()
    updateBreakpoints()

    expect(getColumnWidth(150)).toBe(150)
  })

  it('shouldHideSidebar returns true on mobile/tablet', () => {
    Object.defineProperty(window, 'innerWidth', { value: 400, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { shouldHideSidebar, updateBreakpoints } = useResponsive()
    updateBreakpoints()

    expect(shouldHideSidebar()).toBe(true)
  })

  it('tracks screen dimensions', () => {
    Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 768, writable: true, configurable: true })

    const { screenWidth, screenHeight, updateBreakpoints } = useResponsive()
    updateBreakpoints()

    expect(screenWidth.value).toBe(1024)
    expect(screenHeight.value).toBe(768)
  })
})

// ============================================================
// useKeyboardShortcuts
// ============================================================
import { shallowMount, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'

describe('useKeyboardShortcuts', () => {
  // Helper: wraps the composable in a real component so onMounted fires
  const createShortcutWrapper = (setupFn) => {
    const TestComp = defineComponent({
      setup() {
        return setupFn()
      },
      template: '<div></div>'
    })
    return shallowMount(TestComp)
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('registers and triggers a shortcut', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut } = useKeyboardShortcuts()
      registerShortcut('ctrl+s', handler)
      return {}
    })

    const event = new KeyboardEvent('keydown', {
      key: 's',
      ctrlKey: true,
      bubbles: true
    })
    window.dispatchEvent(event)

    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('does not trigger shortcut for non-matching keys', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut } = useKeyboardShortcuts()
      registerShortcut('ctrl+s', handler)
      return {}
    })

    const event = new KeyboardEvent('keydown', {
      key: 'a',
      ctrlKey: true,
      bubbles: true
    })
    window.dispatchEvent(event)

    expect(handler).not.toHaveBeenCalled()
  })

  it('unregisters a shortcut', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut, unregisterShortcut } = useKeyboardShortcuts()
      registerShortcut('escape', handler)
      unregisterShortcut('escape')
      return {}
    })

    const event = new KeyboardEvent('keydown', {
      key: 'escape',
      bubbles: true
    })
    window.dispatchEvent(event)

    expect(handler).not.toHaveBeenCalled()
  })

  it('clears all shortcuts', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler1 = vi.fn()
    const handler2 = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut, clearShortcuts } = useKeyboardShortcuts()
      registerShortcut('ctrl+s', handler1)
      registerShortcut('escape', handler2)
      clearShortcuts()
      return {}
    })

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'escape', bubbles: true }))

    expect(handler1).not.toHaveBeenCalled()
    expect(handler2).not.toHaveBeenCalled()
  })

  it('prevents default when preventDefault option is true (default)', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut } = useKeyboardShortcuts()
      registerShortcut('ctrl+s', handler)
      return {}
    })

    const event = new KeyboardEvent('keydown', {
      key: 's',
      ctrlKey: true,
      bubbles: true,
      cancelable: true
    })
    const preventDefaultSpy = vi.spyOn(event, 'preventDefault')
    window.dispatchEvent(event)

    expect(preventDefaultSpy).toHaveBeenCalled()
  })
})

// ============================================================
// useUnsavedChanges
// ============================================================
describe('useUnsavedChanges', () => {
  let useUnsavedChanges

  beforeEach(async () => {
    vi.clearAllMocks()
    const mod = await import('../useUnsavedChanges.ts')
    useUnsavedChanges = mod.useUnsavedChanges
  })

  it('initializes with no unsaved changes', () => {
    const { hasUnsavedChanges } = useUnsavedChanges()
    expect(hasUnsavedChanges.value).toBe(false)
  })

  it('marks form as dirty', () => {
    const { hasUnsavedChanges, markDirty } = useUnsavedChanges()
    markDirty()
    expect(hasUnsavedChanges.value).toBe(true)
  })

  it('marks form as clean after save', () => {
    const { hasUnsavedChanges, markDirty, markClean } = useUnsavedChanges()
    markDirty()
    expect(hasUnsavedChanges.value).toBe(true)
    markClean()
    expect(hasUnsavedChanges.value).toBe(false)
  })

  it('confirmNavigation returns true when no unsaved changes', () => {
    const { confirmNavigation } = useUnsavedChanges()
    expect(confirmNavigation()).toBe(true)
  })

  it('confirmNavigation prompts user when there are unsaved changes', () => {
    window.confirm = vi.fn(() => false)
    const { confirmNavigation, markDirty } = useUnsavedChanges()
    markDirty()

    const result = confirmNavigation()

    expect(window.confirm).toHaveBeenCalled()
    expect(result).toBe(false)
  })

  it('setEnabled toggles the warning functionality', () => {
    const { isEnabled, setEnabled } = useUnsavedChanges()
    expect(isEnabled.value).toBe(true)
    setEnabled(false)
    expect(isEnabled.value).toBe(false)
  })

  it('confirmNavigation returns true when disabled even with unsaved changes', () => {
    const { confirmNavigation, markDirty, setEnabled } = useUnsavedChanges()
    markDirty()
    setEnabled(false)
    expect(confirmNavigation()).toBe(true)
  })

  it('accepts custom message option', () => {
    window.confirm = vi.fn(() => true)
    const customMsg = 'Custom warning message'
    const { confirmNavigation, markDirty } = useUnsavedChanges({ message: customMsg })
    markDirty()
    confirmNavigation()
    expect(window.confirm).toHaveBeenCalledWith(customMsg)
  })
})

// ============================================================
// useMobileGrid
// ============================================================
describe('useMobileGrid', () => {
  let useMobileGrid

  beforeEach(async () => {
    vi.clearAllMocks()
    const mod = await import('../useMobileGrid.js')
    useMobileGrid = mod.useMobileGrid
  })

  it('returns grid options with mobile row height when on mobile', () => {
    Object.defineProperty(window, 'innerWidth', { value: 400, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { gridOptions, isMobile } = useMobileGrid()
    // Force breakpoint update — the composable uses useResponsive internally
    isMobile.value = true

    expect(gridOptions.value.rowHeight).toBe(56)
    expect(gridOptions.value.singleClickEdit).toBe(true)
  })

  it('returns desktop row height on desktop', () => {
    Object.defineProperty(window, 'innerWidth', { value: 1200, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { gridOptions } = useMobileGrid()

    expect(gridOptions.value.rowHeight).toBe(40)
  })

  it('getVisibleColumns returns all columns on desktop', () => {
    Object.defineProperty(window, 'innerWidth', { value: 1200, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { getVisibleColumns } = useMobileGrid()
    const allColumns = [
      { field: 'a' }, { field: 'b' }, { field: 'c' },
      { field: 'd' }, { field: 'e' }, { field: 'f' }
    ]

    const visible = getVisibleColumns(allColumns)
    expect(visible).toHaveLength(6)
  })

  it('getColumnWidth returns width config for text type', () => {
    Object.defineProperty(window, 'innerWidth', { value: 1200, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { getColumnWidth } = useMobileGrid()
    const width = getColumnWidth('text')

    expect(width).toHaveProperty('minWidth')
    expect(width.minWidth).toBe(150)
  })

  it('getCellEditorParams returns text editor config by default', () => {
    const { getCellEditorParams } = useMobileGrid()
    const config = getCellEditorParams('text')

    expect(config.cellEditor).toBe('agTextCellEditor')
    expect(config.cellEditorParams.maxLength).toBe(255)
  })

  it('getPaginationOptions returns correct page size for desktop', () => {
    Object.defineProperty(window, 'innerWidth', { value: 1200, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })

    const { getPaginationOptions } = useMobileGrid()

    expect(getPaginationOptions.value.pagination).toBe(true)
    expect(getPaginationOptions.value.paginationPageSize).toBe(50)
  })
})

// ============================================================
// useDashboardWidgets
// ============================================================
describe('useDashboardWidgets', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('useDowntimeImpact', () => {
    let useDowntimeImpact

    beforeEach(async () => {
      const mod = await import('../useDashboardWidgets.ts')
      useDowntimeImpact = mod.useDowntimeImpact
    })

    it('initializes with empty data and no loading', () => {
      const { loading, error, data } = useDowntimeImpact()

      expect(loading.value).toBe(false)
      expect(error.value).toBeNull()
      expect(data.value).toEqual([])
    })

    it('computes totalDowntime from data', () => {
      const { data, totalDowntime } = useDowntimeImpact()
      data.value = [
        { category: 'A', totalHours: 10, oeeImpact: 5, eventCount: 2, severity: 'high' },
        { category: 'B', totalHours: 15, oeeImpact: 8, eventCount: 3, severity: 'critical' }
      ]

      expect(totalDowntime.value).toBe(25)
    })

    it('computes totalOeeImpact from data', () => {
      const { data, totalOeeImpact } = useDowntimeImpact()
      data.value = [
        { category: 'A', totalHours: 10, oeeImpact: 5, eventCount: 2, severity: 'high' },
        { category: 'B', totalHours: 15, oeeImpact: 8, eventCount: 3, severity: 'critical' }
      ]

      expect(totalOeeImpact.value).toBe(13)
    })

    it('fetchData sets loading state and handles API response', async () => {
      mockAxiosGet.mockResolvedValueOnce({
        data: {
          categories: [
            { category: 'Mechanical', total_hours: '5.5', oee_impact: '3.2', event_count: 4 }
          ]
        }
      })

      const { fetchData, loading, data } = useDowntimeImpact()
      const promise = fetchData('2026-01-01', '2026-01-31')

      expect(loading.value).toBe(true)

      await promise

      expect(loading.value).toBe(false)
      expect(data.value).toHaveLength(1)
      expect(data.value[0].category).toBe('Mechanical')
      expect(data.value[0].totalHours).toBe(5.5)
    })
  })

  describe('useBradfordFactor', () => {
    let useBradfordFactor

    beforeEach(async () => {
      const mod = await import('../useDashboardWidgets.ts')
      useBradfordFactor = mod.useBradfordFactor
    })

    it('initializes with empty data', () => {
      const { loading, data } = useBradfordFactor()
      expect(loading.value).toBe(false)
      expect(data.value).toEqual([])
    })

    it('fetches bradford factor data from API', async () => {
      mockAxiosGet.mockResolvedValueOnce({
        data: [
          { employee_id: 1, employee_name: 'John', bradford_score: 100, spells: 3, total_days: 10 }
        ]
      })

      const { fetchData, data } = useBradfordFactor()
      await fetchData()

      expect(data.value).toHaveLength(1)
      expect(data.value[0].employeeName).toBe('John')
      expect(data.value[0].score).toBe(100)
      expect(data.value[0].riskLevel).toBe('monitor')
    })
  })

  describe('useAbsenteeismAlert', () => {
    let useAbsenteeismAlert

    beforeEach(async () => {
      const mod = await import('../useDashboardWidgets.ts')
      useAbsenteeismAlert = mod.useAbsenteeismAlert
    })

    it('initializes with default threshold', () => {
      const { data } = useAbsenteeismAlert(5)
      expect(data.value.threshold).toBe(5)
      expect(data.value.rate).toBe(0)
    })

    it('shouldShowAlert is false when rate is below threshold', () => {
      const { shouldShowAlert } = useAbsenteeismAlert(5)
      expect(shouldShowAlert.value).toBe(false)
    })

    it('shouldShowAlert is true when rate exceeds threshold', () => {
      const { data, shouldShowAlert } = useAbsenteeismAlert(5)
      data.value.rate = 8
      expect(shouldShowAlert.value).toBe(true)
    })

    it('alertSeverity returns error when rate is double the threshold', () => {
      const { data, alertSeverity } = useAbsenteeismAlert(5)
      data.value.rate = 12
      expect(alertSeverity.value).toBe('error')
    })

    it('alertSeverity returns warning when rate slightly exceeds threshold', () => {
      const { data, alertSeverity } = useAbsenteeismAlert(5)
      data.value.rate = 7
      expect(alertSeverity.value).toBe('warning')
    })
  })

  describe('useQualityByOperator', () => {
    let useQualityByOperator

    beforeEach(async () => {
      const mod = await import('../useDashboardWidgets.ts')
      useQualityByOperator = mod.useQualityByOperator
    })

    it('computes averageFPY correctly', () => {
      const { data, averageFPY } = useQualityByOperator()
      data.value = [
        { operatorId: '1', operatorName: 'A', unitsInspected: 100, defects: 2, fpy: 98, trend: 'up' },
        { operatorId: '2', operatorName: 'B', unitsInspected: 100, defects: 5, fpy: 95, trend: 'stable' }
      ]

      expect(averageFPY.value).toBe(96.5)
    })

    it('computes topPerformers count', () => {
      const { data, topPerformers } = useQualityByOperator()
      data.value = [
        { operatorId: '1', operatorName: 'A', unitsInspected: 100, defects: 1, fpy: 99, trend: 'up' },
        { operatorId: '2', operatorName: 'B', unitsInspected: 100, defects: 10, fpy: 90, trend: 'down' },
        { operatorId: '3', operatorName: 'C', unitsInspected: 100, defects: 2, fpy: 98, trend: 'stable' }
      ]

      expect(topPerformers.value).toBe(2)
    })

    it('computes needsAttention count', () => {
      const { data, needsAttention } = useQualityByOperator()
      data.value = [
        { operatorId: '1', operatorName: 'A', unitsInspected: 100, defects: 1, fpy: 99, trend: 'up' },
        { operatorId: '2', operatorName: 'B', unitsInspected: 100, defects: 10, fpy: 90, trend: 'down' }
      ]

      expect(needsAttention.value).toBe(1)
    })
  })

  describe('useReworkByOperation', () => {
    let useReworkByOperation

    beforeEach(async () => {
      const mod = await import('../useDashboardWidgets.ts')
      useReworkByOperation = mod.useReworkByOperation
    })

    it('computes totalReworkUnits', () => {
      const { data, totalReworkUnits } = useReworkByOperation()
      data.value = [
        { operation: 'Sewing', reworkUnits: 20, reworkHours: 10, reworkRate: 2, estimatedCost: 300 },
        { operation: 'Cutting', reworkUnits: 10, reworkHours: 5, reworkRate: 1, estimatedCost: 150 }
      ]

      expect(totalReworkUnits.value).toBe(30)
    })

    it('computes overallReworkRate', () => {
      const { data, totalUnitsProduced, overallReworkRate } = useReworkByOperation()
      totalUnitsProduced.value = 1000
      data.value = [
        { operation: 'Sewing', reworkUnits: 20, reworkHours: 10, reworkRate: 2, estimatedCost: 300 }
      ]

      expect(overallReworkRate.value).toBe(2)
    })
  })
})

// ============================================================
// useQRScanner
// ============================================================
describe('useQRScanner', () => {
  let useQRScanner

  beforeEach(async () => {
    vi.clearAllMocks()
    const mod = await import('../useQRScanner.js')
    useQRScanner = mod.useQRScanner
  })

  it('initializes with scanning inactive', () => {
    const { isScanning, isCameraActive, lastScannedData, scanError } = useQRScanner()

    expect(isScanning.value).toBe(false)
    expect(isCameraActive.value).toBe(false)
    expect(lastScannedData.value).toBeNull()
    expect(scanError.value).toBeNull()
  })

  it('stopScanning sets flags to false', () => {
    const { isScanning, isCameraActive, stopScanning } = useQRScanner()
    isScanning.value = true
    isCameraActive.value = true

    stopScanning()

    expect(isScanning.value).toBe(false)
    expect(isCameraActive.value).toBe(false)
  })

  it('clearHistory empties scan history', () => {
    const { scanHistory, clearHistory } = useQRScanner()
    scanHistory.value = [{ entity_type: 'work_order', entity_data: { id: 1 } }]

    clearHistory()

    expect(scanHistory.value).toEqual([])
  })

  it('clearLastScan resets last scan data and error', () => {
    const { lastScannedData, scanError, clearLastScan } = useQRScanner()
    lastScannedData.value = { foo: 'bar' }
    scanError.value = 'some error'

    clearLastScan()

    expect(lastScannedData.value).toBeNull()
    expect(scanError.value).toBeNull()
  })

  it('autoFillForm fills matching fields from scan result', () => {
    const { autoFillForm } = useQRScanner()
    const formData = { work_order_id: '', product_id: '', notes: '' }
    const scanResult = {
      auto_fill_fields: {
        work_order_id: 'WO-123',
        product_id: 42,
        unknown_field: 'ignored'
      }
    }

    const updated = autoFillForm(formData, scanResult)

    expect(updated.work_order_id).toBe('WO-123')
    expect(updated.product_id).toBe(42)
    expect(updated.notes).toBe('')
  })

  it('autoFillForm returns original data when no auto_fill_fields', () => {
    const { autoFillForm } = useQRScanner()
    const formData = { work_order_id: 'test' }
    const scanResult = {}

    const updated = autoFillForm(formData, scanResult)

    expect(updated.work_order_id).toBe('test')
  })

  it('getQRImageUrl returns correct URL', () => {
    const { getQRImageUrl } = useQRScanner()
    const url = getQRImageUrl('work_order', 123)
    expect(url).toBe('/api/qr/work_order/123/image')
  })

  it('canScan computed is true when permission granted', () => {
    const { hasCameraPermission, canScan } = useQRScanner()
    hasCameraPermission.value = true
    expect(canScan.value).toBe(true)
  })

  it('canScan computed is false when permission denied', () => {
    const { hasCameraPermission, canScan } = useQRScanner()
    hasCameraPermission.value = false
    expect(canScan.value).toBe(false)
  })
})
