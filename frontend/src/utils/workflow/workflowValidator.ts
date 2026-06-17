/**
 * Workflow validator — client-side rule checks for workflow
 * configurations.
 */

import { classifyStatus, STATUS_TYPES, isTerminalStatus, isStartStatus } from './statusClassifier'
import type { WorkflowConfig } from './types'
import i18n from '@/i18n'

export const SEVERITY = {
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
} as const

export type Severity = (typeof SEVERITY)[keyof typeof SEVERITY]

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
  INVALID_STATUS_NAME: 'INVALID_STATUS_NAME',
} as const

export type ValidationCode = (typeof VALIDATION_CODES)[keyof typeof VALIDATION_CODES]

export interface ValidationIssue {
  code: ValidationCode
  message: string
  severity: Severity
  details?: unknown
}

export interface ValidationResult {
  isValid: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
}

export function validateWorkflow(
  config: WorkflowConfig | null | undefined,
): ValidationResult {
  const errors: ValidationIssue[] = []
  const warnings: ValidationIssue[] = []

  if (!config) {
    errors.push({
      code: VALIDATION_CODES.EMPTY_WORKFLOW,
      message: i18n.global.t('workflow.validation.configEmpty'),
      severity: SEVERITY.ERROR,
    })
    return { isValid: false, errors, warnings }
  }

  const { statuses = [], transitions = {} } = config

  if (statuses.length === 0) {
    errors.push({
      code: VALIDATION_CODES.EMPTY_WORKFLOW,
      message: i18n.global.t('workflow.validation.noStatuses'),
      severity: SEVERITY.ERROR,
    })
    return { isValid: false, errors, warnings }
  }

  const duplicates = findDuplicates(statuses)
  if (duplicates.length > 0) {
    errors.push({
      code: VALIDATION_CODES.DUPLICATE_STATUS,
      message: i18n.global.t('workflow.validation.duplicateStatuses', { statuses: duplicates.join(', ') }),
      severity: SEVERITY.ERROR,
      details: duplicates,
    })
  }

  statuses.forEach((status) => {
    if (!isValidStatusName(status)) {
      errors.push({
        code: VALIDATION_CODES.INVALID_STATUS_NAME,
        message: i18n.global.t('workflow.validation.invalidStatusName', { status }),
        severity: SEVERITY.ERROR,
        details: { status },
      })
    }
  })

  const hasEntryPoint = statuses.some((s) => isStartStatus(s))
  if (!hasEntryPoint) {
    errors.push({
      code: VALIDATION_CODES.NO_ENTRY_POINT,
      message: i18n.global.t('workflow.validation.noEntryPoint'),
      severity: SEVERITY.ERROR,
    })
  }

  const terminalStatuses = statuses.filter((s) => isTerminalStatus(s))
  if (terminalStatuses.length === 0) {
    errors.push({
      code: VALIDATION_CODES.NO_TERMINAL_STATUS,
      message: i18n.global.t('workflow.validation.noTerminalStatus'),
      severity: SEVERITY.ERROR,
    })
  }

  const reachable = findReachableStatuses(statuses, transitions)

  statuses.forEach((status) => {
    if (!isStartStatus(status) && !reachable.has(status)) {
      warnings.push({
        code: VALIDATION_CODES.ORPHAN_STATUS,
        message: i18n.global.t('workflow.validation.orphanStatus', { status }),
        severity: SEVERITY.WARNING,
        details: { status },
      })
    }
  })

  statuses.forEach((status) => {
    if (!isTerminalStatus(status)) {
      const hasOutgoing = Object.keys(transitions).some((target) =>
        transitions[target].includes(status),
      )

      if (!hasOutgoing) {
        const statusType = classifyStatus(status)
        if (statusType !== STATUS_TYPES.HOLD) {
          warnings.push({
            code: VALIDATION_CODES.DEAD_END_STATUS,
            message: i18n.global.t('workflow.validation.deadEndStatus', { status }),
            severity: SEVERITY.WARNING,
            details: { status },
          })
        }
      }
    }
  })

  Object.entries(transitions).forEach(([target, sources]) => {
    if (sources.includes(target)) {
      warnings.push({
        code: VALIDATION_CODES.SELF_TRANSITION,
        message: i18n.global.t('workflow.validation.selfTransition', { status: target }),
        severity: SEVERITY.WARNING,
        details: { status: target },
      })
    }
  })

  terminalStatuses.forEach((terminal) => {
    if (!reachable.has(terminal)) {
      warnings.push({
        code: VALIDATION_CODES.UNREACHABLE_TERMINAL,
        message: i18n.global.t('workflow.validation.unreachableTerminal', { status: terminal }),
        severity: SEVERITY.WARNING,
        details: { status: terminal },
      })
    }
  })

  const holdStatuses = statuses.filter((s) => classifyStatus(s) === STATUS_TYPES.HOLD)
  holdStatuses.forEach((holdStatus) => {
    const canResume = Object.keys(transitions).some(
      (target) =>
        transitions[target].includes(holdStatus) && !isTerminalStatus(target),
    )

    if (!canResume) {
      warnings.push({
        code: VALIDATION_CODES.MISSING_HOLD_RESUME,
        message: i18n.global.t('workflow.validation.missingHoldResume', { status: holdStatus }),
        severity: SEVERITY.WARNING,
        details: { status: holdStatus },
      })
    }
  })

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  }
}

