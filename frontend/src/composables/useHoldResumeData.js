/**
 * Composable for HoldResumeEntry form state, validation, and hold/resume operations.
 * Extracted from HoldResumeEntry.vue to keep component under 500 lines.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'

export function useHoldResumeData(emit) {
  const { t } = useI18n()

  // State
  const tab = ref('hold')
  const holdForm = ref(null)
  const resumeForm = ref(null)
  const holdValid = ref(false)
  const resumeValid = ref(false)
  const loading = ref(false)
  const initialLoading = ref(true)
  const workOrders = ref([])
  const activeHolds = ref([])
  const selectedHoldId = ref(null)
  const selectedHold = ref(null)
  const showHoldConfirmDialog = ref(false)
  const showResumeConfirmDialog = ref(false)
  const snackbar = ref({ show: false, text: '', color: 'info' })

  // Dropdown options
  const holdReasons = computed(() => [
    { title: t('holds.reasons.qualityIssue'), value: 'Quality Issue' },
    { title: t('holds.reasons.materialDefect'), value: 'Material Defect' },
    { title: t('holds.reasons.processNonConformance'), value: 'Process Non-Conformance' },
    { title: t('holds.reasons.customerRequest'), value: 'Customer Request' },
    { title: t('holds.reasons.engineeringChange'), value: 'Engineering Change' },
    { title: t('holds.reasons.inspectionFailure'), value: 'Inspection Failure' },
    { title: t('holds.reasons.supplierIssue'), value: 'Supplier Issue' },
    { title: t('holds.reasons.other'), value: 'Other' }
  ])

  const severities = computed(() => [
    { title: t('holds.severities.critical'), value: 'Critical' },
    { title: t('holds.severities.high'), value: 'High' },
    { title: t('holds.severities.medium'), value: 'Medium' },
    { title: t('holds.severities.low'), value: 'Low' }
  ])

  const dispositions = computed(() => [
    { title: t('holds.dispositions.release'), value: 'Release' },
    { title: t('holds.dispositions.rework'), value: 'Rework' },
    { title: t('holds.dispositions.scrap'), value: 'Scrap' },
    { title: t('holds.dispositions.returnToSupplier'), value: 'Return to Supplier' },
    { title: t('holds.dispositions.useAsIs'), value: 'Use As Is' }
  ])

  // Form data
  const holdData = ref({
    work_order_id: null,
    quantity: 0,
    reason: '',
    severity: '',
    description: '',
    required_action: '',
    initiated_by: '',
    customer_notification_required: false
  })

  const resumeData = ref({
    disposition: '',
    released_quantity: 0,
    resolution_notes: '',
    approved_by: '',
    customer_notified: false
  })

  // Validation rules
  const rules = {
    required: value => !!value || t('validation.required'),
    positive: value => value > 0 || t('validation.positive')
  }

  // Confirmation dialog field configs
  const holdConfirmationFieldConfig = computed(() => {
    const workOrderName = workOrders.value.find(w => w.id === holdData.value.work_order_id)?.work_order || 'N/A'

    return [
      { key: 'work_order_id', label: t('production.workOrder'), type: 'text', displayValue: workOrderName },
      { key: 'quantity', label: t('workOrders.quantity'), type: 'number' },
      { key: 'reason', label: t('holds.holdReason'), type: 'text' },
      { key: 'severity', label: t('holds.severity'), type: 'text' },
      { key: 'description', label: t('holds.holdDescription'), type: 'text' },
      { key: 'required_action', label: t('holds.requiredAction'), type: 'text' },
      { key: 'initiated_by', label: t('holds.initiatedBy'), type: 'text' },
      { key: 'customer_notification_required', label: t('holds.customerNotificationRequired'), type: 'boolean' }
    ]
  })

  const resumeConfirmData = computed(() => ({
    work_order: selectedHold.value?.work_order || 'N/A',
    original_quantity: selectedHold.value?.quantity || 0,
    hold_reason: selectedHold.value?.reason || 'N/A',
    ...resumeData.value
  }))

  const resumeConfirmationFieldConfig = computed(() => {
    return [
      { key: 'work_order', label: t('production.workOrder'), type: 'text' },
      { key: 'original_quantity', label: t('holds.originalQuantity'), type: 'number' },
      { key: 'hold_reason', label: t('holds.originalHoldReason'), type: 'text' },
      { key: 'disposition', label: t('holds.disposition'), type: 'text' },
      { key: 'released_quantity', label: t('holds.releasedQuantity'), type: 'number' },
      { key: 'resolution_notes', label: t('holds.resolutionNotes'), type: 'text' },
      { key: 'approved_by', label: t('holds.approvedBy'), type: 'text' },
      { key: 'customer_notified', label: t('holds.customerNotified'), type: 'boolean' }
    ]
  })

  // Helper
  const formatDate = (date) => {
    return date ? format(new Date(date), 'MMM dd, yyyy HH:mm') : ''
  }

  // Data loading
  const loadActiveHolds = async () => {
    try {
      const response = await api.getActiveHolds()
      activeHolds.value = response.data.map(hold => ({
        ...hold,
        display: `${hold.work_order} - ${hold.quantity} units (${hold.reason})`
      }))
    } catch (error) {
      console.error('Error loading active holds:', error)
    } finally {
      initialLoading.value = false
    }
  }

  const loadHoldDetails = async () => {
    if (!selectedHoldId.value) return

    const hold = activeHolds.value.find(h => h.id === selectedHoldId.value)
    selectedHold.value = hold
    resumeData.value.released_quantity = hold?.quantity || 0
  }

  const onImported = () => {
    loadActiveHolds()
    emit('submitted')
  }

  // Hold operations
  const submitHold = async () => {
    const { valid: isValid } = await holdForm.value.validate()
    if (!isValid) return
    showHoldConfirmDialog.value = true
  }

  const onConfirmHold = async () => {
    showHoldConfirmDialog.value = false
    loading.value = true

    try {
      await api.createHoldEntry(holdData.value)

      holdData.value = {
        work_order_id: null,
        quantity: 0,
        reason: '',
        severity: '',
        description: '',
        required_action: '',
        initiated_by: '',
        customer_notification_required: false
      }
      holdForm.value.reset()

      await loadActiveHolds()
      emit('submitted')
    } catch (error) {
      snackbar.value = {
        show: true,
        text: t('holds.errors.createHold') + ': ' + (error.response?.data?.detail || error.message),
        color: 'error'
      }
    } finally {
      loading.value = false
    }
  }

  const onCancelHold = () => {
    showHoldConfirmDialog.value = false
  }

  // Resume operations
  const submitResume = async () => {
    const { valid: isValid } = await resumeForm.value.validate()
    if (!isValid || !selectedHoldId.value) return
    showResumeConfirmDialog.value = true
  }

  const onConfirmResume = async () => {
    showResumeConfirmDialog.value = false
    loading.value = true

    try {
      await api.resumeHold(selectedHoldId.value, resumeData.value)

      selectedHoldId.value = null
      selectedHold.value = null
      resumeData.value = {
        disposition: '',
        released_quantity: 0,
        resolution_notes: '',
        approved_by: '',
        customer_notified: false
      }
      resumeForm.value.reset()

      await loadActiveHolds()
      emit('submitted')
    } catch (error) {
      snackbar.value = {
        show: true,
        text: t('holds.errors.resumeHold') + ': ' + (error.response?.data?.detail || error.message),
        color: 'error'
      }
    } finally {
      loading.value = false
    }
  }

  const onCancelResume = () => {
    showResumeConfirmDialog.value = false
  }

  return {
    // State
    tab,
    holdForm,
    resumeForm,
    holdValid,
    resumeValid,
    loading,
    initialLoading,
    workOrders,
    activeHolds,
    selectedHoldId,
    selectedHold,
    showHoldConfirmDialog,
    showResumeConfirmDialog,
    snackbar,
    // Dropdown options
    holdReasons,
    severities,
    dispositions,
    // Form data
    holdData,
    resumeData,
    // Validation
    rules,
    // Confirmation config
    holdConfirmationFieldConfig,
    resumeConfirmData,
    resumeConfirmationFieldConfig,
    // Methods
    formatDate,
    loadActiveHolds,
    loadHoldDetails,
    onImported,
    submitHold,
    onConfirmHold,
    onCancelHold,
    submitResume,
    onConfirmResume,
    onCancelResume
  }
}
