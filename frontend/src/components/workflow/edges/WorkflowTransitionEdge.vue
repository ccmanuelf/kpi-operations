<template>
  <g>
    <BaseEdge
      :id="id"
      :path="path[0]"
      :marker-end="markerEnd"
      :style="edgeStyle"
    />
    <EdgeLabelRenderer>
      <div
        v-if="data?.label"
        :style="{
          position: 'absolute',
          transform: `translate(-50%, -50%) translate(${path[1]}px, ${path[2]}px)`,
          pointerEvents: 'all',
        }"
        class="edge-label"
      >
        {{ data.label }}
      </div>
    </EdgeLabelRenderer>
    <!-- Invisible wider path for easier clicking -->
    <path
      :d="path[0]"
      fill="none"
      stroke="transparent"
      stroke-width="20"
      @click.stop="handleClick"
      style="cursor: pointer;"
    />
  </g>
</template>

<script setup>
import { computed } from 'vue'
import { BaseEdge, EdgeLabelRenderer, getBezierPath } from '@vue-flow/core'

const props = defineProps({
  id: {
    type: String,
    required: true
  },
  sourceX: {
    type: Number,
    required: true
  },
  sourceY: {
    type: Number,
    required: true
  },
  targetX: {
    type: Number,
    required: true
  },
  targetY: {
    type: Number,
    required: true
  },
  sourcePosition: {
    type: String,
    default: 'bottom'
  },
  targetPosition: {
    type: String,
    default: 'top'
  },
  data: {
    type: Object,
    default: () => ({})
  },
  markerEnd: {
    type: String,
    default: ''
  },
  selected: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['click'])

const path = computed(() => getBezierPath({
  sourceX: props.sourceX,
  sourceY: props.sourceY,
  sourcePosition: props.sourcePosition,
  targetX: props.targetX,
  targetY: props.targetY,
  targetPosition: props.targetPosition,
  curvature: 0.25
}))

const edgeStyle = computed(() => ({
  stroke: props.selected ? '#1976d2' : '#6c757d',
  strokeWidth: props.selected ? 3 : 2,
  transition: 'stroke 0.2s, stroke-width 0.2s'
}))

const handleClick = () => {
  emit('click', { id: props.id, data: props.data })
}
</script>

<style scoped>
.edge-label {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 11px;
  color: #666;
}
</style>
