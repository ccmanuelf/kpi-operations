<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-check-decagram</v-icon>
      {{ t('capacityPlanning.componentCheck.title') }}
      <v-spacer />
      <v-btn
        color="primary"
        size="small"
        variant="elevated"
        :loading="store.isRunningMRP"
        @click="runCheck"
      >
        <v-icon start>mdi-play</v-icon>
        {{ t('capacityPlanning.componentCheck.runComponentCheck') }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <!-- Summary Cards -->
      <v-row v-if="components.length" class="mb-4">
        <v-col cols="4">
          <v-card variant="tonal" color="success">
            <v-card-text class="text-center">
              <div class="text-h4">{{ availableCount }}</div>
              <div class="text-subtitle-1">{{ t('capacityPlanning.stock.available') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="4">
          <v-card variant="tonal" color="warning">
            <v-card-text class="text-center">
              <div class="text-h4">{{ partialCount }}</div>
              <div class="text-subtitle-1">{{ t('capacityPlanning.componentCheck.partial') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="4">
          <v-card variant="tonal" color="error">
            <v-card-text class="text-center">
              <div class="text-h4">{{ shortageCount }}</div>
              <div class="text-subtitle-1">{{ t('capacityPlanning.componentCheck.shortage') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- MRP Error -->
      <v-alert v-if="store.mrpError" type="error" class="mb-4" closable>
        {{ store.mrpError }}
      </v-alert>

      <!-- Results Table -->
      <v-data-table
        v-if="components.length"
        :headers="headers"
        :items="components"
        :items-per-page="15"
        :search="searchTerm"
        class="elevation-1"
        density="compact"
      >
        <template v-slot:top>
          <div class="d-flex align-center pa-2">
            <v-text-field
              v-model="searchTerm"
              prepend-inner-icon="mdi-magnify"
              :label="t('capacityPlanning.componentCheck.searchComponents')"
              variant="outlined"
              density="compact"
              style="max-width: 300px"
              clearable
            />
            <v-spacer />
            <v-btn-toggle v-model="statusFilter" color="primary" variant="outlined" density="compact">
              <v-btn value="all">{{ t('common.all') }}</v-btn>
              <v-btn value="SHORTAGE" color="error">{{ t('capacityPlanning.componentCheck.filters.shortages') }}</v-btn>
              <v-btn value="PARTIAL" color="warning">{{ t('capacityPlanning.componentCheck.filters.partial') }}</v-btn>
            </v-btn-toggle>
          </div>
        </template>

        <template v-slot:item.status="{ item }">
          <v-chip
            :color="getStatusColor(item.status)"
            size="small"
            variant="tonal"
          >
            {{ item.status }}
          </v-chip>
        </template>

        <template v-slot:item.shortage_quantity="{ item }">
          <span :class="item.shortage_quantity > 0 ? 'text-error font-weight-bold' : ''">
            {{ item.shortage_quantity || 0 }}
          </span>
        </template>

        <template v-slot:item.required_quantity="{ item }">
          {{ item.required_quantity?.toLocaleString() }}
        </template>

        <template v-slot:item.available_quantity="{ item }">
          {{ item.available_quantity?.toLocaleString() }}
        </template>

        <template v-slot:item.planner_notes="{ item }">
          <v-text-field
            :model-value="item.planner_notes || ''"
            variant="plain"
            density="compact"
            hide-details
            :placeholder="t('capacityPlanning.componentCheck.addNote')"
            @update:modelValue="(val) => updatePlannerNote(item, val)"
          />
        </template>
      </v-data-table>

      <!-- Empty State -->
      <div v-else class="text-center pa-8 text-grey">
        <v-icon size="64" color="grey-lighten-1">mdi-check-decagram-outline</v-icon>
        <div class="text-h6 mt-4">{{ t('capacityPlanning.componentCheck.noResultsTitle') }}</div>
        <div class="text-body-2 mt-2">
          {{ t('capacityPlanning.componentCheck.noResultsDescription') }}
        </div>
        <v-btn
          color="primary"
          variant="tonal"
          class="mt-4"
          :loading="store.isRunningMRP"
          @click="runCheck"
        >
          {{ t('capacityPlanning.componentCheck.runComponentCheck') }}
        </v-btn>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
/**
 * ComponentCheckPanel - Material Requirements Planning (MRP) component check.
 *
 * Runs a component requirements check against current stock snapshots and BOMs
 * to identify material shortages. Displays summary cards (available, partial,
 * shortage counts), a filterable results table with search and status toggle,
 * and inline planner notes for each component. Errors from the MRP engine
 * are shown as dismissible alerts.
 *
 * Store dependency: useCapacityPlanningStore (worksheets.componentCheck)
 * No props or emits -- all state managed via store.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const { t } = useI18n()
const store = useCapacityPlanningStore()

const searchTerm = ref('')
const statusFilter = ref('all')

const headers = computed(() => [
  { title: t('capacityPlanning.componentCheck.headers.orderNumber'), key: 'order_number', width: '120px' },
  { title: t('capacityPlanning.componentCheck.headers.componentCode'), key: 'component_item_code', width: '150px' },
  { title: t('capacityPlanning.componentCheck.headers.description'), key: 'component_description', width: '200px' },
  { title: t('capacityPlanning.componentCheck.headers.required'), key: 'required_quantity', width: '100px' },
  { title: t('capacityPlanning.componentCheck.headers.available'), key: 'available_quantity', width: '100px' },
  { title: t('capacityPlanning.componentCheck.headers.shortage'), key: 'shortage_quantity', width: '100px' },
  { title: t('capacityPlanning.componentCheck.headers.status'), key: 'status', width: '100px' },
  { title: t('capacityPlanning.componentCheck.headers.plannerNotes'), key: 'planner_notes', width: '200px' }
])

const components = computed(() => {
  const data = store.worksheets.componentCheck.data
  if (statusFilter.value === 'all') return data
  return data.filter(c => c.status === statusFilter.value)
})

const availableCount = computed(() =>
  store.worksheets.componentCheck.data.filter(c => c.status === 'AVAILABLE').length
)

const partialCount = computed(() =>
  store.worksheets.componentCheck.data.filter(c => c.status === 'PARTIAL').length
)

const shortageCount = computed(() =>
  store.worksheets.componentCheck.data.filter(c => c.status === 'SHORTAGE').length
)

const getStatusColor = (status) => {
  const colors = {
    AVAILABLE: 'success',
    PARTIAL: 'warning',
    SHORTAGE: 'error'
  }
  return colors[status] || 'grey'
}

const updatePlannerNote = (item, value) => {
  const idx = store.worksheets.componentCheck.data.findIndex(c => c._id === item._id)
  if (idx !== -1) {
    store.updateCell('componentCheck', idx, 'planner_notes', value)
  }
}

const runCheck = async () => {
  try {
    await store.runComponentCheck()
  } catch (error) {
    console.error('Component check failed:', error)
  }
}
</script>
