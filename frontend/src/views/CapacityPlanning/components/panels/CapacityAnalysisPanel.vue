<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-chart-bar</v-icon>
      Capacity Analysis
      <v-spacer />
      <v-btn
        color="primary"
        size="small"
        variant="elevated"
        :loading="store.isRunningAnalysis"
        @click="showAnalysisDialog = true"
      >
        <v-icon start>mdi-play</v-icon>
        Run Analysis
      </v-btn>
    </v-card-title>
    <v-card-text>
      <!-- Summary Stats -->
      <v-row v-if="analysis.length" class="mb-4">
        <v-col cols="3">
          <v-card variant="tonal" color="primary">
            <v-card-text class="text-center">
              <div class="text-h4">{{ store.averageUtilization }}%</div>
              <div class="text-subtitle-1">Avg Utilization</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="success">
            <v-card-text class="text-center">
              <div class="text-h4">{{ analysis.length }}</div>
              <div class="text-subtitle-1">Lines Analyzed</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="error">
            <v-card-text class="text-center">
              <div class="text-h4">{{ bottleneckCount }}</div>
              <div class="text-subtitle-1">Bottlenecks</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="warning">
            <v-card-text class="text-center">
              <div class="text-h4">{{ overloadCount }}</div>
              <div class="text-subtitle-1">Overloaded</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Utilization Chart (Simple Bar Visualization) -->
      <v-card v-if="analysis.length" variant="outlined" class="mb-4">
        <v-card-title class="text-subtitle-1">Line Utilization</v-card-title>
        <v-card-text>
          <div v-for="line in analysis" :key="line._id" class="mb-3">
            <div class="d-flex align-center mb-1">
              <span class="text-body-2" style="width: 100px">{{ line.line_code }}</span>
              <v-progress-linear
                :model-value="Math.min(line.utilization_percent, 100)"
                :color="getUtilizationColor(line.utilization_percent)"
                height="24"
                class="flex-grow-1"
              >
                <template v-slot:default>
                  <span class="text-caption font-weight-bold">
                    {{ line.utilization_percent?.toFixed(1) }}%
                  </span>
                </template>
              </v-progress-linear>
              <v-chip
                v-if="line.is_bottleneck"
                size="x-small"
                color="error"
                class="ml-2"
              >
                Bottleneck
              </v-chip>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Results Table -->
      <v-data-table
        v-if="analysis.length"
        :headers="headers"
        :items="analysis"
        :items-per-page="10"
        class="elevation-1"
        density="compact"
      >
        <template v-slot:item.utilization_percent="{ item }">
          <span :class="getUtilizationClass(item.utilization_percent)">
            {{ item.utilization_percent?.toFixed(1) }}%
          </span>
        </template>

        <template v-slot:item.is_bottleneck="{ item }">
          <v-icon
            v-if="item.is_bottleneck"
            color="error"
          >
            mdi-alert-circle
          </v-icon>
          <v-icon v-else color="success">mdi-check-circle</v-icon>
        </template>

        <template v-slot:item.required_hours="{ item }">
          {{ item.required_hours?.toFixed(1) }}
        </template>

        <template v-slot:item.available_hours="{ item }">
          {{ item.available_hours?.toFixed(1) }}
        </template>
      </v-data-table>

      <!-- Empty State -->
      <div v-else class="text-center pa-8 text-grey">
        <v-icon size="64" color="grey-lighten-1">mdi-chart-bar</v-icon>
        <div class="text-h6 mt-4">No Capacity Analysis Results</div>
        <div class="text-body-2 mt-2">
          Click "Run Analysis" to evaluate production line capacity and identify bottlenecks.
        </div>
        <v-btn
          color="primary"
          variant="tonal"
          class="mt-4"
          @click="showAnalysisDialog = true"
        >
          Run Analysis
        </v-btn>
      </div>
    </v-card-text>

    <!-- Analysis Dialog -->
    <v-dialog v-model="showAnalysisDialog" max-width="500">
      <v-card>
        <v-card-title>Run Capacity Analysis</v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="6">
              <v-text-field
                v-model="startDate"
                label="Start Date"
                type="date"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="endDate"
                label="End Date"
                type="date"
                variant="outlined"
              />
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showAnalysisDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            :loading="store.isRunningAnalysis"
            @click="runAnalysis"
          >
            Run Analysis
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const store = useCapacityPlanningStore()

const showAnalysisDialog = ref(false)
const startDate = ref('')
const endDate = ref('')

const headers = [
  { title: 'Line', key: 'line_code', width: '120px' },
  { title: 'Period', key: 'period_date', width: '120px' },
  { title: 'Required Hours', key: 'required_hours', width: '120px' },
  { title: 'Available Hours', key: 'available_hours', width: '120px' },
  { title: 'Utilization', key: 'utilization_percent', width: '120px' },
  { title: 'Bottleneck', key: 'is_bottleneck', width: '100px' }
]

const analysis = computed(() => store.worksheets.capacityAnalysis.data)

const bottleneckCount = computed(() =>
  analysis.value.filter(a => a.is_bottleneck).length
)

const overloadCount = computed(() =>
  analysis.value.filter(a => parseFloat(a.utilization_percent) > 100).length
)

const getUtilizationColor = (percent) => {
  if (percent >= 100) return 'error'
  if (percent >= 90) return 'warning'
  if (percent >= 70) return 'success'
  return 'info'
}

const getUtilizationClass = (percent) => {
  if (percent >= 100) return 'text-error font-weight-bold'
  if (percent >= 90) return 'text-warning font-weight-bold'
  return ''
}

const runAnalysis = async () => {
  showAnalysisDialog.value = false
  try {
    await store.runCapacityAnalysis(startDate.value, endDate.value)
  } catch (error) {
    console.error('Capacity analysis failed:', error)
  }
}

onMounted(() => {
  const today = new Date()
  const thirtyDaysLater = new Date(today)
  thirtyDaysLater.setDate(thirtyDaysLater.getDate() + 30)

  startDate.value = today.toISOString().slice(0, 10)
  endDate.value = thirtyDaysLater.toISOString().slice(0, 10)
})
</script>
