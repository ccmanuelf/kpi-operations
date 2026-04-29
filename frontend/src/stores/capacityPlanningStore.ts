/**
 * Capacity Planning module — Pinia store wrapper that composes three
 * still-JS sub-stores (worksheet ops, workbook, analysis) into a
 * single backward-compatible public API. Local state is just the
 * tab/dialog UI flags; everything else is delegated.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useWorksheetOpsStore } from './capacity/useWorksheetOps'
import { useWorkbookStore } from './capacity/useWorkbookStore'
import { useAnalysisStore } from './capacity/useAnalysisStore'

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
  getDefaultDashboardInputs,
} from './capacity/defaults'

// Worksheet rows from the underlying sub-store carry strict types,
// but for this delegating wrapper the row arrays are accessed
// uniformly via `.data.filter(...)` etc., so a `Record<string,
// unknown>` view keeps the wrapper code simple. Where stricter
// typing matters (specific worksheet shapes) consumers can import
// directly from `stores/capacity/defaults`.
type WorksheetRow = Record<string, unknown>
type Worksheets = Record<string, { data: WorksheetRow[]; [key: string]: unknown }>
type Id = string | number | null

export const useCapacityPlanningStore = defineStore('capacityPlanning', () => {
  const _wsOps = () => useWorksheetOpsStore()
  const _wb = () => useWorkbookStore()
  const _analysis = () => useAnalysisStore()

  // Local UI-only state
  const activeTab = ref('orders')
  const showExportDialog = ref(false)
  const showImportDialog = ref(false)

  // Worksheet state (delegated). The sub-store has stricter per-
  // worksheet types (DataWorksheet | DashboardInputsWorksheet |
  // InstructionsWorksheet); the wrapper exposes a loose
  // `Record<string, { data: WorksheetRow[]; ... }>` view that's
  // sufficient for the existing call-site patterns.
  const worksheets = computed<Worksheets>(
    () => _wsOps().worksheets as unknown as Worksheets,
  )

  // Dirty-tracking getters
  const hasUnsavedChanges = computed<boolean>(() => _wsOps().hasUnsavedChanges)
  const dirtyWorksheets = computed<string[]>(() => _wsOps().dirtyWorksheets)
  const dirtyCount = computed<number>(() => _wsOps().dirtyCount)

  // Undo/redo getters
  const canUndo = computed<boolean>(() => _wsOps().canUndo)
  const canRedo = computed<boolean>(() => _wsOps().canRedo)
  const _historyManager = computed(() => _wsOps()._historyManager)

  // Workbook state
  const clientId = computed<Id>({
    get: () => _wb().clientId,
    set: (val) => {
      _wb().clientId = val
    },
  })

  const isLoading = computed<boolean>({
    get: () => _wb().isLoading,
    set: (val) => {
      _wb().isLoading = val
    },
  })

  const isSaving = computed<boolean>({
    get: () => _wb().isSaving,
    set: (val) => {
      _wb().isSaving = val
    },
  })

  const globalError = computed<string | null>({
    get: () => _wb().globalError,
    set: (val) => {
      _wb().globalError = val
    },
  })

  const lastSaved = computed<Date | null>({
    get: () => _wb().lastSaved,
    set: (val) => {
      _wb().lastSaved = val
    },
  })

  // Analysis state — proxied through to the analysis sub-store.
  // The sub-store is now typed; using each store field's own
  // type lets the wrapper's get/set computed pass values through
  // without a coercion mismatch.
  const mrpResults = computed({
    get: () => _analysis().mrpResults,
    set: (val: ReturnType<typeof _analysis>['mrpResults']) => {
      _analysis().mrpResults = val
    },
  })

  const isRunningMRP = computed<boolean>({
    get: () => _analysis().isRunningMRP,
    set: (val) => {
      _analysis().isRunningMRP = val
    },
  })

  const mrpError = computed<string | null>({
    get: () => _analysis().mrpError,
    set: (val) => {
      _analysis().mrpError = val
    },
  })

  const showMRPResultsDialog = computed<boolean>({
    get: () => _analysis().showMRPResultsDialog,
    set: (val) => {
      _analysis().showMRPResultsDialog = val
    },
  })

  const activeScenario = computed({
    get: () => _analysis().activeScenario,
    set: (val: ReturnType<typeof _analysis>['activeScenario']) => {
      _analysis().activeScenario = val
    },
  })

  const scenarioComparisonResults = computed({
    get: () => _analysis().scenarioComparisonResults,
    set: (val: ReturnType<typeof _analysis>['scenarioComparisonResults']) => {
      _analysis().scenarioComparisonResults = val
    },
  })

  const isCreatingScenario = computed<boolean>({
    get: () => _analysis().isCreatingScenario,
    set: (val) => {
      _analysis().isCreatingScenario = val
    },
  })

  const showScenarioCompareDialog = computed<boolean>({
    get: () => _analysis().showScenarioCompareDialog,
    set: (val) => {
      _analysis().showScenarioCompareDialog = val
    },
  })

  const activeSchedule = computed({
    get: () => _analysis().activeSchedule,
    set: (val: ReturnType<typeof _analysis>['activeSchedule']) => {
      _analysis().activeSchedule = val
    },
  })

  const isGeneratingSchedule = computed<boolean>({
    get: () => _analysis().isGeneratingSchedule,
    set: (val) => {
      _analysis().isGeneratingSchedule = val
    },
  })

  const isCommittingSchedule = computed<boolean>({
    get: () => _analysis().isCommittingSchedule,
    set: (val) => {
      _analysis().isCommittingSchedule = val
    },
  })

  const showScheduleCommitDialog = computed<boolean>({
    get: () => _analysis().showScheduleCommitDialog,
    set: (val) => {
      _analysis().showScheduleCommitDialog = val
    },
  })

  const analysisResults = computed({
    get: () => _analysis().analysisResults,
    set: (val: ReturnType<typeof _analysis>['analysisResults']) => {
      _analysis().analysisResults = val
    },
  })

  const isRunningAnalysis = computed<boolean>({
    get: () => _analysis().isRunningAnalysis,
    set: (val) => {
      _analysis().isRunningAnalysis = val
    },
  })

  // Component-check getters
  const shortageComponents = computed<WorksheetRow[]>(() =>
    _wsOps().worksheets.componentCheck.data.filter(
      (c: WorksheetRow) => c.status === 'SHORTAGE',
    ),
  )

  const shortageCount = computed<number>(
    () =>
      _wsOps().worksheets.componentCheck.data.filter(
        (c: WorksheetRow) => c.status === 'SHORTAGE',
      ).length,
  )

  const partialComponents = computed<WorksheetRow[]>(() =>
    _wsOps().worksheets.componentCheck.data.filter(
      (c: WorksheetRow) => c.status === 'PARTIAL',
    ),
  )

  // Capacity-analysis getters
  const bottleneckLines = computed<WorksheetRow[]>(() =>
    _wsOps().worksheets.capacityAnalysis.data.filter(
      (a: WorksheetRow) => a.is_bottleneck,
    ),
  )

  const overloadedLines = computed<WorksheetRow[]>(() =>
    _wsOps().worksheets.capacityAnalysis.data.filter(
      (a: WorksheetRow) => parseFloat(String(a.utilization_percent)) > 100,
    ),
  )

  const averageUtilization = computed<number | string>(() => {
    const data: WorksheetRow[] = _wsOps().worksheets.capacityAnalysis.data
    if (data.length === 0) return 0
    const sum = data.reduce(
      (acc, a) => acc + (parseFloat(String(a.utilization_percent)) || 0),
      0,
    )
    return (sum / data.length).toFixed(1)
  })

  // Order getters
  const schedulableOrders = computed<WorksheetRow[]>(() =>
    _wsOps().worksheets.orders.data.filter((o: WorksheetRow) =>
      ['DRAFT', 'CONFIRMED'].includes(String(o.status)),
    ),
  )

  const totalOrderQuantity = computed<number>(() =>
    _wsOps().worksheets.orders.data.reduce(
      (sum: number, o: WorksheetRow) =>
        sum + (parseInt(String(o.order_quantity)) || 0),
      0,
    ),
  )

  const ordersByStatus = computed<Record<string, WorksheetRow[]>>(() => {
    const grouped: Record<string, WorksheetRow[]> = {}
    for (const order of _wsOps().worksheets.orders.data as WorksheetRow[]) {
      const status = String(order.status || 'UNKNOWN')
      if (!grouped[status]) {
        grouped[status] = []
      }
      grouped[status].push(order)
    }
    return grouped
  })

  const orderPriorityCounts = computed<Record<string, number>>(() => {
    const counts: Record<string, number> = { CRITICAL: 0, HIGH: 0, NORMAL: 0, LOW: 0 }
    for (const order of _wsOps().worksheets.orders.data as WorksheetRow[]) {
      const priority = String(order.priority || 'NORMAL')
      if (counts[priority] !== undefined) {
        counts[priority]++
      }
    }
    return counts
  })

  // Production-line getters
  const activeLineCount = computed<number>(
    () =>
      _wsOps().worksheets.productionLines.data.filter(
        (l: WorksheetRow) => l.is_active,
      ).length,
  )

  const inactiveLines = computed<WorksheetRow[]>(() =>
    _wsOps().worksheets.productionLines.data.filter(
      (l: WorksheetRow) => !l.is_active,
    ),
  )

  const totalCapacity = computed<number>(() =>
    _wsOps()
      .worksheets.productionLines.data.filter((l: WorksheetRow) => l.is_active)
      .reduce(
        (sum: number, l: WorksheetRow) =>
          sum + (parseFloat(String(l.standard_capacity_units_per_hour)) || 0),
        0,
      ),
  )

  // Calendar getters
  const workingDaysCount = computed<number>(
    () =>
      _wsOps().worksheets.masterCalendar.data.filter(
        (d: WorksheetRow) => d.is_working_day,
      ).length,
  )

  const holidays = computed<WorksheetRow[]>(() =>
    _wsOps().worksheets.masterCalendar.data.filter(
      (d: WorksheetRow) => d.holiday_name,
    ),
  )

  // KPI getters
  const kpiVarianceSummary = computed(() => {
    const tracking: WorksheetRow[] = _wsOps().worksheets.kpiTracking.data
    if (!tracking.length) return null

    return {
      totalKPIs: tracking.length,
      onTarget: tracking.filter(
        (k: WorksheetRow) => Math.abs(Number(k.variance_percent) || 0) <= 5,
      ).length,
      offTarget: tracking.filter(
        (k: WorksheetRow) => Math.abs(Number(k.variance_percent) || 0) > 5,
      ).length,
      critical: tracking.filter(
        (k: WorksheetRow) => Math.abs(Number(k.variance_percent) || 0) > 10,
      ).length,
    }
  })

  const offTargetKPIs = computed<WorksheetRow[]>(() =>
    _wsOps().worksheets.kpiTracking.data.filter(
      (k: WorksheetRow) => Math.abs(Number(k.variance_percent) || 0) > 5,
    ),
  )

  // Scenario getters
  const scenariosByType = computed<Record<string, WorksheetRow[]>>(() => {
    const grouped: Record<string, WorksheetRow[]> = {}
    for (const scenario of _wsOps().worksheets.whatIfScenarios.data as WorksheetRow[]) {
      const type = String(scenario.scenario_type || 'other')
      if (!grouped[type]) {
        grouped[type] = []
      }
      grouped[type].push(scenario)
    }
    return grouped
  })

  // BOM getters
  const bomCount = computed<number>(() => _wsOps().worksheets.bom.data.length)

  const stylesWithBOM = computed<string[]>(() =>
    [
      ...new Set(
        _wsOps().worksheets.bom.data.map((b: WorksheetRow) => b.style_model),
      ),
    ].filter(Boolean) as string[],
  )

  // Workbook actions
  function setClientId(id: Id): void {
    _wb().setClientId(id)
  }

  async function loadWorkbook(id: Id = null) {
    return _wb().loadWorkbook(id)
  }

  async function saveWorksheet(worksheetName: string) {
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

  // Worksheet ops actions
  function initHistory(): void {
    _wsOps().initHistory()
  }

  function updateCell(
    worksheetName: string,
    rowIndex: number,
    field: string,
    value: unknown,
  ): void {
    _wsOps().updateCell(worksheetName, rowIndex, field, value)
  }

  function updateRow(
    worksheetName: string,
    rowIndex: number,
    updates: Partial<WorksheetRow>,
  ): void {
    _wsOps().updateRow(worksheetName, rowIndex, updates)
  }

  function addRow(worksheetName: string) {
    return _wsOps().addRow(worksheetName)
  }

  function insertRow(worksheetName: string, index: number, row: WorksheetRow | null = null) {
    return _wsOps().insertRow(worksheetName, index, row)
  }

  function removeRow(worksheetName: string, rowIndex: number) {
    return _wsOps().removeRow(worksheetName, rowIndex)
  }

  function removeRows(worksheetName: string, indices: number[]) {
    return _wsOps().removeRows(worksheetName, indices)
  }

  function duplicateRow(worksheetName: string, rowIndex: number) {
    return _wsOps().duplicateRow(worksheetName, rowIndex)
  }

  function importData(worksheetName: string, data: WorksheetRow[]) {
    return _wsOps().importData(worksheetName, data)
  }

  function appendData(worksheetName: string, data: WorksheetRow[]) {
    return _wsOps().appendData(worksheetName, data)
  }

  function undo() {
    return _wsOps().undo()
  }

  function redo() {
    return _wsOps().redo()
  }

  function updateDashboardInput(key: string, value: unknown): void {
    _wsOps().updateDashboardInput(key, value)
  }

  function exportWorksheetJSON(worksheetName: string) {
    return _wsOps().exportWorksheetJSON(worksheetName)
  }

  function exportWorkbookJSON() {
    return _wsOps().exportWorkbookJSON()
  }

  function addBOMComponent(bomIndex: number) {
    return _wsOps().addBOMComponent(bomIndex)
  }

  function removeBOMComponent(bomIndex: number, componentIndex: number) {
    return _wsOps().removeBOMComponent(bomIndex, componentIndex)
  }

  // Analysis actions
  async function runComponentCheck(orderIds: (string | number)[] | null = null) {
    return _analysis().runComponentCheck(orderIds)
  }

  function clearMRPResults(): void {
    _analysis().clearMRPResults()
  }

  async function explodeBOM(parentItemCode: string, quantity: number) {
    return _analysis().explodeBOM(parentItemCode, quantity)
  }

  async function runCapacityAnalysis(
    startDate: string,
    endDate: string,
    lineIds: (string | number)[] | null = null,
  ) {
    return _analysis().runCapacityAnalysis(startDate, endDate, lineIds)
  }

  function clearAnalysisResults(): void {
    _analysis().clearAnalysisResults()
  }

  async function generateSchedule(
    name: string,
    startDate: string,
    endDate: string,
    orderIds: (string | number)[] | null = null,
  ) {
    return _analysis().generateSchedule(name, startDate, endDate, orderIds)
  }

  async function commitSchedule(
    scheduleId: string | number,
    kpiCommitments: Record<string, unknown>,
  ) {
    return _analysis().commitSchedule(scheduleId, kpiCommitments)
  }

  async function loadSchedule(scheduleId: string | number) {
    return _analysis().loadSchedule(scheduleId)
  }

  async function createScenario(
    name: string,
    type: string,
    parameters: Record<string, unknown>,
    baseScheduleId: string | number | null = null,
  ) {
    return _analysis().createScenario(name, type, parameters, baseScheduleId)
  }

  async function runScenario(scenarioId: string | number) {
    return _analysis().runScenario(scenarioId)
  }

  async function compareScenarios(scenarioIds: (string | number)[]) {
    return _analysis().compareScenarios(scenarioIds)
  }

  async function deleteScenario(scenarioId: string | number) {
    return _analysis().deleteScenario(scenarioId)
  }

  // The original JS wrapper had a `loadKPIActuals` passthrough,
  // but the analysis sub-store never implemented it. Calling it
  // would have thrown at runtime. Surfaced here as a no-op stub
  // so any consumer still importing the symbol gets a typed
  // failure mode instead of a TypeError.
  async function loadKPIActuals(_period: string): Promise<null> {
    void _period
    return null
  }

  // UI state actions
  function setActiveTab(tab: string): void {
    activeTab.value = tab
  }

  function clearError(): void {
    _wb().globalError = null
    _wsOps().clearAllErrors()
    _analysis().mrpError = null
  }

  function closeAllDialogs(): void {
    const a = _analysis()
    a.showMRPResultsDialog = false
    a.showScenarioCompareDialog = false
    a.showScheduleCommitDialog = false
    showExportDialog.value = false
    showImportDialog.value = false
  }

  function reset(): void {
    const wb = _wb()
    wb.clientId = null
    wb.globalError = null
    wb.lastSaved = null
    wb.isLoading = false
    wb.isSaving = false

    _wsOps().resetWorksheets()
    _analysis().resetAnalysis()

    activeTab.value = 'orders'
    showExportDialog.value = false
    showImportDialog.value = false
  }

  return {
    activeTab,
    showExportDialog,
    showImportDialog,
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
    _historyManager,
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
    reset,
  }
})
