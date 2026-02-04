<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-timer</v-icon>
      Production Standards (SAM)
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        Add Standard
      </v-btn>
    </v-card-title>
    <v-card-text>
      <v-data-table
        :headers="headers"
        :items="standards"
        :items-per-page="15"
        class="elevation-1"
        density="compact"
      >
        <template v-slot:item.style_code="{ item, index }">
          <v-text-field
            v-model="item.style_code"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.operation_code="{ item, index }">
          <v-text-field
            v-model="item.operation_code"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.operation_name="{ item, index }">
          <v-text-field
            v-model="item.operation_name"
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

        <template v-slot:item.sam_minutes="{ item, index }">
          <v-text-field
            v-model.number="item.sam_minutes"
            type="number"
            step="0.01"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.setup_time_minutes="{ item, index }">
          <v-text-field
            v-model.number="item.setup_time_minutes"
            type="number"
            step="0.1"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.machine_time_minutes="{ item, index }">
          <v-text-field
            v-model.number="item.machine_time_minutes"
            type="number"
            step="0.01"
            density="compact"
            variant="plain"
            hide-details
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

      <div v-if="!standards.length" class="text-center pa-4 text-grey">
        No production standards defined. Add SAM (Standard Allowed Minutes) data for your operations.
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const store = useCapacityPlanningStore()

const headers = [
  { title: 'Style', key: 'style_code', width: '100px' },
  { title: 'Op Code', key: 'operation_code', width: '100px' },
  { title: 'Operation', key: 'operation_name', width: '180px' },
  { title: 'Department', key: 'department', width: '120px' },
  { title: 'SAM (min)', key: 'sam_minutes', width: '100px' },
  { title: 'Setup (min)', key: 'setup_time_minutes', width: '100px' },
  { title: 'Machine (min)', key: 'machine_time_minutes', width: '100px' },
  { title: 'Actions', key: 'actions', width: '100px', sortable: false }
]

const standards = computed(() => store.worksheets.productionStandards.data)

const addRow = () => store.addRow('productionStandards')
const removeRow = (index) => store.removeRow('productionStandards', index)
const duplicateRow = (index) => store.duplicateRow('productionStandards', index)
const markDirty = () => {
  store.worksheets.productionStandards.dirty = true
}
</script>
