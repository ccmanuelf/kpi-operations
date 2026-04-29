/**
 * Unit tests for Workflow Validator
 * Tests validation rules for workflow configurations
 */
import { describe, it, expect } from 'vitest'
import {
  validateWorkflow,
  SEVERITY,
  VALIDATION_CODES,
  getValidationMessage
} from '../workflowValidator'

describe('Workflow Validator', () => {
  describe('SEVERITY constants', () => {
    it('defines all severity levels', () => {
      expect(SEVERITY.ERROR).toBe('error')
      expect(SEVERITY.WARNING).toBe('warning')
      expect(SEVERITY.INFO).toBe('info')
    })
  })

  describe('VALIDATION_CODES constants', () => {
    it('defines all validation codes', () => {
      expect(VALIDATION_CODES.NO_ENTRY_POINT).toBe('NO_ENTRY_POINT')
      expect(VALIDATION_CODES.NO_TERMINAL_STATUS).toBe('NO_TERMINAL_STATUS')
      expect(VALIDATION_CODES.ORPHAN_STATUS).toBe('ORPHAN_STATUS')
      expect(VALIDATION_CODES.DEAD_END_STATUS).toBe('DEAD_END_STATUS')
      expect(VALIDATION_CODES.SELF_TRANSITION).toBe('SELF_TRANSITION')
      expect(VALIDATION_CODES.EMPTY_WORKFLOW).toBe('EMPTY_WORKFLOW')
    })
  })

  describe('validateWorkflow', () => {
    describe('valid workflows', () => {
      it('validates a simple valid workflow', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            COMPLETED: ['IN_PROGRESS'],
            CLOSED: ['COMPLETED']
          }
        }

        const result = validateWorkflow(config)

        expect(result.isValid).toBe(true)
        expect(result.errors).toHaveLength(0)
      })

      it('validates workflow with multiple terminal statuses', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED', 'CANCELLED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            CLOSED: ['IN_PROGRESS'],
            CANCELLED: ['RECEIVED', 'IN_PROGRESS']
          }
        }

        const result = validateWorkflow(config)

        expect(result.isValid).toBe(true)
      })

      it('validates workflow with hold status', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED', 'ON_HOLD'],
            ON_HOLD: ['IN_PROGRESS'],
            COMPLETED: ['IN_PROGRESS'],
            CLOSED: ['COMPLETED']
          }
        }

        const result = validateWorkflow(config)

        expect(result.isValid).toBe(true)
      })
    })

    describe('empty/null config', () => {
      it('returns error for null config', () => {
        const result = validateWorkflow(null)

        expect(result.isValid).toBe(false)
        expect(result.errors).toHaveLength(1)
        expect(result.errors[0].code).toBe(VALIDATION_CODES.EMPTY_WORKFLOW)
      })

      it('returns error for config with empty statuses', () => {
        const result = validateWorkflow({ statuses: [], transitions: {} })

        expect(result.isValid).toBe(false)
        expect(result.errors.some(e => e.code === VALIDATION_CODES.EMPTY_WORKFLOW)).toBe(true)
      })
    })

    describe('entry point validation', () => {
      it('returns error when no RECEIVED status', () => {
        const config = {
          statuses: ['IN_PROGRESS', 'COMPLETED', 'CLOSED'],
          transitions: {
            COMPLETED: ['IN_PROGRESS'],
            CLOSED: ['COMPLETED']
          }
        }

        const result = validateWorkflow(config)

        expect(result.isValid).toBe(false)
        expect(result.errors.some(e => e.code === VALIDATION_CODES.NO_ENTRY_POINT)).toBe(true)
      })
    })

    describe('terminal status validation', () => {
      it('returns error when no terminal status', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'COMPLETED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            COMPLETED: ['IN_PROGRESS']
          }
        }

        const result = validateWorkflow(config)

        expect(result.isValid).toBe(false)
        expect(result.errors.some(e => e.code === VALIDATION_CODES.NO_TERMINAL_STATUS)).toBe(true)
      })
    })

    describe('duplicate status validation', () => {
      it('returns error for duplicate statuses', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'IN_PROGRESS', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            CLOSED: ['IN_PROGRESS']
          }
        }

        const result = validateWorkflow(config)

        expect(result.isValid).toBe(false)
        expect(result.errors.some(e => e.code === VALIDATION_CODES.DUPLICATE_STATUS)).toBe(true)
      })
    })

    describe('invalid status name validation', () => {
      it('returns error for lowercase status names', () => {
        const config = {
          statuses: ['RECEIVED', 'inProgress', 'CLOSED'],
          transitions: {
            inProgress: ['RECEIVED'],
            CLOSED: ['inProgress']
          }
        }

        const result = validateWorkflow(config)

        expect(result.isValid).toBe(false)
        expect(result.errors.some(e => e.code === VALIDATION_CODES.INVALID_STATUS_NAME)).toBe(true)
      })

      it('allows underscores in status names', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'QUALITY_CHECK', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            QUALITY_CHECK: ['IN_PROGRESS'],
            CLOSED: ['QUALITY_CHECK']
          }
        }

        const result = validateWorkflow(config)

        expect(result.errors.filter(e => e.code === VALIDATION_CODES.INVALID_STATUS_NAME)).toHaveLength(0)
      })

      it('allows numbers in status names', () => {
        const config = {
          statuses: ['RECEIVED', 'STAGE1', 'STAGE2', 'CLOSED'],
          transitions: {
            STAGE1: ['RECEIVED'],
            STAGE2: ['STAGE1'],
            CLOSED: ['STAGE2']
          }
        }

        const result = validateWorkflow(config)

        expect(result.errors.filter(e => e.code === VALIDATION_CODES.INVALID_STATUS_NAME)).toHaveLength(0)
      })
    })

    describe('orphan status warnings', () => {
      it('warns about unreachable statuses', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'ORPHAN', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            CLOSED: ['IN_PROGRESS']
            // ORPHAN has no incoming transitions
          }
        }

        const result = validateWorkflow(config)

        expect(result.warnings.some(w =>
          w.code === VALIDATION_CODES.ORPHAN_STATUS &&
          w.details.status === 'ORPHAN'
        )).toBe(true)
      })
    })

    describe('dead-end status warnings', () => {
      it('warns about non-terminal statuses without outgoing transitions', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'DEAD_END', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            DEAD_END: ['IN_PROGRESS'],
            CLOSED: ['IN_PROGRESS']
            // DEAD_END has no outgoing transitions
          }
        }

        const result = validateWorkflow(config)

        expect(result.warnings.some(w =>
          w.code === VALIDATION_CODES.DEAD_END_STATUS &&
          w.details.status === 'DEAD_END'
        )).toBe(true)
      })

      it('does not warn about terminal statuses without outgoing', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            CLOSED: ['IN_PROGRESS']
          }
        }

        const result = validateWorkflow(config)

        expect(result.warnings.filter(w =>
          w.code === VALIDATION_CODES.DEAD_END_STATUS
        )).toHaveLength(0)
      })
    })

    describe('self-transition warnings', () => {
      it('warns about self-transitions', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED', 'IN_PROGRESS'], // Self-transition
            CLOSED: ['IN_PROGRESS']
          }
        }

        const result = validateWorkflow(config)

        expect(result.warnings.some(w =>
          w.code === VALIDATION_CODES.SELF_TRANSITION &&
          w.details.status === 'IN_PROGRESS'
        )).toBe(true)
      })
    })

    describe('unreachable terminal warnings', () => {
      it('warns when terminal status is unreachable', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'CLOSED', 'REJECTED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            CLOSED: ['IN_PROGRESS']
            // REJECTED has no incoming transitions
          }
        }

        const result = validateWorkflow(config)

        expect(result.warnings.some(w =>
          w.code === VALIDATION_CODES.UNREACHABLE_TERMINAL &&
          w.details.status === 'REJECTED'
        )).toBe(true)
      })
    })

    describe('hold status resume path', () => {
      it('warns when hold status has no resume path', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'ON_HOLD', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED'],
            ON_HOLD: ['IN_PROGRESS'],
            CLOSED: ['IN_PROGRESS']
            // ON_HOLD can go to nothing (only to terminal)
          }
        }

        const result = validateWorkflow(config)

        expect(result.warnings.some(w =>
          w.code === VALIDATION_CODES.MISSING_HOLD_RESUME
        )).toBe(true)
      })

      it('does not warn when hold status can resume', () => {
        const config = {
          statuses: ['RECEIVED', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CLOSED'],
          transitions: {
            IN_PROGRESS: ['RECEIVED', 'ON_HOLD'], // Can resume from ON_HOLD
            ON_HOLD: ['IN_PROGRESS'],
            COMPLETED: ['IN_PROGRESS'],
            CLOSED: ['COMPLETED']
          }
        }

        const result = validateWorkflow(config)

        expect(result.warnings.filter(w =>
          w.code === VALIDATION_CODES.MISSING_HOLD_RESUME
        )).toHaveLength(0)
      })
    })
  })

  describe('getValidationMessage', () => {
    it('returns correct message for NO_ENTRY_POINT', () => {
      const message = getValidationMessage(VALIDATION_CODES.NO_ENTRY_POINT)
      expect(message).toContain('RECEIVED')
    })

    it('returns correct message for NO_TERMINAL_STATUS', () => {
      const message = getValidationMessage(VALIDATION_CODES.NO_TERMINAL_STATUS)
      expect(message).toContain('terminal')
    })

    it('returns fallback for unknown code', () => {
      const message = getValidationMessage('UNKNOWN_CODE')
      expect(message).toBe('Unknown validation issue')
    })
  })
})
