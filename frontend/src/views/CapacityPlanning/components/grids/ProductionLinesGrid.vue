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
      <v-data-table
        :headers="headers"
        :items="lines"
        :items-per-page="10"
        class="elevation-1"
        density="compact"
      >
        <template v-slot:item.line_code="{ item, index }">
          <v-text-field
            v-model="item.line_code"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.line_name="{ item, index }">
          <v-text-field
            v-model="item.line_name"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.department="{ item, index }">
          <v-text-field
            v-model="item.department"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.standard_capacity_units_per_hour="{ item, index }">
          <v-text-field
            v-model.number="item.standard_capacity_units_per_hour"
            type="number"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.max_operators="{ item, index }">
          <v-text-field
            v-model.number="item.max_operators"
            type="number"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.efficiency_factor="{ item, index }">
          <v-text-field
            v-model.number="item.efficiency_factor"
            type="number"
            step="0.01"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.is_active="{ item, index }">
          <v-checkbox
            v-model="item.is_active"
            hide-details
            density="compact"
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.actions="{ index }">
          <v-btn
            icon="mdi-content-copy"
            size="x-small"
            variant="text"
            @click="duplicateRow(index)"
          />
          <v-btn
            icon="mdi-delete"
            size="x-small"
            variant="text"
            color="error"
            @click="removeRow(index)"
          />
        </template>
      </v-data-table>

      <div v-if="!lines.length" class="text-center pa-4 text-grey">
        {{ t('capacityPlanningGrids.productionLines.noLines') }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
/**
 * ProductionLinesGrid - Editable grid for production line configuration.
 *
 * Manages production line definitions including line code, name, department,
 * standard capacity (units/hr), max operators, efficiency factor, and
 * active status. Supports add, duplicate, and delete operations.
 *
 * Store dependency: useCapacityPlanningStore (worksheets.productionLines)
 * No props or emits -- all state managed via store.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const { t } = useI18n()
const store = useCapacityPlanningStore()

const headers = computed(() => [
  { title: t('capacityPlanningGrids.productionLines.code'), key: 'line_code', width: '100px' },
  { title: t('capacityPlanningGrids.productionLines.name'), key: 'line_name', width: '150px' },
  { title: t('capacityPlanningGrids.productionLines.department'), key: 'department', width: '120px' },
  { title: t('capacityPlanningGrids.productionLines.capacityUnitsPerHr'), key: 'standard_capacity_units_per_hour', width: '140px' },
  { title: t('capacityPlanningGrids.productionLines.maxOperators'), key: 'max_operators', width: '110px' },
  { title: t('capacityPlanningGrids.productionLines.efficiency'), key: 'efficiency_factor', width: '100px' },
  { title: t('capacityPlanningGrids.productionLines.active'), key: 'is_active', width: '80px' },
  { title: t('common.actions'), key: 'actions', width: '100px', sortable: false }
])

const lines = computed(() => store.worksheets.productionLines.data)

const addRow = () => store.addRow('productionLines')
const removeRow = (index) => store.removeRow('productionLines', index)
const duplicateRow = (index) => store.duplicateRow('productionLines', index)
const markDirty = () => {
  store.worksheets.productionLines.dirty = true
}
</script>
