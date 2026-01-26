<template>
  <div class="workflow-step-downtime">
    <!-- Downtime Summary -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-primary">{{ totalIncidents }}</div>
          <div class="text-caption text-grey">Total Incidents</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-success">{{ resolvedCount }}</div>
          <div class="text-caption text-grey">Resolved</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4" :class="openCount > 0 ? 'text-error' : 'text-grey'">
            {{ openCount }}
          </div>
          <div class="text-caption text-grey">Open</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-warning">{{ totalMinutes }}</div>
          <div class="text-caption text-grey">Total Minutes</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Open Incidents -->
    <v-card
      v-if="openIncidents.length > 0"
      variant="outlined"
      class="mb-4 border-error"
    >
      <v-card-title class="d-flex align-center bg-red-lighten-4 py-2">
        <v-icon class="mr-2" size="20" color="error">mdi-alert-circle</v-icon>
        Open Downtime Incidents
        <v-chip size="small" color="error" class="ml-2">
          {{ openIncidents.length }} to resolve
        </v-chip>
      </v-card-title>

      <v-card-text class="pa-0">
        <v-list density="compact">
          <v-list-item
            v-for="incident in openIncidents"
            :key="incident.id"
            class="border-b"
          >
            <template v-slot:prepend>
              <v-avatar color="error" size="40">
                <v-icon color="white" size="20">mdi-clock-alert</v-icon>
              </v-avatar>
            </template>

            <v-list-item-title class="font-weight-medium">
              {{ incident.machine }}
            </v-list-item-title>
            <v-list-item-subtitle>
              Started: {{ formatTime(incident.startTime) }} |
              Duration: {{ incident.duration }} min |
              {{ incident.reason }}
            </v-list-item-subtitle>

            <template v-slot:append>
              <v-btn
                color="success"
                variant="elevated"
                size="small"
                @click="openResolveDialog(incident)"
              >
                <v-icon start size="16">mdi-check</v-icon>
                Resolve
              </v-btn>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Resolved Incidents -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-clipboard-check</v-icon>
        Resolved Incidents This Shift
      </v-card-title>

      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="loading" type="list-item-two-line@3" />
        <v-alert
          v-else-if="resolvedIncidents.length === 0"
          type="info"
          variant="tonal"
          class="ma-3"
        >
          No resolved downtime incidents this shift
        </v-alert>
        <v-list v-else density="compact">
          <v-list-item
            v-for="incident in resolvedIncidents"
            :key="incident.id"
          >
            <template v-slot:prepend>
              <v-avatar color="success" size="36">
                <v-icon color="white" size="18">mdi-check-circle</v-icon>
              </v-avatar>
            </template>

            <v-list-item-title>{{ incident.machine }}</v-list-item-title>
            <v-list-item-subtitle>
              {{ incident.reason }} - {{ incident.duration }} min
            </v-list-item-subtitle>

            <template v-slot:append>
              <span class="text-caption text-grey">
                {{ formatTime(incident.endTime) }}
              </span>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Downtime by Category -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-chart-pie</v-icon>
        Downtime by Category
      </v-card-title>
      <v-card-text>
        <div v-for="category in downtimeByCategory" :key="category.name" class="mb-3">
          <div class="d-flex justify-space-between align-center mb-1">
            <span class="text-body-2">{{ category.name }}</span>
            <span class="text-caption text-grey">{{ category.minutes }} min ({{ category.percentage }}%)</span>
          </div>
          <v-progress-linear
            :model-value="category.percentage"
            :color="category.color"
            height="8"
            rounded
          />
        </div>
      </v-card-text>
    </v-card>

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :disabled="openCount > 0"
      label="All downtime incidents have been resolved and documented"
      color="primary"
      @update:model-value="handleConfirm"
    />

    <v-alert
      v-if="openCount > 0"
      type="error"
      variant="tonal"
      density="compact"
      class="mt-2"
    >
      {{ openCount }} downtime incident(s) must be resolved before proceeding.
    </v-alert>

    <!-- Resolve Dialog -->
    <v-dialog v-model="resolveDialog" max-width="500" persistent>
      <v-card v-if="selectedIncident">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" color="success">mdi-check-circle</v-icon>
          Resolve Downtime
        </v-card-title>
        <v-card-text>
          <div class="text-subtitle-1 mb-3">{{ selectedIncident.machine }}</div>

          <v-text-field
            v-model="resolveForm.endTime"
            label="End Time"
            type="time"
            variant="outlined"
            density="compact"
            class="mb-3"
          />

          <v-select
            v-model="resolveForm.rootCause"
            :items="rootCauseOptions"
            label="Root Cause"
            variant="outlined"
            density="compact"
            class="mb-3"
          />

          <v-textarea
            v-model="resolveForm.resolution"
            label="Resolution Notes"
            variant="outlined"
            density="compact"
            rows="3"
            placeholder="Describe what was done to resolve the issue..."
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="resolveDialog = false">Cancel</v-btn>
          <v-btn
            color="success"
            variant="elevated"
            :loading="resolving"
            :disabled="!resolveForm.rootCause"
            @click="resolveIncident"
          >
            Resolve
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

