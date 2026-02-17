<template>
  <div class="station-performance-view">
    <!-- Summary Cards -->
    <v-row class="mb-4">
      <v-col cols="12" md="4">
        <v-card variant="tonal" color="error" class="h-100">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ bottlenecks.length }}</div>
            <div class="text-body-2">Bottleneck Stations</div>
            <div class="text-caption" v-if="bottlenecks.length > 0">
              {{ bottlenecks.map(b => b.operation).join(', ') }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="4">
        <v-card variant="tonal" color="success" class="h-100">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ donors.length }}</div>
            <div class="text-body-2">Donor Stations</div>
            <div class="text-caption" v-if="donors.length > 0">
              Available capacity for rebalancing
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="4">
        <v-card variant="tonal" color="info" class="h-100">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ avgUtilization }}%</div>
            <div class="text-body-2">Average Utilization</div>
            <div class="text-caption">Across all stations</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Filter Controls -->
    <v-card variant="outlined" class="mb-4">
      <v-card-text class="py-2">
        <v-row align="center">
          <v-col cols="12" md="4">
            <v-text-field
              v-model="searchQuery"
              density="compact"
              variant="outlined"
              label="Search"
              prepend-inner-icon="mdi-magnify"
              hide-details
              clearable
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="productFilter"
              :items="productOptions"
              density="compact"
              variant="outlined"
              label="Product"
              hide-details
              clearable
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="statusFilter"
              :items="statusOptions"
              density="compact"
              variant="outlined"
              label="Status"
              hide-details
              clearable
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-btn-toggle v-model="viewMode" density="compact" mandatory variant="outlined">
              <v-btn icon="mdi-table" value="table" />
              <v-btn icon="mdi-view-grid" value="cards" />
            </v-btn-toggle>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Table View -->
    <v-data-table
      v-if="viewMode === 'table'"
      :headers="headers"
      :items="filteredStations"
      :search="searchQuery"
      density="compact"
      class="elevation-1"
      :sort-by="[{ key: 'util_pct', order: 'desc' }]"
      :items-per-page="15"
    >
      <!-- Bottleneck indicator -->
      <template v-slot:item.is_bottleneck="{ item }">
        <v-tooltip v-if="item.is_bottleneck" location="top">
          <template v-slot:activator="{ props }">
            <v-icon v-bind="props" color="error">mdi-alert-circle</v-icon>
          </template>
          Bottleneck - limiting throughput
        </v-tooltip>
      </template>

      <!-- Donor indicator -->
      <template v-slot:item.is_donor="{ item }">
        <v-tooltip v-if="item.is_donor" location="top">
          <template v-slot:activator="{ props }">
            <v-icon v-bind="props" color="success">mdi-account-arrow-right</v-icon>
          </template>
          Donor - can share operators
        </v-tooltip>
      </template>

      <!-- Utilization progress bar -->
      <template v-slot:item.util_pct="{ item }">
        <v-progress-linear
          :model-value="item.util_pct"
          :color="getUtilColor(item.util_pct)"
          height="20"
          rounded
        >
          <template v-slot:default>
            <span class="text-caption font-weight-bold">{{ item.util_pct.toFixed(1) }}%</span>
          </template>
        </v-progress-linear>
      </template>

      <!-- Queue wait time -->
      <template v-slot:item.queue_wait_time_min="{ item }">
        <span :class="getQueueWaitClass(item.queue_wait_time_min)">
          {{ item.queue_wait_time_min.toFixed(2) }} min
        </span>
      </template>

      <!-- Row highlighting -->
      <template v-slot:item="{ item, columns }">
        <tr :class="getRowClass(item)">
          <td v-for="column in columns" :key="column.key">
            <template v-if="column.key === 'is_bottleneck'">
              <v-tooltip v-if="item.is_bottleneck" location="top">
                <template v-slot:activator="{ props }">
                  <v-icon v-bind="props" color="error">mdi-alert-circle</v-icon>
                </template>
                Bottleneck - limiting throughput
              </v-tooltip>
            </template>
            <template v-else-if="column.key === 'is_donor'">
              <v-tooltip v-if="item.is_donor" location="top">
                <template v-slot:activator="{ props }">
                  <v-icon v-bind="props" color="success">mdi-account-arrow-right</v-icon>
                </template>
                Donor - can share operators
              </v-tooltip>
            </template>
            <template v-else-if="column.key === 'util_pct'">
              <v-progress-linear
                :model-value="item.util_pct"
                :color="getUtilColor(item.util_pct)"
                height="20"
                rounded
              >
                <template v-slot:default>
                  <span class="text-caption font-weight-bold">{{ item.util_pct.toFixed(1) }}%</span>
                </template>
              </v-progress-linear>
            </template>
            <template v-else-if="column.key === 'queue_wait_time_min'">
              <span :class="getQueueWaitClass(item.queue_wait_time_min)">
                {{ item.queue_wait_time_min.toFixed(2) }} min
              </span>
            </template>
            <template v-else>
              {{ item[column.key] }}
            </template>
          </td>
        </tr>
      </template>
    </v-data-table>

    <!-- Cards View -->
    <v-row v-else>
      <v-col
        v-for="station in filteredStations"
        :key="`${station.product}-${station.step}`"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <v-card
          :variant="station.is_bottleneck ? 'tonal' : 'outlined'"
          :color="station.is_bottleneck ? 'error' : undefined"
          class="h-100"
        >
          <v-card-title class="d-flex align-center text-subtitle-1 pb-0">
            <span>{{ station.operation }}</span>
            <v-spacer />
            <v-icon v-if="station.is_bottleneck" color="error" size="small">mdi-alert-circle</v-icon>
            <v-icon v-if="station.is_donor" color="success" size="small">mdi-account-arrow-right</v-icon>
          </v-card-title>
          <v-card-subtitle>
            {{ station.product }} · Step {{ station.step }} · {{ station.machine_tool }}
          </v-card-subtitle>
          <v-card-text class="pt-2">
            <div class="mb-3">
              <div class="d-flex justify-space-between mb-1">
                <span class="text-caption">Utilization</span>
                <span class="text-caption font-weight-bold">{{ station.util_pct.toFixed(1) }}%</span>
              </div>
              <v-progress-linear
                :model-value="station.util_pct"
                :color="getUtilColor(station.util_pct)"
                height="8"
                rounded
              />
            </div>
            <v-row dense>
              <v-col cols="6">
                <div class="text-caption text-medium-emphasis">Operators</div>
                <div class="font-weight-bold">{{ station.operators }}</div>
              </v-col>
              <v-col cols="6">
                <div class="text-caption text-medium-emphasis">Queue Wait</div>
                <div class="font-weight-bold" :class="getQueueWaitClass(station.queue_wait_time_min)">
                  {{ station.queue_wait_time_min.toFixed(1) }} min
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Empty state -->
    <v-alert
      v-if="filteredStations.length === 0"
      type="info"
      variant="tonal"
      class="mt-4"
    >
      No stations match the current filter criteria.
    </v-alert>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  stations: {
    type: Array,
    required: true,
    default: () => []
  }
})

