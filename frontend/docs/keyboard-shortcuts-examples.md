# Keyboard Shortcuts - Practical Examples

## Example 1: Enhanced Production Entry Component

This example shows how to integrate keyboard shortcuts into the existing `DataEntryGrid.vue` component.

### Updated DataEntryGrid.vue

```vue
<template>
  <v-card>
    <v-card-title>
      <span class="text-h5">Production Data Entry</span>
      <v-spacer></v-spacer>
      <v-btn color="primary" @click="addNewEntry">
        <v-icon left>mdi-plus</v-icon>
        Add Entry
        <KeyboardShortcutHint shortcut="ctrl+n" />
      </v-btn>
    </v-card-title>

    <v-card-text>
      <!-- Enhanced with keyboard shortcuts info -->
      <div class="mb-3 d-flex align-center">
        <v-chip size="small" variant="outlined">
          <v-icon start size="small">mdi-information</v-icon>
          Press <kbd class="mx-1">Ctrl+/</kbd> for keyboard shortcuts help
        </v-chip>
      </div>

      <v-data-table
        :headers="headers"
        :items="entries"
        :loading="loading"
        class="elevation-1"
        item-key="entry_id"
      >
        <!-- Existing templates... -->
      </v-data-table>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useKPIStore } from '@/stores/kpiStore'
import { format } from 'date-fns'
import KeyboardShortcutHint from '@/components/KeyboardShortcutHint.vue'

const kpiStore = useKPIStore()

// ... existing code ...

// Keyboard shortcut handlers
const handleSave = () => {
  // Find the entry being edited and save it
  const editingEntry = entries.value.find(e => e.editing)
  if (editingEntry) {
    saveEntry(editingEntry)
  }
}

const handleNew = () => {
  addNewEntry()
}

const handleEscape = () => {
  // Cancel any editing entry
  const editingEntry = entries.value.find(e => e.editing)
  if (editingEntry) {
    cancelEdit(editingEntry)
  }
}

// Setup event listeners
onMounted(async () => {
  await kpiStore.fetchReferenceData()
  await kpiStore.fetchProductionEntries()

  // Listen for keyboard shortcuts
  window.addEventListener('keyboard-shortcut:save', handleSave)
  window.addEventListener('keyboard-shortcut:new', handleNew)
  window.addEventListener('keyboard-shortcut:escape', handleEscape)
})

onUnmounted(() => {
  // Cleanup listeners
  window.removeEventListener('keyboard-shortcut:save', handleSave)
  window.removeEventListener('keyboard-shortcut:new', handleNew)
  window.removeEventListener('keyboard-shortcut:escape', handleEscape)
})
</script>

<style scoped>
kbd {
  display: inline-block;
  padding: 2px 6px;
  font-family: monospace;
  font-size: 11px;
  background: #f5f5f5;
  border: 1px solid #ccc;
  border-radius: 3px;
}
</style>
```

## Example 2: AG Grid with Full Shortcuts Support

Create a new enhanced grid component:

### EnhancedDataGrid.vue

