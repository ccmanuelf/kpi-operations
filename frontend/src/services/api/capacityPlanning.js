/**
 * Capacity Planning API Service
 *
 * API functions for capacity planning module operations.
 * Handles all CRUD operations for workbooks, calendars, production lines,
 * orders, standards, BOM, stock, schedules, scenarios, and KPI integration.
 */

import api from './client'

// ============================================
// Workbook Operations
// ============================================

/**
 * Load all worksheet data for a client (13 sheets)
 * @param {number} clientId - The client ID
 * @returns {Promise<Object>} Workbook data with all worksheets
 */
export const loadWorkbook = async (clientId) => {
  const response = await api.get(`/capacity/workbook/${clientId}`)
  return response.data
}

/**
 * Save a specific worksheet's data
 * @param {string} worksheetName - Name of the worksheet to save
 * @param {number} clientId - The client ID
 * @param {Object} data - Worksheet data to save
 * @returns {Promise<Object>} Save confirmation
 */
export const saveWorksheet = async (worksheetName, clientId, data) => {
  const response = await api.put(
    `/capacity/workbook/${clientId}/${worksheetName}`,
    data
  )
  return response.data
}

// ============================================
// Calendar Operations
// ============================================

/**
 * Get calendar entries for a client
 * @param {number} clientId - The client ID
 * @param {string|null} startDate - Optional start date filter (YYYY-MM-DD)
 * @param {string|null} endDate - Optional end date filter (YYYY-MM-DD)
 * @returns {Promise<Array>} List of calendar entries
 */
export const getCalendarEntries = async (clientId, startDate = null, endDate = null) => {
  const params = { client_id: clientId }
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate

  const response = await api.get('/capacity/calendar', { params })
  return response.data
}

/**
 * Create a new calendar entry
 * @param {number} clientId - The client ID
 * @param {Object} entry - Calendar entry data
 * @returns {Promise<Object>} Created calendar entry
 */
