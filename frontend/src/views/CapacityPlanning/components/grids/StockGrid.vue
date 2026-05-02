<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-package-variant</v-icon>
      {{ t('capacityPlanning.stock.title') }}
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" class="mr-2" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanning.stock.addItem') }}
      </v-btn>
      <v-btn size="small" variant="outlined" @click="showImportDialog = true">
        <v-icon start>mdi-upload</v-icon>
        {{ t('capacityPlanning.stock.importStock') }}
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
              <div class="text-caption">{{ t('capacityPlanning.stock.totalItems') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="success">
            <v-card-text class="text-center">
              <div class="text-h6">{{ totalOnHand.toLocaleString() }}</div>
              <div class="text-caption">{{ t('capacityPlanning.stock.onHand') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="warning">
            <v-card-text class="text-center">
              <div class="text-h6">{{ totalAllocated.toLocaleString() }}</div>
              <div class="text-caption">{{ t('capacityPlanning.stock.allocated') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="info">
            <v-card-text class="text-center">
              <div class="text-h6">{{ totalAvailable.toLocaleString() }}</div>
              <div class="text-caption">{{ t('capacityPlanning.stock.available') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Search filter -->
      <v-text-field
        v-model="searchTerm"
        prepend-inner-icon="mdi-magnify"
        :label="t('capacityPlanning.stock.searchItems')"
        variant="outlined"
        density="compact"
        class="mb-3"
        style="max-width: 320px"
        clearable
      />

      <AGGridBase
        :columnDefs="columnDefs"
        :rowData="filteredStock"
        height="500px"
        :pagination="true"
        :paginationPageSize="25"
        :enableExcelPaste="false"
        entry-type="production"
        @cell-value-changed="onCellValueChanged"
      />

      <div v-if="!stock.length" class="text-center pa-4 text-grey">
        {{ t('capacityPlanning.stock.noData') }}
      </div>
    </v-card-text>

    <!-- Import Dialog -->
    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>{{ t('capacityPlanning.stock.importStockSnapshot') }}</v-card-title>
        <v-card-text>
          <v-textarea
            v-model="csvData"
            :label="t('capacityPlanning.orders.pasteCsvData')"
            rows="10"
            variant="outlined"
            placeholder="item_code,item_description,on_hand_quantity,allocated_quantity,on_order_quantity"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="importCSV">{{ t('common.import') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
/**
 * StockGrid - AG Grid surface for inventory stock snapshots.
 *
 * Migrated 2026-05-01 from v-data-table + v-text-field slots to AGGridBase
 * as part of Group D Surface #10 of the entry-interface audit. Per
 * spec-owner R1: forms-disguised-as-tables are not compliant.
 *
 * Preserves staleness warning, summary stats, search filter, and CSV import
 * via textarea paste. available_quantity auto-recomputed when on_hand or
 * allocated changes.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import useStockGridData from '@/composables/useStockGridData'

const { t } = useI18n()

const showImportDialog = ref(false)
const csvData = ref('')

const {
  stock,
  filteredStock,
  searchTerm,
  totalOnHand,
  totalAllocated,
  totalAvailable,
  stalenessWarning,
  columnDefs,
  addRow,
  onCellValueChanged,
  importData,
} = useStockGridData()

const importCSV = () => {
  if (!csvData.value.trim()) return

  const lines = csvData.value.trim().split('\n')
  const headerLine = lines[0].split(',').map((h) => h.trim())

  const today = new Date().toISOString().slice(0, 10)

  const data = lines.slice(1).map((line) => {
    const values = line.split(',').map((v) => v.trim())
    const row = { snapshot_date: today, unit_of_measure: 'EA' }
    headerLine.forEach((h, i) => {
      row[h] = values[i] || ''
    })
    row.on_hand_quantity = parseInt(row.on_hand_quantity) || 0
    row.allocated_quantity = parseInt(row.allocated_quantity) || 0
    row.on_order_quantity = parseInt(row.on_order_quantity) || 0
    row.available_quantity = row.on_hand_quantity - row.allocated_quantity
    return row
  })

  importData(data)
  showImportDialog.value = false
  csvData.value = ''
}
</script>
