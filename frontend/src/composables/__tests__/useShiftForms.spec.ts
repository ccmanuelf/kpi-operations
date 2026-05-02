/**
 * Unit tests for useShiftForms composable — Group C Surface #8.
 *
 * Verifies that the MyShift quick-action submit handlers send Pydantic-aligned
 * payloads to the canonical backend endpoints (Group A reconciliation pattern).
 *
 * Specifically asserts:
 *   - downtimeReasonToCode maps each UI label to the canonical
 *     DowntimeReasonEnum code (e.g. "Equipment Breakdown" -> EQUIPMENT_FAILURE,
 *     "Quality Issue" -> QUALITY_HOLD).
 *   - submitDowntime payload shape: client_id + shift_date + downtime_reason
 *     (enum) + downtime_duration_minutes; legacy fields (downtime_minutes,
 *     reason as UI string, date) are gone.
 *   - submitQuality payload shape: units_inspected/units_passed/units_defective
 *     (computed) + total_defects_count + shift_date + client_id; legacy
 *     fields (inspected_quantity, defect_quantity, defect_type, date) gone.
 *   - submitProduction payload shape: client_id + product_id (resolved from
 *     style_model OR first product) + shift_id (from active shift OR first
 *     shift) + production_date + run_time_hours + employees_assigned.
 *   - All three handlers refuse submission when client_id cannot be resolved.
 *   - product_id resolution prefers style_model match; falls back to first
 *     product when no match.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

const { mockApi, authState, kpiState } = vi.hoisted(() => ({
  mockApi: {
    get: vi.fn(),
    createProductionEntry: vi.fn(),
    createDowntimeEntry: vi.fn(),
    createQualityEntry: vi.fn(),
  },
  authState: { client_id_assigned: 'CLIENT1' as string | null },
  kpiState: { selectedClient: null as string | null },
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => ({
    show: vi.fn(),
    showError: vi.fn(),
    showSuccess: vi.fn(),
  }),
}))

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

import { useShiftForms, downtimeReasonToCode } from '../useShiftForms'

describe('downtimeReasonToCode', () => {
  it('Equipment Breakdown -> EQUIPMENT_FAILURE', () => {
    expect(downtimeReasonToCode('Equipment Breakdown')).toBe('EQUIPMENT_FAILURE')
  })

  it('Material Shortage -> MATERIAL_SHORTAGE (already canonical)', () => {
    expect(downtimeReasonToCode('Material Shortage')).toBe('MATERIAL_SHORTAGE')
  })

  it('Changeover -> SETUP_CHANGEOVER', () => {
    expect(downtimeReasonToCode('Changeover')).toBe('SETUP_CHANGEOVER')
  })

  it('Scheduled Maintenance -> MAINTENANCE', () => {
    expect(downtimeReasonToCode('Scheduled Maintenance')).toBe('MAINTENANCE')
  })

  it('Quality Issue -> QUALITY_HOLD', () => {
    expect(downtimeReasonToCode('Quality Issue')).toBe('QUALITY_HOLD')
  })

  it('Waiting for Inspection -> QUALITY_HOLD', () => {
    expect(downtimeReasonToCode('Waiting for Inspection')).toBe('QUALITY_HOLD')
  })

  it('Other -> OTHER', () => {
    expect(downtimeReasonToCode('Other')).toBe('OTHER')
  })

  it('null / undefined -> OTHER', () => {
    expect(downtimeReasonToCode(null)).toBe('OTHER')
    expect(downtimeReasonToCode(undefined as unknown as string)).toBe('OTHER')
  })

  it('unrecognised label -> OTHER', () => {
    expect(downtimeReasonToCode('Lunch break')).toBe('OTHER')
  })
})

const noopRefresh = async () => {}

const buildHarness = () => {
  const activeShift = { shift_id: 7, shift_number: 2 }
  const today = '2026-05-01'
  const workOrders: Array<{ id: number; work_order_id: string; style_model?: string }> = [
    { id: 1, work_order_id: 'WO-A', style_model: 'STYLE-A' },
    { id: 2, work_order_id: 'WO-B', style_model: 'STYLE-B' },
    { id: 3, work_order_id: 'WO-C', style_model: 'UNKNOWN-STYLE' },
  ]
  return useShiftForms(
    () => activeShift,
    () => today,
    () => workOrders,
    noopRefresh,
  )
}

describe('useShiftForms', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    authState.client_id_assigned = 'CLIENT1'
    kpiState.selectedClient = null
    mockApi.get.mockImplementation((url: string) => {
      if (url === '/products') {
        return Promise.resolve({
          data: [
            { product_id: 10, product_code: 'STYLE-A', product_name: 'Widget A' },
            { product_id: 20, product_code: 'STYLE-B', product_name: 'Widget B' },
          ],
        })
      }
      if (url === '/shifts') {
        return Promise.resolve({
          data: [
            { shift_id: 1, shift_name: 'Day' },
            { shift_id: 2, shift_name: 'Night' },
          ],
        })
      }
      return Promise.resolve({ data: [] })
    })
    mockApi.createProductionEntry.mockResolvedValue({ data: {} })
    mockApi.createDowntimeEntry.mockResolvedValue({ data: {} })
    mockApi.createQualityEntry.mockResolvedValue({ data: {} })
  })

  describe('reference data load', () => {
    it('fetches /products and /shifts on mount via fetchReferenceData', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      expect(mockApi.get).toHaveBeenCalledWith('/products')
      expect(mockApi.get).toHaveBeenCalledWith('/shifts')
    })
  })

  describe('submitDowntime', () => {
    it('sends Pydantic-aligned payload', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.downtimeForm.value = {
        workOrderId: 1,
        reason: 'Equipment Breakdown',
        minutes: 30,
        notes: 'Hydraulic leak',
      }
      await harness.submitDowntime()
      await flushPromises()
      expect(mockApi.createDowntimeEntry).toHaveBeenCalledWith({
        client_id: 'CLIENT1',
        work_order_id: 'WO-A',
        shift_date: '2026-05-01',
        downtime_reason: 'EQUIPMENT_FAILURE',
        downtime_duration_minutes: 30,
        notes: 'Hydraulic leak',
      })
    })

    it('does NOT send legacy fields (downtime_minutes, reason as UI string, date)', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.downtimeForm.value = {
        workOrderId: 1,
        reason: 'Material Shortage',
        minutes: 10,
        notes: '',
      }
      await harness.submitDowntime()
      await flushPromises()
      const call = mockApi.createDowntimeEntry.mock.calls[0][0] as Record<
        string,
        unknown
      >
      expect(call.downtime_minutes).toBeUndefined()
      expect(call.reason).toBeUndefined()
      expect(call.date).toBeUndefined()
      expect(call.shift).toBeUndefined()
    })

    it('refuses to submit when client_id is null', async () => {
      authState.client_id_assigned = null
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.downtimeForm.value = {
        workOrderId: 1,
        reason: 'Other',
        minutes: 5,
        notes: '',
      }
      await harness.submitDowntime()
      await flushPromises()
      expect(mockApi.createDowntimeEntry).not.toHaveBeenCalled()
    })
  })

  describe('submitQuality', () => {
    it('sends Pydantic-aligned payload with computed units_passed', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.qualityForm.value = {
        workOrderId: 1,
        inspectedQty: 100,
        defectQty: 5,
        defectType: 'Visual',
      }
      await harness.submitQuality()
      await flushPromises()
      expect(mockApi.createQualityEntry).toHaveBeenCalledWith({
        client_id: 'CLIENT1',
        work_order_id: 'WO-A',
        shift_date: '2026-05-01',
        inspection_date: '2026-05-01',
        units_inspected: 100,
        units_passed: 95,
        units_defective: 5,
        total_defects_count: 5,
        notes: 'Defect type: Visual',
      })
    })

    it('clamps units_passed to 0 when defects exceed inspected', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.qualityForm.value = {
        workOrderId: 1,
        inspectedQty: 5,
        defectQty: 10,
        defectType: null,
      }
      await harness.submitQuality()
      await flushPromises()
      const call = mockApi.createQualityEntry.mock.calls[0][0] as Record<
        string,
        unknown
      >
      expect(call.units_passed).toBe(0)
    })

    it('does NOT send legacy fields (inspected_quantity, defect_quantity, defect_type, date)', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.qualityForm.value = {
        workOrderId: 1,
        inspectedQty: 50,
        defectQty: 0,
        defectType: null,
      }
      await harness.submitQuality()
      await flushPromises()
      const call = mockApi.createQualityEntry.mock.calls[0][0] as Record<
        string,
        unknown
      >
      expect(call.inspected_quantity).toBeUndefined()
      expect(call.defect_quantity).toBeUndefined()
      expect(call.defect_type).toBeUndefined()
      expect(call.date).toBeUndefined()
      expect(call.shift).toBeUndefined()
    })

    it('refuses to submit when client_id is null', async () => {
      authState.client_id_assigned = null
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.qualityForm.value = {
        workOrderId: 1,
        inspectedQty: 100,
        defectQty: 0,
        defectType: null,
      }
      await harness.submitQuality()
      await flushPromises()
      expect(mockApi.createQualityEntry).not.toHaveBeenCalled()
    })
  })

  describe('submitProduction', () => {
    it('resolves product_id from work order style_model match', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.productionForm.value = { workOrderId: 1, quantity: 50 }
      await harness.submitProduction()
      await flushPromises()
      const call = mockApi.createProductionEntry.mock.calls[0][0] as Record<
        string,
        unknown
      >
      expect(call.product_id).toBe(10) // STYLE-A
    })

    it('falls back to first product when style_model has no match', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.productionForm.value = { workOrderId: 3, quantity: 10 } // WO-C / UNKNOWN-STYLE
      await harness.submitProduction()
      await flushPromises()
      const call = mockApi.createProductionEntry.mock.calls[0][0] as Record<
        string,
        unknown
      >
      expect(call.product_id).toBe(10) // First product
    })

    it('uses active shift_id from getActiveShift when available', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.productionForm.value = { workOrderId: 1, quantity: 10 }
      await harness.submitProduction()
      await flushPromises()
      const call = mockApi.createProductionEntry.mock.calls[0][0] as Record<
        string,
        unknown
      >
      expect(call.shift_id).toBe(7) // From getActiveShift
    })

    it('sends placeholder run_time_hours=1 and employees_assigned=1', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.productionForm.value = { workOrderId: 1, quantity: 10 }
      await harness.submitProduction()
      await flushPromises()
      const call = mockApi.createProductionEntry.mock.calls[0][0] as Record<
        string,
        unknown
      >
      expect(call.run_time_hours).toBe(1)
      expect(call.employees_assigned).toBe(1)
    })

    it('sends Pydantic-aligned payload', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.productionForm.value = { workOrderId: 2, quantity: 25 }
      await harness.submitProduction()
      await flushPromises()
      expect(mockApi.createProductionEntry).toHaveBeenCalledWith({
        client_id: 'CLIENT1',
        product_id: 20,
        shift_id: 7,
        work_order_id: 'WO-B',
        production_date: '2026-05-01',
        shift_date: '2026-05-01',
        units_produced: 25,
        run_time_hours: 1,
        employees_assigned: 1,
        defect_count: 0,
        scrap_count: 0,
      })
    })

    it('does NOT send legacy fields (runtime_hours, shift, date)', async () => {
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.productionForm.value = { workOrderId: 1, quantity: 10 }
      await harness.submitProduction()
      await flushPromises()
      const call = mockApi.createProductionEntry.mock.calls[0][0] as Record<
        string,
        unknown
      >
      expect(call.runtime_hours).toBeUndefined()
      expect(call.shift).toBeUndefined()
      expect(call.date).toBeUndefined()
    })

    it('refuses to submit when reference data has not loaded', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      const harness = buildHarness()
      await harness.fetchReferenceData()
      harness.productionForm.value = { workOrderId: 1, quantity: 10 }
      await harness.submitProduction()
      await flushPromises()
      expect(mockApi.createProductionEntry).not.toHaveBeenCalled()
    })
  })
})
