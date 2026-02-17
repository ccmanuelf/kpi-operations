<template>
  <div>
    <v-row class="mb-4">
      <v-col cols="12">
        <h2 class="text-h4 font-weight-bold">Phase 1: Production KPIs</h2>
        <p class="text-subtitle-1 text-grey">KPI #3 Efficiency & KPI #9 Performance</p>
      </v-col>
    </v-row>

    <!-- KPI Cards -->
    <v-row>
      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title class="bg-primary text-white">
            <v-icon left>mdi-speedometer</v-icon>
            KPI #3: Efficiency
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-primary text-center">
              {{ efficiency }}%
            </div>
            <v-progress-linear
              :model-value="efficiency"
              color="primary"
              height="20"
              class="mt-4"
            >
              <strong>{{ efficiency }}%</strong>
            </v-progress-linear>
            <div class="mt-4">
              <div class="text-subtitle-2 text-grey">Formula:</div>
              <code class="text-caption">(Hours Produced / Hours Available) × 100</code>
            </div>
            <div class="mt-2">
              <v-chip color="success" size="small" class="mr-2">
                <v-icon left small>mdi-check</v-icon>
                Active
              </v-chip>
              <v-chip color="info" size="small">
                Inference Enabled
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title class="bg-success text-white">
            <v-icon left>mdi-chart-line</v-icon>
            KPI #9: Performance
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-success text-center">
              {{ performance }}%
            </div>
            <v-progress-linear
              :model-value="performance"
              color="success"
              height="20"
              class="mt-4"
            >
              <strong>{{ performance }}%</strong>
            </v-progress-linear>
            <div class="mt-4">
              <div class="text-subtitle-2 text-grey">Formula:</div>
              <code class="text-caption">(Ideal Cycle Time × Units) / Run Time × 100</code>
            </div>
            <div class="mt-2">
              <v-chip color="success" size="small" class="mr-2">
                <v-icon left small>mdi-check</v-icon>
                Active
              </v-chip>
              <v-chip color="info" size="small">
                Inference Enabled
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Data Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title>Recent Production Entries</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="headers"
              :items="productionData"
              :loading="loading"
              density="comfortable"
            >
              <template v-slot:item.efficiency="{ item }">
                <v-chip :color="getEfficiencyColor(item.efficiency)" size="small">
                  {{ item.efficiency }}%
                </v-chip>
              </template>
              <template v-slot:item.performance="{ item }">
                <v-chip :color="getPerformanceColor(item.performance)" size="small">
                  {{ item.performance }}%
                </v-chip>
              </template>
            </v-data-table>
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

const efficiency = ref(0)
const performance = ref(0)
const loading = ref(false)
const productionData = ref([])

const headers = [
  { title: 'Date', key: 'shift_date' },
  { title: 'Client', key: 'client_id' },
  { title: 'Units Produced', key: 'units_produced' },
  { title: 'Efficiency', key: 'efficiency' },
  { title: 'Performance', key: 'performance' }
]

const getEfficiencyColor = (value: number) => {
  if (value >= 90) return 'success'
  if (value >= 70) return 'warning'
  return 'error'
}

const getPerformanceColor = (value: number) => {
  if (value >= 90) return 'success'
  if (value >= 70) return 'warning'
  return 'error'
}

const fetchData = async () => {
  loading.value = true
  try {
    const [effRes, perfRes, entriesRes] = await Promise.all([
      axios.get('/api/kpi/efficiency/trend'),
      axios.get('/api/kpi/performance/trend'),
      axios.get('/api/production-entries?limit=20')
    ])

    efficiency.value = parseFloat(effRes.data.value.toFixed(1))
    performance.value = parseFloat(perfRes.data.value.toFixed(1))
    productionData.value = entriesRes.data
  } catch (error) {
    console.error('Error fetching production KPIs:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>
