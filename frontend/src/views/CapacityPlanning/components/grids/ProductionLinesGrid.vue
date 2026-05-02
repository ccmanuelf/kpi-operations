<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-factory</v-icon>
      {{ t('capacityPlanningGrids.productionLines.title') }}
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanningGrids.productionLines.addLine') }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <AGGridBase
        :columnDefs="columnDefs"
        :rowData="lines"
        height="500px"
        :pagination="true"
        :paginationPageSize="25"
        :enableExcelPaste="false"
        entry-type="production"
        @cell-value-changed="onCellValueChanged"
      />

      <div v-if="!lines.length" class="text-center pa-4 text-grey">
        {{ t('capacityPlanningGrids.productionLines.noLines') }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
/**
 * ProductionLinesGrid - AG Grid surface for production line configuration.
 *
 * Manages production line definitions including line code, name, department,
 * standard capacity (units/hr), max operators, efficiency factor, and
 * active status. Supports add, duplicate, and delete operations via the
 * row-level actions column. Excel-style keyboard navigation provided by
 * AGGridBase. Persistence is workbook-level (parent saves dirty worksheets).
 *
 * Migrated 2026-05-01 from v-data-table + v-text-field slots to AGGridBase
 * as part of Group D Surface #9 of the entry-interface audit. Per spec-owner
 * R1: forms-disguised-as-tables are not compliant with the Spreadsheet
 * Standard.
 */
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import useProductionLinesGridData from '@/composables/useProductionLinesGridData'

const { t } = useI18n()

const {
  lines,
  columnDefs,
  addRow,
  onCellValueChanged,
} = useProductionLinesGridData()
</script>
