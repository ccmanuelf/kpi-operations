<template>
  <v-alert
    v-if="shouldShow"
    :type="alertType"
    variant="elevated"
    prominent
    :closable="closable"
    class="mb-4"
    @click:close="dismissed = true"
  >
    <template v-slot:prepend>
      <v-icon size="large" :icon="alertIcon" />
    </template>

    <div class="d-flex flex-column flex-sm-row align-sm-center justify-space-between">
      <div>
        <div class="text-h6 font-weight-bold">{{ alertTitle }}</div>
        <div class="mt-1">
          Current rate: <strong>{{ absenteeismRate }}%</strong>
          (Threshold: {{ threshold }}%)
        </div>
        <div class="text-caption text-grey mt-1">
          {{ alertDescription }}
        </div>
      </div>

      <div class="mt-3 mt-sm-0 d-flex flex-column flex-sm-row ga-2">
        <v-btn
          :variant="alertType === 'error' ? 'flat' : 'outlined'"
          :color="alertType === 'error' ? 'white' : undefined"
          size="small"
          prepend-icon="mdi-chart-line"
          @click="$emit('viewDetails')"
        >
          View Details
        </v-btn>
        <v-btn
          v-if="showScheduleAction"
          variant="outlined"
          :color="alertType === 'error' ? 'white' : undefined"
          size="small"
          prepend-icon="mdi-calendar-clock"
          @click="$emit('scheduleReview')"
        >
          Schedule Review
        </v-btn>
      </div>
    </div>

    <!-- Additional Details (expandable) -->
    <v-expand-transition>
      <div v-if="expanded" class="mt-4 pa-3 bg-white rounded">
        <v-row dense>
          <v-col cols="6" sm="3">
            <div class="text-caption text-grey">Scheduled Hours</div>
            <div class="font-weight-bold">{{ scheduledHours.toLocaleString() }}h</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption text-grey">Absent Hours</div>
            <div class="font-weight-bold text-error">{{ absentHours.toLocaleString() }}h</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption text-grey">Affected Employees</div>
            <div class="font-weight-bold">{{ affectedEmployees }}</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption text-grey">Trend</div>
            <div class="d-flex align-center">
              <v-icon
                :color="trendDirection === 'up' ? 'error' : trendDirection === 'down' ? 'success' : 'grey'"
                :icon="trendIcon"
                size="18"
                class="mr-1"
              />
              <span :class="trendTextColor">{{ trendValue }}%</span>
            </div>
          </v-col>
        </v-row>

        <!-- Quick Actions -->
        <v-divider class="my-3" />
        <div class="text-subtitle-2 mb-2">Recommended Actions</div>
        <v-chip-group>
          <v-chip
            v-for="action in recommendedActions"
            :key="action.id"
            size="small"
            variant="outlined"
            :prepend-icon="action.icon"
            @click="$emit('takeAction', action.id)"
          >
            {{ action.label }}
          </v-chip>
        </v-chip-group>
      </div>
    </v-expand-transition>

    <!-- Expand/Collapse Toggle -->
    <div class="text-center mt-2">
      <v-btn
        variant="text"
        size="x-small"
        :color="alertType === 'error' ? 'white' : undefined"
        @click="expanded = !expanded"
      >
        {{ expanded ? 'Show Less' : 'Show More' }}
        <v-icon :icon="expanded ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
      </v-btn>
    </div>
  </v-alert>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

// Props
const props = withDefaults(defineProps<{
  threshold?: number
  autoFetch?: boolean
  clientId?: string
  startDate?: string
  endDate?: string
  closable?: boolean
}>(), {
  threshold: 5,
  autoFetch: true,
  closable: true
})

// Emits
defineEmits(['viewDetails', 'scheduleReview', 'takeAction'])

// State
const absenteeismRate = ref(0)
const scheduledHours = ref(0)
const absentHours = ref(0)
const affectedEmployees = ref(0)
const trendValue = ref(0)
const trendDirection = ref<'up' | 'down' | 'stable'>('stable')
const dismissed = ref(false)
const expanded = ref(false)

// Computed
const shouldShow = computed(() => {
  return !dismissed.value && absenteeismRate.value > props.threshold
})

const alertType = computed((): 'warning' | 'error' | 'info' => {
  if (absenteeismRate.value > props.threshold * 2) return 'error'
  if (absenteeismRate.value > props.threshold) return 'warning'
  return 'info'
})

