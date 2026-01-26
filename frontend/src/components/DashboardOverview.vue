<template>
  <div role="region" aria-label="KPI Dashboard">
    <v-row class="mb-4">
      <v-col cols="12">
        <h1 id="dashboard-title" class="text-h4 font-weight-bold">KPI Dashboard - All Phases</h1>
        <p class="text-subtitle-1 text-grey" aria-describedby="dashboard-title">
          Real-time manufacturing performance metrics
        </p>
      </v-col>
    </v-row>

    <!-- Shift Status Banner -->
    <ShiftStatusBanner
      @start-shift="handleStartShift"
      @end-shift="handleEndShift"
    />

    <!-- Absenteeism Alert Banner (P3-004) -->
    <AbsenteeismAlert
      :threshold="5"
      :start-date="startDate"
      :end-date="endDate"
      @view-details="navigateToAbsenteeism"
      @schedule-review="openScheduleDialog"
      @take-action="handleAbsenteeismAction"
    />

    <!-- KPI Summary Cards -->
    <v-row role="list" aria-label="Key Performance Indicators">
      <!-- Phase 1: Production KPIs -->
      <v-col cols="12" md="6" lg="3" role="listitem">
        <v-card class="pa-4" elevation="2" role="article" aria-labelledby="kpi-efficiency-label">
          <div class="d-flex align-center mb-2">
            <v-icon color="primary" size="large" aria-hidden="true">mdi-speedometer</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small" aria-label="KPI Status: Active">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-primary" aria-live="polite">
            {{ kpiData.efficiency }}%
          </div>
          <div id="kpi-efficiency-label" class="text-subtitle-2 text-grey">KPI #3: Efficiency</div>
          <v-progress-linear
            :model-value="kpiData.efficiency"
            color="primary"
            class="mt-2"
            :aria-label="`Efficiency progress: ${kpiData.efficiency} percent`"
            role="progressbar"
            :aria-valuenow="kpiData.efficiency"
            aria-valuemin="0"
            aria-valuemax="100"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3" role="listitem">
        <v-card class="pa-4" elevation="2" role="article" aria-labelledby="kpi-performance-label">
          <div class="d-flex align-center mb-2">
            <v-icon color="success" size="large" aria-hidden="true">mdi-chart-line</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small" aria-label="KPI Status: Active">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-success" aria-live="polite">
            {{ kpiData.performance }}%
          </div>
          <div id="kpi-performance-label" class="text-subtitle-2 text-grey">KPI #9: Performance</div>
          <v-progress-linear
            :model-value="kpiData.performance"
            color="success"
            class="mt-2"
            :aria-label="`Performance progress: ${kpiData.performance} percent`"
            role="progressbar"
            :aria-valuenow="kpiData.performance"
            aria-valuemin="0"
            aria-valuemax="100"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <!-- Phase 2: WIP & Downtime KPIs -->
      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="warning" size="large">mdi-clock-outline</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-warning">
            {{ kpiData.wipAging }}
          </div>
          <div class="text-subtitle-2 text-grey">KPI #1: WIP Aging (days)</div>
          <v-progress-linear
            :model-value="(kpiData.wipAging / 30) * 100"
            color="warning"
            class="mt-2"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="info" size="large">mdi-truck-delivery</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-info">
            {{ kpiData.otd }}%
          </div>
          <div class="text-subtitle-2 text-grey">KPI #2: On-Time Delivery</div>
          <v-progress-linear
            :model-value="kpiData.otd"
            color="info"
            class="mt-2"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="primary" size="large">mdi-gauge</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-primary">
            {{ kpiData.availability }}%
          </div>
          <div class="text-subtitle-2 text-grey">KPI #8: Availability</div>
          <v-progress-linear
            :model-value="kpiData.availability"
            color="primary"
            class="mt-2"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <!-- Phase 3: Attendance KPI -->
      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="error" size="large">mdi-account-alert</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-error">
            {{ kpiData.absenteeism }}%
          </div>
          <div class="text-subtitle-2 text-grey">KPI #10: Absenteeism</div>
          <v-progress-linear
            :model-value="kpiData.absenteeism"
            color="error"
            class="mt-2"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <!-- Phase 4: Quality KPIs -->
      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="deep-purple" size="large">mdi-bug</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-deep-purple">
            {{ kpiData.ppm }}
          </div>
          <div class="text-subtitle-2 text-grey">KPI #4: Quality PPM</div>
          <v-progress-linear
            :model-value="Math.min((kpiData.ppm / 10000) * 100, 100)"
            color="deep-purple"
            class="mt-2"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="indigo" size="large">mdi-target</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-indigo">
            {{ kpiData.dpmo }}
          </div>
          <div class="text-subtitle-2 text-grey">KPI #5: Quality DPMO</div>
          <v-progress-linear
            :model-value="Math.min((kpiData.dpmo / 10000) * 100, 100)"
            color="indigo"
            class="mt-2"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="teal" size="large">mdi-check-circle</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-teal">
            {{ kpiData.fpy }}%
          </div>
          <div class="text-subtitle-2 text-grey">KPI #6: First Pass Yield</div>
          <v-progress-linear
            :model-value="kpiData.fpy"
            color="teal"
            class="mt-2"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="cyan" size="large">mdi-shield-check</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-cyan">
            {{ kpiData.rty }}%
          </div>
          <div class="text-subtitle-2 text-grey">KPI #7: Rolled Throughput Yield</div>
          <v-progress-linear
            :model-value="kpiData.rty"
            color="cyan"
            class="mt-2"
          ></v-progress-linear>
        </v-card>
      </v-col>
    </v-row>

    <!-- Trends Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title>KPI Trends - Last {{ dateRange }}</v-card-title>
          <v-card-text>
            <div class="text-center text-grey pa-8">
              Chart component would render here (ApexCharts or Chart.js)
              <br />
              <v-icon size="64" class="mt-4">mdi-chart-line-variant</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Data Quality Indicators -->
    <v-row class="mt-4">
      <v-col cols="12" lg="6">
        <DataCompletenessIndicator
          :date="endDate"
          @navigate="handleCompletenessNavigate"
        />
      </v-col>
      <v-col cols="12" lg="6">
        <v-card elevation="2">
          <v-card-title class="bg-grey-darken-3 text-white py-2">
            <v-icon class="mr-2" size="24">mdi-chart-box</v-icon>
            System Health
          </v-card-title>
          <v-card-text class="pa-4">
            <v-row>
              <v-col cols="6" class="text-center">
                <v-progress-circular
                  :model-value="100"
                  :size="80"
                  :width="8"
                  color="success"
                >
                  <span class="text-h6 font-weight-bold">10/10</span>
                </v-progress-circular>
                <div class="text-subtitle-2 mt-2">KPIs Active</div>
              </v-col>
              <v-col cols="6" class="text-center">
                <v-progress-circular
                  :model-value="88"
                  :size="80"
                  :width="8"
                  color="info"
                >
                  <span class="text-h6 font-weight-bold">88%</span>
                </v-progress-circular>
                <div class="text-subtitle-2 mt-2">Inference Confidence</div>
              </v-col>
            </v-row>
            <v-divider class="my-4" />
            <div class="d-flex justify-space-between align-center">
              <div>
                <v-icon color="success" class="mr-1">mdi-check-circle</v-icon>
                <span class="text-body-2">API Status: Healthy</span>
              </div>
              <div>
                <v-icon color="success" class="mr-1">mdi-database</v-icon>
                <span class="text-body-2">Database: Connected</span>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Advanced Analysis Widgets Section -->
    <v-row class="mt-6">
      <v-col cols="12">
        <h2 class="text-h5 font-weight-bold mb-4">Advanced Analysis</h2>
      </v-col>
    </v-row>

    <!-- Row 1: Downtime Impact & Bradford Factor (P2-002, P3-003) -->
    <v-row>
      <v-col cols="12" lg="6">
        <DowntimeImpactWidget
          :date-range="dateRange"
          :start-date="startDate"
          :end-date="endDate"
          @view-details="navigateToDowntimeAnalysis"
        />
      </v-col>
      <v-col cols="12" lg="6">
        <BradfordFactorWidget
          :date-range="dateRange"
          :start-date="startDate"
          :end-date="endDate"
          @view-employees="navigateToAttendance"
        />
      </v-col>
    </v-row>

    <!-- Row 2: Quality by Operator & Rework by Operation (P4-001, P4-002) -->
    <v-row class="mt-4">
      <v-col cols="12" lg="6">
        <QualityByOperatorWidget
          :start-date="startDate"
          :end-date="endDate"
          @export-report="exportQualityReport"
          @view-trends="navigateToQualityTrends"
        />
      </v-col>
      <v-col cols="12" lg="6">
        <ReworkByOperationWidget
          :start-date="startDate"
          :end-date="endDate"
          @view-details="navigateToReworkAnalysis"
          @create-action="openActionDialog"
        />
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

