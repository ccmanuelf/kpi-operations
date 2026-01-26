<template>
  <div class="workflow-step-targets">
    <!-- Shift Targets Summary -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-target</v-icon>
        Shift Production Targets
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-primary">{{ totalUnits }}</div>
              <div class="text-caption text-grey">Total Units</div>
            </div>
          </v-col>
          <v-col cols="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-info">{{ workOrders.length }}</div>
              <div class="text-caption text-grey">Work Orders</div>
            </div>
          </v-col>
          <v-col cols="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-warning">{{ highPriorityCount }}</div>
              <div class="text-caption text-grey">High Priority</div>
            </div>
          </v-col>
          <v-col cols="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-success">{{ targetEfficiency }}%</div>
              <div class="text-caption text-grey">Target Efficiency</div>
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Work Orders Table -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-clipboard-list</v-icon>
        Work Orders for This Shift
        <v-spacer />
        <v-chip size="small" variant="tonal" color="primary">
          {{ workOrders.length }} orders
        </v-chip>
      </v-card-title>

      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="loading" type="table-tbody" />
        <v-data-table
          v-else
          :headers="headers"
          :items="workOrders"
          :items-per-page="5"
          density="compact"
          class="work-orders-table"
        >
          <template v-slot:item.priority="{ item }">
            <v-chip
              :color="getPriorityColor(item.priority)"
              size="x-small"
              variant="flat"
            >
              {{ item.priority }}
            </v-chip>
          </template>

          <template v-slot:item.dueDate="{ item }">
            <span :class="{ 'text-error': isOverdue(item.dueDate) }">
              {{ formatDate(item.dueDate) }}
            </span>
          </template>

          <template v-slot:item.progress="{ item }">
            <div class="d-flex align-center">
              <v-progress-linear
                :model-value="item.progress"
                :color="getProgressColor(item.progress)"
                height="8"
                rounded
                style="width: 80px"
                class="mr-2"
              />
              <span class="text-caption">{{ item.progress }}%</span>
            </div>
          </template>

          <template v-slot:item.actions="{ item }">
            <v-btn
              icon
              size="x-small"
              variant="text"
              @click="viewWorkOrder(item)"
            >
              <v-icon size="16">mdi-eye</v-icon>
            </v-btn>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>

    <!-- Material Availability -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-package-variant</v-icon>
        Material Availability
      </v-card-title>
      <v-card-text>
        <v-alert
          v-if="materialShortages.length === 0"
          type="success"
          variant="tonal"
          density="compact"
        >
          <v-icon>mdi-check-circle</v-icon>
          All materials available for scheduled work orders
        </v-alert>

        <v-list v-else density="compact">
          <v-list-item
            v-for="shortage in materialShortages"
            :key="shortage.id"
            class="bg-red-lighten-5 mb-2 rounded"
          >
            <template v-slot:prepend>
              <v-icon color="error">mdi-alert</v-icon>
            </template>
            <v-list-item-title>{{ shortage.material }}</v-list-item-title>
            <v-list-item-subtitle>
              WO: {{ shortage.workOrder }} - Need {{ shortage.needed }}, Have {{ shortage.available }}
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Notes -->
    <v-textarea
      v-model="notes"
      label="Shift Planning Notes (Optional)"
      placeholder="Any notes about production priorities or special instructions..."
      variant="outlined"
      rows="3"
      class="mb-4"
      @update:model-value="handleNotesUpdate"
    />

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      label="I have reviewed the production targets and work order priorities"
      color="primary"
      @update:model-value="handleConfirm"
    />

    <!-- Work Order Detail Dialog -->
    <v-dialog v-model="showDetailDialog" max-width="600">
      <v-card v-if="selectedWorkOrder">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-clipboard-text</v-icon>
          Work Order: {{ selectedWorkOrder.id }}
        </v-card-title>
        <v-card-text>
          <v-simple-table density="compact">
            <tbody>
              <tr>
                <td class="text-grey">Product</td>
                <td>{{ selectedWorkOrder.product }}</td>
              </tr>
              <tr>
                <td class="text-grey">Customer</td>
                <td>{{ selectedWorkOrder.customer }}</td>
              </tr>
              <tr>
                <td class="text-grey">Target Quantity</td>
                <td>{{ selectedWorkOrder.targetQuantity }}</td>
              </tr>
              <tr>
                <td class="text-grey">Completed</td>
                <td>{{ selectedWorkOrder.completedQuantity }}</td>
              </tr>
              <tr>
                <td class="text-grey">Due Date</td>
                <td>{{ formatDate(selectedWorkOrder.dueDate) }}</td>
              </tr>
              <tr>
                <td class="text-grey">Priority</td>
                <td>
                  <v-chip :color="getPriorityColor(selectedWorkOrder.priority)" size="small">
                    {{ selectedWorkOrder.priority }}
                  </v-chip>
                </td>
              </tr>
            </tbody>
          </v-simple-table>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showDetailDialog = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

