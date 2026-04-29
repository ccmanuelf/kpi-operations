/**
 * Mermaid converter — main API for bidirectional conversion between
 * workflow config, Vue Flow nodes/edges, and Mermaid syntax.
 */

import { generateMermaid, getWorkflowSummary } from './mermaidGenerator'
import { parseMermaid, validateMermaidSyntax } from './mermaidParser'
import {
  classifyStatus,
  getStatusTypeStyle,
  type StatusStyle,
  type StatusType,
} from './statusClassifier'
import type { WorkflowConfig } from './types'

export interface FlowNodePosition {
  x: number
  y: number
}

export interface FlowNode {
  id: string
  type: string
  position: FlowNodePosition
  data: {
    label: string
    statusType: StatusType
    style?: StatusStyle
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

export interface VueFlowGraph {
  nodes: FlowNode[]
  edges: FlowEdge[]
}

export interface ValidationOutcome {
  isValid: boolean
  config: WorkflowConfig | null
  errors: string[]
}

export interface DiffResult {
  addedStatuses: string[]
  removedStatuses: string[]
  addedEdges: { source: string; target: string }[]
  removedEdges: { source: string; target: string }[]
  hasChanges: boolean
}

export function configToVueFlow(
  config: WorkflowConfig | null | undefined,
): VueFlowGraph {
  if (!config || !config.statuses) {
    return { nodes: [], edges: [] }
  }

  const { statuses, transitions = {} } = config
  const nodes: FlowNode[] = []
  const edges: FlowEdge[] = []

  const COLUMN_WIDTH = 220
  const ROW_HEIGHT = 100
  const COLUMNS = 4

  statuses.forEach((status, index) => {
    const statusType = classifyStatus(status)
    const style = getStatusTypeStyle(statusType)

    const col = index % COLUMNS
    const row = Math.floor(index / COLUMNS)

    nodes.push({
      id: status,
      type: 'workflowState',
      position: {
        x: 50 + col * COLUMN_WIDTH,
        y: 50 + row * ROW_HEIGHT,
      },
      data: {
        label: status,
        statusType,
        style,
      },
    })
  })

  Object.entries(transitions).forEach(([target, sources]) => {
    if (Array.isArray(sources)) {
      sources.forEach((source) => {
        if (statuses.includes(source) && statuses.includes(target)) {
          edges.push({
            id: `${source}-${target}`,
            source,
            target,
            type: 'workflowTransition',
            animated: false,
            data: {},
          })
        }
      })
    }
  })

  return { nodes, edges }
}

export function vueFlowToConfig(
  nodes: FlowNode[],
  edges: FlowEdge[],
  closureTrigger: string = 'at_shipment',
): WorkflowConfig {
  const statuses = nodes.map((node) => node.id)
  const transitions: Record<string, string[]> = {}

  edges.forEach((edge) => {
    if (!transitions[edge.target]) {
      transitions[edge.target] = []
    }
    if (!transitions[edge.target].includes(edge.source)) {
      transitions[edge.target].push(edge.source)
    }
  })

  statuses.sort((a, b) => {
    if (a === 'RECEIVED') return -1
    if (b === 'RECEIVED') return 1
    return 0
  })

  return {
    statuses,
    transitions,
    closure_trigger: closureTrigger,
  }
}

export function configToMermaid(config: WorkflowConfig | null | undefined): string {
  return generateMermaid(config)
}

export function mermaidToConfig(mermaidCode: string): WorkflowConfig | null {
  const validation = validateMermaidSyntax(mermaidCode)
  if (!validation.isValid) {
    throw new Error(`Invalid Mermaid syntax: ${validation.errors.join(', ')}`)
  }

  return parseMermaid(mermaidCode)
}

export function mermaidToVueFlow(mermaidCode: string): VueFlowGraph {
  try {
    const config = mermaidToConfig(mermaidCode)
    if (!config) {
      return { nodes: [], edges: [] }
    }
    return configToVueFlow(config)
  } catch {
    return { nodes: [], edges: [] }
  }
}

export function vueFlowToMermaid(nodes: FlowNode[], edges: FlowEdge[]): string {
  const config = vueFlowToConfig(nodes, edges)
  return configToMermaid(config)
}

export function syncConfigToVueFlow(
  newConfig: WorkflowConfig,
  existingNodes: FlowNode[] = [],
): VueFlowGraph {
  const { nodes: newNodes, edges } = configToVueFlow(newConfig)

  const existingPositions: Record<string, FlowNodePosition> = {}
  existingNodes.forEach((node) => {
    existingPositions[node.id] = node.position
  })

  newNodes.forEach((node) => {
    if (existingPositions[node.id]) {
      node.position = existingPositions[node.id]
    }
  })

  return { nodes: newNodes, edges }
}

export function validateMermaidChange(mermaidCode: string): ValidationOutcome {
  try {
    const syntaxValidation = validateMermaidSyntax(mermaidCode)
    if (!syntaxValidation.isValid) {
      return {
        isValid: false,
        config: null,
        errors: syntaxValidation.errors,
      }
    }

    const config = parseMermaid(mermaidCode)
    if (!config) {
      return {
        isValid: false,
        config: null,
        errors: ['Failed to parse Mermaid code'],
      }
    }

    return {
      isValid: true,
      config,
      errors: [],
    }
  } catch (e) {
    return {
      isValid: false,
      config: null,
      errors: [(e as Error).message || 'Unknown error parsing Mermaid'],
    }
  }
}

export function diffConfigs(
  configA: WorkflowConfig | null | undefined,
  configB: WorkflowConfig | null | undefined,
): DiffResult {
  const statusesA = new Set(configA?.statuses || [])
  const statusesB = new Set(configB?.statuses || [])

  const addedStatuses = [...statusesB].filter((s) => !statusesA.has(s))
  const removedStatuses = [...statusesA].filter((s) => !statusesB.has(s))

  const edgesA = getEdgeSet(configA?.transitions || {})
  const edgesB = getEdgeSet(configB?.transitions || {})

  const addedEdges = [...edgesB].filter((e) => !edgesA.has(e))
  const removedEdges = [...edgesA].filter((e) => !edgesB.has(e))

  return {
    addedStatuses,
    removedStatuses,
    addedEdges: addedEdges.map(parseEdgeKey),
    removedEdges: removedEdges.map(parseEdgeKey),
    hasChanges:
      addedStatuses.length > 0 ||
      removedStatuses.length > 0 ||
      addedEdges.length > 0 ||
      removedEdges.length > 0,
  }
}

function getEdgeSet(transitions: Record<string, string[]>): Set<string> {
  const edges = new Set<string>()
  Object.entries(transitions).forEach(([target, sources]) => {
    ;(sources || []).forEach((source) => {
      edges.add(`${source}-->${target}`)
    })
  })
  return edges
}

function parseEdgeKey(edgeKey: string): { source: string; target: string } {
  const [source, target] = edgeKey.split('-->')
  return { source, target }
}

export default {
  configToVueFlow,
  vueFlowToConfig,
  configToMermaid,
  mermaidToConfig,
  mermaidToVueFlow,
  vueFlowToMermaid,
  syncConfigToVueFlow,
  validateMermaidChange,
  diffConfigs,
  getWorkflowSummary,
}
