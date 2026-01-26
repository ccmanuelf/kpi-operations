<template>
  <v-card role="region" aria-labelledby="data-entry-title">
    <v-card-title class="d-flex align-center flex-wrap ga-3">
      <span id="data-entry-title" class="text-h5">Production Data Entry</span>
      <v-spacer></v-spacer>
      <v-btn
        color="primary"
        @click="addNewEntry"
        aria-label="Add new production entry"
        prepend-icon="mdi-plus"
      >
        Add Entry
      </v-btn>
    </v-card-title>

    <v-card-text>
      <!-- Live region for announcing changes -->
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        class="sr-only"
      >
        {{ statusMessage }}
      </div>

      <!-- Loading Skeleton -->
      <TableSkeleton v-if="initialLoading" :rows="5" :columns="7" />

      <!-- Empty State -->
      <EmptyState
        v-else-if="!loading && entries.length === 0"
        variant="no-entries"
        title="No production entries yet"
        description="Start by adding your first production entry to track manufacturing output and efficiency metrics."
        action-text="Add First Entry"
        action-icon="mdi-plus"
        @action="addNewEntry"
      />

      <!-- Data Table -->
      <v-data-table
        v-else
        :headers="headers"
        :items="entries"
        :loading="loading"
        class="elevation-1"
        item-key="entry_id"
        aria-label="Production entries data table"
        hover
      >
        <template v-slot:item.production_date="{ item }">
          <v-text-field
            v-if="item.editing"
            v-model="item.production_date"
            type="date"
            dense
            hide-details
            :aria-label="`Production date for entry ${item.entry_id || 'new'}`"
          ></v-text-field>
          <span v-else>{{ formatDate(item.production_date) }}</span>
        </template>

        <template v-slot:item.product_id="{ item }">
          <v-select
            v-if="item.editing"
            v-model="item.product_id"
            :items="products"
            item-title="product_name"
            item-value="product_id"
            dense
            hide-details
            :aria-label="`Select product for entry ${item.entry_id || 'new'}`"
          ></v-select>
          <span v-else>{{ getProductName(item.product_id) }}</span>
        </template>

        <template v-slot:item.shift_id="{ item }">
          <v-select
            v-if="item.editing"
            v-model="item.shift_id"
            :items="shifts"
            item-title="shift_name"
            item-value="shift_id"
            dense
            hide-details
            :aria-label="`Select shift for entry ${item.entry_id || 'new'}`"
          ></v-select>
          <span v-else>{{ getShiftName(item.shift_id) }}</span>
        </template>

        <template v-slot:item.units_produced="{ item }">
          <v-text-field
            v-if="item.editing"
            v-model.number="item.units_produced"
            type="number"
            dense
            hide-details
            :aria-label="`Units produced for entry ${item.entry_id || 'new'}`"
          ></v-text-field>
          <span v-else>{{ item.units_produced }}</span>
        </template>

        <template v-slot:item.run_time_hours="{ item }">
          <v-text-field
            v-if="item.editing"
            v-model.number="item.run_time_hours"
            type="number"
            step="0.1"
            dense
            hide-details
            :aria-label="`Run time in hours for entry ${item.entry_id || 'new'}`"
          ></v-text-field>
          <span v-else>{{ item.run_time_hours }}</span>
        </template>

        <template v-slot:item.employees_assigned="{ item }">
          <v-text-field
            v-if="item.editing"
            v-model.number="item.employees_assigned"
            type="number"
            dense
            hide-details
            :aria-label="`Employees assigned for entry ${item.entry_id || 'new'}`"
          ></v-text-field>
          <span v-else>{{ item.employees_assigned }}</span>
        </template>

        <template v-slot:item.actions="{ item }">
          <div v-if="item.editing" role="group" aria-label="Edit actions">
            <v-btn
              icon
              size="small"
              @click="saveEntry(item)"
              color="success"
              :aria-label="`Save entry ${item.entry_id || 'new'}`"
            >
              <v-icon aria-hidden="true">mdi-check</v-icon>
            </v-btn>
            <v-btn
              icon
              size="small"
              @click="cancelEdit(item)"
              color="error"
              :aria-label="`Cancel editing entry ${item.entry_id || 'new'}`"
            >
              <v-icon aria-hidden="true">mdi-close</v-icon>
            </v-btn>
          </div>
          <div v-else role="group" aria-label="Row actions">
            <v-btn
              icon
              size="small"
              @click="editEntry(item)"
              :aria-label="`Edit entry ${item.entry_id}`"
            >
              <v-icon aria-hidden="true">mdi-pencil</v-icon>
            </v-btn>
            <v-btn
              icon
              size="small"
              @click="deleteEntry(item)"
              color="error"
              :aria-label="`Delete entry ${item.entry_id}`"
            >
              <v-icon aria-hidden="true">mdi-delete</v-icon>
            </v-btn>
          </div>
        </template>
      </v-data-table>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useKPIStore } from '@/stores/kpiStore'
