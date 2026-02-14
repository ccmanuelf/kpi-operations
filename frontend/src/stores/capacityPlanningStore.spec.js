/**
 * Unit tests for Capacity Planning Pinia Store
 *
 * Tests state initialization, getters, CRUD row operations, undo/redo,
 * loadWorkbook, saveWorkbook, scenario/schedule/MRP actions, dirty tracking,
 * export/import, UI state helpers, and reset.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock the entire API service module
vi.mock('@/services/api/capacityPlanning', () => ({
  loadWorkbook: vi.fn(),
  saveWorksheet: vi.fn(),
  saveWorkbook: vi.fn(),
  getCalendarEntries: vi.fn(),
  createCalendarEntry: vi.fn(),
  updateCalendarEntry: vi.fn(),
  deleteCalendarEntry: vi.fn(),
  getProductionLines: vi.fn(),
  createProductionLine: vi.fn(),
  updateProductionLine: vi.fn(),
  deleteProductionLine: vi.fn(),
  getOrders: vi.fn(),
  getOrdersForScheduling: vi.fn(),
  createOrder: vi.fn(),
  updateOrder: vi.fn(),
  updateOrderStatus: vi.fn(),
  deleteOrder: vi.fn(),
  getStandards: vi.fn(),
  getStandardsByStyle: vi.fn(),
  getTotalSAMForStyle: vi.fn(),
  createStandard: vi.fn(),
  updateStandard: vi.fn(),
  deleteStandard: vi.fn(),
  getBOMHeaders: vi.fn(),
  getBOMWithDetails: vi.fn(),
  createBOMHeader: vi.fn(),
  updateBOMHeader: vi.fn(),
  deleteBOMHeader: vi.fn(),
  getBOMDetails: vi.fn(),
  createBOMDetail: vi.fn(),
  updateBOMDetail: vi.fn(),
  deleteBOMDetail: vi.fn(),
  explodeBOM: vi.fn(),
  getStockSnapshots: vi.fn(),
  getLatestStock: vi.fn(),
  getAvailableStock: vi.fn(),
  getShortageItems: vi.fn(),
  createStockSnapshot: vi.fn(),
  updateStockSnapshot: vi.fn(),
  deleteStockSnapshot: vi.fn(),
  runComponentCheck: vi.fn(),
  getShortages: vi.fn(),
  runCapacityAnalysis: vi.fn(),
  getBottlenecks: vi.fn(),
  getSchedules: vi.fn(),
  getSchedule: vi.fn(),
  createSchedule: vi.fn(),
  generateSchedule: vi.fn(),
  commitSchedule: vi.fn(),
  getScenarios: vi.fn(),
  getScenario: vi.fn(),
  createScenario: vi.fn(),
  compareScenarios: vi.fn(),
  runScenario: vi.fn(),
  deleteScenario: vi.fn(),
  getKPICommitments: vi.fn(),
  getKPIActuals: vi.fn(),
  getKPIVariance: vi.fn(),
  isFeatureEnabled: vi.fn(),
  getModuleInfo: vi.fn()
}))

import * as capacityApi from '@/services/api/capacityPlanning'
import {
  useCapacityPlanningStore,
  getDefaultCalendarEntry,
  getDefaultProductionLine,
  getDefaultOrder,
  getDefaultStandard,
  getDefaultBOMHeader,
  getDefaultBOMDetail,
  getDefaultStockSnapshot,
  getDefaultComponentCheckRow,
  getDefaultCapacityAnalysisRow,
  getDefaultScheduleRow,
  getDefaultScenario,
  getDefaultKPITrackingRow,
  getDefaultDashboardInputs
} from './capacityPlanningStore'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal workbook API response with optional overrides. */
const buildWorkbookResponse = (overrides = {}) => ({
  master_calendar: [],
  production_lines: [],
  orders: [],
  production_standards: [],
  bom: [],
  stock_snapshot: [],
  component_check: [],
  capacity_analysis: [],
  production_schedule: [],
  what_if_scenarios: [],
  dashboard_inputs: {},
  kpi_tracking: [],
  instructions: '',
  ...overrides
})

