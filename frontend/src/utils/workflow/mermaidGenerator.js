/**
 * Mermaid Generator
 * Generates Mermaid flowchart syntax from workflow configuration
 */

import { classifyStatus, getMermaidShape, getMermaidClassName } from './statusClassifier'

/**
 * Generate Mermaid flowchart code from workflow configuration
 * @param {Object} config - Workflow configuration { statuses, transitions, closure_trigger }
 * @returns {string} Mermaid flowchart code
 */
export function generateMermaid(config) {
  if (!config || !config.statuses || config.statuses.length === 0) {
    return '```mermaid\nflowchart TD\n    %% No statuses defined\n```'
  }

  const { statuses, transitions = {} } = config
  const lines = ['flowchart TD']

  // Add header comment
  lines.push('    %% Workflow States')

  // Generate node definitions
  statuses.forEach(status => {
    const statusType = classifyStatus(status)
    const shape = getMermaidShape(statusType)
    const className = getMermaidClassName(statusType)

    // Format: STATUS_ID([Label]):::className
    lines.push(`    ${status}${shape.open}${formatLabel(status)}${shape.close}:::${className}`)
  })

  lines.push('')
  lines.push('    %% Transitions')

  // Generate edges (transitions)
  // Transitions format: { target: [source1, source2, ...] }
  // We need to convert to: source --> target
  const edges = []

  Object.entries(transitions).forEach(([target, sources]) => {
    if (Array.isArray(sources)) {
      sources.forEach(source => {
        if (statuses.includes(source) && statuses.includes(target)) {
          edges.push({ source, target })
        }
      })
    }
  })

  // Sort edges for consistent output (by source, then target)
  edges.sort((a, b) => {
    if (a.source !== b.source) return a.source.localeCompare(b.source)
    return a.target.localeCompare(b.target)
  })

  // Add edge definitions
  edges.forEach(({ source, target }) => {
    lines.push(`    ${source} --> ${target}`)
  })

  lines.push('')
  lines.push('    %% Styles')

  // Add style definitions
  lines.push('    classDef start fill:#d4edda,stroke:#28a745,stroke-width:2px')
  lines.push('    classDef normal fill:#cce5ff,stroke:#007bff,stroke-width:1px')
  lines.push('    classDef terminal fill:#f8d7da,stroke:#dc3545,stroke-width:2px')
  lines.push('    classDef hold fill:#fff3cd,stroke:#ffc107,stroke-width:2px')
  lines.push('    classDef optional fill:#e2e3e5,stroke:#6c757d,stroke-width:1px,stroke-dasharray:5 5')

  return lines.join('\n')
}

/**
 * Format a status name as a human-readable label
 * @param {string} status - Status name (e.g., IN_PROGRESS)
 * @returns {string} Formatted label (e.g., In Progress)
 */
function formatLabel(status) {
  // Keep original for consistency in diagrams
  return status
}

/**
 * Generate a simple summary of the workflow
 * @param {Object} config - Workflow configuration
 * @returns {Object} Summary { statusCount, transitionCount, hasEntryPoint, hasExit }
 */
export function getWorkflowSummary(config) {
  if (!config) {
    return {
      statusCount: 0,
      transitionCount: 0,
      hasEntryPoint: false,
      hasExit: false
    }
  }

  const { statuses = [], transitions = {} } = config

  let transitionCount = 0
  Object.values(transitions).forEach(sources => {
    transitionCount += sources.length
  })

  const hasEntryPoint = statuses.some(s => classifyStatus(s) === 'start')
  const hasExit = statuses.some(s => classifyStatus(s) === 'terminal')

  return {
    statusCount: statuses.length,
    transitionCount,
    hasEntryPoint,
    hasExit
  }
}

export default {
  generateMermaid,
  getWorkflowSummary
}
