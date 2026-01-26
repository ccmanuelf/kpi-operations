<template>
  <div class="workflow-step-completeness">
    <!-- Data Completeness Component -->
    <DataCompletenessIndicator
      :date="today"
      :shift="currentShift"
      @navigate="handleNavigate"
      @refresh="handleRefresh"
    />

    <!-- Detailed Breakdown -->
    <v-card variant="outlined" class="mt-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-format-list-checks</v-icon>
        Data Entry Status
      </v-card-title>
      <v-card-text>
        <v-skeleton-loader v-if="loading" type="list-item-two-line@5" />
        <v-list v-else density="compact">
          <v-list-item
            v-for="category in dataCategories"
            :key="category.id"
            :class="getCategoryClass(category)"
          >
            <template v-slot:prepend>
              <v-avatar :color="category.color" size="36">
                <v-icon color="white" size="18">{{ category.icon }}</v-icon>
              </v-avatar>
            </template>

            <v-list-item-title>{{ category.name }}</v-list-item-title>
            <v-list-item-subtitle>
              {{ category.entered }} of {{ category.expected }} entries
              <span v-if="category.missing > 0" class="text-error">
                ({{ category.missing }} missing)
              </span>
            </v-list-item-subtitle>

            <template v-slot:append>
              <div class="d-flex align-center">
                <v-progress-circular
                  :model-value="category.percentage"
                  :color="getProgressColor(category.percentage)"
                  size="36"
                  width="4"
                >
                  <span class="text-caption">{{ category.percentage }}%</span>
                </v-progress-circular>
                <v-btn
                  v-if="category.missing > 0"
                  icon
                  size="small"
                  variant="text"
                  color="primary"
                  class="ml-2"
                  @click="goToCategory(category)"
                >
                  <v-icon size="18">mdi-arrow-right</v-icon>
                </v-btn>
              </div>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Missing Items Alert -->
    <v-alert
      v-if="totalMissing > 0"
      type="warning"
      variant="tonal"
      class="mt-4"
    >
      <v-alert-title>Missing Data Entries</v-alert-title>
      <p class="mb-2">{{ totalMissing }} data entry item(s) are missing for this shift.</p>
      <v-btn
        variant="outlined"
        size="small"
        color="warning"
        @click="notifyOperators"
        :loading="notifying"
      >
        <v-icon start>mdi-bell-ring</v-icon>
        Notify Operators
      </v-btn>
    </v-alert>

    <!-- Open Downtime Incidents -->
    <v-card
      v-if="openDowntimeIncidents.length > 0"
      variant="outlined"
      class="mt-4"
    >
      <v-card-title class="d-flex align-center bg-warning-lighten-4 py-2">
        <v-icon class="mr-2" size="20" color="warning">mdi-clock-alert</v-icon>
        Open Downtime Incidents
        <v-chip size="small" color="warning" class="ml-2">
          {{ openDowntimeIncidents.length }}
        </v-chip>
      </v-card-title>
      <v-card-text class="pa-0">
        <v-list density="compact">
          <v-list-item
            v-for="incident in openDowntimeIncidents"
            :key="incident.id"
          >
            <v-list-item-title>{{ incident.machine }}</v-list-item-title>
            <v-list-item-subtitle>
              Started: {{ formatTime(incident.startTime) }} - {{ incident.reason }}
            </v-list-item-subtitle>
            <template v-slot:append>
              <v-btn
                size="small"
                variant="outlined"
                color="warning"
                @click="resolveDowntime(incident)"
              >
                Resolve
              </v-btn>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Confirmation -->
    <v-checkbox
      v-model="acknowledged"
      :disabled="!canAcknowledge"
      :label="acknowledgeLabel"
      color="primary"
      class="mt-4"
      @update:model-value="handleAcknowledge"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import DataCompletenessIndicator from '@/components/DataCompletenessIndicator.vue'

const emit = defineEmits(['complete', 'update'])
const router = useRouter()

// State
const loading = ref(true)
const acknowledged = ref(false)
const notifying = ref(false)
const today = new Date().toISOString().split('T')[0]
const currentShift = ref('1')

const dataCategories = ref([])
const openDowntimeIncidents = ref([])

// Computed
const totalMissing = computed(() => {
  return dataCategories.value.reduce((sum, cat) => sum + cat.missing, 0)
})

const overallPercentage = computed(() => {
  const total = dataCategories.value.reduce((sum, cat) => sum + cat.expected, 0)
  const entered = dataCategories.value.reduce((sum, cat) => sum + cat.entered, 0)
  return total > 0 ? Math.round((entered / total) * 100) : 100
})

const canAcknowledge = computed(() => {
  // Must have at least 80% completeness or acknowledge missing data
  return overallPercentage.value >= 80 || openDowntimeIncidents.value.length === 0
})

