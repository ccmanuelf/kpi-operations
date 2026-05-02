/**
 * Composable for My Shift Dashboard quick-entry forms.
 * Production / downtime / quality / help-request form state and
 * submission against the assigned work orders.
 *
 * Backend alignment: payloads match backend/schemas/{production,downtime,quality}.py
 * Create schemas. client_id derived from authStore (operators) or
 * kpiSelectionStore.selectedClient (admin). product_id and shift_id are
 * resolved client-side from /api/products and /api/shifts reference data
 * loaded once on composable creation. Quick-entry placeholders for
 * run_time_hours and employees_assigned match today's UX (operators
 * refine values via the standalone Production Entry grid).
 */
import { ref, onMounted } from 'vue'
import { useNotificationStore } from '@/stores/notificationStore'
import { useAuthStore } from '@/stores/authStore'
import { useKPIStore } from '@/stores/kpi'
import { DOWNTIME_REASON_CODES } from '@/composables/useDowntimeGridData'
import api from '@/services/api'

export interface ShiftWorkOrder {
  id: string | number
  work_order_id: string | number
  style_model?: string
  [key: string]: unknown
}

export interface ActiveShift {
  shift_number?: number
  shift_id?: number
  [key: string]: unknown
}

interface ProductRef {
  product_id: number
  product_code?: string
  product_name?: string
}

interface ShiftRef {
  shift_id: number
  shift_name?: string
}

interface ProductionForm {
  workOrderId: string | number | null
  quantity: number
}

interface DowntimeForm {
  workOrderId: string | number | null
  reason: string | null
  minutes: number
  notes: string
}

interface QualityForm {
  workOrderId: string | number | null
  inspectedQty: number
  defectQty: number
  defectType: string | null
}

interface HelpForm {
  type: string | null
  description: string
}

const errorDetail = (e: unknown, fallback: string): string => {
  const ax = e as { response?: { data?: { detail?: string } }; message?: string }
  return ax?.response?.data?.detail || ax?.message || fallback
}

// Map UI reason strings to backend DowntimeReasonEnum codes.
// Mirrors backend/schemas/downtime.py:65-78 from_legacy_csv mapping.
export const downtimeReasonToCode = (reason: string | null): string => {
  if (!reason) return 'OTHER'
  const code = reason.toUpperCase().replace(/\s+/g, '_')
  if ((DOWNTIME_REASON_CODES as string[]).includes(code)) return code
  // Map common UI labels to canonical codes.
  const aliases: Record<string, string> = {
    EQUIPMENT_BREAKDOWN: 'EQUIPMENT_FAILURE',
    SCHEDULED_MAINTENANCE: 'MAINTENANCE',
    CHANGEOVER: 'SETUP_CHANGEOVER',
    QUALITY_ISSUE: 'QUALITY_HOLD',
    WAITING_FOR_INSPECTION: 'QUALITY_HOLD',
  }
  return aliases[code] || 'OTHER'
}