import { format } from 'date-fns'
import EmptyState from '@/components/ui/EmptyState.vue'
import TableSkeleton from '@/components/ui/TableSkeleton.vue'

const kpiStore = useKPIStore()

const initialLoading = ref(true)
const loading = computed(() => kpiStore.loading)
const entries = computed(() => kpiStore.productionEntries)
const products = computed(() => kpiStore.products)
const shifts = computed(() => kpiStore.shifts)

// Status message for screen readers
const announceStatus = (message) => {
  statusMessage.value = message
  // Clear after announcement
  setTimeout(() => {
    statusMessage.value = ''
  }, 1000)
}

const headers = [
  { title: 'Date', key: 'production_date', sortable: true },
  { title: 'Product', key: 'product_id' },
  { title: 'Shift', key: 'shift_id' },
  { title: 'Units', key: 'units_produced' },
  { title: 'Runtime (hrs)', key: 'run_time_hours' },
  { title: 'Employees', key: 'employees_assigned' },
  { title: 'Actions', key: 'actions', sortable: false }
]

const formatDate = (date) => {
  return format(new Date(date), 'MMM dd, yyyy')
}

const getProductName = (productId) => {
  const product = products.value.find(p => p.product_id === productId)
  return product?.product_name || `ID: ${productId}`
}

const getShiftName = (shiftId) => {
  const shift = shifts.value.find(s => s.shift_id === shiftId)
  return shift?.shift_name || `ID: ${shiftId}`
}

const addNewEntry = () => {
  const newEntry = {
    editing: true,
    isNew: true,
    production_date: format(new Date(), 'yyyy-MM-dd'),
    product_id: products.value[0]?.product_id,
    shift_id: shifts.value[0]?.shift_id,
    units_produced: 0,
    run_time_hours: 0,
    employees_assigned: 1,
    defect_count: 0,
    scrap_count: 0
  }
  kpiStore.productionEntries.unshift(newEntry)
}

const editEntry = (item) => {
  item.editing = true
  item._backup = { ...item }
}

const cancelEdit = (item) => {
  if (item.isNew) {
    const index = kpiStore.productionEntries.indexOf(item)
    kpiStore.productionEntries.splice(index, 1)
  } else {
    Object.assign(item, item._backup)
    item.editing = false
    delete item._backup
  }
}

const saveEntry = async (item) => {
  const data = {
    product_id: item.product_id,
    shift_id: item.shift_id,
    production_date: item.production_date,
    work_order_number: item.work_order_number,
    units_produced: item.units_produced,
    run_time_hours: item.run_time_hours,
    employees_assigned: item.employees_assigned,
    defect_count: item.defect_count || 0,
    scrap_count: item.scrap_count || 0
  }

  if (item.isNew) {
    await kpiStore.createProductionEntry(data)
    const index = kpiStore.productionEntries.indexOf(item)
    kpiStore.productionEntries.splice(index, 1)
  } else {
    await kpiStore.updateProductionEntry(item.entry_id, data)
    item.editing = false
    delete item._backup
  }
}

const deleteEntry = async (item) => {
  if (confirm('Are you sure you want to delete this entry?')) {
    await kpiStore.deleteProductionEntry(item.entry_id)
    announceStatus(`Entry ${item.entry_id} deleted`)
  }
}

const statusMessage = ref('')

onMounted(async () => {
  try {
    await kpiStore.fetchReferenceData()
    await kpiStore.fetchProductionEntries()
  } finally {
    initialLoading.value = false
  }
})
</script>
