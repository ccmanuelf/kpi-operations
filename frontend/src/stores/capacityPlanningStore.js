/**
 * Capacity Planning Module - Pinia Store
 *
 * State management for the 13-worksheet capacity planning workbook.
 * Manages configuration, dirty tracking, MRP results, and scenarios.
 */

import { defineStore } from 'pinia'
import * as capacityApi from '@/services/api/capacityPlanning'

// ========================================
// Default Structures for Worksheet Types
// ========================================

const getDefaultCalendarEntry = () => ({
  calendar_date: null,
  is_working_day: true,
  shifts_available: 1,
  shift1_hours: 8.0,
  shift2_hours: 0,
  shift3_hours: 0,
  holiday_name: null,
  notes: null
})

const getDefaultProductionLine = () => ({
  line_code: '',
  line_name: '',
  department: '',
  standard_capacity_units_per_hour: 0,
  max_operators: 10,
  efficiency_factor: 0.85,
  absenteeism_factor: 0.05,
  is_active: true,
  notes: null
})

const getDefaultOrder = () => ({
  order_number: '',
  customer_name: '',
  style_code: '',
  style_description: '',
  order_quantity: 0,
  completed_quantity: 0,
  order_date: null,
  required_date: null,
  planned_start_date: null,
  planned_end_date: null,
  priority: 'NORMAL',
  status: 'DRAFT',
  order_sam_minutes: null,
  notes: null
})

const getDefaultStandard = () => ({
  style_code: '',
  operation_code: '',
  operation_name: '',
  department: '',
  sam_minutes: 0,
  setup_time_minutes: 0,
  machine_time_minutes: 0,
  manual_time_minutes: 0,
  notes: null
})

const getDefaultBOMHeader = () => ({
  parent_item_code: '',
  parent_item_description: '',
  style_code: '',
  revision: '1.0',
  is_active: true,
  notes: null,
  components: []
})

const getDefaultBOMDetail = () => ({
  component_item_code: '',
  component_description: '',
  quantity_per: 1.0,
  unit_of_measure: 'EA',
  waste_percentage: 0,
  component_type: '',
  notes: null
})

const getDefaultStockSnapshot = () => ({
  snapshot_date: null,
  item_code: '',
  item_description: '',
  on_hand_quantity: 0,
  allocated_quantity: 0,
  on_order_quantity: 0,
  available_quantity: 0,
  unit_of_measure: 'EA',
  location: null,
  notes: null
})

const getDefaultComponentCheckRow = () => ({
  order_id: null,
  component_item_code: '',
  component_description: '',
  required_quantity: 0,
  available_quantity: 0,
  shortage_quantity: 0,
  total_component_demand: 0,
  status: 'AVAILABLE', // AVAILABLE, SHORTAGE, PARTIAL
  planner_notes: null,
  notes: null
})

const getDefaultCapacityAnalysisRow = () => ({
  line_id: null,
  line_code: '',
  period_date: null,
  required_hours: 0,
  available_hours: 0,
  utilization_percent: 0,
  is_bottleneck: false,
  notes: null
})

const getDefaultScheduleRow = () => ({
  schedule_detail_id: null,
  order_id: null,
  order_number: '',
  line_id: null,
  line_code: '',
  scheduled_date: null,
  planned_quantity: 0,
  sequence_number: 0,
  status: 'SCHEDULED',
  notes: null
})

const getDefaultScenario = () => ({
  scenario_name: '',
  scenario_type: 'OVERTIME', // OVERTIME, SETUP_REDUCTION, SUBCONTRACT, NEW_LINE, THREE_SHIFT, LEAD_TIME_DELAY, ABSENTEEISM_SPIKE, MULTI_CONSTRAINT
  base_schedule_id: null,
  parameters: {},
  status: 'DRAFT',
  notes: null
})

const getDefaultKPITrackingRow = () => ({
  kpi_name: '',
  target_value: 0,
  actual_value: null,
  variance_percent: null,
  period_start: null,
  period_end: null,
  status: 'PENDING',
  notes: null
})

const getDefaultDashboardInputs = () => ({
  planning_horizon_days: 30,
  default_efficiency: 85,
  bottleneck_threshold: 90,
  shortage_alert_days: 7,
  auto_schedule_enabled: false
})

// ========================================
// History Manager for Undo/Redo
// ========================================

