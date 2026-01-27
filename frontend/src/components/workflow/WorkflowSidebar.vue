<template>
  <v-navigation-drawer
    :model-value="isOpen"
    location="right"
    width="320"
    temporary
    @update:model-value="$emit('update:isOpen', $event)"
  >
    <v-toolbar density="compact" color="grey-lighten-4">
      <v-toolbar-title class="text-body-1">
        {{ sidebarTitle }}
      </v-toolbar-title>
      <v-btn icon size="small" @click="$emit('update:isOpen', false)">
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </v-toolbar>

    <v-divider />

    <!-- No selection state -->
    <div v-if="!selectedElement" class="pa-4 text-center text-grey">
      <v-icon size="48" color="grey-lighten-2">mdi-cursor-pointer</v-icon>
      <p class="mt-4">{{ $t('workflowDesigner.sidebar.noSelection') }}</p>
    </div>

    <!-- Node properties -->
    <div v-else-if="selectedElement?.type === 'node'" class="pa-4">
      <v-list density="compact">
        <v-list-item>
          <template v-slot:prepend>
            <v-icon :color="nodeStyle.borderColor">{{ nodeIcon }}</v-icon>
          </template>
          <v-list-item-title class="font-weight-bold">
            {{ selectedNode.data.label }}
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ statusTypeLabel }}
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>

      <v-divider class="my-4" />

      <!-- Status type indicator -->
      <div class="mb-4">
        <div class="text-caption text-grey mb-2">{{ $t('workflowDesigner.sidebar.statusType') }}</div>
        <v-chip
          :color="nodeStyle.borderColor"
          variant="tonal"
          size="small"
        >
          <v-icon start size="small">{{ nodeIcon }}</v-icon>
          {{ statusTypeLabel }}
        </v-chip>
      </div>

      <!-- Incoming transitions -->
      <div class="mb-4">
        <div class="text-caption text-grey mb-2">
          {{ $t('workflowDesigner.sidebar.incomingTransitions') }}
          <v-chip size="x-small" class="ml-2">{{ incomingTransitions.length }}</v-chip>
        </div>
        <v-chip
          v-for="source in incomingTransitions"
          :key="source"
          size="small"
          variant="outlined"
          class="mr-1 mb-1"
        >
          {{ source }} →
        </v-chip>
        <div v-if="incomingTransitions.length === 0" class="text-body-2 text-grey">
          {{ $t('workflowDesigner.sidebar.noIncoming') }}
        </div>
      </div>

      <!-- Outgoing transitions -->
      <div class="mb-4">
        <div class="text-caption text-grey mb-2">
          {{ $t('workflowDesigner.sidebar.outgoingTransitions') }}
          <v-chip size="x-small" class="ml-2">{{ outgoingTransitions.length }}</v-chip>
        </div>
        <v-chip
          v-for="target in outgoingTransitions"
          :key="target"
          size="small"
          variant="outlined"
          class="mr-1 mb-1"
        >
          → {{ target }}
        </v-chip>
        <div v-if="outgoingTransitions.length === 0" class="text-body-2 text-grey">
          {{ $t('workflowDesigner.sidebar.noOutgoing') }}
        </div>
      </div>

      <v-divider class="my-4" />

      <!-- Delete button -->
      <v-btn
        color="error"
        variant="outlined"
        block
        :disabled="!canDeleteNode"
        @click="confirmDeleteNode"
      >
        <v-icon start>mdi-delete</v-icon>
        {{ $t('workflowDesigner.sidebar.deleteStatus') }}
      </v-btn>
      <div v-if="!canDeleteNode" class="text-caption text-error mt-2">
        {{ $t('workflowDesigner.sidebar.cannotDeleteReceived') }}
      </div>
    </div>

    <!-- Edge properties -->
    <div v-else-if="selectedElement?.type === 'edge'" class="pa-4">
      <v-list density="compact">
        <v-list-item>
          <template v-slot:prepend>
            <v-icon>mdi-arrow-right</v-icon>
          </template>
          <v-list-item-title class="font-weight-bold">
            {{ selectedEdge.source }} → {{ selectedEdge.target }}
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ $t('workflowDesigner.sidebar.transition') }}
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>

      <v-divider class="my-4" />

      <!-- Transition info -->
      <div class="mb-4">
        <div class="text-caption text-grey mb-2">{{ $t('workflowDesigner.sidebar.from') }}</div>
        <v-chip variant="tonal" color="primary">{{ selectedEdge.source }}</v-chip>
      </div>

      <div class="mb-4">
        <div class="text-caption text-grey mb-2">{{ $t('workflowDesigner.sidebar.to') }}</div>
        <v-chip variant="tonal" color="primary">{{ selectedEdge.target }}</v-chip>
      </div>

      <v-divider class="my-4" />

      <!-- Delete button -->
      <v-btn
        color="error"
        variant="outlined"
        block
        @click="confirmDeleteEdge"
      >
        <v-icon start>mdi-delete</v-icon>
        {{ $t('workflowDesigner.sidebar.deleteTransition') }}
      </v-btn>
    </div>

    <!-- Validation issues for selected element -->
    <div v-if="selectedElementIssues.length > 0" class="pa-4">
      <v-divider class="mb-4" />
      <div class="text-caption text-grey mb-2">{{ $t('workflowDesigner.sidebar.issues') }}</div>
      <v-alert
        v-for="(issue, index) in selectedElementIssues"
        :key="index"
        :type="issue.severity"
        variant="tonal"
        density="compact"
        class="mb-2"
      >
        {{ issue.message }}
      </v-alert>
    </div>

    <!-- Delete confirmation dialog -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>{{ $t('common.confirmDelete') }}</v-card-title>
        <v-card-text>
          {{ deleteDialogMessage }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showDeleteDialog = false">
            {{ $t('common.cancel') }}
          </v-btn>
          <v-btn
            color="error"
            variant="flat"
            @click="executeDelete"
          >
            {{ $t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-navigation-drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { useWorkflowDesignerStore } from '@/stores/workflowDesignerStore'
import { STATUS_TYPES, getStatusTypeStyle } from '@/utils/workflow/statusClassifier'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:isOpen'])

const { t } = useI18n()
const store = useWorkflowDesignerStore()
const {
  selectedNode,
  selectedEdge,
  selectedElement,
  workflowConfig,
  validationErrors,
  validationWarnings
} = storeToRefs(store)

const showDeleteDialog = ref(false)
const deleteType = ref(null) // 'node' or 'edge'

const sidebarTitle = computed(() => {
  if (!selectedElement.value) {
    return t('workflowDesigner.sidebar.properties')
  }
  if (selectedElement.value.type === 'node') {
    return t('workflowDesigner.sidebar.statusProperties')
  }
  return t('workflowDesigner.sidebar.transitionProperties')
})

// Node-related computed properties
const nodeStyle = computed(() => {
  if (!selectedNode.value) return {}
  const statusType = selectedNode.value.data?.statusType || STATUS_TYPES.NORMAL
  return getStatusTypeStyle(statusType)
})

const nodeIcon = computed(() => {
  if (!selectedNode.value) return 'mdi-circle'
  const statusType = selectedNode.value.data?.statusType
  const icons = {
    [STATUS_TYPES.START]: 'mdi-play-circle',
    [STATUS_TYPES.NORMAL]: 'mdi-checkbox-blank-circle',
    [STATUS_TYPES.TERMINAL]: 'mdi-stop-circle',
    [STATUS_TYPES.HOLD]: 'mdi-pause-circle',
    [STATUS_TYPES.OPTIONAL]: 'mdi-skip-next-circle'
  }
  return icons[statusType] || icons[STATUS_TYPES.NORMAL]
})

const statusTypeLabel = computed(() => {
  if (!selectedNode.value) return ''
  const statusType = selectedNode.value.data?.statusType
  const labels = {
    [STATUS_TYPES.START]: t('workflowDesigner.statusTypes.start'),
    [STATUS_TYPES.NORMAL]: t('workflowDesigner.statusTypes.normal'),
    [STATUS_TYPES.TERMINAL]: t('workflowDesigner.statusTypes.terminal'),
    [STATUS_TYPES.HOLD]: t('workflowDesigner.statusTypes.hold'),
    [STATUS_TYPES.OPTIONAL]: t('workflowDesigner.statusTypes.optional')
  }
  return labels[statusType] || labels[STATUS_TYPES.NORMAL]
})

const incomingTransitions = computed(() => {
  if (!selectedNode.value || !workflowConfig.value.transitions) return []
  const nodeId = selectedNode.value.id
  return workflowConfig.value.transitions[nodeId] || []
})

const outgoingTransitions = computed(() => {
  if (!selectedNode.value || !workflowConfig.value.transitions) return []
  const nodeId = selectedNode.value.id
  const targets = []

  Object.entries(workflowConfig.value.transitions).forEach(([target, sources]) => {
    if (sources.includes(nodeId)) {
      targets.push(target)
    }
  })

  return targets
})

const canDeleteNode = computed(() => {
  if (!selectedNode.value) return false
  // Cannot delete RECEIVED
  return selectedNode.value.id !== 'RECEIVED'
})

const deleteDialogMessage = computed(() => {
  if (deleteType.value === 'node' && selectedNode.value) {
    return t('workflowDesigner.dialog.deleteStatus.confirm', { status: selectedNode.value.id })
  }
  if (deleteType.value === 'edge' && selectedEdge.value) {
    return t('workflowDesigner.dialog.deleteTransition.confirm', {
      from: selectedEdge.value.source,
      to: selectedEdge.value.target
    })
  }
  return ''
})

const selectedElementIssues = computed(() => {
  if (!selectedElement.value) return []

  const issues = []
  const id = selectedElement.value.type === 'node'
    ? selectedNode.value?.id
    : selectedEdge.value?.id

  // Check errors
  validationErrors.value.forEach(error => {
    if (error.details?.status === id) {
      issues.push({ severity: 'error', message: error.message })
    }
  })

  // Check warnings
  validationWarnings.value.forEach(warning => {
    if (warning.details?.status === id) {
      issues.push({ severity: 'warning', message: warning.message })
    }
  })

  return issues
})

// Actions
const confirmDeleteNode = () => {
  deleteType.value = 'node'
  showDeleteDialog.value = true
}

const confirmDeleteEdge = () => {
  deleteType.value = 'edge'
  showDeleteDialog.value = true
}

const executeDelete = () => {
  if (deleteType.value === 'node' && selectedNode.value) {
    store.removeStatus(selectedNode.value.id)
  } else if (deleteType.value === 'edge' && selectedEdge.value) {
    store.removeTransition(selectedEdge.value.source, selectedEdge.value.target)
  }

  showDeleteDialog.value = false
  deleteType.value = null
  emit('update:isOpen', false)
}
</script>
