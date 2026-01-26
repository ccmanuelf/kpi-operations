<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-format-list-numbered</v-icon>
      {{ $t('jobs.lineItems') }}
      <v-chip v-if="jobs.length" class="ml-3" size="small" color="primary">
        {{ jobs.length }} {{ $t('jobs.items') }}
      </v-chip>
      <v-spacer />
      <v-btn
        v-if="showRtyButton"
        color="info"
        variant="outlined"
        size="small"
        @click="loadWorkOrderRty"
        :loading="loadingRty"
      >
        <v-icon left>mdi-calculator</v-icon>
        {{ $t('jobs.calculateRty') }}
      </v-btn>
    </v-card-title>

    <v-card-text>
      <!-- RTY Summary Card -->
      <v-alert
        v-if="rtyData"
        :type="getRtyAlertType(rtyData.rty_percentage)"
        variant="tonal"
        density="compact"
        class="mb-4"
      >
        <div class="d-flex align-center justify-space-between flex-wrap ga-2">
          <div>
            <strong>{{ $t('kpi.rty') }}:</strong>
            {{ formatPercent(rtyData.rty_percentage) }}%
            <span class="text-caption ml-2">({{ rtyData.interpretation }})</span>
          </div>
          <div class="text-caption">
            {{ $t('jobs.totalScrap') }}: {{ rtyData.total_scrap }}
            <span class="mx-2">|</span>
            {{ $t('jobs.bottleneck') }}: {{ rtyData.bottleneck_job?.job_id || 'N/A' }}
            ({{ formatPercent(rtyData.bottleneck_job?.yield_percentage) }}%)
          </div>
        </div>
      </v-alert>

      <!-- Jobs Table -->
      <v-data-table
        :headers="headers"
        :items="jobs"
        :loading="loading"
        :items-per-page="10"
        density="compact"
        class="elevation-0"
      >
        <!-- Job ID -->
        <template v-slot:item.job_id="{ item }">
          <span class="font-weight-medium text-primary">{{ item.job_id }}</span>
        </template>

        <!-- Part Number -->
        <template v-slot:item.part_number="{ item }">
          <v-chip size="small" variant="outlined">
            {{ item.part_number || 'N/A' }}
          </v-chip>
        </template>

        <!-- Progress -->
        <template v-slot:item.progress="{ item }">
          <div class="d-flex align-center" style="min-width: 120px;">
            <v-progress-linear
              :model-value="calculateProgress(item)"
              :color="getProgressColor(item)"
              height="6"
              rounded
              class="mr-2"
            />
            <span class="text-caption text-no-wrap">
              {{ item.completed_quantity || 0 }} / {{ item.quantity_ordered }}
            </span>
          </div>
        </template>

        <!-- Yield -->
        <template v-slot:item.yield="{ item }">
          <v-chip
            :color="getYieldColor(getJobYield(item))"
            size="small"
          >
            {{ formatPercent(getJobYield(item)) }}%
          </v-chip>
        </template>

        <!-- Scrapped -->
        <template v-slot:item.quantity_scrapped="{ item }">
          <span :class="item.quantity_scrapped > 0 ? 'text-error font-weight-medium' : ''">
            {{ item.quantity_scrapped || 0 }}
          </span>
        </template>

        <!-- Status -->
        <template v-slot:item.status="{ item }">
          <v-chip
            :color="getStatusColor(item.status)"
            size="small"
            variant="tonal"
          >
            {{ formatStatus(item.status) }}
          </v-chip>
        </template>

        <!-- Actions -->
        <template v-slot:item.actions="{ item }">
          <v-btn
            icon
            size="small"
            variant="text"
            @click="loadJobYield(item)"
            :loading="loadingJobId === item.job_id"
          >
            <v-icon>mdi-chart-line</v-icon>
            <v-tooltip activator="parent">{{ $t('jobs.viewYield') }}</v-tooltip>
          </v-btn>
        </template>

        <!-- No Data -->
        <template v-slot:no-data>
          <div class="text-center pa-4">
            <v-icon size="48" color="grey">mdi-package-variant</v-icon>
            <p class="mt-2 text-grey">{{ $t('jobs.noJobs') }}</p>
          </div>
        </template>
      </v-data-table>
    </v-card-text>

    <!-- Job Yield Dialog -->
    <v-dialog v-model="yieldDialog" max-width="500">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-chart-line</v-icon>
          {{ $t('jobs.yieldDetails') }}: {{ selectedJob?.job_id }}
        </v-card-title>
        <v-card-text v-if="jobYieldData">
          <v-row>
            <v-col cols="6">
              <div class="text-caption text-grey">{{ $t('jobs.totalUnits') }}</div>
              <div class="text-h5">{{ jobYieldData.total_units }}</div>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-grey">{{ $t('jobs.goodUnits') }}</div>
              <div class="text-h5 text-success">{{ jobYieldData.good_units }}</div>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-grey">{{ $t('jobs.scrappedUnits') }}</div>
              <div class="text-h5 text-error">{{ jobYieldData.scrapped_units }}</div>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-grey">{{ $t('kpi.finalYield') }}</div>
              <div class="text-h5" :class="getYieldTextColor(jobYieldData.yield_percentage)">
                {{ formatPercent(jobYieldData.yield_percentage) }}%
              </div>
            </v-col>
          </v-row>
          <v-alert v-if="jobYieldData.interpretation" :type="getYieldAlertType(jobYieldData.yield_percentage)" variant="tonal" class="mt-4">
            {{ jobYieldData.interpretation }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="yieldDialog = false">{{ $t('common.close') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const props = defineProps({
  workOrderId: {
    type: String,
    required: true
  },
  showRtyButton: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['rty-loaded'])

const { t } = useI18n()

// State
const loading = ref(false)
const loadingRty = ref(false)
const loadingJobId = ref(null)
const jobs = ref([])
const rtyData = ref(null)
const yieldDialog = ref(false)
const selectedJob = ref(null)
const jobYieldData = ref(null)

// Table headers
const headers = computed(() => [
  { title: t('jobs.jobId'), key: 'job_id', sortable: true },
  { title: t('jobs.partNumber'), key: 'part_number', sortable: true },
  { title: t('jobs.progress'), key: 'progress', sortable: false },
  { title: t('jobs.yield'), key: 'yield', sortable: true },
  { title: t('jobs.scrapped'), key: 'quantity_scrapped', sortable: true },
  { title: t('common.status'), key: 'status', sortable: true },
  { title: t('common.actions'), key: 'actions', sortable: false, align: 'end' }
])

// Methods
const loadJobs = async () => {
  if (!props.workOrderId) return

  loading.value = true
  try {
    const response = await api.get(`/api/work-orders/${props.workOrderId}/jobs`)
    jobs.value = response.data || []
  } catch (error) {
    console.error('Failed to load jobs:', error)
    jobs.value = []
  } finally {
    loading.value = false
  }
}

const loadWorkOrderRty = async () => {
  if (!props.workOrderId) return

  loadingRty.value = true
  try {
    const response = await api.get(`/api/work-orders/${props.workOrderId}/rty`)
    rtyData.value = response.data
    emit('rty-loaded', response.data)
  } catch (error) {
    console.error('Failed to load work order RTY:', error)
    rtyData.value = null
  } finally {
    loadingRty.value = false
  }
}

const loadJobYield = async (job) => {
  selectedJob.value = job
  loadingJobId.value = job.job_id

  try {
    const response = await api.get(`/api/jobs/${job.job_id}/yield`)
    jobYieldData.value = response.data
    yieldDialog.value = true
  } catch (error) {
    console.error('Failed to load job yield:', error)
    jobYieldData.value = null
  } finally {
    loadingJobId.value = null
  }
}

const calculateProgress = (item) => {
  if (!item.quantity_ordered || item.quantity_ordered === 0) return 0
  return ((item.completed_quantity || 0) / item.quantity_ordered) * 100
}

const getJobYield = (item) => {
  const total = (item.completed_quantity || 0) + (item.quantity_scrapped || 0)
  if (total === 0) return 100
  return ((item.completed_quantity || 0) / total) * 100
}

const getProgressColor = (item) => {
  const progress = calculateProgress(item)
  if (progress >= 100) return 'success'
  if (progress >= 75) return 'info'
  if (progress >= 50) return 'warning'
  return 'error'
}

const getYieldColor = (yield_pct) => {
  if (yield_pct >= 99) return 'success'
  if (yield_pct >= 95) return 'amber-darken-3'
  if (yield_pct >= 90) return 'warning'
  return 'error'
}

const getYieldTextColor = (yield_pct) => {
  if (yield_pct >= 99) return 'text-success'
  if (yield_pct >= 95) return 'text-amber-darken-3'
  return 'text-error'
}

const getYieldAlertType = (yield_pct) => {
  if (yield_pct >= 99) return 'success'
  if (yield_pct >= 95) return 'warning'
  return 'error'
}

const getRtyAlertType = (rty_pct) => {
  if (rty_pct >= 95) return 'success'
  if (rty_pct >= 90) return 'warning'
  return 'error'
}

const getStatusColor = (status) => {
  const colors = {
    'COMPLETED': 'success',
    'IN_PROGRESS': 'info',
    'PENDING': 'warning',
    'CANCELLED': 'error'
  }
  return colors[status] || 'grey'
}

const formatStatus = (status) => {
  const labels = {
    'COMPLETED': t('workOrders.completed'),
    'IN_PROGRESS': t('workOrders.inProgress'),
    'PENDING': t('workOrders.pending'),
    'CANCELLED': t('workOrders.cancelled')
  }
  return labels[status] || status
}

const formatPercent = (value) => {
  if (value === null || value === undefined) return 'N/A'
  return Number(value).toFixed(1)
}

// Watch for work order changes
watch(() => props.workOrderId, (newVal) => {
  if (newVal) {
    loadJobs()
    rtyData.value = null
  }
}, { immediate: true })
</script>
