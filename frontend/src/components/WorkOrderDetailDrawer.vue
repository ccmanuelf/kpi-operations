<template>
  <v-navigation-drawer
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    location="right"
    temporary
    width="550"
  >
    <template v-if="workOrder">
      <!-- Header -->
      <v-card flat class="rounded-0">
        <v-card-title class="d-flex justify-space-between align-center py-4 px-6 bg-primary">
          <div class="text-white">
            <div class="text-h6 font-weight-bold">{{ workOrder.work_order_id }}</div>
            <div class="text-body-2 text-white-darken-1">{{ workOrder.style_model }}</div>
          </div>
          <v-btn
            icon
            variant="text"
            color="white"
            @click="$emit('update:modelValue', false)"
          >
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
      </v-card>

      <!-- Status Bar -->
      <div class="px-6 py-3 d-flex align-center justify-space-between bg-surface-light">
        <WorkOrderStatusChip
          :work-order-id="workOrder.work_order_id"
          :status="workOrder.status"
          @transitioned="onStatusTransitioned"
        />
        <v-chip
          v-if="workOrder.priority"
          :color="getPriorityColor(workOrder.priority)"
          variant="outlined"
          size="small"
        >
          {{ workOrder.priority }} Priority
        </v-chip>
      </div>

      <v-divider />

      <v-card-text class="pa-0">
        <!-- Progress Section -->
        <div class="px-6 py-4">
          <div class="text-subtitle-2 font-weight-bold mb-3">Production Progress</div>

          <div class="d-flex justify-center mb-4">
            <v-progress-circular
              :model-value="progressPercent"
              :size="120"
              :width="12"
              :color="getProgressColor"
            >
              <div class="text-center">
                <div class="text-h5 font-weight-bold">{{ progressPercent.toFixed(0) }}%</div>
                <div class="text-caption text-medium-emphasis">Complete</div>
              </div>
            </v-progress-circular>
          </div>

          <v-row dense>
            <v-col cols="4" class="text-center">
              <div class="text-h6 font-weight-bold">{{ workOrder.planned_quantity }}</div>
              <div class="text-caption text-medium-emphasis">Planned</div>
            </v-col>
            <v-col cols="4" class="text-center">
              <div class="text-h6 font-weight-bold text-success">{{ workOrder.actual_quantity }}</div>
              <div class="text-caption text-medium-emphasis">Produced</div>
            </v-col>
            <v-col cols="4" class="text-center">
              <div class="text-h6 font-weight-bold text-warning">{{ remaining }}</div>
              <div class="text-caption text-medium-emphasis">Remaining</div>
            </v-col>
          </v-row>
        </div>

        <v-divider />

        <!-- Details Section -->
        <div class="px-6 py-4">
          <div class="text-subtitle-2 font-weight-bold mb-3">Order Details</div>

          <v-list density="compact" class="bg-transparent pa-0">
            <v-list-item>
              <template v-slot:prepend>
                <v-icon size="small" class="mr-2">mdi-calendar</v-icon>
              </template>
              <v-list-item-title class="text-body-2">Planned Start</v-list-item-title>
              <template v-slot:append>
                <span class="text-body-2">{{ formatDate(workOrder.planned_start_date) || 'Not set' }}</span>
              </template>
            </v-list-item>

            <v-list-item>
              <template v-slot:prepend>
                <v-icon size="small" class="mr-2">mdi-calendar-start</v-icon>
              </template>
              <v-list-item-title class="text-body-2">Actual Start</v-list-item-title>
              <template v-slot:append>
                <span class="text-body-2">{{ formatDate(workOrder.actual_start_date) || 'Not started' }}</span>
              </template>
            </v-list-item>

            <v-list-item>
              <template v-slot:prepend>
                <v-icon size="small" class="mr-2" :color="isOverdue ? 'error' : ''">mdi-truck-delivery</v-icon>
              </template>
              <v-list-item-title class="text-body-2">Ship Date</v-list-item-title>
              <template v-slot:append>
                <span class="text-body-2" :class="{ 'text-error font-weight-bold': isOverdue }">
                  {{ formatDate(workOrder.planned_ship_date) || 'Not set' }}
                  <v-icon v-if="isOverdue" color="error" size="x-small" class="ml-1">mdi-alert</v-icon>
                </span>
              </template>
            </v-list-item>

            <v-list-item v-if="workOrder.customer_po_number">
              <template v-slot:prepend>
                <v-icon size="small" class="mr-2">mdi-file-document</v-icon>
              </template>
              <v-list-item-title class="text-body-2">Customer PO</v-list-item-title>
              <template v-slot:append>
                <span class="text-body-2 font-weight-medium">{{ workOrder.customer_po_number }}</span>
              </template>
            </v-list-item>

            <v-list-item v-if="workOrder.ideal_cycle_time">
              <template v-slot:prepend>
                <v-icon size="small" class="mr-2">mdi-timer</v-icon>
              </template>
              <v-list-item-title class="text-body-2">Ideal Cycle Time</v-list-item-title>
              <template v-slot:append>
                <span class="text-body-2">{{ workOrder.ideal_cycle_time }} hrs</span>
              </template>
            </v-list-item>

            <v-list-item v-if="workOrder.total_run_time_hours">
              <template v-slot:prepend>
                <v-icon size="small" class="mr-2">mdi-clock-outline</v-icon>
              </template>
              <v-list-item-title class="text-body-2">Total Run Time</v-list-item-title>
              <template v-slot:append>
                <span class="text-body-2">{{ workOrder.total_run_time_hours }} hrs</span>
              </template>
            </v-list-item>
          </v-list>
        </div>

        <v-divider />

        <!-- QC Status -->
        <div class="px-6 py-4">
          <div class="text-subtitle-2 font-weight-bold mb-3">Quality Control</div>

          <v-alert
            :type="workOrder.qc_approved ? 'success' : 'warning'"
            variant="tonal"
            density="compact"
          >
            <div class="d-flex align-center">
              <v-icon :icon="workOrder.qc_approved ? 'mdi-check-circle' : 'mdi-clock-outline'" class="mr-2" />
              <span>{{ workOrder.qc_approved ? 'QC Approved' : 'Pending QC Approval' }}</span>
            </div>
            <div v-if="workOrder.qc_approved && workOrder.qc_approved_date" class="text-caption mt-1">
              Approved on {{ formatDate(workOrder.qc_approved_date) }}
            </div>
          </v-alert>

          <v-alert
            v-if="workOrder.status === 'REJECTED'"
            type="error"
            variant="tonal"
            density="compact"
            class="mt-2"
          >
            <div class="font-weight-medium">Rejection Reason:</div>
            <div class="text-body-2">{{ workOrder.rejection_reason || 'No reason provided' }}</div>
          </v-alert>
        </div>

        <v-divider />

        <!-- Notes -->
        <div v-if="workOrder.notes" class="px-6 py-4">
          <div class="text-subtitle-2 font-weight-bold mb-2">Notes</div>
          <div class="text-body-2 text-medium-emphasis">{{ workOrder.notes }}</div>
        </div>

        <v-divider v-if="workOrder.notes" />

        <!-- Job Line Items (RTY) -->
        <div class="px-6 py-4">
          <JobLineItems
            :work-order-id="workOrder.work_order_id"
            :show-rty-button="true"
            @rty-loaded="onRtyLoaded"
          />
        </div>

        <v-divider />

        <!-- Elapsed Time Metrics (Phase 10) -->
        <div class="px-6 py-4">
          <WorkOrderElapsedTime
            :work-order-id="workOrder.work_order_id"
            :show-stages="true"
            :show-dates="true"
          />
        </div>

        <v-divider />

        <!-- Transition History (Phase 10) -->
        <div class="px-6 py-4">
          <WorkOrderTransitionHistory
            ref="transitionHistoryRef"
            :work-order-id="workOrder.work_order_id"
            :max-display="5"
            :show-user="true"
            :show-notes="true"
            :show-elapsed-time="true"
          />
        </div>
      </v-card-text>

      <!-- Actions (inside conditional) -->
      <div v-if="workOrder" class="drawer-actions">
        <v-divider />
        <div class="pa-4 d-flex flex-wrap gap-2">
          <v-btn
            variant="outlined"
            color="primary"
            prepend-icon="mdi-pencil"
            @click="$emit('edit', workOrder)"
          >
            Edit Order
          </v-btn>
          <v-btn
            v-if="workOrder.status === 'ACTIVE'"
            variant="outlined"
            color="warning"
            prepend-icon="mdi-pause"
            @click="updateStatus('ON_HOLD')"
          >
            Put On Hold
          </v-btn>
          <v-btn
            v-if="workOrder.status === 'ON_HOLD'"
            variant="outlined"
            color="success"
            prepend-icon="mdi-play"
            @click="updateStatus('ACTIVE')"
          >
            Resume
          </v-btn>
          <v-btn
            v-if="workOrder.status === 'ACTIVE'"
            variant="flat"
            color="success"
            prepend-icon="mdi-check"
            @click="updateStatus('COMPLETED')"
          >
            Mark Complete
          </v-btn>
        </div>
      </div>
    </template>

    <!-- Empty State -->
    <template v-if="!workOrder">
      <div class="d-flex align-center justify-center" style="height: 100%;">
        <div class="text-center text-medium-emphasis">
          <v-icon size="64" class="mb-4">mdi-clipboard-text-outline</v-icon>
          <div>No work order selected</div>
        </div>
      </div>
    </template>
  </v-navigation-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import { format, parseISO, isAfter, startOfDay } from 'date-fns'