```vue
<template>
  <div class="enhanced-data-grid">
    <!-- Toolbar with shortcut hints -->
    <v-toolbar dense color="grey-lighten-4">
      <v-toolbar-title>{{ title }}</v-toolbar-title>
      <v-spacer />

      <v-btn size="small" @click="handleAdd" class="mr-2">
        <v-icon left>mdi-plus</v-icon>
        Add
        <KeyboardShortcutHint shortcut="ctrl+n" />
      </v-btn>

      <v-btn size="small" @click="handleSave" class="mr-2">
        <v-icon left>mdi-content-save</v-icon>
        Save
        <KeyboardShortcutHint shortcut="ctrl+s" />
      </v-btn>

      <v-btn size="small" @click="handleRefresh" class="mr-2">
        <v-icon left>mdi-refresh</v-icon>
        Refresh
        <KeyboardShortcutHint shortcut="ctrl+r" />
      </v-btn>

      <v-menu>
        <template v-slot:activator="{ props }">
          <v-btn size="small" v-bind="props">
            <v-icon left>mdi-export</v-icon>
            Export
          </v-btn>
        </template>
        <v-list density="compact">
          <v-list-item @click="exportToCsv">
            <v-list-item-title>
              Export to CSV
              <KeyboardShortcutHint shortcut="ctrl+shift+e" />
            </v-list-item-title>
          </v-list-item>
          <v-list-item @click="exportToExcel">
            <v-list-item-title>Export to Excel</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </v-toolbar>

    <!-- Grid status bar -->
    <div class="grid-status-bar pa-2 text-caption">
      <span v-if="selectedCount > 0">
        {{ selectedCount }} row(s) selected
      </span>
      <span v-else-if="isGridFocused" class="text-primary">
        <v-icon size="small">mdi-keyboard</v-icon>
        Grid active - keyboard shortcuts enabled
      </span>
      <v-spacer />
      <v-chip v-if="undoStack.length > 0" size="x-small" class="mr-2">
        Undo: {{ undoStack.length }}
        <KeyboardShortcutHint shortcut="ctrl+z" />
      </v-chip>
      <v-chip v-if="clipboardData" size="x-small">
        <v-icon start size="small">mdi-content-copy</v-icon>
        Clipboard ready
        <KeyboardShortcutHint shortcut="ctrl+v" />
      </v-chip>
    </div>

    <!-- AG Grid -->
    <ag-grid-vue
      ref="gridRef"
      :columnDefs="columnDefs"
      :rowData="rowData"
      :defaultColDef="defaultColDef"
      :rowSelection="rowSelection"
      @grid-ready="onGridReady"
      @selection-changed="onSelectionChanged"
      class="ag-theme-alpine"
      :style="{ height: gridHeight }"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { useGridShortcuts } from '@/composables/useGridShortcuts'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import KeyboardShortcutHint from '@/components/KeyboardShortcutHint.vue'

const props = defineProps({
  title: {
    type: String,
    default: 'Data Grid'
  },
  columnDefs: {
    type: Array,
    required: true
  },
  rowData: {
    type: Array,
    required: true
  },
  gridHeight: {
    type: String,
    default: '600px'
  }
})

const emit = defineEmits(['add', 'save', 'refresh', 'export'])

const gridRef = ref(null)
const gridApi = ref(null)
const selectedCount = ref(0)

const defaultColDef = {
  sortable: true,
  filter: true,
  resizable: true,
  editable: true
}

const rowSelection = 'multiple'

const onGridReady = (params) => {
  gridApi.value = params.api
}

const onSelectionChanged = () => {
  if (gridApi.value) {
    selectedCount.value = gridApi.value.getSelectedRows().length
  }
}

// Use grid shortcuts
const { clipboardData, undoStack, isGridFocused } = useGridShortcuts(gridApi)

// Register custom shortcuts
const { registerShortcut } = useKeyboardShortcuts({ registerGlobal: false })

// Handlers
const handleAdd = () => emit('add')
const handleSave = () => emit('save')
const handleRefresh = () => emit('refresh')

const exportToCsv = () => {
  if (gridApi.value) {
    gridApi.value.exportDataAsCsv()
  }
}

const exportToExcel = () => {
  if (gridApi.value) {
    gridApi.value.exportDataAsExcel()
  }
}

// Setup
onMounted(() => {
  // Register export shortcut
  registerShortcut('export-csv', {
    key: 'e',
    ctrl: true,
    shift: true,
    description: 'Export to CSV',
    category: 'Grid Actions',
    context: () => isGridFocused.value,
    handler: exportToCsv
  })

  // Listen for global shortcuts
  window.addEventListener('keyboard-shortcut:save', handleSave)
  window.addEventListener('keyboard-shortcut:new', handleAdd)
  window.addEventListener('keyboard-shortcut:refresh', handleRefresh)
})

onUnmounted(() => {
  window.removeEventListener('keyboard-shortcut:save', handleSave)
  window.removeEventListener('keyboard-shortcut:new', handleAdd)
  window.removeEventListener('keyboard-shortcut:refresh', handleRefresh)
})
</script>

<style scoped>
.enhanced-data-grid {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.grid-status-bar {
  display: flex;
  align-items: center;
  background: #f5f5f5;
  border-top: 1px solid #e0e0e0;
  min-height: 36px;
}
</style>
```

## Example 3: Smart Form with Full Keyboard Navigation

### SmartForm.vue

