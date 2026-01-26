<template>
  <div class="workflow-step-production">
    <!-- Production Summary -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-primary">{{ totalProduced }}</div>
          <div class="text-caption text-grey">Units Produced</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-info">{{ totalTarget }}</div>
          <div class="text-caption text-grey">Target Units</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4" :class="efficiencyColor">{{ efficiency }}%</div>
          <div class="text-caption text-grey">Efficiency</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4" :class="pendingEntries > 0 ? 'text-warning' : 'text-success'">
            {{ pendingEntries }}
          </div>
          <div class="text-caption text-grey">Pending Entries</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Work Orders with Pending Production -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-clipboard-list</v-icon>
        Work Orders - Final Production Count
      </v-card-title>

      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="loading" type="table-tbody" />
        <v-data-table
          v-else
          :headers="headers"
          :items="workOrders"
          :items-per-page="-1"
          density="compact"
          class="production-table"
        >
          <template v-slot:item.status="{ item }">
            <v-chip
              :color="getStatusColor(item)"
              size="x-small"
              variant="flat"
            >
              {{ item.hasEntry ? 'Entered' : 'Pending' }}
            </v-chip>
          </template>

          <template v-slot:item.produced="{ item }">
            <v-text-field
              v-model.number="item.produced"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              single-line
              :disabled="item.hasEntry"
              style="max-width: 100px"
              @update:model-value="updateEntry(item)"
            />
          </template>

          <template v-slot:item.defects="{ item }">
            <v-text-field
              v-model.number="item.defects"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              single-line
              :disabled="item.hasEntry"
              style="max-width: 80px"
              @update:model-value="updateEntry(item)"
            />
          </template>

          <template v-slot:item.efficiency="{ item }">
            <v-chip
              :color="getEfficiencyColor(item.efficiency)"
              size="small"
              variant="tonal"
            >
              {{ item.efficiency }}%
            </v-chip>
          </template>

          <template v-slot:item.actions="{ item }">
            <v-btn
              v-if="!item.hasEntry && item.produced > 0"
              size="small"
              color="primary"
              variant="elevated"
              @click="submitEntry(item)"
              :loading="item.submitting"
            >
              Submit
            </v-btn>
            <v-icon v-else-if="item.hasEntry" color="success" size="20">
              mdi-check-circle
            </v-icon>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>

    <!-- Quick Entry for Remaining -->
    <v-card
      v-if="pendingWorkOrders.length > 0"
      variant="outlined"
      class="mb-4"
    >
      <v-card-title class="d-flex align-center bg-warning-lighten-4 py-2">
        <v-icon class="mr-2" size="20" color="warning">mdi-alert</v-icon>
        Quick Entry for Pending Work Orders
      </v-card-title>
      <v-card-text>
        <v-alert type="info" variant="tonal" density="compact" class="mb-3">
          Enter production counts for remaining work orders or mark as zero if no production occurred.
        </v-alert>

        <v-btn
          color="warning"
          variant="outlined"
          @click="markRemainingZero"
          :disabled="pendingWorkOrders.length === 0"
        >
          <v-icon start>mdi-numeric-0-circle</v-icon>
          Mark Remaining as Zero Production
        </v-btn>
      </v-card-text>
    </v-card>

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :disabled="pendingEntries > 0"
      label="All production entries have been submitted for this shift"
      color="primary"
      @update:model-value="handleConfirm"
    />

    <v-alert
      v-if="pendingEntries > 0"
      type="warning"
      variant="tonal"
      density="compact"
      class="mt-2"
    >
      {{ pendingEntries }} work order(s) still need production entries before proceeding.
    </v-alert>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

const emit = defineEmits(['complete', 'update'])

// State
const loading = ref(true)
const confirmed = ref(false)
const workOrders = ref([])

// Table headers
const headers = [
  { title: 'Work Order', key: 'id', width: '120px' },
  { title: 'Product', key: 'product' },
  { title: 'Status', key: 'status', width: '90px' },
  { title: 'Produced', key: 'produced', width: '120px' },
  { title: 'Defects', key: 'defects', width: '100px' },
  { title: 'Efficiency', key: 'efficiency', width: '100px' },
  { title: '', key: 'actions', width: '100px', sortable: false }
]

