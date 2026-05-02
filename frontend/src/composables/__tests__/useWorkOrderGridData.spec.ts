/**
 * Unit tests for useWorkOrderGridData composable —
 * Group H Surface #19 (WorkOrderManagement).
 *
 * Same Excel-style inline-edit pattern as the Group E admin catalogs.
 * Verifies column shape against backend WorkOrderCreate, status/priority
 * canonical enums, client_id resolution from auth store, autosave PUT
 * for existing rows, explicit Save POST for new rows, progress
 * calculation, and overdue date detection.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'

const { mockApi, authState, kpiState } = vi.hoisted(() => ({
  mockApi: {
    post: vi.fn(),
    put: vi.fn(),
  },
  authState: { client_id_assigned: 'CLIENT1' as string | null },
  kpiState: { selectedClient: null as string | null },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({
    user: authState.client_id_assigned
      ? { client_id_assigned: authState.client_id_assigned }
      : null,
  }),
}))

vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => ({ selectedClient: kpiState.selectedClient }),
}))

import useWorkOrderGridData, {
  WORK_ORDER_STATUS_OPTIONS,
  WORK_ORDER_PRIORITY_OPTIONS,
  calculateProgress,
  isOverdue,
  type WorkOrderRow,
} from '../useWorkOrderGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean | ((params: { data: WorkOrderRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { values?: unknown[]; min?: number; precision?: number }
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

const buildHarness = () => {
  const workOrders = ref<WorkOrderRow[]>([])
  const loadWorkOrders = vi.fn().mockResolvedValue(undefined)
  const notify = { showSuccess: vi.fn(), showError: vi.fn() }
  const onConfirmDelete = vi.fn()
  const onOpenDetail = vi.fn()

  const grid = useWorkOrderGridData({
    workOrders,
    loadWorkOrders,
    notify,
    onConfirmDelete,
    onOpenDetail,
  })

  return { ...grid, workOrders, loadWorkOrders, notify, onConfirmDelete, onOpenDetail }
}

describe('catalogs', () => {
  it('WORK_ORDER_STATUS_OPTIONS mirrors backend WorkOrderStatusEnum', () => {
    expect(WORK_ORDER_STATUS_OPTIONS).toContain('RECEIVED')
    expect(WORK_ORDER_STATUS_OPTIONS).toContain('IN_PROGRESS')
    expect(WORK_ORDER_STATUS_OPTIONS).toContain('ON_HOLD')
    expect(WORK_ORDER_STATUS_OPTIONS).toContain('COMPLETED')
    expect(WORK_ORDER_STATUS_OPTIONS).toContain('CANCELLED')
  })

  it('WORK_ORDER_PRIORITY_OPTIONS mirrors backend URGENT|HIGH|NORMAL|MEDIUM|LOW', () => {
    expect(WORK_ORDER_PRIORITY_OPTIONS).toEqual([
      'URGENT',
      'HIGH',
      'NORMAL',
      'MEDIUM',
      'LOW',
    ])
  })
})

describe('calculateProgress', () => {
  it('returns 0 when planned_quantity is 0', () => {
    expect(calculateProgress({ planned_quantity: 0, actual_quantity: 5 })).toBe(0)
  })

  it('returns 0 when planned_quantity is missing', () => {
    expect(calculateProgress({ actual_quantity: 5 })).toBe(0)
  })

  it('returns 100 when actual = planned', () => {
    expect(calculateProgress({ planned_quantity: 100, actual_quantity: 100 })).toBe(100)
  })

  it('caps at 100 when actual > planned', () => {
    expect(calculateProgress({ planned_quantity: 100, actual_quantity: 150 })).toBe(100)
  })

  it('rounds to nearest integer percent', () => {
    expect(calculateProgress({ planned_quantity: 3, actual_quantity: 1 })).toBe(33)
  })
})

describe('isOverdue', () => {
  it('returns false for missing date', () => {
    expect(isOverdue(undefined)).toBe(false)
    expect(isOverdue(null)).toBe(false)
    expect(isOverdue('')).toBe(false)
  })

  it('returns true for past dates', () => {
    expect(isOverdue('2020-01-01')).toBe(true)
  })

  it('returns false for future dates', () => {
    const future = new Date()
    future.setFullYear(future.getFullYear() + 1)
    expect(isOverdue(future.toISOString())).toBe(false)
  })
})

describe('useWorkOrderGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    authState.client_id_assigned = 'CLIENT1'
    kpiState.selectedClient = null
    mockApi.post.mockResolvedValue({ data: {} })
    mockApi.put.mockResolvedValue({ data: {} })
  })

  describe('column definitions', () => {
    it('work_order_id editable only on new rows', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'work_order_id')!
      const editable = col.editable as (p: { data: WorkOrderRow }) => boolean
      expect(editable({ data: { _isNew: true } })).toBe(true)
      expect(editable({ data: { _isNew: false, work_order_id: 'WO-1' } })).toBe(false)
      expect(col.pinned).toBe('left')
    })

    it('style_model uses text editor', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'style_model')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('planned_quantity uses numeric editor (min:1)', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'planned_quantity')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 1, precision: 0 })
    })

    it('actual_quantity uses numeric editor (min:0)', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'actual_quantity')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, precision: 0 })
    })

    it('status uses select editor over WORK_ORDER_STATUS_OPTIONS', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'status')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual(WORK_ORDER_STATUS_OPTIONS)
    })

    it('priority uses select editor over WORK_ORDER_PRIORITY_OPTIONS', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'priority')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual(WORK_ORDER_PRIORITY_OPTIONS)
    })

    it('planned_start_date / planned_ship_date use date editors', () => {
      const { columnDefs } = buildHarness()
      expect(findCol(columnDefs.value, 'planned_start_date')!.cellEditor).toBe(
        'agDateStringCellEditor',
      )
      expect(findCol(columnDefs.value, 'planned_ship_date')!.cellEditor).toBe(
        'agDateStringCellEditor',
      )
    })

    it('notes uses large-text editor', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'notes')!
      expect(col.cellEditor).toBe('agLargeTextCellEditor')
    })

    it('_progress is read-only with valueGetter', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, '_progress')!
      expect(col.editable).toBe(false)
    })

    it('_actions column pinned right', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, '_actions')!
      expect(col.pinned).toBe('right')
    })
  })

  describe('addRow', () => {
    it('refuses to add a row when no client is resolved', () => {
      authState.client_id_assigned = null
      const { addRow, workOrders, notify } = buildHarness()
      addRow()
      expect(workOrders.value).toHaveLength(0)
      expect(notify.showError).toHaveBeenCalled()
    })

    it('prepends a row marked _isNew with sensible defaults', () => {
      const { addRow, workOrders } = buildHarness()
      addRow()
      expect(workOrders.value).toHaveLength(1)
      const row = workOrders.value[0]
      expect(row._isNew).toBe(true)
      expect(row.client_id).toBe('CLIENT1')
      expect(row.status).toBe('RECEIVED')
      expect(row.actual_quantity).toBe(0)
    })
  })

  describe('saveNewRow', () => {
    it('POSTs payload when required fields present', async () => {
      const { saveNewRow } = buildHarness()
      await saveNewRow({
        _isNew: true,
        work_order_id: 'WO-1',
        style_model: 'STYLE-A',
        planned_quantity: 100,
      } as WorkOrderRow)
      expect(mockApi.post).toHaveBeenCalledWith(
        '/work-orders',
        expect.objectContaining({
          work_order_id: 'WO-1',
          style_model: 'STYLE-A',
          planned_quantity: 100,
          client_id: 'CLIENT1',
          status: 'RECEIVED',
        }),
      )
    })

    it('refuses to POST when work_order_id missing', async () => {
      const { saveNewRow } = buildHarness()
      await saveNewRow({
        _isNew: true,
        style_model: 'STYLE-A',
        planned_quantity: 100,
      } as WorkOrderRow)
      expect(mockApi.post).not.toHaveBeenCalled()
    })

    it('refuses to POST when planned_quantity is 0 or negative', async () => {
      const { saveNewRow } = buildHarness()
      await saveNewRow({
        _isNew: true,
        work_order_id: 'WO-1',
        style_model: 'STYLE-A',
        planned_quantity: 0,
      } as WorkOrderRow)
      expect(mockApi.post).not.toHaveBeenCalled()
    })

    it('reloads on success', async () => {
      const { saveNewRow, loadWorkOrders } = buildHarness()
      await saveNewRow({
        _isNew: true,
        work_order_id: 'WO-1',
        style_model: 'X',
        planned_quantity: 1,
      } as WorkOrderRow)
      expect(loadWorkOrders).toHaveBeenCalled()
    })
  })

  describe('removeNewRow', () => {
    it('removes the matching row from workOrders', () => {
      const { removeNewRow, workOrders } = buildHarness()
      workOrders.value = [
        { _isNew: true, work_order_id: 'NEW' },
        { work_order_id: 'WO-2' },
      ]
      removeNewRow(workOrders.value[0])
      expect(workOrders.value).toHaveLength(1)
      expect(workOrders.value[0]).toMatchObject({ work_order_id: 'WO-2' })
    })
  })

  describe('onCellValueChanged', () => {
    it('PUTs the row when an existing row changes', async () => {
      const { onCellValueChanged } = buildHarness()
      await onCellValueChanged({
        data: {
          work_order_id: 'WO-1',
          style_model: 'NEW',
          planned_quantity: 50,
          actual_quantity: 10,
          status: 'IN_PROGRESS',
        } as WorkOrderRow,
        column: { colId: 'style_model' },
      })
      expect(mockApi.put).toHaveBeenCalledWith(
        '/work-orders/WO-1',
        expect.objectContaining({ style_model: 'NEW' }),
      )
    })

    it('does NOT PUT for new rows', async () => {
      const { onCellValueChanged } = buildHarness()
      await onCellValueChanged({
        data: { _isNew: true, work_order_id: 'WO-X' } as WorkOrderRow,
        column: { colId: 'style_model' },
      })
      expect(mockApi.put).not.toHaveBeenCalled()
    })

    it('reloads on PUT failure to roll back', async () => {
      mockApi.put.mockRejectedValue(new Error('boom'))
      const { onCellValueChanged, loadWorkOrders } = buildHarness()
      await onCellValueChanged({
        data: { work_order_id: 'WO-1' } as WorkOrderRow,
        column: { colId: 'style_model' },
      })
      expect(loadWorkOrders).toHaveBeenCalled()
    })
  })
})