```vue
<template>
  <v-card>
    <v-card-title>
      {{ formTitle }}
      <v-spacer />
      <v-chip size="small" variant="outlined">
        <v-icon start size="small">mdi-keyboard</v-icon>
        Keyboard navigation enabled
      </v-chip>
    </v-card-title>

    <v-card-text>
      <form ref="formRef" @submit.prevent="handleSubmit">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.productionDate"
              label="Production Date"
              type="date"
              required
              :error-messages="errors.productionDate"
            />
          </v-col>

          <v-col cols="12" md="6">
            <v-select
              v-model="formData.productId"
              label="Product"
              :items="products"
              item-title="product_name"
              item-value="product_id"
              required
              :error-messages="errors.productId"
            />
          </v-col>

          <v-col cols="12" md="6">
            <v-select
              v-model="formData.shiftId"
              label="Shift"
              :items="shifts"
              item-title="shift_name"
              item-value="shift_id"
              required
              :error-messages="errors.shiftId"
            />
          </v-col>

          <v-col cols="12" md="6">
            <v-text-field
              v-model.number="formData.unitsProduced"
              label="Units Produced"
              type="number"
              required
              :error-messages="errors.unitsProduced"
            />
          </v-col>

          <v-col cols="12" md="6">
            <v-text-field
              v-model.number="formData.runTimeHours"
              label="Run Time (hours)"
              type="number"
              step="0.1"
              required
              :error-messages="errors.runTimeHours"
            />
          </v-col>

          <v-col cols="12" md="6">
            <v-text-field
              v-model.number="formData.employeesAssigned"
              label="Employees Assigned"
              type="number"
              required
              :error-messages="errors.employeesAssigned"
            />
          </v-col>
        </v-row>

        <!-- Keyboard shortcuts guide -->
        <v-alert type="info" variant="tonal" class="mt-4">
          <div class="text-caption">
            <strong>Quick Actions:</strong>
            <v-chip size="x-small" class="ml-2">Ctrl+S to Save</v-chip>
            <v-chip size="x-small" class="ml-2">Esc to Cancel</v-chip>
            <v-chip size="x-small" class="ml-2">Ctrl+↑/↓ to navigate fields</v-chip>
            <v-chip size="x-small" class="ml-2">Ctrl+E to jump to first error</v-chip>
          </div>
        </v-alert>
      </form>
    </v-card-text>

    <v-card-actions>
      <v-spacer />
      <v-btn @click="handleCancel">
        Cancel
        <KeyboardShortcutHint shortcut="esc" />
      </v-btn>
      <v-btn @click="handleReset" variant="outlined">
        Reset
        <KeyboardShortcutHint shortcut="ctrl+shift+r" />
      </v-btn>
      <v-btn color="primary" @click="handleSubmit">
        Save
        <KeyboardShortcutHint shortcut="ctrl+s" />
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useFormShortcuts } from '@/composables/useFormShortcuts'
import KeyboardShortcutHint from '@/components/KeyboardShortcutHint.vue'

const props = defineProps({
  formTitle: {
    type: String,
    default: 'Production Entry Form'
  },
  products: {
    type: Array,
    required: true
  },
  shifts: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['submit', 'cancel'])

const formRef = ref(null)
const formData = reactive({
  productionDate: '',
  productId: null,
  shiftId: null,
  unitsProduced: 0,
  runTimeHours: 0,
  employeesAssigned: 1
})

const errors = reactive({
  productionDate: [],
  productId: [],
  shiftId: [],
  unitsProduced: [],
  runTimeHours: [],
  employeesAssigned: []
})

const validate = () => {
  // Reset errors
  Object.keys(errors).forEach(key => {
    errors[key] = []
  })

  let isValid = true

  if (!formData.productionDate) {
    errors.productionDate = ['Production date is required']
    isValid = false
  }

  if (!formData.productId) {
    errors.productId = ['Product is required']
    isValid = false
  }

  if (!formData.shiftId) {
    errors.shiftId = ['Shift is required']
    isValid = false
  }

  if (formData.unitsProduced <= 0) {
    errors.unitsProduced = ['Units produced must be greater than 0']
    isValid = false
  }

  if (formData.runTimeHours <= 0) {
    errors.runTimeHours = ['Run time must be greater than 0']
    isValid = false
  }

  if (formData.employeesAssigned <= 0) {
    errors.employeesAssigned = ['At least 1 employee must be assigned']
    isValid = false
  }

  return isValid
}

const handleSubmit = () => {
  if (validate()) {
    emit('submit', { ...formData })
  } else {
    // Focus first invalid field
    focusFirstInvalidField()
  }
}

const handleCancel = () => {
  emit('cancel')
}

const handleReset = () => {
  Object.assign(formData, {
    productionDate: '',
    productId: null,
    shiftId: null,
    unitsProduced: 0,
    runTimeHours: 0,
    employeesAssigned: 1
  })
  Object.keys(errors).forEach(key => {
    errors[key] = []
  })
}

// Use form shortcuts
const { focusFirstInvalidField } = useFormShortcuts(formRef, {
  onSave: handleSubmit,
  onCancel: handleCancel,
  onReset: handleReset
})
</script>
```

## Example 4: Quick Actions Menu with Shortcuts

