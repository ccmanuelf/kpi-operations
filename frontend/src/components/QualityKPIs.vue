<template>
  <div>
    <v-row class="mb-4">
      <v-col cols="12">
        <h2 class="text-h4 font-weight-bold">Phase 4: Quality KPIs</h2>
        <p class="text-subtitle-1 text-grey">KPI #4 PPM, #5 DPMO, #6 FPY, #7 RTY</p>
      </v-col>
    </v-row>

    <!-- KPI Cards -->
    <v-row>
      <v-col cols="12" md="6" lg="3">
        <v-card elevation="2">
          <v-card-title class="bg-deep-purple text-white">
            <v-icon left>mdi-bug</v-icon>
            KPI #4: PPM
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-deep-purple text-center">
              {{ ppm }}
            </div>
            <div class="text-caption text-center text-grey mt-2">
              Parts Per Million
            </div>
            <v-progress-linear
              :model-value="Math.min((ppm / 10000) * 100, 100)"
              color="deep-purple"
              height="15"
              class="mt-4"
            ></v-progress-linear>
            <div class="mt-4">
              <code class="text-caption">(Defective / Inspected) × 1,000,000</code>
            </div>
            <v-chip color="success" size="small" class="mt-2">
              <v-icon left small>mdi-check</v-icon>
              Active
            </v-chip>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3">
        <v-card elevation="2">
          <v-card-title class="bg-indigo text-white">
            <v-icon left>mdi-target</v-icon>
            KPI #5: DPMO
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-indigo text-center">
              {{ dpmo }}
            </div>
            <div class="text-caption text-center text-grey mt-2">
              Defects Per Million Opportunities
            </div>
            <v-progress-linear
              :model-value="Math.min((dpmo / 10000) * 100, 100)"
              color="indigo"
              height="15"
              class="mt-4"
            ></v-progress-linear>
            <div class="mt-4">
              <code class="text-caption">(Defects / Opportunities) × 1,000,000</code>
            </div>
            <v-chip color="success" size="small" class="mt-2">
              <v-icon left small>mdi-check</v-icon>
              Active
            </v-chip>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3">
        <v-card elevation="2">
          <v-card-title class="bg-teal text-white">
            <v-icon left>mdi-check-circle</v-icon>
            KPI #6: FPY
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-teal text-center">
              {{ fpy }}%
            </div>
            <div class="text-caption text-center text-grey mt-2">
              First Pass Yield
            </div>
            <v-progress-linear
              :model-value="fpy"
              color="teal"
              height="15"
              class="mt-4"
            >
              <strong>{{ fpy }}%</strong>
            </v-progress-linear>
            <div class="mt-4">
              <code class="text-caption">(Passed / Inspected) × 100</code>
            </div>
            <v-chip color="success" size="small" class="mt-2">
              <v-icon left small>mdi-check</v-icon>
              Active
            </v-chip>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" lg="3">
        <v-card elevation="2">
          <v-card-title class="bg-cyan text-white">
            <v-icon left>mdi-shield-check</v-icon>
            KPI #7: RTY
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-cyan text-center">
              {{ rty }}%
            </div>
            <div class="text-caption text-center text-grey mt-2">
              Rolled Throughput Yield
            </div>
            <v-progress-linear
              :model-value="rty"
              color="cyan"
              height="15"
              class="mt-4"
            >
              <strong>{{ rty }}%</strong>
            </v-progress-linear>
            <div class="mt-4">
              <code class="text-caption">Product of all step FPYs</code>
            </div>
            <v-chip color="success" size="small" class="mt-2">
              <v-icon left small>mdi-check</v-icon>
              Active
            </v-chip>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Quality Trends -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title>Quality Trend - Last 30 Days</v-card-title>
          <v-card-text>
            <div class="text-center text-grey pa-8">
              Chart: PPM & FPY trend over time
              <v-icon size="64" class="mt-4">mdi-chart-areaspline</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title>Top Defect Categories</v-card-title>
          <v-card-text>
            <div class="text-center text-grey pa-8">
              Chart: Pareto chart of defect types
              <v-icon size="64" class="mt-4">mdi-chart-bar</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Quality Summary Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title>Quality Inspection Summary</v-card-title>
          <v-card-text>
            <v-simple-table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th class="text-right">Value</th>
                  <th class="text-right">Target</th>
                  <th class="text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Total Units Inspected</td>
                  <td class="text-right">{{ qualitySummary.inspected.toLocaleString() }}</td>
                  <td class="text-right">-</td>
                  <td class="text-right">
                    <v-icon color="info">mdi-information</v-icon>
                  </td>
                </tr>
                <tr>
                  <td>Units Passed</td>
                  <td class="text-right">{{ qualitySummary.passed.toLocaleString() }}</td>
                  <td class="text-right">-</td>
                  <td class="text-right">
                    <v-icon color="success">mdi-check</v-icon>
                  </td>
                </tr>
                <tr>
                  <td>Units Defective</td>
                  <td class="text-right">{{ qualitySummary.defective.toLocaleString() }}</td>
                  <td class="text-right">&lt; {{ (qualitySummary.inspected * 0.05).toFixed(0) }}</td>
                  <td class="text-right">
                    <v-icon :color="qualitySummary.defective < qualitySummary.inspected * 0.05 ? 'success' : 'warning'">
                      {{ qualitySummary.defective < qualitySummary.inspected * 0.05 ? 'mdi-check' : 'mdi-alert' }}
                    </v-icon>
                  </td>
                </tr>
                <tr>
                  <td>Total Defects</td>
                  <td class="text-right">{{ qualitySummary.totalDefects.toLocaleString() }}</td>
                  <td class="text-right">-</td>
                  <td class="text-right">
                    <v-icon color="info">mdi-information</v-icon>
                  </td>
                </tr>
              </tbody>
            </v-simple-table>
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

const ppm = ref(0)
const dpmo = ref(0)
const fpy = ref(0)
const rty = ref(0)
const qualitySummary = ref({
  inspected: 0,
  passed: 0,
  defective: 0,
  totalDefects: 0
})

const fetchData = async () => {
  try {
    const [ppmRes, dpmoRes, fpyRes, rtyRes] = await Promise.all([
      axios.get('http://localhost:8000/api/v1/kpi/quality/ppm'),
      axios.get('http://localhost:8000/api/v1/kpi/quality/dpmo'),
      axios.get('http://localhost:8000/api/v1/kpi/quality/fpy'),
      axios.get('http://localhost:8000/api/v1/kpi/quality/rty')
    ])

    ppm.value = parseInt(ppmRes.data.ppm)
    dpmo.value = parseInt(dpmoRes.data.dpmo)
    fpy.value = parseFloat(fpyRes.data.fpy.toFixed(1))
    rty.value = parseFloat(rtyRes.data.rty.toFixed(1))

    // Extract summary data
    qualitySummary.value = {
      inspected: ppmRes.data.total_inspected || 10000,
      passed: Math.round((ppmRes.data.total_inspected || 10000) * (fpy.value / 100)),
      defective: ppmRes.data.total_defective || 0,
      totalDefects: ppmRes.data.total_defects || 0
    }
  } catch (error) {
    console.error('Error fetching quality KPIs:', error)
  }
}

onMounted(() => {
  fetchData()
})
</script>
