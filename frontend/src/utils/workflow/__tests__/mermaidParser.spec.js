/**
 * Unit tests for Mermaid Parser
 * Tests parsing Mermaid flowchart syntax into workflow configuration
 */
import { describe, it, expect } from 'vitest'
import {
  parseMermaid,
  validateMermaidSyntax,
  extractStatuses,
  extractEdges
} from '../mermaidParser'

describe('Mermaid Parser', () => {
  describe('parseMermaid', () => {
    it('parses simple flowchart', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> IN_PROGRESS
        IN_PROGRESS --> CLOSED
      `

      const result = parseMermaid(mermaid)

      expect(result).not.toBeNull()
      expect(result.statuses).toContain('RECEIVED')
      expect(result.statuses).toContain('IN_PROGRESS')
      expect(result.statuses).toContain('CLOSED')
    })

    it('parses edges correctly', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> IN_PROGRESS
        IN_PROGRESS --> COMPLETED
        COMPLETED --> CLOSED
      `

      const result = parseMermaid(mermaid)

      expect(result.transitions.IN_PROGRESS).toContain('RECEIVED')
      expect(result.transitions.COMPLETED).toContain('IN_PROGRESS')
      expect(result.transitions.CLOSED).toContain('COMPLETED')
    })

    it('parses node definitions with shapes', () => {
      const mermaid = `
        flowchart TD
        RECEIVED([RECEIVED]):::start
        IN_PROGRESS[IN_PROGRESS]:::normal
        CLOSED[[CLOSED]]:::terminal
        RECEIVED --> IN_PROGRESS
        IN_PROGRESS --> CLOSED
      `

      const result = parseMermaid(mermaid)

      expect(result.statuses).toContain('RECEIVED')
      expect(result.statuses).toContain('IN_PROGRESS')
      expect(result.statuses).toContain('CLOSED')
    })

    it('parses hexagon shapes for hold status', () => {
      const mermaid = `
        flowchart TD
        ON_HOLD{{ON_HOLD}}:::hold
        RECEIVED --> ON_HOLD
      `

      const result = parseMermaid(mermaid)

      expect(result.statuses).toContain('ON_HOLD')
    })

    it('parses parallelogram shapes for optional status', () => {
      const mermaid = `
        flowchart TD
        SHIPPED[/SHIPPED/]:::optional
        RECEIVED --> SHIPPED
      `

      const result = parseMermaid(mermaid)

      expect(result.statuses).toContain('SHIPPED')
    })

    it('handles multiple sources for same target', () => {
      const mermaid = `
        flowchart TD
        A --> TARGET
        B --> TARGET
        C --> TARGET
      `

      const result = parseMermaid(mermaid)

      expect(result.transitions.TARGET).toHaveLength(3)
      expect(result.transitions.TARGET).toContain('A')
      expect(result.transitions.TARGET).toContain('B')
      expect(result.transitions.TARGET).toContain('C')
    })

    it('ignores comments', () => {
      const mermaid = `
        flowchart TD
        %% This is a comment
        RECEIVED --> CLOSED
        %% Another comment
      `

      const result = parseMermaid(mermaid)

      expect(result.statuses).toHaveLength(2)
    })

    it('ignores style definitions', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> CLOSED
        classDef start fill:#d4edda
        style RECEIVED fill:#fff
      `

      const result = parseMermaid(mermaid)

      expect(result.statuses).toHaveLength(2)
    })

    it('sorts RECEIVED to first position', () => {
      const mermaid = `
        flowchart TD
        CLOSED --> END
        RECEIVED --> CLOSED
      `

      const result = parseMermaid(mermaid)

      expect(result.statuses[0]).toBe('RECEIVED')
    })

    it('returns null for empty input', () => {
      expect(parseMermaid(null)).toBeNull()
      expect(parseMermaid('')).toBeNull()
      expect(parseMermaid(undefined)).toBeNull()
    })

    it('returns null when no statuses found', () => {
      const mermaid = `
        flowchart TD
        %% Only comments
      `

      const result = parseMermaid(mermaid)

      expect(result).toBeNull()
    })

    it('handles different arrow styles', () => {
      const mermaid = `
        flowchart TD
        A --> B
        C -> D
      `

      const result = parseMermaid(mermaid)

      expect(result.transitions.B).toContain('A')
      expect(result.transitions.D).toContain('C')
    })

    it('handles graph declaration instead of flowchart', () => {
      const mermaid = `
        graph TD
        RECEIVED --> CLOSED
      `

      const result = parseMermaid(mermaid)

      expect(result).not.toBeNull()
      expect(result.statuses).toContain('RECEIVED')
    })

    it('ignores markdown code fences', () => {
      const mermaid = `
        \`\`\`mermaid
        flowchart TD
        RECEIVED --> CLOSED
        \`\`\`
      `

      const result = parseMermaid(mermaid)

      expect(result).not.toBeNull()
      expect(result.statuses).toContain('RECEIVED')
    })
  })

  describe('validateMermaidSyntax', () => {
    it('validates correct syntax', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> CLOSED
      `

      const result = validateMermaidSyntax(mermaid)

      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })

    it('returns error for missing flowchart declaration', () => {
      const mermaid = `
        RECEIVED --> CLOSED
      `

      const result = validateMermaidSyntax(mermaid)

      expect(result.isValid).toBe(false)
      expect(result.errors.some(e => e.includes('flowchart'))).toBe(true)
    })

    it('returns error for unbalanced brackets', () => {
      const mermaid = `
        flowchart TD
        RECEIVED([RECEIVED
      `

      const result = validateMermaidSyntax(mermaid)

      expect(result.isValid).toBe(false)
      expect(result.errors.some(e => e.includes('bracket') || e.includes('parenthes'))).toBe(true)
    })

    it('returns error for unbalanced braces', () => {
      const mermaid = `
        flowchart TD
        ON_HOLD{{ON_HOLD}
      `

      const result = validateMermaidSyntax(mermaid)

      expect(result.isValid).toBe(false)
    })

    it('returns error for empty input', () => {
      const result = validateMermaidSyntax('')

      expect(result.isValid).toBe(false)
      expect(result.errors.some(e => e.includes('Empty'))).toBe(true)
    })

    it('returns error for null input', () => {
      const result = validateMermaidSyntax(null)

      expect(result.isValid).toBe(false)
    })

    it('ignores comments in validation', () => {
      const mermaid = `
        flowchart TD
        %% Unbalanced in comment (((
        RECEIVED --> CLOSED
      `

      const result = validateMermaidSyntax(mermaid)

      expect(result.isValid).toBe(true)
    })

    it('validates style definitions', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> CLOSED
        classDef start fill:#d4edda
      `

      const result = validateMermaidSyntax(mermaid)

      expect(result.isValid).toBe(true)
    })
  })

  describe('extractStatuses', () => {
    it('extracts all statuses from mermaid code', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> IN_PROGRESS
        IN_PROGRESS --> CLOSED
      `

      const statuses = extractStatuses(mermaid)

      expect(statuses).toContain('RECEIVED')
      expect(statuses).toContain('IN_PROGRESS')
      expect(statuses).toContain('CLOSED')
    })

    it('returns empty array for invalid mermaid', () => {
      const statuses = extractStatuses('')

      expect(statuses).toEqual([])
    })
  })

  describe('extractEdges', () => {
    it('extracts all edges from mermaid code', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> IN_PROGRESS
        IN_PROGRESS --> CLOSED
      `

      const edges = extractEdges(mermaid)

      expect(edges).toHaveLength(2)
      expect(edges).toContainEqual({ source: 'RECEIVED', target: 'IN_PROGRESS' })
      expect(edges).toContainEqual({ source: 'IN_PROGRESS', target: 'CLOSED' })
    })

    it('returns empty array for invalid mermaid', () => {
      const edges = extractEdges('')

      expect(edges).toEqual([])
    })

    it('handles multiple edges to same target', () => {
      const mermaid = `
        flowchart TD
        A --> C
        B --> C
      `

      const edges = extractEdges(mermaid)

      expect(edges).toHaveLength(2)
      expect(edges).toContainEqual({ source: 'A', target: 'C' })
      expect(edges).toContainEqual({ source: 'B', target: 'C' })
    })
  })
})