export const createCalendarEntry = async (clientId, entry) => {
  const response = await api.post('/capacity/calendar', entry, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Update an existing calendar entry
 * @param {number} clientId - The client ID
 * @param {number} entryId - The entry ID to update
 * @param {Object} updates - Updated fields
 * @returns {Promise<Object>} Updated calendar entry
 */
export const updateCalendarEntry = async (clientId, entryId, updates) => {
  const response = await api.put(`/capacity/calendar/${entryId}`, updates, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Delete a calendar entry
 * @param {number} clientId - The client ID
 * @param {number} entryId - The entry ID to delete
 * @returns {Promise<Object>} Delete confirmation
 */
export const deleteCalendarEntry = async (clientId, entryId) => {
  const response = await api.delete(`/capacity/calendar/${entryId}`, {
    params: { client_id: clientId }
  })
  return response.data
}

// ============================================
// Production Lines Operations
// ============================================

/**
 * Get production lines for a client
 * @param {number} clientId - The client ID
 * @param {boolean} includeInactive - Whether to include inactive lines
 * @param {string|null} department - Optional department filter
 * @returns {Promise<Array>} List of production lines
 */
export const getProductionLines = async (clientId, includeInactive = false, department = null) => {
  const params = {
    client_id: clientId,
    include_inactive: includeInactive
  }
  if (department) params.department = department

  const response = await api.get('/capacity/lines', { params })
  return response.data
}

/**
 * Create a new production line
 * @param {number} clientId - The client ID
 * @param {Object} line - Production line data
 * @returns {Promise<Object>} Created production line
 */
export const createProductionLine = async (clientId, line) => {
  const response = await api.post('/capacity/lines', line, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Update an existing production line
 * @param {number} clientId - The client ID
 * @param {number} lineId - The line ID to update
 * @param {Object} updates - Updated fields
 * @returns {Promise<Object>} Updated production line
 */
export const updateProductionLine = async (clientId, lineId, updates) => {
  const response = await api.put(`/capacity/lines/${lineId}`, updates, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Delete a production line
 * @param {number} clientId - The client ID
 * @param {number} lineId - The line ID to delete
 * @param {boolean} hardDelete - Whether to permanently delete or soft delete
 * @returns {Promise<Object>} Delete confirmation
 */
export const deleteProductionLine = async (clientId, lineId, hardDelete = false) => {
  const response = await api.delete(`/capacity/lines/${lineId}`, {
    params: { client_id: clientId, hard_delete: hardDelete }
  })
  return response.data
}

// ============================================
// Orders Operations
// ============================================

/**
 * Get orders for a client
 * @param {number} clientId - The client ID
 * @param {string|null} status - Optional status filter
 * @param {number} skip - Number of records to skip (pagination)
 * @param {number} limit - Maximum records to return
 * @returns {Promise<Array>} List of orders
 */
export const getOrders = async (clientId, status = null, skip = 0, limit = 100) => {
  const params = { client_id: clientId, skip, limit }
  if (status) params.status = status

  const response = await api.get('/capacity/orders', { params })
  return response.data
}

/**
 * Get orders ready for scheduling
 * @param {number} clientId - The client ID
 * @param {string|null} startDate - Optional start date filter
 * @param {string|null} endDate - Optional end date filter
 * @returns {Promise<Array>} List of orders for scheduling
 */
export const getOrdersForScheduling = async (clientId, startDate = null, endDate = null) => {
  const params = { client_id: clientId }
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate

  const response = await api.get('/capacity/orders/scheduling', { params })
  return response.data
}

/**
 * Create a new order
 * @param {number} clientId - The client ID
 * @param {Object} order - Order data
 * @returns {Promise<Object>} Created order
 */
export const createOrder = async (clientId, order) => {
  const response = await api.post('/capacity/orders', order, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Update an existing order
 * @param {number} clientId - The client ID
 * @param {number} orderId - The order ID to update
 * @param {Object} updates - Updated fields
 * @returns {Promise<Object>} Updated order
 */
export const updateOrder = async (clientId, orderId, updates) => {
  const response = await api.put(`/capacity/orders/${orderId}`, updates, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Update order status
 * @param {number} clientId - The client ID
 * @param {number} orderId - The order ID to update
 * @param {string} status - New status value
 * @returns {Promise<Object>} Updated order
 */
export const updateOrderStatus = async (clientId, orderId, status) => {
  const response = await api.patch(`/capacity/orders/${orderId}/status`,
    { status },
    { params: { client_id: clientId } }
  )
  return response.data
}

/**
 * Delete an order
 * @param {number} clientId - The client ID
 * @param {number} orderId - The order ID to delete
 * @returns {Promise<Object>} Delete confirmation
 */
export const deleteOrder = async (clientId, orderId) => {
  const response = await api.delete(`/capacity/orders/${orderId}`, {
    params: { client_id: clientId }
  })
  return response.data
}

// ============================================
// Standards Operations
// ============================================

/**
 * Get standards for a client
 * @param {number} clientId - The client ID
 * @param {string|null} styleCode - Optional style code filter
 * @returns {Promise<Array>} List of standards
 */
export const getStandards = async (clientId, styleCode = null) => {
  const params = { client_id: clientId }
  if (styleCode) params.style_code = styleCode

  const response = await api.get('/capacity/standards', { params })
  return response.data
}

/**
 * Get standards for a specific style
 * @param {number} clientId - The client ID
 * @param {string} styleCode - The style code
 * @returns {Promise<Array>} List of standards for the style
 */
export const getStandardsByStyle = async (clientId, styleCode) => {
  const response = await api.get(`/capacity/standards/style/${styleCode}`, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Get total SAM for a style
 * @param {number} clientId - The client ID
 * @param {string} styleCode - The style code
 * @returns {Promise<Object>} Total SAM information
 */
export const getTotalSAMForStyle = async (clientId, styleCode) => {
  const response = await api.get(`/capacity/standards/style/${styleCode}/total-sam`, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Create a new standard
 * @param {number} clientId - The client ID
 * @param {Object} standard - Standard data
 * @returns {Promise<Object>} Created standard
 */
export const createStandard = async (clientId, standard) => {
  const response = await api.post('/capacity/standards', standard, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Update an existing standard
 * @param {number} clientId - The client ID
 * @param {number} standardId - The standard ID to update
 * @param {Object} updates - Updated fields
 * @returns {Promise<Object>} Updated standard
 */
export const updateStandard = async (clientId, standardId, updates) => {
  const response = await api.put(`/capacity/standards/${standardId}`, updates, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Delete a standard
 * @param {number} clientId - The client ID
 * @param {number} standardId - The standard ID to delete
 * @returns {Promise<Object>} Delete confirmation
 */
export const deleteStandard = async (clientId, standardId) => {
  const response = await api.delete(`/capacity/standards/${standardId}`, {
    params: { client_id: clientId }
  })
  return response.data
}

// ============================================
// BOM Operations
// ============================================

/**
 * Get BOM headers for a client
 * @param {number} clientId - The client ID
 * @param {string|null} styleCode - Optional style code filter
 * @param {boolean} activeOnly - Whether to return only active BOMs
 * @returns {Promise<Array>} List of BOM headers
 */
export const getBOMHeaders = async (clientId, styleCode = null, activeOnly = true) => {
  const params = { client_id: clientId, active_only: activeOnly }
  if (styleCode) params.style_code = styleCode

  const response = await api.get('/capacity/bom', { params })
  return response.data
}

/**
 * Get BOM with full details
 * @param {number} clientId - The client ID
 * @param {number} headerId - The BOM header ID
 * @returns {Promise<Object>} BOM header with details
 */
export const getBOMWithDetails = async (clientId, headerId) => {
  const response = await api.get(`/capacity/bom/${headerId}`, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Create a new BOM header
 * @param {number} clientId - The client ID
 * @param {Object} header - BOM header data
 * @returns {Promise<Object>} Created BOM header
 */
export const createBOMHeader = async (clientId, header) => {
  const response = await api.post('/capacity/bom', header, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Update an existing BOM header
 * @param {number} clientId - The client ID
 * @param {number} headerId - The BOM header ID to update
 * @param {Object} updates - Updated fields
 * @returns {Promise<Object>} Updated BOM header
 */
export const updateBOMHeader = async (clientId, headerId, updates) => {
  const response = await api.put(`/capacity/bom/${headerId}`, updates, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Delete a BOM header
 * @param {number} clientId - The client ID
 * @param {number} headerId - The BOM header ID to delete
 * @param {boolean} hardDelete - Whether to permanently delete or soft delete
 * @returns {Promise<Object>} Delete confirmation
 */
export const deleteBOMHeader = async (clientId, headerId, hardDelete = false) => {
  const response = await api.delete(`/capacity/bom/${headerId}`, {
    params: { client_id: clientId, hard_delete: hardDelete }
  })
  return response.data
}

/**
 * Get BOM details for a header
 * @param {number} clientId - The client ID
 * @param {number} headerId - The BOM header ID
 * @returns {Promise<Array>} List of BOM detail lines
 */
export const getBOMDetails = async (clientId, headerId) => {
  const response = await api.get(`/capacity/bom/${headerId}/details`, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Create a new BOM detail line
 * @param {number} clientId - The client ID
 * @param {number} headerId - The BOM header ID
 * @param {Object} detail - BOM detail data
 * @returns {Promise<Object>} Created BOM detail
 */
export const createBOMDetail = async (clientId, headerId, detail) => {
  const response = await api.post(`/capacity/bom/${headerId}/details`, detail, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Update an existing BOM detail line
 * @param {number} clientId - The client ID
 * @param {number} detailId - The BOM detail ID to update
 * @param {Object} updates - Updated fields
 * @returns {Promise<Object>} Updated BOM detail
 */
export const updateBOMDetail = async (clientId, detailId, updates) => {
  const response = await api.put(`/capacity/bom/details/${detailId}`, updates, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Delete a BOM detail line
 * @param {number} clientId - The client ID
 * @param {number} detailId - The BOM detail ID to delete
 * @returns {Promise<Object>} Delete confirmation
 */
export const deleteBOMDetail = async (clientId, detailId) => {
  const response = await api.delete(`/capacity/bom/details/${detailId}`, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Run BOM explosion for a parent item
 * @param {number} clientId - The client ID
 * @param {string} parentItemCode - The parent item code to explode
 * @param {number} quantity - Quantity to calculate for
 * @returns {Promise<Object>} Exploded BOM with all components and quantities
 */
export const explodeBOM = async (clientId, parentItemCode, quantity) => {
  const response = await api.post('/capacity/bom/explode',
    { parent_item_code: parentItemCode, quantity },
    { params: { client_id: clientId } }
  )
  return response.data
}

// ============================================
// Stock Operations
// ============================================

/**
 * Get stock snapshots for a client
 * @param {number} clientId - The client ID
 * @param {string|null} snapshotDate - Optional snapshot date filter (YYYY-MM-DD)
 * @returns {Promise<Array>} List of stock snapshots
 */
export const getStockSnapshots = async (clientId, snapshotDate = null) => {
  const params = { client_id: clientId }
  if (snapshotDate) params.snapshot_date = snapshotDate

  const response = await api.get('/capacity/stock', { params })
  return response.data
}

/**
 * Get the latest stock for an item
 * @param {number} clientId - The client ID
 * @param {string} itemCode - The item code
 * @returns {Promise<Object>} Latest stock snapshot for the item
 */
export const getLatestStock = async (clientId, itemCode) => {
  const response = await api.get(`/capacity/stock/item/${itemCode}/latest`, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Get available stock for an item (considering allocations)
 * @param {number} clientId - The client ID
 * @param {string} itemCode - The item code
 * @returns {Promise<Object>} Available stock information
 */
export const getAvailableStock = async (clientId, itemCode) => {
  const response = await api.get(`/capacity/stock/item/${itemCode}/available`, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Get items with stock shortages
 * @param {number} clientId - The client ID
 * @returns {Promise<Array>} List of items with shortages
 */
export const getShortageItems = async (clientId) => {
  const response = await api.get('/capacity/stock/shortages', {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Create a new stock snapshot
 * @param {number} clientId - The client ID
 * @param {Object} snapshot - Stock snapshot data
 * @returns {Promise<Object>} Created stock snapshot
 */
export const createStockSnapshot = async (clientId, snapshot) => {
  const response = await api.post('/capacity/stock', snapshot, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Update an existing stock snapshot
 * @param {number} clientId - The client ID
 * @param {number} snapshotId - The snapshot ID to update
 * @param {Object} updates - Updated fields
 * @returns {Promise<Object>} Updated stock snapshot
 */
export const updateStockSnapshot = async (clientId, snapshotId, updates) => {
  const response = await api.put(`/capacity/stock/${snapshotId}`, updates, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Delete a stock snapshot
 * @param {number} clientId - The client ID
 * @param {number} snapshotId - The snapshot ID to delete
 * @returns {Promise<Object>} Delete confirmation
 */
export const deleteStockSnapshot = async (clientId, snapshotId) => {
  const response = await api.delete(`/capacity/stock/${snapshotId}`, {
    params: { client_id: clientId }
  })
  return response.data
}

// ============================================
// Component Check (MRP) Operations
// ============================================

/**
 * Run component check (Mini-MRP) for orders
 * @param {number} clientId - The client ID
 * @param {Array<number>|null} orderIds - Optional list of order IDs to check
 * @returns {Promise<Object>} Component check results with shortages
 */
export const runComponentCheck = async (clientId, orderIds = null) => {
  const response = await api.post('/capacity/component-check/run',
    { order_ids: orderIds },
    { params: { client_id: clientId } }
  )
  return response.data
}

/**
 * Get shortage components from latest run
 * @param {number} clientId - The client ID
 * @returns {Promise<Array>} List of shortage components
 */
export const getShortages = async (clientId) => {
  const response = await api.get('/capacity/component-check/shortages', {
    params: { client_id: clientId }
  })
  return response.data
}

// ============================================
// Capacity Analysis Operations
// ============================================

/**
 * Run capacity analysis for date range
 * @param {number} clientId - The client ID
 * @param {string} startDate - Analysis start date (YYYY-MM-DD)
 * @param {string} endDate - Analysis end date (YYYY-MM-DD)
 * @param {Array<number>|null} lineIds - Optional list of line IDs to analyze
 * @returns {Promise<Object>} Capacity analysis results
 */
export const runCapacityAnalysis = async (clientId, startDate, endDate, lineIds = null) => {
  const response = await api.post('/capacity/analysis/calculate',
    { start_date: startDate, end_date: endDate, line_ids: lineIds },
    { params: { client_id: clientId } }
  )
  return response.data
}

/**
 * Get bottleneck lines
 * @param {number} clientId - The client ID
 * @returns {Promise<Array>} List of bottleneck lines with utilization data
 */
export const getBottlenecks = async (clientId) => {
  const response = await api.get('/capacity/analysis/bottlenecks', {
    params: { client_id: clientId }
  })
  return response.data
}

// ============================================
// Schedule Operations
// ============================================

/**
 * Get schedules for a client
 * @param {number} clientId - The client ID
 * @param {string|null} status - Optional status filter
 * @returns {Promise<Array>} List of schedules
 */
export const getSchedules = async (clientId, status = null) => {
  const params = { client_id: clientId }
  if (status) params.status = status

  const response = await api.get('/capacity/schedules', { params })
  return response.data
}

/**
 * Get a specific schedule with details
 * @param {number} clientId - The client ID
 * @param {number} scheduleId - The schedule ID
 * @returns {Promise<Object>} Schedule with all details
 */
export const getSchedule = async (clientId, scheduleId) => {
  const response = await api.get(`/capacity/schedules/${scheduleId}`, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Create a new schedule
 * @param {number} clientId - The client ID
 * @param {Object} schedule - Schedule data
 * @returns {Promise<Object>} Created schedule
 */
export const createSchedule = async (clientId, schedule) => {
  const response = await api.post('/capacity/schedules', schedule, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Auto-generate schedule based on orders and capacity
 * @param {number} clientId - The client ID
 * @param {string} name - Schedule name
 * @param {string} startDate - Schedule start date (YYYY-MM-DD)
 * @param {string} endDate - Schedule end date (YYYY-MM-DD)
 * @param {Array<number>|null} orderIds - Optional list of order IDs to include
 * @returns {Promise<Object>} Generated schedule
 */
export const generateSchedule = async (clientId, name, startDate, endDate, orderIds = null) => {
  const response = await api.post('/capacity/schedules/generate',
    { name, start_date: startDate, end_date: endDate, order_ids: orderIds },
    { params: { client_id: clientId } }
  )
  return response.data
}

/**
 * Commit schedule for KPI tracking
 * @param {number} scheduleId - The schedule ID to commit
 * @param {Object} kpiCommitments - KPI commitment values
 * @returns {Promise<Object>} Committed schedule with KPI data
 */
export const commitSchedule = async (scheduleId, kpiCommitments) => {
  const response = await api.post(`/capacity/schedules/${scheduleId}/commit`,
    { kpi_commitments: kpiCommitments }
  )
  return response.data
}

// ============================================
// Scenario Operations
// ============================================

/**
 * Get scenarios for a client
 * @param {number} clientId - The client ID
 * @returns {Promise<Array>} List of scenarios
 */
export const getScenarios = async (clientId) => {
  const response = await api.get('/capacity/scenarios', {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Get a specific scenario with results
 * @param {number} clientId - The client ID
 * @param {number} scenarioId - The scenario ID
 * @returns {Promise<Object>} Scenario with results
 */
export const getScenario = async (clientId, scenarioId) => {
  const response = await api.get(`/capacity/scenarios/${scenarioId}`, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Create a new scenario
 * @param {number} clientId - The client ID
 * @param {string} name - Scenario name
 * @param {string} type - Scenario type
 * @param {Object} parameters - Scenario parameters
 * @param {number|null} baseScheduleId - Optional base schedule ID
 * @returns {Promise<Object>} Created scenario
 */
export const createScenario = async (clientId, name, type, parameters, baseScheduleId = null) => {
  const response = await api.post('/capacity/scenarios',
    { name, scenario_type: type, parameters, base_schedule_id: baseScheduleId },
    { params: { client_id: clientId } }
  )
  return response.data
}

/**
 * Compare multiple scenarios
 * @param {number} clientId - The client ID
 * @param {Array<number>} scenarioIds - List of scenario IDs to compare
 * @returns {Promise<Object>} Comparison results
 */
export const compareScenarios = async (clientId, scenarioIds) => {
  const response = await api.post('/capacity/scenarios/compare',
    { scenario_ids: scenarioIds },
    { params: { client_id: clientId } }
  )
  return response.data
}

// ============================================
// KPI Integration Operations
// ============================================

/**
 * Get KPI commitments for a schedule
 * @param {number} clientId - The client ID
 * @param {number|null} scheduleId - Optional schedule ID filter
 * @returns {Promise<Array>} List of KPI commitments
 */
export const getKPICommitments = async (clientId, scheduleId = null) => {
  const params = { client_id: clientId }
  if (scheduleId) params.schedule_id = scheduleId

  const response = await api.get('/capacity/kpi/commitments', { params })
  return response.data
}

/**
 * Get variance report (committed vs actual)
 * @param {number} clientId - The client ID
 * @param {number|null} scheduleId - Optional schedule ID filter
 * @returns {Promise<Object>} Variance report data
 */
export const getKPIVariance = async (clientId, scheduleId = null) => {
  const params = { client_id: clientId }
  if (scheduleId) params.schedule_id = scheduleId

  const response = await api.get('/capacity/kpi/variance', { params })
  return response.data
}

// ============================================
// Scenario Run/Delete Operations
// ============================================

/**
 * Run/evaluate a scenario (apply parameters and analyze impact)
 * @param {number} clientId - The client ID
 * @param {number} scenarioId - The scenario ID to run
 * @param {string|null} periodStart - Optional analysis period start (YYYY-MM-DD)
 * @param {string|null} periodEnd - Optional analysis period end (YYYY-MM-DD)
 * @returns {Promise<Object>} Scenario results with original and modified metrics
 */
export const runScenario = async (clientId, scenarioId, periodStart = null, periodEnd = null) => {
  const payload = {}
  if (periodStart) payload.period_start = periodStart
  if (periodEnd) payload.period_end = periodEnd

  const response = await api.post(`/capacity/scenarios/${scenarioId}/run`, payload, {
    params: { client_id: clientId }
  })
  return response.data
}

/**
 * Delete a scenario
 * @param {number} clientId - The client ID
 * @param {number} scenarioId - The scenario ID to delete
 * @returns {Promise<Object>} Delete confirmation
 */
export const deleteScenario = async (clientId, scenarioId) => {
  const response = await api.delete(`/capacity/scenarios/${scenarioId}`, {
    params: { client_id: clientId }
  })
  return response.data
}

// ============================================
// Workbook Bulk Save
// ============================================

/**
 * Save complete workbook (all worksheets)
 * @param {number} clientId - The client ID
 * @param {Object} workbookData - Object keyed by worksheet name with data arrays
 * @returns {Promise<Object>} Save results
 */
export const saveWorkbook = async (clientId, workbookData) => {
  const results = { success: [], failed: [] }

  for (const [worksheetName, data] of Object.entries(workbookData)) {
    try {
      await saveWorksheet(worksheetName, clientId, data)
      results.success.push(worksheetName)
    } catch (error) {
      results.failed.push({ worksheetName, error: error.message })
    }
  }

  return results
}

// ============================================
// Utility Functions
// ============================================

// ============================================
// Default Export
// ============================================

export default {
  // Workbook
  loadWorkbook,
  saveWorksheet,
  // Calendar
  getCalendarEntries,
  createCalendarEntry,
  updateCalendarEntry,
  deleteCalendarEntry,
  // Production Lines
  getProductionLines,
  createProductionLine,
  updateProductionLine,
  deleteProductionLine,
  // Orders
  getOrders,
  getOrdersForScheduling,
  createOrder,
  updateOrder,
  updateOrderStatus,
  deleteOrder,
  // Standards
  getStandards,
  getStandardsByStyle,
  getTotalSAMForStyle,
  createStandard,
  updateStandard,
  deleteStandard,
  // BOM
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
  // Stock
  getStockSnapshots,
  getLatestStock,
  getAvailableStock,
  getShortageItems,
  createStockSnapshot,
  updateStockSnapshot,
  deleteStockSnapshot,
  // Component Check (MRP)
  runComponentCheck,
  getShortages,
  // Capacity Analysis
  runCapacityAnalysis,
  getBottlenecks,
  // Schedules
  getSchedules,
  getSchedule,
  createSchedule,
  generateSchedule,
  commitSchedule,
  // Scenarios
  getScenarios,
  getScenario,
  createScenario,
  compareScenarios,
  runScenario,
  deleteScenario,
  // Workbook Bulk
  saveWorkbook,
  // KPI Integration
  getKPICommitments,
  getKPIVariance,
}
