/**
 * Mermaid generator — produces flowchart syntax from a workflow
 * configuration.
 */

import { classifyStatus, getMermaidShape, getMermaidClassName } from './statusClassifier'
import type { WorkflowConfig } from './types'

export interface WorkflowSummary {
  statusCount: number
  transitionCount: number
  hasEntryPoint: boolean
  hasExit: boolean
}

export function generateMermaid(config: WorkflowConfig | null | undefined): string {
  if (!config || !config.statuses || config.statuses.length === 0) {
    return '```mermaid\nflowchart TD\n    %% No statuses defined\n```'
  }

  const { statuses, transitions = {} } = config
  const lines: string[] = ['flowchart TD']

  lines.push('    %% Workflow States')

  statuses.forEach((status) => {
    const statusType = classifyStatus(status)
    const shape = getMermaidShape(statusType)
    const className = getMermaidClassName(statusType)

    lines.push(
      `    ${status}${shape.open}${formatLabel(status)}${shape.close}:::${className}`,
    )
  })

  lines.push('')
  lines.push('    %% Transitions')

  const edges: { source: string; target: string }[] = []

  Object.entries(transitions).forEach(([target, sources]) => {
    if (Array.isArray(sources)) {
      sources.forEach((source) => {
        if (statuses.includes(source) && statuses.includes(target)) {
          edges.push({ source, target })
        }
      })
    }
  })

  edges.sort((a, b) => {
    if (a.source !== b.source) return a.source.localeCompare(b.source)
    return a.target.localeCompare(b.target)
  })

  edges.forEach(({ source, target }) => {
    lines.push(`    ${source} --> ${target}`)
  })

  lines.push('')
  lines.push('    %% Styles')

  lines.push('    classDef start fill:#d4edda,stroke:#28a745,stroke-width:2px')
  lines.push('    classDef normal fill:#cce5ff,stroke:#007bff,stroke-width:1px')
  lines.push('    classDef terminal fill:#f8d7da,stroke:#dc3545,stroke-width:2px')
  lines.push('    classDef hold fill:#fff3cd,stroke:#ffc107,stroke-width:2px')
  lines.push(
    '    classDef optional fill:#e2e3e5,stroke:#6c757d,stroke-width:1px,stroke-dasharray:5 5',
  )

  return lines.join('\n')
}

function formatLabel(status: string): string {
  return status
}

export function getWorkflowSummary(
  config: WorkflowConfig | null | undefined,
): WorkflowSummary {
  if (!config) {
    return {
      statusCount: 0,
      transitionCount: 0,
      hasEntryPoint: false,
      hasExit: false,
    }
  }

  const { statuses = [], transitions = {} } = config

  let transitionCount = 0
  Object.values(transitions).forEach((sources) => {
    transitionCount += sources.length
  })

  const hasEntryPoint = statuses.some((s) => classifyStatus(s) === 'start')
  const hasExit = statuses.some((s) => classifyStatus(s) === 'terminal')

  return {
    statusCount: statuses.length,
    transitionCount,
    hasEntryPoint,
    hasExit,
  }
}

export default {
  generateMermaid,
  getWorkflowSummary,
}