### QuickActionsMenu.vue

```vue
<template>
  <v-menu v-model="isOpen" :close-on-content-click="false">
    <template v-slot:activator="{ props }">
      <v-btn v-bind="props" icon>
        <v-icon>mdi-lightning-bolt</v-icon>
      </v-btn>
    </template>

    <v-card min-width="300">
      <v-card-title class="text-subtitle-1">
        Quick Actions
        <v-chip size="x-small" class="ml-2">Ctrl+K</v-chip>
      </v-card-title>

      <v-list density="compact">
        <v-list-item
          v-for="action in actions"
          :key="action.id"
          @click="executeAction(action)"
        >
          <template v-slot:prepend>
            <v-icon :icon="action.icon" />
          </template>

          <v-list-item-title>
            {{ action.title }}
          </v-list-item-title>

          <template v-slot:append v-if="action.shortcut">
            <KeyboardShortcutHint :shortcut="action.shortcut" />
          </template>
        </v-list-item>
      </v-list>
    </v-card>
  </v-menu>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import KeyboardShortcutHint from '@/components/KeyboardShortcutHint.vue'

const router = useRouter()
const isOpen = ref(false)

const actions = [
  {
    id: 'dashboard',
    title: 'Go to Dashboard',
    icon: 'mdi-view-dashboard',
    shortcut: 'ctrl+d',
    handler: () => router.push('/')
  },
  {
    id: 'production',
    title: 'Production Entry',
    icon: 'mdi-factory',
    shortcut: 'ctrl+p',
    handler: () => router.push('/production-entry')
  },
  {
    id: 'quality',
    title: 'Quality Entry',
    icon: 'mdi-quality-high',
    shortcut: 'ctrl+q',
    handler: () => router.push('/data-entry/quality')
  },
  {
    id: 'divider1',
    divider: true
  },
  {
    id: 'shortcuts',
    title: 'Keyboard Shortcuts',
    icon: 'mdi-keyboard',
    shortcut: 'ctrl+/',
    handler: () => {
      // Trigger help modal
      window.dispatchEvent(new CustomEvent('show-shortcuts-help'))
    }
  }
]

const executeAction = (action) => {
  if (action.handler) {
    action.handler()
    isOpen.value = false
  }
}
</script>
```

## Usage in Your Application

### 1. Update Production Entry View

```vue
<!-- views/ProductionEntry.vue -->
<template>
  <EnhancedDataGrid
    title="Production Entries"
    :columnDefs="columnDefs"
    :rowData="entries"
    @add="handleAdd"
    @save="handleSave"
    @refresh="handleRefresh"
  />
</template>

<script setup>
import EnhancedDataGrid from '@/components/EnhancedDataGrid.vue'
// ... rest of your code
</script>
```

### 2. Update Forms

Replace existing forms with `SmartForm`:

```vue
<SmartForm
  form-title="New Production Entry"
  :products="products"
  :shifts="shifts"
  @submit="handleSubmit"
  @cancel="handleCancel"
/>
```

### 3. Add Quick Actions to App Bar

```vue
<!-- App.vue -->
<v-app-bar>
  <!-- ... existing items ... -->
  <QuickActionsMenu />
  <!-- ... rest ... -->
</v-app-bar>
```

## Testing Your Integration

1. **Test Global Shortcuts**: Press `Ctrl+/` to open help modal
2. **Test Navigation**: Press `Ctrl+D` to go to dashboard
3. **Test Grid Shortcuts**: Focus a grid and use arrow keys, Tab, Ctrl+C, etc.
4. **Test Form Shortcuts**: Focus a form and use Ctrl+↑/↓ for navigation
5. **Test Save**: Press `Ctrl+S` in any form or grid
6. **Test Escape**: Press `Esc` to cancel editing or close modals

## Performance Tips

1. **Lazy Register Shortcuts**: Only register shortcuts when component is mounted
2. **Clean Up**: Always unregister shortcuts on unmount
3. **Use Context**: Only enable shortcuts when relevant (grid focused, form active, etc.)
4. **Debounce Handlers**: For expensive operations, debounce the shortcut handlers

```javascript
import { debounce } from 'lodash-es'

const handleSearch = debounce(() => {
  // Expensive search operation
}, 300)

registerShortcut('search', {
  key: 'f',
  ctrl: true,
  handler: handleSearch
})
```

## Next Steps

1. Add shortcuts to all your existing components
2. Test across different browsers and platforms
3. Gather user feedback
4. Add more custom shortcuts based on user needs
5. Consider adding a command palette (Ctrl+K) for advanced users
