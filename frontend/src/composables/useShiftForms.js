/**
 * Composable for My Shift Dashboard quick-entry forms.
 * Handles: production, downtime, quality, and help request form state and submission.
 */
import { ref } from 'vue'
import { useNotificationStore } from '@/stores/notificationStore'
import api from '@/services/api'

export function useShiftForms(getActiveShift, getCurrentDate, getAssignedWorkOrders, onDataRefresh) {
  const notificationStore = useNotificationStore()

  // Dialog states
  const showProductionDialog = ref(false)
  const showDowntimeDialog = ref(false)
  const showQualityDialog = ref(false)
  const showHelpDialog = ref(false)
  const isSubmitting = ref(false)
  const showSuccess = ref(false)
  const successMessage = ref('')

  // Selected work order for quick log
  const selectedWorkOrder = ref(null)

  // Form objects
  const productionForm = ref({
    workOrderId: null,
    quantity: 10
  })
  const downtimeForm = ref({
    workOrderId: null,
    reason: null,
    minutes: 15,
    notes: ''
  })
  const qualityForm = ref({
    workOrderId: null,
    inspectedQty: 100,
    defectQty: 0,
    defectType: null
  })
  const helpForm = ref({
    type: null,
    description: ''
  })

  // Constants
  const productionPresets = [10, 25, 50, 100]
  const downtimeReasons = [
    'Equipment Breakdown',
    'Material Shortage',
    'Changeover',
    'Scheduled Maintenance',
    'Quality Issue',
    'Waiting for Inspection',
    'Other'
  ]
  const defectTypes = [
    'Dimensional',
    'Visual',
    'Functional',
    'Packaging',
    'Documentation',
    'Other'
  ]
  const helpTypes = [
    'Equipment Issue',
    'Material Issue',
    'Quality Issue',
    'Safety Concern',
    'Training Needed',
    'Supervisor Request',
    'Other'
  ]

  // Dialog openers
  const openQuickLog = (wo) => {
    selectedWorkOrder.value = wo
    productionForm.value.workOrderId = wo.id
    showProductionDialog.value = true
  }

  const openQuickProductionDialog = () => {
    const workOrders = getAssignedWorkOrders()
    if (workOrders.length > 0) {
      productionForm.value.workOrderId = workOrders[0].id
    }
    showProductionDialog.value = true
  }

  const openDowntimeDialog = () => {
    const workOrders = getAssignedWorkOrders()
    if (workOrders.length > 0) {
      downtimeForm.value.workOrderId = workOrders[0].id
    }
    showDowntimeDialog.value = true
  }

  const openQualityDialog = () => {
    const workOrders = getAssignedWorkOrders()
    if (workOrders.length > 0) {
      qualityForm.value.workOrderId = workOrders[0].id
    }
    showQualityDialog.value = true
  }

  const openHelpDialog = () => {
    showHelpDialog.value = true
  }

  // Submission handlers
  const quickLogProduction = async (quantity) => {
    if (!selectedWorkOrder.value) return

    isSubmitting.value = true
    try {
      await api.createProductionEntry({
        work_order_id: selectedWorkOrder.value.work_order_id,
        date: getCurrentDate(),
        shift: getActiveShift()?.shift_number || 1,
        units_produced: quantity,
        runtime_hours: 1
      })

      successMessage.value = `Logged ${quantity} units for ${selectedWorkOrder.value.work_order_id}`
      showSuccess.value = true
      await onDataRefresh()
    } catch (error) {
      notificationStore.error(error.response?.data?.detail || 'Failed to log production')
    } finally {
      isSubmitting.value = false
    }
  }

  const submitProduction = async () => {
    isSubmitting.value = true
    try {
      const workOrders = getAssignedWorkOrders()
      const wo = workOrders.find(w => w.id === productionForm.value.workOrderId)
      await api.createProductionEntry({
        work_order_id: wo.work_order_id,
        date: getCurrentDate(),
        shift: getActiveShift()?.shift_number || 1,
        units_produced: productionForm.value.quantity,
        runtime_hours: 1
      })

      successMessage.value = `Logged ${productionForm.value.quantity} units`
      showSuccess.value = true
      showProductionDialog.value = false
      productionForm.value.quantity = 10
      await onDataRefresh()
    } catch (error) {
      notificationStore.error(error.response?.data?.detail || 'Failed to log production')
    } finally {
      isSubmitting.value = false
    }
  }

  const submitDowntime = async () => {
    isSubmitting.value = true
    try {
      const workOrders = getAssignedWorkOrders()
      const wo = workOrders.find(w => w.id === downtimeForm.value.workOrderId)
      await api.createDowntimeEntry({
        work_order_id: wo.work_order_id,
        date: getCurrentDate(),
        shift: getActiveShift()?.shift_number || 1,
        downtime_minutes: downtimeForm.value.minutes,
        reason: downtimeForm.value.reason,
        notes: downtimeForm.value.notes
      })

      successMessage.value = 'Downtime reported successfully'
      showSuccess.value = true
      showDowntimeDialog.value = false
      downtimeForm.value = { workOrderId: null, reason: null, minutes: 15, notes: '' }
      await onDataRefresh()
    } catch (error) {
      notificationStore.error(error.response?.data?.detail || 'Failed to report downtime')
    } finally {
      isSubmitting.value = false
    }
  }

  const submitQuality = async () => {
    isSubmitting.value = true
    try {
      const workOrders = getAssignedWorkOrders()
      const wo = workOrders.find(w => w.id === qualityForm.value.workOrderId)
      await api.createQualityEntry({
        work_order_id: wo.work_order_id,
        date: getCurrentDate(),
        shift: getActiveShift()?.shift_number || 1,
        inspected_quantity: qualityForm.value.inspectedQty,
        defect_quantity: qualityForm.value.defectQty,
        defect_type: qualityForm.value.defectType
      })

      successMessage.value = 'Quality check recorded'
      showSuccess.value = true
      showQualityDialog.value = false
      qualityForm.value = { workOrderId: null, inspectedQty: 100, defectQty: 0, defectType: null }
      await onDataRefresh()
    } catch (error) {
      notificationStore.error(error.response?.data?.detail || 'Failed to record quality check')
    } finally {
      isSubmitting.value = false
    }
  }

  const submitHelpRequest = async () => {
    isSubmitting.value = true
    try {
      successMessage.value = 'Help request sent to supervisor'
      showSuccess.value = true
      showHelpDialog.value = false
      helpForm.value = { type: null, description: '' }
    } catch (error) {
      notificationStore.error('Failed to send help request')
    } finally {
      isSubmitting.value = false
    }
  }

  return {
    // Dialog states
    showProductionDialog,
    showDowntimeDialog,
    showQualityDialog,
    showHelpDialog,
    isSubmitting,
    showSuccess,
    successMessage,
    // Selected work order
    selectedWorkOrder,
    // Form objects
    productionForm,
    downtimeForm,
    qualityForm,
    helpForm,
    // Constants
    productionPresets,
    downtimeReasons,
    defectTypes,
    helpTypes,
    // Dialog openers
    openQuickLog,
    openQuickProductionDialog,
    openDowntimeDialog,
    openQualityDialog,
    openHelpDialog,
    // Submission handlers
    quickLogProduction,
    submitProduction,
    submitDowntime,
    submitQuality,
    submitHelpRequest
  }
}
