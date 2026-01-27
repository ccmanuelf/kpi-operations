/**
 * Workflow Validator
 * Client-side validation rules for workflow configurations
 */

import { classifyStatus, STATUS_TYPES, isTerminalStatus, isStartStatus } from './statusClassifier'

/**
 * Validation error/warning severity levels
 */
export const SEVERITY = {
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info'
}

/**
 * Validation rule codes
 */
export const VALIDATION_CODES = {
  NO_ENTRY_POINT: 'NO_ENTRY_POINT',
  NO_TERMINAL_STATUS: 'NO_TERMINAL_STATUS',
  ORPHAN_STATUS: 'ORPHAN_STATUS',
  DEAD_END_STATUS: 'DEAD_END_STATUS',
  SELF_TRANSITION: 'SELF_TRANSITION',
  EMPTY_WORKFLOW: 'EMPTY_WORKFLOW',
  UNREACHABLE_TERMINAL: 'UNREACHABLE_TERMINAL',
  MISSING_HOLD_RESUME: 'MISSING_HOLD_RESUME',
  DUPLICATE_STATUS: 'DUPLICATE_STATUS',
  INVALID_STATUS_NAME: 'INVALID_STATUS_NAME'
}

/**
 * Validate a workflow configuration
 * @param {Object} config - Workflow configuration { statuses, transitions, closure_trigger }
 * @returns {Object} Validation result { isValid, errors, warnings }
 */
export function validateWorkflow(config) {
  const errors = []
  const warnings = []

  if (!config) {
    errors.push({
      code: VALIDATION_CODES.EMPTY_WORKFLOW,
      message: 'Workflow configuration is empty',
      severity: SEVERITY.ERROR
    })
    return { isValid: false, errors, warnings }
  }

  const { statuses = [], transitions = {} } = config

  // Check for empty workflow
  if (statuses.length === 0) {
    errors.push({
      code: VALIDATION_CODES.EMPTY_WORKFLOW,
      message: 'Workflow has no statuses defined',
      severity: SEVERITY.ERROR
    })
    return { isValid: false, errors, warnings }
  }

  // Check for duplicate statuses
  const duplicates = findDuplicates(statuses)
  if (duplicates.length > 0) {
    errors.push({
      code: VALIDATION_CODES.DUPLICATE_STATUS,
      message: `Duplicate statuses found: ${duplicates.join(', ')}`,
      severity: SEVERITY.ERROR,
      details: duplicates
    })
  }

  // Check for invalid status names
  statuses.forEach(status => {
    if (!isValidStatusName(status)) {
      errors.push({
        code: VALIDATION_CODES.INVALID_STATUS_NAME,
        message: `Invalid status name: "${status}". Use uppercase letters and underscores only.`,
        severity: SEVERITY.ERROR,
        details: { status }
      })
    }
  })

  // Check for entry point (RECEIVED)
  const hasEntryPoint = statuses.some(s => isStartStatus(s))
  if (!hasEntryPoint) {
    errors.push({
      code: VALIDATION_CODES.NO_ENTRY_POINT,
      message: 'Workflow must have a RECEIVED status as entry point',
      severity: SEVERITY.ERROR
    })
  }

  // Check for at least one terminal status
  const terminalStatuses = statuses.filter(s => isTerminalStatus(s))
  if (terminalStatuses.length === 0) {
    errors.push({
      code: VALIDATION_CODES.NO_TERMINAL_STATUS,
      message: 'Workflow must have at least one terminal status (CLOSED, CANCELLED, or REJECTED)',
      severity: SEVERITY.ERROR
    })
  }

  // Build reachability graph
  const reachable = findReachableStatuses(statuses, transitions)

  // Check for orphan statuses (not reachable from RECEIVED)
  statuses.forEach(status => {
    if (!isStartStatus(status) && !reachable.has(status)) {
      warnings.push({
        code: VALIDATION_CODES.ORPHAN_STATUS,
        message: `Status "${status}" is not reachable from RECEIVED`,
        severity: SEVERITY.WARNING,
        details: { status }
      })
    }
  })

  // Check for dead-end statuses (non-terminal with no outgoing transitions)
  statuses.forEach(status => {
    if (!isTerminalStatus(status)) {
      const hasOutgoing = Object.keys(transitions).some(target =>
        transitions[target].includes(status)
      )

      if (!hasOutgoing) {
        const statusType = classifyStatus(status)
        // Hold statuses without outgoing are still warnings
        if (statusType !== STATUS_TYPES.HOLD) {
          warnings.push({
            code: VALIDATION_CODES.DEAD_END_STATUS,
            message: `Status "${status}" has no outgoing transitions (dead end)`,
            severity: SEVERITY.WARNING,
            details: { status }
          })
        }
      }
    }
  })

  // Check for self-transitions
  Object.entries(transitions).forEach(([target, sources]) => {
    if (sources.includes(target)) {
      warnings.push({
        code: VALIDATION_CODES.SELF_TRANSITION,
        message: `Status "${target}" has a self-transition`,
        severity: SEVERITY.WARNING,
        details: { status: target }
      })
    }
  })

  // Check that terminal statuses are reachable
  terminalStatuses.forEach(terminal => {
    if (!reachable.has(terminal)) {
      warnings.push({
        code: VALIDATION_CODES.UNREACHABLE_TERMINAL,
        message: `Terminal status "${terminal}" is not reachable from RECEIVED`,
        severity: SEVERITY.WARNING,
        details: { status: terminal }
      })
    }
  })

  // Check hold statuses have resume path
  const holdStatuses = statuses.filter(s => classifyStatus(s) === STATUS_TYPES.HOLD)
  holdStatuses.forEach(holdStatus => {
    const canResume = Object.keys(transitions).some(target =>
      transitions[target].includes(holdStatus) && !isTerminalStatus(target)
    )

    if (!canResume) {
      warnings.push({
        code: VALIDATION_CODES.MISSING_HOLD_RESUME,
        message: `Hold status "${holdStatus}" has no resume path to continue workflow`,
        severity: SEVERITY.WARNING,
        details: { status: holdStatus }
      })
    }
  })

  return {
    isValid: errors.length === 0,
    errors,
    warnings
  }
}

