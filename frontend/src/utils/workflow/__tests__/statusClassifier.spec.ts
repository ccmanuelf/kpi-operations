/**
 * Unit tests for Status Classifier
 * Tests status type classification, styling, and Mermaid shape generation
 */
import { describe, it, expect } from 'vitest'
import {
  STATUS_TYPES,
  classifyStatus,
  isTerminalStatus,
  isStartStatus,
  isHoldStatus,
  isOptionalStatus,
  getStatusTypeStyle,
  getMermaidShape,
  getMermaidClassName
} from '../statusClassifier'

describe('Status Classifier', () => {
  describe('STATUS_TYPES constants', () => {
    it('defines all required status types', () => {
      expect(STATUS_TYPES.START).toBe('start')
      expect(STATUS_TYPES.NORMAL).toBe('normal')
      expect(STATUS_TYPES.TERMINAL).toBe('terminal')
      expect(STATUS_TYPES.HOLD).toBe('hold')
      expect(STATUS_TYPES.OPTIONAL).toBe('optional')
    })
  })

  describe('classifyStatus', () => {
    it('classifies RECEIVED as start', () => {
      expect(classifyStatus('RECEIVED')).toBe(STATUS_TYPES.START)
    })

    it('classifies terminal statuses', () => {
      expect(classifyStatus('CLOSED')).toBe(STATUS_TYPES.TERMINAL)
      expect(classifyStatus('CANCELLED')).toBe(STATUS_TYPES.TERMINAL)
      expect(classifyStatus('REJECTED')).toBe(STATUS_TYPES.TERMINAL)
    })

    it('classifies hold statuses', () => {
      expect(classifyStatus('ON_HOLD')).toBe(STATUS_TYPES.HOLD)
      expect(classifyStatus('HOLD')).toBe(STATUS_TYPES.HOLD)
      expect(classifyStatus('PAUSED')).toBe(STATUS_TYPES.HOLD)
    })

    it('classifies optional statuses', () => {
      expect(classifyStatus('SHIPPED')).toBe(STATUS_TYPES.OPTIONAL)
      expect(classifyStatus('DEMOTED')).toBe(STATUS_TYPES.OPTIONAL)
      expect(classifyStatus('REWORK')).toBe(STATUS_TYPES.OPTIONAL)
    })

    it('classifies normal flow statuses', () => {
      expect(classifyStatus('DISPATCHED')).toBe(STATUS_TYPES.NORMAL)
      expect(classifyStatus('IN_WIP')).toBe(STATUS_TYPES.NORMAL)
      expect(classifyStatus('IN_PROGRESS')).toBe(STATUS_TYPES.NORMAL)
      expect(classifyStatus('COMPLETED')).toBe(STATUS_TYPES.NORMAL)
      expect(classifyStatus('READY')).toBe(STATUS_TYPES.NORMAL)
      expect(classifyStatus('PENDING')).toBe(STATUS_TYPES.NORMAL)
      expect(classifyStatus('APPROVED')).toBe(STATUS_TYPES.NORMAL)
    })

    it('defaults unknown statuses to normal', () => {
      expect(classifyStatus('CUSTOM_STATUS')).toBe(STATUS_TYPES.NORMAL)
      expect(classifyStatus('UNKNOWN')).toBe(STATUS_TYPES.NORMAL)
      expect(classifyStatus('MY_NEW_STATUS')).toBe(STATUS_TYPES.NORMAL)
    })

    it('handles case-insensitive input', () => {
      expect(classifyStatus('received')).toBe(STATUS_TYPES.START)
      expect(classifyStatus('Closed')).toBe(STATUS_TYPES.TERMINAL)
      expect(classifyStatus('on_hold')).toBe(STATUS_TYPES.HOLD)
    })

    it('normalizes hyphens to underscores', () => {
      expect(classifyStatus('ON-HOLD')).toBe(STATUS_TYPES.HOLD)
      expect(classifyStatus('IN-PROGRESS')).toBe(STATUS_TYPES.NORMAL)
    })

    it('handles null/undefined gracefully', () => {
      expect(classifyStatus(null)).toBe(STATUS_TYPES.NORMAL)
      expect(classifyStatus(undefined)).toBe(STATUS_TYPES.NORMAL)
    })
  })

  describe('isTerminalStatus', () => {
    it('returns true for terminal statuses', () => {
      expect(isTerminalStatus('CLOSED')).toBe(true)
      expect(isTerminalStatus('CANCELLED')).toBe(true)
      expect(isTerminalStatus('REJECTED')).toBe(true)
    })

    it('returns false for non-terminal statuses', () => {
      expect(isTerminalStatus('RECEIVED')).toBe(false)
      expect(isTerminalStatus('IN_PROGRESS')).toBe(false)
      expect(isTerminalStatus('ON_HOLD')).toBe(false)
    })
  })

  describe('isStartStatus', () => {
    it('returns true for RECEIVED', () => {
      expect(isStartStatus('RECEIVED')).toBe(true)
    })

    it('returns false for other statuses', () => {
      expect(isStartStatus('CLOSED')).toBe(false)
      expect(isStartStatus('IN_PROGRESS')).toBe(false)
    })
  })

  describe('isHoldStatus', () => {
    it('returns true for hold statuses', () => {
      expect(isHoldStatus('ON_HOLD')).toBe(true)
      expect(isHoldStatus('HOLD')).toBe(true)
      expect(isHoldStatus('PAUSED')).toBe(true)
    })

    it('returns false for non-hold statuses', () => {
      expect(isHoldStatus('RECEIVED')).toBe(false)
      expect(isHoldStatus('CLOSED')).toBe(false)
    })
  })

  describe('isOptionalStatus', () => {
    it('returns true for optional statuses', () => {
      expect(isOptionalStatus('SHIPPED')).toBe(true)
      expect(isOptionalStatus('DEMOTED')).toBe(true)
      expect(isOptionalStatus('REWORK')).toBe(true)
    })

    it('returns false for non-optional statuses', () => {
      expect(isOptionalStatus('RECEIVED')).toBe(false)
      expect(isOptionalStatus('CLOSED')).toBe(false)
    })
  })

  describe('getStatusTypeStyle', () => {
    it('returns correct style for start type', () => {
      const style = getStatusTypeStyle(STATUS_TYPES.START)
      expect(style.backgroundColor).toBe('#d4edda')
      expect(style.borderColor).toBe('#28a745')
      expect(style.icon).toBe('mdi-play-circle')
    })

    it('returns correct style for normal type', () => {
      const style = getStatusTypeStyle(STATUS_TYPES.NORMAL)
      expect(style.backgroundColor).toBe('#cce5ff')
      expect(style.borderColor).toBe('#007bff')
      expect(style.icon).toBe('mdi-checkbox-blank-circle')
    })

    it('returns correct style for terminal type', () => {
      const style = getStatusTypeStyle(STATUS_TYPES.TERMINAL)
      expect(style.backgroundColor).toBe('#f8d7da')
      expect(style.borderColor).toBe('#dc3545')
      expect(style.icon).toBe('mdi-stop-circle')
    })

    it('returns correct style for hold type', () => {
      const style = getStatusTypeStyle(STATUS_TYPES.HOLD)
      expect(style.backgroundColor).toBe('#fff3cd')
      expect(style.borderColor).toBe('#ffc107')
      expect(style.icon).toBe('mdi-pause-circle')
    })

    it('returns correct style for optional type', () => {
      const style = getStatusTypeStyle(STATUS_TYPES.OPTIONAL)
      expect(style.backgroundColor).toBe('#e2e3e5')
      expect(style.borderColor).toBe('#6c757d')
      expect(style.icon).toBe('mdi-skip-next-circle')
    })

    it('defaults to normal style for unknown type', () => {
      const style = getStatusTypeStyle('unknown')
      expect(style.backgroundColor).toBe('#cce5ff')
    })
  })

  describe('getMermaidShape', () => {
    it('returns stadium shape for start', () => {
      const shape = getMermaidShape(STATUS_TYPES.START)
      expect(shape.open).toBe('([')
      expect(shape.close).toBe('])')
    })

    it('returns rectangle for normal', () => {
      const shape = getMermaidShape(STATUS_TYPES.NORMAL)
      expect(shape.open).toBe('[')
      expect(shape.close).toBe(']')
    })

    it('returns subroutine shape for terminal', () => {
      const shape = getMermaidShape(STATUS_TYPES.TERMINAL)
      expect(shape.open).toBe('[[')
      expect(shape.close).toBe(']]')
    })

    it('returns hexagon for hold', () => {
      const shape = getMermaidShape(STATUS_TYPES.HOLD)
      expect(shape.open).toBe('{{')
      expect(shape.close).toBe('}}')
    })

    it('returns parallelogram for optional', () => {
      const shape = getMermaidShape(STATUS_TYPES.OPTIONAL)
      expect(shape.open).toBe('[/')
      expect(shape.close).toBe('/]')
    })

    it('defaults to rectangle for unknown', () => {
      const shape = getMermaidShape('unknown')
      expect(shape.open).toBe('[')
      expect(shape.close).toBe(']')
    })
  })

  describe('getMermaidClassName', () => {
    it('returns correct class names', () => {
      expect(getMermaidClassName(STATUS_TYPES.START)).toBe('start')
      expect(getMermaidClassName(STATUS_TYPES.NORMAL)).toBe('normal')
      expect(getMermaidClassName(STATUS_TYPES.TERMINAL)).toBe('terminal')
      expect(getMermaidClassName(STATUS_TYPES.HOLD)).toBe('hold')
      expect(getMermaidClassName(STATUS_TYPES.OPTIONAL)).toBe('optional')
    })

    it('defaults to normal for unknown', () => {
      expect(getMermaidClassName('unknown')).toBe('normal')
    })
  })
})
