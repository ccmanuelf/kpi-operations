import api from './client'

type Id = number
type Payload = Record<string, unknown>
type Params = Record<string, unknown>

// ============================================
// Workbook Operations
// ============================================

export const loadWorkbook = async (clientId: Id) => {
  const response = await api.get(`/capacity/workbook/${clientId}`)
  return response.data
}

export const saveWorksheet = async (worksheetName: string, clientId: Id, data: Payload) => {
  const response = await api.put(`/capacity/workbook/${clientId}/${worksheetName}`, data)
  return response.data
}

// ============================================
// Calendar Operations
// ============================================

export const getCalendarEntries = async (
  clientId: Id,
  startDate: string | null = null,
  endDate: string | null = null,
) => {
  const params: Params = { client_id: clientId }
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate

  const response = await api.get('/capacity/calendar', { params })
  return response.data
}

export const createCalendarEntry = async (clientId: Id, entry: Payload) => {
  const response = await api.post('/capacity/calendar', entry, {
    params: { client_id: clientId },
  })
  return response.data
}

export const updateCalendarEntry = async (clientId: Id, entryId: Id, updates: Payload) => {
  const response = await api.put(`/capacity/calendar/${entryId}`, updates, {
    params: { client_id: clientId },
  })
  return response.data
}

export const deleteCalendarEntry = async (clientId: Id, entryId: Id) => {
  const response = await api.delete(`/capacity/calendar/${entryId}`, {
    params: { client_id: clientId },
  })
  return response.data
}

// ============================================
// Production Lines Operations
// ============================================

export const getProductionLines = async (
  clientId: Id,
  includeInactive = false,
  department: string | null = null,
) => {
  const params: Params = {
    client_id: clientId,
    include_inactive: includeInactive,
  }
  if (department) params.department = department

  const response = await api.get('/capacity/lines', { params })
  return response.data
}

export const createProductionLine = async (clientId: Id, line: Payload) => {
  const response = await api.post('/capacity/lines', line, {
    params: { client_id: clientId },
  })
  return response.data
}

export const updateProductionLine = async (clientId: Id, lineId: Id, updates: Payload) => {
  const response = await api.put(`/capacity/lines/${lineId}`, updates, {
    params: { client_id: clientId },
  })
  return response.data
}

export const deleteProductionLine = async (clientId: Id, lineId: Id, hardDelete = false) => {
  const response = await api.delete(`/capacity/lines/${lineId}`, {
    params: { client_id: clientId, hard_delete: hardDelete },
  })
  return response.data
}

// ============================================
// Orders Operations
// ============================================

export const getOrders = async (
  clientId: Id,
  status: string | null = null,
  skip = 0,
  limit = 100,
) => {
  const params: Params = { client_id: clientId, skip, limit }
  if (status) params.status = status

  const response = await api.get('/capacity/orders', { params })
  return response.data
}

export const getOrdersForScheduling = async (
  clientId: Id,
  startDate: string | null = null,
  endDate: string | null = null,
) => {
  const params: Params = { client_id: clientId }
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate

  const response = await api.get('/capacity/orders/scheduling', { params })
  return response.data
}

export const createOrder = async (clientId: Id, order: Payload) => {
  const response = await api.post('/capacity/orders', order, {
    params: { client_id: clientId },
  })
  return response.data
}

export const updateOrder = async (clientId: Id, orderId: Id, updates: Payload) => {
  const response = await api.put(`/capacity/orders/${orderId}`, updates, {
    params: { client_id: clientId },
  })
  return response.data
}

export const updateOrderStatus = async (clientId: Id, orderId: Id, status: string) => {
  const response = await api.patch(
    `/capacity/orders/${orderId}/status`,
    { status },
    { params: { client_id: clientId } },
  )
  return response.data
}

export const deleteOrder = async (clientId: Id, orderId: Id) => {
  const response = await api.delete(`/capacity/orders/${orderId}`, {
    params: { client_id: clientId },
  })
  return response.data
}

// ============================================
// Standards Operations
// ============================================

