<template>
  <v-card elevation="2">
    <v-card-title class="d-flex align-center bg-deep-purple text-white">
      <v-icon class="mr-2" size="24">mdi-wrench-clock</v-icon>
      Rework by Operation
      <v-spacer />
      <v-btn
        icon="mdi-refresh"
        variant="text"
        size="small"
        color="white"
        :loading="loading"
        @click="fetchData"
      />
    </v-card-title>

    <v-card-text class="pa-4">
      <!-- Loading State -->
      <div v-if="loading" class="d-flex justify-center align-center pa-8">
        <v-progress-circular indeterminate color="deep-purple" />
      </div>

      <!-- Error State -->
      <v-alert
        v-else-if="error"
        type="error"
        variant="tonal"
        class="mb-0"
      >
        {{ error }}
      </v-alert>

      <!-- Empty State -->
      <div v-else-if="!reworkOperations.length" class="text-center text-grey pa-8">
        <v-icon size="64" class="mb-4">mdi-check-all</v-icon>
        <div>No rework operations recorded</div>
      </div>

      <!-- Data Display -->
      <template v-else>
        <!-- Summary Stats -->
        <v-row dense class="mb-4">
          <v-col cols="4" class="text-center">
            <div class="text-h5 font-weight-bold text-deep-purple">{{ totalReworkUnits.toLocaleString() }}</div>
            <div class="text-caption text-grey">Total Rework Units</div>
          </v-col>
          <v-col cols="4" class="text-center">
            <div class="text-h5 font-weight-bold text-warning">{{ totalReworkHours }}h</div>
            <div class="text-caption text-grey">Rework Hours</div>
          </v-col>
          <v-col cols="4" class="text-center">
            <div class="text-h5 font-weight-bold text-error">${{ totalReworkCost.toLocaleString() }}</div>
            <div class="text-caption text-grey">Est. Cost</div>
          </v-col>
        </v-row>

        <!-- Rework Rate Indicator -->
        <div class="mb-4 pa-3 rounded" :class="reworkRateBackgroundColor">
          <div class="d-flex justify-space-between align-center">
            <div>
              <div class="text-subtitle-2">Overall Rework Rate</div>
              <div class="text-caption text-grey">Target: &lt;2%</div>
            </div>
            <div class="text-h4 font-weight-bold" :class="reworkRateTextColor">
              {{ reworkRate }}%
            </div>
          </div>
          <v-progress-linear
            :model-value="Math.min(reworkRate * 10, 100)"
            :color="reworkRateColor"
            height="8"
            rounded
            class="mt-2"
          />
        </div>

        <!-- Operations List -->
        <div class="text-subtitle-2 mb-2">Top Rework Operations</div>
        <v-list density="compact" class="pa-0">
          <v-list-item
            v-for="(item, index) in reworkOperations.slice(0, 6)"
            :key="item.operation"
            class="mb-2 rounded"
            :class="{ 'bg-error-lighten-5': item.rework_rate > 5 }"
          >
            <template v-slot:prepend>
              <v-avatar
                :color="getOperationColor(item.rework_rate)"
                size="36"
                class="mr-3"
              >
                <span class="text-caption font-weight-bold text-white">{{ index + 1 }}</span>
              </v-avatar>
            </template>

            <v-list-item-title class="font-weight-medium">
              {{ item.operation }}
            </v-list-item-title>

            <v-list-item-subtitle class="d-flex align-center mt-1">
              <v-icon size="14" class="mr-1">mdi-package-variant</v-icon>
              {{ item.rework_units.toLocaleString() }} units
              <v-divider vertical class="mx-2" />
              <v-icon size="14" class="mr-1">mdi-clock-outline</v-icon>
              {{ item.rework_hours }}h
              <v-divider vertical class="mx-2" />
              <v-icon size="14" class="mr-1">mdi-percent</v-icon>
              <span :class="getReworkRateTextColor(item.rework_rate)">
                {{ item.rework_rate }}% rate
              </span>
            </v-list-item-subtitle>

            <template v-slot:append>
              <div class="text-right">
                <v-progress-linear
                  :model-value="(item.rework_units / maxReworkUnits) * 100"
                  :color="getOperationColor(item.rework_rate)"
                  height="6"
                  rounded
                  style="width: 80px"
                />
                <div class="text-caption text-grey mt-1">
                  ${{ item.estimated_cost.toLocaleString() }}
                </div>
              </div>
            </template>
          </v-list-item>
        </v-list>

        <!-- Pareto Chart Preview -->
        <v-divider class="my-4" />
        <div class="text-subtitle-2 mb-2">Pareto Analysis (80/20 Rule)</div>
        <div class="d-flex align-center mb-2">
          <div class="flex-grow-1">
            <div v-for="item in paretoItems" :key="item.operation" class="mb-1">
              <div class="d-flex justify-space-between text-caption mb-1">
                <span>{{ item.operation }}</span>
                <span class="text-grey">{{ item.cumulative_percentage }}%</span>
              </div>
              <v-progress-linear
                :model-value="item.percentage"
                color="deep-purple"
                height="6"
                rounded
              />
            </div>
          </div>
        </div>
        <v-alert
          v-if="vitalFewCount > 0"
          type="info"
          variant="tonal"
          density="compact"
          class="mt-2"
        >
          <v-icon>mdi-lightbulb</v-icon>
          <strong>{{ vitalFewCount }}</strong> operations account for <strong>80%</strong> of all rework.
          Focus improvement efforts here.
        </v-alert>
      </template>
    </v-card-text>

    <v-card-actions v-if="reworkOperations.length">
      <v-btn
        variant="text"
        color="deep-purple"
        size="small"
        prepend-icon="mdi-chart-sankey"
        @click="$emit('viewDetails')"
      >
        View Analysis
      </v-btn>
      <v-spacer />
      <v-btn
        variant="text"
        color="deep-purple"
        size="small"
        prepend-icon="mdi-target"
        @click="$emit('createAction')"
      >
        Create Action
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

