<template>
  <v-expand-transition>
    <div v-show="showMermaidPanel" class="mermaid-panel">
      <v-toolbar density="compact" color="grey-darken-3" dark>
        <v-toolbar-title class="text-body-2">
          <v-icon class="mr-2" size="small">mdi-code-braces</v-icon>
          {{ $t('workflowDesigner.mermaid.title') }}
        </v-toolbar-title>

        <v-spacer />

        <!-- Edit mode toggle -->
        <v-btn
          :variant="mermaidEditMode ? 'tonal' : 'text'"
          size="small"
          @click="toggleEditMode"
        >
          <v-icon start>{{ mermaidEditMode ? 'mdi-eye' : 'mdi-pencil' }}</v-icon>
          {{ mermaidEditMode ? $t('workflowDesigner.mermaid.preview') : $t('workflowDesigner.mermaid.edit') }}
        </v-btn>

        <!-- Apply changes (only in edit mode) -->
        <v-btn
          v-if="mermaidEditMode && hasChanges"
          color="primary"
          size="small"
          class="ml-2"
          @click="applyChanges"
        >
          <v-icon start>mdi-check</v-icon>
          {{ $t('workflowDesigner.mermaid.apply') }}
        </v-btn>

        <!-- Copy button -->
        <v-btn
          icon
          size="small"
          variant="text"
          class="ml-2"
          @click="copyToClipboard"
        >
          <v-icon>mdi-content-copy</v-icon>
          <v-tooltip activator="parent" location="top">
            {{ $t('workflowDesigner.mermaid.copy') }}
          </v-tooltip>
        </v-btn>

        <!-- Close button -->
        <v-btn
          icon
          size="small"
          variant="text"
          @click="toggleMermaidPanel"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <div class="mermaid-content">
        <!-- Edit mode: textarea -->
        <div v-if="mermaidEditMode" class="code-editor">
          <v-textarea
            v-model="editableCode"
            :placeholder="$t('workflowDesigner.mermaid.placeholder')"
            variant="solo-filled"
            bg-color="grey-darken-4"
            hide-details
            auto-grow
            rows="10"
            class="mermaid-textarea"
            @input="markCodeChanged"
          />
          <div v-if="syntaxErrors.length > 0" class="syntax-errors">
            <v-alert
              v-for="(error, index) in syntaxErrors"
              :key="index"
              type="error"
              variant="tonal"
              density="compact"
              class="mb-1"
            >
              {{ error }}
            </v-alert>
          </div>
        </div>

        <!-- Preview mode: rendered code -->
        <div v-else class="code-preview">
          <pre class="mermaid-code"><code>{{ mermaidCode }}</code></pre>
        </div>

        <!-- Stats footer -->
        <div class="mermaid-footer">
          <v-chip size="x-small" class="mr-2">
            <v-icon start size="small">mdi-circle</v-icon>
            {{ statusCount }} {{ $t('workflowDesigner.mermaid.statuses') }}
          </v-chip>
          <v-chip size="x-small">
            <v-icon start size="small">mdi-arrow-right</v-icon>
            {{ transitionCount }} {{ $t('workflowDesigner.mermaid.transitions') }}
          </v-chip>
        </div>
      </div>
    </div>
  </v-expand-transition>

  <!-- Snackbar for copy feedback -->
  <v-snackbar
    v-model="showCopySnackbar"
    :timeout="2000"
    color="success"
  >
    {{ $t('workflowDesigner.mermaid.copied') }}
  </v-snackbar>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkflowDesignerStore } from '@/stores/workflowDesignerStore'
import { validateMermaidSyntax } from '@/utils/workflow/mermaidParser'

const store = useWorkflowDesignerStore()
const {
  showMermaidPanel,
  mermaidCode,
  mermaidEditMode,
  statusCount,
  transitionCount
} = storeToRefs(store)

const editableCode = ref('')
const hasChanges = ref(false)
const syntaxErrors = ref([])
const showCopySnackbar = ref(false)

// Sync editable code with store when entering edit mode
watch(mermaidEditMode, (isEditing) => {
  if (isEditing) {
    editableCode.value = mermaidCode.value
    hasChanges.value = false
    syntaxErrors.value = []
  }
})

// Also sync when mermaid code updates externally
watch(mermaidCode, (newCode) => {
  if (!mermaidEditMode.value) {
    editableCode.value = newCode
  }
})

const toggleMermaidPanel = () => {
  store.toggleMermaidPanel()
}

const toggleEditMode = () => {
  if (mermaidEditMode.value && hasChanges.value) {
    // If leaving edit mode with unsaved changes, discard them
    editableCode.value = mermaidCode.value
    hasChanges.value = false
  }
  store.mermaidEditMode = !mermaidEditMode.value
}

const markCodeChanged = () => {
  hasChanges.value = editableCode.value !== mermaidCode.value

  // Validate syntax in real-time
  if (hasChanges.value) {
    const validation = validateMermaidSyntax(editableCode.value)
    syntaxErrors.value = validation.errors
  } else {
    syntaxErrors.value = []
  }
}

const applyChanges = () => {
  if (syntaxErrors.value.length > 0) {
    return
  }

  const result = store.applyMermaidCode(editableCode.value)
  if (result.success) {
    hasChanges.value = false
    store.mermaidEditMode = false
  } else {
    syntaxErrors.value = [result.error]
  }
}

const copyToClipboard = async () => {
  try {
    await navigator.clipboard.writeText(mermaidCode.value)
    showCopySnackbar.value = true
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}
</script>

<style scoped>
.mermaid-panel {
  border-top: 1px solid #424242;
  background: #1e1e1e;
  max-height: 400px;
  display: flex;
  flex-direction: column;
}

.mermaid-content {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.code-editor {
  flex: 1;
  padding: 8px;
}

.mermaid-textarea :deep(textarea) {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace !important;
  font-size: 12px !important;
  line-height: 1.5 !important;
  color: #d4d4d4 !important;
}

.syntax-errors {
  padding: 8px 0;
}

.code-preview {
  flex: 1;
  overflow: auto;
  padding: 12px;
}

.mermaid-code {
  margin: 0;
  padding: 0;
  background: transparent;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.mermaid-footer {
  padding: 8px 12px;
  background: #2d2d2d;
  border-top: 1px solid #424242;
}
</style>
