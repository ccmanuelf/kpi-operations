<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-file-tree</v-icon>
      {{ t('capacityPlanning.bom.title') }}
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" @click="addBOM">
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanning.bom.addBom') }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <!-- Master grid: BOM headers -->
      <div class="text-subtitle-2 mb-2">
        {{ t('capacityPlanning.bom.parentItemCode') }} ({{ boms.length }})
      </div>
      <AGGridBase
        :columnDefs="bomColumnDefs"
        :rowData="boms"
        height="280px"
        :pagination="false"
        :enableExcelPaste="false"
        entry-type="production"
        @cell-value-changed="onBOMCellValueChanged"
        @cell-clicked="onBOMRowClicked"
      />

      <div v-if="!boms.length" class="text-center pa-4 text-grey">
        {{ t('capacityPlanning.bom.noData') }}
      </div>

      <!-- Detail grid: components for the selected BOM -->
      <v-divider class="my-4" />
      <div class="d-flex align-center mb-2">
        <div class="text-subtitle-2">
          {{ t('capacityPlanning.bom.componentsCount') }}
          <span v-if="selectedBOM" class="text-primary">
            · {{ selectedBOM.parent_item_code || t('capacityPlanning.bom.newBom') }}
          </span>
        </div>
        <v-spacer />
        <v-btn
          size="small"
          variant="tonal"
          color="primary"
          :disabled="selectedBOMIndex === null"
          @click="addComponent"
        >
          <v-icon start>mdi-plus</v-icon>
          {{ t('capacityPlanning.bom.addComponent') }}
        </v-btn>
      </div>

      <v-alert
        v-if="selectedBOMIndex === null"
        type="info"
        variant="tonal"
        density="compact"
      >
        {{ t('capacityPlanning.bom.selectBomFirst') }}
      </v-alert>

      <AGGridBase
        v-else
        :columnDefs="componentColumnDefs"
        :rowData="selectedComponents"
        height="320px"
        :pagination="false"
        :enableExcelPaste="false"
        entry-type="production"
        @cell-value-changed="onComponentCellValueChanged"
      />

      <div
        v-if="selectedBOMIndex !== null && selectedComponents.length === 0"
        class="text-center pa-4 text-grey"
      >
        {{ t('capacityPlanning.bom.noComponentsYet') }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
/**
 * BOMGrid - AG Grid master-detail surface for Bill of Materials.
 *
 * Migrated 2026-05-01 from a v-expansion-panels + per-panel v-data-table
 * pattern to two stacked AG Grids (parent + detail) as part of Group F
 * Surface #16 of the entry-interface audit. AG Grid Community has no
 * native master-detail (Enterprise-only); the stacked-grid approach
 * gives equivalent UX without the licence dependency.
 *
 * Operator workflow:
 *   1. Click a row in the parent grid to select that BOM.
 *   2. The detail grid below populates with that BOM's components.
 *   3. Add / edit / delete components inline.
 *   4. Workbook-level "Save Workbook" button persists everything.
 *
 * The store's addBOMComponent / removeBOMComponent actions write to
 * the orphaned POST /capacity/bom/{id}/components and PUT
 * /capacity/bom/{id}/components/{cid} endpoints — endpoints that
 * existed on the backend but had no UI surface before this migration
 * (per Phase 0 § 6.7 finding).
 */
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import useBOMGridData from '@/composables/useBOMGridData'

const { t } = useI18n()

const {
  boms,
  selectedBOM,
  selectedBOMIndex,
  selectedComponents,
  bomColumnDefs,
  componentColumnDefs,
  addBOM,
  addComponent,
  onBOMRowClicked,
  onBOMCellValueChanged,
  onComponentCellValueChanged,
} = useBOMGridData()
</script>
