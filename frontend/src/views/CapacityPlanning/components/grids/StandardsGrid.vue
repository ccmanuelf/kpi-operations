<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-timer</v-icon>
      {{ t('capacityPlanningGrids.standards.title') }}
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanningGrids.standards.addStandard') }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <AGGridBase
        :columnDefs="columnDefs"
        :rowData="standards"
        height="500px"
        :pagination="true"
        :paginationPageSize="25"
        :enableExcelPaste="false"
        entry-type="production"
        @cell-value-changed="onCellValueChanged"
      />

      <div v-if="!standards.length" class="text-center pa-4 text-grey">
        {{ t('capacityPlanningGrids.standards.noStandards') }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
/**
 * StandardsGrid - AG Grid surface for production standards (SAM, setup,
 * machine time per style+operation).
 *
 * Migrated 2026-05-01 from v-data-table + v-text-field slots to AGGridBase
 * as part of Group D Surface #11 of the entry-interface audit. Per
 * spec-owner R1: forms-disguised-as-tables are not compliant.
 */
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import useStandardsGridData from '@/composables/useStandardsGridData'

const { t } = useI18n()

const {
  standards,
  columnDefs,
  addRow,
  onCellValueChanged,
} = useStandardsGridData()
</script>