import api from '@/services/api'
import { useNotificationStore } from '@/stores/notificationStore'
import JobLineItems from '@/components/JobLineItems.vue'
import WorkOrderStatusChip from '@/components/workflow/WorkOrderStatusChip.vue'
import WorkOrderTransitionHistory from '@/components/workflow/WorkOrderTransitionHistory.vue'
import WorkOrderElapsedTime from '@/components/workflow/WorkOrderElapsedTime.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  workOrder: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'update', 'edit'])

const notificationStore = useNotificationStore()
const workOrderRty = ref(null)
const transitionHistoryRef = ref(null)

// Handle RTY data loaded from JobLineItems
const onRtyLoaded = (rtyData) => {
  workOrderRty.value = rtyData
}

// Handle status transition from WorkOrderStatusChip
const onStatusTransitioned = (event) => {
  // Refresh transition history
  if (transitionHistoryRef.value) {
    transitionHistoryRef.value.refresh()
  }
  // Emit update to parent to refresh work order list
  emit('update')
}

// Computed
const progressPercent = computed(() => {
  if (!props.workOrder?.planned_quantity) return 0
  return (props.workOrder.actual_quantity / props.workOrder.planned_quantity) * 100
})

const remaining = computed(() => {
  if (!props.workOrder) return 0
  return Math.max(0, props.workOrder.planned_quantity - props.workOrder.actual_quantity)
})

