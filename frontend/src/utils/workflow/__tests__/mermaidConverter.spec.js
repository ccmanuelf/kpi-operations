/**
 * Unit tests for Mermaid Converter
 * Tests bidirectional conversion between workflow config, Vue Flow, and Mermaid
 */
import { describe, it, expect } from 'vitest'
import {
  configToVueFlow,
  vueFlowToConfig,
  configToMermaid,
  mermaidToConfig,
  mermaidToVueFlow,
  vueFlowToMermaid,
  syncConfigToVueFlow,
  validateMermaidChange,
  diffConfigs
} from '../mermaidConverter'

describe('Mermaid Converter', () => {
  describe('configToVueFlow', () => {
    it('converts simple config to Vue Flow format', () => {
      const config = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          CLOSED: ['IN_PROGRESS']
        }
      }

      const { nodes, edges } = configToVueFlow(config)

      expect(nodes).toHaveLength(3)
      expect(edges).toHaveLength(2)
    })

    it('creates correct node structure', () => {
      const config = {
        statuses: ['RECEIVED'],
        transitions: {}
      }

      const { nodes } = configToVueFlow(config)

      expect(nodes[0].id).toBe('RECEIVED')
      expect(nodes[0].type).toBe('workflowState')
      expect(nodes[0].position).toHaveProperty('x')
      expect(nodes[0].position).toHaveProperty('y')
      expect(nodes[0].data.label).toBe('RECEIVED')
      expect(nodes[0].data.statusType).toBe('start')
    })

    it('creates correct edge structure', () => {
      const config = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: {
          CLOSED: ['RECEIVED']
        }
      }

      const { edges } = configToVueFlow(config)

      expect(edges[0].id).toBe('RECEIVED-CLOSED')
      expect(edges[0].source).toBe('RECEIVED')
      expect(edges[0].target).toBe('CLOSED')
      expect(edges[0].type).toBe('workflowTransition')
    })

    it('assigns correct status types to nodes', () => {
      const config = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'ON_HOLD', 'CLOSED'],
        transitions: {}
      }

      const { nodes } = configToVueFlow(config)

      const findNode = (id) => nodes.find(n => n.id === id)

      expect(findNode('RECEIVED').data.statusType).toBe('start')
      expect(findNode('IN_PROGRESS').data.statusType).toBe('normal')
      expect(findNode('ON_HOLD').data.statusType).toBe('hold')
      expect(findNode('CLOSED').data.statusType).toBe('terminal')
    })

    it('returns empty arrays for null config', () => {
      const { nodes, edges } = configToVueFlow(null)

      expect(nodes).toEqual([])
      expect(edges).toEqual([])
    })

    it('returns empty arrays for config without statuses', () => {
      const { nodes, edges } = configToVueFlow({ transitions: {} })

      expect(nodes).toEqual([])
      expect(edges).toEqual([])
    })

    it('ignores transitions to non-existent statuses', () => {
      const config = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: {
          CLOSED: ['RECEIVED'],
          NON_EXISTENT: ['RECEIVED']
        }
      }

      const { edges } = configToVueFlow(config)

      expect(edges).toHaveLength(1)
    })

    it('arranges nodes in grid layout', () => {
      const config = {
        statuses: ['S1', 'S2', 'S3', 'S4', 'S5'],
        transitions: {}
      }

      const { nodes } = configToVueFlow(config)

      // Check that positions are assigned
      nodes.forEach(node => {
        expect(node.position.x).toBeGreaterThanOrEqual(0)
        expect(node.position.y).toBeGreaterThanOrEqual(0)
      })

      // Check that not all nodes have the same position
      const positions = nodes.map(n => `${n.position.x},${n.position.y}`)
      const uniquePositions = new Set(positions)
      expect(uniquePositions.size).toBe(5)
    })
  })

  describe('vueFlowToConfig', () => {
    it('converts Vue Flow format to config', () => {
      const nodes = [
        { id: 'RECEIVED', data: {} },
        { id: 'IN_PROGRESS', data: {} },
        { id: 'CLOSED', data: {} }
      ]
      const edges = [
        { source: 'RECEIVED', target: 'IN_PROGRESS' },
        { source: 'IN_PROGRESS', target: 'CLOSED' }
      ]

      const config = vueFlowToConfig(nodes, edges)

      expect(config.statuses).toContain('RECEIVED')
      expect(config.statuses).toContain('IN_PROGRESS')
      expect(config.statuses).toContain('CLOSED')
      expect(config.transitions.IN_PROGRESS).toContain('RECEIVED')
      expect(config.transitions.CLOSED).toContain('IN_PROGRESS')
    })

    it('puts RECEIVED first in status list', () => {
      const nodes = [
        { id: 'CLOSED', data: {} },
        { id: 'IN_PROGRESS', data: {} },
        { id: 'RECEIVED', data: {} }
      ]
      const edges = []

      const config = vueFlowToConfig(nodes, edges)

      expect(config.statuses[0]).toBe('RECEIVED')
    })

    it('uses provided closure trigger', () => {
      const nodes = [{ id: 'RECEIVED', data: {} }]
      const edges = []

      const config = vueFlowToConfig(nodes, edges, 'at_completion')

      expect(config.closure_trigger).toBe('at_completion')
    })

    it('defaults to at_shipment closure trigger', () => {
      const nodes = [{ id: 'RECEIVED', data: {} }]
      const edges = []

      const config = vueFlowToConfig(nodes, edges)

      expect(config.closure_trigger).toBe('at_shipment')
    })

    it('handles multiple edges to same target', () => {
      const nodes = [
        { id: 'A', data: {} },
        { id: 'B', data: {} },
        { id: 'TARGET', data: {} }
      ]
      const edges = [
        { source: 'A', target: 'TARGET' },
        { source: 'B', target: 'TARGET' }
      ]

      const config = vueFlowToConfig(nodes, edges)

      expect(config.transitions.TARGET).toHaveLength(2)
      expect(config.transitions.TARGET).toContain('A')
      expect(config.transitions.TARGET).toContain('B')
    })

    it('does not duplicate sources in transitions', () => {
      const nodes = [
        { id: 'A', data: {} },
        { id: 'B', data: {} }
      ]
      const edges = [
        { source: 'A', target: 'B' },
        { source: 'A', target: 'B' } // Duplicate
      ]

      const config = vueFlowToConfig(nodes, edges)

      expect(config.transitions.B).toHaveLength(1)
    })
  })

  describe('configToMermaid', () => {
    it('generates Mermaid code from config', () => {
      const config = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: { CLOSED: ['RECEIVED'] }
      }

      const mermaid = configToMermaid(config)

      expect(mermaid).toContain('flowchart TD')
      expect(mermaid).toContain('RECEIVED')
      expect(mermaid).toContain('CLOSED')
      expect(mermaid).toContain('-->')
    })
  })

  describe('mermaidToConfig', () => {
    it('parses Mermaid code to config', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> IN_PROGRESS
        IN_PROGRESS --> CLOSED
      `

      const config = mermaidToConfig(mermaid)

      expect(config.statuses).toContain('RECEIVED')
      expect(config.statuses).toContain('IN_PROGRESS')
      expect(config.statuses).toContain('CLOSED')
      expect(config.transitions.IN_PROGRESS).toContain('RECEIVED')
    })

    it('throws error for invalid Mermaid syntax', () => {
      const invalidMermaid = 'not valid mermaid'

      expect(() => mermaidToConfig(invalidMermaid)).toThrow()
    })
  })

  describe('mermaidToVueFlow', () => {
    it('converts Mermaid directly to Vue Flow', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> CLOSED
      `

      const { nodes, edges } = mermaidToVueFlow(mermaid)

      expect(nodes).toHaveLength(2)
      expect(edges).toHaveLength(1)
    })

    it('returns empty arrays for invalid Mermaid', () => {
      const { nodes, edges } = mermaidToVueFlow('')

      expect(nodes).toEqual([])
      expect(edges).toEqual([])
    })
  })

  describe('vueFlowToMermaid', () => {
    it('converts Vue Flow directly to Mermaid', () => {
      const nodes = [
        { id: 'RECEIVED', data: {} },
        { id: 'CLOSED', data: {} }
      ]
      const edges = [
        { source: 'RECEIVED', target: 'CLOSED' }
      ]

      const mermaid = vueFlowToMermaid(nodes, edges)

      expect(mermaid).toContain('flowchart TD')
      expect(mermaid).toContain('RECEIVED')
      expect(mermaid).toContain('CLOSED')
    })
  })

  describe('syncConfigToVueFlow', () => {
    it('preserves positions from existing nodes', () => {
      const newConfig = {
        statuses: ['RECEIVED', 'IN_PROGRESS'],
        transitions: { IN_PROGRESS: ['RECEIVED'] }
      }
      const existingNodes = [
        { id: 'RECEIVED', position: { x: 100, y: 200 } }
      ]

      const { nodes } = syncConfigToVueFlow(newConfig, existingNodes)

      const receivedNode = nodes.find(n => n.id === 'RECEIVED')
      expect(receivedNode.position.x).toBe(100)
      expect(receivedNode.position.y).toBe(200)
    })

    it('assigns new positions for new nodes', () => {
      const newConfig = {
        statuses: ['RECEIVED', 'NEW_STATUS'],
        transitions: {}
      }
      const existingNodes = [
        { id: 'RECEIVED', position: { x: 100, y: 200 } }
      ]

      const { nodes } = syncConfigToVueFlow(newConfig, existingNodes)

      const newNode = nodes.find(n => n.id === 'NEW_STATUS')
      expect(newNode.position).toBeDefined()
      expect(newNode.position.x).toBeGreaterThanOrEqual(0)
    })
  })

  describe('validateMermaidChange', () => {
    it('validates correct Mermaid code', () => {
      const mermaid = `
        flowchart TD
        RECEIVED --> CLOSED
      `

      const result = validateMermaidChange(mermaid)

      expect(result.isValid).toBe(true)
      expect(result.config).not.toBeNull()
      expect(result.errors).toHaveLength(0)
    })

    it('returns errors for invalid Mermaid', () => {
      const mermaid = 'invalid mermaid'

      const result = validateMermaidChange(mermaid)

      expect(result.isValid).toBe(false)
      expect(result.errors.length).toBeGreaterThan(0)
    })

    it('handles syntax errors gracefully', () => {
      const mermaid = `
        flowchart TD
        RECEIVED([unbalanced
      `

      const result = validateMermaidChange(mermaid)

      expect(result.isValid).toBe(false)
    })
  })

  describe('diffConfigs', () => {
    it('detects added statuses', () => {
      const configA = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: {}
      }
      const configB = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
        transitions: {}
      }

      const diff = diffConfigs(configA, configB)

      expect(diff.addedStatuses).toContain('IN_PROGRESS')
      expect(diff.hasChanges).toBe(true)
    })

    it('detects removed statuses', () => {
      const configA = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
        transitions: {}
      }
      const configB = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: {}
      }

      const diff = diffConfigs(configA, configB)

      expect(diff.removedStatuses).toContain('IN_PROGRESS')
      expect(diff.hasChanges).toBe(true)
    })

    it('detects added edges', () => {
      const configA = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          CLOSED: ['IN_PROGRESS']
        }
      }
      const configB = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          CLOSED: ['IN_PROGRESS', 'RECEIVED'] // Added edge
        }
      }

      const diff = diffConfigs(configA, configB)

      expect(diff.addedEdges).toContainEqual({ source: 'RECEIVED', target: 'CLOSED' })
      expect(diff.hasChanges).toBe(true)
    })

    it('detects removed edges', () => {
      const configA = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          CLOSED: ['IN_PROGRESS']
        }
      }
      const configB = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED']
          // CLOSED edge removed
        }
      }

      const diff = diffConfigs(configA, configB)

      expect(diff.removedEdges).toContainEqual({ source: 'IN_PROGRESS', target: 'CLOSED' })
      expect(diff.hasChanges).toBe(true)
    })

    it('returns no changes for identical configs', () => {
      const config = {
        statuses: ['RECEIVED', 'CLOSED'],
        transitions: { CLOSED: ['RECEIVED'] }
      }

      const diff = diffConfigs(config, config)

      expect(diff.hasChanges).toBe(false)
      expect(diff.addedStatuses).toHaveLength(0)
      expect(diff.removedStatuses).toHaveLength(0)
      expect(diff.addedEdges).toHaveLength(0)
      expect(diff.removedEdges).toHaveLength(0)
    })

    it('handles null configs', () => {
      const diff = diffConfigs(null, null)

      expect(diff.hasChanges).toBe(false)
    })
  })

  describe('round-trip conversion', () => {
    it('preserves config through config -> VueFlow -> config', () => {
      const originalConfig = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          COMPLETED: ['IN_PROGRESS'],
          CLOSED: ['COMPLETED']
        }
      }

      const { nodes, edges } = configToVueFlow(originalConfig)
      const resultConfig = vueFlowToConfig(nodes, edges)

      expect(new Set(resultConfig.statuses)).toEqual(new Set(originalConfig.statuses))
      expect(resultConfig.transitions.IN_PROGRESS).toEqual(originalConfig.transitions.IN_PROGRESS)
      expect(resultConfig.transitions.COMPLETED).toEqual(originalConfig.transitions.COMPLETED)
      expect(resultConfig.transitions.CLOSED).toEqual(originalConfig.transitions.CLOSED)
    })

    it('preserves config through config -> Mermaid -> config', () => {
      const originalConfig = {
        statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
        transitions: {
          IN_PROGRESS: ['RECEIVED'],
          CLOSED: ['IN_PROGRESS']
        }
      }

      const mermaid = configToMermaid(originalConfig)
      const resultConfig = mermaidToConfig(mermaid)

      expect(new Set(resultConfig.statuses)).toEqual(new Set(originalConfig.statuses))
      expect(resultConfig.transitions.IN_PROGRESS).toEqual(originalConfig.transitions.IN_PROGRESS)
      expect(resultConfig.transitions.CLOSED).toEqual(originalConfig.transitions.CLOSED)
    })
  })
})
