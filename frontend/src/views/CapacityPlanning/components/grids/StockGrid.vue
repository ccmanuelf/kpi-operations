<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-package-variant</v-icon>
      {{ t('capacityPlanning.stock.title') }}
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanning.stock.addItem') }}
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
        @rows-pasted="onRowsPasted"
      />

      <div v-if="!stock.length" class="text-center pa-4 text-grey">
        {{ t('capacityPlanning.stock.noData') }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
/**
 * StockGrid - AG Grid surface for inventory stock snapshots.
 *
 * Migrated 2026-05-01 from v-data-table + v-text-field slots to AGGridBase
 * as part of Group D Surface #10 of the entry-interface audit.
 *
 * 2026-05-02 — toolbar consolidation: dropped the surface's textarea-
 * paste "Import Stock" dialog; AGGridBase's toolbar Import-CSV (Papa-
 * parse-backed) covers the same flow. `@rows-pasted` shapes the parsed
 * rows (snapshot_date today, type-coerce numeric fields, recompute
 * available_quantity) and pushes them through `importData`.
 *
 * Preserves staleness warning, summary stats, and search filter.
 */
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import useStockGridData from '@/composables/useStockGridData'

const { t } = useI18n()

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

const onRowsPasted = (pasteData) => {
  const rows = pasteData?.convertedRows
  if (!rows || rows.length === 0) return
  const today = new Date().toISOString().slice(0, 10)
  const shaped = rows.map((row) => {
    const onHand = parseInt(row.on_hand_quantity, 10) || 0
    const allocated = parseInt(row.allocated_quantity, 10) || 0
    return {
      snapshot_date: row.snapshot_date || today,
      unit_of_measure: row.unit_of_measure || 'EA',
      ...row,
      on_hand_quantity: onHand,
      allocated_quantity: allocated,
      on_order_quantity: parseInt(row.on_order_quantity, 10) || 0,
      available_quantity: onHand - allocated,
    }
  })
  importData(shaped)
}
</script>
