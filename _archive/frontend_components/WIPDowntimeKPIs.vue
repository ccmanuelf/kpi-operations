<template>
  <div>
    <v-row class="mb-4">
      <v-col cols="12">
        <h2 class="text-h4 font-weight-bold">Phase 2: WIP & Downtime KPIs</h2>
        <p class="text-subtitle-1 text-grey">KPI #1 WIP Aging, #2 On-Time Delivery, #8 Availability</p>
      </v-col>
    </v-row>

    <!-- KPI Cards -->
    <v-row>
      <v-col cols="12" md="4">
        <v-card elevation="2">
          <v-card-title class="bg-warning text-white">
            <v-icon left>mdi-clock-outline</v-icon>
            KPI #1: WIP Aging
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-warning text-center">
              {{ wipAging }} days
            </div>
            <v-progress-linear
              :model-value="(wipAging / 30) * 100"
              color="warning"
              height="20"
              class="mt-4"
            ></v-progress-linear>
            <div class="mt-4">
              <div class="text-subtitle-2 text-grey">Formula:</div>
              <code class="text-caption">Today - Start Date - Hold Duration</code>
            </div>
            <div class="mt-2">
              <v-chip color="success" size="small">
                <v-icon left small>mdi-check</v-icon>
                Active
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card elevation="2">
          <v-card-title class="bg-info text-white">
            <v-icon left>mdi-truck-delivery</v-icon>
            KPI #2: On-Time Delivery
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-info text-center">
              {{ otd }}%
            </div>
            <v-progress-linear
              :model-value="otd"
              color="info"
              height="20"
              class="mt-4"
            >
              <strong>{{ otd }}%</strong>
            </v-progress-linear>
            <div class="mt-4">
              <div class="text-subtitle-2 text-grey">Formula:</div>
              <code class="text-caption">(On-Time Orders / Total Orders) × 100</code>
            </div>
            <div class="mt-2">
              <v-chip color="success" size="small">
                <v-icon left small>mdi-check</v-icon>
                Active
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card elevation="2">
          <v-card-title class="bg-primary text-white">
            <v-icon left>mdi-gauge</v-icon>
            KPI #8: Availability
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-primary text-center">
              {{ availability }}%
            </div>
            <v-progress-linear
              :model-value="availability"
              color="primary"
              height="20"
              class="mt-4"
            >
              <strong>{{ availability }}%</strong>
            </v-progress-linear>
            <div class="mt-4">
              <div class="text-subtitle-2 text-grey">Formula:</div>
              <code class="text-caption">(Run Time / Planned Time) × 100</code>
            </div>
            <div class="mt-2">
              <v-chip color="success" size="small">
                <v-icon left small>mdi-check</v-icon>
                Active
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Downtime Analysis -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title>Downtime by Reason</v-card-title>
          <v-card-text>
            <div class="text-center text-grey pa-4">
              Chart: Downtime reasons distribution
              <v-icon size="48" class="mt-2">mdi-chart-pie</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title>Hold Status Summary</v-card-title>
          <v-card-text>
            <v-simple-table>
              <tbody>
                <tr>
                  <td>Active Holds:</td>
                  <td class="text-right font-weight-bold">{{ holdSummary.active }}</td>
                </tr>
                <tr>
                  <td>Resumed:</td>
                  <td class="text-right font-weight-bold">{{ holdSummary.resumed }}</td>
                </tr>
                <tr>
                  <td>Avg Hold Duration:</td>
                  <td class="text-right font-weight-bold">{{ holdSummary.avgDuration }} hrs</td>
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

const wipAging = ref(0)
const otd = ref(0)
const availability = ref(0)
const holdSummary = ref({
  active: 0,
  resumed: 0,
  avgDuration: 0
})

const fetchData = async () => {
  try {
    const [wipRes, otdRes, availRes] = await Promise.all([
      axios.get('/api/kpi/wip-aging'),
      axios.get('/api/kpi/otd'),
      axios.get('/api/kpi/availability')
    ])

    wipAging.value = parseFloat(wipRes.data.average_aging_days.toFixed(1))
    otd.value = parseFloat(otdRes.data.otd_percentage.toFixed(1))
    availability.value = parseFloat(availRes.data.average_availability.toFixed(1))
  } catch (error) {
    console.error('Error fetching WIP/Downtime KPIs:', error)
  }
}

onMounted(() => {
  fetchData()
})
</script>