export const getStandards = async (clientId: Id, styleCode: string | null = null) => {
  const params: Params = { client_id: clientId }
  if (styleCode) params.style_model = styleCode

  const response = await api.get('/capacity/standards', { params })
  return response.data
}

export const getStandardsByStyle = async (clientId: Id, styleCode: string) => {
  const response = await api.get(`/capacity/standards/style/${styleCode}`, {
    params: { client_id: clientId },
  })
  return response.data
}

export const getTotalSAMForStyle = async (clientId: Id, styleCode: string) => {
  const response = await api.get(`/capacity/standards/style/${styleCode}/total-sam`, {
    params: { client_id: clientId },
  })
  return response.data
}

export const createStandard = async (clientId: Id, standard: Payload) => {
  const response = await api.post('/capacity/standards', standard, {
    params: { client_id: clientId },
  })
  return response.data
}

export const updateStandard = async (clientId: Id, standardId: Id, updates: Payload) => {
  const response = await api.put(`/capacity/standards/${standardId}`, updates, {
    params: { client_id: clientId },
  })
  return response.data
}

export const deleteStandard = async (clientId: Id, standardId: Id) => {
  const response = await api.delete(`/capacity/standards/${standardId}`, {
    params: { client_id: clientId },
  })
  return response.data
}

// ============================================
// BOM Operations
// ============================================

export const getBOMHeaders = async (
  clientId: Id,
  styleCode: string | null = null,
  activeOnly = true,
) => {
  const params: Params = { client_id: clientId, active_only: activeOnly }
  if (styleCode) params.style_model = styleCode

  const response = await api.get('/capacity/bom', { params })
  return response.data
}

export const getBOMWithDetails = async (clientId: Id, headerId: Id) => {
  const response = await api.get(`/capacity/bom/${headerId}`, {
    params: { client_id: clientId },
  })
  return response.data
}

export const createBOMHeader = async (clientId: Id, header: Payload) => {
  const response = await api.post('/capacity/bom', header, {
    params: { client_id: clientId },
  })
  return response.data
}

export const updateBOMHeader = async (clientId: Id, headerId: Id, updates: Payload) => {
  const response = await api.put(`/capacity/bom/${headerId}`, updates, {
    params: { client_id: clientId },
  })
  return response.data
}

export const deleteBOMHeader = async (clientId: Id, headerId: Id, hardDelete = false) => {
  const response = await api.delete(`/capacity/bom/${headerId}`, {
    params: { client_id: clientId, hard_delete: hardDelete },
  })
  return response.data
}

export const getBOMDetails = async (clientId: Id, headerId: Id) => {
  const response = await api.get(`/capacity/bom/${headerId}/details`, {
    params: { client_id: clientId },
  })
  return response.data
}

export const createBOMDetail = async (clientId: Id, headerId: Id, detail: Payload) => {
  const response = await api.post(`/capacity/bom/${headerId}/details`, detail, {
    params: { client_id: clientId },
  })
  return response.data
}

export const updateBOMDetail = async (clientId: Id, detailId: Id, updates: Payload) => {
  const response = await api.put(`/capacity/bom/details/${detailId}`, updates, {
    params: { client_id: clientId },
  })
  return response.data
}

export const deleteBOMDetail = async (clientId: Id, detailId: Id) => {
  const response = await api.delete(`/capacity/bom/details/${detailId}`, {
    params: { client_id: clientId },
  })
  return response.data
}

export const explodeBOM = async (clientId: Id, parentItemCode: string, quantity: number) => {
  const response = await api.post(
    '/capacity/bom/explode',
    { parent_item_code: parentItemCode, quantity },
    { params: { client_id: clientId } },
  )
  return response.data
}

// ============================================
// Stock Operations
// ============================================

export const getStockSnapshots = async (clientId: Id, snapshotDate: string | null = null) => {
  const params: Params = { client_id: clientId }
  if (snapshotDate) params.snapshot_date = snapshotDate

  const response = await api.get('/capacity/stock', { params })
  return response.data
}

export const getLatestStock = async (clientId: Id, itemCode: string) => {
  const response = await api.get(`/capacity/stock/item/${itemCode}/latest`, {
    params: { client_id: clientId },
  })
  return response.data
}

