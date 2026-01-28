<template>
  <v-card :elevation="compact ? 1 : 2" :class="{ 'compact-mode': compact }">
    <!-- Header -->
    <v-card-title
      v-if="!compact"
      class="d-flex align-center bg-grey-darken-3 text-white py-2"
    >
      <v-icon class="mr-2" size="24">mdi-clipboard-check-outline</v-icon>
      Data Completeness
      <v-spacer />
      <v-btn
        icon="mdi-refresh"
        variant="text"
        size="small"
        color="white"
        :loading="loading"
        @click="fetchData"
        aria-label="Refresh data completeness"
      />
    </v-card-title>

    <v-card-text :class="compact ? 'pa-2' : 'pa-4'">
      <!-- Loading State -->
      <div v-if="loading" class="d-flex justify-center align-center" :class="compact ? 'pa-2' : 'pa-6'">
        <v-progress-circular indeterminate color="primary" :size="compact ? 24 : 40" />
      </div>

      <!-- Error State -->
      <v-alert
        v-else-if="error"
        type="error"
        variant="tonal"
        class="mb-0"
        :density="compact ? 'compact' : 'default'"
      >
        {{ error }}
      </v-alert>

      <!-- Data Display -->
      <template v-else>
        <!-- Overall Progress (Circular) -->
        <div class="text-center" :class="compact ? 'mb-2' : 'mb-4'">
          <v-tooltip location="bottom" :disabled="compact">
            <template v-slot:activator="{ props: tooltipProps }">
              <v-progress-circular
                v-bind="tooltipProps"
                :model-value="overallPercentage"
                :size="compact ? 60 : 100"
                :width="compact ? 6 : 10"
                :color="getStatusColor(overallStatus)"
                class="cursor-pointer"
                @click="showDetails = !showDetails"
              >
                <span :class="compact ? 'text-body-2 font-weight-bold' : 'text-h5 font-weight-bold'">
                  {{ overallPercentage }}%
                </span>
              </v-progress-circular>
            </template>
            <span>Click for details</span>
          </v-tooltip>
          <div
            v-if="!compact"
            class="text-subtitle-2 mt-2"
            :class="`text-${getStatusColor(overallStatus)}`"
          >
            {{ getStatusLabel(overallStatus) }}
          </div>
        </div>

        <!-- Compact: Mini Category Indicators -->
        <div v-if="compact" class="d-flex justify-center gap-1 flex-wrap">
          <v-tooltip v-for="category in categories" :key="category.id" location="bottom">
            <template v-slot:activator="{ props: tooltipProps }">
              <v-chip
                v-bind="tooltipProps"
                :color="getStatusColor(category.status)"
                size="x-small"
                variant="flat"
                :prepend-icon="category.icon"
                class="cursor-pointer"
                @click="navigateToCategory(category)"
              >
                {{ category.percentage }}%
              </v-chip>
            </template>
            <span>{{ category.name }}: {{ category.entered }}/{{ category.expected }} entries</span>
          </v-tooltip>
        </div>

        <!-- Full: Category Breakdown -->
        <v-expand-transition>
          <div v-if="!compact || showDetails">
            <v-divider v-if="!compact" class="my-3" />

            <!-- Category Progress Bars -->
            <div v-for="category in categories" :key="category.id" class="mb-3">
              <div class="d-flex justify-space-between align-center mb-1">
                <div class="d-flex align-center">
                  <v-icon :color="category.color" size="18" class="mr-2">{{ category.icon }}</v-icon>
                  <span class="text-body-2 font-weight-medium">{{ category.name }}</span>
                </div>
                <div class="d-flex align-center">
                  <span class="text-caption text-grey mr-2">
                    {{ category.entered }}/{{ category.expected }}
                  </span>
                  <v-chip
                    :color="getStatusColor(category.status)"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ category.percentage }}%
                  </v-chip>
                </div>
              </div>
              <v-progress-linear
                :model-value="category.percentage"
                :color="getStatusColor(category.status)"
                height="8"
                rounded
                class="cursor-pointer"
                @click="navigateToCategory(category)"
              />
            </div>

            <!-- Action Buttons -->
            <div v-if="!compact && incompleteCategories.length > 0" class="mt-4">
              <v-alert
                type="info"
                variant="tonal"
                density="compact"
                class="mb-2"
              >
                <v-icon>mdi-information</v-icon>
                {{ incompleteCategories.length }} category(ies) need attention
              </v-alert>

              <div class="d-flex flex-wrap gap-2">
                <v-btn
                  v-for="category in incompleteCategories"
                  :key="category.id"
                  :color="getStatusColor(category.status)"
                  variant="outlined"
                  size="small"
                  :prepend-icon="category.icon"
                  @click="navigateToCategory(category)"
                >
                  Complete {{ category.name }}
                </v-btn>
              </div>
            </div>
          </div>
        </v-expand-transition>
      </template>
    </v-card-text>

    <!-- Footer (non-compact only) -->
    <v-card-actions v-if="!compact && !loading && !error">
      <v-chip size="x-small" variant="outlined" color="grey">
        {{ formattedDate }}
      </v-chip>
      <v-chip v-if="shift" size="x-small" variant="outlined" color="grey" class="ml-1">
        Shift {{ shift }}
      </v-chip>
      <v-spacer />
      <v-btn
        v-if="showDetails"
        variant="text"
        size="small"
        @click="showDetails = false"
      >
        Collapse
      </v-btn>
      <v-btn
        v-else
        variant="text"
        size="small"
        color="primary"
        @click="showDetails = true"
      >
        Details
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

