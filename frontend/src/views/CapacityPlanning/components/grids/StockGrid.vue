<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-package-variant</v-icon>
      Stock Snapshot
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" class="mr-2" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        Add Item
      </v-btn>
      <v-btn size="small" variant="outlined" @click="showImportDialog = true">
        <v-icon start>mdi-upload</v-icon>
        Import Stock
      </v-btn>
    </v-card-title>
    <v-card-text>
      <!-- Staleness Warning -->
      <v-alert
        v-if="stalenessWarning"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-3"
        closable
      >
        <v-icon start>mdi-clock-alert</v-icon>
        {{ stalenessWarning }}
      </v-alert>

      <!-- Summary Stats -->
      <v-row v-if="stock.length" class="mb-3">
        <v-col cols="3">
          <v-card variant="tonal" color="primary">
            <v-card-text class="text-center">
              <div class="text-h6">{{ stock.length }}</div>
              <div class="text-caption">Total Items</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="success">
            <v-card-text class="text-center">
              <div class="text-h6">{{ totalOnHand.toLocaleString() }}</div>
              <div class="text-caption">On Hand</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="warning">
            <v-card-text class="text-center">
              <div class="text-h6">{{ totalAllocated.toLocaleString() }}</div>
              <div class="text-caption">Allocated</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="info">
            <v-card-text class="text-center">
              <div class="text-h6">{{ totalAvailable.toLocaleString() }}</div>
              <div class="text-caption">Available</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-data-table
        :headers="headers"
        :items="stock"
        :items-per-page="15"
        :search="searchTerm"
        class="elevation-1"
        density="compact"
      >
        <template v-slot:top>
          <v-text-field
            v-model="searchTerm"
            prepend-inner-icon="mdi-magnify"
            label="Search items..."
            variant="outlined"
            density="compact"
            class="ma-2"
            style="max-width: 300px"
            clearable
          />
        </template>

        <template v-slot:item.snapshot_date="{ item, index }">
          <v-text-field
            v-model="item.snapshot_date"
            type="date"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.item_code="{ item, index }">
          <v-text-field
            v-model="item.item_code"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.item_description="{ item, index }">
          <v-text-field
            v-model="item.item_description"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.on_hand_quantity="{ item, index }">
          <v-text-field
            v-model.number="item.on_hand_quantity"
            type="number"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="updateAvailable(item, index)"
          />
        </template>

        <template v-slot:item.allocated_quantity="{ item, index }">
          <v-text-field
            v-model.number="item.allocated_quantity"
            type="number"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="updateAvailable(item, index)"
          />
        </template>

        <template v-slot:item.on_order_quantity="{ item, index }">
          <v-text-field
            v-model.number="item.on_order_quantity"
            type="number"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.available_quantity="{ item }">
          <span :class="item.available_quantity < 0 ? 'text-error' : 'text-success'">
            {{ item.available_quantity }}
          </span>
        </template>

        <template v-slot:item.unit_of_measure="{ item, index }">
          <v-select
            v-model="item.unit_of_measure"
            :items="uomOptions"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.actions="{ index }">
          <v-btn
            icon="mdi-delete"
            size="x-small"
            variant="text"
            color="error"
            @click="removeRow(index)"
          />
        </template>
      </v-data-table>

      <div v-if="!stock.length" class="text-center pa-4 text-grey">
        No stock data. Add items or import a stock snapshot.
      </div>
    </v-card-text>

    <!-- Import Dialog -->
    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>Import Stock Snapshot</v-card-title>
        <v-card-text>
          <v-textarea
            v-model="csvData"
            label="Paste CSV data"
            rows="10"
            variant="outlined"
            placeholder="item_code,item_description,on_hand_quantity,allocated_quantity,on_order_quantity"
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
const searchTerm = ref('')

const headers = [
  { title: 'Date', key: 'snapshot_date', width: '120px' },
  { title: 'Item Code', key: 'item_code', width: '120px' },
  { title: 'Description', key: 'item_description', width: '200px' },
  { title: 'On Hand', key: 'on_hand_quantity', width: '100px' },
  { title: 'Allocated', key: 'allocated_quantity', width: '100px' },
  { title: 'On Order', key: 'on_order_quantity', width: '100px' },
  { title: 'Available', key: 'available_quantity', width: '100px' },
  { title: 'UOM', key: 'unit_of_measure', width: '80px' },
  { title: 'Actions', key: 'actions', width: '80px', sortable: false }
]

const uomOptions = ['EA', 'M', 'YD', 'KG', 'LB', 'PC', 'SET']

const stock = computed(() => store.worksheets.stockSnapshot.data)

const stalenessWarning = computed(() => {
  if (!stock.value.length) return null
  const alertDays = store.worksheets.dashboardInputs.data.shortage_alert_days || 7
  const now = new Date()
  const dates = stock.value
    .map(s => s.snapshot_date)
    .filter(Boolean)
    .map(d => new Date(d))
  if (!dates.length) return null
  const mostRecent = new Date(Math.max(...dates))
  const daysSince = Math.floor((now - mostRecent) / (1000 * 60 * 60 * 24))
  if (daysSince > alertDays) {
    return `Stock snapshots are ${daysSince} days old (last: ${mostRecent.toISOString().slice(0, 10)}). Consider updating stock data before running MRP.`
  }
  return null
})

const totalOnHand = computed(() =>
  stock.value.reduce((sum, s) => sum + (parseInt(s.on_hand_quantity) || 0), 0)
)

const totalAllocated = computed(() =>
  stock.value.reduce((sum, s) => sum + (parseInt(s.allocated_quantity) || 0), 0)
)

const totalAvailable = computed(() =>
  stock.value.reduce((sum, s) => sum + (parseInt(s.available_quantity) || 0), 0)
)

const addRow = () => store.addRow('stockSnapshot')
const removeRow = (index) => store.removeRow('stockSnapshot', index)

const updateAvailable = (item, index) => {
  item.available_quantity = (item.on_hand_quantity || 0) - (item.allocated_quantity || 0)
  markDirty(index)
}

const markDirty = () => {
  store.worksheets.stockSnapshot.dirty = true
}

const importCSV = () => {
  if (!csvData.value.trim()) return

  const lines = csvData.value.trim().split('\n')
  const headerLine = lines[0].split(',').map(h => h.trim())

  const today = new Date().toISOString().slice(0, 10)

  const data = lines.slice(1).map(line => {
    const values = line.split(',').map(v => v.trim())
    const row = { snapshot_date: today, unit_of_measure: 'EA' }
    headerLine.forEach((h, i) => {
      row[h] = values[i] || ''
    })
    // Convert quantities to numbers
    row.on_hand_quantity = parseInt(row.on_hand_quantity) || 0
    row.allocated_quantity = parseInt(row.allocated_quantity) || 0
    row.on_order_quantity = parseInt(row.on_order_quantity) || 0
    row.available_quantity = row.on_hand_quantity - row.allocated_quantity
    return row
  })

  store.importData('stockSnapshot', data)
  showImportDialog.value = false
  csvData.value = ''
}
</script>