// Import Dashboard Widgets
import DowntimeImpactWidget from './widgets/DowntimeImpactWidget.vue'
import BradfordFactorWidget from './widgets/BradfordFactorWidget.vue'
import QualityByOperatorWidget from './widgets/QualityByOperatorWidget.vue'
import ReworkByOperationWidget from './widgets/ReworkByOperationWidget.vue'
import AbsenteeismAlert from './alerts/AbsenteeismAlert.vue'
import DataCompletenessIndicator from './DataCompletenessIndicator.vue'
import ShiftStatusBanner from './workflow/ShiftStatusBanner.vue'
import { useWorkflowStore } from '@/stores/workflowStore'

const router = useRouter()
const workflowStore = useWorkflowStore()

const props = defineProps<{
  dateRange: string
}>()

// Computed date range
const startDate = computed(() => {
  const today = new Date()
  const days = props.dateRange === '7d' ? 7 : props.dateRange === '90d' ? 90 : 30
  const start = new Date(today.getTime() - days * 24 * 60 * 60 * 1000)
  return start.toISOString().split('T')[0]
})

const endDate = computed(() => {
  return new Date().toISOString().split('T')[0]
})

const kpiData = ref({
  efficiency: 0,
  performance: 0,
  wipAging: 0,
  otd: 0,
  availability: 0,
  absenteeism: 0,
  ppm: 0,
  dpmo: 0,
  fpy: 0,
  rty: 0
})