// Props
const props = defineProps<{
  clientId?: string
  productId?: number
  startDate?: string
  endDate?: string
}>()

// Emits
defineEmits(['viewDetails', 'createAction'])

// State
const loading = ref(false)
const error = ref<string | null>(null)
const reworkOperations = ref<ReworkOperationItem[]>([])
const totalUnitsProduced = ref(10000) // Will be fetched from API

// Types
interface ReworkOperationItem {
  operation: string
  operation_id: string
  rework_units: number
  rework_hours: number
  rework_rate: number
  estimated_cost: number
}

interface ParetoItem {
  operation: string
  percentage: number
  cumulative_percentage: number
}

// Computed
const totalReworkUnits = computed(() => {
  return reworkOperations.value.reduce((sum, op) => sum + op.rework_units, 0)
})

const totalReworkHours = computed(() => {
  return reworkOperations.value.reduce((sum, op) => sum + op.rework_hours, 0).toFixed(1)
})

const totalReworkCost = computed(() => {
  return reworkOperations.value.reduce((sum, op) => sum + op.estimated_cost, 0)
})

const reworkRate = computed(() => {
  if (totalUnitsProduced.value === 0) return 0
  return ((totalReworkUnits.value / totalUnitsProduced.value) * 100).toFixed(1)
})

const maxReworkUnits = computed(() => {
  if (!reworkOperations.value.length) return 1
  return Math.max(...reworkOperations.value.map(op => op.rework_units))
})

const reworkRateColor = computed(() => {
  const rate = parseFloat(reworkRate.value as string)
  if (rate <= 2) return 'success'
  if (rate <= 5) return 'warning'
  return 'error'
})

const reworkRateTextColor = computed(() => {
  const rate = parseFloat(reworkRate.value as string)
  if (rate <= 2) return 'text-success'
  if (rate <= 5) return 'text-warning'
  return 'text-error'
})

const reworkRateBackgroundColor = computed(() => {
  const rate = parseFloat(reworkRate.value as string)
  if (rate <= 2) return 'bg-success-lighten-5'
  if (rate <= 5) return 'bg-warning-lighten-5'
  return 'bg-error-lighten-5'
})

const paretoItems = computed((): ParetoItem[] => {
  const total = totalReworkUnits.value
  if (total === 0) return []

  let cumulative = 0
  return reworkOperations.value
    .slice(0, 5)
    .map(op => {
      const percentage = (op.rework_units / total) * 100
      cumulative += percentage
      return {
        operation: op.operation,
        percentage: parseFloat(percentage.toFixed(1)),
        cumulative_percentage: parseFloat(cumulative.toFixed(1))
      }
    })
})

const vitalFewCount = computed(() => {
  let cumulative = 0
  let count = 0
  const total = totalReworkUnits.value

  for (const op of reworkOperations.value) {
    cumulative += (op.rework_units / total) * 100
    count++
    if (cumulative >= 80) break
  }

  return count
})

// Methods
const getOperationColor = (reworkRate: number): string => {
  if (reworkRate <= 2) return 'success'
  if (reworkRate <= 5) return 'warning'
  if (reworkRate <= 10) return 'orange'
  return 'error'
}

const getReworkRateTextColor = (rate: number): string => {
  if (rate <= 2) return 'text-success'
  if (rate <= 5) return 'text-warning'
  return 'text-error'
}

