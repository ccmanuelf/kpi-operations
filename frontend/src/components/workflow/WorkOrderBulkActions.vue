<template>
  <v-card v-if="selectedCount > 0" class="bulk-actions-bar pa-3 mb-4" variant="tonal" color="primary">
    <div class="d-flex align-center justify-space-between flex-wrap ga-2">
      <!-- Selection Info -->
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-checkbox-marked-outline</v-icon>
        <span class="text-body-1 font-weight-medium">
          {{ selectedCount }} {{ selectedCount === 1 ? 'order' : 'orders' }} selected
        </span>
        <v-btn
          variant="text"
          size="small"
          class="ml-2"
          @click="$emit('clear-selection')"
        >
          Clear
        </v-btn>
      </div>

      <!-- Actions -->
      <div class="d-flex align-center ga-2">
        <!-- Bulk Transition Menu -->
        <v-menu>
          <template v-slot:activator="{ props }">
            <v-btn
              v-bind="props"
              variant="flat"
              color="primary"
              prepend-icon="mdi-swap-horizontal"
              :disabled="loading"
            >
              Change Status
              <v-icon size="small" class="ml-1">mdi-chevron-down</v-icon>
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-subheader>Transition to:</v-list-subheader>
            <v-list-item
              v-for="status in availableTransitions"
              :key="status.value"
              :prepend-icon="status.icon"
              @click="openBulkTransitionDialog(status.value)"
            >
              <v-list-item-title>{{ status.title }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>

        <!-- More Actions -->
        <v-menu>
          <template v-slot:activator="{ props }">
            <v-btn
              v-bind="props"
              variant="outlined"
              :disabled="loading"
            >
              <v-icon>mdi-dots-vertical</v-icon>
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item
              prepend-icon="mdi-export"
              @click="$emit('export-selected')"
            >
              <v-list-item-title>Export Selected</v-list-item-title>
            </v-list-item>
            <v-divider />
            <v-list-item
              prepend-icon="mdi-delete-outline"
              base-color="error"
              @click="$emit('delete-selected')"
            >
              <v-list-item-title>Delete Selected</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </div>
    </div>

    <!-- Bulk Transition Dialog -->
    <v-dialog v-model="transitionDialog" max-width="500" persistent>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" :color="getStatusColor(targetStatus)">
            {{ getStatusIcon(targetStatus) }}
          </v-icon>
          Bulk Status Change
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            You are about to change {{ selectedCount }} work orders to
            <strong>{{ formatStatus(targetStatus) }}</strong> status.
          </v-alert>

          <!-- Common Note -->
          <v-textarea
            v-model="transitionNote"
            label="Note (optional)"
            placeholder="Add a note that will be applied to all transitions..."
            variant="outlined"
            rows="3"
            hide-details
          />

          <!-- Warnings -->
          <v-alert
            v-if="incompatibleOrders.length > 0"
            type="warning"
            variant="tonal"
            density="compact"
            class="mt-4"
          >
            <strong>{{ incompatibleOrders.length }}</strong> orders cannot transition to this status and will be skipped:
            <ul class="mt-1 mb-0">
              <li v-for="wo in incompatibleOrders.slice(0, 3)" :key="wo.work_order_id">
                {{ wo.work_order_id }} (current: {{ formatStatus(wo.status) }})
              </li>
              <li v-if="incompatibleOrders.length > 3">
                ...and {{ incompatibleOrders.length - 3 }} more
              </li>
            </ul>
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="transitionDialog = false" :disabled="loading">
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            :loading="loading"
            :disabled="compatibleOrders.length === 0"
            @click="executeBulkTransition"
          >
            Change {{ compatibleOrders.length }} Orders
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { bulkTransitionWorkOrders } from '@/services/api/workflow'
import { useNotificationStore } from '@/stores/notificationStore'

const props = defineProps({
  selectedOrders: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['clear-selection', 'transitioned', 'export-selected', 'delete-selected'])

const notificationStore = useNotificationStore()

// State
const loading = ref(false)
const transitionDialog = ref(false)
const targetStatus = ref(null)
const transitionNote = ref('')

// Available status transitions
const availableTransitions = [
  { value: 'RECEIVED', title: 'Received', icon: 'mdi-inbox' },
  { value: 'DISPATCHED', title: 'Dispatched', icon: 'mdi-send' },
  { value: 'IN_WIP', title: 'In WIP', icon: 'mdi-factory' },
  { value: 'COMPLETED', title: 'Completed', icon: 'mdi-check-circle' },
  { value: 'ON_HOLD', title: 'On Hold', icon: 'mdi-pause-circle' },
  { value: 'ACTIVE', title: 'Active', icon: 'mdi-play-circle' }
]

// Computed
const selectedCount = computed(() => props.selectedOrders.length)

// Valid transitions per status (simplified rules)
const validTransitions = {
  'RECEIVED': ['DISPATCHED', 'ON_HOLD', 'CANCELLED'],
  'DISPATCHED': ['IN_WIP', 'ON_HOLD', 'RECEIVED'],
  'IN_WIP': ['COMPLETED', 'ON_HOLD', 'DISPATCHED'],
  'COMPLETED': ['SHIPPED', 'IN_WIP'],
  'SHIPPED': ['CLOSED'],
  'CLOSED': [],
  'ON_HOLD': ['ACTIVE', 'RECEIVED', 'DISPATCHED', 'IN_WIP'],
  'ACTIVE': ['COMPLETED', 'ON_HOLD'],
  'CANCELLED': []
}

const compatibleOrders = computed(() => {
  if (!targetStatus.value) return props.selectedOrders
  return props.selectedOrders.filter(wo => {
    const allowed = validTransitions[wo.status] || []
    return allowed.includes(targetStatus.value) || wo.status === targetStatus.value
  })
})

const incompatibleOrders = computed(() => {
  if (!targetStatus.value) return []
  return props.selectedOrders.filter(wo => {
    const allowed = validTransitions[wo.status] || []
    return !allowed.includes(targetStatus.value) && wo.status !== targetStatus.value
  })
})

// Methods
const getStatusColor = (status) => {
  const colors = {
    RECEIVED: 'blue-grey',
    DISPATCHED: 'info',
    IN_WIP: 'indigo',
    COMPLETED: 'success',
    SHIPPED: 'purple',
    CLOSED: 'grey',
    ON_HOLD: 'warning',
    ACTIVE: 'info',
    REJECTED: 'error',
    CANCELLED: 'grey'
  }
  return colors[status] || 'grey'
}

const getStatusIcon = (status) => {
  const icons = {
    RECEIVED: 'mdi-inbox',
    DISPATCHED: 'mdi-send',
    IN_WIP: 'mdi-factory',
    COMPLETED: 'mdi-check-circle',
    SHIPPED: 'mdi-truck-delivery',
    CLOSED: 'mdi-archive',
    ON_HOLD: 'mdi-pause-circle',
    ACTIVE: 'mdi-play-circle',
    REJECTED: 'mdi-close-circle',
    CANCELLED: 'mdi-cancel'
  }
  return icons[status] || 'mdi-help-circle'
}

const formatStatus = (status) => {
  const labels = {
    RECEIVED: 'Received',
    DISPATCHED: 'Dispatched',
    IN_WIP: 'In WIP',
    COMPLETED: 'Completed',
    SHIPPED: 'Shipped',
    CLOSED: 'Closed',
    ON_HOLD: 'On Hold',
    ACTIVE: 'Active',
    REJECTED: 'Rejected',
    CANCELLED: 'Cancelled'
  }
  return labels[status] || status
}

const openBulkTransitionDialog = (status) => {
  targetStatus.value = status
  transitionNote.value = ''
  transitionDialog.value = true
}

const executeBulkTransition = async () => {
  if (compatibleOrders.value.length === 0) return

  loading.value = true
  try {
    const workOrderIds = compatibleOrders.value.map(wo => wo.work_order_id)
    const result = await bulkTransitionWorkOrders(
      workOrderIds,
      targetStatus.value,
      transitionNote.value || undefined
    )

    const data = result.data
    if (data.successful > 0) {
      notificationStore.showSuccess(
        `Successfully transitioned ${data.successful} work orders to ${formatStatus(targetStatus.value)}`
      )
    }
    if (data.failed > 0) {
      notificationStore.showWarning(
        `${data.failed} work orders could not be transitioned`
      )
    }

    transitionDialog.value = false
    emit('transitioned', data)
  } catch (error) {
    console.error('Error in bulk transition:', error)
    notificationStore.showError(
      error.response?.data?.detail || 'Failed to perform bulk transition'
    )
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.bulk-actions-bar {
  position: sticky;
  top: 64px;
  z-index: 10;
}
</style>
