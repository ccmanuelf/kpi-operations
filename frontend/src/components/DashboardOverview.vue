<template>
  <div>
    <v-row class="mb-4">
      <v-col cols="12">
        <h1 class="text-h4 font-weight-bold">KPI Dashboard - All Phases</h1>
        <p class="text-subtitle-1 text-grey">
          Real-time manufacturing performance metrics
        </p>
      </v-col>
    </v-row>

    <!-- KPI Summary Cards -->
    <v-row>
      <!-- Phase 1: Production KPIs -->
      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="primary" size="large">mdi-speedometer</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-primary">
            {{ kpiData.efficiency }}%
          </div>
          <div class="text-subtitle-2 text-grey">KPI #3: Efficiency</div>
          <v-progress-linear
            :model-value="kpiData.efficiency"
            color="primary"
            class="mt-2"
          ></v-progress-linear>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3">
        <v-card class="pa-4" elevation="2">
          <div class="d-flex align-center mb-2">
            <v-icon color="success" size="large">mdi-chart-line</v-icon>
            <v-spacer></v-spacer>
            <v-chip color="success" size="small">Active</v-chip>
          </div>
          <div class="text-h3 font-weight-bold text-success">
            {{ kpiData.performance }}%
          </div>
          <div class="text-subtitle-2 text-grey">KPI #9: Performance</div>
          <v-progress-linear
            :model-value="kpiData.performance"
            color="success"
            class="mt-2"
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
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title>Data Quality Status</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" md="3">
                <div class="text-center">
                  <v-progress-circular
                    :model-value="100"
                    :size="100"
                    :width="10"
                    color="success"
                  >
                    <span class="text-h5 font-weight-bold">10/10</span>
                  </v-progress-circular>
                  <div class="text-subtitle-2 mt-2">KPIs Active</div>
                </div>
              </v-col>
              <v-col cols="12" md="3">
                <div class="text-center">
                  <v-progress-circular
                    :model-value="95"
                    :size="100"
                    :width="10"
                    color="primary"
                  >
                    <span class="text-h5 font-weight-bold">95%</span>
                  </v-progress-circular>
                  <div class="text-subtitle-2 mt-2">Data Completeness</div>
                </div>
              </v-col>
              <v-col cols="12" md="3">
                <div class="text-center">
                  <v-progress-circular
                    :model-value="88"
                    :size="100"
                    :width="10"
                    color="info"
                  >
                    <span class="text-h5 font-weight-bold">88%</span>
                  </v-progress-circular>
                  <div class="text-subtitle-2 mt-2">Inference Confidence</div>
                </div>
              </v-col>
              <v-col cols="12" md="3">
                <div class="text-center">
                  <v-progress-circular
                    :model-value="100"
                    :size="100"
                    :width="10"
                    color="success"
                  >
                    <span class="text-h5 font-weight-bold">100%</span>
                  </v-progress-circular>
                  <div class="text-subtitle-2 mt-2">System Health</div>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const props = defineProps<{
  dateRange: string
}>()

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
</script>
