/**
 * Mermaid Converter
 * Main API for bidirectional conversion between workflow config, Vue Flow, and Mermaid
 */

import { generateMermaid, getWorkflowSummary } from './mermaidGenerator'
import { parseMermaid, validateMermaidSyntax } from './mermaidParser'
import { classifyStatus, getStatusTypeStyle } from './statusClassifier'

/**
 * Convert workflow configuration to Vue Flow nodes and edges
 * @param {Object} config - Workflow configuration { statuses, transitions, closure_trigger }
 * @returns {Object} { nodes, edges }
 */
export function configToVueFlow(config) {
  if (!config || !config.statuses) {
    return { nodes: [], edges: [] }
  }

  const { statuses, transitions = {} } = config
  const nodes = []
  const edges = []

  // Layout configuration
  const COLUMN_WIDTH = 220
  const ROW_HEIGHT = 100
  const COLUMNS = 4

  // Create nodes
  statuses.forEach((status, index) => {
    const statusType = classifyStatus(status)
    const style = getStatusTypeStyle(statusType)

    // Calculate position in a grid layout
    const col = index % COLUMNS
    const row = Math.floor(index / COLUMNS)

    nodes.push({
      id: status,
      type: 'workflowState',
      position: {
        x: 50 + (col * COLUMN_WIDTH),
        y: 50 + (row * ROW_HEIGHT)
      },
      data: {
        label: status,
        statusType,
        style
      }
    })
  })

  // Create edges from transitions
  // Transitions format: { target: [source1, source2, ...] }
  Object.entries(transitions).forEach(([target, sources]) => {
    if (Array.isArray(sources)) {
      sources.forEach(source => {
        if (statuses.includes(source) && statuses.includes(target)) {
          edges.push({
            id: `${source}-${target}`,
            source,
            target,
            type: 'workflowTransition',
            animated: false,
            data: {}
          })
        }
      })
    }
  })

  return { nodes, edges }
}

/**
 * Convert Vue Flow nodes and edges to workflow configuration
 * @param {Array} nodes - Vue Flow nodes
 * @param {Array} edges - Vue Flow edges
 * @param {string} closureTrigger - Closure trigger setting
 * @returns {Object} Workflow configuration
 */
export function vueFlowToConfig(nodes, edges, closureTrigger = 'at_shipment') {
  const statuses = nodes.map(node => node.id)
  const transitions = {}

  // Convert edges to transition format { target: [sources] }
  edges.forEach(edge => {
    if (!transitions[edge.target]) {
      transitions[edge.target] = []
    }
    if (!transitions[edge.target].includes(edge.source)) {
      transitions[edge.target].push(edge.source)
    }
  })

  // Sort statuses to have RECEIVED first
  statuses.sort((a, b) => {
    if (a === 'RECEIVED') return -1
    if (b === 'RECEIVED') return 1
    return 0
  })

  return {
    statuses,
    transitions,
    closure_trigger: closureTrigger
  }
}

/**
 * Convert workflow configuration to Mermaid code
 * @param {Object} config - Workflow configuration
 * @returns {string} Mermaid flowchart code
 */
export function configToMermaid(config) {
  return generateMermaid(config)
}

/**
 * Convert Mermaid code to workflow configuration
 * @param {string} mermaidCode - Mermaid flowchart code
 * @returns {Object|null} Workflow configuration or null on parse error
 */
export function mermaidToConfig(mermaidCode) {
  // First validate syntax
  const validation = validateMermaidSyntax(mermaidCode)
  if (!validation.isValid) {
    throw new Error(`Invalid Mermaid syntax: ${validation.errors.join(', ')}`)
  }

  return parseMermaid(mermaidCode)
}

/**
 * Convert Mermaid code to Vue Flow nodes and edges
 * @param {string} mermaidCode - Mermaid flowchart code
 * @returns {Object} { nodes, edges }
 */
