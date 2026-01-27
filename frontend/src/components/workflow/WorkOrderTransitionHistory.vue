<template>
  <div class="transition-history">
    <!-- Header -->
    <div class="d-flex align-center justify-space-between mb-3">
      <div class="text-subtitle-2 font-weight-bold">
        {{ $t('workflow.transitionHistory') || 'Status History' }}
      </div>
      <v-btn
        v-if="!loading && transitions.length > 0"
        icon
        size="x-small"
        variant="text"
        @click="fetchHistory"
        :aria-label="$t('common.refresh') || 'Refresh'"
      >
        <v-icon size="small">mdi-refresh</v-icon>
      </v-btn>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="d-flex justify-center py-4">
      <v-progress-circular indeterminate size="24" color="primary" />
    </div>

    <!-- Empty state -->
    <v-alert
      v-else-if="transitions.length === 0"
      type="info"
      variant="tonal"
      density="compact"
    >
      {{ $t('workflow.noTransitions') || 'No status changes recorded' }}
    </v-alert>

    <!-- Timeline -->
    <v-timeline
      v-else
      density="compact"
      side="end"
      :truncate-line="compact ? 'both' : undefined"
    >
      <v-timeline-item
        v-for="(transition, index) in displayedTransitions"
        :key="transition.transition_id || index"
        :dot-color="getTransitionColor(transition)"
        :icon="getTransitionIcon(transition)"
        size="small"
        :class="{ 'timeline-item-compact': compact }"
      >
        <!-- Transition content -->
        <div class="timeline-content">
          <!-- Status change -->
          <div class="d-flex align-center flex-wrap gap-1">
            <v-chip
              v-if="transition.from_status"
              :color="getStatusColor(transition.from_status)"
              size="x-small"
              variant="outlined"
            >
              {{ getStatusLabel(transition.from_status) }}
            </v-chip>
            <span v-if="transition.from_status" class="text-caption mx-1">→</span>
            <v-chip
              :color="getStatusColor(transition.to_status)"
              size="x-small"
              variant="flat"
            >
              {{ getStatusLabel(transition.to_status) }}
            </v-chip>
          </div>

          <!-- Metadata -->
          <div class="mt-1">
            <div class="text-caption text-medium-emphasis">
              {{ formatDateTime(transition.transitioned_at) }}
            </div>
            <div v-if="showUser && transition.transitioned_by_name" class="text-caption">
              <v-icon size="x-small" class="mr-1">mdi-account</v-icon>
              {{ transition.transitioned_by_name }}
            </div>
            <div v-if="showElapsedTime && transition.elapsed_from_previous_hours != null" class="text-caption">
              <v-icon size="x-small" class="mr-1">mdi-clock-outline</v-icon>
              {{ formatElapsedTime(transition.elapsed_from_previous_hours) }}
            </div>
          </div>

          <!-- Notes -->
          <div v-if="transition.notes && showNotes" class="mt-1">
            <v-chip size="x-small" variant="tonal" color="grey">
              <v-icon size="x-small" class="mr-1">mdi-note-text</v-icon>
              {{ truncateNotes(transition.notes) }}
              <v-tooltip v-if="transition.notes.length > 50" activator="parent">
                {{ transition.notes }}
              </v-tooltip>
            </v-chip>
          </div>
        </div>
      </v-timeline-item>

      <!-- Show more button -->
      <v-timeline-item
        v-if="hasMore && !showAll"
        dot-color="grey-lighten-1"
        size="x-small"
      >
        <v-btn
          variant="text"
          size="small"
          color="primary"
          @click="showAll = true"
        >
          {{ $t('common.showMore') || 'Show more' }}
          ({{ transitions.length - maxDisplay }})
        </v-btn>
      </v-timeline-item>
    </v-timeline>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format, parseISO, formatDistanceToNow } from 'date-fns'
import { getTransitionHistory } from '@/services/api/workflow'

const props = defineProps({
  workOrderId: {
    type: String,
    required: true
  },
  maxDisplay: {
    type: Number,
    default: 5
  },
  compact: {
    type: Boolean,
    default: false
  },
  showUser: {
    type: Boolean,
    default: true
  },
  showNotes: {
    type: Boolean,
    default: true
  },
  showElapsedTime: {
    type: Boolean,
    default: true
  },
  autoLoad: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['loaded', 'error'])

const { t } = useI18n()

// State
const loading = ref(false)
const transitions = ref([])
const showAll = ref(false)

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
  ACTIVE: { color: 'info', icon: 'mdi-progress-clock', label: 'Active' }
}

// Computed
const hasMore = computed(() => transitions.value.length > props.maxDisplay)

const displayedTransitions = computed(() => {
  if (showAll.value || !hasMore.value) {
    return transitions.value
  }
  return transitions.value.slice(0, props.maxDisplay)
})

// Methods
const getStatusColor = (status) => STATUS_CONFIG[status]?.color || 'grey'
const getStatusLabel = (status) => {
  const key = `workflow.status.${status?.toLowerCase()}`
  const translated = t(key)
  return translated !== key ? translated : (STATUS_CONFIG[status]?.label || status)
}

const getTransitionColor = (transition) => {
  return getStatusColor(transition.to_status)
}

const getTransitionIcon = (transition) => {
  return STATUS_CONFIG[transition.to_status]?.icon || 'mdi-help-circle'
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = parseISO(dateStr)
    const formatted = format(date, 'MMM dd, yyyy h:mm a')
    const relative = formatDistanceToNow(date, { addSuffix: true })
    return `${formatted} (${relative})`
  } catch {
    return dateStr
  }
}

const formatElapsedTime = (hours) => {
  if (hours == null) return ''
  if (hours < 1) {
    const minutes = Math.round(hours * 60)
    return `${minutes} min`
  }
  if (hours < 24) {
    return `${hours.toFixed(1)} hrs`
  }
  const days = (hours / 24).toFixed(1)
  return `${days} days`
}

const truncateNotes = (notes) => {
  if (!notes) return ''
  if (notes.length <= 50) return notes
  return notes.substring(0, 47) + '...'
}

const fetchHistory = async () => {
  loading.value = true
  try {
    const response = await getTransitionHistory(props.workOrderId)
    // Sort by date descending (most recent first)
    transitions.value = (response.data || []).sort((a, b) => {
      const dateA = new Date(a.transitioned_at)
      const dateB = new Date(b.transitioned_at)
      return dateB - dateA
    })
    emit('loaded', transitions.value)
  } catch (error) {
    console.error('Error fetching transition history:', error)
    emit('error', error)
  } finally {
    loading.value = false
  }
}

// Expose refresh method
defineExpose({ refresh: fetchHistory })

// Watch for work order changes
watch(() => props.workOrderId, () => {
  showAll.value = false
  if (props.autoLoad) {
    fetchHistory()
  }
})

// Initialize
onMounted(() => {
  if (props.autoLoad) {
    fetchHistory()
  }
})
</script>

<style scoped>
.transition-history {
  width: 100%;
}

.timeline-content {
  padding-bottom: 8px;
}

.timeline-item-compact .timeline-content {
  padding-bottom: 4px;
}

.gap-1 {
  gap: 4px;
}
</style>
