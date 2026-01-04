# AG Grid Component Usage Examples

## Quick Integration Guide

### 1. Production Entry Grid

**Replace existing `DataEntryGrid.vue` component in views:**

```vue
<!-- Before (Old Vuetify v-data-table) -->
<template>
  <DataEntryGrid />
</template>

<script setup>
import DataEntryGrid from '@/components/DataEntryGrid.vue'
</script>
```

```vue
<!-- After (New AG Grid) -->
<template>
  <ProductionEntryGrid />
</template>

<script setup>
import ProductionEntryGrid from '@/components/grids/ProductionEntryGrid.vue'
</script>
```

**Full View Example** (`views/ProductionEntry.vue`):

```vue
<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <ProductionEntryGrid />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import ProductionEntryGrid from '@/components/grids/ProductionEntryGrid.vue'
</script>
```

---

### 2. Attendance Entry Grid

**Create new route** (`router/index.js`):

```javascript
{
  path: '/attendance-entry',
  name: 'AttendanceEntry',
  component: () => import('@/views/AttendanceEntry.vue'),
  meta: { requiresAuth: true }
}
```

**Create view** (`views/AttendanceEntry.vue`):

```vue
<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <h1 class="mb-4">Bulk Attendance Entry</h1>
        <AttendanceEntryGrid />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import AttendanceEntryGrid from '@/components/grids/AttendanceEntryGrid.vue'
</script>
```

**Add to navigation menu** (`App.vue` or `components/NavigationDrawer.vue`):

```vue
<v-list-item to="/attendance-entry">
  <template v-slot:prepend>
    <v-icon>mdi-account-clock</v-icon>
  </template>
  <v-list-item-title>Bulk Attendance</v-list-item-title>
</v-list-item>
```

---

### 3. Quality Entry Grid

**Create new route** (`router/index.js`):

```javascript
{
  path: '/quality-entry',
  name: 'QualityEntry',
  component: () => import('@/views/QualityEntry.vue'),
  meta: { requiresAuth: true }
}
```

**Create view** (`views/QualityEntry.vue`):

```vue
<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <h1 class="mb-4">Quality Inspection - Batch Entry</h1>
        <QualityEntryGrid />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import QualityEntryGrid from '@/components/grids/QualityEntryGrid.vue'
</script>
```

---

### 4. Custom Grid with AGGridBase

**Example: Custom Employee Grid**

```vue
<template>
  <v-card>
    <v-card-title>Employee Management</v-card-title>
    <v-card-text>
      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="employees"
        height="500px"
        :pagination="true"
        @cell-value-changed="handleChange"
        @grid-ready="onGridReady"
      />

      <v-btn @click="exportToExcel" class="mt-3">
        Export to Excel
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import api from '@/services/api'

const gridRef = ref(null)
const employees = ref([])

const columnDefs = [
  {
    headerName: 'ID',
    field: 'employee_id',
    editable: false,
    width: 100
  },
  {
    headerName: 'Name',
    field: 'full_name',
    editable: true,
    width: 200
  },
  {
    headerName: 'Department',
    field: 'department',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['Production', 'Quality', 'Maintenance', 'Warehouse']
    },
    width: 150
  },
  {
    headerName: 'Status',
    field: 'status',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['Active', 'Inactive', 'On Leave']
    },
    cellStyle: (params) => {
      return params.value === 'Active'
        ? { backgroundColor: '#e8f5e9', color: '#2e7d32' }
        : { backgroundColor: '#ffebee', color: '#c62828' }
    },
    width: 120
  },
  {
    headerName: 'Hire Date',
    field: 'hire_date',
    editable: true,
    cellEditor: 'agDateStringCellEditor',
    width: 140
  }
]

const onGridReady = (params) => {
  params.api.sizeColumnsToFit()
}

const handleChange = (event) => {
  console.log('Cell changed:', event.data)
  // Auto-save to backend
  saveEmployee(event.data)
}

const exportToExcel = () => {
  gridRef.value.exportToCsv('employees.csv')
}

const saveEmployee = async (employee) => {
  try {
    await api.updateEmployee(employee.employee_id, employee)
  } catch (error) {
    console.error('Error saving employee:', error)
  }
}

onMounted(async () => {
  const response = await api.get('/employees')
  employees.value = response.data
})
</script>
```

---

## Advanced Features

### 1. Cell Renderers (Custom Cell Display)

```javascript
const columnDefs = [
  {
    headerName: 'Status',
    field: 'status',
    cellRenderer: (params) => {
      const statusIcons = {
        'Active': '✓',
        'Inactive': '✗',
        'On Leave': '⏸'
      }
      return `<span style="font-size: 18px;">${statusIcons[params.value]}</span>`
    }
  }
]
```

### 2. Value Getters (Computed Columns)

```javascript
const columnDefs = [
  {
    headerName: 'Full Name',
    valueGetter: (params) => {
      return `${params.data.first_name} ${params.data.last_name}`
    }
  },
  {
    headerName: 'Efficiency',
    valueGetter: (params) => {
      return (params.data.units_produced / params.data.run_time_hours).toFixed(2)
    }
  }
]
```

### 3. Cell Styling (Conditional Formatting)

