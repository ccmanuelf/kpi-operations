/**
 * Composable for Work Order form handling and CRUD operations.
 * Create/edit dialogs, form state, validation, save, delete,
 * status transitions via workflow API.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { transitionWorkOrder } from '@/services/api/workflow'
import { useNotificationStore } from '@/stores/notificationStore'

export interface WorkOrderFormData {
  work_order_id: string
  client_id: string
  style_model: string
  planned_quantity: number | null
  actual_quantity: number
  status: string
  priority: string | null
  planned_start_date: string
  planned_ship_date: string
  customer_po_number: string
  ideal_cycle_time: number | null
  notes: string
}

export interface WorkOrder extends WorkOrderFormData {
  [key: string]: unknown
}

interface FormHandle {
  validate: () => Promise<{ valid: boolean }>
}

type ValidationRule = (v: unknown) => true | string

interface ValidationRules {
  required: ValidationRule
  positive: ValidationRule
  nonNegative: ValidationRule
}

const DEFAULT_FORM_DATA = (): WorkOrderFormData => ({
  work_order_id: '',
  client_id: 'CLIENT001',
  style_model: '',
  planned_quantity: null,
  actual_quantity: 0,
  status: 'ACTIVE',
  priority: null,
  planned_start_date: '',
  planned_ship_date: '',
  customer_po_number: '',
  ideal_cycle_time: null,
  notes: '',
})

export function useWorkOrderForms(
  loadWorkOrders: () => Promise<void>,
  formatStatus: (status: string) => string,
) {
  const notificationStore = useNotificationStore()
  const { t } = useI18n()

  const formDialog = ref(false)
  const deleteDialog = ref(false)
  const editingWorkOrder = ref<WorkOrder | null>(null)
  const workOrderToDelete = ref<WorkOrder | null>(null)
  const formRef = ref<FormHandle | null>(null)
  const formValid = ref(false)

  const saving = ref(false)
  const deleting = ref(false)

  const formData = ref<WorkOrderFormData>(DEFAULT_FORM_DATA())

  const rules: ValidationRules = {
    required: (v) => !!v || 'Required',
    positive: (v) => (typeof v === 'number' && v > 0) || 'Must be greater than 0',
    nonNegative: (v) =>
      v === null ||
      v === '' ||
      (typeof v === 'number' && v >= 0) ||
      'Cannot be negative',
  }

  const openCreateDialog = (): void => {
    editingWorkOrder.value = null
    formData.value = DEFAULT_FORM_DATA()
    formDialog.value = true
  }

  const openEditDialog = (workOrder: WorkOrder): void => {
    editingWorkOrder.value = workOrder
    formData.value = {
      work_order_id: workOrder.work_order_id,
      client_id: workOrder.client_id,
      style_model: workOrder.style_model,
      planned_quantity: workOrder.planned_quantity,
      actual_quantity: workOrder.actual_quantity,
      status: workOrder.status,
      priority: workOrder.priority,
      planned_start_date: workOrder.planned_start_date?.split('T')[0] || '',
      planned_ship_date: workOrder.planned_ship_date?.split('T')[0] || '',
      customer_po_number: workOrder.customer_po_number || '',
      ideal_cycle_time: workOrder.ideal_cycle_time,
      notes: workOrder.notes || '',
    }
    formDialog.value = true
  }

  const saveWorkOrder = async (): Promise<void> => {
    const validateResult = await formRef.value?.validate()
    if (!validateResult?.valid) return

    saving.value = true
    try {
      const data: Partial<WorkOrderFormData> = { ...formData.value }
      if (!data.planned_start_date) delete data.planned_start_date
      if (!data.planned_ship_date) delete data.planned_ship_date
      if (!data.ideal_cycle_time) delete data.ideal_cycle_time
      if (!data.priority) delete data.priority

      if (editingWorkOrder.value) {
        await api.updateWorkOrder(editingWorkOrder.value.work_order_id, data)
        notificationStore.showSuccess(t('notifications.workOrders.updateSuccess'))
      } else {
        await api.createWorkOrder(data)
        notificationStore.showSuccess(t('notifications.workOrders.createSuccess'))
      }

      formDialog.value = false
      await loadWorkOrders()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error saving work order:', error)
      const ax = error as { response?: { data?: { detail?: string } } }
      notificationStore.showError(
        ax?.response?.data?.detail || t('notifications.workOrders.saveFailed'),
      )
    } finally {
      saving.value = false
    }
  }

  // Status transition via workflow API with direct-update fallback —
  // the workflow endpoint enforces guarded transitions; the JS path
  // fell back to a direct PUT if the workflow rejected, preserved
  // here for parity even though it bypasses workflow validation.
  const updateStatus = async (workOrder: WorkOrder, newStatus: string): Promise<void> => {
    try {
      await transitionWorkOrder(workOrder.work_order_id, newStatus)
      notificationStore.showSuccess(
        t('notifications.workOrders.statusUpdated', { status: formatStatus(newStatus) }),
      )
      await loadWorkOrders()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error updating status:', error)
      try {
        await api.updateWorkOrder(workOrder.work_order_id, { status: newStatus })
        notificationStore.showSuccess(
          t('notifications.workOrders.statusUpdated', { status: formatStatus(newStatus) }),
        )
        await loadWorkOrders()
      } catch {
        notificationStore.showError(t('notifications.workOrders.statusUpdateFailed'))
      }
    }
  }

  const onStatusTransitioned = (): void => {
    loadWorkOrders()
  }

  const confirmDelete = (workOrder: WorkOrder): void => {
    workOrderToDelete.value = workOrder
    deleteDialog.value = true
  }

  const deleteWorkOrder = async (): Promise<void> => {
    if (!workOrderToDelete.value) return

    deleting.value = true
    try {
      await api.deleteWorkOrder(workOrderToDelete.value.work_order_id)
      notificationStore.showSuccess(t('notifications.workOrders.deleteSuccess'))
      deleteDialog.value = false
      workOrderToDelete.value = null
      await loadWorkOrders()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error deleting work order:', error)
      const ax = error as { response?: { data?: { detail?: string } } }
      notificationStore.showError(
        ax?.response?.data?.detail || t('notifications.workOrders.deleteFailed'),
      )
    } finally {
      deleting.value = false
    }
  }

  return {
    formDialog,
    deleteDialog,
    editingWorkOrder,
    workOrderToDelete,
    formRef,
    formValid,
    saving,
    deleting,
    formData,
    rules,
    openCreateDialog,
    openEditDialog,
    saveWorkOrder,
    updateStatus,
    onStatusTransitioned,
    confirmDelete,
    deleteWorkOrder,
  }
}
