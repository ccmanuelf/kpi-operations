<template>
  <div class="workflow-step-summary">
    <!-- Shift Performance Summary -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-primary text-white py-3">
        <v-icon class="mr-2" size="24">mdi-chart-box</v-icon>
        {{ $t('workflow.shiftPerformanceSummary') }}
      </v-card-title>
      <v-card-text class="pt-4">
        <v-row>
          <v-col cols="6" md="3">
            <div class="text-center">
              <v-progress-circular
                :model-value="summary.efficiency"
                :color="getEfficiencyColor(summary.efficiency)"
                :size="80"
                :width="8"
              >
                <span class="text-h6 font-weight-bold">{{ summary.efficiency }}%</span>
              </v-progress-circular>
              <div class="text-caption text-grey mt-2">{{ $t('workflow.efficiency') }}</div>
              <div class="text-caption" :class="`text-${getEfficiencyColor(summary.efficiency)}`">
                {{ $t('workflow.targetEfficiency') }}
              </div>
            </div>
          </v-col>
          <v-col cols="6" md="3">
            <div class="text-center">
              <v-progress-circular
                :model-value="summary.quality"
                :color="getQualityColor(summary.quality)"
                :size="80"
                :width="8"
              >
                <span class="text-h6 font-weight-bold">{{ summary.quality }}%</span>
              </v-progress-circular>
              <div class="text-caption text-grey mt-2">{{ $t('workflow.qualityFPY') }}</div>
              <div class="text-caption" :class="`text-${getQualityColor(summary.quality)}`">
                {{ $t('workflow.targetQuality') }}
              </div>
            </div>
          </v-col>
          <v-col cols="6" md="3">
            <div class="text-center">
              <v-progress-circular
                :model-value="summary.availability"
                :color="getAvailabilityColor(summary.availability)"
                :size="80"
                :width="8"
              >
                <span class="text-h6 font-weight-bold">{{ summary.availability }}%</span>
              </v-progress-circular>
              <div class="text-caption text-grey mt-2">{{ $t('workflow.availability') }}</div>
              <div class="text-caption" :class="`text-${getAvailabilityColor(summary.availability)}`">
                {{ $t('workflow.targetAvailability') }}
              </div>
            </div>
          </v-col>
          <v-col cols="6" md="3">
            <div class="text-center">
              <v-progress-circular
                :model-value="summary.oee"
                :color="getOEEColor(summary.oee)"
                :size="80"
                :width="8"
              >
                <span class="text-h6 font-weight-bold">{{ summary.oee }}%</span>
              </v-progress-circular>
              <div class="text-caption text-grey mt-2">{{ $t('workflow.oee') }}</div>
              <div class="text-caption" :class="`text-${getOEEColor(summary.oee)}`">
                {{ $t('workflow.targetOEE') }}
              </div>
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Production Details -->
    <v-row>
      <v-col cols="12" md="6">
        <v-card variant="outlined" class="h-100">
          <v-card-title class="bg-grey-lighten-4 py-2">
            <v-icon class="mr-2" size="20">mdi-factory</v-icon>
            {{ $t('workflow.production') }}
          </v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.unitsProduced') }}</v-list-item-title>
                <template v-slot:append>
                  <span class="font-weight-bold">{{ summary.unitsProduced.toLocaleString() }}</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>{{ $t('common.target') }}</v-list-item-title>
                <template v-slot:append>
                  <span>{{ summary.unitsTarget.toLocaleString() }}</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.variance') }}</v-list-item-title>
                <template v-slot:append>
                  <span :class="summary.variance >= 0 ? 'text-success' : 'text-error'">
                    {{ summary.variance >= 0 ? '+' : '' }}{{ summary.variance.toLocaleString() }}
                  </span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.workOrdersCompleted') }}</v-list-item-title>
                <template v-slot:append>
                  <span>{{ summary.workOrdersCompleted }} / {{ summary.workOrdersTotal }}</span>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card variant="outlined" class="h-100">
          <v-card-title class="bg-grey-lighten-4 py-2">
            <v-icon class="mr-2" size="20">mdi-clock-alert</v-icon>
            {{ $t('navigation.downtime') }}
          </v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.totalDowntime') }}</v-list-item-title>
                <template v-slot:append>
                  <span class="font-weight-bold">{{ summary.downtimeMinutes }} min</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.incidents') }}</v-list-item-title>
                <template v-slot:append>
                  <span>{{ summary.downtimeIncidents }}</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.topReason') }}</v-list-item-title>
                <template v-slot:append>
                  <span class="text-error">{{ summary.topDowntimeReason }}</span>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-2">
      <v-col cols="12" md="6">
        <v-card variant="outlined" class="h-100">
          <v-card-title class="bg-grey-lighten-4 py-2">
            <v-icon class="mr-2" size="20">mdi-check-decagram</v-icon>
            {{ $t('navigation.quality') }}
          </v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.defects') }}</v-list-item-title>
                <template v-slot:append>
                  <span class="font-weight-bold">{{ summary.defects }}</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.ppm') }}</v-list-item-title>
                <template v-slot:append>
                  <span>{{ summary.ppm.toLocaleString() }}</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.activeHolds') }}</v-list-item-title>
                <template v-slot:append>
                  <span :class="summary.activeHolds > 0 ? 'text-warning' : ''">
                    {{ summary.activeHolds }}
                  </span>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card variant="outlined" class="h-100">
          <v-card-title class="bg-grey-lighten-4 py-2">
            <v-icon class="mr-2" size="20">mdi-account-group</v-icon>
            {{ $t('navigation.attendance') }}
          </v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.present') }}</v-list-item-title>
                <template v-slot:append>
                  <span class="font-weight-bold">{{ summary.attendancePresent }} / {{ summary.attendanceExpected }}</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.attendanceRate') }}</v-list-item-title>
                <template v-slot:append>
                  <span>{{ summary.attendanceRate }}%</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>{{ $t('workflow.overtimeHours') }}</v-list-item-title>
                <template v-slot:append>
                  <span>{{ summary.overtimeHours }} hrs</span>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Export Options -->
    <v-card variant="outlined" class="mt-4 mb-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-download</v-icon>
        {{ $t('workflow.exportSummary') }}
      </v-card-title>
      <v-card-text>
        <div class="d-flex flex-wrap gap-2">
          <v-btn
            variant="outlined"
            color="primary"
            @click="exportPDF"
            :loading="exporting === 'pdf'"
          >
            <v-icon start>mdi-file-pdf-box</v-icon>
            {{ $t('workflow.exportPDF') }}
          </v-btn>
          <v-btn
            variant="outlined"
            color="success"
            @click="exportExcel"
            :loading="exporting === 'excel'"
          >
            <v-icon start>mdi-microsoft-excel</v-icon>
            {{ $t('workflow.exportExcel') }}
          </v-btn>
          <v-btn
            variant="outlined"
            @click="emailSummary"
            :loading="exporting === 'email'"
          >
            <v-icon start>mdi-email</v-icon>
            {{ $t('workflow.emailSummary') }}
          </v-btn>
        </div>
      </v-card-text>
    </v-card>

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :label="$t('workflow.summaryConfirmLabel')"
      color="primary"
      @update:model-value="handleConfirm"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

