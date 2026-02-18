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
      <!-- BOM List -->
      <v-expansion-panels v-if="boms.length">
        <v-expansion-panel
          v-for="(bom, bomIndex) in boms"
          :key="bom._id || bomIndex"
        >
          <v-expansion-panel-title>
            <div class="d-flex align-center w-100">
              <v-icon start>mdi-package-variant</v-icon>
              <strong class="mr-2">{{ bom.parent_item_code || t('capacityPlanning.bom.newBom') }}</strong>
              <span class="text-grey">{{ bom.parent_item_description }}</span>
              <v-spacer />
              <v-chip size="small" variant="tonal" class="mr-2">
                {{ bom.components?.length || 0 }} {{ t('capacityPlanning.bom.componentsCount') }}
              </v-chip>
              <v-chip
                v-if="bom.is_active"
                size="small"
                color="success"
                variant="tonal"
              >
                {{ t('common.active') }}
              </v-chip>
            </div>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <!-- BOM Header -->
            <v-row dense class="mb-3">
              <v-col cols="3">
                <v-text-field
                  v-model="bom.parent_item_code"
                  :label="t('capacityPlanning.bom.parentItemCode')"
                  variant="outlined"
                  density="compact"
                  @update:modelValue="markDirty"
                />
              </v-col>
              <v-col cols="4">
                <v-text-field
                  v-model="bom.parent_item_description"
                  :label="t('common.description')"
                  variant="outlined"
                  density="compact"
                  @update:modelValue="markDirty"
                />
              </v-col>
              <v-col cols="2">
                <v-text-field
                  v-model="bom.style_code"
                  :label="t('capacityPlanning.bom.styleCode')"
                  variant="outlined"
                  density="compact"
                  @update:modelValue="markDirty"
                />
              </v-col>
              <v-col cols="2">
                <v-text-field
                  v-model="bom.revision"
                  :label="t('capacityPlanning.bom.revision')"
                  variant="outlined"
                  density="compact"
                  @update:modelValue="markDirty"
                />
              </v-col>
              <v-col cols="1" class="d-flex align-center">
                <v-checkbox
                  v-model="bom.is_active"
                  :label="t('common.active')"
                  density="compact"
                  hide-details
                  @update:modelValue="markDirty"
                />
              </v-col>
            </v-row>

            <!-- Components Table -->
            <v-data-table
              :headers="componentHeaders"
              :items="bom.components || []"
              density="compact"
              class="elevation-1"
            >
              <template v-slot:item.component_item_code="{ item }">
                <v-text-field
                  v-model="item.component_item_code"
                  density="compact"
                  variant="plain"
                  hide-details
                  @update:modelValue="markDirty"
                />
              </template>

              <template v-slot:item.component_description="{ item }">
                <v-text-field
                  v-model="item.component_description"
                  density="compact"
                  variant="plain"
                  hide-details
                  @update:modelValue="markDirty"
                />
              </template>

              <template v-slot:item.quantity_per="{ item }">
                <v-text-field
                  v-model.number="item.quantity_per"
                  type="number"
                  step="0.01"
                  density="compact"
                  variant="plain"
                  hide-details
                  @update:modelValue="markDirty"
                />
              </template>

              <template v-slot:item.unit_of_measure="{ item }">
                <v-select
                  v-model="item.unit_of_measure"
                  :items="uomOptions"
                  density="compact"
                  variant="plain"
                  hide-details
                  @update:modelValue="markDirty"
                />
              </template>

              <template v-slot:item.waste_percentage="{ item }">
                <v-text-field
                  v-model.number="item.waste_percentage"
                  type="number"
                  step="0.1"
                  density="compact"
                  variant="plain"
                  hide-details
                  @update:modelValue="markDirty"
                />
              </template>

              <template v-slot:item.actions="{ index }">
                <v-btn
                  icon="mdi-delete"
                  size="x-small"
                  variant="text"
                  color="error"
                  @click="removeComponent(bomIndex, index)"
                />
              </template>
            </v-data-table>

            <div class="d-flex justify-space-between mt-3">
              <v-btn
                size="small"
                variant="tonal"
                color="primary"
                @click="addComponent(bomIndex)"
              >
                <v-icon start>mdi-plus</v-icon>
                {{ t('capacityPlanning.bom.addComponent') }}
              </v-btn>
              <v-btn
                size="small"
                variant="outlined"
                color="error"
                @click="removeBOM(bomIndex)"
              >
                <v-icon start>mdi-delete</v-icon>
                {{ t('capacityPlanning.bom.deleteBom') }}
              </v-btn>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>

      <div v-else class="text-center pa-4 text-grey">
        {{ t('capacityPlanning.bom.noData') }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
/**
 * BOMGrid - Editable grid for Bill of Materials management.
 *
 * Displays BOMs as expandable panels, each with a header (parent item code,
 * description, style code, revision, active flag) and a nested components
 * table (component code, description, quantity per, UOM, waste percentage).
 * Supports add/remove for both BOMs and individual components.
 *
 * Store dependency: useCapacityPlanningStore (worksheets.bom)
 * No props or emits -- all state managed via store.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const { t } = useI18n()
const store = useCapacityPlanningStore()

const componentHeaders = computed(() => [
  { title: t('capacityPlanning.bom.headers.componentCode'), key: 'component_item_code', width: '150px' },
  { title: t('capacityPlanning.bom.headers.description'), key: 'component_description', width: '200px' },
  { title: t('capacityPlanning.bom.headers.qtyPer'), key: 'quantity_per', width: '100px' },
  { title: t('capacityPlanning.bom.headers.uom'), key: 'unit_of_measure', width: '100px' },
  { title: t('capacityPlanning.bom.headers.wastePercent'), key: 'waste_percentage', width: '100px' },
  { title: t('capacityPlanning.bom.headers.actions'), key: 'actions', width: '80px', sortable: false }
])

const uomOptions = ['EA', 'M', 'YD', 'KG', 'LB', 'PC', 'SET']

const boms = computed(() => store.worksheets.bom.data)

const addBOM = () => store.addRow('bom')
const removeBOM = (index) => store.removeRow('bom', index)
const addComponent = (bomIndex) => store.addBOMComponent(bomIndex)
const removeComponent = (bomIndex, componentIndex) => store.removeBOMComponent(bomIndex, componentIndex)
const markDirty = () => {
  store.worksheets.bom.dirty = true
}
</script>
