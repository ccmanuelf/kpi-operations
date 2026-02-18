/**
 * Workflow Designer Store
 * Manages state for the visual workflow editor
 * Provides undo/redo, validation, and Mermaid sync functionality
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { getWorkflowConfig, updateWorkflowConfig, getWorkflowTemplates, applyWorkflowTemplate } from '@/services/api/workflow'
import { configToVueFlow, vueFlowToConfig, configToMermaid, mermaidToConfig } from '@/utils/workflow/mermaidConverter'
import { validateWorkflow } from '@/utils/workflow/workflowValidator'
import { useNotificationStore } from './notificationStore'

// Maximum history stack size
const MAX_HISTORY_SIZE = 50

export const useWorkflowDesignerStore = defineStore('workflowDesigner', () => {
  // ============================================
  // State
  // ============================================
  const clientId = ref(null)
  const clientName = ref('')
  const workflowConfig = ref({
    statuses: [],
    transitions: {},
    closure_trigger: 'at_shipment'
  })

  // Vue Flow state
  const nodes = ref([])
  const edges = ref([])
  const selectedNode = ref(null)
  const selectedEdge = ref(null)

  // Validation state
  const validationErrors = ref([])
  const validationWarnings = ref([])

  // UI state
  const isDirty = ref(false)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref(null)
  const showMermaidPanel = ref(false)
  const mermaidCode = ref('')
  const mermaidEditMode = ref(false)

  // History for undo/redo
  const historyStack = ref([])
  const historyIndex = ref(-1)

  // Templates
  const templates = ref([])

  // ============================================
  // Getters
  // ============================================
  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < historyStack.value.length - 1)

  const hasErrors = computed(() => validationErrors.value.length > 0)
  const hasWarnings = computed(() => validationWarnings.value.length > 0)

  const isValid = computed(() => !hasErrors.value)

  const statusCount = computed(() => workflowConfig.value.statuses?.length || 0)
  const transitionCount = computed(() => {
    let count = 0
    Object.values(workflowConfig.value.transitions || {}).forEach(sources => {
      count += sources.length
    })
    return count
  })

  const selectedElement = computed(() => {
    if (selectedNode.value) {
      return { type: 'node', data: selectedNode.value }
    }
    if (selectedEdge.value) {
      return { type: 'edge', data: selectedEdge.value }
    }
    return null
  })

  // ============================================
  // Actions
  // ============================================

  /**
   * Load workflow configuration for a client
   */
  const loadConfig = async (clientIdParam, clientNameParam = '') => {
    try {
      isLoading.value = true
      error.value = null
      clientId.value = clientIdParam
      clientName.value = clientNameParam

      const response = await getWorkflowConfig(clientIdParam)
      workflowConfig.value = response.data

      // Convert to Vue Flow format
      const { nodes: flowNodes, edges: flowEdges } = configToVueFlow(workflowConfig.value)
      nodes.value = flowNodes
      edges.value = flowEdges

      // Generate Mermaid code
      mermaidCode.value = configToMermaid(workflowConfig.value)

      // Validate
      runValidation()

      // Initialize history
      pushToHistory()
      isDirty.value = false

    } catch (e) {
      error.value = e.response?.data?.detail || 'Failed to load workflow configuration'
      console.error('Failed to load workflow config:', e)
      useNotificationStore().showError(error.value)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Save workflow configuration
   */
  const saveConfig = async () => {
    if (!clientId.value) {
      error.value = 'No client selected'
      return { success: false, error: error.value }
    }

    // Run validation before save
    runValidation()
    if (hasErrors.value) {
      error.value = 'Cannot save workflow with validation errors'
      return { success: false, error: error.value, validationErrors: validationErrors.value }
    }

    try {
      isSaving.value = true
      error.value = null

      // Convert Vue Flow to config format
      const config = vueFlowToConfig(nodes.value, edges.value, workflowConfig.value.closure_trigger)

      await updateWorkflowConfig(clientId.value, config)
      workflowConfig.value = config
      isDirty.value = false

      return { success: true }
    } catch (e) {
      error.value = e.response?.data?.detail || 'Failed to save workflow configuration'
      return { success: false, error: error.value }
    } finally {
      isSaving.value = false
    }
  }

  /**
   * Load available templates
   */
  const loadTemplates = async () => {
    try {
      const response = await getWorkflowTemplates()
      templates.value = response.data || []
    } catch (e) {
      console.error('Failed to load templates:', e)
      useNotificationStore().showError('Failed to load workflow templates. Please try again.')
    }
  }

  /**
   * Apply a template
   */
  const applyTemplate = async (templateId) => {
    if (!clientId.value) {
      error.value = 'No client selected'
      return { success: false, error: error.value }
    }

    try {
      isLoading.value = true
      error.value = null

      await applyWorkflowTemplate(clientId.value, templateId)

      // Reload config after applying template
      await loadConfig(clientId.value, clientName.value)

      return { success: true }
    } catch (e) {
      error.value = e.response?.data?.detail || 'Failed to apply template'
      return { success: false, error: error.value }
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Add a new status node
   */
  const addStatus = (statusName, position = null) => {
    const normalizedName = statusName.toUpperCase().replace(/\s+/g, '_')

    // Check for duplicates
    if (workflowConfig.value.statuses.includes(normalizedName)) {
      error.value = `Status "${normalizedName}" already exists`
      return false
    }

    // Add to config
    workflowConfig.value.statuses.push(normalizedName)

    // Create node
    const newNode = {
      id: normalizedName,
      type: 'workflowState',
      position: position || calculateNewNodePosition(),
      data: {
        label: normalizedName,
        statusType: classifyStatus(normalizedName)
      }
    }
    nodes.value.push(newNode)

    markDirty()
    pushToHistory()
    runValidation()
    syncMermaidCode()

    return true
  }

  /**
   * Remove a status node and its connected edges
   */
  const removeStatus = (statusId) => {
    // Check if it's a protected status
    if (['RECEIVED'].includes(statusId)) {
      error.value = 'Cannot remove the RECEIVED status (entry point)'
      return false
    }

    // Remove from config
    workflowConfig.value.statuses = workflowConfig.value.statuses.filter(s => s !== statusId)

    // Remove from transitions (as target and source)
    delete workflowConfig.value.transitions[statusId]
    Object.keys(workflowConfig.value.transitions).forEach(target => {
      workflowConfig.value.transitions[target] =
        workflowConfig.value.transitions[target].filter(source => source !== statusId)
    })

    // Remove node
    nodes.value = nodes.value.filter(n => n.id !== statusId)

    // Remove connected edges
    edges.value = edges.value.filter(e => e.source !== statusId && e.target !== statusId)

    // Clear selection if this was selected
    if (selectedNode.value?.id === statusId) {
      selectedNode.value = null
    }

    markDirty()
    pushToHistory()
    runValidation()
    syncMermaidCode()

    return true
  }

  /**
   * Add a transition (edge)
   */
  const addTransition = (sourceId, targetId) => {
    // Validate source and target exist
    if (!workflowConfig.value.statuses.includes(sourceId) ||
        !workflowConfig.value.statuses.includes(targetId)) {
      error.value = 'Invalid source or target status'
      return false
    }

    // Check for existing transition
    const existingTransitions = workflowConfig.value.transitions[targetId] || []
    if (existingTransitions.includes(sourceId)) {
      error.value = 'Transition already exists'
      return false
    }

    // Add to config
    if (!workflowConfig.value.transitions[targetId]) {
      workflowConfig.value.transitions[targetId] = []
    }
    workflowConfig.value.transitions[targetId].push(sourceId)

    // Create edge
    const edgeId = `${sourceId}-${targetId}`
    const newEdge = {
      id: edgeId,
      source: sourceId,
      target: targetId,
      type: 'workflowTransition',
      animated: false,
      data: { label: '' }
    }
    edges.value.push(newEdge)

    markDirty()
    pushToHistory()
    runValidation()
    syncMermaidCode()

    return true
  }

  /**
   * Remove a transition (edge)
   */
  const removeTransition = (sourceId, targetId) => {
    // Remove from config
    if (workflowConfig.value.transitions[targetId]) {
      workflowConfig.value.transitions[targetId] =
        workflowConfig.value.transitions[targetId].filter(s => s !== sourceId)

      // Clean up empty arrays
      if (workflowConfig.value.transitions[targetId].length === 0) {
        delete workflowConfig.value.transitions[targetId]
      }
    }

    // Remove edge
    const edgeId = `${sourceId}-${targetId}`
    edges.value = edges.value.filter(e => e.id !== edgeId)

    // Clear selection if this was selected
    if (selectedEdge.value?.id === edgeId) {
      selectedEdge.value = null
    }

    markDirty()
    pushToHistory()
    runValidation()
    syncMermaidCode()

    return true
  }

  /**
   * Update node position
   */
  const updateNodePosition = (nodeId, position) => {
    const node = nodes.value.find(n => n.id === nodeId)
    if (node) {
      node.position = position
      markDirty()
    }
  }

  /**
   * Update closure trigger
   */
  const setClosureTrigger = (trigger) => {
    workflowConfig.value.closure_trigger = trigger
    markDirty()
    pushToHistory()
    syncMermaidCode()
  }

  /**
   * Select a node
   */
  const selectNode = (node) => {
    selectedNode.value = node
    selectedEdge.value = null
  }

  /**
   * Select an edge
   */
  const selectEdge = (edge) => {
    selectedEdge.value = edge
    selectedNode.value = null
  }

  /**
   * Clear selection
   */
  const clearSelection = () => {
    selectedNode.value = null
    selectedEdge.value = null
  }

  /**
   * Run validation
   */
  const runValidation = () => {
    const result = validateWorkflow(workflowConfig.value)
    validationErrors.value = result.errors
    validationWarnings.value = result.warnings
  }

  /**
   * Sync Mermaid code from current state
   */
  const syncMermaidCode = () => {
    mermaidCode.value = configToMermaid(workflowConfig.value)
  }

  /**
   * Apply Mermaid code changes to canvas
   */
  const applyMermaidCode = (code) => {
    try {
      const config = mermaidToConfig(code)
      if (config) {
        workflowConfig.value = {
          ...config,
          closure_trigger: workflowConfig.value.closure_trigger
        }

        // Regenerate Vue Flow nodes and edges
        const { nodes: flowNodes, edges: flowEdges } = configToVueFlow(workflowConfig.value)
        nodes.value = flowNodes
        edges.value = flowEdges

        markDirty()
        pushToHistory()
        runValidation()

        return { success: true }
      }
    } catch (e) {
      return { success: false, error: e.message || 'Invalid Mermaid syntax' }
    }
    return { success: false, error: 'Failed to parse Mermaid code' }
  }

  /**
   * Toggle Mermaid panel visibility
   */
  const toggleMermaidPanel = () => {
    showMermaidPanel.value = !showMermaidPanel.value
    if (showMermaidPanel.value) {
      syncMermaidCode()
    }
  }

  // ============================================
  // History (Undo/Redo)
  // ============================================

  const markDirty = () => {
    isDirty.value = true
    error.value = null
  }

  const pushToHistory = () => {
    // Truncate any redo history
    if (historyIndex.value < historyStack.value.length - 1) {
      historyStack.value = historyStack.value.slice(0, historyIndex.value + 1)
    }

    // Add current state
    const state = {
      config: JSON.parse(JSON.stringify(workflowConfig.value)),
      nodes: JSON.parse(JSON.stringify(nodes.value)),
      edges: JSON.parse(JSON.stringify(edges.value)),
      timestamp: Date.now()
    }
    historyStack.value.push(state)

    // Limit history size
    if (historyStack.value.length > MAX_HISTORY_SIZE) {
      historyStack.value.shift()
    } else {
      historyIndex.value++
    }
  }

  const undo = () => {
    if (!canUndo.value) return false

    historyIndex.value--
    restoreFromHistory()
    return true
  }

  const redo = () => {
    if (!canRedo.value) return false

    historyIndex.value++
    restoreFromHistory()
    return true
  }

  const restoreFromHistory = () => {
    const state = historyStack.value[historyIndex.value]
    if (state) {
      workflowConfig.value = JSON.parse(JSON.stringify(state.config))
      nodes.value = JSON.parse(JSON.stringify(state.nodes))
      edges.value = JSON.parse(JSON.stringify(state.edges))
      runValidation()
      syncMermaidCode()
      isDirty.value = historyIndex.value > 0
    }
  }

  // ============================================
  // Helper Functions
  // ============================================

  const calculateNewNodePosition = () => {
    // Find the rightmost node and position new one to its right
    let maxX = 100
    let avgY = 200

    if (nodes.value.length > 0) {
      maxX = Math.max(...nodes.value.map(n => n.position?.x || 0)) + 200
      avgY = nodes.value.reduce((sum, n) => sum + (n.position?.y || 0), 0) / nodes.value.length
    }

    return { x: maxX, y: avgY }
  }

  const classifyStatus = (status) => {
    const terminalStatuses = ['CLOSED', 'CANCELLED', 'REJECTED']
    const holdStatuses = ['ON_HOLD', 'HOLD']
    const startStatuses = ['RECEIVED']
    const optionalStatuses = ['SHIPPED', 'DEMOTED']

    if (startStatuses.includes(status)) return 'start'
    if (terminalStatuses.includes(status)) return 'terminal'
    if (holdStatuses.includes(status)) return 'hold'
    if (optionalStatuses.includes(status)) return 'optional'
    return 'normal'
  }

  /**
   * Reset the store
   */
  const reset = () => {
    clientId.value = null
    clientName.value = ''
    workflowConfig.value = { statuses: [], transitions: {}, closure_trigger: 'at_shipment' }
    nodes.value = []
    edges.value = []
    selectedNode.value = null
    selectedEdge.value = null
    validationErrors.value = []
    validationWarnings.value = []
    isDirty.value = false
    isLoading.value = false
    isSaving.value = false
    error.value = null
    showMermaidPanel.value = false
    mermaidCode.value = ''
    historyStack.value = []
    historyIndex.value = -1
  }

  return {
    // State
    clientId,
    clientName,
    workflowConfig,
    nodes,
    edges,
    selectedNode,
    selectedEdge,
    validationErrors,
    validationWarnings,
    isDirty,
    isLoading,
    isSaving,
    error,
    showMermaidPanel,
    mermaidCode,
    mermaidEditMode,
    templates,

    // Getters
    canUndo,
    canRedo,
    hasErrors,
    hasWarnings,
    isValid,
    statusCount,
    transitionCount,
    selectedElement,

    // Actions
    loadConfig,
    saveConfig,
    loadTemplates,
    applyTemplate,
    addStatus,
    removeStatus,
    addTransition,
    removeTransition,
    updateNodePosition,
    setClosureTrigger,
    selectNode,
    selectEdge,
    clearSelection,
    runValidation,
    syncMermaidCode,
    applyMermaidCode,
    toggleMermaidPanel,
    undo,
    redo,
    reset,

    // Helpers
    classifyStatus
  }
})