describe('Capacity Planning Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useCapacityPlanningStore()
    vi.clearAllMocks()
  })

  // =========================================================================
  // 1. State Initialization
  // =========================================================================
  describe('State Initialization', () => {
    it('has null clientId on init', () => {
      expect(store.clientId).toBeNull()
    })

    it('has 13 worksheet keys', () => {
      const keys = Object.keys(store.worksheets)
      expect(keys).toHaveLength(13)
      expect(keys).toContain('masterCalendar')
      expect(keys).toContain('productionLines')
      expect(keys).toContain('orders')
      expect(keys).toContain('productionStandards')
      expect(keys).toContain('bom')
      expect(keys).toContain('stockSnapshot')
      expect(keys).toContain('componentCheck')
      expect(keys).toContain('capacityAnalysis')
      expect(keys).toContain('productionSchedule')
      expect(keys).toContain('whatIfScenarios')
      expect(keys).toContain('dashboardInputs')
      expect(keys).toContain('kpiTracking')
      expect(keys).toContain('instructions')
    })

    it('has empty arrays for array-based worksheets', () => {
      const arraySheets = [
        'masterCalendar', 'productionLines', 'orders', 'productionStandards',
        'bom', 'stockSnapshot', 'componentCheck', 'capacityAnalysis',
        'productionSchedule', 'whatIfScenarios', 'kpiTracking'
      ]
      for (const name of arraySheets) {
        expect(store.worksheets[name].data).toEqual([])
        expect(store.worksheets[name].dirty).toBe(false)
        expect(store.worksheets[name].loading).toBe(false)
        expect(store.worksheets[name].error).toBeNull()
      }
    })

    it('has default dashboard inputs', () => {
      const defaults = getDefaultDashboardInputs()
      expect(store.worksheets.dashboardInputs.data).toEqual(defaults)
    })

    it('has empty string for instructions content', () => {
      expect(store.worksheets.instructions.content).toBe('')
    })

    it('has default UI state', () => {
      expect(store.activeTab).toBe('orders')
      expect(store.showMRPResultsDialog).toBe(false)
      expect(store.showScenarioCompareDialog).toBe(false)
      expect(store.showScheduleCommitDialog).toBe(false)
      expect(store.showExportDialog).toBe(false)
      expect(store.showImportDialog).toBe(false)
    })

    it('has default loading/saving/error state', () => {
      expect(store.isLoading).toBe(false)
      expect(store.isSaving).toBe(false)
      expect(store.globalError).toBeNull()
      expect(store.lastSaved).toBeNull()
    })

    it('has default MRP state', () => {
      expect(store.mrpResults).toBeNull()
      expect(store.isRunningMRP).toBe(false)
      expect(store.mrpError).toBeNull()
    })

    it('has default scenario state', () => {
      expect(store.activeScenario).toBeNull()
      expect(store.scenarioComparisonResults).toBeNull()
      expect(store.isCreatingScenario).toBe(false)
    })

    it('has default schedule state', () => {
      expect(store.activeSchedule).toBeNull()
      expect(store.isGeneratingSchedule).toBe(false)
      expect(store.isCommittingSchedule).toBe(false)
    })
  })

  // =========================================================================
  // 2. Default Factory Exports
  // =========================================================================
  describe('Default Factory Functions', () => {
    it('getDefaultCalendarEntry returns correct shape', () => {
      const entry = getDefaultCalendarEntry()
      expect(entry.is_working_day).toBe(true)
      expect(entry.shifts_available).toBe(1)
      expect(entry.shift1_hours).toBe(8.0)
    })

    it('getDefaultProductionLine returns correct shape', () => {
      const line = getDefaultProductionLine()
      expect(line.line_code).toBe('')
      expect(line.efficiency_factor).toBe(0.85)
      expect(line.is_active).toBe(true)
    })

    it('getDefaultOrder returns correct shape', () => {
      const order = getDefaultOrder()
      expect(order.priority).toBe('NORMAL')
      expect(order.status).toBe('DRAFT')
      expect(order.order_quantity).toBe(0)
    })

    it('getDefaultStandard returns correct shape', () => {
      const std = getDefaultStandard()
      expect(std.sam_minutes).toBe(0)
      expect(std.operation_code).toBe('')
    })

    it('getDefaultBOMHeader returns correct shape with empty components', () => {
      const header = getDefaultBOMHeader()
      expect(header.revision).toBe('1.0')
      expect(header.components).toEqual([])
    })

    it('getDefaultBOMDetail returns correct shape', () => {
      const detail = getDefaultBOMDetail()
      expect(detail.quantity_per).toBe(1.0)
      expect(detail.unit_of_measure).toBe('EA')
    })

    it('getDefaultScenario returns correct shape', () => {
      const scenario = getDefaultScenario()
      expect(scenario.scenario_type).toBe('OVERTIME')
      expect(scenario.status).toBe('DRAFT')
      expect(scenario.parameters).toEqual({})
    })

    it('getDefaultDashboardInputs returns correct shape', () => {
      const inputs = getDefaultDashboardInputs()
      expect(inputs.planning_horizon_days).toBe(30)
      expect(inputs.default_efficiency).toBe(85)
      expect(inputs.auto_schedule_enabled).toBe(false)
    })
  })

  // =========================================================================
  // 3. Getters - Dirty State
  // =========================================================================
  describe('Getters - Dirty State', () => {
    it('hasUnsavedChanges returns false when no sheet is dirty', () => {
      expect(store.hasUnsavedChanges).toBe(false)
    })

    it('hasUnsavedChanges returns true when a sheet is dirty', () => {
      store.worksheets.orders.dirty = true
      expect(store.hasUnsavedChanges).toBe(true)
    })

    it('dirtyWorksheets returns names of dirty sheets', () => {
      store.worksheets.orders.dirty = true
      store.worksheets.bom.dirty = true
      expect(store.dirtyWorksheets).toEqual(expect.arrayContaining(['orders', 'bom']))
      expect(store.dirtyWorksheets).toHaveLength(2)
    })

    it('dirtyCount returns the number of dirty sheets', () => {
      expect(store.dirtyCount).toBe(0)
      store.worksheets.masterCalendar.dirty = true
      store.worksheets.productionLines.dirty = true
      store.worksheets.orders.dirty = true
      expect(store.dirtyCount).toBe(3)
    })
  })

  // =========================================================================
  // 4. Getters - Component Check
  // =========================================================================
  describe('Getters - Component Check', () => {
    it('shortageComponents filters SHORTAGE status', () => {
      store.worksheets.componentCheck.data = [
        { status: 'AVAILABLE' },
        { status: 'SHORTAGE' },
        { status: 'PARTIAL' },
        { status: 'SHORTAGE' }
      ]
      expect(store.shortageComponents).toHaveLength(2)
    })

    it('shortageCount returns count of shortages', () => {
      store.worksheets.componentCheck.data = [
        { status: 'SHORTAGE' },
        { status: 'AVAILABLE' }
      ]
      expect(store.shortageCount).toBe(1)
    })

    it('partialComponents filters PARTIAL status', () => {
      store.worksheets.componentCheck.data = [
        { status: 'PARTIAL' },
        { status: 'AVAILABLE' }
      ]
      expect(store.partialComponents).toHaveLength(1)
    })
  })

  // =========================================================================
  // 5. Getters - Capacity Analysis
  // =========================================================================
  describe('Getters - Capacity Analysis', () => {
    it('bottleneckLines filters bottleneck entries', () => {
      store.worksheets.capacityAnalysis.data = [
        { is_bottleneck: true, line_code: 'L1' },
        { is_bottleneck: false, line_code: 'L2' }
      ]
      expect(store.bottleneckLines).toHaveLength(1)
      expect(store.bottleneckLines[0].line_code).toBe('L1')
    })

    it('overloadedLines filters utilization > 100', () => {
      store.worksheets.capacityAnalysis.data = [
        { utilization_percent: '110' },
        { utilization_percent: '95' },
        { utilization_percent: '105' }
      ]
      expect(store.overloadedLines).toHaveLength(2)
    })

    it('averageUtilization calculates correctly', () => {
      store.worksheets.capacityAnalysis.data = [
        { utilization_percent: '80' },
        { utilization_percent: '100' }
      ]
      expect(store.averageUtilization).toBe('90.0')
    })

    it('averageUtilization returns 0 when empty', () => {
      expect(store.averageUtilization).toBe(0)
    })
  })

  // =========================================================================
  // 6. Getters - Orders
  // =========================================================================
  describe('Getters - Orders', () => {
    it('schedulableOrders returns DRAFT and CONFIRMED orders', () => {
      store.worksheets.orders.data = [
        { status: 'DRAFT' },
        { status: 'CONFIRMED' },
        { status: 'IN_PROGRESS' },
        { status: 'COMPLETED' }
      ]
      expect(store.schedulableOrders).toHaveLength(2)
    })

    it('totalOrderQuantity sums order quantities', () => {
      store.worksheets.orders.data = [
        { order_quantity: 100 },
        { order_quantity: 200 },
        { order_quantity: 50 }
      ]
      expect(store.totalOrderQuantity).toBe(350)
    })

    it('totalOrderQuantity returns 0 when empty', () => {
      expect(store.totalOrderQuantity).toBe(0)
    })

    it('ordersByStatus groups correctly', () => {
      store.worksheets.orders.data = [
        { status: 'DRAFT', id: 1 },
        { status: 'DRAFT', id: 2 },
        { status: 'COMPLETED', id: 3 }
      ]
      const grouped = store.ordersByStatus
      expect(grouped.DRAFT).toHaveLength(2)
      expect(grouped.COMPLETED).toHaveLength(1)
    })

    it('orderPriorityCounts counts by priority', () => {
      store.worksheets.orders.data = [
        { priority: 'CRITICAL' },
        { priority: 'CRITICAL' },
        { priority: 'HIGH' },
        { priority: 'NORMAL' }
      ]
      expect(store.orderPriorityCounts).toEqual({
        CRITICAL: 2, HIGH: 1, NORMAL: 1, LOW: 0
      })
    })
  })

  // =========================================================================
  // 7. Getters - Production Lines
  // =========================================================================
  describe('Getters - Production Lines', () => {
    it('activeLineCount counts active lines', () => {
      store.worksheets.productionLines.data = [
        { is_active: true },
        { is_active: false },
        { is_active: true }
      ]
      expect(store.activeLineCount).toBe(2)
    })

    it('inactiveLines returns inactive lines', () => {
      store.worksheets.productionLines.data = [
        { is_active: true, line_code: 'A' },
        { is_active: false, line_code: 'B' }
      ]
      expect(store.inactiveLines).toHaveLength(1)
      expect(store.inactiveLines[0].line_code).toBe('B')
    })

    it('totalCapacity sums active line capacity', () => {
      store.worksheets.productionLines.data = [
        { is_active: true, standard_capacity_units_per_hour: 50 },
        { is_active: false, standard_capacity_units_per_hour: 30 },
        { is_active: true, standard_capacity_units_per_hour: 70 }
      ]
      expect(store.totalCapacity).toBe(120)
    })
  })

  // =========================================================================
  // 8. Getters - Calendar
  // =========================================================================
  describe('Getters - Calendar', () => {
    it('workingDaysCount counts working days', () => {
      store.worksheets.masterCalendar.data = [
        { is_working_day: true },
        { is_working_day: false },
        { is_working_day: true }
      ]
      expect(store.workingDaysCount).toBe(2)
    })

    it('holidays filters entries with holiday_name', () => {
      store.worksheets.masterCalendar.data = [
        { holiday_name: 'New Year' },
        { holiday_name: null },
        { holiday_name: 'Christmas' }
      ]
      expect(store.holidays).toHaveLength(2)
    })
  })

  // =========================================================================
  // 9. Getters - KPI
  // =========================================================================
  describe('Getters - KPI', () => {
    it('kpiVarianceSummary returns null when empty', () => {
      expect(store.kpiVarianceSummary).toBeNull()
    })

    it('kpiVarianceSummary calculates summary correctly', () => {
      store.worksheets.kpiTracking.data = [
        { variance_percent: 2 },   // on target
        { variance_percent: -3 },  // on target
        { variance_percent: 8 },   // off target
        { variance_percent: -12 }, // critical
        { variance_percent: null } // on target (0 abs)
      ]
      const summary = store.kpiVarianceSummary
      expect(summary.totalKPIs).toBe(5)
      expect(summary.onTarget).toBe(3)
      expect(summary.offTarget).toBe(2)
      expect(summary.critical).toBe(1)
    })

    it('offTargetKPIs filters variance > 5', () => {
      store.worksheets.kpiTracking.data = [
        { kpi_name: 'A', variance_percent: 3 },
        { kpi_name: 'B', variance_percent: -7 },
        { kpi_name: 'C', variance_percent: 15 }
      ]
      expect(store.offTargetKPIs).toHaveLength(2)
    })
  })

  // =========================================================================
  // 10. Getters - Scenarios
  // =========================================================================
  describe('Getters - Scenarios', () => {
    it('scenariosByType groups scenarios', () => {
      store.worksheets.whatIfScenarios.data = [
        { scenario_type: 'OVERTIME', id: 1 },
        { scenario_type: 'OVERTIME', id: 2 },
        { scenario_type: 'NEW_LINE', id: 3 }
      ]
      const grouped = store.scenariosByType
      expect(grouped.OVERTIME).toHaveLength(2)
      expect(grouped.NEW_LINE).toHaveLength(1)
    })
  })

  // =========================================================================
  // 11. Getters - BOM
  // =========================================================================
  describe('Getters - BOM', () => {
    it('bomCount returns number of BOM entries', () => {
      store.worksheets.bom.data = [{ style_code: 'S1' }, { style_code: 'S2' }]
      expect(store.bomCount).toBe(2)
    })

    it('stylesWithBOM returns unique style codes', () => {
      store.worksheets.bom.data = [
        { style_code: 'S1' },
        { style_code: 'S1' },
        { style_code: 'S2' },
        { style_code: '' }
      ]
      expect(store.stylesWithBOM).toEqual(['S1', 'S2'])
    })
  })

  // =========================================================================
  // 12. Getters - Undo/Redo
  // =========================================================================
  describe('Getters - Undo/Redo', () => {
    it('canUndo returns false when history manager is null', () => {
      expect(store.canUndo).toBe(false)
    })

    it('canRedo returns false when history manager is null', () => {
      expect(store.canRedo).toBe(false)
    })
  })

  // =========================================================================
  // 13. Actions - setClientId
  // =========================================================================
  describe('Actions - setClientId', () => {
    it('sets the client ID', () => {
      store.setClientId(42)
      expect(store.clientId).toBe(42)
    })
  })

  // =========================================================================
  // 14. Actions - loadWorkbook
  // =========================================================================
  describe('Actions - loadWorkbook', () => {
    it('throws when no client ID is provided', async () => {
      await expect(store.loadWorkbook()).rejects.toThrow('Client ID is required')
    })

    it('sets isLoading during load', async () => {
      let resolveLoad
      capacityApi.loadWorkbook.mockImplementation(() =>
        new Promise(resolve => { resolveLoad = () => resolve(buildWorkbookResponse()) })
      )

      const loadPromise = store.loadWorkbook(1)
      expect(store.isLoading).toBe(true)

      resolveLoad()
      await loadPromise
      expect(store.isLoading).toBe(false)
    })

    it('populates all worksheets from API response', async () => {
      const response = buildWorkbookResponse({
        orders: [{ id: 10, order_number: 'ORD-1', status: 'DRAFT' }],
        production_lines: [{ id: 20, line_code: 'L1' }],
        master_calendar: [{ id: 30, is_working_day: true }],
        instructions: 'Some instructions text',
        dashboard_inputs: { planning_horizon_days: 60 }
      })
      capacityApi.loadWorkbook.mockResolvedValue(response)

      await store.loadWorkbook(1)

      expect(store.worksheets.orders.data).toHaveLength(1)
      expect(store.worksheets.orders.data[0].order_number).toBe('ORD-1')
      expect(store.worksheets.productionLines.data).toHaveLength(1)
      expect(store.worksheets.masterCalendar.data).toHaveLength(1)
      expect(store.worksheets.instructions.content).toBe('Some instructions text')
      expect(store.worksheets.dashboardInputs.data.planning_horizon_days).toBe(60)
    })

    it('adds _id to loaded rows', async () => {
      const response = buildWorkbookResponse({
        orders: [{ id: 5, order_number: 'ORD-A' }]
      })
      capacityApi.loadWorkbook.mockResolvedValue(response)

      await store.loadWorkbook(1)

      expect(store.worksheets.orders.data[0]._id).toBe(5)
    })

    it('resets dirty flags after load', async () => {
      store.worksheets.orders.dirty = true
      capacityApi.loadWorkbook.mockResolvedValue(buildWorkbookResponse())

      await store.loadWorkbook(1)

      expect(store.worksheets.orders.dirty).toBe(false)
    })

    it('sets clientId from argument', async () => {
      capacityApi.loadWorkbook.mockResolvedValue(buildWorkbookResponse())
      await store.loadWorkbook(99)
      expect(store.clientId).toBe(99)
    })

    it('uses existing clientId when argument is null', async () => {
      store.setClientId(77)
      capacityApi.loadWorkbook.mockResolvedValue(buildWorkbookResponse())
      await store.loadWorkbook()
      expect(capacityApi.loadWorkbook).toHaveBeenCalledWith(77)
    })

    it('sets globalError on API failure', async () => {
      capacityApi.loadWorkbook.mockRejectedValue(new Error('Network error'))

      await expect(store.loadWorkbook(1)).rejects.toThrow('Network error')
      expect(store.globalError).toBe('Network error')
      expect(store.isLoading).toBe(false)
    })
  })

  // =========================================================================
  // 15. Actions - addRow
  // =========================================================================
  describe('Actions - addRow', () => {
    it('adds a calendar entry with default values', () => {
      const row = store.addRow('masterCalendar')
      expect(row).not.toBeNull()
      expect(row.is_working_day).toBe(true)
      expect(row._isNew).toBe(true)
      expect(row._id).toBeDefined()
      expect(store.worksheets.masterCalendar.data).toHaveLength(1)
      expect(store.worksheets.masterCalendar.dirty).toBe(true)
    })

    it('adds a production line with default values', () => {
      const row = store.addRow('productionLines')
      expect(row.line_code).toBe('')
      expect(row.efficiency_factor).toBe(0.85)
      expect(store.worksheets.productionLines.dirty).toBe(true)
    })

    it('adds an order with default values', () => {
      const row = store.addRow('orders')
      expect(row.status).toBe('DRAFT')
      expect(row.priority).toBe('NORMAL')
    })

    it('adds a standard with default values', () => {
      const row = store.addRow('productionStandards')
      expect(row.sam_minutes).toBe(0)
    })

    it('adds a BOM header with default values', () => {
      const row = store.addRow('bom')
      expect(row.revision).toBe('1.0')
      expect(row.components).toEqual([])
    })

    it('adds a stock snapshot with default values', () => {
      const row = store.addRow('stockSnapshot')
      expect(row.unit_of_measure).toBe('EA')
    })

    it('adds a scenario with default values', () => {
      const row = store.addRow('whatIfScenarios')
      expect(row.scenario_type).toBe('OVERTIME')
    })

    it('adds a KPI tracking row with default values', () => {
      const row = store.addRow('kpiTracking')
      expect(row.status).toBe('PENDING')
    })

    it('adds a schedule row with default values', () => {
      const row = store.addRow('productionSchedule')
      expect(row.status).toBe('SCHEDULED')
    })

    it('adds a component check row with default values', () => {
      const row = store.addRow('componentCheck')
      expect(row.status).toBe('AVAILABLE')
    })

    it('adds a capacity analysis row with default values', () => {
      const row = store.addRow('capacityAnalysis')
      expect(row.is_bottleneck).toBe(false)
    })

    it('returns null for unknown worksheet', () => {
      const row = store.addRow('nonExistent')
      expect(row).toBeNull()
    })
  })

  // =========================================================================
  // 16. Actions - updateCell
  // =========================================================================
  describe('Actions - updateCell', () => {
    it('updates a single cell value', () => {
      store.worksheets.orders.data = [{ order_number: 'OLD', status: 'DRAFT' }]
      store.updateCell('orders', 0, 'order_number', 'NEW')
      expect(store.worksheets.orders.data[0].order_number).toBe('NEW')
      expect(store.worksheets.orders.dirty).toBe(true)
    })

    it('does nothing for invalid row index', () => {
      store.worksheets.orders.data = [{ order_number: 'A' }]
      store.updateCell('orders', 5, 'order_number', 'B')
      expect(store.worksheets.orders.data[0].order_number).toBe('A')
    })

    it('does nothing for unknown worksheet', () => {
      store.updateCell('nonExistent', 0, 'field', 'val')
      // should not throw
    })
  })

  // =========================================================================
  // 17. Actions - updateRow
  // =========================================================================
  describe('Actions - updateRow', () => {
    it('updates multiple fields in a row', () => {
      store.worksheets.productionLines.data = [
        { line_code: 'L1', line_name: 'Old', efficiency_factor: 0.8 }
      ]
      store.updateRow('productionLines', 0, { line_name: 'New', efficiency_factor: 0.9 })
      expect(store.worksheets.productionLines.data[0].line_name).toBe('New')
      expect(store.worksheets.productionLines.data[0].efficiency_factor).toBe(0.9)
      expect(store.worksheets.productionLines.dirty).toBe(true)
    })
  })

  // =========================================================================
  // 18. Actions - removeRow
  // =========================================================================
  describe('Actions - removeRow', () => {
    it('removes a row by index', () => {
      store.worksheets.orders.data = [
        { order_number: 'A' },
        { order_number: 'B' },
        { order_number: 'C' }
      ]
      const result = store.removeRow('orders', 1)
      expect(result).toBe(true)
      expect(store.worksheets.orders.data).toHaveLength(2)
      expect(store.worksheets.orders.data[1].order_number).toBe('C')
      expect(store.worksheets.orders.dirty).toBe(true)
    })

    it('returns false for invalid index', () => {
      store.worksheets.orders.data = [{ order_number: 'A' }]
      expect(store.removeRow('orders', -1)).toBe(false)
      expect(store.removeRow('orders', 5)).toBe(false)
    })

    it('returns false for unknown worksheet', () => {
      expect(store.removeRow('nonExistent', 0)).toBe(false)
    })
  })

  // =========================================================================
  // 19. Actions - removeRows
  // =========================================================================
  describe('Actions - removeRows', () => {
    it('removes multiple rows by indices', () => {
      store.worksheets.orders.data = [
        { order_number: 'A' },
        { order_number: 'B' },
        { order_number: 'C' },
        { order_number: 'D' }
      ]
      const result = store.removeRows('orders', [0, 2])
      expect(result).toBe(true)
      expect(store.worksheets.orders.data).toHaveLength(2)
      expect(store.worksheets.orders.data[0].order_number).toBe('B')
      expect(store.worksheets.orders.data[1].order_number).toBe('D')
    })
  })

  // =========================================================================
  // 20. Actions - duplicateRow
  // =========================================================================
  describe('Actions - duplicateRow', () => {
    it('duplicates a row with -COPY suffix on identifiers', () => {
      store.worksheets.orders.data = [
        { order_number: 'ORD-1', status: 'DRAFT', id: 10 }
      ]
      const dup = store.duplicateRow('orders', 0)
      expect(dup).not.toBeNull()
      expect(dup.order_number).toBe('ORD-1-COPY')
      expect(dup._isNew).toBe(true)
      expect(dup.id).toBeUndefined() // id is cleared
      expect(store.worksheets.orders.data).toHaveLength(2)
      expect(store.worksheets.orders.dirty).toBe(true)
    })

    it('duplicates a production line with -COPY suffix', () => {
      store.worksheets.productionLines.data = [
        { line_code: 'L1', line_name: 'Line 1' }
      ]
      const dup = store.duplicateRow('productionLines', 0)
      expect(dup.line_code).toBe('L1-COPY')
    })

    it('returns null for invalid index', () => {
      store.worksheets.orders.data = []
      expect(store.duplicateRow('orders', 0)).toBeNull()
    })
  })

  // =========================================================================
  // 21. Actions - importData / appendData
  // =========================================================================
  describe('Actions - importData / appendData', () => {
    it('importData replaces worksheet data', () => {
      store.worksheets.orders.data = [{ order_number: 'OLD' }]
      const newData = [{ order_number: 'NEW-1' }, { order_number: 'NEW-2' }]
      const result = store.importData('orders', newData)
      expect(result).toBe(true)
      expect(store.worksheets.orders.data).toHaveLength(2)
      expect(store.worksheets.orders.data[0]._imported).toBe(true)
      expect(store.worksheets.orders.dirty).toBe(true)
    })

    it('appendData adds to existing data', () => {
      store.worksheets.orders.data = [{ order_number: 'EXISTING' }]
      const newData = [{ order_number: 'APPENDED' }]
      const result = store.appendData('orders', newData)
      expect(result).toBe(true)
      expect(store.worksheets.orders.data).toHaveLength(2)
      expect(store.worksheets.orders.data[1].order_number).toBe('APPENDED')
    })

    it('importData returns false for unknown worksheet', () => {
      expect(store.importData('nonExistent', [])).toBe(false)
    })

    it('appendData returns false for unknown worksheet', () => {
      expect(store.appendData('nonExistent', [])).toBe(false)
    })
  })

  // =========================================================================
  // 22. Actions - Undo/Redo
  // =========================================================================
  describe('Actions - Undo/Redo', () => {
    it('undo returns false when no history', () => {
      expect(store.undo()).toBe(false)
    })

    it('redo returns false when no history', () => {
      expect(store.redo()).toBe(false)
    })

    it('undo restores previous state after cell update', () => {
      store.initHistory()
      store.worksheets.orders.data = [{ order_number: 'ORIGINAL' }]

      // _saveToHistory pushes state BEFORE modification into past.
      // After two changes the past stack holds: [state-before-change1, state-before-change2]
      store.updateCell('orders', 0, 'order_number', 'MODIFIED')
      store.updateCell('orders', 0, 'order_number', 'SECOND')
      expect(store.worksheets.orders.data[0].order_number).toBe('SECOND')

      // undo() pops the last entry from past (state-before-change2 = ORIGINAL),
      // moves it to future, then returns past[last] which is state-before-change1 = ORIGINAL.
      // The history manager undo returns the *peek* of the remaining past stack.
      const result = store.undo()
      expect(result).toBe(true)
      expect(store.worksheets.orders.data[0].order_number).toBe('ORIGINAL')
    })

    it('redo re-applies undone state', () => {
      store.initHistory()
      store.worksheets.orders.data = [{ order_number: 'V1' }]

      // past = [V1-snapshot]
      store.updateCell('orders', 0, 'order_number', 'V2')
      // past = [V1-snapshot, V2-snapshot]
      store.updateCell('orders', 0, 'order_number', 'V3')

      // undo: pops V2-snapshot from past into future, returns V1-snapshot
      store.undo()
      expect(store.worksheets.orders.data[0].order_number).toBe('V1')

      // redo: pops V2-snapshot from future back into past, returns parsed V2-snapshot
      store.redo()
      expect(store.worksheets.orders.data[0].order_number).toBe('V2')
    })

    it('canUndo returns true after modifications', () => {
      store.initHistory()
      store.worksheets.orders.data = [{ order_number: 'A' }]
      store.updateCell('orders', 0, 'order_number', 'B')
      expect(store.canUndo).toBe(true)
    })

    it('canRedo returns true after undo', () => {
      store.initHistory()
      store.worksheets.orders.data = [{ order_number: 'A' }]
      store.updateCell('orders', 0, 'order_number', 'B')
      store.updateCell('orders', 0, 'order_number', 'C')
      store.undo()
      expect(store.canRedo).toBe(true)
    })

    it('new modification clears redo stack', () => {
      store.initHistory()
      store.worksheets.orders.data = [{ order_number: 'A' }]
      store.updateCell('orders', 0, 'order_number', 'B')
      store.updateCell('orders', 0, 'order_number', 'C')
      store.undo()

      // Make a new change - should clear redo
      store.updateCell('orders', 0, 'order_number', 'D')
      expect(store.canRedo).toBe(false)
    })

    it('addRow also pushes to history', () => {
      store.initHistory()
      store.addRow('orders')
      expect(store.canUndo).toBe(true)
    })
  })

  // =========================================================================
  // 23. Actions - saveWorksheet
  // =========================================================================
  describe('Actions - saveWorksheet', () => {
    beforeEach(() => {
      store.setClientId(1)
    })

    it('saves worksheet data via API and clears dirty flag', async () => {
      capacityApi.saveWorksheet.mockResolvedValue({ status: 'ok' })
      store.worksheets.orders.data = [{ order_number: 'A', _isNew: true }]
      store.worksheets.orders.dirty = true

      const result = await store.saveWorksheet('orders')

      expect(result).toBe(true)
      expect(capacityApi.saveWorksheet).toHaveBeenCalledWith(
        'orders', 1, store.worksheets.orders.data
      )
      expect(store.worksheets.orders.dirty).toBe(false)
      expect(store.lastSaved).toBeInstanceOf(Date)
    })

    it('clears _isNew and _imported flags after save', async () => {
      capacityApi.saveWorksheet.mockResolvedValue({})
      store.worksheets.orders.data = [
        { order_number: 'A', _isNew: true, _imported: true }
      ]
      store.worksheets.orders.dirty = true

      await store.saveWorksheet('orders')

      expect(store.worksheets.orders.data[0]._isNew).toBeUndefined()
      expect(store.worksheets.orders.data[0]._imported).toBeUndefined()
    })

    it('saves instructions content (not data)', async () => {
      capacityApi.saveWorksheet.mockResolvedValue({})
      store.worksheets.instructions.content = 'My notes'
      store.worksheets.instructions.dirty = true

      await store.saveWorksheet('instructions')

      expect(capacityApi.saveWorksheet).toHaveBeenCalledWith(
        'instructions', 1, 'My notes'
      )
    })

    it('sets worksheet error on API failure', async () => {
      capacityApi.saveWorksheet.mockRejectedValue(new Error('Save failed'))
      store.worksheets.orders.dirty = true

      await expect(store.saveWorksheet('orders')).rejects.toThrow('Save failed')
      expect(store.worksheets.orders.error).toBe('Save failed')
      expect(store.worksheets.orders.loading).toBe(false)
    })

    it('returns false when no clientId', async () => {
      store.clientId = null
      const result = await store.saveWorksheet('orders')
      expect(result).toBe(false)
    })
  })

  // =========================================================================
  // 24. Actions - saveAllDirty
  // =========================================================================
  describe('Actions - saveAllDirty', () => {
    beforeEach(() => {
      store.setClientId(1)
    })

    it('saves only dirty worksheets', async () => {
      capacityApi.saveWorksheet.mockResolvedValue({})
      store.worksheets.orders.dirty = true
      store.worksheets.bom.dirty = true

      const results = await store.saveAllDirty()

      expect(results.success).toContain('orders')
      expect(results.success).toContain('bom')
      expect(results.failed).toHaveLength(0)
      expect(store.isSaving).toBe(false)
    })

    it('tracks failures', async () => {
      capacityApi.saveWorksheet
        .mockResolvedValueOnce({})
        .mockRejectedValueOnce(new Error('BOM save failed'))

      store.worksheets.orders.dirty = true
      store.worksheets.bom.dirty = true

      const results = await store.saveAllDirty()

      expect(results.success).toContain('orders')
      expect(results.failed).toHaveLength(1)
      expect(results.failed[0].name).toBe('bom')
    })
  })

  // =========================================================================
  // 25. Actions - saveWorkbook
  // =========================================================================
  describe('Actions - saveWorkbook', () => {
    beforeEach(() => {
      store.setClientId(1)
    })

    it('saves all worksheets and resets dirty flags', async () => {
      capacityApi.saveWorkbook.mockResolvedValue({})
      store.worksheets.orders.dirty = true
      store.worksheets.productionLines.dirty = true

      const result = await store.saveWorkbook()

      expect(result).toBe(true)
      expect(capacityApi.saveWorkbook).toHaveBeenCalledWith(1, expect.any(Object))
      expect(store.worksheets.orders.dirty).toBe(false)
      expect(store.worksheets.productionLines.dirty).toBe(false)
      expect(store.lastSaved).toBeInstanceOf(Date)
      expect(store.isSaving).toBe(false)
    })

    it('returns false when no clientId', async () => {
      store.clientId = null
      const result = await store.saveWorkbook()
      expect(result).toBe(false)
    })

    it('sets globalError on failure', async () => {
      capacityApi.saveWorkbook.mockRejectedValue(new Error('Bulk save failed'))

      await expect(store.saveWorkbook()).rejects.toThrow('Bulk save failed')
      expect(store.globalError).toBe('Bulk save failed')
      expect(store.isSaving).toBe(false)
    })
  })

  // =========================================================================
  // 26. Actions - runComponentCheck (MRP)
  // =========================================================================
  describe('Actions - runComponentCheck', () => {
    beforeEach(() => {
      store.setClientId(1)
    })

    it('runs component check and populates results', async () => {
      const mockResults = {
        components: [
          { id: 1, status: 'SHORTAGE', component_item_code: 'C1' },
          { id: 2, status: 'AVAILABLE', component_item_code: 'C2' }
        ]
      }
      capacityApi.runComponentCheck.mockResolvedValue(mockResults)

      const results = await store.runComponentCheck()

      expect(results).toEqual(mockResults)
      expect(store.mrpResults).toEqual(mockResults)
      expect(store.worksheets.componentCheck.data).toHaveLength(2)
      expect(store.showMRPResultsDialog).toBe(true)
      expect(store.isRunningMRP).toBe(false)
    })

    it('passes orderIds to API', async () => {
      capacityApi.runComponentCheck.mockResolvedValue({ components: [] })
      await store.runComponentCheck([10, 20])
      expect(capacityApi.runComponentCheck).toHaveBeenCalledWith(1, [10, 20])
    })

    it('sets mrpError on failure', async () => {
      capacityApi.runComponentCheck.mockRejectedValue(new Error('MRP failed'))

      await expect(store.runComponentCheck()).rejects.toThrow('MRP failed')
      expect(store.mrpError).toBe('MRP failed')
      expect(store.isRunningMRP).toBe(false)
    })

    it('returns null when no clientId', async () => {
      store.clientId = null
      const result = await store.runComponentCheck()
      expect(result).toBeNull()
    })

    it('clearMRPResults resets MRP state', () => {
      store.mrpResults = { some: 'data' }
      store.mrpError = 'error'
      store.showMRPResultsDialog = true

      store.clearMRPResults()

      expect(store.mrpResults).toBeNull()
      expect(store.mrpError).toBeNull()
      expect(store.showMRPResultsDialog).toBe(false)
    })
  })

  // =========================================================================
  // 27. Actions - BOM Operations
  // =========================================================================
  describe('Actions - BOM Operations', () => {
    beforeEach(() => {
      store.setClientId(1)
    })

    it('explodeBOM calls API and returns result', async () => {
      const mockResult = { components: [{ item: 'C1', qty: 10 }] }
      capacityApi.explodeBOM.mockResolvedValue(mockResult)

      const result = await store.explodeBOM('PARENT-1', 100)

      expect(result).toEqual(mockResult)
      expect(capacityApi.explodeBOM).toHaveBeenCalledWith(1, 'PARENT-1', 100)
    })

    it('explodeBOM returns null when no clientId', async () => {
      store.clientId = null
      const result = await store.explodeBOM('P1', 1)
      expect(result).toBeNull()
    })

    it('addBOMComponent adds a component to a BOM', () => {
      store.worksheets.bom.data = [{ parent_item_code: 'P1', components: [] }]

      const comp = store.addBOMComponent(0)

      expect(comp).not.toBeNull()
      expect(comp.quantity_per).toBe(1.0)
      expect(store.worksheets.bom.data[0].components).toHaveLength(1)
      expect(store.worksheets.bom.dirty).toBe(true)
    })

    it('addBOMComponent initializes components array if missing', () => {
      store.worksheets.bom.data = [{ parent_item_code: 'P1' }]

      store.addBOMComponent(0)

      expect(store.worksheets.bom.data[0].components).toHaveLength(1)
    })

    it('addBOMComponent returns null for invalid index', () => {
      store.worksheets.bom.data = []
      expect(store.addBOMComponent(0)).toBeNull()
    })

    it('removeBOMComponent removes a component', () => {
      store.worksheets.bom.data = [{
        parent_item_code: 'P1',
        components: [
          { component_item_code: 'C1' },
          { component_item_code: 'C2' }
        ]
      }]

      const result = store.removeBOMComponent(0, 0)

      expect(result).toBe(true)
      expect(store.worksheets.bom.data[0].components).toHaveLength(1)
      expect(store.worksheets.bom.data[0].components[0].component_item_code).toBe('C2')
    })
  })

  // =========================================================================
  // 28. Actions - Capacity Analysis
  // =========================================================================
  describe('Actions - Capacity Analysis', () => {
    beforeEach(() => {
      store.setClientId(1)
    })

    it('runCapacityAnalysis calls API and stores results', async () => {
      const mockResults = {
        line_results: [
          { id: 1, line_code: 'L1', utilization_percent: 85 }
        ]
      }
      capacityApi.runCapacityAnalysis.mockResolvedValue(mockResults)

      const results = await store.runCapacityAnalysis('2026-01-01', '2026-01-31')

      expect(results).toEqual(mockResults)
      expect(store.analysisResults).toEqual(mockResults)
      expect(store.worksheets.capacityAnalysis.data).toHaveLength(1)
      expect(store.isRunningAnalysis).toBe(false)
    })

    it('runCapacityAnalysis passes lineIds', async () => {
      capacityApi.runCapacityAnalysis.mockResolvedValue({ line_results: [] })
      await store.runCapacityAnalysis('2026-01-01', '2026-01-31', [1, 2])
      expect(capacityApi.runCapacityAnalysis).toHaveBeenCalledWith(1, '2026-01-01', '2026-01-31', [1, 2])
    })

    it('runCapacityAnalysis returns null when no clientId', async () => {
      store.clientId = null
      const result = await store.runCapacityAnalysis('2026-01-01', '2026-01-31')
      expect(result).toBeNull()
    })

    it('clearAnalysisResults resets analysis state', () => {
      store.analysisResults = { some: 'data' }
      store.clearAnalysisResults()
      expect(store.analysisResults).toBeNull()
    })
  })

  // =========================================================================
  // 29. Actions - Schedule Operations
  // =========================================================================
  describe('Actions - Schedule Operations', () => {
    beforeEach(() => {
      store.setClientId(1)
    })

    it('generateSchedule calls API and sets activeSchedule', async () => {
      const mockSchedule = {
        id: 1,
        name: 'Week 1',
        details: [
          { id: 10, order_number: 'ORD-1', line_code: 'L1' }
        ]
      }
      capacityApi.generateSchedule.mockResolvedValue(mockSchedule)

      const result = await store.generateSchedule('Week 1', '2026-01-01', '2026-01-07')

      expect(result).toEqual(mockSchedule)
      expect(store.activeSchedule).toEqual(mockSchedule)
      expect(store.worksheets.productionSchedule.data).toHaveLength(1)
      expect(store.isGeneratingSchedule).toBe(false)
    })

    it('generateSchedule returns null when no clientId', async () => {
      store.clientId = null
      const result = await store.generateSchedule('Test', '2026-01-01', '2026-01-07')
      expect(result).toBeNull()
    })

    it('commitSchedule calls API and updates KPI tracking', async () => {
      const mockResult = {
        kpi_commitments: [
          { id: 1, kpi_name: 'OTD', target_value: 95 }
        ]
      }
      capacityApi.commitSchedule.mockResolvedValue(mockResult)
      store.activeSchedule = { id: 5, status: 'GENERATED' }

      const result = await store.commitSchedule(5, { otd: 95 })

      expect(result).toEqual(mockResult)
      expect(store.worksheets.kpiTracking.data).toHaveLength(1)
      expect(store.activeSchedule.status).toBe('COMMITTED')
      expect(store.isCommittingSchedule).toBe(false)
      expect(store.showScheduleCommitDialog).toBe(false)
    })

    it('commitSchedule returns null when no clientId', async () => {
      store.clientId = null
      const result = await store.commitSchedule(1, {})
      expect(result).toBeNull()
    })

    it('loadSchedule calls API and sets activeSchedule', async () => {
      const mockSchedule = {
        id: 3,
        details: [{ id: 20, order_number: 'ORD-2' }]
      }
      capacityApi.getSchedule.mockResolvedValue(mockSchedule)

      const result = await store.loadSchedule(3)

      expect(result).toEqual(mockSchedule)
      expect(store.activeSchedule).toEqual(mockSchedule)
      expect(store.worksheets.productionSchedule.data).toHaveLength(1)
    })
  })

  // =========================================================================
  // 30. Actions - Scenario Operations
  // =========================================================================
  describe('Actions - Scenario Operations', () => {
    beforeEach(() => {
      store.setClientId(1)
    })

    it('createScenario calls API and adds to whatIfScenarios', async () => {
      const mockScenario = { id: 1, scenario_name: 'OT Test', scenario_type: 'OVERTIME' }
      capacityApi.createScenario.mockResolvedValue(mockScenario)

      const result = await store.createScenario('OT Test', 'OVERTIME', { hours: 2 })

      expect(result).toEqual(mockScenario)
      expect(store.worksheets.whatIfScenarios.data).toHaveLength(1)
      expect(store.worksheets.whatIfScenarios.dirty).toBe(true)
      expect(store.activeScenario).toEqual(mockScenario)
      expect(store.isCreatingScenario).toBe(false)
    })

    it('createScenario returns null when no clientId', async () => {
      store.clientId = null
      const result = await store.createScenario('Test', 'OVERTIME', {})
      expect(result).toBeNull()
    })

    it('runScenario calls API and updates scenario in list', async () => {
      store.worksheets.whatIfScenarios.data = [
        { id: 1, scenario_name: 'Test', status: 'DRAFT' }
      ]
      const mockResults = { capacity_improvement: 15 }
      capacityApi.runScenario.mockResolvedValue(mockResults)

      const result = await store.runScenario(1)

      expect(result).toEqual(mockResults)
      expect(store.worksheets.whatIfScenarios.data[0].status).toBe('EVALUATED')
    })

    it('runScenario returns null when no clientId', async () => {
      store.clientId = null
      const result = await store.runScenario(1)
      expect(result).toBeNull()
    })

    it('compareScenarios calls API and stores results', async () => {
      const mockComparison = { scenarios: [{ id: 1 }, { id: 2 }], winner: 1 }
      capacityApi.compareScenarios.mockResolvedValue(mockComparison)

      const result = await store.compareScenarios([1, 2])

      expect(result).toEqual(mockComparison)
      expect(store.scenarioComparisonResults).toEqual(mockComparison)
      expect(store.showScenarioCompareDialog).toBe(true)
    })

    it('deleteScenario removes from list and clears active', async () => {
      store.worksheets.whatIfScenarios.data = [
        { id: 1, scenario_name: 'A' },
        { id: 2, scenario_name: 'B' }
      ]
      store.activeScenario = { id: 1 }
      capacityApi.deleteScenario.mockResolvedValue({})

      const result = await store.deleteScenario(1)

      expect(result).toBe(true)
      expect(store.worksheets.whatIfScenarios.data).toHaveLength(1)
      expect(store.worksheets.whatIfScenarios.data[0].id).toBe(2)
      expect(store.activeScenario).toBeNull()
    })

    it('deleteScenario keeps activeScenario if different id', async () => {
      store.worksheets.whatIfScenarios.data = [
        { id: 1 }, { id: 2 }
      ]
      store.activeScenario = { id: 2 }
      capacityApi.deleteScenario.mockResolvedValue({})

      await store.deleteScenario(1)

      expect(store.activeScenario).toEqual({ id: 2 })
    })
  })

  // =========================================================================
  // 31. Actions - KPI Integration
  // =========================================================================
  describe('Actions - KPI Integration', () => {
    beforeEach(() => {
      store.setClientId(1)
    })

    it('loadKPIActuals updates existing KPI tracking entries', async () => {
      store.worksheets.kpiTracking.data = [
        { kpi_name: 'OTD', target_value: 95, actual_value: null, variance_percent: null },
        { kpi_name: 'Efficiency', target_value: 85, actual_value: null, variance_percent: null }
      ]
      const mockActuals = [
        { kpi_name: 'OTD', value: 92 },
        { kpi_name: 'Efficiency', value: 88 }
      ]
      capacityApi.getKPIActuals.mockResolvedValue(mockActuals)

      const result = await store.loadKPIActuals('week')

      expect(result).toEqual(mockActuals)
      expect(store.worksheets.kpiTracking.data[0].actual_value).toBe(92)
      expect(store.worksheets.kpiTracking.data[1].actual_value).toBe(88)
      // Variance: (88 - 85) / 85 * 100 = 3.5
      expect(parseFloat(store.worksheets.kpiTracking.data[1].variance_percent)).toBeCloseTo(3.5, 1)
    })

    it('loadKPIActuals returns null when no clientId', async () => {
      store.clientId = null
      const result = await store.loadKPIActuals('month')
      expect(result).toBeNull()
    })
  })

  // =========================================================================
  // 32. Actions - Export
  // =========================================================================
  describe('Actions - Export', () => {
    it('exportWorksheetJSON returns clean JSON without internal fields', () => {
      store.worksheets.orders.data = [
        { order_number: 'ORD-1', _id: 999, _isNew: true, _imported: true, status: 'DRAFT' }
      ]

      const json = store.exportWorksheetJSON('orders')
      const parsed = JSON.parse(json)

      expect(parsed).toHaveLength(1)
      expect(parsed[0].order_number).toBe('ORD-1')
      expect(parsed[0]._id).toBeUndefined()
      expect(parsed[0]._isNew).toBeUndefined()
      expect(parsed[0]._imported).toBeUndefined()
    })

    it('exportWorksheetJSON handles instructions content', () => {
      store.worksheets.instructions.content = 'My instructions'
      const json = store.exportWorksheetJSON('instructions')
      expect(JSON.parse(json)).toBe('My instructions')
    })

    it('exportWorksheetJSON returns null for unknown worksheet', () => {
      expect(store.exportWorksheetJSON('nonExistent')).toBeNull()
    })

    it('exportWorkbookJSON returns complete workbook', () => {
      store.worksheets.orders.data = [
        { order_number: 'ORD-1', _id: 1, status: 'DRAFT' }
      ]
      store.worksheets.instructions.content = 'Notes'

      const json = store.exportWorkbookJSON()
      const parsed = JSON.parse(json)

      expect(parsed.orders).toHaveLength(1)
      expect(parsed.orders[0]._id).toBeUndefined()
      expect(parsed.instructions).toBe('Notes')
      expect(parsed.masterCalendar).toEqual([])
    })
  })

  // =========================================================================
  // 33. Actions - Dashboard Inputs
  // =========================================================================
  describe('Actions - updateDashboardInput', () => {
    it('updates a dashboard input key and marks dirty', () => {
      store.updateDashboardInput('planning_horizon_days', 60)
      expect(store.worksheets.dashboardInputs.data.planning_horizon_days).toBe(60)
      expect(store.worksheets.dashboardInputs.dirty).toBe(true)
    })
  })

  // =========================================================================
  // 34. Actions - UI State
  // =========================================================================
  describe('Actions - UI State', () => {
    it('setActiveTab changes the active tab', () => {
      store.setActiveTab('masterCalendar')
      expect(store.activeTab).toBe('masterCalendar')
    })

    it('clearError clears globalError and all worksheet errors and mrpError', () => {
      store.globalError = 'global error'
      store.worksheets.orders.error = 'orders error'
      store.mrpError = 'mrp error'

      store.clearError()

      expect(store.globalError).toBeNull()
      expect(store.worksheets.orders.error).toBeNull()
      expect(store.mrpError).toBeNull()
    })

    it('closeAllDialogs closes all dialogs', () => {
      store.showMRPResultsDialog = true
      store.showScenarioCompareDialog = true
      store.showScheduleCommitDialog = true
      store.showExportDialog = true
      store.showImportDialog = true

      store.closeAllDialogs()

      expect(store.showMRPResultsDialog).toBe(false)
      expect(store.showScenarioCompareDialog).toBe(false)
      expect(store.showScheduleCommitDialog).toBe(false)
      expect(store.showExportDialog).toBe(false)
      expect(store.showImportDialog).toBe(false)
    })
  })

  // =========================================================================
  // 35. Actions - Reset
  // =========================================================================
  describe('Actions - reset', () => {
    it('resets all state to defaults', () => {
      // Modify various pieces of state
      store.setClientId(99)
      store.worksheets.orders.data = [{ order_number: 'A' }]
      store.worksheets.orders.dirty = true
      store.worksheets.instructions.content = 'Some content'
      store.activeTab = 'bom'
      store.isLoading = true
      store.globalError = 'error'
      store.mrpResults = { data: [] }
      store.activeScenario = { id: 1 }
      store.activeSchedule = { id: 2 }
      store.lastSaved = new Date()
      store.showMRPResultsDialog = true
      store.initHistory()

      store.reset()

      expect(store.clientId).toBeNull()
      expect(store.worksheets.orders.data).toEqual([])
      expect(store.worksheets.orders.dirty).toBe(false)
      expect(store.worksheets.instructions.content).toBe('')
      expect(store.worksheets.dashboardInputs.data).toEqual(getDefaultDashboardInputs())
      expect(store.activeTab).toBe('orders')
      expect(store.isLoading).toBe(false)
      expect(store.isSaving).toBe(false)
      expect(store.globalError).toBeNull()
      expect(store.mrpResults).toBeNull()
      expect(store.activeScenario).toBeNull()
      expect(store.activeSchedule).toBeNull()
      expect(store.lastSaved).toBeNull()
      expect(store.showMRPResultsDialog).toBe(false)
      expect(store.isRunningMRP).toBe(false)
      expect(store.isRunningAnalysis).toBe(false)
      expect(store.isGeneratingSchedule).toBe(false)
      expect(store.isCommittingSchedule).toBe(false)
      expect(store.isCreatingScenario).toBe(false)
    })
  })

  // =========================================================================
  // 36. Actions - discardChanges
  // =========================================================================
  describe('Actions - discardChanges', () => {
    it('reloads workbook from server', async () => {
      store.setClientId(1)
      capacityApi.loadWorkbook.mockResolvedValue(buildWorkbookResponse())

      const result = await store.discardChanges()

      expect(result).toBe(true)
      expect(capacityApi.loadWorkbook).toHaveBeenCalledWith(1)
    })

    it('returns false when no clientId', async () => {
      const result = await store.discardChanges()
      expect(result).toBe(false)
    })
  })

  // =========================================================================
  // 37. Actions - insertRow
  // =========================================================================
  describe('Actions - insertRow', () => {
    it('inserts a row at a specific index', () => {
      store.worksheets.orders.data = [
        { order_number: 'A', _id: 1 },
        { order_number: 'C', _id: 3 }
      ]

      const inserted = store.insertRow('orders', 1)

      expect(inserted).not.toBeNull()
      expect(store.worksheets.orders.data).toHaveLength(3)
      expect(store.worksheets.orders.data[1]._isNew).toBe(true)
      expect(store.worksheets.orders.data[0].order_number).toBe('A')
      expect(store.worksheets.orders.data[2].order_number).toBe('C')
    })

    it('returns null for unknown worksheet', () => {
      expect(store.insertRow('nonExistent', 0)).toBeNull()
    })
  })

  // =========================================================================
  // 38. Dirty Tracking Integration
  // =========================================================================
  describe('Dirty Tracking Integration', () => {
    it('addRow marks sheet dirty', () => {
      store.addRow('masterCalendar')
      expect(store.worksheets.masterCalendar.dirty).toBe(true)
      expect(store.hasUnsavedChanges).toBe(true)
    })

    it('updateCell marks sheet dirty', () => {
      store.worksheets.orders.data = [{ order_number: 'A' }]
      store.updateCell('orders', 0, 'order_number', 'B')
      expect(store.worksheets.orders.dirty).toBe(true)
    })

    it('removeRow marks sheet dirty', () => {
      store.worksheets.orders.data = [{ order_number: 'A' }]
      store.removeRow('orders', 0)
      expect(store.worksheets.orders.dirty).toBe(true)
    })

    it('duplicateRow marks sheet dirty', () => {
      store.worksheets.orders.data = [{ order_number: 'A' }]
      store.duplicateRow('orders', 0)
      expect(store.worksheets.orders.dirty).toBe(true)
    })

    it('importData marks sheet dirty', () => {
      store.importData('orders', [{ order_number: 'NEW' }])
      expect(store.worksheets.orders.dirty).toBe(true)
    })

    it('appendData marks sheet dirty', () => {
      store.appendData('orders', [{ order_number: 'NEW' }])
      expect(store.worksheets.orders.dirty).toBe(true)
    })

    it('updateDashboardInput marks sheet dirty', () => {
      store.updateDashboardInput('planning_horizon_days', 90)
      expect(store.worksheets.dashboardInputs.dirty).toBe(true)
    })

    it('loadWorkbook resets all dirty flags', async () => {
      store.worksheets.orders.dirty = true
      store.worksheets.bom.dirty = true
      capacityApi.loadWorkbook.mockResolvedValue(buildWorkbookResponse())

      await store.loadWorkbook(1)

      expect(store.hasUnsavedChanges).toBe(false)
    })
  })

  // =========================================================================
  // 39. initHistory
  // =========================================================================
  describe('Actions - initHistory', () => {
    it('creates history manager if not present', () => {
      expect(store._historyManager).toBeNull()
      store.initHistory()
      expect(store._historyManager).not.toBeNull()
      expect(store._historyManager.canUndo()).toBe(false)
    })

    it('does not recreate history manager if already present', () => {
      store.initHistory()
      const first = store._historyManager
      store.initHistory()
      expect(store._historyManager).toBe(first)
    })
  })
})