const getProgressColor = computed(() => {
  const progress = progressPercent.value
  if (progress >= 100) return 'success'
  if (progress >= 75) return 'info'
  if (progress >= 50) return 'warning'
  return 'error'
})

const isOverdue = computed(() => {
  if (!props.workOrder?.planned_ship_date || props.workOrder.status === 'COMPLETED') return false
  const dueDate = parseISO(props.workOrder.planned_ship_date)
  return isAfter(startOfDay(new Date()), dueDate)
})

// Methods
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

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    return format(parseISO(dateStr), 'MMM dd, yyyy h:mm a')
  } catch {
    return dateStr
  }
}

const updateStatus = async (newStatus) => {
  try {
    await api.transitionWorkOrder(props.workOrder.work_order_id, newStatus)
    notificationStore.showSuccess(`Work order status updated to ${formatStatus(newStatus)}`)
    // Refresh transition history
    if (transitionHistoryRef.value) {
      transitionHistoryRef.value.refresh()
    }
    emit('update')
    emit('update:modelValue', false)
  } catch (error) {
    console.error('Error updating status:', error)
    // Fallback to direct update if workflow API fails
    try {
      await api.updateWorkOrder(props.workOrder.work_order_id, { status: newStatus })
      notificationStore.showSuccess(`Work order status updated to ${formatStatus(newStatus)}`)
      emit('update')
      emit('update:modelValue', false)
    } catch (fallbackError) {
      notificationStore.showError(error.response?.data?.detail || 'Failed to update status')
    }
  }
}
</script>

<style scoped>
.bg-surface-light {
  background-color: rgba(var(--v-theme-surface-variant), 0.4);
}

.drawer-actions {
  position: sticky;
  bottom: 0;
  background: rgb(var(--v-theme-surface));
}

.gap-2 {
  gap: 8px;
}
</style>