const createHistoryManager = (maxHistory = 50) => ({
  past: [],
  future: [],
  maxHistory,

  push(state) {
    this.past.push(JSON.stringify(state))
    if (this.past.length > this.maxHistory) {
      this.past.shift()
    }
    this.future = [] // Clear redo stack on new action
  },

  undo() {
    if (this.past.length === 0) return null
    const current = this.past.pop()
    this.future.push(current)
    return this.past.length > 0 ? JSON.parse(this.past[this.past.length - 1]) : null
  },

  redo() {
    if (this.future.length === 0) return null
    const state = this.future.pop()
    this.past.push(state)
    return JSON.parse(state)
  },

  canUndo() {
    return this.past.length > 0
  },

  canRedo() {
    return this.future.length > 0
  },

  clear() {
    this.past = []
    this.future = []
  }
})

// ========================================
// Store Definition
// ========================================

export const useCapacityPlanningStore = defineStore('capacityPlanning', {
  state: () => ({
    // Current client context
    clientId: null,

    // 13 worksheets with dirty tracking
    worksheets: {
      masterCalendar: { data: [], dirty: false, loading: false, error: null },
      productionLines: { data: [], dirty: false, loading: false, error: null },
      orders: { data: [], dirty: false, loading: false, error: null },
      productionStandards: { data: [], dirty: false, loading: false, error: null },
      bom: { data: [], dirty: false, loading: false, error: null },
      stockSnapshot: { data: [], dirty: false, loading: false, error: null },
      componentCheck: { data: [], dirty: false, loading: false, error: null },
      capacityAnalysis: { data: [], dirty: false, loading: false, error: null },
      productionSchedule: { data: [], dirty: false, loading: false, error: null },
      whatIfScenarios: { data: [], dirty: false, loading: false, error: null },
      dashboardInputs: { data: getDefaultDashboardInputs(), dirty: false, loading: false, error: null },
      kpiTracking: { data: [], dirty: false, loading: false, error: null },
      instructions: { content: '', dirty: false, loading: false, error: null }
    },

    // UI state
    activeTab: 'orders',
    showMRPResultsDialog: false,
    showScenarioCompareDialog: false,
    showScheduleCommitDialog: false,
    showExportDialog: false,
    showImportDialog: false,

    // MRP/Component Check state
    mrpResults: null,
    isRunningMRP: false,
    mrpError: null,

    // Scenario state
    activeScenario: null,
    scenarioComparisonResults: null,
    isCreatingScenario: false,

    // Schedule state
    activeSchedule: null,
    isGeneratingSchedule: false,
    isCommittingSchedule: false,

    // Analysis state
    analysisResults: null,
    isRunningAnalysis: false,

    // Global state
    isLoading: false,
    isSaving: false,
    globalError: null,
    lastSaved: null,

    // History for undo/redo (managed externally)
    _historyManager: null
  }),

  getters: {
    // ========================================
    // Dirty State Getters
    // ========================================

    /**
     * Check if any worksheet has unsaved changes
     */
    hasUnsavedChanges: (state) => {
      return Object.values(state.worksheets).some(ws => ws.dirty)
    },

    /**
     * Get list of worksheets with unsaved changes
     */
    dirtyWorksheets: (state) => {
      return Object.entries(state.worksheets)
        .filter(([, ws]) => ws.dirty)
        .map(([name]) => name)
    },

    /**
     * Get count of dirty worksheets
     */
    dirtyCount: (state) => {
      return Object.values(state.worksheets).filter(ws => ws.dirty).length
    },

    // ========================================
    // Component Check Getters
    // ========================================

    /**
     * Get components with shortages
     */
    shortageComponents: (state) => {
      return state.worksheets.componentCheck.data.filter(c => c.status === 'SHORTAGE')
    },

    /**
     * Get count of shortages
     */
    shortageCount: (state) => {
      return state.worksheets.componentCheck.data.filter(c => c.status === 'SHORTAGE').length
    },

    /**
     * Get components with partial availability
     */
    partialComponents: (state) => {
      return state.worksheets.componentCheck.data.filter(c => c.status === 'PARTIAL')
    },

    // ========================================
    // Capacity Analysis Getters
    // ========================================

    /**
     * Get bottleneck lines from analysis
     */
    bottleneckLines: (state) => {
      return state.worksheets.capacityAnalysis.data.filter(a => a.is_bottleneck)
    },

    /**
     * Get lines with overload (>100% utilization)
     */
    overloadedLines: (state) => {
      return state.worksheets.capacityAnalysis.data.filter(a =>
        parseFloat(a.utilization_percent) > 100
      )
    },

    /**
     * Get average utilization across all lines
     */
    averageUtilization: (state) => {
      const data = state.worksheets.capacityAnalysis.data
      if (data.length === 0) return 0
      const sum = data.reduce((acc, a) => acc + (parseFloat(a.utilization_percent) || 0), 0)
      return (sum / data.length).toFixed(1)
    },

    // ========================================
    // Order Getters
    // ========================================

    /**
     * Get orders ready for scheduling
     */
    schedulableOrders: (state) => {
      return state.worksheets.orders.data.filter(o =>
        ['DRAFT', 'CONFIRMED'].includes(o.status)
      )
    },

    /**
     * Get total order quantity across all orders
     */
    totalOrderQuantity: (state) => {
      return state.worksheets.orders.data.reduce((sum, o) =>
        sum + (parseInt(o.order_quantity) || 0), 0
      )
    },

    /**
     * Get orders grouped by status
     */
    ordersByStatus: (state) => {
      const grouped = {}
      for (const order of state.worksheets.orders.data) {
        const status = order.status || 'UNKNOWN'
        if (!grouped[status]) {
          grouped[status] = []
        }
        grouped[status].push(order)
      }
      return grouped
    },

    /**
     * Get orders count by priority
     */
    orderPriorityCounts: (state) => {
      const counts = { CRITICAL: 0, HIGH: 0, NORMAL: 0, LOW: 0 }
      for (const order of state.worksheets.orders.data) {
        const priority = order.priority || 'NORMAL'
        if (counts[priority] !== undefined) {
          counts[priority]++
        }
      }
      return counts
    },

    // ========================================
    // Production Line Getters
    // ========================================

    /**
     * Get active production lines count
     */
    activeLineCount: (state) => {
      return state.worksheets.productionLines.data.filter(l => l.is_active).length
    },

    /**
     * Get inactive production lines
     */
    inactiveLines: (state) => {
      return state.worksheets.productionLines.data.filter(l => !l.is_active)
    },

    /**
     * Get total available capacity (units/hour)
     */
    totalCapacity: (state) => {
      return state.worksheets.productionLines.data
        .filter(l => l.is_active)
        .reduce((sum, l) => sum + (parseFloat(l.standard_capacity_units_per_hour) || 0), 0)
    },

    // ========================================
    // Calendar Getters
    // ========================================

    /**
     * Get working days count in calendar
     */
    workingDaysCount: (state) => {
      return state.worksheets.masterCalendar.data.filter(d => d.is_working_day).length
    },

    /**
     * Get holidays list
     */
    holidays: (state) => {
      return state.worksheets.masterCalendar.data.filter(d => d.holiday_name)
    },

    // ========================================
    // KPI Getters
    // ========================================

    /**
     * Get KPI variance summary
     */
    kpiVarianceSummary: (state) => {
      const tracking = state.worksheets.kpiTracking.data
      if (!tracking.length) return null

      return {
        totalKPIs: tracking.length,
        onTarget: tracking.filter(k => Math.abs(k.variance_percent || 0) <= 5).length,
        offTarget: tracking.filter(k => Math.abs(k.variance_percent || 0) > 5).length,
        critical: tracking.filter(k => Math.abs(k.variance_percent || 0) > 10).length
      }
    },

    /**
     * Get KPIs that are off target
     */
    offTargetKPIs: (state) => {
      return state.worksheets.kpiTracking.data.filter(k =>
        Math.abs(k.variance_percent || 0) > 5
      )
    },

    // ========================================
    // Scenario Getters
    // ========================================

    /**
     * Get scenarios by type
     */
    scenariosByType: (state) => {
      const grouped = {}
      for (const scenario of state.worksheets.whatIfScenarios.data) {
        const type = scenario.scenario_type || 'other'
        if (!grouped[type]) {
          grouped[type] = []
        }
        grouped[type].push(scenario)
      }
      return grouped
    },

    // ========================================
    // BOM Getters
    // ========================================

    /**
     * Get BOM count
     */
    bomCount: (state) => {
      return state.worksheets.bom.data.length
    },

    /**
     * Get unique styles with BOM
     */
    stylesWithBOM: (state) => {
      return [...new Set(state.worksheets.bom.data.map(b => b.style_code))].filter(Boolean)
    },

    // ========================================
    // Undo/Redo Getters
    // ========================================

    canUndo: (state) => {
      return state._historyManager?.canUndo() || false
    },

    canRedo: (state) => {
      return state._historyManager?.canRedo() || false
    }
  },

  actions: {
    // ========================================
    // Initialization
    // ========================================

    /**
     * Initialize history manager
     */
    initHistory() {
      if (!this._historyManager) {
        this._historyManager = createHistoryManager(50)
      }
    },

    /**
     * Set current client ID
     */
    setClientId(clientId) {
      this.clientId = clientId
    },

    /**
     * Load complete workbook for a client
     */
    async loadWorkbook(clientId = null) {
      const targetClientId = clientId || this.clientId
      if (!targetClientId) {
        throw new Error('Client ID is required')
      }

      this.clientId = targetClientId
      this.isLoading = true
      this.globalError = null

      try {
        const workbook = await capacityApi.loadWorkbook(targetClientId)

        // Populate all worksheets from response
        const worksheetMapping = {
          masterCalendar: 'master_calendar',
          productionLines: 'production_lines',
          orders: 'orders',
          productionStandards: 'production_standards',
          bom: 'bom',
          stockSnapshot: 'stock_snapshot',
          componentCheck: 'component_check',
          capacityAnalysis: 'capacity_analysis',
          productionSchedule: 'production_schedule',
          whatIfScenarios: 'what_if_scenarios',
          dashboardInputs: 'dashboard_inputs',
          kpiTracking: 'kpi_tracking',
          instructions: 'instructions'
        }

        for (const [storeKey, apiKey] of Object.entries(worksheetMapping)) {
          if (workbook[apiKey]) {
            if (storeKey === 'instructions') {
              this.worksheets[storeKey].content = workbook[apiKey]
            } else if (storeKey === 'dashboardInputs') {
              this.worksheets[storeKey].data = { ...getDefaultDashboardInputs(), ...workbook[apiKey] }
            } else {
              this.worksheets[storeKey].data = workbook[apiKey].map((row, idx) => ({
                ...row,
                _id: row.id || (Date.now() + idx)
              }))
            }
          }
        }

        // Reset dirty flags and errors
        Object.values(this.worksheets).forEach(ws => {
          ws.dirty = false
          ws.error = null
        })

        // Initialize history
        this.initHistory()
        this._historyManager.clear()

        return workbook
      } catch (error) {
        this.globalError = error.message || 'Failed to load workbook'
        throw error
      } finally {
        this.isLoading = false
      }
    },

    // ========================================
    // Cell/Row Operations with History
    // ========================================

    /**
     * Save current state to history before modification
     */
    _saveToHistory(worksheetName) {
      if (!this._historyManager) {
        this.initHistory()
      }
      const worksheet = this.worksheets[worksheetName]
      if (worksheet) {
        this._historyManager.push({
          worksheetName,
          data: JSON.parse(JSON.stringify(worksheet.data))
        })
      }
    },

    /**
     * Update a single cell in a worksheet
     */
    updateCell(worksheetName, rowIndex, field, value) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet || !worksheet.data[rowIndex]) return

      this._saveToHistory(worksheetName)
      worksheet.data[rowIndex][field] = value
      worksheet.dirty = true
    },

    /**
     * Update multiple cells in a row
     */
    updateRow(worksheetName, rowIndex, updates) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet || !worksheet.data[rowIndex]) return

      this._saveToHistory(worksheetName)
      Object.assign(worksheet.data[rowIndex], updates)
      worksheet.dirty = true
    },

    /**
     * Add a new row to a worksheet
     */
    addRow(worksheetName) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return null

      this._saveToHistory(worksheetName)

      let newRow
      switch (worksheetName) {
        case 'masterCalendar':
          newRow = getDefaultCalendarEntry()
          break
        case 'productionLines':
          newRow = getDefaultProductionLine()
          break
        case 'orders':
          newRow = getDefaultOrder()
          break
        case 'productionStandards':
          newRow = getDefaultStandard()
          break
        case 'bom':
          newRow = getDefaultBOMHeader()
          break
        case 'stockSnapshot':
          newRow = getDefaultStockSnapshot()
          break
        case 'componentCheck':
          newRow = getDefaultComponentCheckRow()
          break
        case 'capacityAnalysis':
          newRow = getDefaultCapacityAnalysisRow()
          break
        case 'productionSchedule':
          newRow = getDefaultScheduleRow()
          break
        case 'whatIfScenarios':
          newRow = getDefaultScenario()
          break
        case 'kpiTracking':
          newRow = getDefaultKPITrackingRow()
          break
        default:
          newRow = {}
      }

      newRow._id = Date.now()
      newRow._isNew = true
      worksheet.data.push(newRow)
      worksheet.dirty = true

      return newRow
    },

    /**
     * Insert a row at a specific index
     */
    insertRow(worksheetName, index, row = null) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return null

      this._saveToHistory(worksheetName)

      const newRow = row || this.addRow(worksheetName)
      if (newRow && index >= 0 && index < worksheet.data.length) {
        // Remove from end (where addRow placed it)
        worksheet.data.pop()
        // Insert at desired position
        worksheet.data.splice(index, 0, newRow)
      }

      return newRow
    },

    /**
     * Remove a row from a worksheet
     */
    removeRow(worksheetName, rowIndex) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet || rowIndex < 0 || rowIndex >= worksheet.data.length) return false

      this._saveToHistory(worksheetName)
      worksheet.data.splice(rowIndex, 1)
      worksheet.dirty = true

      return true
    },

    /**
     * Remove multiple rows by indices
     */
    removeRows(worksheetName, indices) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return false

      this._saveToHistory(worksheetName)

      // Sort indices descending to remove from end first
      const sortedIndices = [...indices].sort((a, b) => b - a)
      for (const idx of sortedIndices) {
        if (idx >= 0 && idx < worksheet.data.length) {
          worksheet.data.splice(idx, 1)
        }
      }

      worksheet.dirty = true
      return true
    },

    /**
     * Duplicate a row
     */
    duplicateRow(worksheetName, rowIndex) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet || rowIndex < 0 || rowIndex >= worksheet.data.length) return null

      this._saveToHistory(worksheetName)

      const original = worksheet.data[rowIndex]
      const duplicate = {
        ...JSON.parse(JSON.stringify(original)),
        _id: Date.now(),
        _isNew: true
      }

      // Clear identifiers that should be unique
      delete duplicate.id
      if (duplicate.order_number) {
        duplicate.order_number = `${duplicate.order_number}-COPY`
      }
      if (duplicate.line_code) {
        duplicate.line_code = `${duplicate.line_code}-COPY`
      }

      worksheet.data.splice(rowIndex + 1, 0, duplicate)
      worksheet.dirty = true

      return duplicate
    },

    /**
     * Import data into a worksheet (replaces existing data)
     */
    importData(worksheetName, data) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return false

      this._saveToHistory(worksheetName)

      worksheet.data = data.map((row, idx) => ({
        ...row,
        _id: row.id || (Date.now() + idx),
        _imported: true
      }))
      worksheet.dirty = true

      return true
    },

    /**
     * Merge imported data with existing (append)
     */
    appendData(worksheetName, data) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return false

      this._saveToHistory(worksheetName)

      const newRows = data.map((row, idx) => ({
        ...row,
        _id: row.id || (Date.now() + idx),
        _imported: true
      }))

      worksheet.data = [...worksheet.data, ...newRows]
      worksheet.dirty = true

      return true
    },

    // ========================================
    // Undo/Redo Operations
    // ========================================

    /**
     * Undo last change
     */
    undo() {
      if (!this._historyManager?.canUndo()) return false

      const previousState = this._historyManager.undo()
      if (previousState && previousState.worksheetName) {
        const worksheet = this.worksheets[previousState.worksheetName]
        if (worksheet) {
          worksheet.data = previousState.data
          worksheet.dirty = true
        }
      }

      return true
    },

    /**
     * Redo previously undone change
     */
    redo() {
      if (!this._historyManager?.canRedo()) return false

      const nextState = this._historyManager.redo()
      if (nextState && nextState.worksheetName) {
        const worksheet = this.worksheets[nextState.worksheetName]
        if (worksheet) {
          worksheet.data = nextState.data
          worksheet.dirty = true
        }
      }

      return true
    },

    // ========================================
    // Save Operations
    // ========================================

    /**
     * Save a single worksheet
     */
    async saveWorksheet(worksheetName) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet || !this.clientId) return false

      worksheet.loading = true
      worksheet.error = null

      try {
        const dataToSave = worksheetName === 'instructions'
          ? worksheet.content
          : worksheet.data

        await capacityApi.saveWorksheet(worksheetName, this.clientId, dataToSave)
        worksheet.dirty = false
        this.lastSaved = new Date()

        // Clear _isNew flags
        if (Array.isArray(worksheet.data)) {
          worksheet.data.forEach(row => {
            delete row._isNew
            delete row._imported
          })
        }

        return true
      } catch (error) {
        worksheet.error = error.message || 'Failed to save'
        throw error
      } finally {
        worksheet.loading = false
      }
    },

    /**
     * Save all worksheets with unsaved changes
     */
    async saveAllDirty() {
      this.isSaving = true
      const results = { success: [], failed: [] }

      for (const [name, worksheet] of Object.entries(this.worksheets)) {
        if (worksheet.dirty) {
          try {
            await this.saveWorksheet(name)
            results.success.push(name)
          } catch (error) {
            results.failed.push({ name, error: error.message })
          }
        }
      }

      this.isSaving = false
      return results
    },

    /**
     * Save complete workbook (all worksheets)
     */
    async saveWorkbook() {
      if (!this.clientId) return false

      this.isSaving = true
      this.globalError = null

      try {
        const workbookData = {}

        for (const [key, worksheet] of Object.entries(this.worksheets)) {
          if (key === 'instructions') {
            workbookData[key] = worksheet.content
          } else {
            workbookData[key] = worksheet.data
          }
        }

        await capacityApi.saveWorkbook(this.clientId, workbookData)

        // Reset all dirty flags
        Object.values(this.worksheets).forEach(ws => {
          ws.dirty = false
        })

        this.lastSaved = new Date()
        return true
      } catch (error) {
        this.globalError = error.message || 'Failed to save workbook'
        throw error
      } finally {
        this.isSaving = false
      }
    },

    // ========================================
    // MRP / Component Check
    // ========================================

    /**
     * Run component requirements check (MRP explosion)
     */
    async runComponentCheck(orderIds = null) {
      if (!this.clientId) return null

      this.isRunningMRP = true
      this.mrpError = null
      this.mrpResults = null

      try {
        const results = await capacityApi.runComponentCheck(this.clientId, orderIds)
        this.mrpResults = results

        // Update component check worksheet with results
        if (results.components) {
          this.worksheets.componentCheck.data = results.components.map((c, idx) => ({
            ...c,
            _id: c.id || (Date.now() + idx)
          }))
        }

        this.showMRPResultsDialog = true
        return results
      } catch (error) {
        this.mrpError = error.message || 'Component check failed'
        throw error
      } finally {
        this.isRunningMRP = false
      }
    },

    /**
     * Clear MRP results
     */
    clearMRPResults() {
      this.mrpResults = null
      this.mrpError = null
      this.showMRPResultsDialog = false
    },

    // ========================================
    // BOM Operations
    // ========================================

    /**
     * Explode BOM for a parent item
     */
    async explodeBOM(parentItemCode, quantity) {
      if (!this.clientId) return null

      try {
        const result = await capacityApi.explodeBOM(this.clientId, parentItemCode, quantity)
        return result
      } catch (error) {
        throw error
      }
    },

    /**
     * Add a component to a BOM
     */
    addBOMComponent(bomIndex) {
      const bom = this.worksheets.bom.data[bomIndex]
      if (!bom) return null

      this._saveToHistory('bom')

      if (!bom.components) {
        bom.components = []
      }

      const newComponent = {
        ...getDefaultBOMDetail(),
        _id: Date.now()
      }

      bom.components.push(newComponent)
      this.worksheets.bom.dirty = true

      return newComponent
    },

    /**
     * Remove a component from a BOM
     */
    removeBOMComponent(bomIndex, componentIndex) {
      const bom = this.worksheets.bom.data[bomIndex]
      if (!bom || !bom.components || componentIndex < 0) return false

      this._saveToHistory('bom')
      bom.components.splice(componentIndex, 1)
      this.worksheets.bom.dirty = true

      return true
    },

    // ========================================
    // Capacity Analysis
    // ========================================

    /**
     * Run capacity analysis for date range
     */
    async runCapacityAnalysis(startDate, endDate, lineIds = null) {
      if (!this.clientId) return null

      this.isRunningAnalysis = true

      try {
        const results = await capacityApi.runCapacityAnalysis(
          this.clientId, startDate, endDate, lineIds
        )
        this.analysisResults = results

        // Update analysis worksheet with results
        if (results.line_results) {
          this.worksheets.capacityAnalysis.data = results.line_results.map((r, idx) => ({
            ...r,
            _id: r.id || (Date.now() + idx)
          }))
        }

        return results
      } catch (error) {
        throw error
      } finally {
        this.isRunningAnalysis = false
      }
    },

    /**
     * Clear analysis results
     */
    clearAnalysisResults() {
      this.analysisResults = null
    },

    // ========================================
    // Schedule Operations
    // ========================================

    /**
     * Generate a new production schedule
     */
    async generateSchedule(name, startDate, endDate, orderIds = null) {
      if (!this.clientId) return null

      this.isGeneratingSchedule = true

      try {
        const schedule = await capacityApi.generateSchedule(
          this.clientId, name, startDate, endDate, orderIds
        )
        this.activeSchedule = schedule

        // Update schedule worksheet with details
        if (schedule.details) {
          this.worksheets.productionSchedule.data = schedule.details.map((d, idx) => ({
            ...d,
            _id: d.id || (Date.now() + idx)
          }))
        }

        return schedule
      } catch (error) {
        throw error
      } finally {
        this.isGeneratingSchedule = false
      }
    },

    /**
     * Commit a schedule with KPI commitments
     */
    async commitSchedule(scheduleId, kpiCommitments) {
      if (!this.clientId) return null

      this.isCommittingSchedule = true
      this.showScheduleCommitDialog = false

      try {
        const result = await capacityApi.commitSchedule(scheduleId, kpiCommitments)

        // Update KPI tracking worksheet with commitments
        if (result.kpi_commitments) {
          this.worksheets.kpiTracking.data = result.kpi_commitments.map((k, idx) => ({
            ...k,
            _id: k.id || (Date.now() + idx)
          }))
        }

        // Update schedule status
        if (this.activeSchedule && this.activeSchedule.id === scheduleId) {
          this.activeSchedule.status = 'COMMITTED'
        }

        return result
      } catch (error) {
        throw error
      } finally {
        this.isCommittingSchedule = false
      }
    },

    /**
     * Load existing schedule
     */
    async loadSchedule(scheduleId) {
      if (!this.clientId) return null

      try {
        const schedule = await capacityApi.getSchedule(scheduleId)
        this.activeSchedule = schedule

        if (schedule.details) {
          this.worksheets.productionSchedule.data = schedule.details.map((d, idx) => ({
            ...d,
            _id: d.id || (Date.now() + idx)
          }))
        }

        return schedule
      } catch (error) {
        throw error
      }
    },

    // ========================================
    // Scenario Operations
    // ========================================

    /**
     * Create a what-if scenario
     */
    async createScenario(name, type, parameters, baseScheduleId = null) {
      if (!this.clientId) return null

      this.isCreatingScenario = true

      try {
        const scenario = await capacityApi.createScenario(
          this.clientId, name, type, parameters, baseScheduleId
        )

        // Add to scenarios worksheet
        this.worksheets.whatIfScenarios.data.push({
          ...scenario,
          _id: scenario.id || Date.now()
        })
        this.worksheets.whatIfScenarios.dirty = true

        this.activeScenario = scenario
        return scenario
      } catch (error) {
        throw error
      } finally {
        this.isCreatingScenario = false
      }
    },

    /**
     * Run/evaluate a scenario
     */
    async runScenario(scenarioId) {
      if (!this.clientId) return null

      try {
        const results = await capacityApi.runScenario(this.clientId, scenarioId)

        // Update scenario in list with results
        const idx = this.worksheets.whatIfScenarios.data.findIndex(s => s.id === scenarioId)
        if (idx !== -1) {
          this.worksheets.whatIfScenarios.data[idx] = {
            ...this.worksheets.whatIfScenarios.data[idx],
            ...results,
            status: 'EVALUATED'
          }
        }

        return results
      } catch (error) {
        throw error
      }
    },

    /**
     * Compare multiple scenarios
     */
    async compareScenarios(scenarioIds) {
      if (!this.clientId) return null

      try {
        const results = await capacityApi.compareScenarios(this.clientId, scenarioIds)
        this.scenarioComparisonResults = results
        this.showScenarioCompareDialog = true
        return results
      } catch (error) {
        throw error
      }
    },

    /**
     * Delete a scenario
     */
    async deleteScenario(scenarioId) {
      try {
        await capacityApi.deleteScenario(this.clientId, scenarioId)

        // Remove from local list
        const idx = this.worksheets.whatIfScenarios.data.findIndex(s => s.id === scenarioId)
        if (idx !== -1) {
          this.worksheets.whatIfScenarios.data.splice(idx, 1)
        }

        if (this.activeScenario?.id === scenarioId) {
          this.activeScenario = null
        }

        return true
      } catch (error) {
        throw error
      }
    },

    // ========================================
    // KPI Integration
    // ========================================

    /**
     * Load KPI actual values for a period
     */
    async loadKPIActuals(period) {
      if (!this.clientId) return null

      try {
        const actuals = await capacityApi.getKPIActuals(this.clientId, period)

        // Update KPI tracking with actuals
        if (actuals && Array.isArray(actuals)) {
          for (const actual of actuals) {
            const kpi = this.worksheets.kpiTracking.data.find(k => k.kpi_name === actual.kpi_name)
            if (kpi) {
              kpi.actual_value = actual.value
              kpi.variance_percent = kpi.target_value
                ? ((actual.value - kpi.target_value) / kpi.target_value * 100).toFixed(1)
                : null
            }
          }
        }

        return actuals
      } catch (error) {
        throw error
      }
    },

    // ========================================
    // Export/Import Operations
    // ========================================

    /**
     * Export worksheet data as JSON
     */
    exportWorksheetJSON(worksheetName) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return null

      const data = worksheetName === 'instructions' ? worksheet.content : worksheet.data

      // Remove internal fields
      const cleanData = Array.isArray(data)
        ? data.map(row => {
            const { _id, _isNew, _imported, ...clean } = row
            return clean
          })
        : data

      return JSON.stringify(cleanData, null, 2)
    },

    /**
     * Export all worksheets as complete workbook JSON
     */
    exportWorkbookJSON() {
      const workbook = {}

      for (const [key, worksheet] of Object.entries(this.worksheets)) {
        if (key === 'instructions') {
          workbook[key] = worksheet.content
        } else {
          workbook[key] = Array.isArray(worksheet.data)
            ? worksheet.data.map(row => {
                const { _id, _isNew, _imported, ...clean } = row
                return clean
              })
            : worksheet.data
        }
      }

      return JSON.stringify(workbook, null, 2)
    },

    // ========================================
    // Dashboard Inputs
    // ========================================

    /**
     * Update dashboard input setting
     */
    updateDashboardInput(key, value) {
      this._saveToHistory('dashboardInputs')
      this.worksheets.dashboardInputs.data[key] = value
      this.worksheets.dashboardInputs.dirty = true
    },

    // ========================================
    // UI State
    // ========================================

    /**
     * Set active worksheet tab
     */
    setActiveTab(tab) {
      this.activeTab = tab
    },

    /**
     * Clear all errors
     */
    clearError() {
      this.globalError = null
      Object.values(this.worksheets).forEach(ws => {
        ws.error = null
      })
      this.mrpError = null
    },

    /**
     * Close all dialogs
     */
    closeAllDialogs() {
      this.showMRPResultsDialog = false
      this.showScenarioCompareDialog = false
      this.showScheduleCommitDialog = false
      this.showExportDialog = false
      this.showImportDialog = false
    },

    // ========================================
    // Reset
    // ========================================

    /**
     * Reset store to initial state
     */
    reset() {
      this.clientId = null

      // Reset all worksheets
      Object.keys(this.worksheets).forEach(key => {
        if (key === 'instructions') {
          this.worksheets[key] = { content: '', dirty: false, loading: false, error: null }
        } else if (key === 'dashboardInputs') {
          this.worksheets[key] = {
            data: getDefaultDashboardInputs(),
            dirty: false,
            loading: false,
            error: null
          }
        } else {
          this.worksheets[key] = { data: [], dirty: false, loading: false, error: null }
        }
      })

      // Reset UI state
      this.activeTab = 'orders'
      this.showMRPResultsDialog = false
      this.showScenarioCompareDialog = false
      this.showScheduleCommitDialog = false
      this.showExportDialog = false
      this.showImportDialog = false

      // Reset operation state
      this.mrpResults = null
      this.mrpError = null
      this.analysisResults = null
      this.activeScenario = null
      this.scenarioComparisonResults = null
      this.activeSchedule = null

      // Reset global state
      this.globalError = null
      this.lastSaved = null
      this.isLoading = false
      this.isSaving = false
      this.isRunningMRP = false
      this.isRunningAnalysis = false
      this.isGeneratingSchedule = false
      this.isCommittingSchedule = false
      this.isCreatingScenario = false

      // Clear history
      if (this._historyManager) {
        this._historyManager.clear()
      }
    },

    /**
     * Discard changes and reload from server
     */
    async discardChanges() {
      if (!this.clientId) return false

      await this.loadWorkbook(this.clientId)
      return true
    }
  }
})

// ========================================
// Helper Exports
// ========================================

export {
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
}
