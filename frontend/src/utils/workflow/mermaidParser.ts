/**
 * Mermaid parser — converts flowchart syntax into a workflow
 * configuration shape.
 */

import type { WorkflowConfig, MermaidValidationResult } from './types'

export function parseMermaid(mermaidCode: string | null | undefined): WorkflowConfig | null {
  if (!mermaidCode || typeof mermaidCode !== 'string') {
    return null
  }

  try {
    const lines = mermaidCode
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith('%') && !line.startsWith('```'))

    const statuses = new Set<string>()
    const transitions: Record<string, string[]> = {}

    lines.forEach((line) => {
      if (line.startsWith('flowchart') || line.startsWith('graph')) {
        return
      }

      if (
        line.startsWith('classDef') ||
        line.startsWith('class ') ||
        line.startsWith('style ')
      ) {
        return
      }

      const edgeMatch = line.match(
        /^([A-Z][A-Z0-9_]*)\s*(?:-->|->|-->>|-.->)\s*([A-Z][A-Z0-9_]*)/,
      )
      if (edgeMatch) {
        const [, source, target] = edgeMatch
        statuses.add(source)
        statuses.add(target)

        if (!transitions[target]) {
          transitions[target] = []
        }
        if (!transitions[target].includes(source)) {
          transitions[target].push(source)
        }
        return
      }

      const nodeMatch = line.match(/^([A-Z][A-Z0-9_]*)(?:\(?\[{1,2}|{{|\[\/)/)
      if (nodeMatch) {
        const [, status] = nodeMatch
        statuses.add(status)
        return
      }

      const simpleNodeMatch = line.match(/^([A-Z][A-Z0-9_]*)(?:\s|$|:::)/)
      if (simpleNodeMatch && !line.includes('-->') && !line.includes('->')) {
        const [, status] = simpleNodeMatch
        if (status.length > 0) {
          statuses.add(status)
        }
      }
    })

    const statusArray = Array.from(statuses).sort((a, b) => {
      if (a === 'RECEIVED') return -1
      if (b === 'RECEIVED') return 1
      return a.localeCompare(b)
    })

    if (statusArray.length === 0) {
      return null
    }

    return {
      statuses: statusArray,
      transitions,
    }
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('Error parsing Mermaid code:', e)
    return null
  }
}

export function validateMermaidSyntax(
  mermaidCode: string | null | undefined,
): MermaidValidationResult {
  const errors: string[] = []

  if (!mermaidCode || typeof mermaidCode !== 'string') {
    errors.push('Empty or invalid input')
    return { isValid: false, errors }
  }

  const lines = mermaidCode
    .split('\n')
    .map((line, i) => ({ text: line.trim(), lineNum: i + 1 }))
    .filter(({ text }) => text && !text.startsWith('%') && !text.startsWith('```'))

  const hasFlowchart = lines.some(
    ({ text }) => text.startsWith('flowchart') || text.startsWith('graph'),
  )

  if (!hasFlowchart) {
    errors.push('Missing flowchart or graph declaration')
  }

  lines.forEach(({ text, lineNum }) => {
    if (text.startsWith('flowchart') || text.startsWith('graph')) {
      return
    }
    if (
      text.startsWith('classDef') ||
      text.startsWith('class ') ||
      text.startsWith('style ')
    ) {
      return
    }

    const openBrackets = (text.match(/\[/g) || []).length
    const closeBrackets = (text.match(/\]/g) || []).length
    const openParens = (text.match(/\(/g) || []).length
    const closeParens = (text.match(/\)/g) || []).length
    const openBraces = (text.match(/\{/g) || []).length
    const closeBraces = (text.match(/\}/g) || []).length

    if (openBrackets !== closeBrackets) {
      errors.push(`Line ${lineNum}: Unbalanced brackets`)
    }
    if (openParens !== closeParens) {
      errors.push(`Line ${lineNum}: Unbalanced parentheses`)
    }
    if (openBraces !== closeBraces) {
      errors.push(`Line ${lineNum}: Unbalanced braces`)
    }

    if (
      text.includes('--') &&
      !text.includes('-->') &&
      !text.includes('--.') &&
      !text.includes('-.')
    ) {
      if (!text.startsWith('---') && !text.includes('-- ')) {
        errors.push(`Line ${lineNum}: Invalid arrow syntax`)
      }
    }
  })

  return {
    isValid: errors.length === 0,
    errors,
  }
}

export function extractStatuses(mermaidCode: string): string[] {
  const result = parseMermaid(mermaidCode)
  return result?.statuses || []
}

export function extractEdges(mermaidCode: string): { source: string; target: string }[] {
  const result = parseMermaid(mermaidCode)
  if (!result?.transitions) return []

  const edges: { source: string; target: string }[] = []
  Object.entries(result.transitions).forEach(([target, sources]) => {
    sources.forEach((source) => {
      edges.push({ source, target })
    })
  })

  return edges
}

export default {
  parseMermaid,
  validateMermaidSyntax,
  extractStatuses,
  extractEdges,
}