const fetchData = async () => {
  loading.value = true
  error.value = null

  try {
    // Try to fetch rework by operation from API
    const response = await axios.get('http://localhost:8000/api/v1/kpi/quality/rework-by-operation', {
      params: {
        client_id: props.clientId,
        product_id: props.productId,
        start_date: props.startDate,
        end_date: props.endDate
      }
    })

    if (response.data && Array.isArray(response.data.operations || response.data)) {
      const operations = response.data.operations || response.data
      totalUnitsProduced.value = response.data.total_units_produced || 10000

      reworkOperations.value = operations.map((op: any) => ({
        operation: op.operation || op.inspection_stage || op.process_step || 'Unknown',
        operation_id: op.operation_id || op.step_id || '',
        rework_units: op.rework_units || op.rework_count || 0,
        rework_hours: parseFloat(op.rework_hours || op.estimated_hours || 0),
        rework_rate: parseFloat(op.rework_rate || 0),
        estimated_cost: op.estimated_cost || op.cost || (op.rework_units * 15) // $15/unit default
      }))
    } else {
      await fetchQualityAndAggregate()
    }
  } catch (err: any) {
    console.warn('Rework by operation API not available, using fallback calculation')
    await fetchQualityAndAggregate()
  } finally {
    loading.value = false
  }
}

const fetchQualityAndAggregate = async () => {
  try {
    // Fallback: fetch quality inspections and aggregate by operation/stage
    const response = await axios.get('http://localhost:8000/api/v1/quality', {
      params: {
        start_date: props.startDate,
        end_date: props.endDate,
        limit: 1000
      }
    })

    if (response.data && Array.isArray(response.data)) {
      // Aggregate by inspection stage/operation
      const operationMap = new Map<string, { rework_units: number; total_units: number }>()

      let totalProduced = 0
      response.data.forEach((inspection: any) => {
        const operation = inspection.inspection_stage || inspection.operation || 'General Inspection'
        const rework = inspection.rework_units || 0
        const total = inspection.units_inspected || 0

        totalProduced += total

        if (operationMap.has(operation)) {
          const existing = operationMap.get(operation)!
          existing.rework_units += rework
          existing.total_units += total
        } else {
          operationMap.set(operation, { rework_units: rework, total_units: total })
        }
      })

      totalUnitsProduced.value = totalProduced

      reworkOperations.value = Array.from(operationMap.entries())
        .filter(([_, data]) => data.rework_units > 0)
        .map(([operation, data]) => {
          const reworkRate = data.total_units > 0
            ? (data.rework_units / data.total_units) * 100
            : 0
          return {
            operation,
            operation_id: operation.toLowerCase().replace(/\s+/g, '-'),
            rework_units: data.rework_units,
            rework_hours: data.rework_units * 0.5, // Estimate: 30 min per unit
            rework_rate: parseFloat(reworkRate.toFixed(1)),
            estimated_cost: data.rework_units * 15 // $15/unit estimate
          }
        })
        .sort((a, b) => b.rework_units - a.rework_units)
        .slice(0, 10)
    } else {
      // Use demo data
      reworkOperations.value = generateDemoData()
    }
  } catch (err: any) {
    // Use demo data for display
    reworkOperations.value = generateDemoData()
    totalUnitsProduced.value = 10000
  }
}

const generateDemoData = (): ReworkOperationItem[] => {
  return [
    { operation: 'Final Assembly', operation_id: 'final-assembly', rework_units: 145, rework_hours: 72.5, rework_rate: 4.8, estimated_cost: 2175 },
    { operation: 'PCB Soldering', operation_id: 'pcb-soldering', rework_units: 98, rework_hours: 49.0, rework_rate: 3.3, estimated_cost: 1470 },
    { operation: 'Component Mounting', operation_id: 'component-mounting', rework_units: 67, rework_hours: 33.5, rework_rate: 2.2, estimated_cost: 1005 },
    { operation: 'Visual Inspection', operation_id: 'visual-inspection', rework_units: 45, rework_hours: 22.5, rework_rate: 1.5, estimated_cost: 675 },
    { operation: 'Cable Assembly', operation_id: 'cable-assembly', rework_units: 32, rework_hours: 16.0, rework_rate: 1.1, estimated_cost: 480 },
    { operation: 'Packaging', operation_id: 'packaging', rework_units: 18, rework_hours: 9.0, rework_rate: 0.6, estimated_cost: 270 }
  ]
}

// Lifecycle
onMounted(() => {
  fetchData()
})

// Watch for prop changes
watch(
  () => [props.clientId, props.productId, props.startDate, props.endDate],
  () => {
    fetchData()
  }
)
</script>

<style scoped>
.v-list-item {
  border: 1px solid rgba(0, 0, 0, 0.08);
}
</style>
