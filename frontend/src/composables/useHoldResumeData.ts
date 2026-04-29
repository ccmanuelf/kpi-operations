/**
 * Composable for HoldResumeEntry form state, validation, and
 * hold/resume operations.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'

export interface WorkOrderRef {
  id?: string | number
  work_order?: string
  work_order_id?: string | number
  [key: string]: unknown
}

export interface ActiveHold {
  id: string | number
  work_order?: string
  work_order_id?: string | number
  quantity?: number
  reason?: string
  display?: string
  [key: string]: unknown
}

export interface HoldFormData {
  work_order_id: string | number | null
  quantity: number
  reason: string
  severity: string
  description: string
  required_action: string
  initiated_by: string
  customer_notification_required: boolean
}

export interface ResumeFormData {
  disposition: string
  released_quantity: number
  resolution_notes: string
  approved_by: string
  customer_notified: boolean
}

interface FormHandle {
  validate: () => Promise<{ valid: boolean }>
  reset: () => void
}

export interface DropdownOption {
  title: string
  value: string
}

export interface FieldConfig {
  key: string
  label: string
  type: 'text' | 'number' | 'boolean'
  displayValue?: string | number
}

interface SnackbarState {
  show: boolean
  text: string
  color: string
}

type EmitFn = (event: string, payload?: unknown) => void

const initialHoldData = (): HoldFormData => ({
  work_order_id: null,
  quantity: 0,
  reason: '',
  severity: '',
  description: '',
  required_action: '',
  initiated_by: '',
  customer_notification_required: false,
})

const initialResumeData = (): ResumeFormData => ({
  disposition: '',
  released_quantity: 0,
  resolution_notes: '',
  approved_by: '',
  customer_notified: false,
})

export function useHoldResumeData(emit: EmitFn) {
  const { t } = useI18n()

  const tab = ref<'hold' | 'resume'>('hold')
  const holdForm = ref<FormHandle | null>(null)
  const resumeForm = ref<FormHandle | null>(null)
  const holdValid = ref(false)
  const resumeValid = ref(false)
  const loading = ref(false)
  const initialLoading = ref(true)
  const workOrders = ref<WorkOrderRef[]>([])
  const activeHolds = ref<ActiveHold[]>([])
  const selectedHoldId = ref<string | number | null>(null)
  const selectedHold = ref<ActiveHold | null>(null)
  const showHoldConfirmDialog = ref(false)
  const showResumeConfirmDialog = ref(false)
  const snackbar = ref<SnackbarState>({ show: false, text: '', color: 'info' })

  const holdReasons = computed<DropdownOption[]>(() => [
    { title: t('holds.reasons.qualityIssue'), value: 'Quality Issue' },
    { title: t('holds.reasons.materialDefect'), value: 'Material Defect' },
    { title: t('holds.reasons.processNonConformance'), value: 'Process Non-Conformance' },
    { title: t('holds.reasons.customerRequest'), value: 'Customer Request' },
    { title: t('holds.reasons.engineeringChange'), value: 'Engineering Change' },
    { title: t('holds.reasons.inspectionFailure'), value: 'Inspection Failure' },
    { title: t('holds.reasons.supplierIssue'), value: 'Supplier Issue' },
    { title: t('holds.reasons.other'), value: 'Other' },
  ])

  const severities = computed<DropdownOption[]>(() => [
    { title: t('holds.severities.critical'), value: 'Critical' },
    { title: t('holds.severities.high'), value: 'High' },
    { title: t('holds.severities.medium'), value: 'Medium' },
    { title: t('holds.severities.low'), value: 'Low' },
  ])

  const dispositions = computed<DropdownOption[]>(() => [
    { title: t('holds.dispositions.release'), value: 'Release' },
    { title: t('holds.dispositions.rework'), value: 'Rework' },
    { title: t('holds.dispositions.scrap'), value: 'Scrap' },
    { title: t('holds.dispositions.returnToSupplier'), value: 'Return to Supplier' },
    { title: t('holds.dispositions.useAsIs'), value: 'Use As Is' },
  ])

  const holdData = ref<HoldFormData>(initialHoldData())
  const resumeData = ref<ResumeFormData>(initialResumeData())

  const rules = {
    required: (value: unknown) => !!value || t('validation.required'),
    positive: (value: unknown) =>
      (typeof value === 'number' && value > 0) || t('validation.positive'),
  }

  const holdConfirmationFieldConfig = computed<FieldConfig[]>(() => {
    const workOrderName =
      workOrders.value.find((w) => w.id === holdData.value.work_order_id)
        ?.work_order || 'N/A'

    return [
      {
        key: 'work_order_id',
        label: t('production.workOrder'),
        type: 'text',
        displayValue: workOrderName,
      },
      { key: 'quantity', label: t('workOrders.quantity'), type: 'number' },
      { key: 'reason', label: t('holds.holdReason'), type: 'text' },
      { key: 'severity', label: t('holds.severity'), type: 'text' },
      { key: 'description', label: t('holds.holdDescription'), type: 'text' },
      { key: 'required_action', label: t('holds.requiredAction'), type: 'text' },
      { key: 'initiated_by', label: t('holds.initiatedBy'), type: 'text' },
      {
        key: 'customer_notification_required',
        label: t('holds.customerNotificationRequired'),
        type: 'boolean',
      },
    ]
  })

  const resumeConfirmData = computed(() => ({
    work_order: selectedHold.value?.work_order || 'N/A',
    original_quantity: selectedHold.value?.quantity || 0,
    hold_reason: selectedHold.value?.reason || 'N/A',
    ...resumeData.value,
  }))

  const resumeConfirmationFieldConfig = computed<FieldConfig[]>(() => [
    { key: 'work_order', label: t('production.workOrder'), type: 'text' },
    { key: 'original_quantity', label: t('holds.originalQuantity'), type: 'number' },
    { key: 'hold_reason', label: t('holds.originalHoldReason'), type: 'text' },
    { key: 'disposition', label: t('holds.disposition'), type: 'text' },
    { key: 'released_quantity', label: t('holds.releasedQuantity'), type: 'number' },
    { key: 'resolution_notes', label: t('holds.resolutionNotes'), type: 'text' },
    { key: 'approved_by', label: t('holds.approvedBy'), type: 'text' },
    { key: 'customer_notified', label: t('holds.customerNotified'), type: 'boolean' },
  ])

  const formatDate = (date: string | Date | null | undefined): string =>
    date ? format(new Date(date), 'MMM dd, yyyy HH:mm') : ''

  const loadActiveHolds = async (): Promise<void> => {
    try {
      const response = await api.getActiveHolds()
      activeHolds.value = (response.data as ActiveHold[]).map((hold) => ({
        ...hold,
        display: `${hold.work_order} - ${hold.quantity} units (${hold.reason})`,
      }))
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading active holds:', error)
    } finally {
      initialLoading.value = false
    }
  }

  const loadHoldDetails = async (): Promise<void> => {
    if (!selectedHoldId.value) return

    const hold = activeHolds.value.find((h) => h.id === selectedHoldId.value)
    selectedHold.value = hold ?? null
    resumeData.value.released_quantity = hold?.quantity || 0
  }

  const onImported = (): void => {
    loadActiveHolds()
    emit('submitted')
  }

  const submitHold = async (): Promise<void> => {
    const result = await holdForm.value?.validate()
    if (!result?.valid) return
    showHoldConfirmDialog.value = true
  }

  const onConfirmHold = async (): Promise<void> => {
    showHoldConfirmDialog.value = false
    loading.value = true

    try {
      await api.createHoldEntry(holdData.value)

      holdData.value = initialHoldData()
      holdForm.value?.reset()

      await loadActiveHolds()
      emit('submitted')
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } }; message?: string }
      snackbar.value = {
        show: true,
        text:
          t('holds.errors.createHold') +
          ': ' +
          (ax?.response?.data?.detail || ax?.message || ''),
        color: 'error',
      }
    } finally {
      loading.value = false
    }
  }

  const onCancelHold = (): void => {
    showHoldConfirmDialog.value = false
  }

  const submitResume = async (): Promise<void> => {
    const result = await resumeForm.value?.validate()
    if (!result?.valid || !selectedHoldId.value) return
    showResumeConfirmDialog.value = true
  }

  const onConfirmResume = async (): Promise<void> => {
    showResumeConfirmDialog.value = false
    if (!selectedHoldId.value) return
    loading.value = true

    try {
      await api.resumeHold(selectedHoldId.value, resumeData.value)

      selectedHoldId.value = null
      selectedHold.value = null
      resumeData.value = initialResumeData()
      resumeForm.value?.reset()

      await loadActiveHolds()
      emit('submitted')
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } }; message?: string }
      snackbar.value = {
        show: true,
        text:
          t('holds.errors.resumeHold') +
          ': ' +
          (ax?.response?.data?.detail || ax?.message || ''),
        color: 'error',
      }
    } finally {
      loading.value = false
    }
  }

  const onCancelResume = (): void => {
    showResumeConfirmDialog.value = false
  }

  return {
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
    holdReasons,
    severities,
    dispositions,
    holdData,
    resumeData,
    rules,
    holdConfirmationFieldConfig,
    resumeConfirmData,
    resumeConfirmationFieldConfig,
    formatDate,
    loadActiveHolds,
    loadHoldDetails,
    onImported,
    submitHold,
    onConfirmHold,
    onCancelHold,
    submitResume,
    onConfirmResume,
    onCancelResume,
  }
}
