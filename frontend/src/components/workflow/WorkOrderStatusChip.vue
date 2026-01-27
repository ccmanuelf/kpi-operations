<template>
  <div class="work-order-status-chip">
    <v-menu
      v-if="allowTransitions && allowedStatuses.length > 0"
      :disabled="loading || disabled"
    >
      <template v-slot:activator="{ props: menuProps }">
        <v-chip
          v-bind="{ ...menuProps, ...$attrs }"
          :color="statusColor"
          :variant="variant"
          :size="size"
          :class="{ 'cursor-pointer': !disabled }"
          :prepend-icon="loading ? undefined : statusIcon"
        >
          <v-progress-circular
            v-if="loading"
            :size="14"
            :width="2"
            indeterminate
            class="mr-1"
          />
          {{ statusLabel }}
          <v-icon v-if="!disabled && !loading" size="small" class="ml-1">
            mdi-chevron-down
          </v-icon>
        </v-chip>
      </template>

      <v-list density="compact" min-width="180">
        <v-list-subheader>{{ $t('workflow.changeStatus') || 'Change Status' }}</v-list-subheader>
        <v-list-item
          v-for="status in allowedStatuses"
          :key="status"
          :disabled="status === currentStatus"
          @click="handleTransition(status)"
        >
          <template v-slot:prepend>
            <v-icon :color="getStatusColor(status)" size="small">
              {{ getStatusIcon(status) }}
            </v-icon>
          </template>
          <v-list-item-title>{{ getStatusLabel(status) }}</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-menu>

    <!-- Non-interactive chip -->
    <v-chip
      v-else
      :color="statusColor"
      :variant="variant"
      :size="size"
      :prepend-icon="statusIcon"
      v-bind="$attrs"
    >
      {{ statusLabel }}
    </v-chip>

    <!-- Transition notes dialog -->
    <v-dialog v-model="notesDialog" max-width="400" persistent>
      <v-card>
        <v-card-title class="text-h6">
          {{ $t('workflow.transitionNotes') || 'Transition Notes' }}
        </v-card-title>
        <v-card-text>
          <p class="text-body-2 mb-3">
            {{ $t('workflow.transitionPrompt') || 'Transitioning to' }}:
            <v-chip :color="getStatusColor(pendingStatus)" size="small" class="ml-1">
              {{ getStatusLabel(pendingStatus) }}
            </v-chip>
          </p>
          <v-textarea
            v-model="transitionNotes"
            :label="$t('workflow.notes') || 'Notes (optional)'"
            variant="outlined"
            rows="3"
            hide-details
            autofocus
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="cancelTransition">
            {{ $t('common.cancel') || 'Cancel' }}
          </v-btn>
          <v-btn
            color="primary"
            variant="elevated"
            :loading="transitioning"
            @click="confirmTransition"
          >
            {{ $t('workflow.confirm') || 'Confirm' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getAllowedTransitions, transitionWorkOrder } from '@/services/api/workflow'
import { useNotificationStore } from '@/stores/notificationStore'

const props = defineProps({
  workOrderId: {
    type: String,
    required: true
  },
  status: {
    type: String,
    required: true
  },
  allowTransitions: {
    type: Boolean,
    default: true
  },
  requireNotes: {
    type: Boolean,
    default: false
  },
  variant: {
    type: String,
    default: 'flat'
  },
  size: {
    type: String,
    default: 'default'
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['transitioned', 'error'])

const { t } = useI18n()
const notificationStore = useNotificationStore()

// State
const loading = ref(false)
const transitioning = ref(false)
const allowedStatuses = ref([])
const currentStatus = ref(props.status)
const notesDialog = ref(false)
const pendingStatus = ref(null)
const transitionNotes = ref('')

// Status configuration
const STATUS_CONFIG = {
  RECEIVED: { color: 'blue-grey', icon: 'mdi-inbox', label: 'Received' },
  DISPATCHED: { color: 'blue', icon: 'mdi-send', label: 'Dispatched' },
  IN_WIP: { color: 'info', icon: 'mdi-progress-clock', label: 'In WIP' },
  ON_HOLD: { color: 'warning', icon: 'mdi-pause-circle', label: 'On Hold' },
  COMPLETED: { color: 'success', icon: 'mdi-check-circle', label: 'Completed' },
  SHIPPED: { color: 'purple', icon: 'mdi-truck-delivery', label: 'Shipped' },
  CLOSED: { color: 'grey', icon: 'mdi-archive', label: 'Closed' },
  CANCELLED: { color: 'error', icon: 'mdi-cancel', label: 'Cancelled' },
  REJECTED: { color: 'error', icon: 'mdi-alert-circle', label: 'Rejected' },
  // Legacy statuses
  ACTIVE: { color: 'info', icon: 'mdi-progress-clock', label: 'Active' }
}

// Computed
const statusColor = computed(() => getStatusColor(currentStatus.value))
const statusIcon = computed(() => getStatusIcon(currentStatus.value))
const statusLabel = computed(() => getStatusLabel(currentStatus.value))

// Methods
const getStatusColor = (status) => STATUS_CONFIG[status]?.color || 'grey'
const getStatusIcon = (status) => STATUS_CONFIG[status]?.icon || 'mdi-help-circle'
const getStatusLabel = (status) => {
  const key = `workflow.status.${status?.toLowerCase()}`
  const translated = t(key)
  // Return translated if different from key, otherwise use config or status
  return translated !== key ? translated : (STATUS_CONFIG[status]?.label || status)
}

const fetchAllowedTransitions = async () => {
  if (!props.allowTransitions || props.disabled) return

  loading.value = true
  try {
    const response = await getAllowedTransitions(props.workOrderId)
    allowedStatuses.value = response.data?.allowed_transitions || []
  } catch (error) {
    console.error('Error fetching allowed transitions:', error)
    allowedStatuses.value = []
  } finally {
    loading.value = false
  }
}

const handleTransition = (toStatus) => {
  if (toStatus === currentStatus.value) return

  pendingStatus.value = toStatus
  transitionNotes.value = ''

  if (props.requireNotes) {
    notesDialog.value = true
  } else {
    confirmTransition()
  }
}

const confirmTransition = async () => {
  if (!pendingStatus.value) return

  transitioning.value = true
  try {
    const response = await transitionWorkOrder(
      props.workOrderId,
      pendingStatus.value,
      transitionNotes.value || null
    )

    currentStatus.value = pendingStatus.value
    notificationStore.showSuccess(
      t('workflow.transitionSuccess') || `Status changed to ${getStatusLabel(pendingStatus.value)}`
    )
    emit('transitioned', {
      workOrderId: props.workOrderId,
      fromStatus: props.status,
      toStatus: pendingStatus.value,
      response: response.data
    })

    // Refresh allowed transitions
    await fetchAllowedTransitions()
  } catch (error) {
    console.error('Transition error:', error)
    const message = error.response?.data?.detail || t('workflow.transitionError') || 'Failed to change status'
    notificationStore.showError(message)
    emit('error', { error, pendingStatus: pendingStatus.value })
  } finally {
    transitioning.value = false
    notesDialog.value = false
    pendingStatus.value = null
    transitionNotes.value = ''
  }
}

const cancelTransition = () => {
  notesDialog.value = false
  pendingStatus.value = null
  transitionNotes.value = ''
}

// Watch for external status changes
watch(() => props.status, (newStatus) => {
  currentStatus.value = newStatus
  fetchAllowedTransitions()
})

// Initialize
onMounted(() => {
  fetchAllowedTransitions()
})
</script>

<style scoped>
.work-order-status-chip {
  display: inline-flex;
}

.cursor-pointer {
  cursor: pointer;
}
</style>
