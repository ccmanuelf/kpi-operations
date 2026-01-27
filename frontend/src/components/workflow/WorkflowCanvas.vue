<template>
  <div class="workflow-canvas">
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      :node-types="nodeTypes"
      :edge-types="edgeTypes"
      :default-viewport="{ zoom: 1, x: 0, y: 0 }"
      :min-zoom="0.25"
      :max-zoom="2"
      :snap-to-grid="true"
      :snap-grid="[20, 20]"
      :connection-mode="ConnectionMode.Loose"
      :default-edge-options="defaultEdgeOptions"
      fit-view-on-init
      @node-click="handleNodeClick"
      @edge-click="handleEdgeClick"
      @pane-click="handlePaneClick"
      @connect="handleConnect"
      @node-drag-stop="handleNodeDragStop"
    >
      <Background :pattern-color="'#aaa'" :gap="20" />
      <Controls position="bottom-left" />
      <MiniMap
        v-if="showMinimap"
        position="bottom-right"
        :node-color="getMinimapNodeColor"
        :pannable="true"
        :zoomable="true"
      />

      <!-- Connection line while dragging -->
      <template #connection-line="{ sourceX, sourceY, targetX, targetY }">
        <g>
          <path
            :d="`M ${sourceX} ${sourceY} C ${sourceX} ${(sourceY + targetY) / 2}, ${targetX} ${(sourceY + targetY) / 2}, ${targetX} ${targetY}`"
            stroke="#007bff"
            stroke-width="2"
            fill="none"
            stroke-dasharray="5,5"
          />
          <circle :cx="targetX" :cy="targetY" r="5" fill="#007bff" />
        </g>
      </template>
    </VueFlow>

    <!-- Empty state -->
    <div v-if="nodes.length === 0" class="empty-state">
      <v-icon size="64" color="grey-lighten-1">mdi-sitemap</v-icon>
      <p class="text-h6 text-grey-darken-1 mt-4">{{ $t('workflowDesigner.canvas.emptyState') }}</p>
      <p class="text-body-2 text-grey">{{ $t('workflowDesigner.canvas.emptyStateHint') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, markRaw, watch } from 'vue'
import { VueFlow, ConnectionMode, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { storeToRefs } from 'pinia'
import { useWorkflowDesignerStore } from '@/stores/workflowDesignerStore'
import WorkflowStateNode from './nodes/WorkflowStateNode.vue'
import WorkflowTransitionEdge from './edges/WorkflowTransitionEdge.vue'

// Vue Flow CSS must be imported
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

const props = defineProps({
  showMinimap: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['node-select', 'edge-select', 'deselect'])

const store = useWorkflowDesignerStore()
const { nodes, edges, selectedNode, selectedEdge } = storeToRefs(store)

// Register custom node and edge types
const nodeTypes = {
  workflowState: markRaw(WorkflowStateNode)
}

const edgeTypes = {
  workflowTransition: markRaw(WorkflowTransitionEdge)
}

// Default edge options
const defaultEdgeOptions = {
  type: 'workflowTransition',
  animated: false,
  markerEnd: {
    type: 'arrowclosed',
    color: '#6c757d'
  }
}

// Event handlers
const handleNodeClick = (event) => {
  const node = event.node
  store.selectNode(node)
  emit('node-select', node)
}

const handleEdgeClick = (event) => {
  const edge = event.edge
  store.selectEdge(edge)
  emit('edge-select', edge)
}

const handlePaneClick = () => {
  store.clearSelection()
  emit('deselect')
}

const handleConnect = (connection) => {
  // When user drags from one node to another
  if (connection.source && connection.target) {
    store.addTransition(connection.source, connection.target)
  }
}

const handleNodeDragStop = (event) => {
  const node = event.node
  store.updateNodePosition(node.id, node.position)
}

// Minimap node coloring
const getMinimapNodeColor = (node) => {
  const statusType = node.data?.statusType
  const colors = {
    start: '#28a745',
    normal: '#007bff',
    terminal: '#dc3545',
    hold: '#ffc107',
    optional: '#6c757d'
  }
  return colors[statusType] || colors.normal
}

// Sync selection state with Vue Flow
const { setNodes, setEdges, getNodes, getEdges } = useVueFlow()

watch(selectedNode, (node) => {
  if (node) {
    // Update selected state in nodes
    const updatedNodes = getNodes.value.map(n => ({
      ...n,
      selected: n.id === node.id
    }))
    setNodes(updatedNodes)

    // Deselect edges
    const updatedEdges = getEdges.value.map(e => ({
      ...e,
      selected: false
    }))
    setEdges(updatedEdges)
  }
})

watch(selectedEdge, (edge) => {
  if (edge) {
    // Update selected state in edges
    const updatedEdges = getEdges.value.map(e => ({
      ...e,
      selected: e.id === edge.id
    }))
    setEdges(updatedEdges)

    // Deselect nodes
    const updatedNodes = getNodes.value.map(n => ({
      ...n,
      selected: false
    }))
    setNodes(updatedNodes)
  }
})
</script>

<style scoped>
.workflow-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 500px;
  background: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.workflow-canvas :deep(.vue-flow) {
  width: 100%;
  height: 100%;
}

.empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}

/* Custom controls styling */
.workflow-canvas :deep(.vue-flow__controls) {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  border-radius: 8px;
  overflow: hidden;
}

.workflow-canvas :deep(.vue-flow__controls-button) {
  background: white;
  border: none;
  color: #333;
}

.workflow-canvas :deep(.vue-flow__controls-button:hover) {
  background: #f5f5f5;
}

/* Minimap styling */
.workflow-canvas :deep(.vue-flow__minimap) {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
</style>