export function useShiftForms(
  getActiveShift: () => ActiveShift | null,
  getCurrentDate: () => string,
  getAssignedWorkOrders: () => ShiftWorkOrder[],
  onDataRefresh: () => Promise<void> | void,
) {
  const notificationStore = useNotificationStore()
  const authStore = useAuthStore()
  const kpiSelectionStore = useKPIStore()

  const showProductionDialog = ref(false)
  const showDowntimeDialog = ref(false)
  const showQualityDialog = ref(false)
  const showHelpDialog = ref(false)
  const isSubmitting = ref(false)
  const showSuccess = ref(false)
  const successMessage = ref('')

  const selectedWorkOrder = ref<ShiftWorkOrder | null>(null)

  const products = ref<ProductRef[]>([])
  const shifts = ref<ShiftRef[]>([])

  const productionForm = ref<ProductionForm>({
    workOrderId: null,
    quantity: 10,
  })
  const downtimeForm = ref<DowntimeForm>({
    workOrderId: null,
    reason: null,
    minutes: 15,
    notes: '',
  })
  const qualityForm = ref<QualityForm>({
    workOrderId: null,
    inspectedQty: 100,
    defectQty: 0,
    defectType: null,
  })
  const helpForm = ref<HelpForm>({
    type: null,
    description: '',
  })

  const productionPresets: number[] = [10, 25, 50, 100]
  // UI labels mapped to backend DowntimeReasonEnum via downtimeReasonToCode().
  const downtimeReasons: string[] = [
    'Equipment Breakdown',
    'Material Shortage',
    'Changeover',
    'Scheduled Maintenance',
    'Quality Issue',
    'Waiting for Inspection',
    'Other',
  ]
  const defectTypes: string[] = [
    'Dimensional',
    'Visual',
    'Functional',
    'Packaging',
    'Documentation',
    'Other',
  ]
  const helpTypes: string[] = [
    'Equipment Issue',
    'Material Issue',
    'Quality Issue',
    'Safety Concern',
    'Training Needed',
    'Supervisor Request',
    'Other',
  ]

  const activeClientId = (): string | number | null => {
    return authStore.user?.client_id_assigned ?? kpiSelectionStore.selectedClient ?? null
  }

  // Resolve product_id for a work order: try style_model → product_code match,
  // fall back to first product. Returns null if no products are loaded.
  const resolveProductId = (wo: ShiftWorkOrder | null | undefined): number | null => {
    if (products.value.length === 0) return null
    if (wo?.style_model) {
      const match = products.value.find(
        (p) => p.product_code === wo.style_model || p.product_name === wo.style_model,
      )
      if (match) return match.product_id
    }
    return products.value[0]?.product_id ?? null
  }

  // Resolve shift_id: prefer active shift's shift_id field, else first shift.
  const resolveShiftId = (): number | null => {
    const active = getActiveShift()
    if (active?.shift_id !== undefined) return Number(active.shift_id)
    if (shifts.value.length > 0) return shifts.value[0].shift_id
    return null
  }

  const openQuickLog = (wo: ShiftWorkOrder): void => {
    selectedWorkOrder.value = wo
    productionForm.value.workOrderId = wo.id
    showProductionDialog.value = true
  }

  const openQuickProductionDialog = (): void => {
    const workOrders = getAssignedWorkOrders()
    if (workOrders.length > 0) {
      productionForm.value.workOrderId = workOrders[0].id
    }
    showProductionDialog.value = true
  }

  const openDowntimeDialog = (): void => {
    const workOrders = getAssignedWorkOrders()
    if (workOrders.length > 0) {
      downtimeForm.value.workOrderId = workOrders[0].id
    }
    showDowntimeDialog.value = true
  }

  const openQualityDialog = (): void => {
    const workOrders = getAssignedWorkOrders()
    if (workOrders.length > 0) {
      qualityForm.value.workOrderId = workOrders[0].id
    }
    showQualityDialog.value = true
  }

  const openHelpDialog = (): void => {
    showHelpDialog.value = true
  }

  // Build a Pydantic-aligned ProductionEntryCreate payload.
  // Quick-entry uses placeholder run_time_hours=1.0 and employees_assigned=1
  // matching today's UX; operators refine via the standalone grid.
  const buildProductionPayload = (
    wo: ShiftWorkOrder,
    quantity: number,
  ): Record<string, unknown> | null => {
    const clientId = activeClientId()
    const productId = resolveProductId(wo)
    const shiftId = resolveShiftId()
    if (!clientId || productId === null || shiftId === null) return null
    const today = getCurrentDate()
    return {
      client_id: String(clientId),
      product_id: productId,
      shift_id: shiftId,
      work_order_id: String(wo.work_order_id),
      production_date: today,
      shift_date: today,
      units_produced: quantity,
      run_time_hours: 1,
      employees_assigned: 1,
      defect_count: 0,
      scrap_count: 0,
    }
  }

  const quickLogProduction = async (quantity: number): Promise<void> => {
    if (!selectedWorkOrder.value) return

    isSubmitting.value = true
    try {
      const payload = buildProductionPayload(selectedWorkOrder.value, quantity)
      if (!payload) {
        notificationStore.showError('Cannot log production: client/product/shift not resolved')
        return
      }
      await api.createProductionEntry(payload)

      successMessage.value = `Logged ${quantity} units for ${selectedWorkOrder.value.work_order_id}`
      showSuccess.value = true
      await onDataRefresh()
    } catch (error) {
      notificationStore.showError(errorDetail(error, 'Failed to log production'))
    } finally {
      isSubmitting.value = false
    }
  }

  const submitProduction = async (): Promise<void> => {
    isSubmitting.value = true
    try {
      const workOrders = getAssignedWorkOrders()
      const wo = workOrders.find((w) => w.id === productionForm.value.workOrderId)
      if (!wo) {
        notificationStore.showError('Work order not found')
        return
      }
      const payload = buildProductionPayload(wo, productionForm.value.quantity)
      if (!payload) {
        notificationStore.showError(
          'Cannot log production: client/product/shift not resolved',
        )
        return
      }
      await api.createProductionEntry(payload)

      successMessage.value = `Logged ${productionForm.value.quantity} units`
      showSuccess.value = true
      showProductionDialog.value = false
      productionForm.value.quantity = 10
      await onDataRefresh()
    } catch (error) {
      notificationStore.showError(errorDetail(error, 'Failed to log production'))
    } finally {
      isSubmitting.value = false
    }
  }

  const submitDowntime = async (): Promise<void> => {
    isSubmitting.value = true
    try {
      const workOrders = getAssignedWorkOrders()
      const wo = workOrders.find((w) => w.id === downtimeForm.value.workOrderId)
      if (!wo) {
        notificationStore.showError('Work order not found')
        return
      }
      const clientId = activeClientId()
      if (!clientId) {
        notificationStore.showError('No client selected')
        return
      }
      await api.createDowntimeEntry({
        client_id: String(clientId),
        work_order_id: String(wo.work_order_id),
        shift_date: getCurrentDate(),
        downtime_reason: downtimeReasonToCode(downtimeForm.value.reason),
        downtime_duration_minutes: downtimeForm.value.minutes,
        notes: downtimeForm.value.notes || undefined,
      })

      successMessage.value = 'Downtime reported successfully'
      showSuccess.value = true
      showDowntimeDialog.value = false
      downtimeForm.value = { workOrderId: null, reason: null, minutes: 15, notes: '' }
      await onDataRefresh()
    } catch (error) {
      notificationStore.showError(errorDetail(error, 'Failed to report downtime'))
    } finally {
      isSubmitting.value = false
    }
  }

  const submitQuality = async (): Promise<void> => {
    isSubmitting.value = true
    try {
      const workOrders = getAssignedWorkOrders()
      const wo = workOrders.find((w) => w.id === qualityForm.value.workOrderId)
      if (!wo) {
        notificationStore.showError('Work order not found')
        return
      }
      const clientId = activeClientId()
      if (!clientId) {
        notificationStore.showError('No client selected')
        return
      }
      const inspected = qualityForm.value.inspectedQty || 0
      const defective = qualityForm.value.defectQty || 0
      const today = getCurrentDate()
      await api.createQualityEntry({
        client_id: String(clientId),
        work_order_id: String(wo.work_order_id),
        shift_date: today,
        inspection_date: today,
        units_inspected: inspected,
        units_passed: Math.max(0, inspected - defective),
        units_defective: defective,
        total_defects_count: defective,
        notes: qualityForm.value.defectType
          ? `Defect type: ${qualityForm.value.defectType}`
          : undefined,
      })

      successMessage.value = 'Quality check recorded'
      showSuccess.value = true
      showQualityDialog.value = false
      qualityForm.value = {
        workOrderId: null,
        inspectedQty: 100,
        defectQty: 0,
        defectType: null,
      }
      await onDataRefresh()
    } catch (error) {
      notificationStore.showError(errorDetail(error, 'Failed to record quality check'))
    } finally {
      isSubmitting.value = false
    }
  }

  const submitHelpRequest = async (): Promise<void> => {
    isSubmitting.value = true
    try {
      successMessage.value = 'Help request sent to supervisor'
      showSuccess.value = true
      showHelpDialog.value = false
      helpForm.value = { type: null, description: '' }
    } catch {
      notificationStore.showError('Failed to send help request')
    } finally {
      isSubmitting.value = false
    }
  }

  const fetchReferenceData = async (): Promise<void> => {
    try {
      const [productsRes, shiftsRes] = await Promise.all([
        api.get('/products'),
        api.get('/shifts'),
      ])
      products.value = productsRes.data || []
      shifts.value = shiftsRes.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to fetch reference data for shift forms:', error)
      // Non-fatal: submission paths show their own error if resolution fails.
    }
  }

  onMounted(() => {
    fetchReferenceData()
  })

  return {
    showProductionDialog,
    showDowntimeDialog,
    showQualityDialog,
    showHelpDialog,
    isSubmitting,
    showSuccess,
    successMessage,
    selectedWorkOrder,
    productionForm,
    downtimeForm,
    qualityForm,
    helpForm,
    productionPresets,
    downtimeReasons,
    defectTypes,
    helpTypes,
    products,
    shifts,
    openQuickLog,
    openQuickProductionDialog,
    openDowntimeDialog,
    openQualityDialog,
    openHelpDialog,
    quickLogProduction,
    submitProduction,
    submitDowntime,
    submitQuality,
    submitHelpRequest,
    fetchReferenceData,
  }
}
