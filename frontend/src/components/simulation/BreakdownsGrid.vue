<template>
  <v-card>
    <v-card-title class="bg-warning">
      <div class="d-flex align-center justify-space-between" style="width: 100%;">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-wrench-clock</v-icon>
          <span class="text-h6">Equipment Breakdowns (Optional)</span>
        </div>
        <v-btn color="white" variant="outlined" size="small" @click="addRow">
          <v-icon left>mdi-plus</v-icon>
          Add Breakdown Rule
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        Configure probability of equipment breakdown per operation. Leave empty for perfect reliability.
      </v-alert>

      <div v-if="store.breakdowns.length > 0" class="ag-theme-material" style="height: 200px; width: 100%;">
        <ag-grid-vue
          style="width: 100%; height: 100%;"
          :columnDefs="columnDefs"
          :rowData="store.breakdowns"
          :defaultColDef="defaultColDef"
          :gridOptions="gridOptions"
          :getRowId="getRowId"
          @grid-ready="onGridReady"
          @cell-value-changed="onCellValueChanged"
        />
      </div>

      <div v-else class="text-center py-6 text-medium-emphasis">
        <v-icon size="48" color="grey-lighten-1">mdi-check-circle-outline</v-icon>
        <p class="mt-2">No breakdown rules configured. Simulation assumes perfect equipment reliability.</p>
      </div>

      <!-- Quick Add from Machine Tools -->
      <v-btn
        v-if="availableMachineTools.length > 0"
        color="warning"
        variant="tonal"
        class="mt-3"
        @click="showQuickAdd = true"
      >
        <v-icon left>mdi-lightning-bolt</v-icon>
        Quick Add from Operations ({{ availableMachineTools.length }} machines)
      </v-btn>

      <!-- Quick Add Dialog -->
      <v-dialog v-model="showQuickAdd" max-width="500">
        <v-card>
          <v-card-title>Add Breakdown Rules</v-card-title>
          <v-card-text>
            <v-list>
              <v-list-item
                v-for="tool in availableMachineTools"
                :key="tool"
              >
                <template v-slot:prepend>
                  <v-checkbox
                    v-model="selectedTools"
                    :value="tool"
                    hide-details
                  />
                </template>
                <v-list-item-title>{{ tool }}</v-list-item-title>
              </v-list-item>
            </v-list>
            <v-text-field
              v-model.number="defaultBreakdownPct"
              label="Default Breakdown %"
              type="number"
              :min="0"
              :max="100"
              step="0.5"
              variant="outlined"
              density="compact"
              class="mt-3"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn @click="showQuickAdd = false">Cancel</v-btn>
            <v-btn color="primary" @click="addSelectedTools">Add Selected</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { useSimulationV2Store } from '@/stores/simulationV2Store'

const store = useSimulationV2Store()
const gridApi = ref(null)
const showQuickAdd = ref(false)
const selectedTools = ref([])
const defaultBreakdownPct = ref(2.0)

const getRowId = (params) => String(params.data._id)

const defaultColDef = {
  sortable: true,
  filter: true,
  resizable: true,
  editable: true,
  minWidth: 100
}

const gridOptions = {
  theme: 'legacy',
  singleClickEdit: true,
  stopEditingWhenCellsLoseFocus: true,
  undoRedoCellEditing: true
}

// Machine tools from operations that don't have breakdown rules yet
const availableMachineTools = computed(() => {
  const existingTools = new Set(store.breakdowns.map(b => b.machine_tool))
  return store.machineTools.filter(tool => !existingTools.has(tool))
})

const columnDefs = computed(() => [
  {
    headerName: '',
    field: 'actions',
    width: 50,
    editable: false,
    sortable: false,
    filter: false,
    cellRenderer: (params) => {
      const btn = document.createElement('button')
      btn.innerHTML = '✕'
      btn.style.cssText = 'cursor:pointer;color:red;border:none;background:none;font-size:16px;'
      btn.onclick = () => removeRow(params.node.rowIndex)
      return btn
    }
  },
  {
    headerName: 'Machine/Tool',
    field: 'machine_tool',
    flex: 1,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: { values: store.machineTools }
  },
  {
    headerName: 'Breakdown %',
    field: 'breakdown_pct',
    width: 130,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    valueFormatter: (params) => `${params.value?.toFixed(1)}%`
  }
])

const onGridReady = (params) => {
  gridApi.value = params.api
  params.api.sizeColumnsToFit()
}

const onCellValueChanged = (event) => {
  const index = store.breakdowns.findIndex(b => b._id === event.data._id)
  if (index >= 0) {
    store.updateBreakdown(index, { [event.colDef.field]: event.newValue })
  }
}

const addRow = () => {
  store.addBreakdown()
}

const removeRow = (index) => {
  store.removeBreakdown(index)
}

const addSelectedTools = () => {
  selectedTools.value.forEach(tool => {
    store.addBreakdown({
      machine_tool: tool,
      breakdown_pct: defaultBreakdownPct.value
    })
  })
  selectedTools.value = []
  showQuickAdd.value = false
}
</script>

<style scoped>
.ag-theme-material {
  font-family: 'Roboto', sans-serif;
}
</style>
