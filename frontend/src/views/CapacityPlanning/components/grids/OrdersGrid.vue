<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-clipboard-list</v-icon>
      Orders
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" class="mr-2" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        Add Order
      </v-btn>
      <v-btn size="small" variant="outlined" @click="showImportDialog = true">
        <v-icon start>mdi-upload</v-icon>
        Import CSV
      </v-btn>
    </v-card-title>
    <v-card-text>
      <v-data-table
        :headers="headers"
        :items="orders"
        :items-per-page="10"
        class="elevation-1"
        density="compact"
      >
        <template v-slot:item.order_number="{ item, index }">
          <v-text-field
            v-model="item.order_number"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.customer_name="{ item, index }">
          <v-text-field
            v-model="item.customer_name"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.style_code="{ item, index }">
          <v-text-field
            v-model="item.style_code"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.order_quantity="{ item, index }">
          <v-text-field
            v-model.number="item.order_quantity"
            type="number"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.required_date="{ item, index }">
          <v-text-field
            v-model="item.required_date"
            type="date"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.priority="{ item, index }">
          <v-select
            v-model="item.priority"
            :items="priorityOptions"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
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

        <template v-slot:item.actions="{ index }">
          <v-btn
            icon="mdi-content-copy"
            size="x-small"
            variant="text"
            @click="duplicateRow(index)"
          />
          <v-btn
            icon="mdi-delete"
            size="x-small"
            variant="text"
            color="error"
            @click="removeRow(index)"
          />
        </template>
      </v-data-table>

      <div v-if="!orders.length" class="text-center pa-4 text-grey">
        No orders yet. Click "Add Order" to create one or import from CSV.
      </div>
    </v-card-text>

    <!-- CSV Import Dialog -->
    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>Import Orders from CSV</v-card-title>
        <v-card-text>
          <v-textarea
            v-model="csvData"
            label="Paste CSV data"
            rows="10"
            variant="outlined"
            placeholder="order_number,customer_name,style_code,order_quantity,required_date"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="importCSV">Import</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const store = useCapacityPlanningStore()

const showImportDialog = ref(false)
const csvData = ref('')

const headers = [
  { title: 'Order #', key: 'order_number', width: '120px' },
  { title: 'Customer', key: 'customer_name', width: '150px' },
  { title: 'Style', key: 'style_code', width: '100px' },
  { title: 'Quantity', key: 'order_quantity', width: '100px' },
  { title: 'Required Date', key: 'required_date', width: '140px' },
  { title: 'Priority', key: 'priority', width: '120px' },
  { title: 'Status', key: 'status', width: '100px' },
  { title: 'Actions', key: 'actions', width: '100px', sortable: false }
]

const priorityOptions = ['CRITICAL', 'HIGH', 'NORMAL', 'LOW']

const orders = computed(() => store.worksheets.orders.data)

const getStatusColor = (status) => {
  const colors = {
    DRAFT: 'grey',
    CONFIRMED: 'blue',
    IN_PROGRESS: 'orange',
    COMPLETED: 'green',
    CANCELLED: 'red'
  }
  return colors[status] || 'grey'
}

const addRow = () => store.addRow('orders')
const removeRow = (index) => store.removeRow('orders', index)
const duplicateRow = (index) => store.duplicateRow('orders', index)
const markDirty = () => {
  store.worksheets.orders.dirty = true
}

const importCSV = () => {
  if (!csvData.value.trim()) return

  const lines = csvData.value.trim().split('\n')
  const headerLine = lines[0].split(',').map(h => h.trim())

  const data = lines.slice(1).map(line => {
    const values = line.split(',').map(v => v.trim())
    const row = {}
    headerLine.forEach((h, i) => {
      row[h] = values[i] || ''
    })
    // Convert quantity to number
    if (row.order_quantity) {
      row.order_quantity = parseInt(row.order_quantity) || 0
    }
    row.status = 'DRAFT'
    row.priority = row.priority || 'NORMAL'
    return row
  })

  store.importData('orders', data)
  showImportDialog.value = false
  csvData.value = ''
}
</script>