function findReachableStatuses(
  statuses: string[],
  transitions: Record<string, string[]>,
): Set<string> {
  const reachable = new Set<string>()
  const startStatus = statuses.find((s) => isStartStatus(s))

  if (!startStatus) {
    return reachable
  }

  const queue: string[] = [startStatus]
  reachable.add(startStatus)

  const outgoing: Record<string, string[]> = {}
  statuses.forEach((s) => {
    outgoing[s] = []
  })

  Object.entries(transitions).forEach(([target, sources]) => {
    sources.forEach((source) => {
      if (outgoing[source]) {
        outgoing[source].push(target)
      }
    })
  })

  while (queue.length > 0) {
    const current = queue.shift()
    if (current === undefined) break
    const targets = outgoing[current] || []

    targets.forEach((target) => {
      if (!reachable.has(target)) {
        reachable.add(target)
        queue.push(target)
      }
    })
  }

  return reachable
}

function findDuplicates(arr: string[]): string[] {
  const seen = new Set<string>()
  const duplicates = new Set<string>()

  arr.forEach((item) => {
    if (seen.has(item)) {
      duplicates.add(item)
    }
    seen.add(item)
  })

  return Array.from(duplicates)
}

function isValidStatusName(name: unknown): boolean {
  if (!name || typeof name !== 'string') return false
  return /^[A-Z][A-Z0-9_]*$/.test(name)
}

export function getValidationMessage(code: ValidationCode | string): string {
  const messages: Record<string, string> = {
    [VALIDATION_CODES.NO_ENTRY_POINT]: i18n.global.t('workflow.validation.fix.noEntryPoint'),
    [VALIDATION_CODES.NO_TERMINAL_STATUS]: i18n.global.t('workflow.validation.fix.noTerminalStatus'),
    [VALIDATION_CODES.ORPHAN_STATUS]: i18n.global.t('workflow.validation.fix.orphanStatus'),
    [VALIDATION_CODES.DEAD_END_STATUS]: i18n.global.t('workflow.validation.fix.deadEndStatus'),
    [VALIDATION_CODES.SELF_TRANSITION]: i18n.global.t('workflow.validation.fix.selfTransition'),
    [VALIDATION_CODES.EMPTY_WORKFLOW]: i18n.global.t('workflow.validation.fix.emptyWorkflow'),
    [VALIDATION_CODES.UNREACHABLE_TERMINAL]: i18n.global.t('workflow.validation.fix.unreachableTerminal'),
    [VALIDATION_CODES.MISSING_HOLD_RESUME]: i18n.global.t('workflow.validation.fix.missingHoldResume'),
    [VALIDATION_CODES.DUPLICATE_STATUS]: i18n.global.t('workflow.validation.fix.duplicateStatus'),
    [VALIDATION_CODES.INVALID_STATUS_NAME]: i18n.global.t('workflow.validation.fix.invalidStatusName'),
  }

  return messages[code] || i18n.global.t('workflow.validation.unknownIssue')
}

export default {
  validateWorkflow,
  SEVERITY,
  VALIDATION_CODES,
  getValidationMessage,
}