// View state
const searchQuery = ref('')
const productFilter = ref(null)
const statusFilter = ref(null)
const viewMode = ref('table')

// Table headers
const headers = [
  { title: 'Product', key: 'product', width: 100 },
  { title: 'Step', key: 'step', width: 60 },
  { title: 'Operation', key: 'operation' },
  { title: 'Machine/Tool', key: 'machine_tool' },
  { title: 'Operators', key: 'operators', width: 80 },
  { title: 'Utilization', key: 'util_pct', width: 150 },
  { title: 'Queue Wait', key: 'queue_wait_time_min', width: 100 },
  { title: 'BN', key: 'is_bottleneck', width: 50 },
  { title: 'DN', key: 'is_donor', width: 50 }
]

// Computed properties
const bottlenecks = computed(() =>
  props.stations.filter(s => s.is_bottleneck)
)

const donors = computed(() =>
  props.stations.filter(s => s.is_donor)
)

const avgUtilization = computed(() => {
  if (props.stations.length === 0) return 0
  const sum = props.stations.reduce((acc, s) => acc + s.util_pct, 0)
  return (sum / props.stations.length).toFixed(1)
})

const productOptions = computed(() => {
  const products = [...new Set(props.stations.map(s => s.product))]
  return [{ title: 'All Products', value: null }, ...products.map(p => ({ title: p, value: p }))]
})

const statusOptions = [
  { title: 'All Status', value: null },
  { title: 'Bottleneck', value: 'bottleneck' },
  { title: 'Donor', value: 'donor' },
  { title: 'High Utilization (>80%)', value: 'high' },
  { title: 'Low Utilization (<50%)', value: 'low' }
]

const filteredStations = computed(() => {
  let result = [...props.stations]

  // Product filter
  if (productFilter.value) {
    result = result.filter(s => s.product === productFilter.value)
  }

  // Status filter
  if (statusFilter.value) {
    switch (statusFilter.value) {
      case 'bottleneck':
        result = result.filter(s => s.is_bottleneck)
        break
      case 'donor':
        result = result.filter(s => s.is_donor)
        break
      case 'high':
        result = result.filter(s => s.util_pct > 80)
        break
      case 'low':
        result = result.filter(s => s.util_pct < 50)
        break
    }
  }

  return result
})

// Helper functions
const getUtilColor = (util) => {
  if (util >= 95) return 'error'
  if (util >= 80) return 'warning'
  if (util <= 50) return 'info'
  return 'success'
}

const getQueueWaitClass = (wait) => {
  if (wait > 5) return 'text-error'
  if (wait > 2) return 'text-warning'
  return ''
}

const getRowClass = (item) => {
  if (item.is_bottleneck) return 'bg-error-lighten-5'
  if (item.is_donor) return 'bg-success-lighten-5'
  return ''
}
</script>

<style scoped>
.station-performance-view {
  padding: 0;
}

.bg-error-lighten-5 {
  background-color: rgba(var(--v-theme-error), 0.05) !important;
}

.bg-success-lighten-5 {
  background-color: rgba(var(--v-theme-success), 0.05) !important;
}
</style>
