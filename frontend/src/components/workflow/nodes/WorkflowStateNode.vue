<template>
  <div
    class="workflow-state-node"
    :class="[statusTypeClass, { selected: selected }]"
    @click.stop="handleClick"
  >
    <v-tooltip location="top" :text="tooltipText">
      <template v-slot:activator="{ props: tooltipProps }">
        <div class="node-content" v-bind="tooltipProps">
          <v-icon
            size="16"
            class="node-icon"
            :color="iconColor"
          >
            {{ icon }}
          </v-icon>
          <span class="node-label">{{ data.label }}</span>
        </div>
      </template>
    </v-tooltip>

    <!-- Connection handles -->
    <Handle
      id="target"
      type="target"
      :position="Position.Top"
      :style="handleStyle"
    />
    <Handle
      id="source"
      type="source"
      :position="Position.Bottom"
      :style="handleStyle"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { STATUS_TYPES, getStatusTypeStyle } from '@/utils/workflow/statusClassifier'

const props = defineProps({
  id: {
    type: String,
    required: true
  },
  data: {
    type: Object,
    required: true
  },
  selected: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['click'])

const statusType = computed(() => props.data.statusType || STATUS_TYPES.NORMAL)

const statusTypeClass = computed(() => `status-type-${statusType.value}`)

const style = computed(() => getStatusTypeStyle(statusType.value))

const icon = computed(() => {
  const icons = {
    [STATUS_TYPES.START]: 'mdi-play-circle',
    [STATUS_TYPES.NORMAL]: 'mdi-checkbox-blank-circle',
    [STATUS_TYPES.TERMINAL]: 'mdi-stop-circle',
    [STATUS_TYPES.HOLD]: 'mdi-pause-circle',
    [STATUS_TYPES.OPTIONAL]: 'mdi-skip-next-circle'
  }
  return icons[statusType.value] || icons[STATUS_TYPES.NORMAL]
})

const iconColor = computed(() => style.value.borderColor)

const tooltipText = computed(() => {
  const typeLabels = {
    [STATUS_TYPES.START]: 'Entry Point',
    [STATUS_TYPES.NORMAL]: 'Standard Status',
    [STATUS_TYPES.TERMINAL]: 'Terminal Status',
    [STATUS_TYPES.HOLD]: 'Hold Status',
    [STATUS_TYPES.OPTIONAL]: 'Optional Status'
  }
  return `${props.data.label} (${typeLabels[statusType.value]})`
})

const handleStyle = computed(() => ({
  background: style.value.borderColor,
  width: '10px',
  height: '10px'
}))

const handleClick = () => {
  emit('click', { id: props.id, data: props.data })
}
</script>

<style scoped>
.workflow-state-node {
  padding: 10px 16px;
  border-radius: 8px;
  border-width: 2px;
  border-style: solid;
  min-width: 120px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.workflow-state-node:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
  transform: translateY(-1px);
}

.workflow-state-node.selected {
  box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.4);
}

.node-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.node-label {
  font-weight: 500;
  font-size: 13px;
  white-space: nowrap;
}

/* Status type styles */
.status-type-start {
  background-color: #d4edda;
  border-color: #28a745;
  color: #155724;
}

.status-type-normal {
  background-color: #cce5ff;
  border-color: #007bff;
  color: #004085;
}

.status-type-terminal {
  background-color: #f8d7da;
  border-color: #dc3545;
  color: #721c24;
  border-width: 3px;
}

.status-type-hold {
  background-color: #fff3cd;
  border-color: #ffc107;
  color: #856404;
}

.status-type-optional {
  background-color: #e2e3e5;
  border-color: #6c757d;
  color: #383d41;
  border-style: dashed;
}

/* Handle positioning */
:deep(.vue-flow__handle) {
  border: 2px solid #fff;
}

:deep(.vue-flow__handle-top) {
  top: -6px;
}

:deep(.vue-flow__handle-bottom) {
  bottom: -6px;
}
</style>