// Props interface
interface DataCompletenessProps {
  date?: string
  shift?: string
  compact?: boolean
  clientId?: string
}

const props = withDefaults(defineProps<DataCompletenessProps>(), {
  date: () => new Date().toISOString().split('T')[0],
  shift: undefined,
  compact: false,
  clientId: undefined
})

// Emits
const emit = defineEmits(['navigate', 'refresh'])

// Router
const router = useRouter()

// State
const loading = ref(false)
const error = ref<string | null>(null)
const showDetails = ref(!props.compact)
const completenessData = ref<CompletenessResponse | null>(null)

// Types
interface CategoryData {
  id: string
  name: string
  icon: string
  color: string
  route: string
  entered: number
  expected: number
  percentage: number
  status: 'complete' | 'warning' | 'incomplete'
}

interface CompletenessResponse {
  date: string
  shift_id: number | null
  client_id: string | null
  production: CategoryEntry
  downtime: CategoryEntry
  attendance: CategoryEntry
  quality: CategoryEntry
  hold: CategoryEntry
  overall: {
    percentage: number
    status: 'complete' | 'warning' | 'incomplete'
  }
  calculation_timestamp: string
}

interface CategoryEntry {
  entered: number
  expected: number
  percentage: number
  status: 'complete' | 'warning' | 'incomplete'
}

// Computed
const overallPercentage = computed(() => {
  return completenessData.value?.overall.percentage ?? 0
})

const overallStatus = computed(() => {
  return completenessData.value?.overall.status ?? 'incomplete'
})

const categories = computed<CategoryData[]>(() => {
  if (!completenessData.value) return []

  return [
    {
      id: 'production',
      name: 'Production',
      icon: 'mdi-factory',
      color: 'primary',
      route: '/entry/production',
      ...completenessData.value.production
    },
    {
      id: 'downtime',
      name: 'Downtime',
      icon: 'mdi-clock-alert',
      color: 'warning',
      route: '/entry/downtime',
      ...completenessData.value.downtime
    },
    {
      id: 'attendance',
      name: 'Attendance',
      icon: 'mdi-account-check',
      color: 'info',
      route: '/entry/attendance',
      ...completenessData.value.attendance
    },
    {
      id: 'quality',
      name: 'Quality',
      icon: 'mdi-check-decagram',
      color: 'success',
      route: '/entry/quality',
      ...completenessData.value.quality
    },
    {
      id: 'hold',
      name: 'Hold/Resume',
      icon: 'mdi-pause-circle',
      color: 'error',
      route: '/entry/hold',
      ...completenessData.value.hold
    }
  ]
})