const alertIcon = computed(() => {
  if (alertType.value === 'error') return 'mdi-alert-octagon'
  if (alertType.value === 'warning') return 'mdi-alert'
  return 'mdi-information'
})

const alertTitle = computed(() => {
  if (alertType.value === 'error') return 'Critical Absenteeism Alert'
  if (alertType.value === 'warning') return 'High Absenteeism Alert'
  return 'Absenteeism Notice'
})

const alertDescription = computed(() => {
  if (alertType.value === 'error') {
    return 'Absenteeism significantly exceeds threshold. Immediate action recommended.'
  }
  if (alertType.value === 'warning') {
    return 'Absenteeism above target threshold. Consider reviewing attendance patterns.'
  }
  return 'Absenteeism is within acceptable range but approaching threshold.'
})

const showScheduleAction = computed(() => {
  return absenteeismRate.value > props.threshold * 1.5
})

const trendIcon = computed(() => {
  if (trendDirection.value === 'up') return 'mdi-trending-up'
  if (trendDirection.value === 'down') return 'mdi-trending-down'
  return 'mdi-minus'
})

const trendTextColor = computed(() => {
  // For absenteeism, up is bad (error), down is good (success)
  if (trendDirection.value === 'up') return 'text-error'
  if (trendDirection.value === 'down') return 'text-success'
  return 'text-grey'
})

const recommendedActions = computed(() => {
  const actions = [
    { id: 'review-patterns', label: 'Review Patterns', icon: 'mdi-chart-timeline-variant' }
  ]

  if (absenteeismRate.value > props.threshold) {
    actions.push({ id: 'notify-supervisors', label: 'Notify Supervisors', icon: 'mdi-email-alert' })
  }

  if (absenteeismRate.value > props.threshold * 1.5) {
    actions.push({ id: 'activate-floating-pool', label: 'Activate Floating Pool', icon: 'mdi-account-switch' })
    actions.push({ id: 'schedule-meetings', label: 'Schedule Meetings', icon: 'mdi-calendar' })
  }

  if (absenteeismRate.value > props.threshold * 2) {
    actions.push({ id: 'escalate-hr', label: 'Escalate to HR', icon: 'mdi-account-alert' })
  }

  return actions
})

// Methods
const fetchData = async () => {
  if (!props.autoFetch) return

  try {
    const response = await axios.get('/api/attendance/kpi/absenteeism', {
      params: {
        client_id: props.clientId,
        start_date: props.startDate,
        end_date: props.endDate
      }
    })

    if (response.data) {
      absenteeismRate.value = parseFloat(response.data.absenteeism_rate || 0)
      scheduledHours.value = response.data.total_scheduled_hours || 0
      absentHours.value = response.data.total_absent_hours || 0
      affectedEmployees.value = response.data.affected_employees || response.data.employee_count || 0

      // Calculate trend if previous data available
      if (response.data.previous_rate !== undefined) {
        const prevRate = parseFloat(response.data.previous_rate)
        trendValue.value = parseFloat((absenteeismRate.value - prevRate).toFixed(1))
        if (trendValue.value > 0.5) {
          trendDirection.value = 'up'
        } else if (trendValue.value < -0.5) {
          trendDirection.value = 'down'
        } else {
          trendDirection.value = 'stable'
        }
      }
    }
  } catch (err: any) {
    console.warn('Absenteeism API not available, using demo data')
    // Demo data for display
    absenteeismRate.value = 7.2
    scheduledHours.value = 4800
    absentHours.value = 346
    affectedEmployees.value = 12
    trendValue.value = 1.3
    trendDirection.value = 'up'
  }
}

// Lifecycle
onMounted(() => {
  fetchData()
})

// Watch for prop changes
watch(
  () => [props.clientId, props.startDate, props.endDate],
  () => {
    dismissed.value = false
    fetchData()
  }
)

// Expose method for parent to manually update
defineExpose({
  updateRate: (rate: number) => {
    absenteeismRate.value = rate
    dismissed.value = false
  },
  dismiss: () => {
    dismissed.value = true
  },
  show: () => {
    dismissed.value = false
  }
})
</script>

<style scoped>
.v-alert {
  transition: all 0.3s ease;
}
</style>