const acknowledgeLabel = computed(() => {
  if (overallPercentage.value >= 100 && openDowntimeIncidents.value.length === 0) {
    return 'Data entry is complete for this shift'
  }
  return 'I acknowledge the missing data and will complete it before shift end'
})

// Methods
const getProgressColor = (percentage) => {
  if (percentage >= 100) return 'success'
  if (percentage >= 80) return 'warning'
  return 'error'
}

const getCategoryClass = (category) => {
  if (category.percentage < 80) return 'bg-red-lighten-5'
  if (category.percentage < 100) return 'bg-orange-lighten-5'
  return ''
}

const formatTime = (timeString) => {
  if (!timeString) return ''
  const date = new Date(timeString)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

const handleNavigate = (categoryId, route) => {
  console.log('Navigate to:', categoryId, route)
}

const handleRefresh = (data) => {
  console.log('Refresh data:', data)
}

const goToCategory = (category) => {
  router.push(category.route)
}

const notifyOperators = async () => {
  notifying.value = true
  try {
    await api.post('/notifications/missing-data', {
      categories: dataCategories.value.filter(c => c.missing > 0).map(c => c.id)
    })
    // Show success notification
  } catch (error) {
    console.error('Failed to notify operators:', error)
  } finally {
    notifying.value = false
  }
}

const resolveDowntime = (incident) => {
  router.push({
    path: '/data-entry/downtime',
    query: { resolve: incident.id }
  })
}

const handleAcknowledge = (value) => {
  emit('update', { acknowledged: value, isValid: value })
  if (value) {
    emit('complete', {
      completenessPercentage: overallPercentage.value,
      categories: dataCategories.value,
      openIncidents: openDowntimeIncidents.value.length
    })
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const [completenessRes, downtimeRes] = await Promise.all([
      api.get('/data-completeness', { params: { date: today } }),
      api.get('/downtime/open')
    ])

    // Transform completeness data to categories
    const data = completenessRes.data
    dataCategories.value = [
      {
        id: 'production',
        name: 'Production',
        icon: 'mdi-factory',
        color: 'primary',
        route: '/production-entry',
        entered: data.production?.entered || 0,
        expected: data.production?.expected || 0,
        missing: (data.production?.expected || 0) - (data.production?.entered || 0),
        percentage: data.production?.percentage || 0
      },
      {
        id: 'downtime',
        name: 'Downtime',
        icon: 'mdi-clock-alert',
        color: 'warning',
        route: '/data-entry/downtime',
        entered: data.downtime?.entered || 0,
        expected: data.downtime?.expected || 0,
        missing: (data.downtime?.expected || 0) - (data.downtime?.entered || 0),
        percentage: data.downtime?.percentage || 0
      },
      {
        id: 'attendance',
        name: 'Attendance',
        icon: 'mdi-account-check',
        color: 'info',
        route: '/data-entry/attendance',
        entered: data.attendance?.entered || 0,
        expected: data.attendance?.expected || 0,
        missing: (data.attendance?.expected || 0) - (data.attendance?.entered || 0),
        percentage: data.attendance?.percentage || 0
      },
      {
        id: 'quality',
        name: 'Quality',
        icon: 'mdi-check-decagram',
        color: 'success',
        route: '/data-entry/quality',
        entered: data.quality?.entered || 0,
        expected: data.quality?.expected || 0,
        missing: (data.quality?.expected || 0) - (data.quality?.entered || 0),
        percentage: data.quality?.percentage || 0
      }
    ]

    openDowntimeIncidents.value = downtimeRes.data || []
  } catch (error) {
    console.error('Failed to fetch completeness data:', error)
    // Mock data
    dataCategories.value = [
      { id: 'production', name: 'Production', icon: 'mdi-factory', color: 'primary', route: '/production-entry', entered: 12, expected: 15, missing: 3, percentage: 80 },
      { id: 'downtime', name: 'Downtime', icon: 'mdi-clock-alert', color: 'warning', route: '/data-entry/downtime', entered: 5, expected: 5, missing: 0, percentage: 100 },
      { id: 'attendance', name: 'Attendance', icon: 'mdi-account-check', color: 'info', route: '/data-entry/attendance', entered: 28, expected: 30, missing: 2, percentage: 93 },
      { id: 'quality', name: 'Quality', icon: 'mdi-check-decagram', color: 'success', route: '/data-entry/quality', entered: 8, expected: 10, missing: 2, percentage: 80 }
    ]
    openDowntimeIncidents.value = [
      { id: 1, machine: 'CNC Machine #2', startTime: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), reason: 'Sensor malfunction' }
    ]
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>
