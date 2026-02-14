/**
 * Capacity Planning API Service - Unit Tests
 *
 * Tests all exported API functions (~60 exports) from capacityPlanning.js.
 * Verifies correct HTTP methods, URLs, query params, request bodies,
 * and response data extraction.
 */
import { vi } from 'vitest'

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}))

import api from './client'
import {
  // Workbook
  loadWorkbook,
  saveWorksheet,
  saveWorkbook,
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
  // KPI Integration
  getKPICommitments,
  getKPIActuals,
  getKPIVariance,
  // Utility
  isFeatureEnabled,
  getModuleInfo,
} from './capacityPlanning'

describe('Capacity Planning API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ============================================
  // Workbook Operations
  // ============================================

  describe('Workbook Operations', () => {
    it('loadWorkbook calls GET with client ID in path', async () => {
      const mockData = { master_calendar: [], production_lines: [] }
      api.get.mockResolvedValue({ data: mockData })

      const result = await loadWorkbook(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/workbook/5')
      expect(result).toEqual(mockData)
    })

    it('saveWorksheet calls PUT with worksheet name, client ID, and data', async () => {
      const rows = [{ id: 1, date: '2026-01-01' }]
      api.put.mockResolvedValue({ data: { message: 'saved' } })

      const result = await saveWorksheet('master_calendar', 3, rows)

      expect(api.put).toHaveBeenCalledWith(
        '/capacity/workbook/3/master_calendar',
        rows
      )
      expect(result).toEqual({ message: 'saved' })
    })

    it('saveWorkbook iterates all worksheets and collects results', async () => {
      api.put.mockResolvedValue({ data: { message: 'saved' } })

      const workbookData = {
        master_calendar: [{ id: 1 }],
        production_lines: [{ id: 2 }],
      }
      const result = await saveWorkbook(7, workbookData)

      expect(api.put).toHaveBeenCalledTimes(2)
      expect(api.put).toHaveBeenCalledWith(
        '/capacity/workbook/7/master_calendar',
        [{ id: 1 }]
      )
      expect(api.put).toHaveBeenCalledWith(
        '/capacity/workbook/7/production_lines',
        [{ id: 2 }]
      )
      expect(result.success).toEqual(['master_calendar', 'production_lines'])
      expect(result.failed).toEqual([])
    })

    it('saveWorkbook records failures per worksheet', async () => {
      api.put
        .mockResolvedValueOnce({ data: { message: 'saved' } })
        .mockRejectedValueOnce(new Error('Server error'))

      const workbookData = {
        master_calendar: [{ id: 1 }],
        orders: [{ id: 2 }],
      }
      const result = await saveWorkbook(7, workbookData)

      expect(result.success).toEqual(['master_calendar'])
      expect(result.failed).toEqual([
        { worksheetName: 'orders', error: 'Server error' },
      ])
    })
  })

  // ============================================
  // Calendar Operations
  // ============================================

  describe('Calendar Operations', () => {
    it('getCalendarEntries calls GET with client_id param', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1 }] })

      const result = await getCalendarEntries(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/calendar', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ id: 1 }])
    })

    it('getCalendarEntries includes date range when provided', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getCalendarEntries(5, '2026-01-01', '2026-01-31')

      expect(api.get).toHaveBeenCalledWith('/capacity/calendar', {
        params: {
          client_id: 5,
          start_date: '2026-01-01',
          end_date: '2026-01-31',
        },
      })
    })

    it('getCalendarEntries omits null date params', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getCalendarEntries(5, null, null)

      expect(api.get).toHaveBeenCalledWith('/capacity/calendar', {
        params: { client_id: 5 },
      })
    })

    it('createCalendarEntry calls POST with body and client_id param', async () => {
      const entry = { date: '2026-02-01', type: 'holiday', name: 'National Day' }
      api.post.mockResolvedValue({ data: { id: 10, ...entry } })

      const result = await createCalendarEntry(5, entry)

      expect(api.post).toHaveBeenCalledWith('/capacity/calendar', entry, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 10, ...entry })
    })

    it('updateCalendarEntry calls PUT with entry ID and client_id param', async () => {
      const updates = { name: 'Updated Holiday' }
      api.put.mockResolvedValue({ data: { id: 10, name: 'Updated Holiday' } })

      const result = await updateCalendarEntry(5, 10, updates)

      expect(api.put).toHaveBeenCalledWith('/capacity/calendar/10', updates, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 10, name: 'Updated Holiday' })
    })

    it('deleteCalendarEntry calls DELETE with entry ID and client_id param', async () => {
      api.delete.mockResolvedValue({ data: { message: 'deleted' } })

      const result = await deleteCalendarEntry(5, 10)

      expect(api.delete).toHaveBeenCalledWith('/capacity/calendar/10', {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ message: 'deleted' })
    })
  })

  // ============================================
  // Production Lines Operations
  // ============================================

  describe('Production Lines Operations', () => {
    it('getProductionLines calls GET with client_id and include_inactive params', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1, name: 'Line A' }] })

      const result = await getProductionLines(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/lines', {
        params: { client_id: 5, include_inactive: false },
      })
      expect(result).toEqual([{ id: 1, name: 'Line A' }])
    })

    it('getProductionLines includes inactive and department when provided', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getProductionLines(5, true, 'Sewing')

      expect(api.get).toHaveBeenCalledWith('/capacity/lines', {
        params: {
          client_id: 5,
          include_inactive: true,
          department: 'Sewing',
        },
      })
    })

    it('getProductionLines omits department when null', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getProductionLines(5, false, null)

      expect(api.get).toHaveBeenCalledWith('/capacity/lines', {
        params: { client_id: 5, include_inactive: false },
      })
    })

    it('createProductionLine calls POST with body and client_id param', async () => {
      const line = { name: 'Line B', capacity: 100 }
      api.post.mockResolvedValue({ data: { id: 2, ...line } })

      const result = await createProductionLine(5, line)

      expect(api.post).toHaveBeenCalledWith('/capacity/lines', line, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 2, ...line })
    })

    it('updateProductionLine calls PUT with line ID and client_id param', async () => {
      const updates = { capacity: 120 }
      api.put.mockResolvedValue({ data: { id: 2, capacity: 120 } })

      const result = await updateProductionLine(5, 2, updates)

      expect(api.put).toHaveBeenCalledWith('/capacity/lines/2', updates, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 2, capacity: 120 })
    })

    it('deleteProductionLine calls DELETE with line ID and default hardDelete false', async () => {
      api.delete.mockResolvedValue({ data: { message: 'deleted' } })

      const result = await deleteProductionLine(5, 2)

      expect(api.delete).toHaveBeenCalledWith('/capacity/lines/2', {
        params: { client_id: 5, hard_delete: false },
      })
      expect(result).toEqual({ message: 'deleted' })
    })

    it('deleteProductionLine passes hard_delete true when requested', async () => {
      api.delete.mockResolvedValue({ data: { message: 'permanently deleted' } })

      await deleteProductionLine(5, 2, true)

      expect(api.delete).toHaveBeenCalledWith('/capacity/lines/2', {
        params: { client_id: 5, hard_delete: true },
      })
    })
  })

  // ============================================
  // Orders Operations
  // ============================================

  describe('Orders Operations', () => {
    it('getOrders calls GET with defaults for skip and limit', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1, style: 'T-SHIRT' }] })

      const result = await getOrders(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/orders', {
        params: { client_id: 5, skip: 0, limit: 100 },
      })
      expect(result).toEqual([{ id: 1, style: 'T-SHIRT' }])
    })

    it('getOrders includes status filter when provided', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getOrders(5, 'confirmed', 10, 50)

      expect(api.get).toHaveBeenCalledWith('/capacity/orders', {
        params: { client_id: 5, status: 'confirmed', skip: 10, limit: 50 },
      })
    })

    it('getOrdersForScheduling calls GET with client_id', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1 }] })

      const result = await getOrdersForScheduling(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/orders/scheduling', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ id: 1 }])
    })

    it('getOrdersForScheduling includes date range when provided', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getOrdersForScheduling(5, '2026-03-01', '2026-03-31')

      expect(api.get).toHaveBeenCalledWith('/capacity/orders/scheduling', {
        params: {
          client_id: 5,
          start_date: '2026-03-01',
          end_date: '2026-03-31',
        },
      })
    })

    it('createOrder calls POST with body and client_id param', async () => {
      const order = { style_code: 'POLO', quantity: 5000 }
      api.post.mockResolvedValue({ data: { id: 10, ...order } })

      const result = await createOrder(5, order)

      expect(api.post).toHaveBeenCalledWith('/capacity/orders', order, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 10, ...order })
    })

    it('updateOrder calls PUT with order ID and client_id param', async () => {
      const updates = { quantity: 6000 }
      api.put.mockResolvedValue({ data: { id: 10, quantity: 6000 } })

      const result = await updateOrder(5, 10, updates)

      expect(api.put).toHaveBeenCalledWith('/capacity/orders/10', updates, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 10, quantity: 6000 })
    })

    it('updateOrderStatus calls PATCH with status body and client_id param', async () => {
      api.patch.mockResolvedValue({ data: { id: 10, status: 'in_progress' } })

      const result = await updateOrderStatus(5, 10, 'in_progress')

      expect(api.patch).toHaveBeenCalledWith(
        '/capacity/orders/10/status',
        { status: 'in_progress' },
        { params: { client_id: 5 } }
      )
      expect(result).toEqual({ id: 10, status: 'in_progress' })
    })

    it('deleteOrder calls DELETE with order ID and client_id param', async () => {
      api.delete.mockResolvedValue({ data: { message: 'deleted' } })

      const result = await deleteOrder(5, 10)

      expect(api.delete).toHaveBeenCalledWith('/capacity/orders/10', {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ message: 'deleted' })
    })
  })

  // ============================================
  // Standards Operations
  // ============================================

  describe('Standards Operations', () => {
    it('getStandards calls GET with client_id param', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1, operation: 'Sewing' }] })

      const result = await getStandards(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/standards', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ id: 1, operation: 'Sewing' }])
    })

    it('getStandards includes style_code filter when provided', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getStandards(5, 'POLO-001')

      expect(api.get).toHaveBeenCalledWith('/capacity/standards', {
        params: { client_id: 5, style_code: 'POLO-001' },
      })
    })

    it('getStandardsByStyle calls GET with style code in path', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1, sam: 12.5 }] })

      const result = await getStandardsByStyle(5, 'POLO-001')

      expect(api.get).toHaveBeenCalledWith(
        '/capacity/standards/style/POLO-001',
        { params: { client_id: 5 } }
      )
      expect(result).toEqual([{ id: 1, sam: 12.5 }])
    })

    it('getTotalSAMForStyle calls GET with style code and total-sam path', async () => {
      api.get.mockResolvedValue({ data: { total_sam: 45.2 } })

      const result = await getTotalSAMForStyle(5, 'POLO-001')

      expect(api.get).toHaveBeenCalledWith(
        '/capacity/standards/style/POLO-001/total-sam',
        { params: { client_id: 5 } }
      )
      expect(result).toEqual({ total_sam: 45.2 })
    })

    it('createStandard calls POST with body and client_id param', async () => {
      const standard = { operation: 'Cutting', sam: 5.3 }
      api.post.mockResolvedValue({ data: { id: 3, ...standard } })

      const result = await createStandard(5, standard)

      expect(api.post).toHaveBeenCalledWith('/capacity/standards', standard, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 3, ...standard })
    })

    it('updateStandard calls PUT with standard ID and client_id param', async () => {
      const updates = { sam: 6.0 }
      api.put.mockResolvedValue({ data: { id: 3, sam: 6.0 } })

      const result = await updateStandard(5, 3, updates)

      expect(api.put).toHaveBeenCalledWith('/capacity/standards/3', updates, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 3, sam: 6.0 })
    })

    it('deleteStandard calls DELETE with standard ID and client_id param', async () => {
      api.delete.mockResolvedValue({ data: { message: 'deleted' } })

      const result = await deleteStandard(5, 3)

      expect(api.delete).toHaveBeenCalledWith('/capacity/standards/3', {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ message: 'deleted' })
    })
  })

  // ============================================
  // BOM Operations
  // ============================================

  describe('BOM Operations', () => {
    it('getBOMHeaders calls GET with client_id and active_only params', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1, style_code: 'POLO' }] })

      const result = await getBOMHeaders(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/bom', {
        params: { client_id: 5, active_only: true },
      })
      expect(result).toEqual([{ id: 1, style_code: 'POLO' }])
    })

    it('getBOMHeaders includes style_code filter and activeOnly override', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getBOMHeaders(5, 'TSHIRT-001', false)

      expect(api.get).toHaveBeenCalledWith('/capacity/bom', {
        params: {
          client_id: 5,
          active_only: false,
          style_code: 'TSHIRT-001',
        },
      })
    })

    it('getBOMWithDetails calls GET with header ID in path', async () => {
      const detail = { id: 1, components: [] }
      api.get.mockResolvedValue({ data: detail })

      const result = await getBOMWithDetails(5, 20)

      expect(api.get).toHaveBeenCalledWith('/capacity/bom/20', {
        params: { client_id: 5 },
      })
      expect(result).toEqual(detail)
    })

    it('createBOMHeader calls POST with body and client_id param', async () => {
      const header = { style_code: 'POLO', version: 1 }
      api.post.mockResolvedValue({ data: { id: 20, ...header } })

      const result = await createBOMHeader(5, header)

      expect(api.post).toHaveBeenCalledWith('/capacity/bom', header, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 20, ...header })
    })

    it('updateBOMHeader calls PUT with header ID and client_id param', async () => {
      const updates = { version: 2 }
      api.put.mockResolvedValue({ data: { id: 20, version: 2 } })

      const result = await updateBOMHeader(5, 20, updates)

      expect(api.put).toHaveBeenCalledWith('/capacity/bom/20', updates, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 20, version: 2 })
    })

    it('deleteBOMHeader calls DELETE with default soft delete', async () => {
      api.delete.mockResolvedValue({ data: { message: 'deleted' } })

      const result = await deleteBOMHeader(5, 20)

      expect(api.delete).toHaveBeenCalledWith('/capacity/bom/20', {
        params: { client_id: 5, hard_delete: false },
      })
      expect(result).toEqual({ message: 'deleted' })
    })

    it('deleteBOMHeader passes hard_delete true when requested', async () => {
      api.delete.mockResolvedValue({ data: { message: 'permanently deleted' } })

      await deleteBOMHeader(5, 20, true)

      expect(api.delete).toHaveBeenCalledWith('/capacity/bom/20', {
        params: { client_id: 5, hard_delete: true },
      })
    })

    it('getBOMDetails calls GET with header ID in path', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1, item_code: 'FABRIC-A' }] })

      const result = await getBOMDetails(5, 20)

      expect(api.get).toHaveBeenCalledWith('/capacity/bom/20/details', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ id: 1, item_code: 'FABRIC-A' }])
    })

    it('createBOMDetail calls POST with header ID in path and body', async () => {
      const detail = { item_code: 'FABRIC-B', quantity: 1.5 }
      api.post.mockResolvedValue({ data: { id: 5, ...detail } })

      const result = await createBOMDetail(5, 20, detail)

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/bom/20/details',
        detail,
        { params: { client_id: 5 } }
      )
      expect(result).toEqual({ id: 5, ...detail })
    })

    it('updateBOMDetail calls PUT with detail ID in path', async () => {
      const updates = { quantity: 2.0 }
      api.put.mockResolvedValue({ data: { id: 5, quantity: 2.0 } })

      const result = await updateBOMDetail(5, 5, updates)

      expect(api.put).toHaveBeenCalledWith('/capacity/bom/details/5', updates, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 5, quantity: 2.0 })
    })

    it('deleteBOMDetail calls DELETE with detail ID in path', async () => {
      api.delete.mockResolvedValue({ data: { message: 'deleted' } })

      const result = await deleteBOMDetail(5, 5)

      expect(api.delete).toHaveBeenCalledWith('/capacity/bom/details/5', {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ message: 'deleted' })
    })

    it('explodeBOM calls POST with parent_item_code and quantity', async () => {
      const explosion = { components: [{ item: 'THREAD', qty: 100 }] }
      api.post.mockResolvedValue({ data: explosion })

      const result = await explodeBOM(5, 'POLO-PARENT', 500)

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/bom/explode',
        { parent_item_code: 'POLO-PARENT', quantity: 500 },
        { params: { client_id: 5 } }
      )
      expect(result).toEqual(explosion)
    })
  })

  // ============================================
  // Stock Operations
  // ============================================

  describe('Stock Operations', () => {
    it('getStockSnapshots calls GET with client_id param', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1, item_code: 'FABRIC-A' }] })

      const result = await getStockSnapshots(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/stock', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ id: 1, item_code: 'FABRIC-A' }])
    })

    it('getStockSnapshots includes snapshot_date when provided', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getStockSnapshots(5, '2026-02-01')

      expect(api.get).toHaveBeenCalledWith('/capacity/stock', {
        params: { client_id: 5, snapshot_date: '2026-02-01' },
      })
    })

    it('getLatestStock calls GET with item code in path', async () => {
      api.get.mockResolvedValue({ data: { item_code: 'FABRIC-A', qty: 1000 } })

      const result = await getLatestStock(5, 'FABRIC-A')

      expect(api.get).toHaveBeenCalledWith(
        '/capacity/stock/item/FABRIC-A/latest',
        { params: { client_id: 5 } }
      )
      expect(result).toEqual({ item_code: 'FABRIC-A', qty: 1000 })
    })

    it('getAvailableStock calls GET with item code in path', async () => {
      api.get.mockResolvedValue({ data: { item_code: 'FABRIC-A', available: 800 } })

      const result = await getAvailableStock(5, 'FABRIC-A')

      expect(api.get).toHaveBeenCalledWith(
        '/capacity/stock/item/FABRIC-A/available',
        { params: { client_id: 5 } }
      )
      expect(result).toEqual({ item_code: 'FABRIC-A', available: 800 })
    })

    it('getShortageItems calls GET with client_id param', async () => {
      api.get.mockResolvedValue({ data: [{ item_code: 'BUTTON-X', shortage: 200 }] })

      const result = await getShortageItems(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/stock/shortages', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ item_code: 'BUTTON-X', shortage: 200 }])
    })

    it('createStockSnapshot calls POST with body and client_id param', async () => {
      const snapshot = { item_code: 'FABRIC-B', quantity: 500 }
      api.post.mockResolvedValue({ data: { id: 10, ...snapshot } })

      const result = await createStockSnapshot(5, snapshot)

      expect(api.post).toHaveBeenCalledWith('/capacity/stock', snapshot, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 10, ...snapshot })
    })

    it('updateStockSnapshot calls PUT with snapshot ID and client_id', async () => {
      const updates = { quantity: 450 }
      api.put.mockResolvedValue({ data: { id: 10, quantity: 450 } })

      const result = await updateStockSnapshot(5, 10, updates)

      expect(api.put).toHaveBeenCalledWith('/capacity/stock/10', updates, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 10, quantity: 450 })
    })

    it('deleteStockSnapshot calls DELETE with snapshot ID and client_id', async () => {
      api.delete.mockResolvedValue({ data: { message: 'deleted' } })

      const result = await deleteStockSnapshot(5, 10)

      expect(api.delete).toHaveBeenCalledWith('/capacity/stock/10', {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ message: 'deleted' })
    })
  })

  // ============================================
  // Component Check (MRP) Operations
  // ============================================

  describe('Component Check (MRP) Operations', () => {
    it('runComponentCheck calls POST with null order_ids by default', async () => {
      const checkResult = { shortages: [], coverage: 100 }
      api.post.mockResolvedValue({ data: checkResult })

      const result = await runComponentCheck(5)

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/component-check/run',
        { order_ids: null },
        { params: { client_id: 5 } }
      )
      expect(result).toEqual(checkResult)
    })

    it('runComponentCheck passes specific order IDs', async () => {
      api.post.mockResolvedValue({ data: { shortages: [] } })

      await runComponentCheck(5, [101, 102, 103])

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/component-check/run',
        { order_ids: [101, 102, 103] },
        { params: { client_id: 5 } }
      )
    })

    it('getShortages calls GET with client_id param', async () => {
      api.get.mockResolvedValue({
        data: [{ item_code: 'ZIPPER', shortage: 50 }],
      })

      const result = await getShortages(5)

      expect(api.get).toHaveBeenCalledWith(
        '/capacity/component-check/shortages',
        { params: { client_id: 5 } }
      )
      expect(result).toEqual([{ item_code: 'ZIPPER', shortage: 50 }])
    })
  })

  // ============================================
  // Capacity Analysis Operations
  // ============================================

  describe('Capacity Analysis Operations', () => {
    it('runCapacityAnalysis calls POST with date range and no line IDs', async () => {
      const analysis = { utilization: 0.85 }
      api.post.mockResolvedValue({ data: analysis })

      const result = await runCapacityAnalysis(5, '2026-03-01', '2026-03-31')

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/analysis/calculate',
        {
          start_date: '2026-03-01',
          end_date: '2026-03-31',
          line_ids: null,
        },
        { params: { client_id: 5 } }
      )
      expect(result).toEqual(analysis)
    })

    it('runCapacityAnalysis passes specific line IDs', async () => {
      api.post.mockResolvedValue({ data: {} })

      await runCapacityAnalysis(5, '2026-03-01', '2026-03-31', [1, 2, 3])

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/analysis/calculate',
        {
          start_date: '2026-03-01',
          end_date: '2026-03-31',
          line_ids: [1, 2, 3],
        },
        { params: { client_id: 5 } }
      )
    })

    it('getBottlenecks calls GET with client_id param', async () => {
      api.get.mockResolvedValue({
        data: [{ line_id: 1, utilization: 0.98 }],
      })

      const result = await getBottlenecks(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/analysis/bottlenecks', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ line_id: 1, utilization: 0.98 }])
    })
  })

  // ============================================
  // Schedule Operations
  // ============================================

  describe('Schedule Operations', () => {
    it('getSchedules calls GET with client_id param', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1, name: 'Week 10' }] })

      const result = await getSchedules(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/schedules', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ id: 1, name: 'Week 10' }])
    })

    it('getSchedules includes status filter when provided', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getSchedules(5, 'committed')

      expect(api.get).toHaveBeenCalledWith('/capacity/schedules', {
        params: { client_id: 5, status: 'committed' },
      })
    })

    it('getSchedule calls GET with schedule ID in path', async () => {
      const schedule = { id: 1, name: 'Week 10', details: [] }
      api.get.mockResolvedValue({ data: schedule })

      const result = await getSchedule(5, 1)

      expect(api.get).toHaveBeenCalledWith('/capacity/schedules/1', {
        params: { client_id: 5 },
      })
      expect(result).toEqual(schedule)
    })

    it('createSchedule calls POST with body and client_id param', async () => {
      const schedule = { name: 'Week 11', start_date: '2026-03-09' }
      api.post.mockResolvedValue({ data: { id: 2, ...schedule } })

      const result = await createSchedule(5, schedule)

      expect(api.post).toHaveBeenCalledWith('/capacity/schedules', schedule, {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ id: 2, ...schedule })
    })

    it('generateSchedule calls POST with name, dates, and no order IDs', async () => {
      const generated = { id: 3, name: 'Auto Schedule', assignments: [] }
      api.post.mockResolvedValue({ data: generated })

      const result = await generateSchedule(
        5,
        'Auto Schedule',
        '2026-03-01',
        '2026-03-31'
      )

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/schedules/generate',
        {
          name: 'Auto Schedule',
          start_date: '2026-03-01',
          end_date: '2026-03-31',
          order_ids: null,
        },
        { params: { client_id: 5 } }
      )
      expect(result).toEqual(generated)
    })

    it('generateSchedule passes specific order IDs', async () => {
      api.post.mockResolvedValue({ data: {} })

      await generateSchedule(5, 'Selective', '2026-03-01', '2026-03-31', [1, 2])

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/schedules/generate',
        {
          name: 'Selective',
          start_date: '2026-03-01',
          end_date: '2026-03-31',
          order_ids: [1, 2],
        },
        { params: { client_id: 5 } }
      )
    })

    it('commitSchedule calls POST with schedule ID and KPI commitments (no client_id)', async () => {
      const kpis = { otd_target: 95, efficiency_target: 80 }
      const committed = { id: 1, status: 'committed', kpis }
      api.post.mockResolvedValue({ data: committed })

      const result = await commitSchedule(1, kpis)

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/schedules/1/commit',
        { kpi_commitments: kpis }
      )
      expect(result).toEqual(committed)
    })
  })

  // ============================================
  // Scenario Operations
  // ============================================

  describe('Scenario Operations', () => {
    it('getScenarios calls GET with client_id param', async () => {
      api.get.mockResolvedValue({ data: [{ id: 1, name: 'Overtime' }] })

      const result = await getScenarios(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/scenarios', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ id: 1, name: 'Overtime' }])
    })

    it('getScenario calls GET with scenario ID in path', async () => {
      const scenario = { id: 1, name: 'Overtime', results: {} }
      api.get.mockResolvedValue({ data: scenario })

      const result = await getScenario(5, 1)

      expect(api.get).toHaveBeenCalledWith('/capacity/scenarios/1', {
        params: { client_id: 5 },
      })
      expect(result).toEqual(scenario)
    })

    it('createScenario calls POST with full scenario body', async () => {
      const params = { overtime_hours: 2 }
      api.post.mockResolvedValue({ data: { id: 2, name: 'OT Scenario' } })

      const result = await createScenario(5, 'OT Scenario', 'OVERTIME', params)

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/scenarios',
        {
          name: 'OT Scenario',
          scenario_type: 'OVERTIME',
          parameters: params,
          base_schedule_id: null,
        },
        { params: { client_id: 5 } }
      )
      expect(result).toEqual({ id: 2, name: 'OT Scenario' })
    })

    it('createScenario includes base_schedule_id when provided', async () => {
      api.post.mockResolvedValue({ data: { id: 3 } })

      await createScenario(5, 'Based', 'SUBCONTRACT', { vendor: 'X' }, 10)

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/scenarios',
        {
          name: 'Based',
          scenario_type: 'SUBCONTRACT',
          parameters: { vendor: 'X' },
          base_schedule_id: 10,
        },
        { params: { client_id: 5 } }
      )
    })

    it('compareScenarios calls POST with scenario IDs array', async () => {
      const comparison = { scenarios: [], metrics: [] }
      api.post.mockResolvedValue({ data: comparison })

      const result = await compareScenarios(5, [1, 2, 3])

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/scenarios/compare',
        { scenario_ids: [1, 2, 3] },
        { params: { client_id: 5 } }
      )
      expect(result).toEqual(comparison)
    })

    it('runScenario calls POST with scenario ID and no period dates', async () => {
      const results = { original: {}, modified: {} }
      api.post.mockResolvedValue({ data: results })

      const result = await runScenario(5, 1)

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/scenarios/1/run',
        {},
        { params: { client_id: 5 } }
      )
      expect(result).toEqual(results)
    })

    it('runScenario includes period dates when provided', async () => {
      api.post.mockResolvedValue({ data: {} })

      await runScenario(5, 1, '2026-03-01', '2026-03-31')

      expect(api.post).toHaveBeenCalledWith(
        '/capacity/scenarios/1/run',
        { period_start: '2026-03-01', period_end: '2026-03-31' },
        { params: { client_id: 5 } }
      )
    })

    it('deleteScenario calls DELETE with scenario ID and client_id', async () => {
      api.delete.mockResolvedValue({ data: { message: 'deleted' } })

      const result = await deleteScenario(5, 1)

      expect(api.delete).toHaveBeenCalledWith('/capacity/scenarios/1', {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ message: 'deleted' })
    })
  })

  // ============================================
  // KPI Integration Operations
  // ============================================

  describe('KPI Integration Operations', () => {
    it('getKPICommitments calls GET with client_id param', async () => {
      api.get.mockResolvedValue({
        data: [{ schedule_id: 1, otd_target: 95 }],
      })

      const result = await getKPICommitments(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/kpi/commitments', {
        params: { client_id: 5 },
      })
      expect(result).toEqual([{ schedule_id: 1, otd_target: 95 }])
    })

    it('getKPICommitments includes schedule_id filter when provided', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getKPICommitments(5, 10)

      expect(api.get).toHaveBeenCalledWith('/capacity/kpi/commitments', {
        params: { client_id: 5, schedule_id: 10 },
      })
    })

    it('getKPIActuals calls GET with client_id and period params', async () => {
      api.get.mockResolvedValue({ data: { efficiency: 82 } })

      const result = await getKPIActuals(5, 'month')

      expect(api.get).toHaveBeenCalledWith('/capacity/kpi/actuals', {
        params: { client_id: 5, period: 'month' },
      })
      expect(result).toEqual({ efficiency: 82 })
    })

    it('getKPIVariance calls GET with client_id param', async () => {
      api.get.mockResolvedValue({
        data: { otd_variance: -2.5, efficiency_variance: 1.3 },
      })

      const result = await getKPIVariance(5)

      expect(api.get).toHaveBeenCalledWith('/capacity/kpi/variance', {
        params: { client_id: 5 },
      })
      expect(result).toEqual({ otd_variance: -2.5, efficiency_variance: 1.3 })
    })

    it('getKPIVariance includes schedule_id filter when provided', async () => {
      api.get.mockResolvedValue({ data: {} })

      await getKPIVariance(5, 10)

      expect(api.get).toHaveBeenCalledWith('/capacity/kpi/variance', {
        params: { client_id: 5, schedule_id: 10 },
      })
    })
  })

  // ============================================
  // Utility Operations
  // ============================================

  describe('Utility Operations', () => {
    it('isFeatureEnabled returns true when API responds with enabled: true', async () => {
      api.get.mockResolvedValue({ data: { enabled: true } })

      const result = await isFeatureEnabled()

      expect(api.get).toHaveBeenCalledWith('/capacity/health')
      expect(result).toBe(true)
    })

    it('isFeatureEnabled returns false when API responds with enabled: false', async () => {
      api.get.mockResolvedValue({ data: { enabled: false } })

      const result = await isFeatureEnabled()

      expect(result).toBe(false)
    })

    it('isFeatureEnabled returns false when API call fails', async () => {
      api.get.mockRejectedValue(new Error('Network error'))

      const result = await isFeatureEnabled()

      expect(result).toBe(false)
    })

    it('isFeatureEnabled returns false when response data is null', async () => {
      api.get.mockResolvedValue({ data: null })

      const result = await isFeatureEnabled()

      expect(result).toBe(false)
    })

    it('getModuleInfo calls GET and returns module data', async () => {
      const info = { version: '1.0.0', worksheets: 13 }
      api.get.mockResolvedValue({ data: info })

      const result = await getModuleInfo()

      expect(api.get).toHaveBeenCalledWith('/capacity/info')
      expect(result).toEqual(info)
    })
  })

  // ============================================
  // Error Handling
  // ============================================

  describe('Error Handling', () => {
    it('loadWorkbook propagates API errors', async () => {
      const error = new Error('Request failed with status code 500')
      error.response = { status: 500, data: { detail: 'Internal server error' } }
      api.get.mockRejectedValue(error)

      await expect(loadWorkbook(5)).rejects.toThrow('Request failed with status code 500')
    })

    it('createOrder propagates 400 validation errors', async () => {
      const error = new Error('Request failed with status code 400')
      error.response = { status: 400, data: { detail: 'Validation failed' } }
      api.post.mockRejectedValue(error)

      await expect(createOrder(5, {})).rejects.toThrow(
        'Request failed with status code 400'
      )
    })

    it('updateProductionLine propagates 404 not found errors', async () => {
      const error = new Error('Request failed with status code 404')
      error.response = { status: 404, data: { detail: 'Not found' } }
      api.put.mockRejectedValue(error)

      await expect(updateProductionLine(5, 999, {})).rejects.toThrow(
        'Request failed with status code 404'
      )
    })

    it('deleteCalendarEntry propagates 403 forbidden errors', async () => {
      const error = new Error('Request failed with status code 403')
      error.response = { status: 403, data: { detail: 'Forbidden' } }
      api.delete.mockRejectedValue(error)

      await expect(deleteCalendarEntry(5, 1)).rejects.toThrow(
        'Request failed with status code 403'
      )
    })

    it('runCapacityAnalysis propagates network errors', async () => {
      const error = new Error('Network Error')
      error.code = 'ERR_NETWORK'
      api.post.mockRejectedValue(error)

      await expect(
        runCapacityAnalysis(5, '2026-03-01', '2026-03-31')
      ).rejects.toThrow('Network Error')
    })

    it('getModuleInfo propagates errors unlike isFeatureEnabled', async () => {
      api.get.mockRejectedValue(new Error('Service unavailable'))

      await expect(getModuleInfo()).rejects.toThrow('Service unavailable')
    })

    it('commitSchedule propagates errors', async () => {
      const error = new Error('Request failed with status code 409')
      error.response = { status: 409, data: { detail: 'Already committed' } }
      api.post.mockRejectedValue(error)

      await expect(
        commitSchedule(1, { otd_target: 95 })
      ).rejects.toThrow('Request failed with status code 409')
    })

    it('explodeBOM propagates errors', async () => {
      const error = new Error('Request failed with status code 422')
      error.response = { status: 422, data: { detail: 'Invalid item code' } }
      api.post.mockRejectedValue(error)

      await expect(explodeBOM(5, 'INVALID', 100)).rejects.toThrow(
        'Request failed with status code 422'
      )
    })
  })

  // ============================================
  // Edge Cases and Default Parameters
  // ============================================

  describe('Edge Cases and Default Parameters', () => {
    it('getOrders uses default skip=0 and limit=100', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getOrders(1)

      const call = api.get.mock.calls[0]
      expect(call[1].params.skip).toBe(0)
      expect(call[1].params.limit).toBe(100)
    })

    it('getProductionLines defaults include_inactive to false', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getProductionLines(1)

      const call = api.get.mock.calls[0]
      expect(call[1].params.include_inactive).toBe(false)
    })

    it('getBOMHeaders defaults active_only to true', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getBOMHeaders(1)

      const call = api.get.mock.calls[0]
      expect(call[1].params.active_only).toBe(true)
    })

    it('deleteProductionLine defaults hard_delete to false', async () => {
      api.delete.mockResolvedValue({ data: {} })

      await deleteProductionLine(1, 1)

      const call = api.delete.mock.calls[0]
      expect(call[1].params.hard_delete).toBe(false)
    })

    it('deleteBOMHeader defaults hard_delete to false', async () => {
      api.delete.mockResolvedValue({ data: {} })

      await deleteBOMHeader(1, 1)

      const call = api.delete.mock.calls[0]
      expect(call[1].params.hard_delete).toBe(false)
    })

    it('createScenario defaults base_schedule_id to null', async () => {
      api.post.mockResolvedValue({ data: {} })

      await createScenario(1, 'Test', 'OVERTIME', {})

      const call = api.post.mock.calls[0]
      expect(call[1].base_schedule_id).toBeNull()
    })

    it('generateSchedule defaults order_ids to null', async () => {
      api.post.mockResolvedValue({ data: {} })

      await generateSchedule(1, 'Sched', '2026-01-01', '2026-01-31')

      const call = api.post.mock.calls[0]
      expect(call[1].order_ids).toBeNull()
    })

    it('runComponentCheck defaults order_ids to null', async () => {
      api.post.mockResolvedValue({ data: {} })

      await runComponentCheck(1)

      const call = api.post.mock.calls[0]
      expect(call[1].order_ids).toBeNull()
    })

    it('runScenario sends empty payload when no period dates provided', async () => {
      api.post.mockResolvedValue({ data: {} })

      await runScenario(5, 1)

      const call = api.post.mock.calls[0]
      expect(call[1]).toEqual({})
    })

    it('runScenario includes only period_start when period_end is null', async () => {
      api.post.mockResolvedValue({ data: {} })

      await runScenario(5, 1, '2026-03-01', null)

      const call = api.post.mock.calls[0]
      expect(call[1]).toEqual({ period_start: '2026-03-01' })
    })

    it('loadWorkbook works with string client ID', async () => {
      api.get.mockResolvedValue({ data: {} })

      await loadWorkbook('CLIENT-A')

      expect(api.get).toHaveBeenCalledWith('/capacity/workbook/CLIENT-A')
    })

    it('getCalendarEntries with only startDate omits endDate', async () => {
      api.get.mockResolvedValue({ data: [] })

      await getCalendarEntries(5, '2026-01-01')

      expect(api.get).toHaveBeenCalledWith('/capacity/calendar', {
        params: { client_id: 5, start_date: '2026-01-01' },
      })
    })
  })
})
