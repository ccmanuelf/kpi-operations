/**
 * Workflow designer store — visual editor state with undo/redo,
 * validation, and Mermaid sync.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getWorkflowConfig,
  updateWorkflowConfig,
  getWorkflowTemplates,
  applyWorkflowTemplate,
} from '@/services/api/workflow'
import {
  configToVueFlow,
  vueFlowToConfig,
  configToMermaid,
  mermaidToConfig,
} from '@/utils/workflow/mermaidConverter'
import { validateWorkflow } from '@/utils/workflow/workflowValidator'
import i18n from '@/i18n'
import { useNotificationStore } from './notificationStore'

export type StatusType = 'start' | 'terminal' | 'hold' | 'optional' | 'normal'
export type ClosureTrigger = 'at_shipment' | 'at_completion' | string

export interface WorkflowConfig {
  statuses: string[]
  transitions: Record<string, string[]>
  closure_trigger: ClosureTrigger
}

export interface NodePosition {
  x: number
  y: number
}

export interface FlowNode {
  id: string
  type: string
  position: NodePosition
  data: {
    label: string
    statusType: StatusType
    [key: string]: unknown
  }
}

export interface FlowEdge {
  id: string
  source: string
  target: string
  type: string
  animated?: boolean
  data?: Record<string, unknown>
}

export interface WorkflowTemplate {
  template_id?: string | number
  name?: string
  [key: string]: unknown
}

export interface ValidationIssue {
  message?: string
  severity?: string
  [key: string]: unknown
}

export interface ActionResult<T = unknown> {
  success: boolean
  error?: string
  validationErrors?: ValidationIssue[]
  data?: T
}

interface HistoryState {
  config: WorkflowConfig
  nodes: FlowNode[]
  edges: FlowEdge[]
  timestamp: number
}

const t = (key: string): string => i18n.global.t(key)

const MAX_HISTORY_SIZE = 50

const extractDetail = (e: unknown, fallback: string): string => {
  const ax = e as { response?: { data?: { detail?: string } }; message?: string }
  return ax?.response?.data?.detail || ax?.message || fallback
}

export const useWorkflowDesignerStore = defineStore('workflowDesigner', () => {
  const clientId = ref<string | number | null>(null)
  const clientName = ref('')
  const workflowConfig = ref<WorkflowConfig>({
    statuses: [],
    transitions: {},
    closure_trigger: 'at_shipment',
  })

  const nodes = ref<FlowNode[]>([])
  const edges = ref<FlowEdge[]>([])
  const selectedNode = ref<FlowNode | null>(null)
  const selectedEdge = ref<FlowEdge | null>(null)

  const validationErrors = ref<ValidationIssue[]>([])
  const validationWarnings = ref<ValidationIssue[]>([])

  const isDirty = ref(false)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)
  const showMermaidPanel = ref(false)
  const mermaidCode = ref('')
  const mermaidEditMode = ref(false)

  const historyStack = ref<HistoryState[]>([])
  const historyIndex = ref(-1)

  const templates = ref<WorkflowTemplate[]>([])

  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < historyStack.value.length - 1)

  const hasErrors = computed(() => validationErrors.value.length > 0)
  const hasWarnings = computed(() => validationWarnings.value.length > 0)
  const isValid = computed(() => !hasErrors.value)

  const statusCount = computed(() => workflowConfig.value.statuses?.length || 0)
  const transitionCount = computed(() => {
    let count = 0
    Object.values(workflowConfig.value.transitions || {}).forEach((sources) => {
      count += sources.length
    })
    return count
  })

  const selectedElement = computed(() => {
    if (selectedNode.value) {
      return { type: 'node' as const, data: selectedNode.value }
    }
    if (selectedEdge.value) {
      return { type: 'edge' as const, data: selectedEdge.value }
    }
    return null
  })

  const calculateNewNodePosition = (): NodePosition => {
    let maxX = 100
    let avgY = 200

    if (nodes.value.length > 0) {
      maxX = Math.max(...nodes.value.map((n) => n.position?.x || 0)) + 200
      avgY =
        nodes.value.reduce((sum, n) => sum + (n.position?.y || 0), 0) / nodes.value.length
    }

    return { x: maxX, y: avgY }
  }

  const classifyStatus = (status: string): StatusType => {
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

  const runValidation = (): void => {
    const result = validateWorkflow(workflowConfig.value) as {
      errors: ValidationIssue[]
      warnings: ValidationIssue[]
    }
    validationErrors.value = result.errors
    validationWarnings.value = result.warnings
  }

  const syncMermaidCode = (): void => {
    mermaidCode.value = configToMermaid(workflowConfig.value)
  }

  const markDirty = (): void => {
    isDirty.value = true
    error.value = null
  }

  const pushToHistory = (): void => {
    if (historyIndex.value < historyStack.value.length - 1) {
      historyStack.value = historyStack.value.slice(0, historyIndex.value + 1)
    }

    const state: HistoryState = {
      config: JSON.parse(JSON.stringify(workflowConfig.value)),
      nodes: JSON.parse(JSON.stringify(nodes.value)),
      edges: JSON.parse(JSON.stringify(edges.value)),
      timestamp: Date.now(),
    }
    historyStack.value.push(state)

    if (historyStack.value.length > MAX_HISTORY_SIZE) {
      historyStack.value.shift()
    } else {
      historyIndex.value++
    }
  }

  const restoreFromHistory = (): void => {
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

  const undo = (): boolean => {
    if (!canUndo.value) return false
    historyIndex.value--
    restoreFromHistory()
    return true
  }

  const redo = (): boolean => {
    if (!canRedo.value) return false
    historyIndex.value++
    restoreFromHistory()
    return true
  }

  const loadConfig = async (
    clientIdParam: string | number,
    clientNameParam = '',
  ): Promise<void> => {
    try {
      isLoading.value = true
      error.value = null
      clientId.value = clientIdParam
      clientName.value = clientNameParam

      const response = await getWorkflowConfig(clientIdParam)
      workflowConfig.value = response.data as WorkflowConfig

      const { nodes: flowNodes, edges: flowEdges } = configToVueFlow(workflowConfig.value)
      nodes.value = flowNodes
      edges.value = flowEdges

      mermaidCode.value = configToMermaid(workflowConfig.value)

      runValidation()
      pushToHistory()
      isDirty.value = false
    } catch (e) {
      error.value = extractDetail(e, 'Failed to load workflow configuration')
      // eslint-disable-next-line no-console
      console.error('Failed to load workflow config:', e)
      useNotificationStore().showError(error.value)
    } finally {
      isLoading.value = false
    }
  }

  const saveConfig = async (): Promise<ActionResult> => {
    if (!clientId.value) {
      error.value = 'No client selected'
      return { success: false, error: error.value }
    }

    runValidation()
    if (hasErrors.value) {
      error.value = 'Cannot save workflow with validation errors'
      return {
        success: false,
        error: error.value,
        validationErrors: validationErrors.value,
      }
    }

    try {
      isSaving.value = true
      error.value = null

      const config = vueFlowToConfig(
        nodes.value,
        edges.value,
        workflowConfig.value.closure_trigger,
      ) as WorkflowConfig

      await updateWorkflowConfig(
        clientId.value,
        config as unknown as Record<string, unknown>,
      )
      workflowConfig.value = config
      isDirty.value = false

      return { success: true }
    } catch (e) {
      error.value = extractDetail(e, 'Failed to save workflow configuration')
      return { success: false, error: error.value }
    } finally {
      isSaving.value = false
    }
  }

  const loadTemplates = async (): Promise<void> => {
    try {
      const response = await getWorkflowTemplates()
      templates.value = (response.data as WorkflowTemplate[]) || []
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to load templates:', e)
      useNotificationStore().showError(t('notifications.workflow.templateLoadFailed'))
    }
  }

  const applyTemplate = async (
    templateId: string | number,
  ): Promise<ActionResult> => {
    if (!clientId.value) {
      error.value = 'No client selected'
      return { success: false, error: error.value }
    }

    try {
      isLoading.value = true
      error.value = null

      await applyWorkflowTemplate(clientId.value, templateId)
      await loadConfig(clientId.value, clientName.value)

      return { success: true }
    } catch (e) {
      error.value = extractDetail(e, 'Failed to apply template')
      return { success: false, error: error.value }
    } finally {
      isLoading.value = false
    }
  }

  const addStatus = (statusName: string, position: NodePosition | null = null): boolean => {
    const normalizedName = statusName.toUpperCase().replace(/\s+/g, '_')

    if (workflowConfig.value.statuses.includes(normalizedName)) {
      error.value = `Status "${normalizedName}" already exists`
      return false
    }

    workflowConfig.value.statuses.push(normalizedName)

    const newNode: FlowNode = {
      id: normalizedName,
      type: 'workflowState',
      position: position || calculateNewNodePosition(),
      data: {
        label: normalizedName,
        statusType: classifyStatus(normalizedName),
      },
    }
    nodes.value.push(newNode)

    markDirty()
    pushToHistory()
    runValidation()
    syncMermaidCode()

    return true
  }

  const removeStatus = (statusId: string): boolean => {
    if (['RECEIVED'].includes(statusId)) {
      error.value = 'Cannot remove the RECEIVED status (entry point)'
      return false
    }

    workflowConfig.value.statuses = workflowConfig.value.statuses.filter(
      (s) => s !== statusId,
    )

    delete workflowConfig.value.transitions[statusId]
    Object.keys(workflowConfig.value.transitions).forEach((target) => {
      workflowConfig.value.transitions[target] = workflowConfig.value.transitions[
        target
      ].filter((source) => source !== statusId)
    })

    nodes.value = nodes.value.filter((n) => n.id !== statusId)
    edges.value = edges.value.filter((e) => e.source !== statusId && e.target !== statusId)

    if (selectedNode.value?.id === statusId) {
      selectedNode.value = null
    }

    markDirty()
    pushToHistory()
    runValidation()
    syncMermaidCode()

    return true
  }

  const addTransition = (sourceId: string, targetId: string): boolean => {
    if (
      !workflowConfig.value.statuses.includes(sourceId) ||
      !workflowConfig.value.statuses.includes(targetId)
    ) {
      error.value = 'Invalid source or target status'
      return false
    }

    const existingTransitions = workflowConfig.value.transitions[targetId] || []
    if (existingTransitions.includes(sourceId)) {
      error.value = 'Transition already exists'
      return false
    }

    if (!workflowConfig.value.transitions[targetId]) {
      workflowConfig.value.transitions[targetId] = []
    }
    workflowConfig.value.transitions[targetId].push(sourceId)

    const edgeId = `${sourceId}-${targetId}`
    const newEdge: FlowEdge = {
      id: edgeId,
      source: sourceId,
      target: targetId,
      type: 'workflowTransition',
      animated: false,
      data: { label: '' },
    }
    edges.value.push(newEdge)

    markDirty()
    pushToHistory()
    runValidation()
    syncMermaidCode()

    return true
  }

  const removeTransition = (sourceId: string, targetId: string): boolean => {
    if (workflowConfig.value.transitions[targetId]) {
      workflowConfig.value.transitions[targetId] = workflowConfig.value.transitions[
        targetId
      ].filter((s) => s !== sourceId)

      if (workflowConfig.value.transitions[targetId].length === 0) {
        delete workflowConfig.value.transitions[targetId]
      }
    }

    const edgeId = `${sourceId}-${targetId}`
    edges.value = edges.value.filter((e) => e.id !== edgeId)

    if (selectedEdge.value?.id === edgeId) {
      selectedEdge.value = null
    }

    markDirty()
    pushToHistory()
    runValidation()
    syncMermaidCode()

    return true
  }

  const updateNodePosition = (nodeId: string, position: NodePosition): void => {
    const node = nodes.value.find((n) => n.id === nodeId)
    if (node) {
      node.position = position
      markDirty()
    }
  }

  const setClosureTrigger = (trigger: ClosureTrigger): void => {
    workflowConfig.value.closure_trigger = trigger
    markDirty()
    pushToHistory()
    syncMermaidCode()
  }

  const selectNode = (node: FlowNode | null): void => {
    selectedNode.value = node
    selectedEdge.value = null
  }

  const selectEdge = (edge: FlowEdge | null): void => {
    selectedEdge.value = edge
    selectedNode.value = null
  }

  const clearSelection = (): void => {
    selectedNode.value = null
    selectedEdge.value = null
  }

  const applyMermaidCode = (code: string): ActionResult => {
    try {
      const config = mermaidToConfig(code) as WorkflowConfig | null
      if (config) {
        workflowConfig.value = {
          ...config,
          closure_trigger: workflowConfig.value.closure_trigger,
        }

        const { nodes: flowNodes, edges: flowEdges } = configToVueFlow(workflowConfig.value)
        nodes.value = flowNodes
        edges.value = flowEdges

        markDirty()
        pushToHistory()
        runValidation()

        return { success: true }
      }
    } catch (e) {
      return { success: false, error: extractDetail(e, 'Invalid Mermaid syntax') }
    }
    return { success: false, error: 'Failed to parse Mermaid code' }
  }

  const toggleMermaidPanel = (): void => {
    showMermaidPanel.value = !showMermaidPanel.value
    if (showMermaidPanel.value) {
      syncMermaidCode()
    }
  }

  const reset = (): void => {
    clientId.value = null
    clientName.value = ''
    workflowConfig.value = {
      statuses: [],
      transitions: {},
      closure_trigger: 'at_shipment',
    }
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
    canUndo,
    canRedo,
    hasErrors,
    hasWarnings,
    isValid,
    statusCount,
    transitionCount,
    selectedElement,
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
    classifyStatus,
  }
})