// Computed
const totalProduced = computed(() => {
  return workOrders.value.reduce((sum, wo) => sum + (wo.produced || 0), 0)
})

const totalTarget = computed(() => {
  return workOrders.value.reduce((sum, wo) => sum + wo.target, 0)
})

const efficiency = computed(() => {
  if (totalTarget.value === 0) return 0
  return Math.round((totalProduced.value / totalTarget.value) * 100)
})

const efficiencyColor = computed(() => {
  if (efficiency.value >= 95) return 'text-success'
  if (efficiency.value >= 85) return 'text-warning'
  return 'text-error'
})

const pendingEntries = computed(() => {
  return workOrders.value.filter(wo => !wo.hasEntry).length
})

const pendingWorkOrders = computed(() => {
  return workOrders.value.filter(wo => !wo.hasEntry)
})

// Methods
const getStatusColor = (item) => {
  return item.hasEntry ? 'success' : 'warning'
}

const getEfficiencyColor = (eff) => {
  if (eff >= 95) return 'success'
  if (eff >= 85) return 'warning'
  return 'error'
}

const updateEntry = (item) => {
  // Calculate efficiency
  if (item.target > 0) {
    item.efficiency = Math.round(((item.produced || 0) / item.target) * 100)
  }
  emitUpdate()
}

const submitEntry = async (item) => {
  item.submitting = true
  try {
    await api.post('/production-entries', {
      work_order_id: item.id,
      quantity_produced: item.produced,
      defect_quantity: item.defects || 0,
      date: new Date().toISOString().split('T')[0]
    })
    item.hasEntry = true
    emitUpdate()
  } catch (error) {
    console.error('Failed to submit production entry:', error)
  } finally {
    item.submitting = false
  }
}

const markRemainingZero = async () => {
  for (const wo of pendingWorkOrders.value) {
    wo.produced = 0
    wo.defects = 0
    wo.efficiency = 0
    await submitEntry(wo)
  }
}

const emitUpdate = () => {
  emit('update', {
    workOrders: workOrders.value,
    totalProduced: totalProduced.value,
    efficiency: efficiency.value,
    isValid: confirmed.value && pendingEntries.value === 0
  })
}

const handleConfirm = (value) => {
  if (value && pendingEntries.value === 0) {
    emit('complete', {
      workOrders: workOrders.value,
      totalProduced: totalProduced.value,
      totalTarget: totalTarget.value,
      efficiency: efficiency.value
    })
  }
  emitUpdate()
}

const fetchData = async () => {
  loading.value = true
  try {
    const response = await api.get('/work-orders/shift-production')
    workOrders.value = response.data.map(wo => ({
      ...wo,
      produced: wo.produced || 0,
      defects: wo.defects || 0,
      efficiency: wo.efficiency || 0,
      hasEntry: wo.hasEntry || false,
      submitting: false
    }))
  } catch (error) {
    console.error('Failed to fetch production data:', error)
    // Mock data
    workOrders.value = [
      { id: 'WO-2024-001', product: 'Widget A', target: 500, produced: 485, defects: 3, efficiency: 97, hasEntry: true, submitting: false },
      { id: 'WO-2024-002', product: 'Widget B', target: 1000, produced: 920, defects: 8, efficiency: 92, hasEntry: true, submitting: false },
      { id: 'WO-2024-003', product: 'Gadget X', target: 300, produced: 0, defects: 0, efficiency: 0, hasEntry: false, submitting: false },
      { id: 'WO-2024-004', product: 'Component C', target: 200, produced: 195, defects: 1, efficiency: 98, hasEntry: true, submitting: false },
      { id: 'WO-2024-005', product: 'Assembly D', target: 750, produced: 0, defects: 0, efficiency: 0, hasEntry: false, submitting: false }
    ]
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.production-table :deep(.v-data-table__td) {
  padding: 8px 16px;
}
</style>
