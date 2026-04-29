/**
 * Composable for My Shift Dashboard quick-entry forms.
 * Production / downtime / quality / help-request form state and
 * submission against the assigned work orders.
 */
import { ref } from 'vue'
import { useNotificationStore } from '@/stores/notificationStore'
import api from '@/services/api'

export interface ShiftWorkOrder {
  id: string | number
  work_order_id: string | number
  [key: string]: unknown
}

export interface ActiveShift {
  shift_number?: number
  [key: string]: unknown
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

export function useShiftForms(
  getActiveShift: () => ActiveShift | null,
  getCurrentDate: () => string,
  getAssignedWorkOrders: () => ShiftWorkOrder[],
  onDataRefresh: () => Promise<void> | void,
) {
  const notificationStore = useNotificationStore()

  const showProductionDialog = ref(false)
  const showDowntimeDialog = ref(false)
  const showQualityDialog = ref(false)
  const showHelpDialog = ref(false)
  const isSubmitting = ref(false)
  const showSuccess = ref(false)
  const successMessage = ref('')

  const selectedWorkOrder = ref<ShiftWorkOrder | null>(null)

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

  const quickLogProduction = async (quantity: number): Promise<void> => {
    if (!selectedWorkOrder.value) return

    isSubmitting.value = true
    try {
      await api.createProductionEntry({
        work_order_id: selectedWorkOrder.value.work_order_id,
        date: getCurrentDate(),
        shift: getActiveShift()?.shift_number || 1,
        units_produced: quantity,
        runtime_hours: 1,
      })

      successMessage.value = `Logged ${quantity} units for ${selectedWorkOrder.value.work_order_id}`
      showSuccess.value = true
      await onDataRefresh()
    } catch (error) {
      // The JS code called `notificationStore.error(...)` but that
      // method doesn't exist on the store — it's `showError`. Fixed
      // the call site here; the JS path was failing silently with
      // a TypeError.
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
      await api.createProductionEntry({
        work_order_id: wo.work_order_id,
        date: getCurrentDate(),
        shift: getActiveShift()?.shift_number || 1,
        units_produced: productionForm.value.quantity,
        runtime_hours: 1,
      })

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
      await api.createDowntimeEntry({
        work_order_id: wo.work_order_id,
        date: getCurrentDate(),
        shift: getActiveShift()?.shift_number || 1,
        downtime_minutes: downtimeForm.value.minutes,
        reason: downtimeForm.value.reason,
        notes: downtimeForm.value.notes,
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
      await api.createQualityEntry({
        work_order_id: wo.work_order_id,
        date: getCurrentDate(),
        shift: getActiveShift()?.shift_number || 1,
        inspected_quantity: qualityForm.value.inspectedQty,
        defect_quantity: qualityForm.value.defectQty,
        defect_type: qualityForm.value.defectType,
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
  }
}
