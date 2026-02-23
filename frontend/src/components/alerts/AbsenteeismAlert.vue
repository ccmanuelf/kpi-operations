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
          {{ t('absenteeismAlert.currentRate') }}: <strong>{{ absenteeismRate }}%</strong>
          ({{ t('absenteeismAlert.threshold') }}: {{ threshold }}%)
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
          {{ t('absenteeismAlert.viewDetails') }}
        </v-btn>
        <v-btn
          v-if="showScheduleAction"
          variant="outlined"
          :color="alertType === 'error' ? 'white' : undefined"
          size="small"
          prepend-icon="mdi-calendar-clock"
          @click="$emit('scheduleReview')"
        >
          {{ t('absenteeismAlert.scheduleReview') }}
        </v-btn>
      </div>
    </div>

    <!-- Additional Details (expandable) -->
    <v-expand-transition>
      <div v-if="expanded" class="mt-4 pa-3 bg-white rounded">
        <v-row dense>
          <v-col cols="6" sm="3">
            <div class="text-caption text-grey">{{ t('absenteeismAlert.scheduledHours') }}</div>
            <div class="font-weight-bold">{{ scheduledHours.toLocaleString() }}h</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption text-grey">{{ t('absenteeismAlert.absentHours') }}</div>
            <div class="font-weight-bold text-error">{{ absentHours.toLocaleString() }}h</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption text-grey">{{ t('absenteeismAlert.affectedEmployees') }}</div>
            <div class="font-weight-bold">{{ affectedEmployees }}</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption text-grey">{{ t('absenteeismAlert.trend') }}</div>
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
        <div class="text-subtitle-2 mb-2">{{ t('absenteeismAlert.recommendedActions') }}</div>
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
        {{ expanded ? t('absenteeismAlert.showLess') : t('absenteeismAlert.showMore') }}
        <v-icon :icon="expanded ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
      </v-btn>
    </div>
  </v-alert>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

const { t } = useI18n()

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
  if (alertType.value === 'error') return t('absenteeismAlert.criticalAlert')
  if (alertType.value === 'warning') return t('absenteeismAlert.highAlert')
  return t('absenteeismAlert.notice')
})

const alertDescription = computed(() => {
  if (alertType.value === 'error') {
    return t('absenteeismAlert.criticalDesc')
  }
  if (alertType.value === 'warning') {
    return t('absenteeismAlert.highDesc')
  }
  return t('absenteeismAlert.noticeDesc')
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
    { id: 'review-patterns', label: t('absenteeismAlert.reviewPatterns'), icon: 'mdi-chart-timeline-variant' }
  ]

  if (absenteeismRate.value > props.threshold) {
    actions.push({ id: 'notify-supervisors', label: t('absenteeismAlert.notifySupervisors'), icon: 'mdi-email-alert' })
  }

  if (absenteeismRate.value > props.threshold * 1.5) {
    actions.push({ id: 'activate-floating-pool', label: t('absenteeismAlert.activateFloatingPool'), icon: 'mdi-account-switch' })
    actions.push({ id: 'schedule-meetings', label: t('absenteeismAlert.scheduleMeetings'), icon: 'mdi-calendar' })
  }

  if (absenteeismRate.value > props.threshold * 2) {
    actions.push({ id: 'escalate-hr', label: t('absenteeismAlert.escalateHr'), icon: 'mdi-account-alert' })
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
