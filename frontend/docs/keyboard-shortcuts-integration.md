# Keyboard Shortcuts Integration Guide

## Overview

This guide shows how to integrate keyboard shortcuts into your Vue components, both for AG Grid data tables and standard forms.

## Table of Contents

1. [Global Shortcuts](#global-shortcuts)
2. [Grid Integration](#grid-integration)
3. [Form Integration](#form-integration)
4. [Custom Shortcuts](#custom-shortcuts)
5. [Visual Hints](#visual-hints)
6. [Best Practices](#best-practices)

## Global Shortcuts

Global shortcuts are automatically registered when the app loads. They work anywhere in the application.

### Using the Composable

```vue
<script setup>
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'

// Access help modal and utilities
const {
  isHelpModalOpen,
  toggleHelpModal,
  modifierSymbol
} = useKeyboardShortcuts()

// The global shortcuts are automatically registered
</script>
```

### Listening to Global Shortcut Events

```vue
<script setup>
import { onMounted, onUnmounted } from 'vue'

const handleSave = () => {
  console.log('Save triggered by Ctrl+S')
  // Your save logic here
}

const handleNew = () => {
  console.log('New entry triggered by Ctrl+N')
  // Your new entry logic here
}

onMounted(() => {
  // Listen for global shortcut events
  window.addEventListener('keyboard-shortcut:save', handleSave)
  window.addEventListener('keyboard-shortcut:new', handleNew)
  window.addEventListener('keyboard-shortcut:refresh', handleRefresh)
})

onUnmounted(() => {
  // Clean up listeners
  window.removeEventListener('keyboard-shortcut:save', handleSave)
  window.removeEventListener('keyboard-shortcut:new', handleNew)
  window.removeEventListener('keyboard-shortcut:refresh', handleRefresh)
})
</script>
```

## Grid Integration

### Basic AG Grid Integration

```vue
<template>
  <ag-grid-vue
    ref="gridRef"
    :columnDefs="columnDefs"
    :rowData="rowData"
    @grid-ready="onGridReady"
    class="ag-theme-alpine"
  />
</template>

<script setup>
import { ref } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { useGridShortcuts } from '@/composables/useGridShortcuts'

const gridRef = ref(null)
const gridApi = ref(null)

const columnDefs = ref([
  { field: 'name', editable: true },
  { field: 'age', editable: true },
  { field: 'country', editable: true }
])

const rowData = ref([
  { name: 'John', age: 30, country: 'USA' },
  { name: 'Jane', age: 25, country: 'UK' }
])

const onGridReady = (params) => {
  gridApi.value = params.api
}

// Enable grid shortcuts
useGridShortcuts(gridApi)
</script>
```

### Advanced Grid Integration with Custom Handlers

```vue
<script setup>
import { ref, watch } from 'vue'
import { useGridShortcuts } from '@/composables/useGridShortcuts'
import { useToast } from '@/composables/useToast'

const gridApi = ref(null)
const { clipboardData, undoStack, isGridFocused } = useGridShortcuts(gridApi)
const toast = useToast()

// Watch for clipboard operations
watch(clipboardData, (newData) => {
  if (newData) {
    toast.success(`Copied ${newData.type === 'rows' ? newData.data.length : 1} item(s)`)
  }
})

// Watch for undo/redo
watch(undoStack, (stack) => {
  console.log(`Undo stack has ${stack.length} items`)
})
</script>
```

## Form Integration

### Basic Form Integration

```vue
<template>
  <form ref="formRef" @submit.prevent="handleSubmit">
    <v-text-field
      v-model="formData.name"
      label="Name"
      required
    />
    <v-text-field
      v-model="formData.email"
      label="Email"
      type="email"
      required
    />
    <v-text-field
      v-model="formData.phone"
      label="Phone"
    />

    <v-btn type="submit">
      Save
      <KeyboardShortcutHint shortcut="ctrl+s" />
    </v-btn>
    <v-btn @click="handleCancel">
      Cancel
      <KeyboardShortcutHint shortcut="esc" />
    </v-btn>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { useFormShortcuts } from '@/composables/useFormShortcuts'
import KeyboardShortcutHint from '@/components/KeyboardShortcutHint.vue'

const formRef = ref(null)
const formData = ref({
  name: '',
  email: '',
  phone: ''
})

const handleSubmit = () => {
  console.log('Form submitted:', formData.value)
  // Your submit logic
}

const handleCancel = () => {
  console.log('Form cancelled')
  // Your cancel logic
}

const handleReset = () => {
  formData.value = {
    name: '',
    email: '',
    phone: ''
  }
}

// Enable form shortcuts
useFormShortcuts(formRef, {
  onSave: handleSubmit,
  onCancel: handleCancel,
  onReset: handleReset
})
</script>
```

### Form with Custom Navigation

```vue
<script setup>
import { ref } from 'vue'
import { useFormShortcuts } from '@/composables/useFormShortcuts'

const formRef = ref(null)

const {
  focusNextField,
  focusPrevField,
  focusFirstInvalidField
} = useFormShortcuts(formRef, {
  onSave: handleSubmit,
  onCancel: handleCancel,
  // Custom field navigation
  onNextField: () => {
    console.log('Moving to next field')
    focusNextField()
  },
  onPrevField: () => {
    console.log('Moving to previous field')
    focusPrevField()
  }
})

// Programmatically navigate to first error after validation
const validateAndFocus = () => {
  // Your validation logic
  const isValid = validate()
  if (!isValid) {
    focusFirstInvalidField()
  }
}
</script>
```

## Custom Shortcuts

### Registering Custom Shortcuts

```vue
<script setup>
import { onMounted } from 'vue'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'

const { registerShortcut, unregisterShortcut } = useKeyboardShortcuts({
  registerGlobal: false // Don't register global shortcuts again
})

onMounted(() => {
  // Register a custom shortcut
  const unregister = registerShortcut('export-data', {
    key: 'e',
    ctrl: true,
    shift: true,
    description: 'Export data to CSV',
    category: 'Custom',
    handler: () => {
      console.log('Exporting data...')
      exportToCsv()
    }
  })

  // Unregister on component unmount (optional, automatic cleanup)
  onUnmounted(() => {
    unregister()
  })
})

const exportToCsv = () => {
  // Your export logic
}
</script>
```

### Context-Aware Shortcuts

```vue
<script setup>
import { ref } from 'vue'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'

const isEditing = ref(false)
const { registerShortcut } = useKeyboardShortcuts({ registerGlobal: false })

// Only work when editing
registerShortcut('save-draft', {
  key: 's',
  ctrl: true,
  shift: true,
  description: 'Save as draft',
  category: 'Custom',
  context: () => isEditing.value, // Only active when editing
  handler: () => {
    saveDraft()
  }
})
</script>
```

## Visual Hints

### Using the KeyboardShortcutHint Component

```vue
<template>
  <!-- In buttons -->
  <v-btn @click="save">
    Save
    <KeyboardShortcutHint shortcut="ctrl+s" />
  </v-btn>

  <!-- In menu items -->
  <v-list-item @click="newEntry">
    <v-list-item-title>
      New Entry
      <KeyboardShortcutHint shortcut="ctrl+n" />
    </v-list-item-title>
  </v-list-item>

  <!-- In tooltips -->
  <v-tooltip bottom>
    <template v-slot:activator="{ props }">
      <v-btn icon v-bind="props">
        <v-icon>mdi-refresh</v-icon>
      </v-btn>
    </template>
    <span>
      Refresh
      <KeyboardShortcutHint shortcut="ctrl+r" />
    </span>
  </v-tooltip>

  <!-- Complex shortcuts -->
  <v-btn>
    Reset Form
    <KeyboardShortcutHint shortcut="ctrl+shift+r" />
  </v-btn>

  <!-- Navigation shortcuts -->
  <v-btn>
    Next Field
    <KeyboardShortcutHint shortcut="ctrl+down" />
  </v-btn>
</template>

<script setup>
import KeyboardShortcutHint from '@/components/KeyboardShortcutHint.vue'
</script>
```

### Custom Styling

```vue
<template>
  <v-btn class="with-shortcut-hint">
    Save
    <KeyboardShortcutHint shortcut="ctrl+s" />
  </v-btn>
</template>

<style scoped>
.with-shortcut-hint {
  position: relative;
}

.with-shortcut-hint .keyboard-shortcut-hint {
  margin-left: auto;
  padding-left: 16px;
}
</style>
```

## Best Practices

### 1. Always Provide Context

```javascript
// ✅ Good - Context-aware
registerShortcut('delete-item', {
  key: 'delete',
  context: () => hasSelection.value && !isEditing.value,
  handler: deleteSelected
})

// ❌ Bad - No context check
registerShortcut('delete-item', {
  key: 'delete',
  handler: deleteSelected // Might delete when user doesn't expect it
})
```

### 2. Prevent Default Behavior When Needed

```javascript
// ✅ Good - Prevent browser's save dialog
registerShortcut('save', {
  key: 's',
  ctrl: true,
  preventDefault: true, // Prevents Ctrl+S browser save
  handler: saveData
})
```

### 3. Clean Up Shortcuts

```javascript
// ✅ Good - Clean up on unmount
onMounted(() => {
  const unregister = registerShortcut('custom', {
    key: 'x',
    ctrl: true,
    handler: customAction
  })

  onUnmounted(() => {
    unregister()
  })
})
```

### 4. Use Appropriate Categories

```javascript
// ✅ Good - Clear categorization
registerShortcut('export', {
  key: 'e',
  ctrl: true,
  description: 'Export to CSV',
  category: 'Data Management', // Clear category
  handler: exportData
})
```

### 5. Provide Clear Descriptions

```javascript
// ✅ Good - Descriptive
description: 'Export current view to CSV file'

// ❌ Bad - Vague
description: 'Export'
```

### 6. Test Cross-Platform

```javascript
// ✅ Good - Works on both Mac and Windows/Linux
registerShortcut('save', {
  key: 's',
  ctrl: true, // Automatically uses Cmd on Mac
  handler: save
})
```

### 7. Avoid Conflicts

```javascript
// ⚠️ Warning - Ctrl+N conflicts with browser "new window"
// Consider using Ctrl+Shift+N instead
registerShortcut('new-entry', {
  key: 'n',
  ctrl: true,
  shift: true, // Less likely to conflict
  handler: newEntry
})
```

### 8. Show Visual Hints

```vue
<!-- ✅ Good - User can see the shortcut -->
<v-btn @click="save">
  Save
  <KeyboardShortcutHint shortcut="ctrl+s" />
</v-btn>

<!-- ❌ Bad - User doesn't know about shortcut -->
<v-btn @click="save">
  Save
</v-btn>
```

## Complete Example: Production Entry Grid

```vue
<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <span>Production Entries</span>
      <v-spacer />
      <v-btn color="primary" @click="addEntry">
        <v-icon left>mdi-plus</v-icon>
        New Entry
        <KeyboardShortcutHint shortcut="ctrl+n" />
      </v-btn>
    </v-card-title>

    <v-card-text>
      <ag-grid-vue
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="rowData"
        @grid-ready="onGridReady"
        class="ag-theme-alpine"
        style="height: 600px"
      />
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { useGridShortcuts } from '@/composables/useGridShortcuts'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import KeyboardShortcutHint from '@/components/KeyboardShortcutHint.vue'

const gridRef = ref(null)
const gridApi = ref(null)

const columnDefs = ref([
  { field: 'date', editable: true },
  { field: 'product', editable: true },
  { field: 'quantity', editable: true },
  { field: 'shift', editable: true }
])

const rowData = ref([])

const onGridReady = (params) => {
  gridApi.value = params.api
  loadData()
}

// Enable grid shortcuts
useGridShortcuts(gridApi)

// Register custom shortcuts
const { registerShortcut } = useKeyboardShortcuts({ registerGlobal: false })

const addEntry = () => {
  console.log('Adding new entry')
  // Your logic
}

const saveData = () => {
  console.log('Saving data')
  // Your logic
}

const handleNew = () => {
  addEntry()
}

const handleSave = () => {
  saveData()
}

onMounted(() => {
  // Listen for global shortcuts
  window.addEventListener('keyboard-shortcut:new', handleNew)
  window.addEventListener('keyboard-shortcut:save', handleSave)

  // Register custom export shortcut
  registerShortcut('export-production', {
    key: 'e',
    ctrl: true,
    shift: true,
    description: 'Export production data',
    category: 'Production',
    handler: () => {
      console.log('Exporting production data')
      // Your export logic
    }
  })
})

onUnmounted(() => {
  window.removeEventListener('keyboard-shortcut:new', handleNew)
  window.removeEventListener('keyboard-shortcut:save', handleSave)
})
</script>
```

## Troubleshooting

### Shortcuts Not Working

1. Check if shortcuts are enabled (keyboard icon should be blue in app bar)
2. Ensure you're not in an input field (unless shortcut allows it)
3. Check browser console for errors
4. Verify context function returns true

### Conflicts with Browser Shortcuts

Some browser shortcuts may conflict. Consider:
- Adding `Shift` modifier: `Ctrl+Shift+N` instead of `Ctrl+N`
- Using alternative keys
- Documenting known conflicts

### Shortcuts Not Showing in Help Modal

Make sure you:
1. Register shortcuts with proper category
2. Provide description
3. Use `useKeyboardShortcuts()` composable

## Additional Resources

- [Vue 3 Composition API](https://vuejs.org/guide/extras/composition-api-faq.html)
- [AG Grid Vue Documentation](https://www.ag-grid.com/vue-data-grid/)
- [Keyboard Event Reference](https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent)
- [Accessibility Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