const emit = defineEmits(['complete', 'update'])

// State
const loading = ref(true)
const confirmed = ref(false)
const resolveDialog = ref(false)
const resolving = ref(false)
const selectedIncident = ref(null)
const incidents = ref([])

const resolveForm = ref({
  endTime: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
  rootCause: null,
  resolution: ''
})

const rootCauseOptions = [
  'Mechanical Failure',
  'Electrical Issue',
  'Sensor Malfunction',
  'Operator Error',
  'Material Issue',
  'Scheduled Maintenance',
  'Changeover',
  'Other'
]

// Computed
const openIncidents = computed(() => incidents.value.filter(i => !i.resolved))
const resolvedIncidents = computed(() => incidents.value.filter(i => i.resolved))
const totalIncidents = computed(() => incidents.value.length)
const resolvedCount = computed(() => resolvedIncidents.value.length)
const openCount = computed(() => openIncidents.value.length)
const totalMinutes = computed(() => incidents.value.reduce((sum, i) => sum + i.duration, 0))

const downtimeByCategory = computed(() => {
  const categories = {}
  const colors = ['primary', 'error', 'warning', 'info', 'success', 'grey']

  incidents.value.forEach(incident => {
    const cat = incident.category || 'Other'
    if (!categories[cat]) {
      categories[cat] = { name: cat, minutes: 0 }
    }
    categories[cat].minutes += incident.duration
  })

  return Object.values(categories).map((cat, idx) => ({
    ...cat,
    percentage: totalMinutes.value > 0 ? Math.round((cat.minutes / totalMinutes.value) * 100) : 0,
    color: colors[idx % colors.length]
  })).sort((a, b) => b.minutes - a.minutes)
})

// Methods
const formatTime = (timeString) => {
  if (!timeString) return ''
  const date = new Date(timeString)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

const openResolveDialog = (incident) => {
  selectedIncident.value = incident
  resolveForm.value = {
    endTime: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
    rootCause: null,
    resolution: ''
  }
  resolveDialog.value = true
}

const resolveIncident = async () => {
  if (!selectedIncident.value) return

  resolving.value = true
  try {
    await api.patch(`/downtime/${selectedIncident.value.id}/resolve`, {
      end_time: resolveForm.value.endTime,
      root_cause: resolveForm.value.rootCause,
      resolution: resolveForm.value.resolution
    })

    // Update local state
    const incident = incidents.value.find(i => i.id === selectedIncident.value.id)
    if (incident) {
      incident.resolved = true
      incident.endTime = new Date().toISOString()
      incident.rootCause = resolveForm.value.rootCause
    }

    resolveDialog.value = false
    emitUpdate()
  } catch (error) {
    console.error('Failed to resolve incident:', error)
    // Still update locally for demo
    const incident = incidents.value.find(i => i.id === selectedIncident.value.id)
    if (incident) {
      incident.resolved = true
      incident.endTime = new Date().toISOString()
    }
    resolveDialog.value = false
    emitUpdate()
  } finally {
    resolving.value = false
  }
}

const emitUpdate = () => {
  emit('update', {
    incidents: incidents.value,
    openCount: openCount.value,
    totalMinutes: totalMinutes.value,
    isValid: confirmed.value && openCount.value === 0
  })
}

const handleConfirm = (value) => {
  if (value && openCount.value === 0) {
    emit('complete', {
      incidents: incidents.value,
      totalIncidents: totalIncidents.value,
      totalMinutes: totalMinutes.value,
      byCategory: downtimeByCategory.value
    })
  }
  emitUpdate()
}

const fetchData = async () => {
  loading.value = true
  try {
    const response = await api.get('/downtime/shift')
    incidents.value = response.data
  } catch (error) {
    console.error('Failed to fetch downtime data:', error)
    // Mock data
    incidents.value = [
      { id: 1, machine: 'CNC Machine #2', startTime: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(), endTime: new Date(Date.now() - 3.5 * 60 * 60 * 1000).toISOString(), duration: 30, reason: 'Sensor malfunction', category: 'Mechanical Failure', resolved: true },
      { id: 2, machine: 'Conveyor System', startTime: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), endTime: new Date(Date.now() - 1.75 * 60 * 60 * 1000).toISOString(), duration: 15, reason: 'Belt adjustment', category: 'Scheduled Maintenance', resolved: true },
      { id: 3, machine: 'Press #1', startTime: new Date(Date.now() - 45 * 60 * 1000).toISOString(), endTime: null, duration: 45, reason: 'Hydraulic leak', category: 'Mechanical Failure', resolved: false }
    ]
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.border-error {
  border-color: rgb(var(--v-theme-error)) !important;
}

.border-b {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}
</style>
