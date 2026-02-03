<template>
  <v-card>
    <v-card-title class="bg-secondary">
      <div class="d-flex align-center justify-space-between" style="width: 100%;">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-chart-bar</v-icon>
          <span class="text-h6">Demand Configuration</span>
        </div>
        <v-btn color="white" variant="outlined" size="small" @click="addRow">
          <v-icon left>mdi-plus</v-icon>
          Add Product Demand
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Mode Selection -->
      <v-row class="mb-3">
        <v-col cols="12" md="4">
          <v-select
            v-model="store.mode"
            :items="modeOptions"
            item-title="title"
            item-value="value"
            label="Demand Mode"
            variant="outlined"
            density="compact"
            hide-details
          />
        </v-col>
        <v-col v-if="store.mode === 'mix-driven'" cols="12" md="4">
          <v-text-field
            v-model.number="store.totalDemand"
            label="Total Daily Demand (pieces)"
            type="number"
            variant="outlined"
            density="compact"
            hide-details
          />
        </v-col>
        <v-col cols="12" md="4">
          <v-select
            v-model.number="store.horizonDays"
            :items="[1, 2, 3, 5, 7]"
            label="Simulation Horizon (days)"
            variant="outlined"
            density="compact"
            hide-details
          />
        </v-col>
      </v-row>

      <!-- Mix Percentage Warning -->
      <v-alert
        v-if="store.mode === 'mix-driven' && Math.abs(store.totalMixPercent - 100) > 0.1"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-3"
      >
        Mix percentages sum to {{ store.totalMixPercent.toFixed(1) }}%. They should equal 100%.
      </v-alert>

      <v-alert v-if="store.demands.length === 0" type="info" variant="tonal" class="mb-3">
        Add demand for each product. Products must match those defined in Operations.
      </v-alert>

      <div class="ag-theme-material" style="height: 300px; width: 100%;">
        <ag-grid-vue
          style="width: 100%; height: 100%;"
          :columnDefs="columnDefs"
          :rowData="store.demands"
          :defaultColDef="defaultColDef"
          :gridOptions="gridOptions"
          :getRowId="getRowId"
          @grid-ready="onGridReady"
          @cell-value-changed="onCellValueChanged"
        />
      </div>

      <!-- Auto-fill from operations -->
      <v-btn
        v-if="store.products.length > 0 && store.demands.length === 0"
        color="primary"
        variant="tonal"
        class="mt-3"
        @click="autoFillFromProducts"
      >
        <v-icon left>mdi-auto-fix</v-icon>
        Auto-fill from Operations ({{ store.products.length }} products)
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { useSimulationV2Store } from '@/stores/simulationV2Store'

const store = useSimulationV2Store()
const gridApi = ref(null)

const getRowId = (params) => String(params.data._id)

const modeOptions = [
  { title: 'Demand-Driven (specify daily/weekly)', value: 'demand-driven' },
  { title: 'Mix-Driven (specify percentages)', value: 'mix-driven' }
]

const defaultColDef = {
  sortable: true,
  filter: true,
  resizable: true,
  editable: true,
  minWidth: 80
}

const gridOptions = {
  theme: 'legacy',
  singleClickEdit: true,
  stopEditingWhenCellsLoseFocus: true,
  undoRedoCellEditing: true
}

const columnDefs = computed(() => {
  const cols = [
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
      headerName: 'Product',
      field: 'product',
      width: 150,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: store.products.length > 0 ? store.products : [''] }
    },
    {
      headerName: 'Bundle Size',
      field: 'bundle_size',
      width: 110,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor'
    }
  ]

  if (store.mode === 'demand-driven') {
    cols.push(
      {
        headerName: 'Daily Demand',
        field: 'daily_demand',
        width: 120,
        type: 'numericColumn',
        cellEditor: 'agNumberCellEditor'
      },
      {
        headerName: 'Weekly Demand',
        field: 'weekly_demand',
        width: 130,
        type: 'numericColumn',
        cellEditor: 'agNumberCellEditor'
      }
    )
  } else {
    cols.push({
      headerName: 'Mix Share %',
      field: 'mix_share_pct',
      width: 110,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      valueFormatter: (params) => params.value?.toFixed(1)
    })
  }

  return cols
})

const onGridReady = (params) => {
  gridApi.value = params.api
  params.api.sizeColumnsToFit()
}

const onCellValueChanged = (event) => {
  const index = store.demands.findIndex(d => d._id === event.data._id)
  if (index >= 0) {
    store.updateDemand(index, { [event.colDef.field]: event.newValue })
  }
}

const addRow = () => {
  store.addDemand()
}

const removeRow = (index) => {
  store.removeDemand(index)
}

const autoFillFromProducts = () => {
  const equalShare = 100 / store.products.length
  store.products.forEach(product => {
    store.addDemand({
      product,
      bundle_size: 10,
      daily_demand: null,
      weekly_demand: null,
      mix_share_pct: store.mode === 'mix-driven' ? equalShare : null
    })
  })
}
</script>

<style scoped>
.ag-theme-material {
  font-family: 'Roboto', sans-serif;
}
</style>
