<template>
  <div class="workflow-step-previous-shift">
    <v-row>
      <!-- Previous Shift Summary -->
      <v-col cols="12" md="6">
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="text-subtitle-1 bg-grey-lighten-4">
            <v-icon class="mr-2" size="20">mdi-chart-box</v-icon>
            Previous Shift Performance
          </v-card-title>
          <v-card-text>
            <v-skeleton-loader v-if="loading" type="list-item-three-line" />
            <template v-else>
              <div class="d-flex justify-space-between align-center mb-3">
                <span class="text-body-2 text-grey">Production</span>
                <v-chip
                  :color="getPercentageColor(previousShift.productionPercent)"
                  size="small"
                  variant="flat"
                >
                  {{ previousShift.productionActual }} / {{ previousShift.productionTarget }}
                  ({{ previousShift.productionPercent }}%)
                </v-chip>
              </div>
              <v-progress-linear
                :model-value="previousShift.productionPercent"
                :color="getPercentageColor(previousShift.productionPercent)"
                height="8"
                rounded
                class="mb-4"
              />

              <div class="d-flex justify-space-between align-center mb-3">
                <span class="text-body-2 text-grey">Efficiency</span>
                <v-chip
                  :color="getPercentageColor(previousShift.efficiency)"
                  size="small"
                  variant="flat"
                >
                  {{ previousShift.efficiency }}%
                </v-chip>
              </div>
              <v-progress-linear
                :model-value="previousShift.efficiency"
                :color="getPercentageColor(previousShift.efficiency)"
                height="8"
                rounded
                class="mb-4"
              />

              <div class="d-flex justify-space-between align-center mb-3">
                <span class="text-body-2 text-grey">Quality (FPY)</span>
                <v-chip
                  :color="getPercentageColor(previousShift.quality)"
                  size="small"
                  variant="flat"
                >
                  {{ previousShift.quality }}%
                </v-chip>
              </div>
              <v-progress-linear
                :model-value="previousShift.quality"
                :color="getPercentageColor(previousShift.quality)"
                height="8"
                rounded
              />
            </template>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Key Metrics -->
      <v-col cols="12" md="6">
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="text-subtitle-1 bg-grey-lighten-4">
            <v-icon class="mr-2" size="20">mdi-alert-circle-outline</v-icon>
            Key Metrics
          </v-card-title>
          <v-card-text>
            <v-skeleton-loader v-if="loading" type="list-item-two-line@3" />
            <v-list v-else density="compact">
              <v-list-item>
                <template v-slot:prepend>
                  <v-avatar color="error" size="32">
                    <v-icon size="18" color="white">mdi-clock-alert</v-icon>
                  </v-avatar>
                </template>
                <v-list-item-title>Downtime Incidents</v-list-item-title>
                <v-list-item-subtitle>{{ previousShift.downtimeIncidents }} incidents ({{ previousShift.downtimeMinutes }} min)</v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <template v-slot:prepend>
                  <v-avatar color="warning" size="32">
                    <v-icon size="18" color="white">mdi-pause-circle</v-icon>
                  </v-avatar>
                </template>
                <v-list-item-title>Quality Holds</v-list-item-title>
                <v-list-item-subtitle>{{ previousShift.qualityHolds }} active holds</v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <template v-slot:prepend>
                  <v-avatar color="info" size="32">
                    <v-icon size="18" color="white">mdi-account-group</v-icon>
                  </v-avatar>
                </template>
                <v-list-item-title>Attendance</v-list-item-title>
                <v-list-item-subtitle>{{ previousShift.attendanceActual }} / {{ previousShift.attendanceExpected }} present</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Handoff Notes -->
      <v-col cols="12">
        <v-card variant="outlined">
          <v-card-title class="text-subtitle-1 bg-grey-lighten-4">
            <v-icon class="mr-2" size="20">mdi-note-text</v-icon>
            Handoff Notes from Previous Shift
          </v-card-title>
          <v-card-text>
            <v-skeleton-loader v-if="loading" type="paragraph" />
            <template v-else>
              <v-alert
                v-if="!previousShift.handoffNotes"
                type="info"
                variant="tonal"
                density="compact"
              >
                No handoff notes from previous shift
              </v-alert>
              <div v-else class="handoff-notes">
                <div class="text-caption text-grey mb-2">
                  From {{ previousShift.supervisor }} - {{ formatTime(previousShift.endTime) }}
                </div>
                <p class="text-body-2">{{ previousShift.handoffNotes }}</p>
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Acknowledgment -->
    <v-checkbox
      v-model="acknowledged"
      label="I have reviewed the previous shift information"
      color="primary"
      class="mt-4"
      @update:model-value="handleAcknowledge"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const emit = defineEmits(['complete', 'update'])

// State
const loading = ref(true)
const acknowledged = ref(false)
const previousShift = ref({
  productionActual: 0,
  productionTarget: 0,
  productionPercent: 0,
  efficiency: 0,
  quality: 0,
  downtimeIncidents: 0,
  downtimeMinutes: 0,
  qualityHolds: 0,
  attendanceActual: 0,
  attendanceExpected: 0,
  handoffNotes: '',
  supervisor: '',
  endTime: null
})

// Methods
const getPercentageColor = (value) => {
  if (value >= 95) return 'success'
  if (value >= 85) return 'warning'
  return 'error'
}

const formatTime = (timeString) => {
  if (!timeString) return ''
  const date = new Date(timeString)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const handleAcknowledge = (value) => {
  emit('update', { acknowledged: value, isValid: value })
  if (value) {
    emit('complete', { acknowledged: true, reviewedAt: new Date().toISOString() })
  }
}

const fetchPreviousShift = async () => {
  loading.value = true
  try {
    const response = await api.get('/shifts/previous/summary')
    previousShift.value = response.data
  } catch (error) {
    console.error('Failed to fetch previous shift:', error)
    // Use mock data for demonstration
    previousShift.value = {
      productionActual: 2450,
      productionTarget: 3000,
      productionPercent: 82,
      efficiency: 94,
      quality: 99.1,
      downtimeIncidents: 2,
      downtimeMinutes: 45,
      qualityHolds: 1,
      attendanceActual: 28,
      attendanceExpected: 30,
      handoffNotes: 'Line 3 had intermittent sensor issues - maintenance has been notified. Quality hold on WO-12345 pending disposition decision.',
      supervisor: 'Carlos M.',
      endTime: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString()
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchPreviousShift()
})
</script>

<style scoped>
.handoff-notes {
  background: #f5f5f5;
  border-radius: 8px;
  padding: 16px;
}
</style>
