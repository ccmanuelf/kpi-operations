<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-clipboard-list</v-icon>
      {{ t('capacityPlanning.orders.title') }}
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" class="mr-2" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanning.orders.addOrder') }}
      </v-btn>
      <v-btn size="small" variant="outlined" @click="showImportDialog = true">
        <v-icon start>mdi-upload</v-icon>
        {{ t('capacityPlanning.orders.importCsv') }}
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
      />

      <div v-if="!orders.length" class="text-center pa-4 text-grey">
        {{ t('capacityPlanning.orders.noOrdersYet') }}
      </div>
    </v-card-text>

    <!-- CSV Import Dialog -->
    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>{{ t('capacityPlanning.orders.importOrdersFromCsv') }}</v-card-title>
        <v-card-text>
          <v-textarea
            v-model="csvData"
            :label="t('capacityPlanning.orders.pasteCsvData')"
            rows="10"
            variant="outlined"
            placeholder="order_number,customer_name,style_model,order_quantity,required_date"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="doImportCsv">{{ t('common.import') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
/**
 * OrdersGrid - AG Grid surface for capacity planning customer orders.
 *
 * Migrated 2026-05-01 from v-data-table + per-cell v-text-field/v-select
 * slots to AGGridBase as part of Group D Surface #13 (final Group D
 * surface) of the entry-interface audit.
 *
 * Priority dropdown now uses the canonical OrderPriority enum
 * (LOW/NORMAL/HIGH/URGENT). The legacy 'CRITICAL' value was a UI bug —
 * the backend enum has no CRITICAL; URGENT is the equivalent.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import useOrdersGridData from '@/composables/useOrdersGridData'

const { t } = useI18n()

const showImportDialog = ref(false)
const csvData = ref('')

const {
  orders,
  columnDefs,
  addRow,
  onCellValueChanged,
  importCsv,
} = useOrdersGridData()

const doImportCsv = () => {
  importCsv(csvData.value)
  showImportDialog.value = false
  csvData.value = ''
}
</script>
