<template>
  <v-toolbar density="compact" class="workflow-toolbar">
    <v-toolbar-title class="text-body-1">
      <v-icon class="mr-2">mdi-sitemap</v-icon>
      {{ $t('workflowDesigner.title') }}
      <span v-if="clientName" class="text-grey ml-2">
        - {{ clientName }}
      </span>
    </v-toolbar-title>

    <v-spacer />

    <!-- Template selector -->
    <v-menu v-if="templates.length > 0">
      <template v-slot:activator="{ props }">
        <v-btn
          v-bind="props"
          variant="text"
          size="small"
          :disabled="isLoading"
        >
          <v-icon start>mdi-file-document-outline</v-icon>
          {{ $t('workflowDesigner.toolbar.templates') }}
          <v-icon end>mdi-chevron-down</v-icon>
        </v-btn>
      </template>
      <v-list density="compact">
        <v-list-subheader>{{ $t('workflowDesigner.toolbar.applyTemplate') }}</v-list-subheader>
        <v-list-item
          v-for="template in templates"
          :key="template.id"
          @click="confirmApplyTemplate(template)"
        >
          <v-list-item-title>{{ template.name }}</v-list-item-title>
          <v-list-item-subtitle>{{ template.description }}</v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-menu>

    <v-divider vertical class="mx-2" />

    <!-- Add Status -->
    <v-btn
      variant="text"
      size="small"
      color="primary"
      @click="showAddStatusDialog = true"
      :disabled="isLoading"
    >
      <v-icon start>mdi-plus-circle</v-icon>
      {{ $t('workflowDesigner.toolbar.addStatus') }}
    </v-btn>

    <v-divider vertical class="mx-2" />

    <!-- Undo/Redo -->
    <v-btn
      icon
      size="small"
      variant="text"
      :disabled="!canUndo"
      @click="undo"
    >
      <v-icon>mdi-undo</v-icon>
      <v-tooltip activator="parent" location="bottom">
        {{ $t('workflowDesigner.toolbar.undo') }} (Ctrl+Z)
      </v-tooltip>
    </v-btn>

    <v-btn
      icon
      size="small"
      variant="text"
      :disabled="!canRedo"
      @click="redo"
    >
      <v-icon>mdi-redo</v-icon>
      <v-tooltip activator="parent" location="bottom">
        {{ $t('workflowDesigner.toolbar.redo') }} (Ctrl+Y)
      </v-tooltip>
    </v-btn>

    <v-divider vertical class="mx-2" />

    <!-- Mermaid toggle -->
    <v-btn
      :variant="showMermaidPanel ? 'tonal' : 'text'"
      size="small"
      @click="toggleMermaidPanel"
    >
      <v-icon start>mdi-code-braces</v-icon>
      {{ $t('workflowDesigner.toolbar.mermaid') }}
    </v-btn>

    <v-divider vertical class="mx-2" />

    <!-- Validation status -->
    <v-chip
      v-if="hasErrors"
      color="error"
      size="small"
      variant="tonal"
      class="mr-2"
    >
      <v-icon start size="small">mdi-alert-circle</v-icon>
      {{ validationErrors.length }} {{ $t('workflowDesigner.toolbar.errors') }}
    </v-chip>
    <v-chip
      v-else-if="hasWarnings"
      color="warning"
      size="small"
      variant="tonal"
      class="mr-2"
    >
      <v-icon start size="small">mdi-alert</v-icon>
      {{ validationWarnings.length }} {{ $t('workflowDesigner.toolbar.warnings') }}
    </v-chip>
    <v-chip
      v-else-if="statusCount > 0"
      color="success"
      size="small"
      variant="tonal"
      class="mr-2"
    >
      <v-icon start size="small">mdi-check-circle</v-icon>
      {{ $t('workflowDesigner.toolbar.valid') }}
    </v-chip>

    <v-divider vertical class="mx-2" />

    <!-- Save button -->
    <v-btn
      color="primary"
      size="small"
      :loading="isSaving"
      :disabled="!isDirty || hasErrors || isLoading"
      @click="handleSave"
    >
      <v-icon start>mdi-content-save</v-icon>
      {{ $t('common.save') }}
    </v-btn>
  </v-toolbar>

  <!-- Add Status Dialog -->
  <v-dialog v-model="showAddStatusDialog" max-width="400">
    <v-card>
      <v-card-title>{{ $t('workflowDesigner.dialog.addStatus.title') }}</v-card-title>
      <v-card-text>
        <v-text-field
          v-model="newStatusName"
          :label="$t('workflowDesigner.dialog.addStatus.name')"
          :hint="$t('workflowDesigner.dialog.addStatus.hint')"
          :rules="[statusNameRule]"
          @keyup.enter="addStatus"
          autofocus
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showAddStatusDialog = false">
          {{ $t('common.cancel') }}
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :disabled="!isValidStatusName"
          @click="addStatus"
        >
          {{ $t('common.add') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Template Confirm Dialog -->
  <v-dialog v-model="showTemplateConfirmDialog" max-width="400">
    <v-card>
      <v-card-title>{{ $t('workflowDesigner.dialog.applyTemplate.title') }}</v-card-title>
      <v-card-text>
        <v-alert type="warning" variant="tonal" class="mb-4">
          {{ $t('workflowDesigner.dialog.applyTemplate.warning') }}
        </v-alert>
        <p>
          {{ $t('workflowDesigner.dialog.applyTemplate.confirm', { template: selectedTemplate?.name }) }}
        </p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showTemplateConfirmDialog = false">
          {{ $t('common.cancel') }}
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="applySelectedTemplate"
        >
          {{ $t('common.apply') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkflowDesignerStore } from '@/stores/workflowDesignerStore'

const emit = defineEmits(['save'])

const store = useWorkflowDesignerStore()
const {
  clientName,
  isDirty,
  isLoading,
  isSaving,
  hasErrors,
  hasWarnings,
  validationErrors,
  validationWarnings,
  statusCount,
  canUndo,
  canRedo,
  showMermaidPanel,
  templates
} = storeToRefs(store)

// Dialog state
const showAddStatusDialog = ref(false)
const showTemplateConfirmDialog = ref(false)
const newStatusName = ref('')
const selectedTemplate = ref(null)

// Validation for status name
const statusNameRule = (v) => {
  if (!v) return 'Status name is required'
  if (!/^[A-Z][A-Z0-9_]*$/.test(v.toUpperCase().replace(/\s+/g, '_'))) {
    return 'Use uppercase letters, numbers, and underscores only'
  }
  return true
}

const isValidStatusName = computed(() => {
  const name = newStatusName.value.trim()
  return name && /^[A-Za-z][A-Za-z0-9_\s]*$/.test(name)
})

// Actions
const addStatus = () => {
  const name = newStatusName.value.trim().toUpperCase().replace(/\s+/g, '_')
  if (store.addStatus(name)) {
    showAddStatusDialog.value = false
    newStatusName.value = ''
  }
}

const confirmApplyTemplate = (template) => {
  selectedTemplate.value = template
  showTemplateConfirmDialog.value = true
}

const applySelectedTemplate = async () => {
  if (selectedTemplate.value) {
    await store.applyTemplate(selectedTemplate.value.id)
    showTemplateConfirmDialog.value = false
    selectedTemplate.value = null
  }
}

const handleSave = async () => {
  const result = await store.saveConfig()
  if (result.success) {
    emit('save', result)
  }
}

const undo = () => store.undo()
const redo = () => store.redo()
const toggleMermaidPanel = () => store.toggleMermaidPanel()

// Keyboard shortcuts
const handleKeydown = (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'z') {
    event.preventDefault()
    if (event.shiftKey) {
      redo()
    } else {
      undo()
    }
  }
  if ((event.ctrlKey || event.metaKey) && event.key === 'y') {
    event.preventDefault()
    redo()
  }
  if ((event.ctrlKey || event.metaKey) && event.key === 's') {
    event.preventDefault()
    if (isDirty.value && !hasErrors.value && !isLoading.value) {
      handleSave()
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  store.loadTemplates()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.workflow-toolbar {
  border-bottom: 1px solid #e0e0e0;
}
</style>