```javascript
const columnDefs = [
  {
    headerName: 'Performance',
    field: 'performance',
    cellStyle: (params) => {
      if (params.value >= 95) {
        return { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' }
      } else if (params.value >= 85) {
        return { backgroundColor: '#fff3e0', color: '#f57c00' }
      } else {
        return { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
      }
    }
  }
]
```

### 4. Custom Validators

```javascript
const columnDefs = [
  {
    headerName: 'Email',
    field: 'email',
    editable: true,
    cellEditor: 'agTextCellEditor',
    cellEditorParams: {
      validation: (newValue) => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        return emailRegex.test(newValue)
      }
    }
  }
]
```

---

## Keyboard Shortcuts Reference Card

**Print this for operators:**

```
╔════════════════════════════════════════════════════════╗
║          AG GRID KEYBOARD SHORTCUTS                    ║
╠════════════════════════════════════════════════════════╣
║ NAVIGATION                                             ║
║  Tab              → Move to next cell                  ║
║  Shift + Tab      → Move to previous cell              ║
║  Enter            → Move down to next row              ║
║  Arrow Keys       → Navigate between cells             ║
║                                                        ║
║ EDITING                                                ║
║  F2               → Start editing cell                 ║
║  Esc              → Cancel editing                     ║
║  Delete           → Clear cell contents                ║
║                                                        ║
║ CLIPBOARD                                              ║
║  Ctrl + C         → Copy selected cells                ║
║  Ctrl + V         → Paste from clipboard               ║
║  Ctrl + X         → Cut selected cells                 ║
║                                                        ║
║ UNDO/REDO                                              ║
║  Ctrl + Z         → Undo last change                   ║
║  Ctrl + Y         → Redo change                        ║
║                                                        ║
║ SELECTION                                              ║
║  Ctrl + A         → Select all cells                   ║
║  Shift + Click    → Extend selection                   ║
║  Ctrl + Click     → Multi-select cells                 ║
║                                                        ║
║ ADVANCED                                               ║
║  Ctrl + D         → Fill down (copy to selected)       ║
║  Drag corner      → Fill handle (Excel-like)           ║
╚════════════════════════════════════════════════════════╝
```

---

## Troubleshooting

### Grid Not Rendering

**Problem**: Grid shows empty or doesn't appear

**Solution**:
```javascript
// Make sure AG Grid styles are imported in main.js
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-material.css'

// Make sure container has height set
<AGGridBase height="600px" ... />
```

### Copy/Paste Not Working

**Problem**: Clipboard operations don't work

**Solution**:
```javascript
// Ensure enableClipboard is true in AGGridBase
:enableClipboard="true"

// Check browser clipboard permissions
// Chrome: Site Settings → Permissions → Clipboard
```

### Columns Too Narrow

**Problem**: Columns are compressed or text is cut off

**Solution**:
```javascript
// Auto-size columns on grid ready
const onGridReady = (params) => {
  params.api.sizeColumnsToFit()
  // OR auto-size specific columns
  params.columnApi.autoSizeAllColumns()
}
```

### Performance Issues with Large Datasets

**Problem**: Grid is slow with 1000+ rows

**Solution**:
```javascript
// Enable pagination
<AGGridBase
  :pagination="true"
  :paginationPageSize="100"
/>

// OR use server-side row model (requires backend changes)
:rowModelType="'serverSide'"
```

---

## Migration Path from Old Components

### Step 1: Install Dependencies
```bash
npm install ag-grid-community@35.0.0 ag-grid-vue3@35.0.0
```

### Step 2: Update main.js
```javascript
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-material.css'
import './assets/aggrid-theme.css'
```

### Step 3: Replace Old Components
1. Backup existing component: `cp DataEntryGrid.vue DataEntryGrid.vue.old`
2. Update imports in views to use new grid components
3. Test all data entry workflows
4. Remove old components after testing

### Step 4: Update Routes (if needed)
```javascript
// router/index.js
const routes = [
  // ... existing routes
  {
    path: '/attendance-bulk',
    name: 'AttendanceBulk',
    component: () => import('@/views/AttendanceEntry.vue')
  },
  {
    path: '/quality-batch',
    name: 'QualityBatch',
    component: () => import('@/views/QualityEntry.vue')
  }
]
```

---

## Testing Checklist

### Manual Testing

**Production Entry Grid:**
- [ ] Add new entry
- [ ] Edit existing entry
- [ ] Delete entry
- [ ] Save changes
- [ ] Filter by date
- [ ] Filter by product
- [ ] Filter by shift
- [ ] Copy/paste from Excel
- [ ] Keyboard navigation works
- [ ] Summary stats update correctly

**Attendance Entry Grid:**
- [ ] Load employees (50+)
- [ ] Mark all present
- [ ] Edit individual status
- [ ] Add absence reason
- [ ] Save bulk changes
- [ ] Status counts update
- [ ] Handle 200+ employees

**Quality Entry Grid:**
- [ ] Add new inspection
- [ ] FPY calculates correctly
- [ ] PPM calculates correctly
- [ ] Color coding works
- [ ] Save batch entries
- [ ] Delete inspection

---

**Last Updated**: January 2, 2026
**Component Versions**:
- ag-grid-community: 35.0.0
- ag-grid-vue3: 35.0.0
- Vue: 3.4.0
- Vuetify: 3.5.0