/**
 * Find all statuses reachable from the start status
 * @param {string[]} statuses - All statuses
 * @param {Object} transitions - Transition map { target: [sources] }
 * @returns {Set} Set of reachable status names
 */
function findReachableStatuses(statuses, transitions) {
  const reachable = new Set()
  const startStatus = statuses.find(s => isStartStatus(s))

  if (!startStatus) {
    return reachable
  }

  // BFS from start status
  const queue = [startStatus]
  reachable.add(startStatus)

  // Convert transitions to outgoing format for easier traversal
  const outgoing = {}
  statuses.forEach(s => { outgoing[s] = [] })

  Object.entries(transitions).forEach(([target, sources]) => {
    sources.forEach(source => {
      if (outgoing[source]) {
        outgoing[source].push(target)
      }
    })
  })

  while (queue.length > 0) {
    const current = queue.shift()
    const targets = outgoing[current] || []

    targets.forEach(target => {
      if (!reachable.has(target)) {
        reachable.add(target)
        queue.push(target)
      }
    })
  }

  return reachable
}

/**
 * Find duplicates in an array
 * @param {string[]} arr - Array to check
 * @returns {string[]} Array of duplicate values
 */
function findDuplicates(arr) {
  const seen = new Set()
  const duplicates = new Set()

  arr.forEach(item => {
    if (seen.has(item)) {
      duplicates.add(item)
    }
    seen.add(item)
  })

  return Array.from(duplicates)
}

/**
 * Validate a status name
 * @param {string} name - Status name
 * @returns {boolean} True if valid
 */
function isValidStatusName(name) {
  if (!name || typeof name !== 'string') return false
  // Allow uppercase letters, numbers, and underscores
  return /^[A-Z][A-Z0-9_]*$/.test(name)
}

/**
 * Get validation message for a code
 * @param {string} code - Validation code
 * @returns {string} Human-readable message
 */
export function getValidationMessage(code) {
  const messages = {
    [VALIDATION_CODES.NO_ENTRY_POINT]: 'Add RECEIVED status as the workflow entry point',
    [VALIDATION_CODES.NO_TERMINAL_STATUS]: 'Add at least one terminal status (CLOSED, CANCELLED, or REJECTED)',
    [VALIDATION_CODES.ORPHAN_STATUS]: 'Connect this status to the workflow or remove it',
    [VALIDATION_CODES.DEAD_END_STATUS]: 'Add an outgoing transition or mark as terminal',
    [VALIDATION_CODES.SELF_TRANSITION]: 'Self-transitions are usually not recommended',
    [VALIDATION_CODES.EMPTY_WORKFLOW]: 'Add statuses to define the workflow',
    [VALIDATION_CODES.UNREACHABLE_TERMINAL]: 'This terminal status cannot be reached from the start',
    [VALIDATION_CODES.MISSING_HOLD_RESUME]: 'Add a resume path from this hold status',
    [VALIDATION_CODES.DUPLICATE_STATUS]: 'Remove duplicate status definitions',
    [VALIDATION_CODES.INVALID_STATUS_NAME]: 'Use uppercase letters and underscores for status names'
  }

  return messages[code] || 'Unknown validation issue'
}

export default {
  validateWorkflow,
  SEVERITY,
  VALIDATION_CODES,
  getValidationMessage
}
