<template>
  <v-container fluid>
    <v-skeleton-loader
      v-if="initialLoading"
      type="heading, card, table"
      class="mb-4"
    />
    <template v-else>
      <!-- Header -->
      <v-row class="mb-4">
        <v-col cols="12">
          <div class="d-flex justify-space-between align-center flex-wrap ga-2">
            <div>
              <h1 class="text-h4 font-weight-bold">Work Order Management</h1>
              <p class="text-body-2 text-medium-emphasis mt-1">
                Track and manage production work orders
              </p>
            </div>
            <v-btn
              color="primary"
              prepend-icon="mdi-plus"
              @click="openCreateDialog"
            >
              New Work Order
            </v-btn>
          </div>
        </v-col>
      </v-row>

      <!-- Summary Cards -->
      <v-row class="mb-4">
        <v-col cols="12" sm="6" md="3">
          <v-card class="pa-4" variant="tonal" color="primary">
            <div class="d-flex align-center">
              <v-avatar color="primary" size="48" class="mr-4">
                <v-icon>mdi-clipboard-list</v-icon>
              </v-avatar>
              <div>
                <div class="text-h5 font-weight-bold">{{ summaryStats.total }}</div>
                <div class="text-body-2">Total Orders</div>
              </div>
            </div>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card class="pa-4" variant="tonal" color="info">
            <div class="d-flex align-center">
              <v-avatar color="info" size="48" class="mr-4">
                <v-icon>mdi-progress-clock</v-icon>
              </v-avatar>
              <div>
                <div class="text-h5 font-weight-bold">{{ summaryStats.active }}</div>
                <div class="text-body-2">Active</div>
              </div>
            </div>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card class="pa-4" variant="tonal" color="warning">
            <div class="d-flex align-center">
              <v-avatar color="warning" size="48" class="mr-4">
                <v-icon>mdi-pause-circle</v-icon>
              </v-avatar>
              <div>
                <div class="text-h5 font-weight-bold">{{ summaryStats.onHold }}</div>
                <div class="text-body-2">On Hold</div>
              </div>
            </div>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card class="pa-4" variant="tonal" color="success">
            <div class="d-flex align-center">
              <v-avatar color="success" size="48" class="mr-4">
                <v-icon>mdi-check-circle</v-icon>
              </v-avatar>
              <div>
                <div class="text-h5 font-weight-bold">{{ summaryStats.completed }}</div>
                <div class="text-body-2">Completed</div>
              </div>
            </div>
          </v-card>
        </v-col>
      </v-row>

      <!-- Filters -->
      <v-card class="mb-4">
        <v-card-text>
          <v-row align="center">
            <v-col cols="12" md="3">
              <v-text-field
                v-model="filters.search"
                prepend-inner-icon="mdi-magnify"
                label="Search work orders..."
                variant="outlined"
                density="compact"
                hide-details
                clearable
                @update:model-value="debouncedSearch"
              />
            </v-col>
            <v-col cols="12" md="2">
              <v-select
                v-model="filters.status"
                :items="statusOptions"
                label="Status"
                variant="outlined"
                density="compact"
                hide-details
                clearable
                @update:model-value="loadWorkOrders"
              />
            </v-col>
            <v-col cols="12" md="2">
              <v-select
                v-model="filters.priority"
                :items="priorityOptions"
                label="Priority"
                variant="outlined"
                density="compact"
                hide-details
                clearable
                @update:model-value="loadWorkOrders"
              />
            </v-col>
            <v-col cols="12" md="2">
              <v-text-field
                v-model="filters.startDate"
                type="date"
                label="Start Date"
                variant="outlined"
                density="compact"
                hide-details
                @update:model-value="loadWorkOrders"
              />
            </v-col>
            <v-col cols="12" md="2">
              <v-text-field
                v-model="filters.endDate"
                type="date"
                label="End Date"
                variant="outlined"
                density="compact"
                hide-details
                @update:model-value="loadWorkOrders"
              />
            </v-col>
            <v-col cols="12" md="1">
              <v-btn
                variant="text"
                color="primary"
                @click="resetFilters"
              >
                Reset
              </v-btn>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- Work Orders Table -->
      <v-card>
        <v-data-table
          :headers="headers"
          :items="workOrders"
          :loading="loading"
          :items-per-page="25"
          :sort-by="[{ key: 'planned_ship_date', order: 'asc' }]"
          class="elevation-0"
          hover
          @click:row="onRowClick"
        >
          <!-- Work Order ID -->
          <template v-slot:item.work_order_id="{ item }">
            <div class="font-weight-medium text-primary">
              {{ item.work_order_id }}
            </div>
          </template>

          <!-- Style/Model -->
          <template v-slot:item.style_model="{ item }">
            <div class="text-body-2">{{ item.style_model }}</div>
          </template>

          <!-- Progress -->
          <template v-slot:item.progress="{ item }">
            <div class="d-flex align-center" style="min-width: 150px;">
              <v-progress-linear
                :model-value="calculateProgress(item)"
                :color="getProgressColor(item)"
                height="8"
                rounded
                class="mr-2"
              />
              <span class="text-body-2 text-no-wrap">
                {{ item.actual_quantity }} / {{ item.planned_quantity }}
              </span>
            </div>
          </template>

          <!-- Progress Percentage -->
          <template v-slot:item.progress_pct="{ item }">
            <span class="font-weight-medium">
              {{ calculateProgress(item).toFixed(1) }}%
            </span>
          </template>

          <!-- Status -->
          <template v-slot:item.status="{ item }">
            <v-chip
              :color="getStatusColor(item.status)"
              size="small"
              variant="flat"
            >
              {{ formatStatus(item.status) }}
            </v-chip>
          </template>

          <!-- Priority -->
          <template v-slot:item.priority="{ item }">
            <v-chip
              v-if="item.priority"
              :color="getPriorityColor(item.priority)"
              size="small"
              variant="outlined"
            >
              {{ item.priority }}
            </v-chip>
            <span v-else class="text-medium-emphasis">-</span>
          </template>

          <!-- Due Date -->
          <template v-slot:item.planned_ship_date="{ item }">
            <div v-if="item.planned_ship_date" class="d-flex align-center">
              <v-icon
                v-if="isOverdue(item)"
                color="error"
                size="small"
                class="mr-1"
              >
                mdi-alert-circle
              </v-icon>
              <span :class="{ 'text-error': isOverdue(item) }">
                {{ formatDate(item.planned_ship_date) }}
              </span>
            </div>
            <span v-else class="text-medium-emphasis">Not set</span>
          </template>

          <!-- Actions -->
          <template v-slot:item.actions="{ item }">
            <v-btn
              icon
              size="small"
              variant="text"
              @click.stop="openDetailDrawer(item)"
            >
              <v-icon>mdi-eye</v-icon>
              <v-tooltip activator="parent">View Details</v-tooltip>
            </v-btn>
            <v-btn
              icon
              size="small"
              variant="text"
              @click.stop="openEditDialog(item)"
            >
              <v-icon>mdi-pencil</v-icon>
              <v-tooltip activator="parent">Edit</v-tooltip>
            </v-btn>
            <v-menu>
              <template v-slot:activator="{ props }">
                <v-btn
                  icon
                  size="small"
                  variant="text"
                  v-bind="props"
                  @click.stop
                >
                  <v-icon>mdi-dots-vertical</v-icon>
                </v-btn>
              </template>
              <v-list density="compact">
                <v-list-item
                  v-if="item.status === 'ACTIVE'"
                  prepend-icon="mdi-pause"
                  @click="updateStatus(item, 'ON_HOLD')"
                >
                  <v-list-item-title>Put On Hold</v-list-item-title>
                </v-list-item>
                <v-list-item
                  v-if="item.status === 'ON_HOLD'"
                  prepend-icon="mdi-play"
                  @click="updateStatus(item, 'ACTIVE')"
                >
                  <v-list-item-title>Resume</v-list-item-title>
                </v-list-item>
                <v-list-item
                  v-if="item.status === 'ACTIVE'"
                  prepend-icon="mdi-check"
                  @click="updateStatus(item, 'COMPLETED')"
                >
                  <v-list-item-title>Mark Complete</v-list-item-title>
                </v-list-item>
                <v-divider />
                <v-list-item
                  prepend-icon="mdi-delete"
                  base-color="error"
                  @click="confirmDelete(item)"
                >
                  <v-list-item-title>Delete</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
          </template>
        </v-data-table>
      </v-card>
    </template>

    <!-- Work Order Detail Drawer -->
    <WorkOrderDetailDrawer
      v-model="detailDrawerOpen"
      :work-order="selectedWorkOrder"
      @update="loadWorkOrders"
      @edit="openEditDialog"
    />

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="formDialog" max-width="700" persistent>
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center">
          <span>{{ editingWorkOrder ? 'Edit Work Order' : 'Create Work Order' }}</span>
          <v-btn icon variant="text" @click="formDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <v-form ref="formRef" v-model="formValid">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.work_order_id"
                  label="Work Order ID *"
                  variant="outlined"
                  :rules="[rules.required]"
                  :disabled="!!editingWorkOrder"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.style_model"
                  label="Style/Model *"
                  variant="outlined"
                  :rules="[rules.required]"
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.planned_quantity"
                  type="number"
                  label="Planned Quantity *"
                  variant="outlined"
                  :rules="[rules.required, rules.positive]"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.actual_quantity"
                  type="number"
                  label="Actual Quantity"
                  variant="outlined"
                  :rules="[rules.nonNegative]"
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-select
                  v-model="formData.status"
                  :items="statusOptions"
                  label="Status *"
                  variant="outlined"
                  :rules="[rules.required]"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="formData.priority"
                  :items="priorityOptions"
                  label="Priority"
                  variant="outlined"
                  clearable
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.planned_start_date"
                  type="date"
                  label="Planned Start Date"
                  variant="outlined"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.planned_ship_date"
                  type="date"
                  label="Planned Ship Date"
                  variant="outlined"
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.customer_po_number"
                  label="Customer PO Number"
                  variant="outlined"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.ideal_cycle_time"
                  type="number"
                  step="0.01"
                  label="Ideal Cycle Time (hrs)"
                  variant="outlined"
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12">
                <v-textarea
                  v-model="formData.notes"
                  label="Notes"
                  variant="outlined"
                  rows="3"
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="formDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!formValid"
            @click="saveWorkOrder"
          >
            {{ editingWorkOrder ? 'Update' : 'Create' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6">Confirm Delete</v-card-title>
        <v-card-text>
          Are you sure you want to delete work order
          <strong>{{ workOrderToDelete?.work_order_id }}</strong>?
          This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Cancel</v-btn>
          <v-btn
            color="error"
            :loading="deleting"
            @click="deleteWorkOrder"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { format, parseISO, isAfter, startOfDay } from 'date-fns'
import api from '@/services/api'
import { useNotificationStore } from '@/stores/notificationStore'
import WorkOrderDetailDrawer from '@/components/WorkOrderDetailDrawer.vue'

// Simple debounce utility
const debounce = (fn, delay) => {
  let timeoutId
  return (...args) => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }
}

const notificationStore = useNotificationStore()

// State
const initialLoading = ref(true)
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const workOrders = ref([])
const selectedWorkOrder = ref(null)
const detailDrawerOpen = ref(false)
const formDialog = ref(false)
const deleteDialog = ref(false)
const editingWorkOrder = ref(null)
const workOrderToDelete = ref(null)
const formRef = ref(null)
const formValid = ref(false)

// Filters
const filters = ref({
  search: '',
  status: null,
  priority: null,
  startDate: '',
  endDate: ''
})

// Form data
const formData = ref({
  work_order_id: '',
  client_id: 'CLIENT001', // Default client
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
})

// Options
const statusOptions = [
  { title: 'Active', value: 'ACTIVE' },
  { title: 'On Hold', value: 'ON_HOLD' },
  { title: 'Completed', value: 'COMPLETED' },
  { title: 'Rejected', value: 'REJECTED' },
  { title: 'Cancelled', value: 'CANCELLED' }
]

const priorityOptions = [
  { title: 'High', value: 'HIGH' },
  { title: 'Medium', value: 'MEDIUM' },
  { title: 'Low', value: 'LOW' }
]

// Validation rules
const rules = {
  required: v => !!v || 'Required',
  positive: v => (v && v > 0) || 'Must be greater than 0',
  nonNegative: v => v === null || v === '' || v >= 0 || 'Cannot be negative'
}

// Table headers
const headers = [
  { title: 'WO Number', key: 'work_order_id', sortable: true },
  { title: 'Style/Model', key: 'style_model', sortable: true },
  { title: 'Progress', key: 'progress', sortable: false, width: '200px' },
  { title: '%', key: 'progress_pct', sortable: true, width: '80px' },
  { title: 'Status', key: 'status', sortable: true },
  { title: 'Priority', key: 'priority', sortable: true },
  { title: 'Due Date', key: 'planned_ship_date', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, width: '140px' }
]

// Computed
const summaryStats = computed(() => {
  const stats = {
    total: workOrders.value.length,
    active: 0,
    onHold: 0,
    completed: 0
  }
  workOrders.value.forEach(wo => {
    if (wo.status === 'ACTIVE') stats.active++
    else if (wo.status === 'ON_HOLD') stats.onHold++
    else if (wo.status === 'COMPLETED') stats.completed++
  })
  return stats
})

// Methods
const loadWorkOrders = async () => {
  loading.value = true
  try {
    const params = {}
    if (filters.value.status) params.status_filter = filters.value.status
    if (filters.value.search) params.style_model = filters.value.search

    const response = await api.getWorkOrders(params)
    workOrders.value = response.data || []
  } catch (error) {
    console.error('Error loading work orders:', error)
    notificationStore.showError('Failed to load work orders')
  } finally {
    loading.value = false
    initialLoading.value = false
  }
}

const debouncedSearch = debounce(() => {
  loadWorkOrders()
}, 300)

const resetFilters = () => {
  filters.value = {
    search: '',
    status: null,
    priority: null,
    startDate: '',
    endDate: ''
  }
  loadWorkOrders()
}

const calculateProgress = (item) => {
  if (!item.planned_quantity || item.planned_quantity === 0) return 0
  return (item.actual_quantity / item.planned_quantity) * 100
}

const getProgressColor = (item) => {
  const progress = calculateProgress(item)
  if (progress >= 100) return 'success'
  if (progress >= 75) return 'info'
  if (progress >= 50) return 'warning'
  return 'error'
}

const getStatusColor = (status) => {
  const colors = {
    ACTIVE: 'info',
    ON_HOLD: 'warning',
    COMPLETED: 'success',
    REJECTED: 'error',
    CANCELLED: 'grey'
  }
  return colors[status] || 'grey'
}

const formatStatus = (status) => {
  const labels = {
    ACTIVE: 'Active',
    ON_HOLD: 'On Hold',
    COMPLETED: 'Completed',
    REJECTED: 'Rejected',
    CANCELLED: 'Cancelled'
  }
  return labels[status] || status
}

const getPriorityColor = (priority) => {
  const colors = {
    HIGH: 'error',
    MEDIUM: 'warning',
    LOW: 'success'
  }
  return colors[priority] || 'grey'
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  try {
    return format(parseISO(dateStr), 'MMM dd, yyyy')
  } catch {
    return dateStr
  }
}

const isOverdue = (item) => {
  if (!item.planned_ship_date || item.status === 'COMPLETED') return false
  const dueDate = parseISO(item.planned_ship_date)
  return isAfter(startOfDay(new Date()), dueDate)
}

const onRowClick = (event, { item }) => {
  openDetailDrawer(item)
}

const openDetailDrawer = (workOrder) => {
  selectedWorkOrder.value = workOrder
  detailDrawerOpen.value = true
}

const openCreateDialog = () => {
  editingWorkOrder.value = null
  formData.value = {
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
  formDialog.value = true
}

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

const saveWorkOrder = async () => {
  const { valid } = await formRef.value.validate()
  if (!valid) return

  saving.value = true
  try {
    // Prepare data, removing empty date strings
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

const updateStatus = async (workOrder, newStatus) => {
  try {
    await api.updateWorkOrder(workOrder.work_order_id, { status: newStatus })
    notificationStore.showSuccess(`Work order status updated to ${formatStatus(newStatus)}`)
    await loadWorkOrders()
  } catch (error) {
    console.error('Error updating status:', error)
    notificationStore.showError('Failed to update status')
  }
}

const confirmDelete = (workOrder) => {
  workOrderToDelete.value = workOrder
  deleteDialog.value = true
}

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

// Lifecycle
onMounted(() => {
  loadWorkOrders()
})
</script>

<style scoped>
.v-data-table :deep(tbody tr) {
  cursor: pointer;
}

.v-data-table :deep(tbody tr:hover) {
  background-color: rgba(var(--v-theme-primary), 0.04) !important;
}
</style>