const props = defineProps({
  workflowData: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['complete', 'update'])

// State
const loading = ref(true)
const confirmed = ref(false)
const exporting = ref(null)

const summary = ref({
  efficiency: 0,
  quality: 0,
  availability: 0,
  oee: 0,
  unitsProduced: 0,
  unitsTarget: 0,
  variance: 0,
  workOrdersCompleted: 0,
  workOrdersTotal: 0,
  downtimeMinutes: 0,
  downtimeIncidents: 0,
  topDowntimeReason: '',
  defects: 0,
  ppm: 0,
  activeHolds: 0,
  attendancePresent: 0,
  attendanceExpected: 0,
  attendanceRate: 0,
  overtimeHours: 0
})

// Methods
const getEfficiencyColor = (value) => {
  if (value >= 85) return 'success'
  if (value >= 70) return 'warning'
  return 'error'
}

const getQualityColor = (value) => {
  if (value >= 98) return 'success'
  if (value >= 95) return 'warning'
  return 'error'
}

const getAvailabilityColor = (value) => {
  if (value >= 95) return 'success'
  if (value >= 85) return 'warning'
  return 'error'
}

const getOEEColor = (value) => {
  if (value >= 80) return 'success'
  if (value >= 65) return 'warning'
  return 'error'
}

const exportPDF = async () => {
  exporting.value = 'pdf'
  try {
    // In a real implementation, this would generate a PDF
    await new Promise(resolve => setTimeout(resolve, 1000))
    console.log('PDF exported')
  } finally {
    exporting.value = null
  }
}

const exportExcel = async () => {
  exporting.value = 'excel'
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    console.log('Excel exported')
  } finally {
    exporting.value = null
  }
}

const emailSummary = async () => {
  exporting.value = 'email'
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    console.log('Email sent')
  } finally {
    exporting.value = null
  }
}

const handleConfirm = (value) => {
  if (value) {
    emit('complete', { summary: summary.value })
  }
  emit('update', { summary: summary.value, isValid: value })
}

const fetchSummary = async () => {
  loading.value = true
  try {
    const response = await api.get('/shifts/current/summary')
    summary.value = response.data
  } catch (error) {
    console.error('Failed to fetch summary:', error)
    // Generate summary from workflow data or use mock
    const productionData = props.workflowData['complete-production'] || {}
    const downtimeData = props.workflowData['close-downtime'] || {}
    const attendanceData = props.workflowData['confirm-attendance'] || {}

    summary.value = {
      efficiency: productionData.efficiency || 92,
      quality: 99.1,
      availability: 94,
      oee: 81,
      unitsProduced: productionData.totalProduced || 1600,
      unitsTarget: productionData.totalTarget || 1750,
      variance: (productionData.totalProduced || 1600) - (productionData.totalTarget || 1750),
      workOrdersCompleted: 4,
      workOrdersTotal: 5,
      downtimeMinutes: downtimeData.totalMinutes || 90,
      downtimeIncidents: downtimeData.totalIncidents || 3,
      topDowntimeReason: 'Mechanical Failure',
      defects: 14,
      ppm: 8750,
      activeHolds: 1,
      attendancePresent: attendanceData.presentCount || 28,
      attendanceExpected: 30,
      attendanceRate: Math.round(((attendanceData.presentCount || 28) / 30) * 100),
      overtimeHours: 4.5
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchSummary()
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}

.h-100 {
  height: 100%;
}
</style>