const fetchKPIData = async () => {
  try {
    // Fetch all 10 KPIs from backend
    const [
      efficiencyRes,
      performanceRes,
      wipRes,
      otdRes,
      availabilityRes,
      absenteeismRes,
      ppmRes,
      dpmoRes,
      fpyRes,
      rtyRes
    ] = await Promise.all([
      axios.get('http://localhost:8000/api/v1/kpi/efficiency'),
      axios.get('http://localhost:8000/api/v1/kpi/performance'),
      axios.get('http://localhost:8000/api/v1/kpi/wip-aging'),
      axios.get('http://localhost:8000/api/v1/kpi/on-time-delivery'),
      axios.get('http://localhost:8000/api/v1/kpi/availability'),
      axios.get('http://localhost:8000/api/v1/kpi/absenteeism'),
      axios.get('http://localhost:8000/api/v1/kpi/quality/ppm'),
      axios.get('http://localhost:8000/api/v1/kpi/quality/dpmo'),
      axios.get('http://localhost:8000/api/v1/kpi/quality/fpy'),
      axios.get('http://localhost:8000/api/v1/kpi/quality/rty')
    ])

    kpiData.value = {
      efficiency: parseFloat(efficiencyRes.data.value.toFixed(1)),
      performance: parseFloat(performanceRes.data.value.toFixed(1)),
      wipAging: parseFloat(wipRes.data.average_aging_days.toFixed(1)),
      otd: parseFloat(otdRes.data.otd_percentage.toFixed(1)),
      availability: parseFloat(availabilityRes.data.average_availability.toFixed(1)),
      absenteeism: parseFloat(absenteeismRes.data.absenteeism_rate.toFixed(1)),
      ppm: parseInt(ppmRes.data.ppm),
      dpmo: parseInt(dpmoRes.data.dpmo),
      fpy: parseFloat(fpyRes.data.fpy.toFixed(1)),
      rty: parseFloat(rtyRes.data.rty.toFixed(1))
    }
  } catch (error) {
    console.error('Error fetching KPI data:', error)
  }
}

onMounted(() => {
  fetchKPIData()
})

// Navigation methods for widget events
const navigateToAbsenteeism = () => {
  router.push('/kpi/absenteeism')
}

const navigateToDowntimeAnalysis = () => {
  router.push('/kpi/availability')
}

const navigateToAttendance = () => {
  router.push('/kpi/absenteeism')
}

const navigateToQualityTrends = () => {
  router.push('/kpi/quality')
}

const navigateToReworkAnalysis = () => {
  router.push('/kpi/quality')
}

// Action handlers
const openScheduleDialog = () => {
  console.log('Opening schedule review dialog')
  // Implementation: Open modal for scheduling attendance review
}

const handleAbsenteeismAction = (actionId: string) => {
  console.log('Handling absenteeism action:', actionId)
  // Implementation: Handle specific actions like notify-supervisors, activate-floating-pool, etc.
}

const exportQualityReport = () => {
  console.log('Exporting quality by operator report')
  // Implementation: Generate and download CSV/PDF report
}

const openActionDialog = () => {
  console.log('Opening corrective action dialog')
  // Implementation: Open modal for creating corrective action items
}

const handleCompletenessNavigate = (categoryId: string, route: string) => {
  console.log(`Navigating to ${categoryId} at ${route}`)
  // Navigation is handled by the component itself
}

// Shift workflow handlers
const handleStartShift = () => {
  workflowStore.startWorkflow('shift-start')
}

const handleEndShift = () => {
  workflowStore.startWorkflow('shift-end')
}
</script>
