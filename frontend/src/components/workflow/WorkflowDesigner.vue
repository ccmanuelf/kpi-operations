<template>
  <div class="workflow-designer">
    <!-- Loading overlay -->
    <v-overlay
      :model-value="isLoading"
      contained
      class="align-center justify-center"
    >
      <v-progress-circular indeterminate color="primary" size="64" />
    </v-overlay>

    <!-- Toolbar -->
    <WorkflowToolbar @save="handleSave" />

    <!-- Main content area -->
    <div class="designer-content">
      <!-- Canvas -->
      <div class="canvas-container">
        <WorkflowCanvas
          :show-minimap="showMinimap"
          @node-select="openSidebar"
          @edge-select="openSidebar"
          @deselect="closeSidebar"
        />
      </div>

      <!-- Sidebar -->
      <WorkflowSidebar
        v-model:is-open="sidebarOpen"
      />
    </div>

    <!-- Mermaid panel (bottom) -->
    <WorkflowMermaidPanel />

    <!-- Validation summary panel -->
    <v-expand-transition>
      <div v-if="showValidationPanel" class="validation-panel">
        <v-toolbar density="compact" color="grey-lighten-4">
          <v-toolbar-title class="text-body-2">
            {{ $t('workflowDesigner.validation.title') }}
          </v-toolbar-title>
          <v-spacer />
          <v-btn icon size="small" @click="showValidationPanel = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-toolbar>
        <v-list density="compact">
          <v-list-item
            v-for="(error, index) in validationErrors"
            :key="'error-' + index"
            prepend-icon="mdi-alert-circle"
            color="error"
          >
            <v-list-item-title>{{ error.message }}</v-list-item-title>
            <v-list-item-subtitle v-if="error.details?.status">
              {{ $t('workflowDesigner.validation.affectedStatus') }}: {{ error.details.status }}
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item
            v-for="(warning, index) in validationWarnings"
            :key="'warning-' + index"
            prepend-icon="mdi-alert"
            color="warning"
          >
            <v-list-item-title>{{ warning.message }}</v-list-item-title>
            <v-list-item-subtitle v-if="warning.details?.status">
              {{ $t('workflowDesigner.validation.affectedStatus') }}: {{ warning.details.status }}
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </div>
    </v-expand-transition>

    <!-- Snackbar for notifications -->
    <v-snackbar
      v-model="showSnackbar"
      :color="snackbarColor"
      :timeout="3000"
    >
      {{ snackbarMessage }}
      <template v-slot:actions>
        <v-btn variant="text" @click="showSnackbar = false">
          {{ $t('common.close') }}
        </v-btn>
      </template>
    </v-snackbar>

    <!-- Unsaved changes dialog -->
    <v-dialog v-model="showUnsavedDialog" max-width="400" persistent>
      <v-card>
        <v-card-title>{{ $t('workflowDesigner.dialog.unsavedChanges.title') }}</v-card-title>
        <v-card-text>
          {{ $t('workflowDesigner.dialog.unsavedChanges.message') }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="discardAndLeave">
            {{ $t('workflowDesigner.dialog.unsavedChanges.discard') }}
          </v-btn>
          <v-btn color="primary" variant="flat" @click="saveAndLeave">
            {{ $t('workflowDesigner.dialog.unsavedChanges.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { useWorkflowDesignerStore } from '@/stores/workflowDesignerStore'
import WorkflowToolbar from './WorkflowToolbar.vue'
import WorkflowCanvas from './WorkflowCanvas.vue'
import WorkflowSidebar from './WorkflowSidebar.vue'
import WorkflowMermaidPanel from './WorkflowMermaidPanel.vue'

const props = defineProps({
  clientId: {
    type: [String, Number],
    required: true
  },
  clientName: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['saved', 'error'])

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useWorkflowDesignerStore()

const {
  isLoading,
  isDirty,
  error,
  hasErrors,
  validationErrors,
  validationWarnings
} = storeToRefs(store)

// Local UI state
const sidebarOpen = ref(false)
const showMinimap = ref(true)
const showValidationPanel = ref(false)
const showSnackbar = ref(false)
const snackbarMessage = ref('')
const snackbarColor = ref('success')
const showUnsavedDialog = ref(false)
const pendingNavigation = ref(null)

// Initialize on mount
onMounted(async () => {
  await store.loadConfig(props.clientId, props.clientName)

  // Show validation panel if there are issues
  if (hasErrors.value || validationWarnings.value.length > 0) {
    showValidationPanel.value = true
  }
})

// Cleanup on unmount
onBeforeUnmount(() => {
  store.reset()
})

// Watch for error changes
watch(error, (newError) => {
  if (newError) {
    showNotification(newError, 'error')
  }
})

// Navigation guard for unsaved changes
onBeforeRouteLeave((to, from, next) => {
  if (isDirty.value) {
    pendingNavigation.value = next
    showUnsavedDialog.value = true
    return false
  }
  next()
})

// Also handle browser navigation
onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

const handleBeforeUnload = (e) => {
  if (isDirty.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

// Event handlers
const openSidebar = () => {
  sidebarOpen.value = true
}

const closeSidebar = () => {
  // Keep sidebar open if something is selected
  // sidebarOpen.value = false
}

const handleSave = async () => {
  const result = await store.saveConfig()
  if (result.success) {
    showNotification(t('success.saved'), 'success')
    emit('saved')
  } else {
    showNotification(result.error, 'error')
    emit('error', result.error)
  }
}

const showNotification = (message, color = 'success') => {
  snackbarMessage.value = message
  snackbarColor.value = color
  showSnackbar.value = true
}

const discardAndLeave = () => {
  showUnsavedDialog.value = false
  store.reset()
  if (pendingNavigation.value) {
    pendingNavigation.value()
    pendingNavigation.value = null
  }
}

const saveAndLeave = async () => {
  const result = await store.saveConfig()
  showUnsavedDialog.value = false

  if (result.success && pendingNavigation.value) {
    pendingNavigation.value()
    pendingNavigation.value = null
  } else if (!result.success) {
    showNotification(result.error, 'error')
  }
}

// Expose for parent components
defineExpose({
  save: handleSave,
  isDirty: computed(() => isDirty.value)
})
</script>

<style scoped>
.workflow-designer {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 600px;
  background: #f5f5f5;
  position: relative;
}

.designer-content {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.canvas-container {
  flex: 1;
  padding: 16px;
  overflow: hidden;
}

.validation-panel {
  border-top: 1px solid #e0e0e0;
  max-height: 200px;
  overflow: auto;
  background: white;
}
</style>
