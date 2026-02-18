/**
 * Composable for Work Order form handling and CRUD operations.
 * Handles: create/edit dialogs, form state, validation, save, delete,
 *          status transitions via workflow API.
 */
import { ref } from 'vue'
import api from '@/services/api'
import { transitionWorkOrder } from '@/services/api/workflow'
import { useNotificationStore } from '@/stores/notificationStore'

const DEFAULT_FORM_DATA = {
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
  notes: ''
}

export function useWorkOrderForms(loadWorkOrders, formatStatus) {
  const notificationStore = useNotificationStore()

  // Dialog state
  const formDialog = ref(false)
  const deleteDialog = ref(false)
  const editingWorkOrder = ref(null)
  const workOrderToDelete = ref(null)
  const formRef = ref(null)
  const formValid = ref(false)

  // Loading flags
  const saving = ref(false)
  const deleting = ref(false)

  // Form data
  const formData = ref({ ...DEFAULT_FORM_DATA })

  // Validation rules
  const rules = {
    required: v => !!v || 'Required',
    positive: v => (v && v > 0) || 'Must be greater than 0',
    nonNegative: v => v === null || v === '' || v >= 0 || 'Cannot be negative'
  }

  // Create dialog
  const openCreateDialog = () => {
    editingWorkOrder.value = null
    formData.value = { ...DEFAULT_FORM_DATA }
    formDialog.value = true
  }

  // Edit dialog
  const openEditDialog = (workOrder) => {
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
      notes: workOrder.notes || ''
    }
    formDialog.value = true
  }

  // Save (create or update)
  const saveWorkOrder = async () => {
    const { valid } = await formRef.value.validate()
    if (!valid) return

    saving.value = true
    try {
      const data = { ...formData.value }
      if (!data.planned_start_date) delete data.planned_start_date
      if (!data.planned_ship_date) delete data.planned_ship_date
      if (!data.ideal_cycle_time) delete data.ideal_cycle_time
      if (!data.priority) delete data.priority

      if (editingWorkOrder.value) {
        await api.updateWorkOrder(editingWorkOrder.value.work_order_id, data)
        notificationStore.showSuccess('Work order updated successfully')
      } else {
        await api.createWorkOrder(data)
        notificationStore.showSuccess('Work order created successfully')
      }

      formDialog.value = false
      await loadWorkOrders()
    } catch (error) {
      console.error('Error saving work order:', error)
      notificationStore.showError(
        error.response?.data?.detail || 'Failed to save work order'
      )
    } finally {
      saving.value = false
    }
  }

  // Status transition via workflow API with direct-update fallback
  const updateStatus = async (workOrder, newStatus) => {
    try {
      await transitionWorkOrder(workOrder.work_order_id, newStatus)
      notificationStore.showSuccess(`Work order status updated to ${formatStatus(newStatus)}`)
      await loadWorkOrders()
    } catch (error) {
      console.error('Error updating status:', error)
      try {
        await api.updateWorkOrder(workOrder.work_order_id, { status: newStatus })
        notificationStore.showSuccess(`Work order status updated to ${formatStatus(newStatus)}`)
        await loadWorkOrders()
      } catch (fallbackError) {
        notificationStore.showError('Failed to update status')
      }
    }
  }

  // Handle status transition from WorkOrderStatusChip
  const onStatusTransitioned = () => {
    loadWorkOrders()
  }

  // Delete confirmation
  const confirmDelete = (workOrder) => {
    workOrderToDelete.value = workOrder
    deleteDialog.value = true
  }

  // Delete work order
  const deleteWorkOrder = async () => {
    if (!workOrderToDelete.value) return

    deleting.value = true
    try {
      await api.deleteWorkOrder(workOrderToDelete.value.work_order_id)
      notificationStore.showSuccess('Work order deleted successfully')
      deleteDialog.value = false
      workOrderToDelete.value = null
      await loadWorkOrders()
    } catch (error) {
      console.error('Error deleting work order:', error)
      notificationStore.showError(
        error.response?.data?.detail || 'Failed to delete work order'
      )
    } finally {
      deleting.value = false
    }
  }

  return {
    // Dialog state
    formDialog,
    deleteDialog,
    editingWorkOrder,
    workOrderToDelete,
    formRef,
    formValid,
    // Loading
    saving,
    deleting,
    // Form
    formData,
    rules,
    // Methods
    openCreateDialog,
    openEditDialog,
    saveWorkOrder,
    updateStatus,
    onStatusTransitioned,
    confirmDelete,
    deleteWorkOrder
  }
}
