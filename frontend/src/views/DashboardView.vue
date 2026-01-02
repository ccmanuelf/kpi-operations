<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <h1 class="text-h3 mb-4">Production Dashboard</h1>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" md="3">
        <v-card>
          <v-card-text>
            <div class="text-overline">Today's Units</div>
            <div class="text-h4">{{ totalUnitsToday }}</div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="3">
        <v-card>
          <v-card-text>
            <div class="text-overline">Avg Efficiency</div>
            <div class="text-h4">{{ averageEfficiency }}%</div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="3">
        <v-card>
          <v-card-text>
            <div class="text-overline">Avg Performance</div>
            <div class="text-h4">{{ averagePerformance }}%</div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="3">
        <v-card>
          <v-card-text>
            <div class="text-overline">Total Entries</div>
            <div class="text-h4">{{ productionEntries.length }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title>Recent Production Entries</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="headers"
              :items="recentEntries"
              :loading="loading"
              class="elevation-1"
            >
              <template v-slot:item.production_date="{ item }">
                {{ formatDate(item.production_date) }}
              </template>
              <template v-slot:item.efficiency_percentage="{ item }">
                <v-chip :color="getEfficiencyColor(item.efficiency_percentage)" small>
                  {{ parseFloat(item.efficiency_percentage || 0).toFixed(2) }}%
                </v-chip>
              </template>
              <template v-slot:item.performance_percentage="{ item }">
                <v-chip :color="getPerformanceColor(item.performance_percentage)" small>
                  {{ parseFloat(item.performance_percentage || 0).toFixed(2) }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useKPIStore } from '@/stores/kpiStore'
import { format } from 'date-fns'

const kpiStore = useKPIStore()

const loading = computed(() => kpiStore.loading)
const productionEntries = computed(() => kpiStore.productionEntries)
const recentEntries = computed(() => kpiStore.recentEntries)
const totalUnitsToday = computed(() => kpiStore.totalUnitsToday)
const averageEfficiency = computed(() => kpiStore.averageEfficiency)
const averagePerformance = computed(() => kpiStore.averagePerformance)

const headers = [
  { title: 'Date', key: 'production_date' },
  { title: 'Work Order', key: 'work_order_number' },
  { title: 'Product', key: 'product_id' },
  { title: 'Units', key: 'units_produced' },
  { title: 'Efficiency', key: 'efficiency_percentage' },
  { title: 'Performance', key: 'performance_percentage' }
]

const formatDate = (date) => {
  return format(new Date(date), 'MMM dd, yyyy')
}

const getEfficiencyColor = (value) => {
  const val = parseFloat(value || 0)
  if (val >= 85) return 'success'
  if (val >= 70) return 'warning'
  return 'error'
}

const getPerformanceColor = (value) => {
  const val = parseFloat(value || 0)
  if (val >= 90) return 'success'
  if (val >= 75) return 'warning'
  return 'error'
}

onMounted(async () => {
  await kpiStore.fetchProductionEntries()
  await kpiStore.fetchKPIDashboard()
})
</script>
