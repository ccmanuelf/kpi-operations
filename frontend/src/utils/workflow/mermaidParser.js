/**
 * Mermaid Parser
 * Parses Mermaid flowchart syntax into workflow configuration
 */

import { classifyStatus } from './statusClassifier'

/**
 * Parse Mermaid flowchart code into workflow configuration
 * @param {string} mermaidCode - Mermaid flowchart code
 * @returns {Object|null} Workflow configuration { statuses, transitions } or null on error
 */
export function parseMermaid(mermaidCode) {
  if (!mermaidCode || typeof mermaidCode !== 'string') {
    return null
  }

  try {
    const lines = mermaidCode.split('\n')
      .map(line => line.trim())
      .filter(line => line && !line.startsWith('%') && !line.startsWith('```'))

    const statuses = new Set()
    const transitions = {}

    lines.forEach(line => {
      // Skip flowchart declaration
      if (line.startsWith('flowchart') || line.startsWith('graph')) {
        return
      }

      // Skip style definitions
      if (line.startsWith('classDef') || line.startsWith('class ') || line.startsWith('style ')) {
        return
      }

      // Check for edge definition: SOURCE --> TARGET or SOURCE -> TARGET
      const edgeMatch = line.match(/^([A-Z][A-Z0-9_]*)\s*(?:-->|->|-->>|-.->)\s*([A-Z][A-Z0-9_]*)/)
      if (edgeMatch) {
        const [, source, target] = edgeMatch
        statuses.add(source)
        statuses.add(target)

        // Add transition (target: [sources])
        if (!transitions[target]) {
          transitions[target] = []
        }
        if (!transitions[target].includes(source)) {
          transitions[target].push(source)
        }
        return
      }

      // Check for node definition with various shapes
      // Examples:
      //   STATUS([Label]):::class
      //   STATUS[Label]:::class
      //   STATUS[[Label]]:::class
      //   STATUS{{Label}}:::class
      //   STATUS[/Label/]:::class
      const nodeMatch = line.match(/^([A-Z][A-Z0-9_]*)(?:\(?\[{1,2}|{{|\[\/)/)
      if (nodeMatch) {
        const [, status] = nodeMatch
        statuses.add(status)
        return
      }

      // Check for simple node (just a name)
      const simpleNodeMatch = line.match(/^([A-Z][A-Z0-9_]*)(?:\s|$|:::)/)
      if (simpleNodeMatch && !line.includes('-->') && !line.includes('->')) {
        const [, status] = simpleNodeMatch
        if (status.length > 0) {
          statuses.add(status)
        }
      }
    })

    // Convert Set to sorted Array
    const statusArray = Array.from(statuses).sort((a, b) => {
      // Put RECEIVED first
      if (a === 'RECEIVED') return -1
      if (b === 'RECEIVED') return 1
      return a.localeCompare(b)
    })

    if (statusArray.length === 0) {
      return null
    }

    return {
      statuses: statusArray,
      transitions
    }
  } catch (e) {
    console.error('Error parsing Mermaid code:', e)
    return null
  }
}

/**
 * Validate Mermaid syntax without full parsing
 * @param {string} mermaidCode - Mermaid code to validate
 * @returns {Object} { isValid, errors }
 */
export function validateMermaidSyntax(mermaidCode) {
  const errors = []

  if (!mermaidCode || typeof mermaidCode !== 'string') {
    errors.push('Empty or invalid input')
    return { isValid: false, errors }
  }

  const lines = mermaidCode.split('\n')
    .map((line, i) => ({ text: line.trim(), lineNum: i + 1 }))
    .filter(({ text }) => text && !text.startsWith('%') && !text.startsWith('```'))

  // Check for flowchart declaration
  const hasFlowchart = lines.some(({ text }) =>
    text.startsWith('flowchart') || text.startsWith('graph')
  )

  if (!hasFlowchart) {
    errors.push('Missing flowchart or graph declaration')
  }

  // Check for common syntax errors
  lines.forEach(({ text, lineNum }) => {
    // Skip declarations
    if (text.startsWith('flowchart') || text.startsWith('graph')) {
      return
    }
    if (text.startsWith('classDef') || text.startsWith('class ') || text.startsWith('style ')) {
      return
    }

    // Check for unclosed brackets
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

    // Check for invalid arrow syntax
    if (text.includes('--') && !text.includes('-->') && !text.includes('--.') && !text.includes('-.')) {
      if (!text.startsWith('---') && !text.includes('-- ')) {
        errors.push(`Line ${lineNum}: Invalid arrow syntax`)
      }
    }
  })

  return {
    isValid: errors.length === 0,
    errors
  }
}

/**
 * Extract status names from Mermaid code
 * @param {string} mermaidCode - Mermaid code
 * @returns {string[]} Array of status names
 */
export function extractStatuses(mermaidCode) {
  const result = parseMermaid(mermaidCode)
  return result?.statuses || []
}

/**
 * Extract edges from Mermaid code
 * @param {string} mermaidCode - Mermaid code
 * @returns {Array} Array of { source, target } objects
 */
export function extractEdges(mermaidCode) {
  const result = parseMermaid(mermaidCode)
  if (!result?.transitions) return []

  const edges = []
  Object.entries(result.transitions).forEach(([target, sources]) => {
    sources.forEach(source => {
      edges.push({ source, target })
    })
  })

  return edges
}

export default {
  parseMermaid,
  validateMermaidSyntax,
  extractStatuses,
  extractEdges
}
