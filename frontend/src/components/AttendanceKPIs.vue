<template>
  <div>
    <v-row class="mb-4">
      <v-col cols="12">
        <h2 class="text-h4 font-weight-bold">Phase 3: Attendance KPIs</h2>
        <p class="text-subtitle-1 text-grey">KPI #10 Absenteeism Rate</p>
      </v-col>
    </v-row>

    <!-- KPI Card -->
    <v-row>
      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title class="bg-error text-white">
            <v-icon left>mdi-account-alert</v-icon>
            KPI #10: Absenteeism Rate
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-error text-center">
              {{ absenteeism }}%
            </div>
            <v-progress-linear
              :model-value="absenteeism"
              color="error"
              height="20"
              class="mt-4"
            >
              <strong>{{ absenteeism }}%</strong>
            </v-progress-linear>
            <div class="mt-4">
              <div class="text-subtitle-2 text-grey">Formula:</div>
              <code class="text-caption">(Absent Hours / Scheduled Hours) × 100</code>
            </div>
            <div class="mt-4">
              <div class="text-subtitle-2 text-grey">Target: &lt; 5%</div>
              <v-chip
                :color="absenteeism < 5 ? 'success' : absenteeism < 10 ? 'warning' : 'error'"
                size="small"
                class="mt-2"
              >
                {{ absenteeism < 5 ? 'Excellent' : absenteeism < 10 ? 'Good' : 'Needs Improvement' }}
              </v-chip>
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

      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title>Absence Breakdown</v-card-title>
          <v-card-text>
            <v-list>
              <v-list-item v-for="(item, index) in absenceBreakdown" :key="index">
                <template v-slot:prepend>
                  <v-icon :color="item.color">{{ item.icon }}</v-icon>
                </template>
                <v-list-item-title>{{ item.type }}</v-list-item-title>
                <template v-slot:append>
                  <v-chip size="small" :color="item.color">
                    {{ item.percentage }}%
                  </v-chip>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Attendance Trend -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title>Attendance Trend - Last 30 Days</v-card-title>
          <v-card-text>
            <div class="text-center text-grey pa-8">
              Chart: Daily absenteeism trend
              <v-icon size="64" class="mt-4">mdi-chart-timeline-variant</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Floating Pool Coverage -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title>Floating Pool Coverage</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="4" class="text-center">
                <div class="text-h3 font-weight-bold text-primary">{{ floatingPool.total }}</div>
                <div class="text-caption text-grey">Total Floating Staff</div>
              </v-col>
              <v-col cols="4" class="text-center">
                <div class="text-h3 font-weight-bold text-success">{{ floatingPool.active }}</div>
                <div class="text-caption text-grey">Currently Covering</div>
              </v-col>
              <v-col cols="4" class="text-center">
                <div class="text-h3 font-weight-bold text-info">{{ floatingPool.available }}</div>
                <div class="text-caption text-grey">Available</div>
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

const absenteeism = ref(0)
const absenceBreakdown = ref([
  { type: 'Unscheduled Absence', percentage: 0, color: 'error', icon: 'mdi-alert-circle' },
  { type: 'Vacation', percentage: 0, color: 'info', icon: 'mdi-beach' },
  { type: 'Medical Leave', percentage: 0, color: 'warning', icon: 'mdi-hospital-box' },
  { type: 'Personal Leave', percentage: 0, color: 'grey', icon: 'mdi-account' }
])
const floatingPool = ref({
  total: 0,
  active: 0,
  available: 0
})

const fetchData = async () => {
  try {
    const response = await axios.get('/api/attendance/kpi/absenteeism')
    absenteeism.value = parseFloat(response.data.absenteeism_rate.toFixed(1))

    // Mock absence breakdown (would come from API)
    absenceBreakdown.value[0].percentage = (absenteeism.value * 0.4).toFixed(1)
    absenceBreakdown.value[1].percentage = (absenteeism.value * 0.3).toFixed(1)
    absenceBreakdown.value[2].percentage = (absenteeism.value * 0.2).toFixed(1)
    absenceBreakdown.value[3].percentage = (absenteeism.value * 0.1).toFixed(1)

    // Mock floating pool data
    floatingPool.value = {
      total: 5,
      active: 3,
      available: 2
    }
  } catch (error) {
    console.error('Error fetching attendance KPIs:', error)
  }
}

onMounted(() => {
  fetchData()
})
</script>
