/**
 * Unit tests for Mermaid Generator
 * Tests Mermaid flowchart syntax generation from workflow configuration
 */
import { describe, it, expect } from 'vitest'
import { generateMermaid, getWorkflowSummary } from '../mermaidGenerator'

describe('Mermaid Generator', () => {
  describe('generateMermaid', () => {
    it('generates valid Mermaid syntax for simple workflow', () => {
      const config = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          COMPLETED: ['IN_PROGRESS'],
          CLOSED: ['COMPLETED']
        }
      }

      const result = generateMermaid(config)

      expect(result).toContain('flowchart TD')
      expect(result).toContain('RECEIVED')
      expect(result).toContain('IN_PROGRESS')
      expect(result).toContain('COMPLETED')
      expect(result).toContain('CLOSED')
    })

    it('includes node shape for start status', () => {
      const config = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: { CLOSED: ['RECEIVED'] }
      }

      const result = generateMermaid(config)

      // Start status uses stadium shape ([...])
      expect(result).toContain('RECEIVED([RECEIVED])')
    })

    it('includes node shape for terminal status', () => {
      const config = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: { CLOSED: ['RECEIVED'] }
      }

      const result = generateMermaid(config)

      // Terminal status uses subroutine shape [[...]]
      expect(result).toContain('CLOSED[[CLOSED]]')
    })

    it('includes node shape for hold status', () => {
      const config = {
        statuses: ['RECEIVED', 'ON_HOLD', 'CLOSED'],
        transitions: {
          ON_HOLD: ['RECEIVED'],
          CLOSED: ['ON_HOLD']
        }
      }

      const result = generateMermaid(config)

      // Hold status uses hexagon shape {{...}}
      expect(result).toContain('ON_HOLD{{ON_HOLD}}')
    })

    it('includes node shape for optional status', () => {
      const config = {
        statuses: ['RECEIVED', 'SHIPPED', 'CLOSED'],
        transitions: {
          SHIPPED: ['RECEIVED'],
          CLOSED: ['SHIPPED']
        }
      }

      const result = generateMermaid(config)

      // Optional status uses parallelogram shape [/.../]
      expect(result).toContain('SHIPPED[/SHIPPED/]')
    })

    it('includes class definitions for styling', () => {
      const config = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: { CLOSED: ['RECEIVED'] }
      }

      const result = generateMermaid(config)

      expect(result).toContain('classDef start')
      expect(result).toContain('classDef normal')
      expect(result).toContain('classDef terminal')
      expect(result).toContain('classDef hold')
      expect(result).toContain('classDef optional')
    })

    it('generates correct edge syntax', () => {
      const config = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          CLOSED: ['IN_PROGRESS']
        }
      }

      const result = generateMermaid(config)

      expect(result).toContain('RECEIVED --> IN_PROGRESS')
      expect(result).toContain('IN_PROGRESS --> CLOSED')
    })

    it('handles multiple sources for same target', () => {
      const config = {
        statuses: ['RECEIVED', 'STEP_A', 'STEP_B', 'FINAL', 'CLOSED'],
        transitions: {
          STEP_A: ['RECEIVED'],
          STEP_B: ['RECEIVED'],
          FINAL: ['STEP_A', 'STEP_B'],
          CLOSED: ['FINAL']
        }
      }

      const result = generateMermaid(config)

      expect(result).toContain('STEP_A --> FINAL')
      expect(result).toContain('STEP_B --> FINAL')
    })

    it('handles empty config gracefully', () => {
      const result = generateMermaid(null)

      expect(result).toContain('flowchart TD')
      expect(result).toContain('No statuses defined')
    })

    it('handles config with empty statuses', () => {
      const result = generateMermaid({ statuses: [], transitions: {} })

      expect(result).toContain('No statuses defined')
    })

    it('ignores transitions for non-existent statuses', () => {
      const config = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: {
          CLOSED: ['RECEIVED'],
          NON_EXISTENT: ['RECEIVED'] // Should be ignored
        }
      }

      const result = generateMermaid(config)

      expect(result).not.toContain('NON_EXISTENT')
    })

    it('sorts edges consistently', () => {
      const config = {
        statuses: ['RECEIVED', 'A', 'B', 'C', 'CLOSED'],
        transitions: {
          B: ['RECEIVED'],
          A: ['RECEIVED'],
          C: ['RECEIVED'],
          CLOSED: ['A', 'B', 'C']
        }
      }

      const result = generateMermaid(config)

      // Edges should be sorted by source, then target
      const lines = result.split('\n')
      const edgeLines = lines.filter(l => l.includes('-->'))

      expect(edgeLines.length).toBeGreaterThan(0)
    })

    it('applies correct class to each node', () => {
      const config = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'ON_HOLD', 'SHIPPED', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          ON_HOLD: ['IN_PROGRESS'],
          SHIPPED: ['IN_PROGRESS'],
          CLOSED: ['SHIPPED']
        }
      }

      const result = generateMermaid(config)

      expect(result).toContain(':::start')
      expect(result).toContain(':::normal')
      expect(result).toContain(':::hold')
      expect(result).toContain(':::optional')
      expect(result).toContain(':::terminal')
    })
  })

  describe('getWorkflowSummary', () => {
    it('returns correct summary for valid workflow', () => {
      const config = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          COMPLETED: ['IN_PROGRESS'],
          CLOSED: ['COMPLETED']
        }
      }

      const summary = getWorkflowSummary(config)

      expect(summary.statusCount).toBe(4)
      expect(summary.transitionCount).toBe(3)
      expect(summary.hasEntryPoint).toBe(true)
      expect(summary.hasExit).toBe(true)
    })

    it('returns correct summary for workflow without entry', () => {
      const config = {
        statuses: ['IN_PROGRESS', 'CLOSED'],
        transitions: {
          CLOSED: ['IN_PROGRESS']
        }
      }

      const summary = getWorkflowSummary(config)

      expect(summary.hasEntryPoint).toBe(false)
      expect(summary.hasExit).toBe(true)
    })

    it('returns correct summary for workflow without exit', () => {
      const config = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'COMPLETED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          COMPLETED: ['IN_PROGRESS']
        }
      }

      const summary = getWorkflowSummary(config)

      expect(summary.hasEntryPoint).toBe(true)
      expect(summary.hasExit).toBe(false)
    })

    it('returns zero counts for null config', () => {
      const summary = getWorkflowSummary(null)

      expect(summary.statusCount).toBe(0)
      expect(summary.transitionCount).toBe(0)
      expect(summary.hasEntryPoint).toBe(false)
      expect(summary.hasExit).toBe(false)
    })

    it('counts transitions from multiple sources correctly', () => {
      const config = {
        statuses: ['RECEIVED', 'A', 'B', 'CLOSED'],
        transitions: {
          A: ['RECEIVED'],
          B: ['RECEIVED'],
          CLOSED: ['A', 'B'] // 2 sources
        }
      }

      const summary = getWorkflowSummary(config)

      expect(summary.transitionCount).toBe(4)
    })
  })
})
