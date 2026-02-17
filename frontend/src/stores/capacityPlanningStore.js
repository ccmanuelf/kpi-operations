/**
 * Capacity Planning Module - Pinia Store (Composed)
 *
 * State management for the 13-worksheet capacity planning workbook.
 * This is the public entry point that all consumers import from.
 *
 * Internally delegates to three sub-stores:
 *   - useWorksheetOpsStore  (worksheet CRUD, undo/redo, dirty tracking)
 *   - useWorkbookStore      (load/save workbook, clientId)
 *   - useAnalysisStore      (MRP, analysis, schedules, scenarios, KPI)
 *
 * Uses the Pinia composition (setup) API so every property exposed is a ref
 * or computed, preserving full read/write backward compatibility.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useWorksheetOpsStore } from './capacity/useWorksheetOps'
import { useWorkbookStore } from './capacity/useWorkbookStore'
import { useAnalysisStore } from './capacity/useAnalysisStore'

// Re-export defaults for consumers that import them directly
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
} from './capacity/defaults'

export const useCapacityPlanningStore = defineStore('capacityPlanning', () => {
  // ========================================
  // Sub-store references (lazy, resolved per call)
  // ========================================

  const _wsOps = () => useWorksheetOpsStore()
  const _wb = () => useWorkbookStore()
  const _analysis = () => useAnalysisStore()

  // ========================================
  // Local UI-only state
  // ========================================

  const activeTab = ref('orders')
  const showExportDialog = ref(false)
  const showImportDialog = ref(false)

  // ========================================
  // Worksheet state (delegated, writable)
  // ========================================

  const worksheets = computed(() => _wsOps().worksheets)

  // ========================================
  // Dirty tracking getters (delegated, read-only)
  // ========================================

  const hasUnsavedChanges = computed(() => _wsOps().hasUnsavedChanges)
  const dirtyWorksheets = computed(() => _wsOps().dirtyWorksheets)
  const dirtyCount = computed(() => _wsOps().dirtyCount)

  // ========================================
  // Undo/Redo getters
  // ========================================

  const canUndo = computed(() => _wsOps().canUndo)
  const canRedo = computed(() => _wsOps().canRedo)
  const _historyManager = computed(() => _wsOps()._historyManager)

  // ========================================
  // Workbook state (delegated, writable via computed get/set)
  // ========================================

  const clientId = computed({
    get: () => _wb().clientId,
    set: (val) => { _wb().clientId = val }
  })

  const isLoading = computed({
    get: () => _wb().isLoading,
    set: (val) => { _wb().isLoading = val }
  })

  const isSaving = computed({
    get: () => _wb().isSaving,
    set: (val) => { _wb().isSaving = val }
  })

  const globalError = computed({
    get: () => _wb().globalError,
    set: (val) => { _wb().globalError = val }
  })

  const lastSaved = computed({
    get: () => _wb().lastSaved,
    set: (val) => { _wb().lastSaved = val }
  })

  // ========================================
  // Analysis state (delegated, writable via computed get/set)
  // ========================================

  const mrpResults = computed({
    get: () => _analysis().mrpResults,
    set: (val) => { _analysis().mrpResults = val }
  })

  const isRunningMRP = computed({
    get: () => _analysis().isRunningMRP,
    set: (val) => { _analysis().isRunningMRP = val }
  })

  const mrpError = computed({
    get: () => _analysis().mrpError,
    set: (val) => { _analysis().mrpError = val }
  })

  const showMRPResultsDialog = computed({
    get: () => _analysis().showMRPResultsDialog,
    set: (val) => { _analysis().showMRPResultsDialog = val }
  })

  const activeScenario = computed({
    get: () => _analysis().activeScenario,
    set: (val) => { _analysis().activeScenario = val }
  })

  const scenarioComparisonResults = computed({
    get: () => _analysis().scenarioComparisonResults,
    set: (val) => { _analysis().scenarioComparisonResults = val }
  })

  const isCreatingScenario = computed({
    get: () => _analysis().isCreatingScenario,
    set: (val) => { _analysis().isCreatingScenario = val }
  })

  const showScenarioCompareDialog = computed({
    get: () => _analysis().showScenarioCompareDialog,
    set: (val) => { _analysis().showScenarioCompareDialog = val }
  })

  const activeSchedule = computed({
    get: () => _analysis().activeSchedule,
    set: (val) => { _analysis().activeSchedule = val }
  })

  const isGeneratingSchedule = computed({
    get: () => _analysis().isGeneratingSchedule,
    set: (val) => { _analysis().isGeneratingSchedule = val }
  })

  const isCommittingSchedule = computed({
    get: () => _analysis().isCommittingSchedule,
    set: (val) => { _analysis().isCommittingSchedule = val }
  })

  const showScheduleCommitDialog = computed({
    get: () => _analysis().showScheduleCommitDialog,
    set: (val) => { _analysis().showScheduleCommitDialog = val }
  })

  const analysisResults = computed({
    get: () => _analysis().analysisResults,
    set: (val) => { _analysis().analysisResults = val }
  })

  const isRunningAnalysis = computed({
    get: () => _analysis().isRunningAnalysis,
    set: (val) => { _analysis().isRunningAnalysis = val }
  })

  // ========================================
  // Component Check getters
  // ========================================

  const shortageComponents = computed(() =>
    _wsOps().worksheets.componentCheck.data.filter(c => c.status === 'SHORTAGE')
  )

  const shortageCount = computed(() =>
    _wsOps().worksheets.componentCheck.data.filter(c => c.status === 'SHORTAGE').length
  )

  const partialComponents = computed(() =>
    _wsOps().worksheets.componentCheck.data.filter(c => c.status === 'PARTIAL')
  )

  // ========================================
  // Capacity Analysis getters
  // ========================================

  const bottleneckLines = computed(() =>
    _wsOps().worksheets.capacityAnalysis.data.filter(a => a.is_bottleneck)
  )

  const overloadedLines = computed(() =>
    _wsOps().worksheets.capacityAnalysis.data.filter(a =>
      parseFloat(a.utilization_percent) > 100
    )
  )

  const averageUtilization = computed(() => {
    const data = _wsOps().worksheets.capacityAnalysis.data
    if (data.length === 0) return 0
    const sum = data.reduce((acc, a) => acc + (parseFloat(a.utilization_percent) || 0), 0)
    return (sum / data.length).toFixed(1)
  })

  // ========================================
  // Order getters
  // ========================================

  const schedulableOrders = computed(() =>
    _wsOps().worksheets.orders.data.filter(o =>
      ['DRAFT', 'CONFIRMED'].includes(o.status)
    )
  )

  const totalOrderQuantity = computed(() =>
    _wsOps().worksheets.orders.data.reduce((sum, o) =>
      sum + (parseInt(o.order_quantity) || 0), 0
    )
  )

  const ordersByStatus = computed(() => {
    const grouped = {}
    for (const order of _wsOps().worksheets.orders.data) {
      const status = order.status || 'UNKNOWN'
      if (!grouped[status]) {
        grouped[status] = []
      }
      grouped[status].push(order)
    }
    return grouped
  })

  const orderPriorityCounts = computed(() => {
    const counts = { CRITICAL: 0, HIGH: 0, NORMAL: 0, LOW: 0 }
    for (const order of _wsOps().worksheets.orders.data) {
      const priority = order.priority || 'NORMAL'
      if (counts[priority] !== undefined) {
        counts[priority]++
      }
    }
    return counts
  })

  // ========================================
  // Production Line getters
  // ========================================

  const activeLineCount = computed(() =>
    _wsOps().worksheets.productionLines.data.filter(l => l.is_active).length
  )

  const inactiveLines = computed(() =>
    _wsOps().worksheets.productionLines.data.filter(l => !l.is_active)
  )

  const totalCapacity = computed(() =>
    _wsOps().worksheets.productionLines.data
      .filter(l => l.is_active)
      .reduce((sum, l) => sum + (parseFloat(l.standard_capacity_units_per_hour) || 0), 0)
  )

  // ========================================
  // Calendar getters
  // ========================================

  const workingDaysCount = computed(() =>
    _wsOps().worksheets.masterCalendar.data.filter(d => d.is_working_day).length
  )

  const holidays = computed(() =>
    _wsOps().worksheets.masterCalendar.data.filter(d => d.holiday_name)
  )

  // ========================================
  // KPI getters
  // ========================================

  const kpiVarianceSummary = computed(() => {
    const tracking = _wsOps().worksheets.kpiTracking.data
    if (!tracking.length) return null

    return {
      totalKPIs: tracking.length,
      onTarget: tracking.filter(k => Math.abs(k.variance_percent || 0) <= 5).length,
      offTarget: tracking.filter(k => Math.abs(k.variance_percent || 0) > 5).length,
      critical: tracking.filter(k => Math.abs(k.variance_percent || 0) > 10).length
    }
  })

  const offTargetKPIs = computed(() =>
    _wsOps().worksheets.kpiTracking.data.filter(k =>
      Math.abs(k.variance_percent || 0) > 5
    )
  )

  // ========================================
  // Scenario getters
  // ========================================

  const scenariosByType = computed(() => {
    const grouped = {}
    for (const scenario of _wsOps().worksheets.whatIfScenarios.data) {
      const type = scenario.scenario_type || 'other'
      if (!grouped[type]) {
        grouped[type] = []
      }
      grouped[type].push(scenario)
    }
    return grouped
  })

  // ========================================
  // BOM getters
  // ========================================

  const bomCount = computed(() => _wsOps().worksheets.bom.data.length)

  const stylesWithBOM = computed(() =>
    [...new Set(_wsOps().worksheets.bom.data.map(b => b.style_code))].filter(Boolean)
  )

  // ========================================
  // Actions - Workbook (delegated)
  // ========================================

  function setClientId(id) {
    _wb().setClientId(id)
  }

  async function loadWorkbook(id = null) {
    return _wb().loadWorkbook(id)
  }

  async function saveWorksheet(worksheetName) {
    return _wb().saveWorksheet(worksheetName)
  }

  async function saveAllDirty() {
    return _wb().saveAllDirty()
  }

  async function saveWorkbook() {
    return _wb().saveWorkbook()
  }

  async function discardChanges() {
    return _wb().discardChanges()
  }

  // ========================================
  // Actions - Worksheet Ops (delegated)
  // ========================================

  function initHistory() {
    _wsOps().initHistory()
  }

  function updateCell(worksheetName, rowIndex, field, value) {
    _wsOps().updateCell(worksheetName, rowIndex, field, value)
  }

  function updateRow(worksheetName, rowIndex, updates) {
    _wsOps().updateRow(worksheetName, rowIndex, updates)
  }

  function addRow(worksheetName) {
    return _wsOps().addRow(worksheetName)
  }

  function insertRow(worksheetName, index, row = null) {
    return _wsOps().insertRow(worksheetName, index, row)
  }

  function removeRow(worksheetName, rowIndex) {
    return _wsOps().removeRow(worksheetName, rowIndex)
  }

  function removeRows(worksheetName, indices) {
    return _wsOps().removeRows(worksheetName, indices)
  }

  function duplicateRow(worksheetName, rowIndex) {
    return _wsOps().duplicateRow(worksheetName, rowIndex)
  }

  function importData(worksheetName, data) {
    return _wsOps().importData(worksheetName, data)
  }

  function appendData(worksheetName, data) {
    return _wsOps().appendData(worksheetName, data)
  }

  function undo() {
    return _wsOps().undo()
  }

  function redo() {
    return _wsOps().redo()
  }

  function updateDashboardInput(key, value) {
    _wsOps().updateDashboardInput(key, value)
  }

  function exportWorksheetJSON(worksheetName) {
    return _wsOps().exportWorksheetJSON(worksheetName)
  }

  function exportWorkbookJSON() {
    return _wsOps().exportWorkbookJSON()
  }

  function addBOMComponent(bomIndex) {
    return _wsOps().addBOMComponent(bomIndex)
  }

  function removeBOMComponent(bomIndex, componentIndex) {
    return _wsOps().removeBOMComponent(bomIndex, componentIndex)
  }

  // ========================================
  // Actions - Analysis (delegated)
  // ========================================

  async function runComponentCheck(orderIds = null) {
    return _analysis().runComponentCheck(orderIds)
  }

  function clearMRPResults() {
    _analysis().clearMRPResults()
  }

  async function explodeBOM(parentItemCode, quantity) {
    return _analysis().explodeBOM(parentItemCode, quantity)
  }

  async function runCapacityAnalysis(startDate, endDate, lineIds = null) {
    return _analysis().runCapacityAnalysis(startDate, endDate, lineIds)
  }

  function clearAnalysisResults() {
    _analysis().clearAnalysisResults()
  }

  async function generateSchedule(name, startDate, endDate, orderIds = null) {
    return _analysis().generateSchedule(name, startDate, endDate, orderIds)
  }

  async function commitSchedule(scheduleId, kpiCommitments) {
    return _analysis().commitSchedule(scheduleId, kpiCommitments)
  }

  async function loadSchedule(scheduleId) {
    return _analysis().loadSchedule(scheduleId)
  }

  async function createScenario(name, type, parameters, baseScheduleId = null) {
    return _analysis().createScenario(name, type, parameters, baseScheduleId)
  }

  async function runScenario(scenarioId) {
    return _analysis().runScenario(scenarioId)
  }

  async function compareScenarios(scenarioIds) {
    return _analysis().compareScenarios(scenarioIds)
  }

  async function deleteScenario(scenarioId) {
    return _analysis().deleteScenario(scenarioId)
  }

  async function loadKPIActuals(period) {
    return _analysis().loadKPIActuals(period)
  }

  // ========================================
  // Actions - UI State
  // ========================================

  function setActiveTab(tab) {
    activeTab.value = tab
  }

  function clearError() {
    _wb().globalError = null
    _wsOps().clearAllErrors()
    _analysis().mrpError = null
  }

  function closeAllDialogs() {
    const a = _analysis()
    a.showMRPResultsDialog = false
    a.showScenarioCompareDialog = false
    a.showScheduleCommitDialog = false
    showExportDialog.value = false
    showImportDialog.value = false
  }

  // ========================================
  // Actions - Reset
  // ========================================

  function reset() {
    // Reset workbook store
    const wb = _wb()
    wb.clientId = null
    wb.globalError = null
    wb.lastSaved = null
    wb.isLoading = false
    wb.isSaving = false

    // Reset worksheet ops
    _wsOps().resetWorksheets()

    // Reset analysis
    _analysis().resetAnalysis()

    // Reset local UI state
    activeTab.value = 'orders'
    showExportDialog.value = false
    showImportDialog.value = false
  }

  // ========================================
  // Return public API (backward-compatible)
  // ========================================

  return {
    // State (writable)
    activeTab,
    showExportDialog,
    showImportDialog,

    // Delegated state (writable via computed get/set)
    worksheets,
    clientId,
    isLoading,
    isSaving,
    globalError,
    lastSaved,
    mrpResults,
    isRunningMRP,
    mrpError,
    showMRPResultsDialog,
    activeScenario,
    scenarioComparisonResults,
    isCreatingScenario,
    showScenarioCompareDialog,
    activeSchedule,
    isGeneratingSchedule,
    isCommittingSchedule,
    showScheduleCommitDialog,
    analysisResults,
    isRunningAnalysis,

    // Read-only getters
    hasUnsavedChanges,
    dirtyWorksheets,
    dirtyCount,
    canUndo,
    canRedo,
    shortageComponents,
    shortageCount,
    partialComponents,
    bottleneckLines,
    overloadedLines,
    averageUtilization,
    schedulableOrders,
    totalOrderQuantity,
    ordersByStatus,
    orderPriorityCounts,
    activeLineCount,
    inactiveLines,
    totalCapacity,
    workingDaysCount,
    holidays,
    kpiVarianceSummary,
    offTargetKPIs,
    scenariosByType,
    bomCount,
    stylesWithBOM,

    // Internal (tests access this)
    _historyManager,

    // Actions
    setClientId,
    loadWorkbook,
    saveWorksheet,
    saveAllDirty,
    saveWorkbook,
    discardChanges,
    initHistory,
    updateCell,
    updateRow,
    addRow,
    insertRow,
    removeRow,
    removeRows,
    duplicateRow,
    importData,
    appendData,
    undo,
    redo,
    updateDashboardInput,
    exportWorksheetJSON,
    exportWorkbookJSON,
    addBOMComponent,
    removeBOMComponent,
    runComponentCheck,
    clearMRPResults,
    explodeBOM,
    runCapacityAnalysis,
    clearAnalysisResults,
    generateSchedule,
    commitSchedule,
    loadSchedule,
    createScenario,
    runScenario,
    compareScenarios,
    deleteScenario,
    loadKPIActuals,
    setActiveTab,
    clearError,
    closeAllDialogs,
    reset
  }
})