export function mermaidToVueFlow(mermaidCode) {
  try {
    const config = mermaidToConfig(mermaidCode)
    if (!config) {
      return { nodes: [], edges: [] }
    }
    return configToVueFlow(config)
  } catch (e) {
    // Return empty arrays for invalid Mermaid input
    return { nodes: [], edges: [] }
  }
}

/**
 * Convert Vue Flow nodes and edges to Mermaid code
 * @param {Array} nodes - Vue Flow nodes
 * @param {Array} edges - Vue Flow edges
 * @returns {string} Mermaid flowchart code
 */
export function vueFlowToMermaid(nodes, edges) {
  const config = vueFlowToConfig(nodes, edges)
  return configToMermaid(config)
}

/**
 * Synchronize workflow config from external source to Vue Flow
 * Preserves node positions from existing nodes where possible
 * @param {Object} newConfig - New workflow configuration
 * @param {Array} existingNodes - Existing Vue Flow nodes (for position preservation)
 * @returns {Object} { nodes, edges }
 */
export function syncConfigToVueFlow(newConfig, existingNodes = []) {
  const { nodes: newNodes, edges } = configToVueFlow(newConfig)

  // Create position lookup from existing nodes
  const existingPositions = {}
  existingNodes.forEach(node => {
    existingPositions[node.id] = node.position
  })

  // Preserve positions where possible
  newNodes.forEach(node => {
    if (existingPositions[node.id]) {
      node.position = existingPositions[node.id]
    }
  })

  return { nodes: newNodes, edges }
}

/**
 * Validate that a Mermaid code change can be applied
 * @param {string} mermaidCode - Mermaid code to validate
 * @returns {Object} { isValid, config, errors }
 */
export function validateMermaidChange(mermaidCode) {
  try {
    const syntaxValidation = validateMermaidSyntax(mermaidCode)
    if (!syntaxValidation.isValid) {
      return {
        isValid: false,
        config: null,
        errors: syntaxValidation.errors
      }
    }

    const config = parseMermaid(mermaidCode)
    if (!config) {
      return {
        isValid: false,
        config: null,
        errors: ['Failed to parse Mermaid code']
      }
    }

    return {
      isValid: true,
      config,
      errors: []
    }
  } catch (e) {
    return {
      isValid: false,
      config: null,
      errors: [e.message || 'Unknown error parsing Mermaid']
    }
  }
}

/**
 * Get a summary of differences between two workflow configurations
 * @param {Object} configA - First configuration
 * @param {Object} configB - Second configuration
 * @returns {Object} Difference summary
 */
export function diffConfigs(configA, configB) {
  const statusesA = new Set(configA?.statuses || [])
  const statusesB = new Set(configB?.statuses || [])

  const addedStatuses = [...statusesB].filter(s => !statusesA.has(s))
  const removedStatuses = [...statusesA].filter(s => !statusesB.has(s))

  const edgesA = getEdgeSet(configA?.transitions || {})
  const edgesB = getEdgeSet(configB?.transitions || {})

  const addedEdges = [...edgesB].filter(e => !edgesA.has(e))
  const removedEdges = [...edgesA].filter(e => !edgesB.has(e))

  return {
    addedStatuses,
    removedStatuses,
    addedEdges: addedEdges.map(parseEdgeKey),
    removedEdges: removedEdges.map(parseEdgeKey),
    hasChanges: addedStatuses.length > 0 || removedStatuses.length > 0 ||
                addedEdges.length > 0 || removedEdges.length > 0
  }
}

// Helper to create a Set of edge keys for comparison
function getEdgeSet(transitions) {
  const edges = new Set()
  Object.entries(transitions).forEach(([target, sources]) => {
    (sources || []).forEach(source => {
      edges.add(`${source}-->${target}`)
    })
  })
  return edges
}

// Helper to parse an edge key back to { source, target }
function parseEdgeKey(edgeKey) {
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
  getWorkflowSummary
}