const incompleteCategories = computed(() => {
  return categories.value.filter(c => c.status !== 'complete')
})

const formattedDate = computed(() => {
  if (!props.date) return 'Today'
  const d = new Date(props.date)
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  if (d.toDateString() === today.toDateString()) {
    return 'Today'
  }

  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric'
  })
})

// Methods
const getStatusColor = (status: string): string => {
  const colors: Record<string, string> = {
    complete: 'success',
    warning: 'warning',
    incomplete: 'error'
  }
  return colors[status] || 'grey'
}

const getStatusLabel = (status: string): string => {
  const labels: Record<string, string> = {
    complete: 'Data Complete',
    warning: 'Needs Attention',
    incomplete: 'Incomplete'
  }
  return labels[status] || 'Unknown'
}

const navigateToCategory = (category: CategoryData) => {
  emit('navigate', category.id, category.route)

  // If route exists, navigate to it
  if (category.route) {
    router.push({
      path: category.route,
      query: {
        date: props.date,
        shift: props.shift
      }
    })
  }
}

const fetchData = async () => {
  loading.value = true
  error.value = null

  try {
    const params: Record<string, string | undefined> = {
      date: props.date,
      shift_id: props.shift,
      client_id: props.clientId
    }

    // Remove undefined values
    Object.keys(params).forEach(key => {
      if (params[key] === undefined) {
        delete params[key]
      }
    })

    const response = await api.get('/data-completeness', { params })

    completenessData.value = response.data
    emit('refresh', completenessData.value)
  } catch (err: any) {
    console.error('Error fetching data completeness:', err)
    error.value = err.response?.data?.detail || 'Failed to load completeness data'

    // Fallback: generate mock data for UI demonstration
    completenessData.value = generateMockData()
  } finally {
    loading.value = false
  }
}

const generateMockData = (): CompletenessResponse => {
  // Generate plausible mock data when API is unavailable
  const production = { entered: 12, expected: 15, percentage: 80, status: 'warning' as const }
  const downtime = { entered: 5, expected: 5, percentage: 100, status: 'complete' as const }
  const attendance = { entered: 28, expected: 30, percentage: 93, status: 'complete' as const }
  const quality = { entered: 6, expected: 10, percentage: 60, status: 'incomplete' as const }
  const hold = { entered: 2, expected: 2, percentage: 100, status: 'complete' as const }

  const overallPct = Math.round(
    production.percentage * 0.3 +
    downtime.percentage * 0.15 +
    attendance.percentage * 0.3 +
    quality.percentage * 0.15 +
    hold.percentage * 0.1
  )

  return {
    date: props.date || new Date().toISOString().split('T')[0],
    shift_id: props.shift ? parseInt(props.shift) : null,
    client_id: props.clientId || null,
    production,
    downtime,
    attendance,
    quality,
    hold,
    overall: {
      percentage: overallPct,
      status: overallPct >= 90 ? 'complete' : overallPct >= 70 ? 'warning' : 'incomplete'
    },
    calculation_timestamp: new Date().toISOString()
  }
}

// Lifecycle
onMounted(() => {
  fetchData()
})

// Watch for prop changes
watch(
  () => [props.date, props.shift, props.clientId],
  () => {
    fetchData()
  }
)
</script>

<style scoped>
.compact-mode {
  max-width: 280px;
}

.compact-mode .v-card-text {
  padding: 8px !important;
}

.cursor-pointer {
  cursor: pointer;
}

.gap-1 {
  gap: 4px;
}

.gap-2 {
  gap: 8px;
}
</style>
