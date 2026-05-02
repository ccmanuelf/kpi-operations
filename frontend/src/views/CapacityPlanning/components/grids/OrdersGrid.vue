<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-clipboard-list</v-icon>
      {{ t('capacityPlanning.orders.title') }}
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanning.orders.addOrder') }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <AGGridBase
        :columnDefs="columnDefs"
        :rowData="orders"
        height="500px"
        :pagination="true"
        :paginationPageSize="25"
        :enableExcelPaste="false"
        entry-type="production"
        @cell-value-changed="onCellValueChanged"
        @rows-pasted="onRowsPasted"
      />

      <div v-if="!orders.length" class="text-center pa-4 text-grey">
        {{ t('capacityPlanning.orders.noOrdersYet') }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
/**
 * OrdersGrid - AG Grid surface for capacity planning customer orders.
 *
 * Migrated 2026-05-01 from v-data-table + per-cell v-text-field/v-select
 * slots to AGGridBase as part of Group D Surface #13 of the entry-
 * interface audit.
 *
 * 2026-05-02 — toolbar consolidation: dropped the surface's textarea-
 * paste "Import CSV" dialog; AGGridBase's toolbar Import-CSV button +
 * Excel paste-in cover the same flow with a richer parser (Papaparse).
 * `@rows-pasted` routes the parsed rows into `store.importData('orders',
 * rows)` — same downstream path the legacy dialog used.
 *
 * Priority dropdown uses the canonical OrderPriority enum
 * (LOW/NORMAL/HIGH/URGENT). The legacy 'CRITICAL' value was a UI bug —
 * the backend enum has no CRITICAL; URGENT is the equivalent.
 */
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import useOrdersGridData from '@/composables/useOrdersGridData'

const { t } = useI18n()

const {
  orders,
  columnDefs,
  addRow,
  onCellValueChanged,
  onRowsPasted,
} = useOrdersGridData()
</script>