export const getAvailableStock = async (clientId: Id, itemCode: string) => {
  const response = await api.get(`/capacity/stock/item/${itemCode}/available`, {
    params: { client_id: clientId },
  })
  return response.data
}

export const getShortageItems = async (clientId: Id) => {
  const response = await api.get('/capacity/stock/shortages', {
    params: { client_id: clientId },
  })
  return response.data
}

export const createStockSnapshot = async (clientId: Id, snapshot: Payload) => {
  const response = await api.post('/capacity/stock', snapshot, {
    params: { client_id: clientId },
  })
  return response.data
}

export const updateStockSnapshot = async (clientId: Id, snapshotId: Id, updates: Payload) => {
  const response = await api.put(`/capacity/stock/${snapshotId}`, updates, {
    params: { client_id: clientId },
  })
  return response.data
}

export const deleteStockSnapshot = async (clientId: Id, snapshotId: Id) => {
  const response = await api.delete(`/capacity/stock/${snapshotId}`, {
    params: { client_id: clientId },
  })
  return response.data
}

// ============================================
// Component Check (MRP) Operations
// ============================================

export const runComponentCheck = async (clientId: Id, orderIds: Id[] | null = null) => {
  const response = await api.post(
    '/capacity/component-check/run',
    { order_ids: orderIds },
    { params: { client_id: clientId } },
  )
  return response.data
}

export const getShortages = async (clientId: Id) => {
  const response = await api.get('/capacity/component-check/shortages', {
    params: { client_id: clientId },
  })
  return response.data
}

// ============================================
// Capacity Analysis Operations
// ============================================

export const runCapacityAnalysis = async (
  clientId: Id,
  startDate: string,
  endDate: string,
  lineIds: Id[] | null = null,
) => {
  const response = await api.post(
    '/capacity/analysis/calculate',
    { start_date: startDate, end_date: endDate, line_ids: lineIds },
    { params: { client_id: clientId } },
  )
  return response.data
}

export const getBottlenecks = async (clientId: Id) => {
  const response = await api.get('/capacity/analysis/bottlenecks', {
    params: { client_id: clientId },
  })
  return response.data
}

// ============================================
// Schedule Operations
// ============================================

export const getSchedules = async (clientId: Id, status: string | null = null) => {
  const params: Params = { client_id: clientId }
  if (status) params.status = status

  const response = await api.get('/capacity/schedules', { params })
  return response.data
}

export const getSchedule = async (clientId: Id, scheduleId: Id) => {
  const response = await api.get(`/capacity/schedules/${scheduleId}`, {
    params: { client_id: clientId },
  })
  return response.data
}

export const createSchedule = async (clientId: Id, schedule: Payload) => {
  const response = await api.post('/capacity/schedules', schedule, {
    params: { client_id: clientId },
  })
  return response.data
}

export const generateSchedule = async (
  clientId: Id,
  name: string,
  startDate: string,
  endDate: string,
  orderIds: Id[] | null = null,
) => {
  const response = await api.post(
    '/capacity/schedules/generate',
    { name, start_date: startDate, end_date: endDate, order_ids: orderIds },
    { params: { client_id: clientId } },
  )
  return response.data
}

export const commitSchedule = async (scheduleId: Id, kpiCommitments: Payload) => {
  const response = await api.post(`/capacity/schedules/${scheduleId}/commit`, {
    kpi_commitments: kpiCommitments,
  })
  return response.data
}

// ============================================
// Scenario Operations
// ============================================

export const getScenarios = async (clientId: Id) => {
  const response = await api.get('/capacity/scenarios', {
    params: { client_id: clientId },
  })
  return response.data
}

export const getScenario = async (clientId: Id, scenarioId: Id) => {
  const response = await api.get(`/capacity/scenarios/${scenarioId}`, {
    params: { client_id: clientId },
  })
  return response.data
}

