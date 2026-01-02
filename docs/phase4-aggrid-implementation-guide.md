# AG Grid Implementation Guide - Manufacturing KPI Platform

**Target**: Replace Vuetify v-data-table with AG Grid for Excel-like data entry
**Timeline**: 3-4 weeks
**Developer**: 1 senior Vue.js developer

---

## Table of Contents

1. [Setup & Installation](#1-setup--installation)
2. [Component Architecture](#2-component-architecture)
3. [Production Entry Grid](#3-production-entry-grid)
4. [Attendance Entry Grid](#4-attendance-entry-grid)
5. [Quality Entry Grid](#5-quality-entry-grid)
6. [Integration with Pinia](#6-integration-with-pinia)
7. [Styling & Theming](#7-styling--theming)
8. [Testing Strategy](#8-testing-strategy)

---

## 1. Setup & Installation

### 1.1 Install Dependencies

```bash
cd frontend
npm install ag-grid-community ag-grid-vue3
```

**Package Versions**:
- `ag-grid-community`: ^31.0.0 (latest stable)
- `ag-grid-vue3`: ^31.0.0

**Bundle Impact**:
- AG Grid Community: ~150KB gzipped
- Incremental build time: +5-10 seconds

### 1.2 Import AG Grid Styles

**Option A**: Import in `main.js` (global)
```javascript
// frontend/src/main.js
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-material.css' // Material Design theme
```

**Option B**: Import in individual components (code-splitting)
```vue
<style>
@import 'ag-grid-community/styles/ag-grid.css';
@import 'ag-grid-community/styles/ag-theme-material.css';
</style>
```

**Recommendation**: Use Option A for consistency across all grids.

### 1.3 Configure Vite (Optional - Tree Shaking)

```javascript
// frontend/vite.config.js
export default {
  optimizeDeps: {
    include: ['ag-grid-community', 'ag-grid-vue3']
  }
}
```

---

## 2. Component Architecture

### 2.1 Reusable Grid Wrapper Component

Create a base wrapper to avoid code duplication:

**File**: `frontend/src/components/AGGridBase.vue`

```vue
<template>
  <div :class="`ag-theme-material ${customClass}`" :style="containerStyle">
    <ag-grid-vue
      :columnDefs="columnDefs"
      :rowData="rowData"
      :defaultColDef="defaultColDef"
      :gridOptions="gridOptions"
      :rowSelection="rowSelection"
      :suppressRowClickSelection="true"
      :enableRangeSelection="true"
      :enableClipboard="true"
      :singleClickEdit="true"
      :enterMovesDownAfterEdit="true"
      :animateRows="true"
      @grid-ready="onGridReady"
      @cell-value-changed="handleCellValueChanged"
      @row-editing-started="handleRowEditingStarted"
      @row-editing-stopped="handleRowEditingStopped"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'

const props = defineProps({
  columnDefs: {
    type: Array,
    required: true
  },
  rowData: {
    type: Array,
    default: () => []
  },
  height: {
    type: String,
    default: '500px'
  },
  customClass: {
    type: String,
    default: ''
  },
  rowSelection: {
    type: String,
    default: 'multiple'
  },
  gridOptions: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits([
  'grid-ready',
  'cell-value-changed',
  'row-editing-started',
  'row-editing-stopped'
])

const gridApi = ref(null)

const containerStyle = computed(() => ({
  height: props.height,
  width: '100%'
}))

// Default column configuration
const defaultColDef = {
  sortable: true,
  filter: true,
  resizable: true,
  editable: true,
  minWidth: 100,
  cellStyle: {
    fontFamily: 'Roboto, sans-serif',
    fontSize: '14px'
  }
}

const onGridReady = (params) => {
  gridApi.value = params.api
  emit('grid-ready', params)
}

const handleCellValueChanged = (event) => {
  emit('cell-value-changed', event)
}

const handleRowEditingStarted = (event) => {
  emit('row-editing-started', event)
}

const handleRowEditingStopped = (event) => {
  emit('row-editing-stopped', event)
}

// Expose grid API for parent components
defineExpose({
  gridApi
})
</script>

<style scoped>
/* Custom theme overrides */
.ag-theme-material {
  --ag-header-background-color: #1a237e; /* Match Vuetify primary */
  --ag-header-foreground-color: white;
  --ag-row-hover-color: rgba(26, 35, 126, 0.05);
  --ag-selected-row-background-color: rgba(26, 35, 126, 0.1);
}
</style>
```

---

## 3. Production Entry Grid

### 3.1 Replace `DataEntryGrid.vue`

**File**: `frontend/src/components/DataEntryGrid.vue`

```vue
<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center">
      <span class="text-h5">Production Data Entry</span>
      <div>
        <v-btn color="primary" @click="addNewEntry" class="mr-2">
          <v-icon left>mdi-plus</v-icon>
          Add Entry
        </v-btn>
        <v-btn color="success" @click="saveChanges" :disabled="!hasUnsavedChanges">
          <v-icon left>mdi-content-save</v-icon>
          Save All
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Keyboard shortcuts help -->
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        <strong>Keyboard Shortcuts:</strong>
        Tab (next cell) | Enter (down) | Ctrl+C/V (copy/paste) | Delete (clear cell)
      </v-alert>

      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="entries"
        height="600px"
        @grid-ready="onGridReady"
        @cell-value-changed="onCellValueChanged"
      />
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useKPIStore } from '@/stores/kpiStore'
import { format } from 'date-fns'
import AGGridBase from '@/components/AGGridBase.vue'

const kpiStore = useKPIStore()
const gridRef = ref(null)
const unsavedChanges = ref(new Set())

const entries = computed(() => kpiStore.productionEntries)
const products = computed(() => kpiStore.products)
const shifts = computed(() => kpiStore.shifts)
const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

// Column definitions
const columnDefs = [
  {
    headerName: 'Date',
    field: 'production_date',
    editable: true,
    cellEditor: 'agDateStringCellEditor',
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd, yyyy') : ''
    },
    cellClass: 'font-weight-bold',
    pinned: 'left', // Freeze column
    width: 130
  },
  {
    headerName: 'Product',
    field: 'product_id',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: products.value.map(p => p.product_id)
    },
    valueFormatter: (params) => {
      const product = products.value.find(p => p.product_id === params.value)
      return product?.product_name || `ID: ${params.value}`
    },
    width: 200
  },
  {
    headerName: 'Shift',
    field: 'shift_id',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: shifts.value.map(s => s.shift_id)
    },
    valueFormatter: (params) => {
      const shift = shifts.value.find(s => s.shift_id === params.value)
      return shift?.shift_name || `ID: ${params.value}`
    },
    width: 120
  },
  {
    headerName: 'Work Order',
    field: 'work_order_number',
    editable: true,
    width: 150
  },
  {
    headerName: 'Units Produced',
    field: 'units_produced',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 0
    },
    valueFormatter: (params) => {
      return params.value ? params.value.toLocaleString() : '0'
    },
    cellStyle: (params) => {
      return params.value > 0 ? { color: '#2e7d32' } : { color: '#c62828' }
    },
    width: 150
  },
  {
    headerName: 'Runtime (hrs)',
    field: 'run_time_hours',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      max: 24,
      precision: 2
    },
    width: 130
  },
  {
    headerName: 'Employees',
    field: 'employees_assigned',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 1,
      precision: 0
    },
    width: 130
  },
  {
    headerName: 'Defects',
    field: 'defect_count',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 0
    },
    width: 110
  },
  {
    headerName: 'Scrap',
    field: 'scrap_count',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 0
    },
    width: 110
  },
  {
    headerName: 'Actions',
    field: 'actions',
    editable: false,
    sortable: false,
    filter: false,
    cellRenderer: 'ActionsCellRenderer',
    width: 100,
    pinned: 'right'
  }
]

const onGridReady = (params) => {
  params.api.sizeColumnsToFit()
}

const onCellValueChanged = (event) => {
  // Mark row as unsaved
  const rowId = event.data.entry_id || event.node.id
  unsavedChanges.value.add(rowId)

  // Highlight changed row
  event.node.setDataValue('_hasChanges', true)
}

const addNewEntry = () => {
  const newEntry = {
    entry_id: null,
    production_date: format(new Date(), 'yyyy-MM-dd'),
    product_id: products.value[0]?.product_id,
    shift_id: shifts.value[0]?.shift_id,
    work_order_number: '',
    units_produced: 0,
    run_time_hours: 0,
    employees_assigned: 1,
    defect_count: 0,
    scrap_count: 0,
    _isNew: true
  }

  const api = gridRef.value?.gridApi
  if (api) {
    api.applyTransaction({ add: [newEntry], addIndex: 0 })
    api.startEditingCell({
      rowIndex: 0,
      colKey: 'production_date'
    })
  }
}

const saveChanges = async () => {
  const api = gridRef.value?.gridApi
  if (!api) return

  const allRows = []
  api.forEachNode(node => {
    if (unsavedChanges.value.has(node.data.entry_id || node.id)) {
      allRows.push(node.data)
    }
  })

  try {
    for (const row of allRows) {
      if (row._isNew) {
        await kpiStore.createProductionEntry(row)
      } else {
        await kpiStore.updateProductionEntry(row.entry_id, row)
      }
    }

    unsavedChanges.value.clear()
    await kpiStore.fetchProductionEntries()

    // Show success message
    alert('Changes saved successfully!')
  } catch (error) {
    alert('Error saving changes: ' + (error.response?.data?.detail || error.message))
  }
}

onMounted(async () => {
  await kpiStore.fetchReferenceData()
  await kpiStore.fetchProductionEntries()
})
</script>
```

### 3.2 Custom Actions Cell Renderer

**File**: `frontend/src/components/grid/ActionsCellRenderer.vue`

```vue
<template>
  <div class="d-flex justify-center">
    <v-btn icon size="small" @click="handleDelete" color="error">
      <v-icon>mdi-delete</v-icon>
    </v-btn>
  </div>
</template>

<script setup>
const props = defineProps({
  params: Object
})

const handleDelete = () => {
  if (confirm('Are you sure you want to delete this entry?')) {
    props.params.api.applyTransaction({ remove: [props.params.data] })
  }
}
</script>
```

**Register in AG Grid**:
```javascript
import ActionsCellRenderer from '@/components/grid/ActionsCellRenderer.vue'

// In component setup
const gridOptions = {
  components: {
    ActionsCellRenderer
  }
}
```

---

## 4. Attendance Entry Grid

**File**: `frontend/src/components/entries/AttendanceEntryGrid.vue`

```vue
<template>
  <v-card>
    <v-card-title>
      <v-icon class="mr-2">mdi-account-clock</v-icon>
      Attendance Entry - Bulk Grid
    </v-card-title>

    <v-card-text>
      <!-- Date and Shift Selector -->
      <v-row class="mb-3">
        <v-col cols="12" md="4">
          <v-text-field
            v-model="selectedDate"
            type="date"
            label="Date"
            variant="outlined"
            density="compact"
          />
        </v-col>
        <v-col cols="12" md="4">
          <v-select
            v-model="selectedShift"
            :items="shifts"
            item-title="shift_name"
            item-value="shift_id"
            label="Shift"
            variant="outlined"
            density="compact"
          />
        </v-col>
        <v-col cols="12" md="4">
          <v-btn color="primary" @click="loadEmployees" block>
            Load Employees
          </v-btn>
        </v-col>
      </v-row>

      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="attendanceData"
        height="600px"
        @cell-value-changed="markRowAsChanged"
      />

      <v-btn color="success" @click="saveAttendance" class="mt-3" block>
        Save Attendance Records
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AGGridBase from '@/components/AGGridBase.vue'
import api from '@/services/api'

const gridRef = ref(null)
const selectedDate = ref(new Date().toISOString().split('T')[0])
const selectedShift = ref(null)
const shifts = ref([])
const attendanceData = ref([])

const columnDefs = [
  {
    headerName: 'Employee ID',
    field: 'employee_id',
    editable: false,
    pinned: 'left',
    width: 130
  },
  {
    headerName: 'Name',
    field: 'employee_name',
    editable: false,
    pinned: 'left',
    width: 200
  },
  {
    headerName: 'Status',
    field: 'status',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['Present', 'Absent', 'Late', 'Half Day', 'Leave']
    },
    cellStyle: (params) => {
      const statusColors = {
        'Present': { backgroundColor: '#e8f5e9' },
        'Absent': { backgroundColor: '#ffebee' },
        'Late': { backgroundColor: '#fff3e0' },
        'Half Day': { backgroundColor: '#fff9c4' },
        'Leave': { backgroundColor: '#f3e5f5' }
      }
      return statusColors[params.value] || {}
    },
    width: 130
  },
  {
    headerName: 'Clock In',
    field: 'clock_in',
    editable: true,
    cellEditor: 'agTextCellEditor',
    width: 120
  },
  {
    headerName: 'Clock Out',
    field: 'clock_out',
    editable: true,
    cellEditor: 'agTextCellEditor',
    width: 120
  },
  {
    headerName: 'Absence Reason',
    field: 'absence_reason',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['Sick Leave', 'Personal Leave', 'Family Emergency', 'Medical Appointment', 'No Show', 'Unauthorized', 'Other']
    },
    cellEditorPopup: true,
    width: 180
  },
  {
    headerName: 'Excused',
    field: 'is_excused',
    editable: true,
    cellRenderer: 'agCheckboxCellRenderer',
    cellEditor: 'agCheckboxCellEditor',
    width: 100
  },
  {
    headerName: 'Late (min)',
    field: 'late_minutes',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    width: 120
  },
  {
    headerName: 'Notes',
    field: 'notes',
    editable: true,
    cellEditor: 'agLargeTextCellEditor',
    cellEditorPopup: true,
    width: 200
  }
]

const loadEmployees = async () => {
  // Load all active employees for the shift
  try {
    const response = await api.get('/employees', {
      params: { shift_id: selectedShift.value, active: true }
    })

    attendanceData.value = response.data.map(emp => ({
      employee_id: emp.employee_id,
      employee_name: emp.full_name,
      date: selectedDate.value,
      shift_id: selectedShift.value,
      status: 'Present',
      clock_in: '',
      clock_out: '',
      absence_reason: '',
      is_excused: false,
      late_minutes: 0,
      notes: ''
    }))
  } catch (error) {
    console.error('Error loading employees:', error)
  }
}

const markRowAsChanged = (event) => {
  event.data._hasChanges = true
}

const saveAttendance = async () => {
  const api = gridRef.value?.gridApi
  if (!api) return

  const changedRows = []
  api.forEachNode(node => {
    if (node.data._hasChanges) {
      changedRows.push(node.data)
    }
  })

  try {
    for (const row of changedRows) {
      await api.createAttendanceEntry(row)
    }

    alert(`${changedRows.length} attendance records saved successfully!`)
    attendanceData.value = []
  } catch (error) {
    alert('Error saving attendance: ' + error.message)
  }
}

onMounted(async () => {
  const response = await api.getShifts()
  shifts.value = response.data
})
</script>
```

---

## 5. Quality Entry Grid

**File**: `frontend/src/components/entries/QualityEntryGrid.vue`

```vue
<template>
  <v-card>
    <v-card-title>
      <v-icon class="mr-2">mdi-clipboard-check</v-icon>
      Quality Inspection - Batch Entry
    </v-card-title>

    <v-card-text>
      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="qualityData"
        height="600px"
        @cell-value-changed="onCellValueChanged"
      />

      <v-btn color="primary" @click="addRow" class="mt-3 mr-2">
        Add Inspection
      </v-btn>
      <v-btn color="success" @click="saveInspections" class="mt-3">
        Save All
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AGGridBase from '@/components/AGGridBase.vue'
import api from '@/services/api'

const gridRef = ref(null)
const qualityData = ref([])
const products = ref([])
const defectTypes = ref([])

const columnDefs = [
  {
    headerName: 'Work Order',
    field: 'work_order_id',
    editable: true,
    width: 150
  },
  {
    headerName: 'Product',
    field: 'product_id',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: products.value.map(p => p.product_id)
    },
    valueFormatter: (params) => {
      const product = products.value.find(p => p.product_id === params.value)
      return product?.product_name || params.value
    },
    width: 200
  },
  {
    headerName: 'Inspected Qty',
    field: 'inspected_quantity',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    width: 140
  },
  {
    headerName: 'Defect Qty',
    field: 'defect_quantity',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    width: 130
  },
  {
    headerName: 'FPY %',
    field: 'fpy',
    editable: false,
    valueGetter: (params) => {
      const inspected = params.data.inspected_quantity || 0
      const defects = params.data.defect_quantity || 0
      if (inspected === 0) return 0
      return ((1 - defects / inspected) * 100).toFixed(2)
    },
    cellStyle: (params) => {
      const fpy = parseFloat(params.value)
      if (fpy >= 99) return { backgroundColor: '#e8f5e9', color: '#2e7d32' }
      if (fpy >= 95) return { backgroundColor: '#fff3e0', color: '#f57c00' }
      return { backgroundColor: '#ffebee', color: '#c62828' }
    },
    width: 110
  },
  {
    headerName: 'PPM',
    field: 'ppm',
    editable: false,
    valueGetter: (params) => {
      const inspected = params.data.inspected_quantity || 0
      const defects = params.data.defect_quantity || 0
      if (inspected === 0) return 0
      return Math.round((defects / inspected) * 1000000)
    },
    width: 110
  },
  {
    headerName: 'Defect Type',
    field: 'defect_type_id',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: defectTypes.value.map(d => d.defect_type_id)
    },
    width: 150
  },
  {
    headerName: 'Severity',
    field: 'severity',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['Critical', 'Major', 'Minor', 'Cosmetic']
    },
    width: 120
  },
  {
    headerName: 'Disposition',
    field: 'disposition',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['Accept', 'Reject', 'Rework', 'Use As Is', 'Return to Supplier']
    },
    width: 150
  },
  {
    headerName: 'Inspector',
    field: 'inspector_id',
    editable: true,
    width: 130
  },
  {
    headerName: 'Notes',
    field: 'defect_description',
    editable: true,
    cellEditor: 'agLargeTextCellEditor',
    cellEditorPopup: true,
    width: 200
  }
]

const onCellValueChanged = (event) => {
  // Recalculate FPY and PPM when quantities change
  if (event.column.colId === 'inspected_quantity' || event.column.colId === 'defect_quantity') {
    event.api.refreshCells({
      rowNodes: [event.node],
      columns: ['fpy', 'ppm']
    })
  }
}

const addRow = () => {
  const newRow = {
    work_order_id: '',
    product_id: null,
    inspected_quantity: 0,
    defect_quantity: 0,
    defect_type_id: null,
    severity: '',
    disposition: '',
    inspector_id: '',
    defect_description: ''
  }

  const api = gridRef.value?.gridApi
  if (api) {
    api.applyTransaction({ add: [newRow], addIndex: 0 })
  }
}

const saveInspections = async () => {
  const api = gridRef.value?.gridApi
  if (!api) return

  const allRows = []
  api.forEachNode(node => allRows.push(node.data))

  try {
    for (const row of allRows) {
      await api.createQualityEntry(row)
    }

    alert('Quality inspections saved successfully!')
    qualityData.value = []
  } catch (error) {
    alert('Error saving inspections: ' + error.message)
  }
}

onMounted(async () => {
  const [productsRes, defectTypesRes] = await Promise.all([
    api.getProducts(),
    api.getDefectTypes()
  ])
  products.value = productsRes.data
  defectTypes.value = defectTypesRes.data
})
</script>
```

---

## 6. Integration with Pinia

### Update `kpiStore.js` to handle AG Grid data

```javascript
// frontend/src/stores/kpiStore.js

import { defineStore } from 'pinia'
import api from '@/services/api'

export const useKPIStore = defineStore('kpi', {
  state: () => ({
    productionEntries: [],
    products: [],
    shifts: [],
    loading: false,
    error: null
  }),

  actions: {
    async fetchReferenceData() {
      try {
        const [productsRes, shiftsRes] = await Promise.all([
          api.getProducts(),
          api.getShifts()
        ])
        this.products = productsRes.data
        this.shifts = shiftsRes.data
      } catch (error) {
        this.error = error.message
        throw error
      }
    },

    async fetchProductionEntries() {
      this.loading = true
      try {
        const response = await api.getProductionEntries()
        this.productionEntries = response.data
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.loading = false
      }
    },

    async createProductionEntry(data) {
      try {
        const response = await api.createProductionEntry(data)
        this.productionEntries.unshift(response.data)
        return response.data
      } catch (error) {
        this.error = error.message
        throw error
      }
    },

    async updateProductionEntry(id, data) {
      try {
        const response = await api.updateProductionEntry(id, data)
        const index = this.productionEntries.findIndex(e => e.entry_id === id)
        if (index !== -1) {
          this.productionEntries[index] = response.data
        }
        return response.data
      } catch (error) {
        this.error = error.message
        throw error
      }
    },

    async deleteProductionEntry(id) {
      try {
        await api.deleteProductionEntry(id)
        this.productionEntries = this.productionEntries.filter(e => e.entry_id !== id)
      } catch (error) {
        this.error = error.message
        throw error
      }
    }
  }
})
```

---

## 7. Styling & Theming

### 7.1 Custom Theme Variables

**File**: `frontend/src/assets/aggrid-theme.css`

```css
/* AG Grid Material Theme Customization */
.ag-theme-material {
  /* Header styling */
  --ag-header-height: 48px;
  --ag-header-background-color: #1a237e;
  --ag-header-foreground-color: white;
  --ag-header-cell-hover-background-color: #0d47a1;

  /* Row styling */
  --ag-row-height: 40px;
  --ag-row-hover-color: rgba(26, 35, 126, 0.05);
  --ag-selected-row-background-color: rgba(26, 35, 126, 0.1);

  /* Cell styling */
  --ag-cell-horizontal-padding: 12px;
  --ag-font-size: 14px;
  --ag-font-family: 'Roboto', sans-serif;

  /* Borders */
  --ag-borders: solid 1px #e0e0e0;
  --ag-border-color: #e0e0e0;

  /* Focus */
  --ag-range-selection-border-color: #1a237e;
  --ag-range-selection-background-color: rgba(26, 35, 126, 0.1);
}

/* Custom cell classes */
.ag-cell-error {
  background-color: #ffebee !important;
  color: #c62828;
}

.ag-cell-warning {
  background-color: #fff3e0 !important;
  color: #f57c00;
}

.ag-cell-success {
  background-color: #e8f5e9 !important;
  color: #2e7d32;
}

/* Highlight unsaved changes */
.ag-row-unsaved {
  border-left: 4px solid #f57c00;
}
```

Import in `main.js`:
```javascript
import '@/assets/aggrid-theme.css'
```

---

## 8. Testing Strategy

### 8.1 Unit Tests (Vitest)

**File**: `frontend/src/components/__tests__/DataEntryGrid.spec.js`

```javascript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import DataEntryGrid from '@/components/DataEntryGrid.vue'

describe('DataEntryGrid', () => {
  let wrapper
  let pinia

  beforeEach(() => {
    pinia = createPinia()
    wrapper = mount(DataEntryGrid, {
      global: {
        plugins: [pinia]
      }
    })
  })

  it('renders AG Grid component', () => {
    expect(wrapper.find('.ag-theme-material').exists()).toBe(true)
  })

  it('adds new entry when Add Entry button clicked', async () => {
    const addButton = wrapper.find('button')
    await addButton.trigger('click')

    // Verify new row added to grid
    // (requires AG Grid API access)
  })

  it('validates numeric inputs', () => {
    const columnDef = wrapper.vm.columnDefs.find(col => col.field === 'units_produced')
    expect(columnDef.cellEditorParams.min).toBe(0)
  })
})
```

### 8.2 E2E Tests (Playwright)

**File**: `frontend/e2e/production-entry.spec.js`

```javascript
import { test, expect } from '@playwright/test'

test.describe('Production Entry Grid', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[name="email"]', 'test@example.com')
    await page.fill('input[name="password"]', 'password')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')
  })

  test('should allow adding new production entry', async ({ page }) => {
    await page.goto('/production-entry')

    // Click Add Entry
    await page.click('text=Add Entry')

    // Fill in production data
    await page.fill('.ag-cell[col-id="production_date"] input', '2026-01-15')
    await page.selectOption('.ag-cell[col-id="product_id"] select', { index: 1 })
    await page.fill('.ag-cell[col-id="units_produced"] input', '1000')

    // Save
    await page.click('text=Save All')

    // Verify success message
    await expect(page.locator('text=Changes saved successfully')).toBeVisible()
  })

  test('should support keyboard navigation', async ({ page }) => {
    await page.goto('/production-entry')
    await page.click('text=Add Entry')

    // Focus first cell
    await page.focus('.ag-cell[col-id="production_date"]')

    // Press Tab to move to next cell
    await page.keyboard.press('Tab')

    // Verify focus moved
    await expect(page.locator('.ag-cell[col-id="product_id"]:focus')).toBeVisible()
  })

  test('should support copy/paste', async ({ page }) => {
    await page.goto('/production-entry')

    // Select cells
    await page.click('.ag-cell[row-index="0"][col-id="units_produced"]')

    // Copy (Ctrl+C)
    await page.keyboard.press('Control+C')

    // Paste (Ctrl+V) in another cell
    await page.click('.ag-cell[row-index="1"][col-id="units_produced"]')
    await page.keyboard.press('Control+V')

    // Verify value copied
    // (requires checking cell value)
  })
})
```

---

## 9. Migration Checklist

- [ ] Install AG Grid dependencies
- [ ] Create `AGGridBase.vue` wrapper component
- [ ] Replace `DataEntryGrid.vue` with AG Grid implementation
- [ ] Create `ActionsCellRenderer.vue` for delete actions
- [ ] Update `kpiStore.js` for AG Grid data handling
- [ ] Implement Attendance Entry Grid
- [ ] Implement Quality Entry Grid
- [ ] Add custom CSS theme overrides
- [ ] Write unit tests for grid components
- [ ] Write E2E tests for keyboard navigation and copy/paste
- [ ] Update user documentation with keyboard shortcuts
- [ ] Conduct user acceptance testing (UAT)
- [ ] Deploy to staging environment
- [ ] Train operators on new Excel-like features
- [ ] Monitor performance metrics (data entry time)
- [ ] Gather feedback and iterate

---

## 10. Performance Optimization

### 10.1 Virtual Scrolling (Enabled by Default)

AG Grid uses virtual DOM rendering, so only visible rows are rendered.

**Configuration**:
```javascript
const gridOptions = {
  rowModelType: 'clientSide', // Default
  rowBuffer: 10, // Rows to render outside viewport
  debounceVerticalScrollbar: true
}
```

### 10.2 Lazy Loading for Large Datasets

For 10,000+ rows, use infinite scroll model:

```javascript
const gridOptions = {
  rowModelType: 'infinite',
  cacheBlockSize: 100, // Fetch 100 rows at a time
  cacheOverflowSize: 2,
  maxConcurrentDatasourceRequests: 2,
  infiniteInitialRowCount: 1000
}
```

### 10.3 Bundle Size Optimization

Use tree-shaking to reduce bundle size:

```javascript
// Instead of importing all of AG Grid
import { AgGridVue } from 'ag-grid-vue3'

// Only import required modules
import { ModuleRegistry } from 'ag-grid-community'
import { ClientSideRowModelModule } from 'ag-grid-community'
import { ClipboardModule } from 'ag-grid-community'

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  ClipboardModule
])
```

---

## 11. Support Resources

- **AG Grid Documentation**: https://www.ag-grid.com/vue-data-grid/
- **Vue 3 Examples**: https://www.ag-grid.com/vue-data-grid/getting-started/
- **Community Forum**: https://github.com/ag-grid/ag-grid/discussions
- **StackOverflow**: `[ag-grid] [vue.js]`

---

**Next Steps**: Begin Phase 4.1 implementation (Production Entry Grid).
