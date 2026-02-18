<template>
  <v-card role="region" aria-labelledby="data-entry-title">
    <v-card-title class="d-flex align-center flex-wrap ga-3">
      <span id="data-entry-title" class="text-h5">{{ $t('dataEntry.productionDataEntry') }}</span>
      <v-spacer></v-spacer>
      <v-btn
        color="primary"
        @click="addNewEntry"
        :aria-label="$t('dataEntry.addNewProductionEntry')"
        prepend-icon="mdi-plus"
      >
        {{ $t('dataEntry.addEntry') }}
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
        :title="$t('dataEntry.noProductionEntries')"
        :description="$t('dataEntry.noProductionEntriesDesc')"
        :action-text="$t('dataEntry.addFirstEntry')"
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
        :aria-label="$t('dataEntry.productionEntriesTable')"
        hover
      >
        <template v-slot:item.production_date="{ item }">
          <v-text-field
            v-if="item.editing"
            v-model="item.production_date"
            type="date"
            dense
            hide-details
            :aria-label="$t('dataEntry.ariaProductionDate', { id: item.entry_id || $t('dataEntry.new') })"
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
            :aria-label="$t('dataEntry.ariaSelectProduct', { id: item.entry_id || $t('dataEntry.new') })"
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
            :aria-label="$t('dataEntry.ariaSelectShift', { id: item.entry_id || $t('dataEntry.new') })"
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
            :aria-label="$t('dataEntry.ariaUnitsProduced', { id: item.entry_id || $t('dataEntry.new') })"
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
            :aria-label="$t('dataEntry.ariaRunTime', { id: item.entry_id || $t('dataEntry.new') })"
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
            :aria-label="$t('dataEntry.ariaEmployees', { id: item.entry_id || $t('dataEntry.new') })"
          ></v-text-field>
          <span v-else>{{ item.employees_assigned }}</span>
        </template>

        <template v-slot:item.actions="{ item }">
          <div v-if="item.editing" role="group" :aria-label="$t('dataEntry.ariaEditActions')">
            <v-btn
              icon
              size="small"
              @click="saveEntry(item)"
              color="success"
              :aria-label="$t('dataEntry.ariaSaveEntry', { id: item.entry_id || $t('dataEntry.new') })"
            >
              <v-icon aria-hidden="true">mdi-check</v-icon>
            </v-btn>
            <v-btn
              icon
              size="small"
              @click="cancelEdit(item)"
              color="error"
              :aria-label="$t('dataEntry.ariaCancelEdit', { id: item.entry_id || $t('dataEntry.new') })"
            >
              <v-icon aria-hidden="true">mdi-close</v-icon>
            </v-btn>
          </div>
          <div v-else role="group" :aria-label="$t('dataEntry.ariaRowActions')">
            <v-btn
              icon
              size="small"
              @click="editEntry(item)"
              :aria-label="$t('dataEntry.ariaEditEntry', { id: item.entry_id })"
            >
              <v-icon aria-hidden="true">mdi-pencil</v-icon>
            </v-btn>
            <v-btn
              icon
              size="small"
              @click="deleteEntry(item)"
              color="error"
              :aria-label="$t('dataEntry.ariaDeleteEntry', { id: item.entry_id })"
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
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format } from 'date-fns'
import EmptyState from '@/components/ui/EmptyState.vue'
import TableSkeleton from '@/components/ui/TableSkeleton.vue'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'

const { t } = useI18n()
const kpiStore = useProductionDataStore()

// Unsaved changes warning when rows are being edited
const { hasUnsavedChanges, markDirty, markClean } = useUnsavedChanges({
  message: t('dataEntry.unsavedChangesWarning')
})

// Keyboard shortcuts (Ctrl+S to save, Escape to cancel)
const { registerShortcut } = useKeyboardShortcuts()

// Track if any row is being edited
const hasEditingRows = computed(() => entries.value.some(item => item.editing))

// Sync editing state with unsaved changes
watch(hasEditingRows, (isEditing) => {
  if (isEditing) {
    markDirty()
  } else {
    markClean()
  }
})

// Save all editing rows via Ctrl+S
const saveAllEditingRows = async () => {
  const editingRows = entries.value.filter(item => item.editing)
  if (editingRows.length === 0) return

  for (const item of editingRows) {
    await saveEntry(item)
  }
  announceStatus(t('dataEntry.savedEntries', { count: editingRows.length }))
}

// Cancel all editing via Escape
const cancelAllEditing = () => {
  const editingRows = [...entries.value.filter(item => item.editing)]
  editingRows.forEach(item => cancelEdit(item))
}

// Register keyboard shortcuts
registerShortcut('ctrl+s', saveAllEditingRows)
registerShortcut('escape', cancelAllEditing)

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

const headers = computed(() => [
  { title: t('grids.columns.date'), key: 'production_date', sortable: true },
  { title: t('grids.columns.product'), key: 'product_id' },
  { title: t('grids.columns.shift'), key: 'shift_id' },
  { title: t('dataEntry.units'), key: 'units_produced' },
  { title: t('grids.columns.runtimeHrs'), key: 'run_time_hours' },
  { title: t('grids.columns.employees'), key: 'employees_assigned' },
  { title: t('common.actions'), key: 'actions', sortable: false }
])

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
  if (confirm(t('dataEntry.confirmDeleteEntry'))) {
    await kpiStore.deleteProductionEntry(item.entry_id)
    announceStatus(t('dataEntry.entryDeleted', { id: item.entry_id }))
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