const emit = defineEmits(['complete', 'update'])

// State
const loading = ref(true)
const confirmed = ref(false)
const notes = ref('')
const workOrders = ref([])
const materialShortages = ref([])
const showDetailDialog = ref(false)
const selectedWorkOrder = ref(null)

// Table headers
const headers = [
  { title: 'Work Order', key: 'id', width: '120px' },
  { title: 'Product', key: 'product' },
  { title: 'Priority', key: 'priority', width: '100px' },
  { title: 'Target', key: 'targetQuantity', width: '80px' },
  { title: 'Due Date', key: 'dueDate', width: '100px' },
  { title: 'Progress', key: 'progress', width: '140px' },
  { title: '', key: 'actions', width: '50px', sortable: false }
]

// Computed
const totalUnits = computed(() => {
  return workOrders.value.reduce((sum, wo) => sum + (wo.targetQuantity - wo.completedQuantity), 0)
})

const highPriorityCount = computed(() => {
  return workOrders.value.filter(wo => wo.priority === 'High' || wo.priority === 'Critical').length
})

const targetEfficiency = computed(() => 85) // This would come from configuration

// Methods
const getPriorityColor = (priority) => {
  const colors = {
    Critical: 'error',
    High: 'warning',
    Medium: 'info',
    Low: 'grey'
  }
  return colors[priority] || 'grey'
}

const getProgressColor = (progress) => {
  if (progress >= 80) return 'success'
  if (progress >= 50) return 'info'
  if (progress >= 25) return 'warning'
  return 'error'
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const isOverdue = (dateString) => {
  if (!dateString) return false
  const date = new Date(dateString)
  return date < new Date()
}

const viewWorkOrder = (workOrder) => {
  selectedWorkOrder.value = workOrder
  showDetailDialog.value = true
}

const handleNotesUpdate = () => {
  emit('update', { notes: notes.value, isValid: confirmed.value })
}

const handleConfirm = (value) => {
  if (value) {
    emit('complete', {
      workOrders: workOrders.value,
      totalUnits: totalUnits.value,
      notes: notes.value
    })
  }
  emit('update', { isValid: value })
}

const fetchData = async () => {
  loading.value = true
  try {
    const [workOrdersRes, materialsRes] = await Promise.all([
      api.get('/work-orders/shift-queue'),
      api.get('/materials/availability')
    ])
    workOrders.value = workOrdersRes.data
    materialShortages.value = materialsRes.data.shortages || []
  } catch (error) {
    console.error('Failed to fetch targets data:', error)
    // Mock data for demonstration
    workOrders.value = [
      { id: 'WO-2024-001', product: 'Widget A', customer: 'ACME Corp', priority: 'High', targetQuantity: 500, completedQuantity: 0, dueDate: '2024-01-26', progress: 0 },
      { id: 'WO-2024-002', product: 'Widget B', customer: 'Tech Industries', priority: 'Critical', targetQuantity: 1000, completedQuantity: 250, dueDate: '2024-01-25', progress: 25 },
      { id: 'WO-2024-003', product: 'Gadget X', customer: 'Global Mfg', priority: 'Medium', targetQuantity: 300, completedQuantity: 150, dueDate: '2024-01-27', progress: 50 },
      { id: 'WO-2024-004', product: 'Component C', customer: 'ACME Corp', priority: 'Low', targetQuantity: 200, completedQuantity: 180, dueDate: '2024-01-28', progress: 90 },
      { id: 'WO-2024-005', product: 'Assembly D', customer: 'Quick Ship', priority: 'High', targetQuantity: 750, completedQuantity: 0, dueDate: '2024-01-26', progress: 0 }
    ]
    materialShortages.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.work-orders-table {
  border: none;
}

:deep(.v-data-table) {
  border-radius: 0;
}
</style>