export const createScenario = async (
  clientId: Id,
  name: string,
  type: string,
  parameters: Payload,
  baseScheduleId: Id | null = null,
) => {
  // Backend ScenarioCreate expects `scenario_name` (not `name`) — see
  // backend/routes/capacity/_models.py:474. Sending `name` 422'd silently
  // because the legacy dialog was the only caller and never surfaced
  // errors. Caught during the Surface #20 migration audit (2026-05-01).
  const response = await api.post(
    '/capacity/scenarios',
    { scenario_name: name, scenario_type: type, parameters, base_schedule_id: baseScheduleId },
    { params: { client_id: clientId } },
  )
  return response.data
}

export const compareScenarios = async (clientId: Id, scenarioIds: Id[]) => {
  const response = await api.post(
    '/capacity/scenarios/compare',
    { scenario_ids: scenarioIds },
    { params: { client_id: clientId } },
  )
  return response.data
}

// ============================================
// KPI Integration Operations
// ============================================

export const getKPICommitments = async (clientId: Id, scheduleId: Id | null = null) => {
  const params: Params = { client_id: clientId }
  if (scheduleId) params.schedule_id = scheduleId

  const response = await api.get('/capacity/kpi/commitments', { params })
  return response.data
}

export const getKPIVariance = async (clientId: Id, scheduleId: Id | null = null) => {
  const params: Params = { client_id: clientId }
  if (scheduleId) params.schedule_id = scheduleId

  const response = await api.get('/capacity/kpi/variance', { params })
  return response.data
}

// ============================================
// Scenario Run/Delete Operations
// ============================================

export const runScenario = async (
  clientId: Id,
  scenarioId: Id,
  periodStart: string | null = null,
  periodEnd: string | null = null,
) => {
  const payload: Payload = {}
  if (periodStart) payload.period_start = periodStart
  if (periodEnd) payload.period_end = periodEnd

  const response = await api.post(`/capacity/scenarios/${scenarioId}/run`, payload, {
    params: { client_id: clientId },
  })
  return response.data
}

export const deleteScenario = async (clientId: Id, scenarioId: Id) => {
  const response = await api.delete(`/capacity/scenarios/${scenarioId}`, {
    params: { client_id: clientId },
  })
  return response.data
}

// ============================================
// Workbook Bulk Save
// ============================================

export interface SaveWorkbookResults {
  success: string[]
  failed: { worksheetName: string; error: string }[]
}

export const saveWorkbook = async (
  clientId: Id,
  workbookData: Record<string, Payload>,
): Promise<SaveWorkbookResults> => {
  const results: SaveWorkbookResults = { success: [], failed: [] }

  for (const [worksheetName, data] of Object.entries(workbookData)) {
    try {
      await saveWorksheet(worksheetName, clientId, data)
      results.success.push(worksheetName)
    } catch (error) {
      results.failed.push({
        worksheetName,
        error: error instanceof Error ? error.message : String(error),
      })
    }
  }

  return results
}

// ============================================
// Default Export
// ============================================

export default {
  loadWorkbook,
  saveWorksheet,
  getCalendarEntries,
  createCalendarEntry,
  updateCalendarEntry,
  deleteCalendarEntry,
  getProductionLines,
  createProductionLine,
  updateProductionLine,
  deleteProductionLine,
  getOrders,
  getOrdersForScheduling,
  createOrder,
  updateOrder,
  updateOrderStatus,
  deleteOrder,
  getStandards,
  getStandardsByStyle,
  getTotalSAMForStyle,
  createStandard,
  updateStandard,
  deleteStandard,
  getBOMHeaders,
  getBOMWithDetails,
  createBOMHeader,
  updateBOMHeader,
  deleteBOMHeader,
  getBOMDetails,
  createBOMDetail,
  updateBOMDetail,
  deleteBOMDetail,
  explodeBOM,
  getStockSnapshots,
  getLatestStock,
  getAvailableStock,
  getShortageItems,
  createStockSnapshot,
  updateStockSnapshot,
  deleteStockSnapshot,
  runComponentCheck,
  getShortages,
  runCapacityAnalysis,
  getBottlenecks,
  getSchedules,
  getSchedule,
  createSchedule,
  generateSchedule,
  commitSchedule,
  getScenarios,
  getScenario,
  createScenario,
  compareScenarios,
  runScenario,
  deleteScenario,
  saveWorkbook,
  getKPICommitments,
  getKPIVariance,
}
