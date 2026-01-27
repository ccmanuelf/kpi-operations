<template>
  <div class="elapsed-time-metrics">
    <!-- Header -->
    <div class="d-flex align-center justify-space-between mb-3">
      <div class="text-subtitle-2 font-weight-bold">
        {{ $t('workflow.elapsedTime') || 'Elapsed Time' }}
      </div>
      <v-chip
        v-if="metrics?.lifecycle?.is_overdue"
        color="error"
        size="x-small"
        variant="flat"
      >
        <v-icon size="x-small" class="mr-1">mdi-alert</v-icon>
        {{ $t('workflow.overdue') || 'Overdue' }}
      </v-chip>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="d-flex justify-center py-4">
      <v-progress-circular indeterminate size="24" color="primary" />
    </div>

    <!-- Error state -->
    <v-alert
      v-else-if="error"
      type="error"
      variant="tonal"
      density="compact"
    >
      {{ $t('common.loadError') || 'Failed to load data' }}
    </v-alert>

    <!-- Metrics display -->
    <template v-else-if="metrics">
      <!-- Main lifecycle metrics -->
      <v-row dense class="mb-3">
        <v-col cols="6">
          <v-card variant="tonal" :color="getLifecycleColor" class="pa-3">
            <div class="text-h5 font-weight-bold">
              {{ formatDays(metrics.lifecycle?.total_days) }}
            </div>
            <div class="text-caption text-medium-emphasis">
              {{ $t('workflow.totalTime') || 'Total Time' }}
            </div>
          </v-card>
        </v-col>
        <v-col cols="6">
          <v-card variant="tonal" :color="getExpectedColor" class="pa-3">
            <div class="text-h5 font-weight-bold">
              {{ formatDaysRemaining(metrics.lifecycle?.days_early_or_late) }}
            </div>
            <div class="text-caption text-medium-emphasis">
              {{ getDaysLabel }}
            </div>
          </v-card>
        </v-col>
      </v-row>

      <!-- Stage breakdown -->
      <div v-if="showStages" class="mb-3">
        <div class="text-caption font-weight-medium mb-2">
          {{ $t('workflow.stageBreakdown') || 'Stage Breakdown' }}
        </div>

        <v-list density="compact" class="pa-0 bg-transparent">
          <!-- Lead time (received to dispatch) -->
          <v-list-item v-if="metrics.stages?.lead_time_hours != null" class="px-0">
            <template v-slot:prepend>
              <v-icon color="blue-grey" size="small" class="mr-2">mdi-inbox</v-icon>
            </template>
            <v-list-item-title class="text-body-2">
              {{ $t('workflow.leadTime') || 'Lead Time' }}
            </v-list-item-title>
            <v-list-item-subtitle class="text-caption">
              {{ $t('workflow.receivedToDispatch') || 'Received → Dispatch' }}
            </v-list-item-subtitle>
            <template v-slot:append>
              <span class="text-body-2 font-weight-medium">
                {{ formatHours(metrics.stages.lead_time_hours) }}
              </span>
            </template>
          </v-list-item>

          <!-- Processing time (dispatch to completion) -->
          <v-list-item v-if="metrics.stages?.processing_time_hours != null" class="px-0">
            <template v-slot:prepend>
              <v-icon color="info" size="small" class="mr-2">mdi-progress-clock</v-icon>
            </template>
            <v-list-item-title class="text-body-2">
              {{ $t('workflow.processingTime') || 'Processing Time' }}
            </v-list-item-title>
            <v-list-item-subtitle class="text-caption">
              {{ $t('workflow.dispatchToComplete') || 'Dispatch → Complete' }}
            </v-list-item-subtitle>
            <template v-slot:append>
              <span class="text-body-2 font-weight-medium">
                {{ formatHours(metrics.stages.processing_time_hours) }}
              </span>
            </template>
          </v-list-item>

          <!-- Shipping time -->
          <v-list-item v-if="metrics.stages?.shipping_time_hours != null" class="px-0">
            <template v-slot:prepend>
              <v-icon color="purple" size="small" class="mr-2">mdi-truck-delivery</v-icon>
            </template>
            <v-list-item-title class="text-body-2">
              {{ $t('workflow.shippingTime') || 'Shipping Time' }}
            </v-list-item-title>
            <v-list-item-subtitle class="text-caption">
              {{ $t('workflow.completeToShip') || 'Complete → Ship' }}
            </v-list-item-subtitle>
            <template v-slot:append>
              <span class="text-body-2 font-weight-medium">
                {{ formatHours(metrics.stages.shipping_time_hours) }}
              </span>
            </template>
          </v-list-item>
        </v-list>
      </div>

      <!-- Key dates -->
      <div v-if="showDates">
        <div class="text-caption font-weight-medium mb-2">
          {{ $t('workflow.keyDates') || 'Key Dates' }}
        </div>

        <v-list density="compact" class="pa-0 bg-transparent">
          <v-list-item v-if="metrics.dates?.received_date" class="px-0">
            <template v-slot:prepend>
              <v-icon size="small" class="mr-2">mdi-calendar-import</v-icon>
            </template>
            <v-list-item-title class="text-body-2">
              {{ $t('workflow.received') || 'Received' }}
            </v-list-item-title>
            <template v-slot:append>
              <span class="text-body-2">{{ formatDate(metrics.dates.received_date) }}</span>
            </template>
          </v-list-item>

          <v-list-item v-if="metrics.dates?.dispatch_date" class="px-0">
            <template v-slot:prepend>
              <v-icon size="small" class="mr-2">mdi-send</v-icon>
            </template>
            <v-list-item-title class="text-body-2">
              {{ $t('workflow.dispatched') || 'Dispatched' }}
            </v-list-item-title>
            <template v-slot:append>
              <span class="text-body-2">{{ formatDate(metrics.dates.dispatch_date) }}</span>
            </template>
          </v-list-item>

          <v-list-item v-if="metrics.forecast?.expected_date" class="px-0">
            <template v-slot:prepend>
              <v-icon
                size="small"
                class="mr-2"
                :color="metrics.lifecycle?.is_overdue ? 'error' : ''"
              >
                mdi-calendar-clock
              </v-icon>
            </template>
            <v-list-item-title class="text-body-2">
              {{ $t('workflow.expected') || 'Expected' }}
            </v-list-item-title>
            <template v-slot:append>
              <span
                class="text-body-2"
                :class="{ 'text-error font-weight-bold': metrics.lifecycle?.is_overdue }"
              >
                {{ formatDate(metrics.forecast.expected_date) }}
              </span>
            </template>
          </v-list-item>

          <v-list-item v-if="metrics.dates?.closure_date" class="px-0">
            <template v-slot:prepend>
              <v-icon size="small" class="mr-2" color="success">mdi-check-circle</v-icon>
            </template>
            <v-list-item-title class="text-body-2">
              {{ $t('workflow.closed') || 'Closed' }}
            </v-list-item-title>
            <template v-slot:append>
              <span class="text-body-2 text-success">{{ formatDate(metrics.dates.closure_date) }}</span>
            </template>
          </v-list-item>
        </v-list>
      </div>
    </template>

    <!-- No data state -->
    <v-alert
      v-else
      type="info"
      variant="tonal"
      density="compact"
    >
      {{ $t('workflow.noTimeData') || 'No elapsed time data available' }}
    </v-alert>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format, parseISO } from 'date-fns'
import { getWorkOrderElapsedTime } from '@/services/api/workflow'

const props = defineProps({
  workOrderId: {
    type: String,
    required: true
  },
  showStages: {
    type: Boolean,
    default: true
  },
  showDates: {
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
const error = ref(false)
const metrics = ref(null)

// Computed
const getLifecycleColor = computed(() => {
  if (!metrics.value?.lifecycle) return 'grey'
  if (metrics.value.lifecycle.is_overdue) return 'error'
  const days = metrics.value.lifecycle.total_days
  if (days > 14) return 'warning'
  return 'success'
})

const getExpectedColor = computed(() => {
  if (!metrics.value?.lifecycle) return 'grey'
  const diff = metrics.value.lifecycle.days_early_or_late
  if (diff == null) return 'grey'
  if (diff < 0) return 'error'  // Late
  if (diff === 0) return 'warning'  // On time
  return 'success'  // Early
})

const getDaysLabel = computed(() => {
  if (!metrics.value?.lifecycle) return ''
  const diff = metrics.value.lifecycle.days_early_or_late
  if (diff == null) return t('workflow.noExpectedDate') || 'No target'
  if (diff < 0) return t('workflow.daysLate') || 'Days Late'
  if (diff === 0) return t('workflow.onTime') || 'On Time'
  return t('workflow.daysEarly') || 'Days Early'
})

// Methods
const formatDays = (days) => {
  if (days == null) return '-'
  if (days < 1) {
    const hours = Math.round(days * 24)
    return `${hours}h`
  }
  return `${days.toFixed(1)}d`
}

const formatDaysRemaining = (days) => {
  if (days == null) return '-'
  return Math.abs(days).toString()
}

const formatHours = (hours) => {
  if (hours == null) return '-'
  if (hours < 1) {
    const minutes = Math.round(hours * 60)
    return `${minutes}m`
  }
  if (hours < 24) {
    return `${hours.toFixed(1)}h`
  }
  const days = (hours / 24).toFixed(1)
  return `${days}d`
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  try {
    return format(parseISO(dateStr), 'MMM dd, yyyy')
  } catch {
    return dateStr
  }
}

const fetchMetrics = async () => {
  loading.value = true
  error.value = false
  try {
    const response = await getWorkOrderElapsedTime(props.workOrderId)
    metrics.value = response.data
    emit('loaded', metrics.value)
  } catch (err) {
    console.error('Error fetching elapsed time metrics:', err)
    error.value = true
    emit('error', err)
  } finally {
    loading.value = false
  }
}

// Expose refresh method
defineExpose({ refresh: fetchMetrics })

// Watch for work order changes
watch(() => props.workOrderId, () => {
  if (props.autoLoad) {
    fetchMetrics()
  }
})

// Initialize
onMounted(() => {
  if (props.autoLoad) {
    fetchMetrics()
  }
})
</script>

<style scoped>
.elapsed-time-metrics {
  width: 100%;
}
</style>
